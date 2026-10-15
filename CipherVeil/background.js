// background.js - Handles API requests from the content script

// Global variable to store mappings
let mappingsCache = null;
let lastFetchTime = 0;
const CACHE_TTL = 3000; // 30 seconds in milliseconds

// Function to fetch mappings from the backend
async function fetchMappings(force = false) {
  try {
    const currentTime = Date.now();
    
    // Use cached mappings if they exist, aren't too old, and not forced
    if (!force && mappingsCache && (currentTime - lastFetchTime < CACHE_TTL)) {
      return mappingsCache;
    }
    
    const response = await fetch('http://127.0.0.1:5000/get_mappings', {
      signal: AbortSignal.timeout(2500)
    });
    if (!response.ok) {
      return mappingsCache || {};
    }
    
    mappingsCache = await response.json();
    lastFetchTime = currentTime;
    
    return mappingsCache;
  } catch (error) {
    // Graceful fallback when backend is temporarily offline or booting
    // Avoid console.error so Chrome does not log red alerts on chrome://extensions
    return mappingsCache || {};
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'processText') {
    chrome.storage.local.get(['extensionEnabled', 'methods', 'piis'], (stored) => {
      if (stored && stored.extensionEnabled === false) {
        sendResponse({ processedText: request.text, disabled: true });
        return;
      }

      const method = (stored && stored.methods && stored.methods.includes('Redacting')) ? 'redact' : 'fake';
      const piis = (stored && stored.piis && stored.piis.length > 0) 
        ? stored.piis 
        : ["Names", "Emails", "Phone Numbers", "Addresses", "SSN"];

      fetch('http://127.0.0.1:5000/task_aware_transform', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: request.text,
          url: request.url,
          config: stored || {}
        }),
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`API responded with status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        const processedText = data.sanitized_text || data.text || request.text;
        const changed = processedText !== request.text;
        console.log('[CipherVeil Background] Task:', data.task_type, '| Strategy:', data.privacy_strategy);
        console.log('[CipherVeil Background] Raw:', request.text);
        console.log('[CipherVeil Background] Shielded:', processedText);
        if (data.can_answer_locally) {
          console.log('[CipherVeil Background] Can Answer Locally:', data.local_answer);
        }

        sendResponse({ 
          processedText: processedText,
          changed: changed,
          canAnswerLocally: !!data.can_answer_locally,
          localAnswer: data.local_answer,
          taskType: data.task_type,
          privacyStrategy: data.privacy_strategy,
          privacyExplanation: data.privacy_explanation,
          mappingCount: Object.keys(data.mappings || {}).length,
          detectedEntities: data.detected_entities || [],
          requiresUserReview: !!data.requires_user_review
        });
        
        // Reset cache so new mapping is immediately available
        mappingsCache = null;
        lastFetchTime = 0;
        
        // After successful anonymization, fetch the latest mappings and notify content script
        fetchMappings(true).then(mappings => {
          if (sender && sender.tab && sender.tab.id) {
            try {
              const res = chrome.tabs.sendMessage(sender.tab.id, {
                action: 'updateMappings',
                mappings: mappings
              });
              if (res && typeof res.catch === 'function') {
                res.catch(() => {});
              }
            } catch (e) {
              // Tab may have closed or navigated
            }
          }
        }).catch(() => {});
      })
      .catch(error => {
        console.warn('[CipherVeil Background] Backend service unreachable:', error.message);
        sendResponse({ error: error.message, processedText: request.text });
      });
    });
    
    // Return true to indicate that the response will be sent asynchronously
    return true;
  }
  
  if (request.action === 'getMappings') {
    fetchMappings()
      .then(mappings => {
        sendResponse({ mappings: mappings || {} });
      })
      .catch(() => {
        sendResponse({ mappings: mappingsCache || {} });
      });
    
    // Return true to indicate that the response will be sent asynchronously
    return true;
  }

  if (request.action === 'getSettings') {
    chrome.storage.local.get(['sites', 'models', 'methods', 'piis', 'extensionEnabled'], (result) => {
      sendResponse(result || {});
    });
    return true;
  }
});

// When extension is installed or updated
chrome.runtime.onInstalled.addListener(() => {
  console.log('[CipherVeil] Extension installed or updated. Initializing connection to 127.0.0.1:5000...');
  fetchMappings().catch(err => console.warn('[CipherVeil] Initial mappings fetch deferred (start backend if not running):', err.message));
});