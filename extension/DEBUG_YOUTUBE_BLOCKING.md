# Debugging YouTube Blocking

## Problem: YouTube video not being blocked

If `https://www.youtube.com/watch?v=r6k3NdKoMX8` is not being blocked, follow these steps:

## Step 1: Verify Extension is Loaded

1. Open Chrome → `chrome://extensions`
2. Find "Workspace AI Focus Guard"
3. Ensure it's **Enabled** (toggle should be ON)
4. Check if there are any errors (red error icon)

## Step 2: Check Extension Console

1. Go to the YouTube video page
2. Open Developer Tools (F12)
3. Go to **Console** tab
4. Look for messages starting with `[Workspace AI]`
5. You should see:
   - `[Workspace AI] Starting analysis`
   - `[Workspace AI] Analyzing: {url: ..., title: ...}`
   - `[Workspace AI] Calling backend API...`
   - `[Workspace AI] Analysis result: {should_close: true, ...}`

## Step 3: Check Backend API

1. Open browser DevTools → **Network** tab
2. Go to YouTube video
3. Look for request to `/api/analyze-tab`
4. Click on it and check:
   - **Request payload**: Should have `url` and `title`
   - **Response**: Should have `should_close: true`

### Test Backend Directly:

```bash
curl -X POST https://workspace-ai.onrender.com/api/analyze-tab \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=r6k3NdKoMX8", "title": "Test Video"}'
```

Expected response should have:
```json
{
  "result": {
    "should_close": true,
    "is_distraction": true,
    "popup_title": "🚫 Blocked - Non-Educational Content"
  }
}
```

## Step 4: Verify Title Detection

The extension tries multiple methods to get YouTube title:

1. **document.title** (default)
2. **h1.ytd-watch-metadata** element (YouTube video title)
3. **meta[property="og:title"]** tag

Check console for:
```
[Workspace AI] Got YouTube title from h1: ...
[Workspace AI] Got YouTube title from meta: ...
```

## Step 5: Manual Test

1. Open YouTube video: `https://www.youtube.com/watch?v=r6k3NdKoMX8`
2. Open Console (F12)
3. Run this manually:
```javascript
fetch('https://workspace-ai.onrender.com/api/analyze-tab', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    url: window.location.href,
    title: document.querySelector('h1.ytd-watch-metadata')?.textContent || document.title
  })
}).then(r => r.json()).then(console.log);
```

Should return `should_close: true` if blocking is working.

## Common Issues

### Issue 1: Extension not loaded
**Solution**: Reload extension in `chrome://extensions`

### Issue 2: Content script not running
**Solution**: 
- Check `manifest.json` includes `workspace-guard.js`
- Reload extension
- Check console for errors

### Issue 3: Backend not responding
**Solution**: 
- Check backend is deployed on Render
- Test `/health` endpoint
- Check backend logs for errors

### Issue 4: Title not captured
**Solution**: 
- Extension now waits 3 seconds for YouTube title to load
- Checks multiple times
- Uses fallback selectors

### Issue 5: CORS errors
**Solution**: 
- Already fixed in backend
- Redeploy backend if needed

## Expected Behavior

When visiting `https://www.youtube.com/watch?v=r6k3NdKoMX8`:

1. ✅ **3 seconds after page load**: Extension calls backend API
2. ✅ **Backend checks**: Title has no educational keywords
3. ✅ **Backend returns**: `should_close: true`
4. ✅ **Extension shows**: Red popup "🚫 Blocked - Non-Educational Content"
5. ✅ **3 seconds later**: Tab closes automatically

## If Still Not Working

1. **Check backend logs** on Render dashboard
2. **Check extension console** for errors
3. **Test API manually** (Step 5 above)
4. **Reload extension** completely
5. **Clear browser cache** and reload page

## Testing Educational Videos

To test that educational videos ARE allowed, try:
```
https://www.youtube.com/watch?v=VIDEO_ID_WITH_TUTORIAL_IN_TITLE
```

Should show green popup: "✅ Educational Content"

