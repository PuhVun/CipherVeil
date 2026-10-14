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
    
    const response = await fetch('http://localhost:5000/get_mappings');
    if (!response.ok) {
      throw new Error(`Failed to fetch mappings: ${response.status} ${response.statusText}`);
    }
    
    mappingsCache = await response.json();
    lastFetchTime = currentTime;
    
    return mappingsCache;
  } catch (error) {
    console.error('Error fetching mappings:', error);
    throw error;
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

      fetch('http://localhost:5000/anonymize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: request.text,
          url: request.url,
          anonymization_method: method,
          piis: piis
        }),
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`API responded with status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        const processedText = data.anonymized_text || data.text || request.text;
        const changed = processedText !== request.text;
        sendResponse({ 
          processedText: processedText,
          changed: changed,
          mappingCount: Object.keys(data.mapping || {}).length
        });
        
        // Reset cache so new mapping is immediately available
        mappingsCache = null;
        lastFetchTime = 0;
        
        // After successful anonymization, fetch the latest mappings and notify content script
        fetchMappings(true).then(mappings => {
          if (sender && sender.tab && sender.tab.id) {
            chrome.tabs.sendMessage(sender.tab.id, {
              action: 'updateMappings',
              mappings: mappings
            });
          }
        });
      })
      .catch(error => {
        console.error('Error in background script:', error);
        sendResponse({ error: error.message });
      });
    });
    
    // Return true to indicate that the response will be sent asynchronously
    return true;
  }
  
  if (request.action === 'getMappings') {
    fetchMappings()
      .then(mappings => {
        sendResponse({ mappings });
      })
      .catch(error => {
        sendResponse({ error: error.message });
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
  console.log('Extension installed or updated. Fetching initial mappings...');
  fetchMappings().catch(err => console.error('Initial mappings fetch failed:', err));
});