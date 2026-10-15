<div align="center">

# 🛡️ CipherVeil

**Protect your privacy while unleashing the full power of AI.**  
*A lightweight, intelligent browser extension that auto-detects, redacts, and pseudonymizes sensitive data before it reaches LLMs—and transparently de-anonymizes model responses.*

[![Manifest V3](https://img.shields.io/badge/Manifest-V3-brightgreen.svg)](https://developer.chrome.com/docs/extensions/mv3/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-black.svg)](https://flask.palletsprojects.com/)
[![Presidio](https://img.shields.io/badge/Microsoft-Presidio-0078D4.svg)](https://microsoft.github.io/presidio/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](CipherVeil/LICENSE)

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Chrome Extension Setup](#2-chrome-extension-setup)
- [Usage Guide](#-usage-guide)
- [Supported PII Entities](#-supported-pii-entities)
- [Task-Aware Privacy Pipeline](#-task-aware-privacy-pipeline)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 💡 Overview

As AI models like **ChatGPT**, **Claude**, and **Gemini** become integral to our daily workflows, confidential and personally identifiable information (PII) is frequently shared without realizing the privacy and compliance risks.

**CipherVeil** bridges this gap by acting as a real-time privacy layer between you and AI services:
- **Pre-flight Anonymization**: Before your prompt leaves your browser, sensitive entities (names, phone numbers, emails, financial records, dates of birth, etc.) are detected and safely transformed using realistic pseudonymization or redaction.
- **Transparent De-anonymization**: When the AI responds, CipherVeil automatically maps the synthetic entities back to your original data on the fly—giving you accurate, readable answers without ever exposing your private details to external servers.

---

## ✨ Key Features

- **🔒 Real-Time Client-Side Interception**: Seamlessly captures prompt inputs in ChatGPT and replaces sensitive tokens before transmission.
- **🎭 Dual Transformation Strategies**:
  - **Pseudonymization**: Replaces sensitive data with realistic, context-preserving synthetic entities via Faker.
  - **Redaction**: Replaces tokens with explicit markers (e.g. `<PERSON>`, `<EMAIL_ADDRESS>`).
- **🔄 Bidirectional Mapping & Restoration**: Maintains local conversation mappings so the AI's responses are restored to your original values automatically.
- **🧠 Hybrid Detection Engines**:
  - **Microsoft Presidio Analyzer**: High-accuracy NER with custom pattern recognizers.
  - **Enhanced Person Recognizer**: Specialized detection for casual greetings and multi-regional name patterns.
  - **Local On-Device LLM Support**: Optional local detection using Ollama / Mistral 3B.
  - **Task-Aware Pipeline**: Dynamically chooses transformation policies based on task context (e.g., utility vs. privacy trade-offs).
- **🎛️ Interactive Popup Control**:
  - Global ON/OFF toggle with live status badge.
  - Granular selection of PII categories to shield.
  - Quick switching between Anonymization methods and Masking styles.
  - One-click cache and mapping cleanup.

---

## 🔄 How It Works

```
 [User Input] 
      │
      ▼
┌─────────────────────────┐
│  Chrome Content Script  │  ── Intercepts prompt submission
└────────────┬────────────┘
             │ (HTTP POST /anonymize or /task_aware_transform)
             ▼
┌─────────────────────────┐
│   Flask Local Backend   │  ── Presidio / Custom NER / Task-Aware Policy
└────────────┬────────────┘
             │
             ├── Stores synthetic-to-original mappings locally
             │
             ▼
┌─────────────────────────┐
│   Anonymized Prompt     │  ── Submits safely to ChatGPT / Claude
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       AI Model          │  ── Processes prompt with zero PII exposure
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   AI Model Response     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  De-Anonymization Step  │  ── Restores synthetic tokens to original values
└────────────┬────────────┘
             │
             ▼
 [User sees complete, private response]
```

---

## 🛠️ Architecture

| Component | Technology | Description |
|---|---|---|
| **Extension Frontend** | JavaScript (ES6+), HTML5, CSS3 | Manifest V3 content scripts, background service worker, and popup UI. |
| **Local API Server** | Python 3, Flask, Flask-CORS | Local REST API handling entity recognition, transformation, and storage. |
| **Entity Extraction** | Microsoft Presidio, spaCy (`en_core_web_sm`) | Rule-based and statistical natural language entity extraction. |
| **Data Synthesis** | Faker | Generates realistic synthetic names, locations, emails, and credentials. |
| **Task-Aware Engine** | Modular Python Pipeline | Intent classification, risk evaluation, and adaptive policy enforcement. |

---

## 📋 Prerequisites

Before setting up CipherVeil, ensure you have:
- **Python**: Version `3.9` or higher
- **Browser**: Google Chrome, Brave, Edge, or any Chromium-compatible browser
- **Git**: Installed on your system

---

## 🚀 Installation & Setup

### 1. Backend Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PuhVun/CipherVeil.git
   cd CipherVeil
   ```

2. **Create and activate a virtual environment** *(recommended)*:
   ```bash
   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install required dependencies**:
   ```bash
   pip install flask flask-cors faker presidio-analyzer presidio-anonymizer spacy requests
   python -m spacy download en_core_web_sm
   ```

4. **Launch the Flask backend**:
   ```bash
   # From inside the CipherVeil directory
   python flaskBackend.py
   ```
   *The backend will initialize and run on `http://127.0.0.1:5000`.*

---

### 2. Chrome Extension Setup

1. Open your browser and navigate to:
   ```
   chrome://extensions/
   ```
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `CipherVeil` project directory (where `manifest.json` is located).
5. The **CipherVeil** extension icon will now appear in your browser toolbar. Pin it for quick access!

---

## 🎯 Usage Guide

1. Ensure the Flask backend is running (`http://127.0.0.1:5000`).
2. Click the **CipherVeil** extension icon in your browser:
   - Ensure the shield is toggled **ON**.
   - Select your desired **Anonymization Method** (e.g., *General Anonymization* or *Task-Aware*).
   - Choose your preferred **Masking Type** (*Pseudonymize* or *Redact*).
   - Check the entity types you wish to protect.
3. Open [ChatGPT](https://chatgpt.com) or [Claude](https://claude.ai).
4. Type a prompt containing sensitive information, for example:
   > *"Hi, my name is Alex Carter. My email is alex.carter@example.com and my phone number is 415-555-0199. Can you help me format a cover letter?"*
5. Submit the prompt:
   - CipherVeil intercepts the message and anonymizes the entities.
   - The AI receives sanitized tokens (e.g. *Jordan Hayes*, *jordan.hayes@example.org*).
   - Once the response arrives, CipherVeil automatically restores your real information in the view.

---

## 🛡️ Supported PII Entities

CipherVeil provides out-of-the-box detection and masking for:

- 👤 **Names / Individuals** (`PERSON`)
- 📧 **Email Addresses** (`EMAIL_ADDRESS`)
- 📞 **Phone Numbers** (`PHONE_NUMBER`)
- 📍 **Locations & Addresses** (`LOCATION`)
- 🎂 **Dates of Birth** (`DATE_OF_BIRTH`)
- 💳 **Financial / Credit Cards** (`CREDIT_CARD`, `IBAN_CODE`)
- 🆔 **Identification Numbers** (`US_SSN`, `US_PASSPORT`, `US_DRIVER_LICENSE`)
- 🌐 **Network Identifiers** (`IP_ADDRESS`, `URL`)

---

## 🔬 Task-Aware Privacy Pipeline

CipherVeil includes an experimental **Task-Aware Privacy Engine** (`task_aware/`):
- **Intent & Task Classification**: Classifies prompts into task domains (e.g., Code Review, Financial Analysis, Medical Inquiry, Creative Writing).
- **Adaptive Policy Enforcement**: Applies context-specific privacy rules—retaining data necessary for task utility while masking genuinely sensitive identifiers.
- **Evaluation Suite**: Built-in benchmark evaluation framework (`/evaluate`) to measure utility preservation vs. privacy leak prevention.

---

## ❓ Troubleshooting

| Issue | Solution |
|---|---|
| **"Could not connect to anonymization server"** | Verify that `python flaskBackend.py` is running on `http://127.0.0.1:5000`. |
| **Extension context invalidated** | Refresh the ChatGPT or Claude tab after reloading the extension in `chrome://extensions`. |
| **spaCy model missing error** | Run `python -m spacy download en_core_web_sm` in your active Python environment. |
| **CORS errors** | The backend includes explicit CORS handling for `chrome-extension://` origins; make sure you are running the latest `flaskBackend.py`. |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See [LICENSE](CipherVeil/LICENSE) for more information.