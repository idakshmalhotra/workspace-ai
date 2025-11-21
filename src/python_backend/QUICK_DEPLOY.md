# Quick Deploy Guide - Render

## ✅ SOLUTION: Removed pandas from requirements.txt

**The issue**: Render was trying to compile pandas from source with Python 3.13, which fails.

**The fix**: 
- ✅ Removed pandas from `requirements.txt` (it's only used conditionally anyway)
- ✅ Your app will work fine without pandas - the model prediction feature will gracefully skip if pandas isn't available
- ✅ All other features (screen analysis, focus detection, distraction detection) work perfectly

## Deploy Steps (Render Dashboard)

1. **Go to Render Dashboard** → New + → Web Service

2. **Configure**:
   - **Root Directory**: `src/python_backend` ⚠️ IMPORTANT
   - **Build Command**: 
     ```bash
     pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
     ```
   - **Start Command**: 
     ```bash
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```

3. **Add Environment Variables** (in Environment tab):
   - `FRONTEND_URL`: Your frontend URL
   - `CLERK_JWKS_URL`, `CLERK_JWT_AUD`, `CLERK_JWT_ISSUER` (if using Clerk)

4. **Click Deploy** ✅

## If You Need pandas Later

If you need the model prediction feature:

1. **Option A: Use Docker** (Recommended)
   - Enable Docker in Render
   - Dockerfile Path: `src/python_backend/Dockerfile`
   - This uses Python 3.11 which has pandas wheels

2. **Option B: Add pandas manually**
   - After deployment, SSH into your instance
   - Run: `pip install pandas==2.1.4 --only-binary :all:`

3. **Option C: Use requirements-full.txt**
   - Change build command to: `pip install -r requirements-full.txt`
   - Only works if Render uses Python 3.11

## Verify Deployment

After deployment, test:
```bash
curl https://your-service.onrender.com/health
```

Should return: `{"status":"ok","python":true,"time":"..."}`

---

**Current Status**: ✅ Ready to deploy without pandas compilation errors!

