// content.js - Chrome Extension Content Script for Automatic Anonymization & Deanonymization

// Global variable to store mappings
let deanonymizationMappings = {};
let isAutoSending = false;
let uiInterval = null;
let mappingInterval = null;
let domObserver = null;
let extensionInvalidated = false;
let keydownHandler = null;
let clickHandler = null;

// Catch and suppress uncaught extension context invalidated errors from orphaned content scripts
window.addEventListener('error', (event) => {
  if (event?.message?.includes('Extension context invalidated')) {
    event.preventDefault();
    event.stopImmediatePropagation();
    cleanupOnInvalidation();
  }
}, true);

window.addEventListener('unhandledrejection', (event) => {
  if (event?.reason?.message?.includes('Extension context invalidated')) {
    event.preventDefault();
    event.stopImmediatePropagation();
    cleanupOnInvalidation();
  }
}, true);

// Check whether the extension context is still valid (avoids errors after extension reload/update)
function isExtensionValid() {
  try {
    return !extensionInvalidated && typeof chrome !== 'undefined' && !!chrome.runtime && !!chrome.runtime.id;
  } catch {
    return false;
  }
}

// Safely send a message via chrome.runtime, catching invalidation errors
function safeSendMessage(message, callback) {
  if (!isExtensionValid()) {
    cleanupOnInvalidation();
    return;
  }
  try {
    chrome.runtime.sendMessage(message, (response) => {
      try {
        if (!isExtensionValid()) {
          cleanupOnInvalidation();
          return;
        }
        let lastErr = null;
        try {
          lastErr = chrome.runtime.lastError;
        } catch {
          cleanupOnInvalidation();
          return;
        }
        if (lastErr) {
          if (typeof callback === 'function') callback(null);
          return;
        }
        if (typeof callback === 'function') callback(response);
      } catch (err) {
        if (err?.message?.includes('Extension context invalidated')) {
          cleanupOnInvalidation();
        } else {
          console.warn('[CipherVeil] Error handling message response:', err);
        }
      }
    });
  } catch (err) {
    if (err?.message?.includes('Extension context invalidated')) {
      cleanupOnInvalidation();
    }
  }
}

// Cleanup timers, observers, and event listeners when the extension context is invalidated
function cleanupOnInvalidation() {
  if (extensionInvalidated) return;
  extensionInvalidated = true;
  if (uiInterval) { clearInterval(uiInterval); uiInterval = null; }
  if (mappingInterval) { clearInterval(mappingInterval); mappingInterval = null; }
  if (domObserver) { domObserver.disconnect(); domObserver = null; }
  if (keydownHandler) {
    document.removeEventListener('keydown', keydownHandler, true);
    keydownHandler = null;
  }
  if (clickHandler) {
    document.removeEventListener('click', clickHandler, true);
    clickHandler = null;
  }
  console.warn('CipherVeil: Extension context invalidated. Please refresh the page.');
}

// Default button markup
const defaultButtonContent = `
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
  <span>Auto-Shield On</span>
`;

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

function getPromptEditor() {
  return document.querySelector('#prompt-textarea, div.ProseMirror, div[contenteditable="true"]');
}

function getSendButton() {
  return document.querySelector(
    'button[data-testid="send-button"], ' +
    'button[data-testid="fruitjuice-send-button"], ' +
    'button[aria-label="Send prompt"], ' +
    'button[aria-label="Send message"], ' +
    'button[aria-label*="Send"], ' +
    'button[aria-label*="send"], ' +
    'form button[type="submit"]'
  );
}

// Safely update ProseMirror editor content so ChatGPT internal state recognizes changes
function setEditorText(editor, newText) {
  if (!editor || !isExtensionValid()) return;
  
  try {
    editor.focus();
  } catch (e) {
    if (e?.message?.includes('Extension context invalidated')) {
      cleanupOnInvalidation();
      return;
    }
  }

  // 1. Try modern DataTransfer synthetic paste event (supported natively by ProseMirror)
  try {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    const dataTransfer = new DataTransfer();
    dataTransfer.setData('text/plain', newText);

    const selection = window.getSelection();
    if (selection) {
      const range = document.createRange();
      range.selectNodeContents(editor);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    const pasteEvent = new ClipboardEvent('paste', {
      clipboardData: dataTransfer,
      bubbles: true,
      cancelable: true,
      composed: true
    });

    editor.dispatchEvent(pasteEvent);
  } catch (e) {
    if (e?.message?.includes('Extension context invalidated')) {
      cleanupOnInvalidation();
      return;
    }
    console.warn('Synthetic paste event error, trying execCommand', e);
  }

  if (!isExtensionValid()) { cleanupOnInvalidation(); return; }

  // 2. If text didn't update to newText, try execCommand insertText
  if (editor.textContent.trim() !== newText.trim()) {
    try {
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, newText);
    } catch (e) {
      if (e?.message?.includes('Extension context invalidated')) {
        cleanupOnInvalidation();
        return;
      }
      console.warn('execCommand insertText failed, falling back to innerHTML', e);
    }
  }

  if (!isExtensionValid()) { cleanupOnInvalidation(); return; }

  // 3. Fallback innerHTML
  if (editor.textContent.trim() !== newText.trim()) {
    try {
      const formattedHTML = newText
        .split('\n')
        .map(line => `<p>${line === '' ? '<br>' : escapeHTML(line)}</p>`)
        .join('');
      editor.innerHTML = formattedHTML;
    } catch (e) {
      if (e?.message?.includes('Extension context invalidated')) {
        cleanupOnInvalidation();
        return;
      }
    }
  }

  if (!isExtensionValid()) { cleanupOnInvalidation(); return; }

  // 4. Dispatch InputEvent & keyup so ProseMirror, React, and ChatGPT re-render and enable Send button
  try {
    editor.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertText',
      data: newText
    }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));
    editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
  } catch (e) {
    if (e?.message?.includes('Extension context invalidated')) {
      cleanupOnInvalidation();
    }
  }
}

// Fetch all mappings from background
function fetchMappings() {
  if (!isExtensionValid()) {
    cleanupOnInvalidation();
    return;
  }
  safeSendMessage({ action: 'getMappings' }, (response) => {
    if (response && response.mappings) {
      deanonymizationMappings = response.mappings;
      processResponses();
    }
  });
}

// Listen for mapping updates from background script
if (isExtensionValid()) {
  try {
    chrome.runtime.onMessage.addListener((message) => {
      if (!isExtensionValid()) {
        cleanupOnInvalidation();
        return;
      }
      if (message.action === 'updateMappings' && message.mappings) {
        deanonymizationMappings = message.mappings;
        resetDeanonymizationFlags();
        processResponses();
      }
    });
  } catch {
    cleanupOnInvalidation();
  }
}

// Aggregate all known mappings across the current URL and all sessions
function getAllMappings(currentUrl) {
  const combined = {};
  
  // 1. Prioritize current conversation / URL match
  const bestUrl = findBestUrlMatch(currentUrl);
  if (bestUrl && Array.isArray(deanonymizationMappings[bestUrl])) {
    deanonymizationMappings[bestUrl].forEach(entry => {
      if (entry && entry.mapping) {
        Object.assign(combined, entry.mapping);
      }
    });
  }
  
  // 2. Also pool all mappings for any chatgpt conversation in this session
  for (const [key, entries] of Object.entries(deanonymizationMappings)) {
    if (Array.isArray(entries)) {
      entries.forEach(entry => {
        if (entry && entry.mapping) {
          for (const [fakeVal, realVal] of Object.entries(entry.mapping)) {
            if (!combined[fakeVal]) {
              combined[fakeVal] = realVal;
            }
          }
        }
      });
    }
  }
  
  return combined;
}

// Function to find the best URL match for deanonymization
function findBestUrlMatch(currentUrl) {
  if (!currentUrl) return null;
  
  if (deanonymizationMappings[currentUrl]) return currentUrl;
  
  const cleanUrl = currentUrl.split('?')[0].split('#')[0].replace(/\/+$/, '');
  if (deanonymizationMappings[cleanUrl]) return cleanUrl;
  
  const match = currentUrl.match(/chatgpt\.com\/c\/([a-zA-Z0-9-]+)/);
  if (match) {
    const convId = match[1];
    if (deanonymizationMappings[`conv:${convId}`]) return `conv:${convId}`;
    for (const url in deanonymizationMappings) {
      if (url.includes(convId)) return url;
    }
  }
  
  if (deanonymizationMappings['https://chatgpt.com']) return 'https://chatgpt.com';
  if (deanonymizationMappings['https://chatgpt.com/']) return 'https://chatgpt.com/';
  
  const chatgptUrls = Object.keys(deanonymizationMappings).filter(u => u.includes('chatgpt.com'));
  if (chatgptUrls.length > 0) return chatgptUrls[chatgptUrls.length - 1];
  
  return null;
}

// De-anonymize text using all active mappings
function deanonymizeText(text, url) {
  if (!text || typeof text !== 'string') return text;
  
  const mappings = getAllMappings(url);
  const keys = Object.keys(mappings);
  if (keys.length === 0) return text;
  
  let deanonymizedText = text;
  
  // Sort keys from longest to shortest to prevent partial substring collisions
  const sortedKeys = keys.sort((a, b) => b.length - a.length);
  
  for (const anonymized of sortedKeys) {
    const original = mappings[anonymized];
    if (!anonymized || !original) continue;
    
    try {
      const escaped = anonymized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // For alphanumeric words use word boundaries; for emails/redactions match token directly
      const isWord = /^[A-Za-z0-9_]+$/.test(anonymized);
      const regex = isWord 
        ? new RegExp('\\b' + escaped + '\\b', 'gi')
        : new RegExp(escaped, 'gi');
      
      deanonymizedText = deanonymizedText.replace(regex, original);
    } catch (e) {
      deanonymizedText = deanonymizedText.split(anonymized).join(original);
    }
  }
  
  return deanonymizedText;
}

// Process responses and user messages that need deanonymization
function processResponses() {
  const currentUrl = window.location.href;
  const isStreaming = document.querySelector('button[aria-label="Stop generating"], button[data-testid="stop-button"], .result-streaming') !== null;
  
  // Assistant response selectors
  const assistantSelectors = [
    '[data-message-author-role="assistant"]',
    '.prose',
    '.markdown',
    '[data-testid*="conversation-turn-assistant"]'
  ];
  
  assistantSelectors.forEach(selector => {
    try {
      const elements = document.querySelectorAll(selector);
      elements.forEach(element => {
        if (!isStreaming && element.dataset.deanonymized === 'true') return;
        
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let node;
        let hasChanges = false;
        
        while (node = walker.nextNode()) {
          const original = node.nodeValue;
          const deanonymized = deanonymizeText(original, currentUrl);
          if (original !== deanonymized) {
            node.nodeValue = deanonymized;
            hasChanges = true;
          }
        }
        
        if (!isStreaming && hasChanges) {
          element.dataset.deanonymized = 'true';
        }
      });
    } catch (err) {
      console.warn('Error processing assistant responses:', err);
    }
  });

  // User sent message selectors
  const userSelectors = [
    '[data-message-author-role="user"]',
    '.whitespace-pre-wrap',
    '[data-testid*="conversation-turn-user"]'
  ];

  userSelectors.forEach(selector => {
    try {
      const elements = document.querySelectorAll(selector);
      elements.forEach(element => {
        if (element.dataset.deanonymized === 'true') return;
        
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let node;
        let hasChanges = false;
        
        while (node = walker.nextNode()) {
          const original = node.nodeValue;
          const deanonymized = deanonymizeText(original, currentUrl);
          if (original !== deanonymized) {
            node.nodeValue = deanonymized;
            hasChanges = true;
          }
        }
        
        if (hasChanges) {
          element.dataset.deanonymized = 'true';
        }
      });
    } catch (err) {
      console.warn('Error processing user messages:', err);
    }
  });
}

function resetDeanonymizationFlags() {
  document.querySelectorAll('[data-deanonymized="true"]').forEach(element => {
    element.dataset.deanonymized = 'false';
  });
}

// Core Automatic Shielding & Submission Handler
async function autoAnonymizeAndSend(editor, rawText, submitCallback) {
  const currentUrl = window.location.href;
  const statusBtn = document.getElementById('prosemirror-api-button');
  
  if (!isExtensionValid()) {
    cleanupOnInvalidation();
    // Fall through to original submission so the user isn't stuck
    if (typeof submitCallback === 'function') submitCallback();
    return;
  }
  
  if (statusBtn) {
    statusBtn.innerHTML = '<span>Auto-Shielding...</span>';
    statusBtn.style.borderColor = '#38bdf8';
  }
  
  safeSendMessage({
    action: 'processText',
    text: rawText,
    url: currentUrl
  }, (response) => {
    if (!isExtensionValid() || !response || response.error) {
      if (statusBtn) {
        statusBtn.innerHTML = '<span style="color:#ef4444;">⚠️ Backend Offline</span>';
        statusBtn.style.borderColor = '#ef4444';
        setTimeout(() => {
          if (statusBtn) {
            statusBtn.innerHTML = defaultButtonContent;
            statusBtn.style.borderColor = '#475569';
          }
        }, 3000);
      }
      return;
    }

    if (response.changed && response.processedText) {
      console.log('[CipherVeil] Shielded prompt:', rawText, '->', response.processedText);
      setEditorText(editor, response.processedText);
      if (statusBtn) {
        statusBtn.innerHTML = '<span style="color:#4ade80;">✓ Auto-Shielded!</span>';
        statusBtn.style.borderColor = '#4ade80';
        setTimeout(() => {
          if (statusBtn) {
            statusBtn.innerHTML = defaultButtonContent;
            statusBtn.style.borderColor = '#475569';
          }
        }, 2500);
      }
    } else {
      if (statusBtn) {
        statusBtn.innerHTML = defaultButtonContent;
        statusBtn.style.borderColor = '#475569';
      }
    }
    
    // Invalidate and refresh mappings immediately so responses are de-anonymized live
    fetchMappings();
    
    // Allow ProseMirror and React enough time (200ms) to sync virtual DOM state
    isAutoSending = true;
    setTimeout(() => {
      if (typeof submitCallback === 'function') {
        submitCallback();
      } else {
        const sendButton = getSendButton();
        if (sendButton && !sendButton.disabled) {
          sendButton.click();
        }
      }
      
      setTimeout(() => {
        isAutoSending = false;
      }, 500);
    }, 200);
  });
}

// Setup Automatic Event Interceptors on Enter key & Send button
function setupAutoInterceptors() {
  if (keydownHandler || clickHandler) return;

  // 1. Intercept Enter key on the ChatGPT prompt editor
  keydownHandler = (e) => {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    if (isAutoSending) return;
    
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      const editor = getPromptEditor();
      if (!editor) return;
      
      if (!editor.contains(e.target) && e.target !== editor) return;
      
      const text = (editor.textContent || editor.innerText || '').trim();
      if (!text) return;
      
      // Stop un-anonymized submission
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      
      autoAnonymizeAndSend(editor, text, () => {
        const sendButton = getSendButton();
        if (sendButton && !sendButton.disabled) {
          sendButton.click();
        } else {
          editor.focus();
          editor.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true
          }));
        }
      });
    }
  };

  // 2. Intercept mouse clicks on ChatGPT's Send button
  clickHandler = (e) => {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    if (isAutoSending) return;
    
    const sendBtn = e.target.closest(
      'button[data-testid="send-button"], ' +
      'button[data-testid="fruitjuice-send-button"], ' +
      'button[aria-label="Send prompt"], ' +
      'button[aria-label="Send message"], ' +
      'button[aria-label*="Send"], ' +
      'button[aria-label*="send"], ' +
      'form button[type="submit"]'
    );
    if (!sendBtn) return;
    
    const editor = getPromptEditor();
    if (!editor) return;
    
    const text = (editor.textContent || editor.innerText || '').trim();
    if (!text) return;
    
    // Stop un-anonymized click
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    
    autoAnonymizeAndSend(editor, text, () => {
      const btn = getSendButton() || sendBtn;
      btn.click();
    });
  };

  document.addEventListener('keydown', keydownHandler, true);
  document.addEventListener('click', clickHandler, true);
}

// Create and place the status button (allows optional manual click as well)
function createProcessButton() {
  if (document.getElementById('prosemirror-api-button')) return;
  
  const proseMirrorDiv = getPromptEditor();
  if (!proseMirrorDiv) return;
  
  const apiButton = document.createElement('button');
  apiButton.id = 'prosemirror-api-button';
  apiButton.title = 'CipherVeil: Automatically shields prompts before sending. Click to manual shield anytime.';
  apiButton.style.display = 'inline-flex';
  apiButton.style.alignItems = 'center';
  apiButton.style.justifyContent = 'center';
  apiButton.style.gap = '6px';
  apiButton.style.margin = '8px 4px';
  apiButton.style.padding = '6px 12px';
  apiButton.style.backgroundColor = '#1e293b';
  apiButton.style.color = '#f8fafc';
  apiButton.style.border = '1px solid #475569';
  apiButton.style.borderRadius = '20px';
  apiButton.style.cursor = 'pointer';
  apiButton.style.fontSize = '12px';
  apiButton.style.fontWeight = '500';
  apiButton.style.transition = 'all 0.2s ease';
  apiButton.style.boxShadow = '0 2px 4px rgba(0,0,0,0.15)';
  apiButton.style.zIndex = '100';

  apiButton.innerHTML = defaultButtonContent;

  const targetParent = proseMirrorDiv.parentNode;
  if (targetParent) {
    targetParent.insertBefore(apiButton, proseMirrorDiv.nextSibling);
  }
  
  apiButton.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const editor = getPromptEditor() || proseMirrorDiv;
    const text = (editor.textContent || editor.innerText || '').trim();
    if (!text) return;
    
    if (!isExtensionValid()) {
      cleanupOnInvalidation();
      alert('CipherVeil extension was reloaded. Please refresh the page.');
      return;
    }
    
    apiButton.innerHTML = '<span>Shielding...</span>';
    
    safeSendMessage({
      action: 'processText',
      text: text,
      url: window.location.href
    }, (response) => {
      if (response && response.changed) {
        console.log('[CipherVeil Manual] Shielded:', text, '->', response.processedText);
        try {
          setEditorText(editor, response.processedText);
        } catch (err) {
          console.warn('[CipherVeil] setEditorText error:', err);
        }
        apiButton.innerHTML = '<span style="color:#4ade80;">✓ Shielded!</span>';
        setTimeout(() => { apiButton.innerHTML = defaultButtonContent; }, 2500);
      } else {
        apiButton.innerHTML = '<span style="color:#fbbf24;">No PII Detected</span>';
        setTimeout(() => { apiButton.innerHTML = defaultButtonContent; }, 2000);
      }
      fetchMappings();
    });
  });
}

function ensureButtonExists() {
  if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
  if (!document.getElementById('prosemirror-api-button')) {
    createProcessButton();
  }
}

function startObserver() {
  if (!isExtensionValid()) return;
  const target = document.body || document.documentElement;
  if (!target) {
    setTimeout(startObserver, 100);
    return;
  }
  
  domObserver = new MutationObserver(() => {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    ensureButtonExists();
    processResponses();
  });
  
  domObserver.observe(target, {
    childList: true,
    subtree: true
  });
}

// Initial setup
async function initialize() {
  if (!isExtensionValid()) return;
  
  fetchMappings();
  ensureButtonExists();
  processResponses();
  setupAutoInterceptors();
  
  uiInterval = setInterval(() => {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    ensureButtonExists();
    processResponses();
  }, 1000);
  
  mappingInterval = setInterval(() => {
    if (!isExtensionValid()) { cleanupOnInvalidation(); return; }
    fetchMappings();
  }, 3000);
  
  startObserver();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}