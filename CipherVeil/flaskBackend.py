# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import re
import sys
from faker import Faker
# pyrefly: ignore [missing-import]
from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerResult
# pyrefly: ignore [missing-import]
from presidio_anonymizer import AnonymizerEngine

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension

# Initialize Faker
fake = Faker()

# Directory to store mapping files
MAPPINGS_DIR = 'mappings'
os.makedirs(MAPPINGS_DIR, exist_ok=True)

# Path to the ChatGPT mapping file
CHATGPT_MAPPING_FILE = os.path.join(MAPPINGS_DIR, "chatgpt.json")
GENERIC_URL = "https://chatgpt.com/"

# Custom Presidio recognizer for conversational and casual name contexts
class EnhancedPersonRecognizer(EntityRecognizer):
    def __init__(self):
        super().__init__(supported_entities=['PERSON'], name='EnhancedPersonRecognizer')
        self.greetings = re.compile(r'\b(?:hey+|hi+|hello+|dear|hola|howdy|yo+)\s+([A-Za-z0-9_-]+)', re.IGNORECASE)
        self.intros = re.compile(r'\b(?:i\s+am|my\s+name\s+is|this\s+is|call\s+me|i\'m|im)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', re.IGNORECASE)
        self.common_names = {
            'sam', 'sami', 'samvritha', 'devarajan', 'shashank', 'singh',
            'rahul', 'priya', 'aarav', 'ananya', 'alex', 'john', 'david',
            'sarah', 'emily', 'michael', 'jessica', 'karen', 'robert'
        }
        
    def load(self):
        pass
        
    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        if 'PERSON' not in entities:
            return results
            
        # 1. Names following greetings (e.g., "HEYYYY SAMMMM", "hey alex")
        for match in self.greetings.finditer(text):
            word = match.group(1)
            # Avoid matching words like "there", "everyone", "guys", "all"
            if word.lower() not in {'there', 'everyone', 'everybody', 'guys', 'all', 'bot', 'assistant'}:
                results.append(RecognizerResult(
                    entity_type='PERSON',
                    start=match.start(1),
                    end=match.end(1),
                    score=0.95
                ))
            
        # 2. Names following introductions (e.g., "I am Samvritha Devarajan", "My name is John")
        for match in self.intros.finditer(text):
            results.append(RecognizerResult(
                entity_type='PERSON',
                start=match.start(1),
                end=match.end(1),
                score=0.95
            ))
            
        # 3. Common names and repeated-letter names (e.g., "SAMMMM" -> "sam")
        for word_match in re.finditer(r'\b([A-Za-z]{2,})\b', text):
            word = word_match.group(1)
            norm = re.sub(r'(.)\1+', r'\1', word.lower())
            if word.lower() in self.common_names or norm in self.common_names:
                results.append(RecognizerResult(
                    entity_type='PERSON',
                    start=word_match.start(1),
                    end=word_match.end(1),
                    score=0.92
                ))
                
        return results

# Initialize Presidio engines
analyzer = AnalyzerEngine()
analyzer.registry.add_recognizer(EnhancedPersonRecognizer())
anonymizer = AnonymizerEngine()

def normalize_url(url):
    """Strip query parameters, fragments, and trailing slashes for stable mapping lookups."""
    if not url:
        return GENERIC_URL
    clean = url.split('?')[0].split('#')[0].rstrip('/')
    return clean if clean else GENERIC_URL

def extract_conv_id(url):
    """Extract conversation ID from a ChatGPT URL."""
    if not url:
        return None
    match = re.search(r'chatgpt\.com/c/([a-zA-Z0-9-]+)', url)
    return match.group(1) if match else None

def filter_overlapping_spans(analyzer_results):
    """Resolve and deduplicate overlapping entity spans, prioritizing higher confidence."""
    sorted_results = sorted(analyzer_results, key=lambda x: (x.start, -x.score, -(x.end - x.start)))
    filtered = []
    last_end = -1
    for r in sorted_results:
        if r.start >= last_end:
            filtered.append(r)
            last_end = r.end
        else:
            if filtered and r.score > filtered[-1].score:
                filtered[-1] = r
                last_end = r.end
    return filtered

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

@app.route('/status', methods=['POST'])
def update_status():
    data = request.json or {}
    enabled = data.get('extensionEnabled', True)
    app.config['EXTENSION_ENABLED'] = enabled
    print(f"Extension status updated: {'Enabled' if enabled else 'Disabled'}", flush=True)
    return jsonify({"status": "ok", "extensionEnabled": enabled})

@app.route('/get_mappings', methods=['GET'])
def get_mappings():
    """Return all mappings from the JSON file"""
    mappings = load_chatgpt_mappings()
    return jsonify(mappings)

def get_fake_value(entity_type, original_value):
    """Generate appropriate fake value based on entity type and preserve formatting."""
    is_upper = original_value.isupper()
    is_single = " " not in original_value.strip()

    if entity_type == "PERSON":
        val = fake.first_name() if is_single else fake.name()
        return val.upper() if is_upper else val
    elif entity_type == "EMAIL_ADDRESS":
        return fake.email()
    elif entity_type == "PHONE_NUMBER":
        return fake.phone_number()
    elif entity_type == "CREDIT_CARD":
        return fake.credit_card_number()
    elif entity_type == "US_SSN":
        return fake.ssn()
    elif entity_type == "US_BANK_NUMBER":
        return fake.bban()
    elif entity_type == "LOCATION":
        return fake.city()
    elif entity_type == "IP_ADDRESS":
        return fake.ipv4()
    elif entity_type == "DATE_TIME":
        return fake.date()
    else:
        return f"FAKE_{entity_type}"

def load_chatgpt_mappings():
    """Load existing ChatGPT mappings or create an empty dict if file doesn't exist"""
    if os.path.exists(CHATGPT_MAPPING_FILE):
        try:
            with open(CHATGPT_MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_chatgpt_mappings(mappings):
    """Save ChatGPT mappings to file"""
    try:
        with open(CHATGPT_MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=2)
        print(f"Successfully saved mappings to {CHATGPT_MAPPING_FILE}", flush=True)
        return True
    except Exception as e:
        print(f"Error saving mappings: {e}", flush=True)
        return False

@app.route('/config', methods=['POST'])
def update_config():
    """Update the anonymization configuration"""
    try:
        config = request.json or {}
        print(f"Received configuration update: {config}", flush=True)
        app.config['ANONYMIZATION_CONFIG'] = config

        entity_mapping = {
            "Names": "PERSON",
            "Emails": "EMAIL_ADDRESS",
            "Phone Numbers": "PHONE_NUMBER",
            "Addresses": "LOCATION",
            "SSN": "US_SSN"
        }
        
        selected_entities = []
        for pii in config.get('piis', []):
            if pii in entity_mapping:
                selected_entities.append(entity_mapping[pii])
        
        if not selected_entities:
            selected_entities = list(entity_mapping.values())
        
        app.config['SELECTED_ENTITIES'] = selected_entities
        
        if "Pseudonymization" in config.get('methods', []):
            app.config['ANONYMIZATION_METHOD'] = "fake"
        elif "Redacting" in config.get('methods', []):
            app.config['ANONYMIZATION_METHOD'] = "redact"
        else:
            app.config['ANONYMIZATION_METHOD'] = "fake"
        
        return jsonify({"status": "Configuration updated successfully", "config": config})
    except Exception as e:
        print(f"Error updating configuration: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/anonymize', methods=['POST'])
def anonymize_text():
    data = request.json or {}
    print(f"Received anonymize request: {data}", flush=True)
    
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided"}), 400
    
    text = data['text']
    raw_url = data.get('url', '')
    url = normalize_url(raw_url)
    
    # Check for direct request-level anonymization method and PIIs
    entity_mapping = {
        "Names": "PERSON",
        "Emails": "EMAIL_ADDRESS",
        "Phone Numbers": "PHONE_NUMBER",
        "Addresses": "LOCATION",
        "SSN": "US_SSN"
    }

    if data.get('piis'):
        selected_entities = [entity_mapping[p] for p in data['piis'] if p in entity_mapping]
    else:
        selected_entities = app.config.get('SELECTED_ENTITIES', list(entity_mapping.values()))
    
    if not selected_entities:
        selected_entities = list(entity_mapping.values())

    if data.get('anonymization_method'):
        anonymization_method = data.get('anonymization_method')
    else:
        anonymization_method = app.config.get('ANONYMIZATION_METHOD', 'fake')
    
    if anonymization_method not in ['redact', 'fake']:
        anonymization_method = 'fake'
    
    # Presidio analysis
    analyzer_results = analyzer.analyze(
        text=text,
        entities=selected_entities,
        language="en"
    )

    # Filter out overlapping spans
    filtered_results = filter_overlapping_spans(analyzer_results)
    
    value_mapping = {}  # Maps original -> replacement
    mapping = {}        # Maps replacement -> original (for de-anonymization)
    
    for result in filtered_results:
        entity_type = result.entity_type
        original_value = text[result.start:result.end]
        
        if original_value not in value_mapping:
            if anonymization_method == "redact":
                replacement = f"[REDACTED_{entity_type}]"
            else:
                replacement = get_fake_value(entity_type, original_value)
            
            value_mapping[original_value] = replacement
            mapping[replacement] = original_value
    
    # Apply replacements from right to left to preserve offsets
    anonymized_text = text
    for result in sorted(filtered_results, key=lambda x: x.start, reverse=True):
        original_value = text[result.start:result.end]
        replacement = value_mapping.get(original_value, original_value)
        anonymized_text = anonymized_text[:result.start] + replacement + anonymized_text[result.end:]
    
    # Store mappings
    mappings = load_chatgpt_mappings()
    new_entry = {
        "anonymization_method": anonymization_method,
        "mapping": mapping,
        "config": data.get('config', {})
    }
    
    conv_id = extract_conv_id(url)

    # Associate with exact normalized url
    if url not in mappings:
        mappings[url] = []
    mappings[url].append(new_entry)

    # Also associate under conversation ID key if available for foolproof lookup
    if conv_id:
        conv_key = f"conv:{conv_id}"
        if conv_key not in mappings:
            mappings[conv_key] = []
        mappings[conv_key].append(new_entry)

    # Always keep generic fallback updated
    if GENERIC_URL not in mappings:
        mappings[GENERIC_URL] = []
    mappings[GENERIC_URL].append(new_entry)

    save_chatgpt_mappings(mappings)
    
    print(f"Anonymized text: '{text}' -> '{anonymized_text}' (mappings: {mapping})", flush=True)
    return jsonify({
        "anonymized_text": anonymized_text,
        "mapping": mapping,
        "anonymization_method": anonymization_method
    })

@app.route('/deanonymize', methods=['POST'])
def deanonymize_text():
    data = request.json or {}
    print(f"Deanonymize request: {data}", flush=True)
    
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided"}), 400
    
    text = data['text']
    chat_url = normalize_url(data.get('url', ''))
    conv_id = extract_conv_id(chat_url)
    
    mappings = load_chatgpt_mappings()
    url_mappings = []

    # Priority 1: match exact normalized URL
    if chat_url in mappings:
        url_mappings = mappings[chat_url]
    # Priority 2: match by conversation ID
    elif conv_id and f"conv:{conv_id}" in mappings:
        url_mappings = mappings[f"conv:{conv_id}"]
    # Priority 3: fallback to generic URL
    elif GENERIC_URL in mappings:
        url_mappings = mappings[GENERIC_URL]
    # Priority 4: fallback to the most recent URL mappings
    elif len(mappings) > 0:
        url_mappings = list(mappings.values())[-1]
    
    if not url_mappings:
        return jsonify({"deanonymized_text": text, "anonymization_method": "none"})
    
    deanonymized_text = text
    anonymization_method = "unknown"
    
    for mapping_entry in reversed(url_mappings):
        current_mapping = mapping_entry.get("mapping", {})
        anonymization_method = mapping_entry.get("anonymization_method", "unknown")
        for anonymized, original in current_mapping.items():
            deanonymized_text = deanonymized_text.replace(anonymized, original)
            
    return jsonify({
        "deanonymized_text": deanonymized_text,
        "anonymization_method": anonymization_method
    })

if __name__ == '__main__':
    print("Starting CipherVeil Flask Backend on http://127.0.0.1:5000", flush=True)
    app.run(debug=True, port=5000)