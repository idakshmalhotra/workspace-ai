// Workspace AI Guard - Content Script for Popup and Tab Control
// Injected into web pages to show popups and communicate with backend

(function() {
  'use strict';

  const API_BASE = 'https://workspace-ai.onrender.com'; // Update with your backend URL
  
  let currentPopup = null;
  let analysisResult = null;

  // Create and show popup
  function showPopup(title, message, type, shouldClose) {
    // Remove existing popup
    if (currentPopup) {
      currentPopup.remove();
      currentPopup = null;
    }

    // Create popup element
    const popup = document.createElement('div');
    popup.id = 'workspace-ai-popup';
    popup.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      width: 350px;
      background: ${type === 'error' ? '#ff4444' : type === 'warning' ? '#ffaa00' : type === 'success' ? '#44ff44' : '#4488ff'};
      color: white;
      padding: 20px;
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      animation: slideIn 0.3s ease-out;
    `;

    // Add animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from {
          transform: translateX(400px);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
      @keyframes slideOut {
        from {
          transform: translateX(0);
          opacity: 1;
        }
        to {
          transform: translateX(400px);
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);

    // Popup content
    popup.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
        <h3 style="margin: 0; font-size: 16px; font-weight: 600;">${title}</h3>
        <button id="workspace-popup-close" style="background: transparent; border: none; color: white; font-size: 20px; cursor: pointer; padding: 0; width: 24px; height: 24px;">&times;</button>
      </div>
      <p style="margin: 0 0 16px 0;">${message}</p>
      ${shouldClose ? `
        <div style="display: flex; gap: 8px;">
          <button id="workspace-popup-close-tab" style="flex: 1; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500;">
            Close Tab
          </button>
          <button id="workspace-popup-allow" style="flex: 1; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer;">
            Allow Once
          </button>
        </div>
      ` : `
        <button id="workspace-popup-dismiss" style="width: 100%; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500;">
          Got it
        </button>
      `}
      ${shouldClose ? `
        <div id="workspace-countdown" style="margin-top: 12px; text-align: center; font-size: 12px; opacity: 0.9;">
          Tab will close in <span id="countdown-number">5</span> seconds...
        </div>
      ` : ''}
    `;

    document.body.appendChild(popup);
    currentPopup = popup;

    // Close button
    const closeBtn = popup.querySelector('#workspace-popup-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => hidePopup());
    }

    // Dismiss button
    const dismissBtn = popup.querySelector('#workspace-popup-dismiss');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => hidePopup());
    }

    // Close tab button
    const closeTabBtn = popup.querySelector('#workspace-popup-close-tab');
    if (closeTabBtn) {
      closeTabBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ type: 'close-tab' });
        hidePopup();
      });
    }

    // Allow once button
    const allowBtn = popup.querySelector('#workspace-popup-allow');
    if (allowBtn) {
      allowBtn.addEventListener('click', () => {
        chrome.storage.local.set({ [`allowed_${window.location.href}`]: Date.now() });
        hidePopup();
      });
    }

    // Auto-hide after 10 seconds for non-blocking popups
    if (!shouldClose) {
      setTimeout(() => hidePopup(), 10000);
    }
    
    // Add countdown timer if tab will close
    if (shouldClose) {
      let secondsLeft = 5;
      const countdownElement = popup.querySelector('#countdown-number');
      const countdownInterval = setInterval(() => {
        secondsLeft--;
        if (countdownElement) {
          countdownElement.textContent = secondsLeft;
        }
        if (secondsLeft <= 0) {
          clearInterval(countdownInterval);
        }
      }, 1000);
    }
  }

  function hidePopup() {
    if (currentPopup) {
      currentPopup.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => {
        if (currentPopup) {
          currentPopup.remove();
          currentPopup = null;
        }
      }, 300);
    }
  }

  // Analyze current tab
  async function analyzeCurrentTab() {
    try {
      const url = window.location.href;
      let title = document.title || '';
      
      // CRITICAL: For YouTube watch pages, ALWAYS analyze even if title is missing
      const isYouTubeWatchPage = isYouTube(url) && (url.includes('/watch') || url.includes('youtu.be/'));
      
      // For YouTube, try harder to get title
      if (isYouTubeWatchPage) {
        // Try multiple selectors for YouTube video title
        const selectors = [
          'h1.ytd-watch-metadata yt-formatted-string',
          'h1.ytd-watch-metadata',
          'ytd-watch-metadata h1',
          'h1[class*="title"]',
          'h1',
          '#watch-title',
          'meta[property="og:title"]',
          'meta[name="title"]'
        ];
        
        for (const selector of selectors) {
          try {
            const element = document.querySelector(selector);
            if (element) {
              if (element.tagName === 'META') {
                title = element.getAttribute('content') || element.getAttribute('property') || title;
              } else {
                title = element.textContent || element.innerText || element.title || title;
              }
              if (title && title !== 'YouTube' && title.length > 5) {
                console.log(`[Workspace AI] Got YouTube title from ${selector}:`, title.substring(0, 80));
                break;
              }
            }
          } catch (e) {
            // Continue to next selector
          }
        }
        
        // If still no title, use URL video ID as fallback
        if (!title || title === 'YouTube' || title.length < 5) {
          const videoIdMatch = url.match(/(?:watch\?v=|youtu\.be\/)([^&?]+)/);
          if (videoIdMatch) {
            title = `YouTube Video ${videoIdMatch[1]}`;
            console.log('[Workspace AI] Using video ID as title fallback');
          }
        }
      }

      console.log('[Workspace AI] Analyzing:', { url: url.substring(0, 60), title: title.substring(0, 60) });

      // Check if this is a distraction site that should always be blocked
      const distractionSites = ['instagram.com', 'instagr.am', 'facebook.com', 'fb.com', 'tiktok.com', 'twitter.com', 'x.com', 'reddit.com', 'snapchat.com'];
      const isDistractionSite = distractionSites.some(site => url.includes(site));
      
      // CRITICAL: For YouTube watch pages and distraction sites, skip the "allowed" check - always analyze
      // This ensures non-educational videos and distraction sites get blocked even if user clicked "Allow" before
      const skipAllowedCheck = isYouTubeWatchPage || isDistractionSite;
      
      if (!skipAllowedCheck) {
        // Check if this URL was recently allowed (only for non-YouTube or non-watch pages)
        const storage = await chrome.storage.local.get([`allowed_${url}`]);
        if (storage[`allowed_${url}`]) {
          const allowedTime = storage[`allowed_${url}`];
          // Allow for 5 minutes
          if (Date.now() - allowedTime < 5 * 60 * 1000) {
            console.log('[Workspace AI] URL was recently allowed, skipping');
            return;
          }
        }
      }

      // Call backend API - ALWAYS call for YouTube watch pages
      console.log('[Workspace AI] Calling backend API...', { url: url.substring(0, 60), title: title.substring(0, 60) });
      
      let response;
      let data;
      
      try {
        response = await fetch(`${API_BASE}/api/analyze-tab`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, title, timestamp: Date.now() })
        });

        if (!response.ok) {
          console.error('[Workspace AI] Analysis failed:', response.status, response.statusText);
          // For YouTube watch pages, if API fails, still try to block (default to blocking)
          if (isYouTubeWatchPage) {
            console.warn('[Workspace AI] API failed for YouTube, defaulting to block');
            showPopup(
              "🚫 Unable to Verify - Blocking by Default",
              "Could not verify if this video is educational. Closing tab for safety. Stay focused! 📚",
              "error",
              true
            );
            setTimeout(() => {
              chrome.runtime.sendMessage({ type: 'close-tab' });
            }, 5000);
          }
          return;
        }

        data = await response.json();
        console.log('[Workspace AI] Full API response:', data);
        
        if (!data || !data.result) {
          console.error('[Workspace AI] Invalid API response:', data);
          return;
        }
      } catch (fetchError) {
        console.error('[Workspace AI] Fetch error:', fetchError);
        // For YouTube watch pages, if fetch fails, still try to block
        if (isYouTubeWatchPage) {
          console.warn('[Workspace AI] Fetch failed for YouTube, defaulting to block');
          showPopup(
            "🚫 Connection Error - Blocking by Default",
            "Could not connect to verification service. Closing tab for safety. Stay focused! 📚",
            "error",
            true
          );
          setTimeout(() => {
            chrome.runtime.sendMessage({ type: 'close-tab' });
          }, 5000);
        }
        return;
      }

      analysisResult = data.result || {};

      const { popup_title, popup_message, popup_type, should_close, is_distraction } = analysisResult;

      console.log('[Workspace AI] Analysis result:', { 
        popup_title, 
        popup_message: popup_message?.substring(0, 50), 
        popup_type, 
        should_close, 
        is_distraction 
      });

      // Check if this is a YouTube video or a known distraction site
      const isYouTubeUrl = url.includes('youtube.com') || url.includes('youtu.be');
      const distractionSites = ['instagram.com', 'instagr.am', 'facebook.com', 'fb.com', 'tiktok.com', 'twitter.com', 'x.com', 'reddit.com', 'snapchat.com'];
      const isDistractionSite = distractionSites.some(site => url.includes(site));
      
      // For distraction sites (Instagram, Facebook, etc.), always block if backend says to close
      if (isDistractionSite && should_close === true) {
        console.log('[Workspace AI] Distraction site detected, blocking:', url.substring(0, 60));
        const finalTitle = popup_title || "🚫 Distracting Site Blocked";
        const finalMessage = popup_message || "This site is blocked during study sessions. Stay focused on your studies! 📚";
        const finalType = popup_type || 'error';
        
        showPopup(finalTitle, finalMessage, finalType, true);
        
        setTimeout(() => {
          console.log('[Workspace AI] Closing distraction site tab');
          chrome.runtime.sendMessage({ type: 'close-tab' }, (response) => {
            if (chrome.runtime.lastError) {
              console.error('[Workspace AI] Error closing tab:', chrome.runtime.lastError);
            }
          });
        }, 5000);
        return;
      }
      
      // Safety check: If not YouTube and not a distraction site, never close or show blocking popup
      if (!isYouTubeUrl && !isDistractionSite) {
        console.log('[Workspace AI] Other site detected, skipping blocking:', url.substring(0, 60));
        // Still show info popups if they're positive (educational content detected on other sites)
        if (popup_type === 'success' && popup_title && popup_message) {
          showPopup(popup_title, popup_message, popup_type, false);
        }
        return; // Don't block or close other sites
      }
      
      // For YouTube only: Show popup and handle closing
      // CRITICAL: Always show popup for YouTube if should_close is true, even if popup fields are missing
      if (should_close === true) {
        // Force show blocking popup for YouTube videos that should be closed
        const finalTitle = popup_title || "🚫 Tab Not Educational - Will Close";
        const finalMessage = popup_message || "This YouTube video is not educational and will be closed in 5 seconds. Stay focused on your studies! 📚";
        const finalType = popup_type || 'error';
        
        console.log('[Workspace AI] SHOWING BLOCKING POPUP for YouTube:', { finalTitle, finalMessage, finalType });
        showPopup(finalTitle, finalMessage, finalType, true);
        
        // Auto-close tab in 5 seconds
        console.log('[Workspace AI] YouTube tab will be closed in 5 seconds - should_close=true');
        setTimeout(() => {
          console.log('[Workspace AI] Closing YouTube tab now - non-educational content detected');
          chrome.runtime.sendMessage({ type: 'close-tab' }, (response) => {
            if (chrome.runtime.lastError) {
              console.error('[Workspace AI] Error closing tab:', chrome.runtime.lastError);
              // Fallback: try window.close() if message fails
              try {
                window.close();
              } catch (e) {
                console.error('[Workspace AI] Could not close tab:', e);
              }
            } else {
              console.log('[Workspace AI] Tab close message sent successfully');
            }
          });
        }, 5000);
      } else if (popup_title && popup_message) {
        // Show informational popup for allowed YouTube videos
        showPopup(popup_title, popup_message, popup_type || 'success', false);
      } else if (is_distraction && isYouTubeUrl) {
        // Fallback: if backend marked as distraction but didn't set should_close, still block
        console.warn('[Workspace AI] YouTube marked as distraction but should_close not set, blocking anyway');
        showPopup(
          "🚫 Blocked - Non-Educational Content",
          "This YouTube video appears to be distracting and will be closed in 5 seconds.",
          "error",
          true
        );
        setTimeout(() => {
          chrome.runtime.sendMessage({ type: 'close-tab' });
        }, 5000);
      }
    } catch (error) {
      console.error('[Workspace AI] Analysis error:', error);
    }
  }

  // For YouTube, wait longer for title to load
  function isYouTube(url) {
    return url.includes('youtube.com') || url.includes('youtu.be');
  }

  // Analyze when page loads - with special handling for YouTube
  function startAnalysis() {
    const url = window.location.href;
    const isYouTubePage = isYouTube(url);
    
    // YouTube pages need more time for title to load
    const delay = isYouTubePage ? 3000 : 1000;
    
    console.log('[Workspace AI] Starting analysis', { url: url.substring(0, 50), isYouTubePage, delay });
    
    setTimeout(() => {
      analyzeCurrentTab();
      
      // For YouTube, also check again after title might have updated
      if (isYouTubePage) {
        setTimeout(() => {
          console.log('[Workspace AI] Re-checking YouTube after title update');
          analyzeCurrentTab();
        }, 5000);
      }
    }, delay);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startAnalysis);
  } else {
    startAnalysis();
  }

  // Re-analyze on navigation (for SPAs)
  let lastUrl = window.location.href;
  setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      console.log('[Workspace AI] URL changed, re-analyzing:', lastUrl.substring(0, 50));
      startAnalysis();
    }
  }, 2000);
  
  // For YouTube, also listen for title changes
  if (isYouTube(window.location.href)) {
    let lastTitle = document.title;
    setInterval(() => {
      if (document.title !== lastTitle) {
        lastTitle = document.title;
        console.log('[Workspace AI] YouTube title changed, re-analyzing:', lastTitle.substring(0, 50));
        setTimeout(analyzeCurrentTab, 1000);
      }
    }, 1000);
  }

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'analyze-tab') {
      analyzeCurrentTab();
      sendResponse({ ok: true });
    }
  });

})();

