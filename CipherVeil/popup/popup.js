// State of selection with default values
const state = {
  sites: ["Chatgpt"],
  models: ["Presidio"],  // Set Presidio as default
  methods: ["Pseudonymization"],  // Set Pseudonymization as default (assuming you meant this instead of "fake")
  piis: ["Names", "Emails", "Phone Numbers", "Addresses", "SSN"]  // All PIIs selected by default
};

// Dropdown elements
const dropdowns = [
  {
    name: 'sites',
    boxId: 'sitesBox',
    listId: 'sitesList',
    selectedId: 'selectedSites',
  },
  {
    name: 'models',
    boxId: 'modelsBox',
    listId: 'modelsList',
    selectedId: 'selectedModels',
  },
  {
    name: 'methods',
    boxId: 'methodsBox',
    listId: 'methodsList',
    selectedId: 'selectedMethods',
  },
  {
    name: 'piis',
    boxId: 'piisBox',
    listId: 'piisList',
    selectedId: 'selectedPIIs',
  }
];

// DOM elements
const statusIndicator = document.getElementById('statusIndicator');
const connectionStatus = document.getElementById('connectionStatus');
const checkConnectionBtn = document.getElementById('checkConnection');

// Load settings when the popup opens
document.addEventListener('DOMContentLoaded', () => {
  // Load settings directly from chrome.storage.local
  if (chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(['sites', 'models', 'methods', 'piis'], (stored) => {
      if (stored) {
        if (Array.isArray(stored.sites) && stored.sites.length > 0) state.sites = stored.sites;
        if (Array.isArray(stored.models) && stored.models.length > 0) state.models = stored.models;
        if (Array.isArray(stored.methods) && stored.methods.length > 0) state.methods = stored.methods;
        if (Array.isArray(stored.piis) && stored.piis.length > 0) state.piis = stored.piis;
      }
      
      // Setup dropdowns and UI
      setupDropdowns();
      updateAllSelections();
      sendConfigToBackend();
    });
  } else {
    setupDropdowns();
    updateAllSelections();
    sendConfigToBackend();
  }
  
  // Check connection to the Python backend
  checkConnection();
});

// Check connection to Python backend
checkConnectionBtn.addEventListener('click', checkConnection);

async function checkConnection() {
  try {
    // Use 127.0.0.1 to avoid macOS AirPlay receiver conflict on localhost:5000
    const response = await fetch('http://127.0.0.1:5000/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (response.ok) {
      statusIndicator.classList.add('active');
      connectionStatus.textContent = 'Connected to anonymization service';
    } else {
      statusIndicator.classList.remove('active');
      connectionStatus.textContent = 'Service unavailable';
    }
  } catch (error) {
    console.error('Connection check failed:', error);
    statusIndicator.classList.remove('active');
    connectionStatus.textContent = 'Cannot connect to service';
  }
}

// Setup dropdowns
function setupDropdowns() {
  dropdowns.forEach(dropdown => {
    const box = document.getElementById(dropdown.boxId);
    const list = document.getElementById(dropdown.listId);
    
    // Toggle dropdown on click
    box.addEventListener('click', (e) => {
      e.stopPropagation();
      list.classList.toggle('active');
      
      // Close other dropdowns
      dropdowns.forEach(otherDropdown => {
        if (otherDropdown.name !== dropdown.name) {
          document.getElementById(otherDropdown.listId).classList.remove('active');
        }
      });
    });
    
    // Handle checkbox changes
    const checkboxes = list.querySelectorAll('input[type="checkbox"]:not([disabled])');
    checkboxes.forEach(checkbox => {
      // Set initial state based on default values
      checkbox.checked = state[dropdown.name].includes(checkbox.value);
      
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        updateSelection(dropdown.name, checkbox.value, checkbox.checked);
      });
    });
  });
  
  // Close dropdowns when clicking outside
  document.addEventListener('click', () => {
    dropdowns.forEach(dropdown => {
      document.getElementById(dropdown.listId).classList.remove('active');
    });
  });
}

// Update selection state
function updateSelection(dropdownName, value, isSelected) {
  if (isSelected) {
    if (!state[dropdownName].includes(value)) {
      state[dropdownName].push(value);
    }
  } else {
    state[dropdownName] = state[dropdownName].filter(item => item !== value);
  }
  
  updateSelectionUI(dropdownName);
  
  // Save to storage
  const update = {};
  update[dropdownName] = state[dropdownName];
  chrome.storage.local.set(update, () => {
    console.log(`${dropdownName} settings updated:`, state[dropdownName]);
    sendConfigToBackend();
  });
}

// Update UI for a single dropdown
function updateSelectionUI(dropdownName) {
  // Look up the correct element ID from the dropdowns config to avoid casing issues
  // (e.g. "piis" would become "selectedPiis" dynamically, but the HTML has "selectedPIIs")
  const dd = dropdowns.find(d => d.name === dropdownName);
  const selectedContainer = dd
    ? document.getElementById(dd.selectedId)
    : document.getElementById(`selected${dropdownName.charAt(0).toUpperCase() + dropdownName.slice(1)}`);
  const placeholder = document.querySelector(`#${dropdownName}Box .placeholder`);
  
  if (!selectedContainer) {
    console.warn('CipherVeil: selectedContainer not found for dropdown:', dropdownName);
    return;
  }
  
  selectedContainer.innerHTML = '';
  
  if (state[dropdownName] && state[dropdownName].length > 0) {
    if (placeholder) placeholder.style.display = 'none';
    
    state[dropdownName].forEach(item => {
      const tag = document.createElement('span');
      tag.className = 'selected-tag';
      tag.innerHTML = `${item} <span class="remove">×</span>`;
      
      tag.querySelector('.remove').addEventListener('click', (e) => {
        e.stopPropagation();
        updateSelection(dropdownName, item, false);
      });
      
      selectedContainer.appendChild(tag);
    });
  } else {
    if (placeholder) placeholder.style.display = 'inline';
  }
  
  // Update checkboxes to match state
  const list = dd
    ? document.getElementById(dd.listId)
    : document.getElementById(`${dropdownName}List`);
  if (!list) return;
  const checkboxes = list.querySelectorAll('input[type="checkbox"]');
  checkboxes.forEach(checkbox => {
    checkbox.checked = state[dropdownName] && state[dropdownName].includes(checkbox.value);
  });
}

// Update all selections UI
function updateAllSelections() {
  dropdowns.forEach(dropdown => {
    updateSelectionUI(dropdown.name);
  });
}

// Send configuration to backend
async function sendConfigToBackend() {
  try {
    const config = {
      sites: state.sites,
      models: state.models,
      methods: state.methods,
      piis: state.piis
    };
    
    console.log('Sending config to backend:', config);
    
    const response = await fetch('http://127.0.0.1:5000/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config)
    });
    
    if (response.ok) {
      console.log('Configuration sent to backend successfully');
    } else {
      console.error('Failed to send configuration to backend');
    }
  } catch (error) {
    console.error('Error sending configuration to backend:', error);
  }
}

// Toggle functionality
document.addEventListener('DOMContentLoaded', () => {
  const toggleSwitch = document.getElementById('extensionToggle');
  const toggleStatus = document.getElementById('toggleStatus');
  
  // Load the saved state
  chrome.storage.local.get(['extensionEnabled'], (result) => {
    // Default to enabled if not set
    const isEnabled = result.extensionEnabled !== undefined ? result.extensionEnabled : true;
    toggleSwitch.checked = isEnabled;
    updateToggleUI(isEnabled);
  });
  
  // Handle toggle changes
  toggleSwitch.addEventListener('change', () => {
    const isEnabled = toggleSwitch.checked;
    
    // Update UI
    updateToggleUI(isEnabled);
    
    // Save state
    chrome.storage.local.set({ extensionEnabled: isEnabled }, () => {
      console.log(`Extension ${isEnabled ? 'enabled' : 'disabled'}`);
    });
    
    // Send to backend
    sendExtensionStatusToBackend(isEnabled);
  });
});

// Update toggle UI based on state
function updateToggleUI(isEnabled) {
  const toggleStatus = document.getElementById('toggleStatus');
  
  if (isEnabled) {
    toggleStatus.textContent = 'Enabled';
    toggleStatus.className = 'status-text enabled';
  } else {
    toggleStatus.textContent = 'Disabled';
    toggleStatus.className = 'status-text disabled';
  }
}

// Send extension status to backend
async function sendExtensionStatusToBackend(isEnabled) {
  try {
    const response = await fetch('http://127.0.0.1:5000/status', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ extensionEnabled: isEnabled })
    });
    
    if (response.ok) {
      console.log(`Extension status sent to backend: ${isEnabled}`);
    } else {
      console.error('Failed to send extension status to backend');
    }
  } catch (error) {
    console.error('Error sending extension status to backend:', error);
  }
}