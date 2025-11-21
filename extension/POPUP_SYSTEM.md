# YouTube Educational Content Filter & Popup System

## Overview

The system now:
1. ✅ **Strictly blocks non-educational YouTube videos**
2. ✅ **Shows popup notifications** indicating if content is educational or blocked
3. ✅ **Automatically closes tabs** for non-educational YouTube videos
4. ✅ **Allows temporary exceptions** ("Allow Once" button)

## How It Works

### Backend Detection (`analyze_tab` endpoint)

1. **URL Analysis**: Detects YouTube URLs (youtube.com/watch, youtu.be, etc.)
2. **Title Analysis**: Checks video titles for educational keywords
3. **Content Classification**:
   - ✅ **Educational**: Contains keywords like "tutorial", "lecture", "course", "learn", etc.
   - 🚫 **Non-Educational**: Entertainment, music videos, comedy, gaming, etc.

### Popup System

The extension shows different popups based on content type:

#### ✅ Educational Content (Green)
- **Title**: "✅ Educational Content"
- **Message**: "This YouTube content appears to be educational. Keep learning! 🎓"
- **Action**: Shows for 10 seconds, then auto-dismisses

#### 🚫 Non-Educational Content (Red) 
- **Title**: "🚫 Blocked - Non-Educational Content"
- **Message**: "This YouTube content is not educational and will be closed. Stay focused on your studies! 📚"
- **Actions**: 
  - "Close Tab" - Immediately closes the tab
  - "Allow Once" - Allows the video for 5 minutes
- **Auto-Close**: Tab closes automatically after 3 seconds

#### ⚠️ Warning (Orange)
- **Title**: "⚠️ Warning - Distracting Content"
- **Message**: "This content may be distracting. Consider closing this tab to stay focused."

## Installation

1. **Load Extension**:
   - Open Chrome → Extensions (`chrome://extensions`)
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `extension` folder

2. **Update API URL** (if needed):
   - Edit `workspace-guard.js`
   - Update `API_BASE` constant with your backend URL

## Testing

### Test Educational Video:
```
URL: https://www.youtube.com/watch?v=VIDEO_ID_WITH_EDUCATIONAL_TITLE
Expected: Green popup "✅ Educational Content"
```

### Test Non-Educational Video:
```
URL: https://www.youtube.com/watch?v=r6k3NdKoMX8 (or any entertainment video)
Expected: Red popup "🚫 Blocked - Non-Educational Content" → Tab closes in 3 seconds
```

## Educational Keywords

The system looks for these keywords in video titles:

- Academic: "tutorial", "lecture", "course", "class", "lesson"
- Subjects: "math", "physics", "chemistry", "programming", "computer science"
- Learning: "learn", "education", "study", "explained", "guide"
- Channels: "khan academy", "crash course", "mit", "coursera"

## Non-Educational Keywords (Blocked)

These trigger immediate blocking:

- Entertainment: "funny", "comedy", "viral", "memes", "prank"
- Music: "music video", "song", "official video", "lyric video"
- Gaming: "gameplay", "gaming", "streamer", "let's play"
- Social: "vlog", "lifestyle", "makeup", "fashion"

## Customization

### Adjust Detection Strictness

Edit `src/python_backend/ai_modules/analyzers.py`:
- `detect_educational_content()` - Add more educational keywords
- `detect_high_distraction_content()` - Add more blocking keywords

### Adjust Popup Timing

Edit `extension/workspace-guard.js`:
- `setTimeout(() => { chrome.runtime.sendMessage({ type: 'close-tab' }); }, 3000);` - Change 3000ms (3 seconds) to desired delay

### Adjust Allow Duration

Edit `extension/workspace-guard.js`:
- `if (Date.now() - allowedTime < 5 * 60 * 1000)` - Change 5 minutes to desired duration

## Troubleshooting

### Popup Not Showing
1. Check browser console for errors
2. Verify extension is loaded and enabled
3. Check backend API is accessible
4. Verify manifest.json includes workspace-guard.js

### False Positives (Educational videos blocked)
1. Video title needs clear educational keywords
2. Add video-specific exceptions in backend
3. Use "Allow Once" button to bypass

### False Negatives (Non-educational videos allowed)
1. Video may have ambiguous title
2. Improve keyword detection in analyzers.py
3. Report specific URLs for improvement

## Backend Deployment

After pushing changes:
1. **Redeploy backend** on Render
2. **Wait for deployment** to complete
3. **Test with YouTube URLs** to verify detection

## Next Steps

To further improve:
1. Add YouTube API integration for better video metadata
2. Add user feedback system for classification accuracy
3. Add whitelist/blacklist management in extension options
4. Add analytics for blocked/allowed content

