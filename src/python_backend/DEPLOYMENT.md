# FastAPI Backend Deployment Guide for Render

This guide walks you through deploying your FastAPI backend to Render.

## Prerequisites

- A Render account (sign up at https://render.com)
- Your code pushed to a Git repository (GitHub, GitLab, or Bitbucket)

## Step-by-Step Deployment

### Option 1: Using Render Dashboard (Recommended)

1. **Sign in to Render Dashboard**
   - Go to https://dashboard.render.com
   - Sign in with your GitHub/GitLab account

2. **Create a New Web Service**
   - Click "New +" button
   - Select "Web Service"
   - Connect your repository
   - Select the repository containing your backend

3. **Configure the Service**
   - **Name**: `workspace-python-backend` (or your preferred name)
   - **Region**: Choose closest to your users (e.g., `Oregon`)
   - **Branch**: `master` (or your default branch)
   - **Root Directory**: `src/python_backend`
   - **Environment**: `Python 3`
   - **Build Command**: 
     ```bash
     pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
     ```
     (Note: pandas has been removed from requirements.txt since it causes compilation issues. The app works without it.)
   - **Start Command**: 
     ```bash
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```
   - **Plan**: Choose `Starter` ($7/month) or `Free` (for testing)

4. **Environment Variables**
   Add these in the "Environment" section:
   - `PORT`: `8000` (Render sets this automatically, but include for safety)
   - `FRONTEND_URL`: Your frontend URL (e.g., `https://your-frontend.onrender.com`)
   - `CLERK_JWKS_URL`: Your Clerk JWKS URL
   - `CLERK_JWT_AUD`: Your Clerk JWT Audience
   - `CLERK_JWT_ISSUER`: Your Clerk JWT Issuer
   - `DEFAULT_EDU_URL`: Default educational YouTube URL (optional)

5. **Deploy**
   - Click "Create Web Service"
   - Render will start building and deploying your service
   - Wait for the build to complete (usually 5-10 minutes)

### Option 2: Using render.yaml (Infrastructure as Code)

1. **The `render.yaml` file is already created** in `src/python_backend/`
   
2. **Deploy using Blueprint**
   - Go to Render Dashboard
   - Click "New +" → "Blueprint"
   - Connect your repository
   - Render will detect `render.yaml` and create services automatically

3. **Set Environment Variables**
   - Go to your service settings
   - Add the same environment variables as mentioned in Option 1

## Troubleshooting Common Issues

### Issue: pandas compilation error (Python 3.13 incompatibility)

**Root Cause**: Render may be using Python 3.13 by default, which doesn't have pre-built pandas wheels, causing compilation from source to fail.

**Solution 1: Use requirements.txt without pandas (Recommended)**
- We've removed pandas from `requirements.txt` since it's only used conditionally
- The code will work without pandas - it gracefully falls back if pandas isn't available
- The model prediction feature will be disabled, but all other features work

**Solution 2: Force Python 3.11 in Render settings**
1. Go to your service settings in Render
2. Add environment variable: `PYTHON_VERSION=3.11.9`
3. Or use the runtime.txt file (ensure Root Directory is `src/python_backend`)

**Solution 3: Use Docker (Best for consistency)**
- Use the provided `Dockerfile` which explicitly uses Python 3.11
- In Render: Enable Docker, set Dockerfile Path to `src/python_backend/Dockerfile`

**Solution 4: Build command workaround**
```bash
pip install --upgrade pip setuptools wheel && \
pip install -r requirements.txt && \
pip install pandas==2.1.4 --only-binary :all: || echo "pandas skipped"
```

### Issue: Port binding error

**Solution**: Make sure your start command uses `$PORT`:
```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

### Issue: Missing dependencies

**Solution**: Ensure all dependencies are in `requirements.txt`. The current list includes:
- fastapi
- uvicorn
- pydantic
- opencv-python
- pytesseract
- numpy
- pandas
- joblib
- Pillow
- python-jose[cryptography]
- requests

### Issue: Build timeout

**Solution**: 
- OpenCV and pandas are large packages
- Consider using a Dockerfile for better caching
- Or upgrade to a higher Render plan with longer build times

## Post-Deployment Steps

1. **Test the Health Endpoint**
   ```bash
   curl https://your-service.onrender.com/health
   ```
   Should return: `{"status":"ok","python":true,"time":"..."}`

2. **Update Frontend URLs**
   - Update your frontend to point to the new backend URL
   - Update CORS settings if needed

3. **Monitor Logs**
   - Go to your service dashboard
   - Check "Logs" tab for any runtime errors

4. **Set up Auto-Deploy**
   - Render auto-deploys on push to your main branch
   - Configure custom branch if needed in settings

## Alternative: Docker Deployment (If Issues Persist)

If you continue having build issues, create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Then update Render:
- **Docker**: Yes
- **Dockerfile Path**: `src/python_backend/Dockerfile`
- **Docker Context**: `src/python_backend`

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PORT` | Auto-set | Port Render assigns | `8000` |
| `FRONTEND_URL` | Yes | Your frontend URL | `https://app.example.com` |
| `CLERK_JWKS_URL` | Optional | Clerk JWKS endpoint | `https://your-clerk.jwks` |
| `CLERK_JWT_AUD` | Optional | Clerk JWT audience | `your-audience` |
| `CLERK_JWT_ISSUER` | Optional | Clerk JWT issuer | `https://your-clerk.issuer` |
| `DEFAULT_EDU_URL` | Optional | Default educational URL | YouTube playlist URL |

## Cost Estimation

- **Free Tier**: Limited hours/month, spins down after inactivity
- **Starter Plan**: $7/month, always on, 512MB RAM
- **Professional Plan**: $25/month, more RAM and CPU

For production, Starter or higher is recommended.

## Additional Resources

- [Render Python Documentation](https://render.com/docs/python)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Render Status Page](https://status.render.com)

## Support

If you encounter issues:
1. Check Render logs in the dashboard
2. Verify all environment variables are set
3. Test locally with the same Python version (`python-3.11.9`)
4. Check Render community forums

