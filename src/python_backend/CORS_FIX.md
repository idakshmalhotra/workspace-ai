# CORS Configuration Fix

## Issue
Frontend deployed on Vercel (`https://workspace-frontend-liard.vercel.app`) was blocked by CORS when trying to access the backend API.

## Solution
Updated CORS middleware in `app.py` to explicitly allow the Vercel frontend URL.

## Changes Made

1. **Added Vercel URL to allowed origins**:
   - `https://workspace-frontend-liard.vercel.app`

2. **Improved CORS configuration**:
   - Production mode: Specific origins with credentials enabled
   - Development mode: Can allow all origins (if `ALLOW_ALL_ORIGINS=true`)

## Environment Variables

Set these in Render dashboard for the backend:

- `FRONTEND_URL`: Your frontend URL (optional, defaults to localhost)
- `FRONTEND_VERCEL_URL`: `https://workspace-frontend-liard.vercel.app` (optional, already hardcoded)
- `ALLOW_ALL_ORIGINS`: `false` for production (default), `true` for development

## After Deployment

1. Redeploy the backend to Render
2. The CORS errors should be resolved
3. Focus analysis (`/api/analyze-focus`) should now work from Vercel

## Testing

After redeploying, check browser console - CORS errors should be gone.

To test manually:
```bash
curl -H "Origin: https://workspace-frontend-liard.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://workspace-ai.onrender.com/api/analyze-focus
```

Should return CORS headers with the Vercel origin allowed.

