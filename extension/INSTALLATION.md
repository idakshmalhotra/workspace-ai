# How to Install Workspace AI Extension in Chrome

## Step-by-Step Installation Guide

### Step 1: Open Chrome Extensions Page

1. Open Google Chrome browser
2. Go to the extensions page using one of these methods:
   - Type `chrome://extensions` in the address bar and press Enter
   - OR: Click the **three dots menu** (⋮) → **Extensions** → **Manage extensions**
   - OR: Right-click the extensions icon → **Manage extensions**

### Step 2: Enable Developer Mode

1. On the extensions page, look for **"Developer mode"** toggle in the top-right corner
2. **Turn it ON** (toggle should be blue/enabled)

### Step 3: Load the Extension

1. Click the **"Load unpacked"** button (appears after enabling Developer mode)
2. In the file picker, navigate to:
   ```
   /Users/user/Projects/Workspace-backend/extension
   ```
   OR on Windows:
   ```
   C:\Users\YourName\Projects\Workspace-backend\extension
   ```
3. Select the `extension` folder
4. Click **"Select Folder"** or **"Open"**

### Step 4: Verify Installation

After loading, you should see:
- ✅ **Extension appears** in the extensions list
- ✅ **Status shows** as "Enabled" (green toggle)
- ✅ **No red error icons** or error messages

### Step 5: Pin the Extension (Optional but Recommended)

1. Click the **puzzle piece icon** (🧩) in Chrome toolbar (extensions icon)
2. Find **"Workspace AI Focus Guard"**
3. Click the **pin icon** 📌 to pin it to your toolbar for easy access

## Verify It's Working

### Quick Test:

1. Visit a YouTube video: `https://www.youtube.com/watch?v=r6k3NdKoMX8`
2. Open **Developer Tools** (Press `F12` or Right-click → Inspect)
3. Go to **Console** tab
4. Look for messages starting with `[Workspace AI]`
5. You should see:
   - `[Workspace AI] Starting analysis`
   - `[Workspace AI] Analyzing: ...`
   - After 3 seconds, a popup should appear

## Troubleshooting

### Issue: "Load unpacked" button not showing
**Solution**: Make sure Developer mode is enabled (blue toggle)

### Issue: "Manifest file is missing or unreadable"
**Solution**: 
- Make sure you selected the `extension` folder, not a parent folder
- Check that `manifest.json` exists in the folder

### Issue: Extension shows errors
**Solution**:
- Check the error message details
- Click "Errors" button to see full error
- Common fixes:
  - Make sure all files are present: `manifest.json`, `background.js`, `workspace-guard.js`
  - Check file paths in manifest.json

### Issue: Extension not blocking YouTube
**Solution**:
- Check backend is running: `https://workspace-ai.onrender.com/health`
- Open Console (F12) on YouTube page
- Look for `[Workspace AI]` messages
- Check Network tab for API calls to `/api/analyze-tab`

## Extension Files Required

Make sure these files exist in the `extension` folder:

```
extension/
├── manifest.json          ✅ Required
├── background.js          ✅ Required
├── workspace-guard.js    ✅ Required (content script)
├── content.js            ✅ Optional (for dashboard)
├── popup.html            ✅ Optional
└── options.html           ✅ Optional
```

## After Installation

The extension will:
- ✅ Monitor all web pages you visit
- ✅ Analyze YouTube videos for educational content
- ✅ Show popups when content is blocked/allowed
- ✅ Automatically close non-educational YouTube videos
- ✅ Allow temporary exceptions ("Allow Once" button)

## Need Help?

If you encounter issues:
1. Check browser console (F12) for errors
2. Verify all files are in the extension folder
3. Reload the extension: Click the reload icon (🔄) on extensions page
4. Check backend API is accessible

