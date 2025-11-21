# Render Service Diagnostics

## Current Status: 502 Bad Gateway

The backend is returning `502 Bad Gateway`, which means the service is down or not responding.

## Immediate Steps

### 1. Check Render Dashboard

Go to: https://dashboard.render.com → Your Service

**Check these:**

#### Service Status
- ✅ **Live** (green) = Service is running
- ⚠️ **Build failed** (red) = Check build logs
- ⏸️ **Suspended** = Service stopped
- 💤 **Sleeping** (free tier) = Service auto-sleeps after 15 min inactivity

#### Recent Logs
Click on "Logs" tab and look for:
- ❌ **Error messages** - Python errors, import errors, etc.
- ✅ **Startup success** - `🚀 Starting WorkSpace AI Backend on port...`
- ✅ **CORS log** - `🌐 CORS allowed origins: [...]`

#### Common Errors to Look For:

1. **Import Errors:**
   ```
   ModuleNotFoundError: No module named 'X'
   ```
   → Fix: Check `requirements.txt` has all dependencies

2. **Port Issues:**
   ```
   Address already in use
   ```
   → Fix: Make sure using `$PORT` environment variable

3. **Python Version:**
   ```
   Python version not supported
   ```
   → Fix: Check `runtime.txt` specifies correct version

4. **Startup Timeout:**
   ```
   Service failed to start within timeout
   ```
   → Fix: Backend taking too long to start

### 2. Common Fixes

#### If Service is Sleeping:
- Free tier services sleep after 15 min of inactivity
- First request wakes it up (takes ~30-60 seconds)
- Keep service awake by upgrading to paid plan OR use a ping service

#### If Build Failed:
1. Check build logs for errors
2. Common issues:
   - Missing dependencies in `requirements.txt`
   - Python version mismatch
   - Build command errors
3. Fix the issue and redeploy

#### If Service Crashed:
1. Check runtime logs for error messages
2. Look for Python tracebacks
3. Common causes:
   - Missing environment variables
   - Port binding issues
   - Import errors
   - Database connection issues (if using DB)

### 3. Quick Health Check

Try these commands to diagnose:

```bash
# Check if service responds (might take time if sleeping)
curl https://workspace-ai.onrender.com/health

# Check service info
curl -I https://workspace-ai.onrender.com/health

# Test with timeout
curl --max-time 60 https://workspace-ai.onrender.com/health
```

### 4. Manual Restart

If service is stuck:

1. Go to Render Dashboard
2. Click your service
3. Click "Manual Deploy"
4. Select "Clear build cache & deploy"
5. Wait for deployment

### 5. Verify Configuration

Check these in Render settings:

#### Build Settings:
- **Root Directory:** `src/python_backend` ✅
- **Build Command:** `pip install --upgrade pip setuptools wheel && pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

#### Environment Variables:
- `PORT` - Auto-set by Render (don't override)
- `FRONTEND_URL` - Optional
- `PYTHON_VERSION` - Optional (uses runtime.txt)

#### Service Settings:
- **Plan:** Starter or above (free tier sleeps)
- **Region:** Check you're in correct region
- **Auto-Deploy:** Should be enabled

## Next Steps

1. **Check Render Dashboard** - Most important step!
2. **Review Logs** - Look for startup errors
3. **Check Build Logs** - See if build succeeded
4. **Manual Deploy** - Try clearing cache and redeploying
5. **Contact Support** - If service keeps failing

## Expected Log Output (When Working)

When the service starts successfully, you should see:

```
🚀 Starting WorkSpace AI Backend on port 8000
🔌 Browser extension endpoints enabled
🌐 CORS allowed origins: ['https://workspace-frontend-liard.vercel.app', ...]
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

If you don't see this, the service didn't start properly.

