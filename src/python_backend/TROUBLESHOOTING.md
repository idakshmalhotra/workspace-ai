# Troubleshooting Guide

## Current Issues

### 1. CORS Errors Still Occurring

**Symptoms:**
- `Access to fetch at 'https://workspace-ai.onrender.com/api/analyze-focus' from origin 'https://workspace-frontend-liard.vercel.app' has been blocked by CORS policy`
- `502 Bad Gateway` errors

**Possible Causes:**
1. **Backend hasn't redeployed yet** - The latest CORS fixes need to be deployed
2. **Backend service is down** - 502 suggests the backend might be restarting or crashed
3. **Render auto-deploy not triggered** - Check if Render detected the new commit

**Solutions:**

#### Check Backend Status
1. Go to Render Dashboard → Your service → Logs
2. Check if the service is running
3. Look for the CORS log: `🌐 CORS allowed origins: [...]`
4. Verify the service shows as "Live" (green)

#### Manual Redeploy
1. In Render Dashboard → Your service
2. Click "Manual Deploy" → "Deploy latest commit"
3. Wait for deployment to complete
4. Check logs to see if CORS origins are logged

#### Verify CORS Configuration
After deployment, test CORS with:
```bash
curl -H "Origin: https://workspace-frontend-liard.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://workspace-ai.onrender.com/api/analyze-focus \
     -v
```

You should see:
```
Access-Control-Allow-Origin: https://workspace-frontend-liard.vercel.app
Access-Control-Allow-Credentials: true
```

### 2. Placeholder Image 404 Errors

**Symptoms:**
- `Failed to load resource: the server responded with a status of 404 ()` for `/api/placeholder/500/300`

**Cause:**
Frontend is using relative paths like `/api/placeholder/600/400` which loads from the Vercel domain, not the backend.

**Solution:**
Update frontend to use full backend URL:
```typescript
const API_BASE = import.meta.env.VITE_API_BASE || '';
// Use: `${API_BASE}/api/placeholder/600/400`
// Instead of: `/api/placeholder/600/400`
```

Files to update:
- `src/components/landing/FeatureSection.tsx`
- `src/components/landing/AboutSection.tsx`
- `src/components/landing/TestimonialsSection.tsx`

### 3. Clerk Development Keys Warning

**Symptoms:**
- `Clerk: Clerk has been loaded with development keys`

**Solution:**
This is just a warning. For production:
1. Get production keys from Clerk dashboard
2. Update `VITE_CLERK_PUBLISHABLE_KEY` in Vercel environment variables
3. Redeploy frontend

## Next Steps

1. **Verify Backend Deployment:**
   - Check Render logs for CORS origin list
   - Ensure service is "Live"
   - Test health endpoint: `https://workspace-ai.onrender.com/health`

2. **If CORS Still Fails:**
   - Check Render environment variables
   - Verify no firewall/proxy blocking requests
   - Check browser console for preflight OPTIONS requests

3. **Fix Placeholder Images:**
   - Update frontend to use `${API_BASE}/api/placeholder/...`
   - Or configure Vercel to proxy `/api` requests to backend

## Quick Test Commands

```bash
# Test backend health
curl https://workspace-ai.onrender.com/health

# Test CORS preflight
curl -X OPTIONS \
     -H "Origin: https://workspace-frontend-liard.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     https://workspace-ai.onrender.com/api/analyze-focus \
     -v

# Test placeholder endpoint
curl https://workspace-ai.onrender.com/api/placeholder/100/100 -I
```

