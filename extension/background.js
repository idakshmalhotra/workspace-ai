// Workspace AI Focus Guard - Background Service Worker (MV3)
// Enforces allowlist/blocklist; simple YouTube heuristic.

const DEFAULT_ALLOW = [
  'wikipedia.org',
  'khanacademy.org',
  'coursera.org',
  'edx.org',
  'docs.google.com',
  'stackoverflow.com',
  'stackexchange.com',
  'unacademy.com',
  'physicswallah.live',
  'pw.live',
  'youtube.com', // filtered by title
];
const DEFAULT_BLOCK = ['instagram.com', 'instagr.am'];

const YT_KEYWORDS = [
  'lecture','tutorial','course','class','chapter','gate','jee','neet',
  'math','physics','chemistry','biology','dsa','algorithm','programming',
  'computer science','notes','learn','educational','education','study'
];

const STATE = {
  allow: new Set(DEFAULT_ALLOW),
  block: new Set(DEFAULT_BLOCK),
  enabled: true,
  backendRulesUrl: null, // e.g., http://localhost:5001/api/enforcement/rules
  actionMode: 'close', // 'close' | 'redirect'
  redirectUrl: 'https://www.youtube.com/results?search_query=study+lecture',
  lockedDomain: null,
  previousAllow: null,
  lockedUrl: null,
  requiredKeyword: '',
  disallowedKeywords: [],
};

function domainFromUrl(url) {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

function getYouTubeVideoId(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, '');
    if (host === 'youtu.be') {
      // Short link: https://youtu.be/VIDEOID
      return u.pathname.slice(1);
    }
    if (host.endsWith('youtube.com')) {
      if (u.pathname === '/watch') {
        return u.searchParams.get('v');
      }
      const m = u.pathname.match(/^\/embed\/([a-zA-Z0-9_-]{6,})/);
      if (m) return m[1];
    }
  } catch {}
  return null;
}

function isHttpOrHttps(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

function looksEducationalYouTube(titleOrUrl) {
  const text = (titleOrUrl || '').toLowerCase();
  return YT_KEYWORDS.some(k => text.includes(k));
}

function youtubeHasDisallowedKeyword(url, title) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, '');
    if (!(host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtu.be')) return false;
    const haystack = ((title || '') + ' ' + url).toLowerCase();
    // Parse common search params for YouTube search
    const q1 = (u.searchParams.get('search_query') || '').toLowerCase();
    const q2 = (u.searchParams.get('q') || '').toLowerCase();
    const terms = Array.isArray(STATE.disallowedKeywords) ? STATE.disallowedKeywords : [];
    for (const raw of terms) {
      const kw = (raw || '').trim().toLowerCase();
      if (!kw) continue;
      if (haystack.includes(kw)) return true;
      if (q1.includes(kw) || q2.includes(kw)) return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function isAllowedUrl(url, title) {
  // IMPORTANT: Disable automatic blocking - let workspace-guard.js handle it via backend API
  // This prevents blocking all sites. Only block if explicitly requested.
  
  if (!STATE.enabled) return true;
  
  const domain = domainFromUrl(url);
  if (!domain) return true; // can't parse, allow

  // Always allow local dev hosts and frontend
  if (domain === 'localhost' || domain === '127.0.0.1') return true;
  if (url.includes('workspace-frontend') || url.includes('vercel.app')) return true;

  // If an exact URL is locked, only allow that URL (plus localhost)
  if (STATE.lockedUrl) {
    try {
      const locked = new URL(STATE.lockedUrl);
      const cur = new URL(url);

      // Special handling for YouTube: allow same video id across variants (/watch?v=, youtu.be/, /embed/)
      const lockedId = getYouTubeVideoId(locked.href);
      const curId = getYouTubeVideoId(cur.href);
      if (lockedId && curId && lockedId === curId) {
        return true;
      }

      // Otherwise require same host and path prefix
      const sameHost = locked.hostname === cur.hostname;
      const samePath = cur.href.startsWith(locked.href);
      if (sameHost && samePath) return true;
      return false;
    } catch {
      // if parsing fails, fall back to domain rules
    }
  }

  // Only block explicitly blocked domains
  if (STATE.block.has(domain)) return false;

  // CRITICAL CHANGE: Don't use allowlist blocking - allow all sites by default
  // The workspace-guard.js content script will handle YouTube blocking via backend API
  // This prevents the extension from blocking all non-allowed sites
  
  // For YouTube: Only block if disallowed keywords are present AND not educational
  const isYouTube = domain.includes('youtube.com') || domain === 'youtu.be';
  if (isYouTube) {
    if (youtubeHasDisallowedKeyword(url, title)) return false;
    // If required keyword is set, check it
    const kw = (STATE.requiredKeyword || '').trim().toLowerCase();
    if (kw) {
      const haystack = ((title || '') + ' ' + url).toLowerCase();
      if (!haystack.includes(kw)) return false;
    }
  }

  // Allow all other sites by default - workspace-guard.js will handle YouTube blocking
  return true;
}

// Close or redirect disallowed tabs
// NOTE: This is now DISABLED by default - workspace-guard.js handles blocking via backend API
async function enforceTab(tabId, changeInfo, tab) {
  try {
    // IMPORTANT: Only enforce if explicitly enabled AND it's a blocked domain
    // Don't block sites just because they're not in the allowlist
    
    // Only run when URL is ready
    const url = changeInfo.url || tab.url;
    if (!url) return;
    // Never enforce on chrome://, chrome-extension://, file://, etc.
    if (!isHttpOrHttps(url)) return;
    
    // Allow all sites by default - only block explicitly blocked domains
    const domain = domainFromUrl(url);
    if (!domain) return;
    
    // Only block if domain is explicitly in block list (like instagram.com)
    if (STATE.block.has(domain)) {
      console.log('[FocusGuard] Blocked domain:', domain);
      if (STATE.actionMode === 'redirect' && STATE.redirectUrl) {
        await chrome.tabs.update(tabId, { url: STATE.redirectUrl });
      } else {
        await chrome.tabs.remove(tabId);
      }
      return;
    }
    
    // For all other sites, allow them - workspace-guard.js will handle YouTube via backend
    // Don't check allowlist - just allow everything except explicit blocks
    return;
    
  } catch (e) {
    console.warn('Enforce error:', e);
  }
}

// Enable blocking for explicitly blocked domains (like Instagram)
// This runs in parallel with workspace-guard.js which handles YouTube via backend API
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading' || changeInfo.url) {
    enforceTab(tabId, changeInfo, tab);
  }
});

// Helper to enforce by tabId (for activation/focus events)
async function enforceByTabId(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !tab.url) return;
    await enforceTab(tabId, { url: tab.url, status: 'complete' }, tab);
  } catch (e) {
    // ignore
  }
}

// Enable blocking for explicitly blocked domains when user switches tabs
// When the user switches tabs, enforce immediately
chrome.tabs.onActivated.addListener(({ tabId }) => {
  enforceByTabId(tabId);
});

// When window focus changes, enforce on the active tab in that window
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) return;
  try {
    const [tab] = await chrome.tabs.query({ active: true, windowId });
    if (tab?.id) enforceByTabId(tab.id);
  } catch (e) {
    // ignore
  }
});

// When a new tab is created, enforce as soon as it has a URL
chrome.tabs.onCreated.addListener((tab) => {
  if (tab.id) {
    setTimeout(() => enforceByTabId(tab.id), 300);
  }
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({
    allow: Array.from(STATE.allow),
    block: Array.from(STATE.block),
    enabled: STATE.enabled,
    actionMode: STATE.actionMode,
    redirectUrl: STATE.redirectUrl,
    requiredKeyword: STATE.requiredKeyword,
    disallowedKeywords: STATE.disallowedKeywords,
  });
});

async function hydrateFromStorage() {
  try {
    const {
      allow,
      block,
      enabled,
      backendRulesUrl,
      actionMode,
      redirectUrl,
      requiredKeyword,
      disallowedKeywords,
    } = await chrome.storage.sync.get([
      'allow', 'block', 'enabled', 'backendRulesUrl', 'actionMode', 'redirectUrl', 'requiredKeyword', 'disallowedKeywords'
    ]);
    if (Array.isArray(allow)) STATE.allow = new Set(allow);
    if (Array.isArray(block)) STATE.block = new Set(block);
    if (typeof enabled === 'boolean') STATE.enabled = enabled;
    if (typeof backendRulesUrl === 'string') STATE.backendRulesUrl = backendRulesUrl;
    if (actionMode === 'close' || actionMode === 'redirect') STATE.actionMode = actionMode;
    if (typeof redirectUrl === 'string' && redirectUrl) STATE.redirectUrl = redirectUrl;
    if (typeof requiredKeyword === 'string') STATE.requiredKeyword = requiredKeyword;
    if (Array.isArray(disallowedKeywords)) STATE.disallowedKeywords = disallowedKeywords;
  } catch (e) {
    // ignore
  }
}

// Hydrate settings at startup
hydrateFromStorage();

// React to settings changes
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'sync') return;
  if (changes.allow?.newValue) STATE.allow = new Set(changes.allow.newValue);
  if (changes.block?.newValue) STATE.block = new Set(changes.block.newValue);
  if (typeof changes.enabled?.newValue === 'boolean') STATE.enabled = changes.enabled.newValue;
  if (changes.backendRulesUrl?.newValue) STATE.backendRulesUrl = changes.backendRulesUrl.newValue;
  if (changes.actionMode?.newValue && (changes.actionMode.newValue === 'close' || changes.actionMode.newValue === 'redirect')) STATE.actionMode = changes.actionMode.newValue;
  if (changes.redirectUrl?.newValue) STATE.redirectUrl = changes.redirectUrl.newValue;
  if (typeof changes.requiredKeyword?.newValue === 'string') STATE.requiredKeyword = changes.requiredKeyword.newValue;
  if (Array.isArray(changes.disallowedKeywords?.newValue)) STATE.disallowedKeywords = changes.disallowedKeywords.newValue;
  // If enforcement was just enabled, sweep all tabs
  if (typeof changes.enabled?.newValue === 'boolean' && changes.enabled.newValue === true) {
    sweepAllTabs();
  }
});

// Receive updates from options page
// Handle tab closing requests from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === 'close-tab') {
    // Get tab ID from sender
    const tabId = sender?.tab?.id;
    if (tabId) {
      console.log('[FocusGuard] Closing tab:', tabId);
      chrome.tabs.remove(tabId).then(() => {
        sendResponse({ ok: true });
      }).catch((error) => {
        console.error('[FocusGuard] Error closing tab:', error);
        sendResponse({ ok: false, error: error.message });
      });
      return true; // Keep channel open for async response
    } else {
      // Fallback: get current active tab
      chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
        if (tabs[0]?.id) {
          console.log('[FocusGuard] Closing active tab:', tabs[0].id);
          chrome.tabs.remove(tabs[0].id).then(() => {
            sendResponse({ ok: true });
          }).catch((error) => {
            console.error('[FocusGuard] Error closing active tab:', error);
            sendResponse({ ok: false, error: error.message });
          });
        } else {
          console.warn('[FocusGuard] No tab ID available to close');
          sendResponse({ ok: false, error: 'No tab ID' });
        }
      });
      return true; // Keep channel open for async response
    }
    return true;
  }
  
  if (msg?.type === 'update-rules') {
    const { allow, block, enabled, actionMode, redirectUrl, requiredKeyword, disallowedKeywords } = msg;
    if (Array.isArray(allow)) STATE.allow = new Set(allow);
    if (Array.isArray(block)) STATE.block = new Set(block);
    if (typeof enabled === 'boolean') STATE.enabled = enabled;
    if (actionMode === 'close' || actionMode === 'redirect') STATE.actionMode = actionMode;
    if (typeof redirectUrl === 'string' && redirectUrl) STATE.redirectUrl = redirectUrl;
    if (typeof requiredKeyword === 'string') STATE.requiredKeyword = requiredKeyword;
    if (Array.isArray(disallowedKeywords)) STATE.disallowedKeywords = disallowedKeywords;
    sendResponse({ ok: true });
    // Enforce updated rules immediately
    sweepAllTabs();
  } else if (msg?.type === 'lock-domain' && typeof msg.domain === 'string') {
    // Store previous allow to restore later
    STATE.previousAllow = Array.from(STATE.allow);
    STATE.lockedDomain = msg.domain;
    STATE.allow = new Set([msg.domain]);
    chrome.storage.sync.set({ allow: [msg.domain], lockedDomain: msg.domain, previousAllow: STATE.previousAllow });
    sendResponse({ ok: true, lockedDomain: msg.domain });
    // After locking, sweep tabs
    sweepAllTabs();
  } else if (msg?.type === 'lock-url' && typeof msg.url === 'string') {
    // Lock to a specific URL; store previous allow and domain for visibility
    try {
      const u = new URL(msg.url);
      STATE.previousAllow = Array.from(STATE.allow);
      STATE.lockedUrl = u.href;
      STATE.lockedDomain = u.hostname.replace(/^www\./, '');
      STATE.allow = new Set([STATE.lockedDomain]);
      chrome.storage.sync.set({ allow: [STATE.lockedDomain], lockedDomain: STATE.lockedDomain, lockedUrl: STATE.lockedUrl, previousAllow: STATE.previousAllow });
      sendResponse({ ok: true, lockedUrl: STATE.lockedUrl, lockedDomain: STATE.lockedDomain });
      // After locking, sweep tabs
      sweepAllTabs();
    } catch (e) {
      sendResponse({ ok: false, error: 'Invalid URL' });
    }
  } else if (msg?.type === 'unlock-domain') {
    if (Array.isArray(STATE.previousAllow)) {
      STATE.allow = new Set(STATE.previousAllow);
      chrome.storage.sync.set({ allow: STATE.previousAllow, lockedDomain: null, lockedUrl: null, previousAllow: null });
    }
    STATE.lockedDomain = null;
    STATE.previousAllow = null;
    STATE.lockedUrl = null;
    sendResponse({ ok: true });
  }
});

async function sweepAllTabs() {
  // DISABLED: Don't sweep all tabs - this blocks non-allowed sites
  // Let workspace-guard.js handle YouTube blocking via backend API
  // Only block explicitly blocked domains if needed
  try {
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      const url = tab.url;
      if (!url || !isHttpOrHttps(url)) continue;
      
      // Only block explicitly blocked domains
      const domain = domainFromUrl(url);
      if (domain && STATE.block.has(domain) && tab.id != null) {
        console.log('[FocusGuard] Sweeping blocked domain:', domain);
        try {
          if (STATE.actionMode === 'redirect' && STATE.redirectUrl) {
            await chrome.tabs.update(tab.id, { url: STATE.redirectUrl });
          } else {
            await chrome.tabs.remove(tab.id);
          }
        } catch (_) {}
      }
    }
  } catch (_) {}
}

// Optional: poll backend rules periodically
async function pollBackendRules() {
  if (!STATE.backendRulesUrl) return;
  try {
    const res = await fetch(STATE.backendRulesUrl);
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.allow)) STATE.allow = new Set(data.allow);
      if (Array.isArray(data.block)) STATE.block = new Set(data.block);
    }
  } catch (e) {
    // ignore network errors
  }
}

setInterval(pollBackendRules, 60_000);
