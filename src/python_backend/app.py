from typing import Optional, Dict, Any, List
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, Response
import io
import uvicorn
import os
import logging
import requests
import re
from jose import jwt
from jose.utils import base64url_decode
from jose.exceptions import JWTError
from ai_modules.analyzers import (
    analyze_screen_from_b64,
    analyze_focus_from_b64,
    analyze_distraction_from_window,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# Models matching Node bridge inputs
# ==============================
class ScreenAnalyzeRequest(BaseModel):
    screenshot_data: str
    user_id: str
    session_id: str

class FocusAnalyzeRequest(BaseModel):
    frame_data: str
    user_id: str
    session_id: str

class DistractionDetectRequest(BaseModel):
    window_info: Dict[str, Any]
    user_id: str
    session_id: str

class PostureAnalyzeRequest(BaseModel):
    frame_data: str
    user_id: str
    session_id: str

# ==============================
# New models for browser extension
# ==============================
class TabAnalyzeRequest(BaseModel):
    url: str
    title: str
    timestamp: Optional[int] = None

class ExtensionStatsRequest(BaseModel):
    action: str
    site: Optional[str] = None
    duration: Optional[int] = None

class SessionStartRequest(BaseModel):
    subject: str
    goal_minutes: Optional[int] = None
    user_id: Optional[str] = None

class SessionEndRequest(BaseModel):
    session_id: str
    average_focus: float
    scores: List[float]
    timeline: Optional[List[Dict[str, Any]]] = None
    sites: Optional[List[Dict[str, Any]]] = None
    user_id: Optional[str] = None

# ==============================
# FastAPI app setup
# ==============================
app = FastAPI(title="WorkSpace AI Python Backend", version="0.1.0")

# Simple in-memory cache for the latest tab analysis (after imports so types exist)
LAST_TAB_RESULT: Dict[str, Any] = {
    "success": False,
    "analysis_type": "browser_tab",
    "result": {},
    "timestamp": None,
}

# In-memory session store (in production, use a database)
SESSIONS_STORE: Dict[str, Any] = {}

# In-memory last educational URL (used by extension to redirect)
LAST_EDU_URL: str = os.getenv(
    "DEFAULT_EDU_URL",
    "https://www.youtube.com/embed/?listType=playlist&list=PL-osiE80TeTs4UjLw5MM6OjgkjFeUxCYH",
)

# Clerk settings (env-driven)
CLERK_JWKS_URL: str = os.getenv("CLERK_JWKS_URL", "")
CLERK_AUDIENCE: str = os.getenv("CLERK_JWT_AUD", "")
CLERK_ISSUER: str = os.getenv("CLERK_JWT_ISSUER", "")

_JWKS_CACHE: Optional[Dict[str, Any]] = None

def _get_jwks() -> Dict[str, Any]:
    global _JWKS_CACHE
    if _JWKS_CACHE is not None:
        return _JWKS_CACHE
    if not CLERK_JWKS_URL:
        return {"keys": []}
    try:
        resp = requests.get(CLERK_JWKS_URL, timeout=5)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
        return _JWKS_CACHE
    except Exception as e:
        logger.warning(f"Failed to fetch Clerk JWKS: {e}")
        return {"keys": []}

def verify_clerk_token(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        # JOSE will use "kid" in header to pick key from JWKS
        jwks = _get_jwks()
        options = {"verify_aud": bool(CLERK_AUDIENCE)}
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=CLERK_AUDIENCE if CLERK_AUDIENCE else None,
            issuer=CLERK_ISSUER if CLERK_ISSUER else None,
            options=options,
        )
        return claims
    except JWTError as e:
        logger.debug(f"Clerk JWT verification failed: {e}")
        return None

def clerk_dependency(authorization: Optional[str] = None):
    """FastAPI dependency to optionally verify Clerk JWT.
    If env vars are not set or token missing, returns None (no auth).
    """
    claims = verify_clerk_token(authorization)
    return claims

# CORS: allow local dev frontend/backend + browser extensions + production frontend
# Always include Vercel frontend explicitly
allowed_origins = [
    "https://workspace-frontend-liard.vercel.app",  # Vercel production frontend
    "http://localhost:3000",  # Local development
    "http://localhost:5000",  # Local development
    "http://localhost:5001",  # Local development
]

# Add environment variable origins if provided
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

frontend_vercel_url = os.getenv("FRONTEND_VERCEL_URL")
if frontend_vercel_url and frontend_vercel_url not in allowed_origins:
    allowed_origins.append(frontend_vercel_url)

# Remove duplicates
allowed_origins = list(set(allowed_origins))

logger.info(f"🌐 CORS allowed origins: {allowed_origins}")

# Apply CORS middleware - must be added BEFORE routes
# Use allow_origin_regex for flexibility with subdomains
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel deployments
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add explicit OPTIONS handler for preflight requests (as backup)
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle OPTIONS preflight requests with dynamic origin"""
    import re
    origin = request.headers.get("origin")
    
    # Check if origin is in allowed origins or matches Vercel pattern
    is_allowed = False
    if origin:
        if origin in allowed_origins:
            is_allowed = True
        elif re.match(r"https://.*\.vercel\.app", origin):
            is_allowed = True
    
    response = Response()
    if is_allowed and origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        # Default to first allowed origin if no origin or not allowed
        response.headers["Access-Control-Allow-Origin"] = allowed_origins[0] if allowed_origins else "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

# Add HTTP exception handler to ensure CORS headers are present on HTTP errors
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def cors_http_exception_handler(request: Request, exc: HTTPException):
    """Ensure CORS headers are present on HTTP exceptions"""
    import re
    origin = request.headers.get("origin", "")
    
    # Check if origin is allowed
    is_allowed = False
    if origin:
        if origin in allowed_origins:
            is_allowed = True
        elif re.match(r"https://.*\.vercel\.app", origin):
            is_allowed = True
    
    response = JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "type": "HTTPException"}
    )
    
    if is_allowed and origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    elif allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = allowed_origins[0]
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# ==============================
# Existing endpoints
# ==============================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "python": True,
        "time": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }

# ==============================
# Last educational URL endpoints
# ==============================
@app.get("/api/last-educational-url")
def get_last_educational_url():
    return {"url": LAST_EDU_URL}

class LastEduUrlPayload(BaseModel):
    url: str

@app.post("/api/last-educational-url")
def set_last_educational_url(payload: LastEduUrlPayload):
    global LAST_EDU_URL
    try:
        url = payload.url.strip()
        if not url:
            return {"success": False, "error": "empty url"}
        LAST_EDU_URL = url
        logger.info(f"🎓 Updated LAST_EDU_URL -> {url}")
        return {"success": True, "url": LAST_EDU_URL}
    except Exception as e:
        logger.error(f"❌ set_last_educational_url error: {e}")
        return {"success": False, "error": str(e)}

# ==============================
# Utility: Placeholder image endpoint
# ==============================
@app.get("/api/placeholder/{w}/{h}")
def placeholder_image(w: int, h: int):
    """Return a simple PNG placeholder of size w x h"""
    try:
        from PIL import Image, ImageDraw
        w = max(1, min(2048, int(w)))
        h = max(1, min(2048, int(h)))
        img = Image.new("RGB", (w, h), color=(240, 244, 248))
        draw = ImageDraw.Draw(img)
        # border
        draw.rectangle([(0,0),(w-1,h-1)], outline=(200,210,220))
        # center crosshair
        draw.line([(0, h//2), (w, h//2)], fill=(210, 220, 230))
        draw.line([(w//2, 0), (w//2, h)], fill=(210, 220, 230))
        # size label
        label = f"{w}×{h}"
        tw, th = draw.textlength(label), 12
        draw.text(((w - tw) / 2, (h - th) / 2), label, fill=(120, 130, 140))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        # Fallback: 1x1 PNG
        import base64
        pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
        return StreamingResponse(io.BytesIO(pixel), media_type="image/png")

@app.post("/api/analyze-screen")
def analyze_screen(payload: ScreenAnalyzeRequest, authorization: Optional[str] = None):
    # Use analyzer to OCR and classify task vs distraction
    _ = clerk_dependency(authorization)
    result = analyze_screen_from_b64(payload.screenshot_data)
    return {
        "success": True,
        "analysis_type": "screen",
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "result": result,
    }

@app.post("/api/analyze-focus")
def analyze_focus(payload: FocusAnalyzeRequest, authorization: Optional[str] = None):
    _ = clerk_dependency(authorization)
    result = analyze_focus_from_b64(payload.frame_data)
    return {
        "success": True,
        "analysis_type": "focus",
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "result": result,
    }

@app.post("/api/detect-distractions")
def detect_distractions(payload: DistractionDetectRequest, authorization: Optional[str] = None):
    _ = clerk_dependency(authorization)
    result = analyze_distraction_from_window(payload.window_info)
    return {
        "success": True,
        "analysis_type": "distraction",
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "result": result,
    }

@app.post("/api/analyze-posture")
def analyze_posture(payload: PostureAnalyzeRequest, authorization: Optional[str] = None):
    _ = clerk_dependency(authorization)
    size = len(payload.frame_data)
    posture_status = ["good", "ok", "poor"][ (size // 13) % 3 ]
    result = {
        "posture_status": posture_status,
        "analysis_timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "recommendations": ["sit upright", "relax shoulders"] if posture_status == "poor" else [],
    }
    return {
        "success": True,
        "analysis_type": "posture",
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "result": result,
    }

# ==============================
# New endpoints for browser extension
# ==============================
@app.post("/api/analyze-tab")
def analyze_tab(payload: TabAnalyzeRequest, background_tasks: BackgroundTasks):
    """Analyze a specific tab for the browser extension"""
    try:
        logger.info(f"🔍 Analyzing tab: {payload.title[:50]}... ({payload.url[:50]}...)")
        
        # ALWAYS ALLOW: Frontend URL and localhost (never block the app itself)
        url_lower = payload.url.lower()
        is_frontend = any([
            "workspace-frontend" in url_lower,
            "vercel.app" in url_lower,
            "localhost" in url_lower,
            "127.0.0.1" in url_lower
        ])
        
        if is_frontend:
            logger.info(f"✅ ALLOWING: Frontend/localhost URL - {payload.url[:80]}")
            return {
                "success": True,
                "analysis_type": "browser_tab",
                "result": {
                    "is_distraction": False,
                    "distraction_score": 0,
                    "content_type": "application",
                    "should_warn": False,
                    "should_block": False,
                    "should_close": False,
                    "popup_title": "✅ Application Page",
                    "popup_message": "You're on the WorkSpace application. Continue your session!",
                    "popup_type": "success"
                },
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
            }
        
        # Block known distraction sites (Instagram, Facebook, TikTok, etc.)
        distraction_domains = [
            "instagram.com", "instagr.am", "facebook.com", "fb.com",
            "tiktok.com", "twitter.com", "x.com", "reddit.com", "snapchat.com"
        ]
        is_distraction_site = any(domain in url_lower for domain in distraction_domains)
        
        if is_distraction_site:
            site_name = next((domain for domain in distraction_domains if domain in url_lower), "distraction site")
            logger.warning(f"🚫 BLOCKING: Known distraction site - {site_name}")
            return {
                "success": True,
                "analysis_type": "browser_tab",
                "result": {
                    "is_distraction": True,
                    "distraction_score": 100,
                    "content_type": "high_distraction",
                    "severity": "critical",
                    "should_warn": False,
                    "should_block": True,
                    "should_close": True,
                    "site_name": site_name,
                    "warning_level": "high",
                    "recommended_action": "close_tab",
                    "popup_title": "🚫 Distracting Site Blocked",
                    "popup_message": f"This site ({site_name}) is blocked during study sessions. Stay focused on your studies! 📚",
                    "popup_type": "error",
                    "blocking_reason": f"Known distraction site: {site_name}",
                    "detected_indicators": ["known_distraction_site"],
                },
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
            }
        
        # STRICT YouTube Watch Page Policy: Block by default unless educational
        is_youtube = "youtube.com" in url_lower or "youtu.be" in url_lower
        
        # Watch page detection: /watch?v=VIDEO_ID or youtu.be/VIDEO_ID
        # Exclude non-watch pages: /embed, /channel, /playlist, /user/, /c/, /@
        is_watch_page = False
        if is_youtube:
            # Check for watch page patterns
            has_watch_pattern = "/watch" in url_lower and "v=" in url_lower
            has_youtube_be_pattern = "youtu.be/" in url_lower
            
            # Exclude non-watch page patterns
            is_excluded = any(pattern in url_lower for pattern in [
                "/embed", "/channel/", "/playlist", "/user/", "/c/", "/@", 
                "/shorts/", "/results", "/feed", "/subscriptions", "/library"
            ])
            
            is_watch_page = (has_watch_pattern or has_youtube_be_pattern) and not is_excluded
        
        logger.info(f"🔍 YouTube check: is_youtube={is_youtube}, is_watch_page={is_watch_page}, url={payload.url[:80]}, title={payload.title[:50] if payload.title else 'None'}")
        
        # For YouTube watch pages, apply STRICT policy - BLOCK BY DEFAULT
        if is_youtube and is_watch_page:
            # Check if title contains educational keywords
            title_lower = (payload.title or "").lower().strip()
            url_lower = payload.url.lower()
            
            # If title is missing, empty, or just "YouTube", treat as non-educational (BLOCK)
            if not title_lower or title_lower == "youtube" or len(title_lower) < 5:
                logger.warning(f"🚫 BLOCKING: YouTube watch page with missing/invalid title")
                logger.warning(f"   URL: {payload.url}")
                logger.warning(f"   Title: '{payload.title}'")
                return {
                    "success": True,
                    "analysis_type": "browser_tab",
                    "result": {
                        "is_distraction": True,
                        "distraction_score": 95,
                        "content_type": "high_distraction",
                        "severity": "critical",
                        "should_warn": False,
                        "should_block": True,
                        "should_close": True,
                        "site_name": "youtube.com",
                        "warning_level": "high",
                        "recommended_action": "close_tab",
                        "popup_title": "🚫 Tab Not Educational - Will Close",
                        "popup_message": f"This content cannot be verified as educational and will be closed in 5 seconds. Stay focused on your studies! 📚",
                        "popup_type": "error",
                        "blocking_reason": "YouTube watch page title missing or invalid",
                        "detected_indicators": ["youtube_watch_page_missing_title"],
                        "video_title": payload.title or "Unknown"
                    },
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
                }
            
            # Comprehensive educational keywords that ALLOW the video
            educational_keywords = [
                # General education terms
                "tutorial", "lecture", "course", "class", "lesson", "learn", "learning",
                "education", "educational", "study", "studying", "academic", "university",
                "college", "professor", "instructor", "teacher", "explained", "explanation",
                "guide", "how to", "introduction", "basics", "fundamentals", "concepts",
                
                # Math terms
                "math", "mathematics", "calculus", "algebra", "geometry", "trigonometry",
                "derivative", "integral", "limit", "limits", "function", "functions",
                "equation", "equations", "theorem", "proof", "derivative", "integration",
                "differential", "linear algebra", "vector", "matrix", "matrices",
                "statistics", "probability", "discrete", "topology", "analysis",
                
                # Science terms
                "physics", "chemistry", "biology", "organic chemistry", "quantum",
                "mechanic", "thermodynamics", "electromagnetism", "optics",
                "neuroscience", "genetics", "molecular", "biochemistry",
                
                # Computer science / programming
                "programming", "coding", "computer science", "algorithm", "algorithms",
                "data structure", "data structures", "python", "javascript", "java",
                "react", "web development", "machine learning", "neural network",
                "neural networks", "deep learning", "ai", "artificial intelligence",
                "software engineering", "app development", "html", "css", "sql",
                
                # Educational channel names / patterns
                "3blue1brown", "3 blue 1 brown", "khan academy", "khanacademy",
                "crash course", "crashcourse", "veritasium", "numberphile", "minutephysics",
                "ted-ed", "ted ed", "smarter every day", "scishow", "sixty symbols",
                
                # Educational phrases
                "what is", "why does", "how does", "explained simply", "visualized",
                "understanding", "overview", "summary", "review", "notes", "chapter",
                "part 1", "part 2", "part 3", "episode", "series"
            ]
            
            # Check if title has educational markers
            has_educational_marker = any(keyword in title_lower for keyword in educational_keywords)
            
            # Also check URL for educational patterns (playlists are usually educational)
            has_url_educational_marker = any(keyword in url_lower for keyword in ["playlist", "list="])
            
            # Check for educational channel patterns in URL (various YouTube URL formats)
            # YouTube URLs can be: /c/ChannelName, /user/Username, /channel/ChannelID, /@ChannelHandle
            educational_channel_patterns = [
                "3blue1brown", "khanacademy", "khan academy", "crashcourse", "crash course",
                "veritasium", "numberphile", "minutephysics", "smartereveryday", "smarter every day",
                "scishow", "sixty symbols", "ted-ed", "ted ed", "periodic videos",
                "vsauce", "minuteearth", "sci show", "kurzgesagt", "cody's lab"
            ]
            has_educational_channel = any(pattern in url_lower for pattern in educational_channel_patterns)
            
            # Also try to extract channel name from common URL patterns
            # Match patterns like /c/ChannelName, /user/Username, /@Handle
            channel_match = re.search(r'/(?:c|user|channel|@)/([^/?&]+)', url_lower)
            if channel_match:
                channel_name = channel_match.group(1)
                has_educational_channel = has_educational_channel or any(
                    pattern in channel_name for pattern in educational_channel_patterns
                )
            
            # STRICT POLICY: Block ALL YouTube watch pages UNLESS educational markers are found
            # This is a whitelist approach - only allow if clearly educational
            should_allow = has_educational_marker or has_url_educational_marker or has_educational_channel
            
            # Find which specific keywords were matched for better logging
            matched_keywords = [kw for kw in educational_keywords if kw in title_lower]
            matched_channel = None
            if has_educational_channel:
                for pattern in educational_channel_patterns:
                    if pattern in url_lower:
                        matched_channel = pattern
                        break
            
            # If no educational markers found, BLOCK immediately
            if not should_allow:
                logger.warning(f"🚫 BLOCKING: YouTube watch page without educational markers")
                logger.warning(f"   URL: {payload.url}")
                logger.warning(f"   Title: {payload.title}")
                logger.warning(f"   Title length: {len(title_lower.split())} words")
                logger.warning(f"   Has educational marker: {has_educational_marker}")
                logger.warning(f"   Has URL educational marker: {has_url_educational_marker}")
                logger.warning(f"   Has educational channel: {has_educational_channel}")
                
                return {
                    "success": True,
                    "analysis_type": "browser_tab",
                    "result": {
                        "is_distraction": True,
                        "distraction_score": 95,
                        "content_type": "high_distraction",
                        "severity": "critical",
                        "should_warn": False,
                        "should_block": True,
                        "should_close": True,  # CRITICAL: This must be True
                        "site_name": "youtube.com",
                        "warning_level": "high",
                        "recommended_action": "close_tab",
                        "popup_title": "🚫 Tab Not Educational - Will Close",
                        "popup_message": f"This content is not educational and will be closed in 5 seconds. Stay focused on your studies! 📚",
                        "popup_type": "error",
                        "blocking_reason": "YouTube watch page lacks educational content markers",
                        "detected_indicators": ["youtube_watch_page_no_educational_markers"],
                        "video_title": payload.title  # Include title for debugging
                    },
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
                }
            else:
                logger.info(f"✅ ALLOWING: YouTube watch page with educational markers")
                logger.info(f"   Title: {payload.title}")
                logger.info(f"   Matched keywords: {matched_keywords}")
                if matched_channel:
                    logger.info(f"   Matched channel: {matched_channel}")
                if has_url_educational_marker:
                    logger.info(f"   URL contains playlist/list indicator")
        
        # Create window info for existing analyzer
        window_info = {
            "title": payload.title,
            "url": payload.url,
            "process_name": "chrome.exe",  # Assume Chrome
            "active_time": 30  # Default active time for new tabs
        }

        # Use existing distraction analyzer
        result = analyze_distraction_from_window(window_info)
        
        # Add extension-specific fields
        distraction_score = result.get("distraction_score", 0)
        severity = result.get("severity", "low")
        is_distraction = result.get("is_distraction", False)
        
        # Determine extension actions based on analysis
        # ONLY close YouTube videos - never close other sites
        if is_youtube and is_distraction and not result.get("content_type") == "educational":
            should_block = True
            should_warn = False
            should_close = True  # Close non-educational YouTube videos ONLY
        elif is_youtube:
            # Educational YouTube - allow
            should_warn = False
            should_block = False
            should_close = False
        else:
            # For non-YouTube sites: warn but NEVER close
            should_warn = is_distraction and distraction_score > 50
            should_block = is_distraction and distraction_score > 70
            should_close = False  # NEVER close non-YouTube tabs
        
        # Get site name from URL
        site_name = "unknown site"
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(payload.url)
            site_name = parsed_url.netloc.replace("www.", "")
        except:
            pass
        
        # Determine popup message
        # CRITICAL: Only set should_close for YouTube. For other sites, never close.
        if not is_youtube:
            # Non-YouTube sites: Never close, only inform
            should_close = False  # Force to False for safety
            if not is_distraction or result.get("content_type") == "educational":
                popup_title = "✅ Educational Content"
                popup_message = f"This {site_name} content appears to be educational. Keep learning! 🎓"
                popup_type = "success"
            elif should_block:
                popup_title = "⚠️ Warning - Distracting Content"
                popup_message = f"This {site_name} content may be distracting. Stay focused on your studies!"
                popup_type = "warning"
            else:
                popup_title = None  # Don't show popup for neutral non-YouTube content
                popup_message = None
                popup_type = "info"
        elif not is_distraction or result.get("content_type") == "educational":
            # Educational YouTube
            popup_title = "✅ Educational Content"
            popup_message = f"This YouTube video appears to be educational. Keep learning! 🎓"
            popup_type = "success"
        elif should_close:
            # Non-educational YouTube - will close
            popup_title = "🚫 Tab Not Educational - Will Close"
            popup_message = f"This YouTube video is not educational and will be closed in 5 seconds. Stay focused on your studies! 📚"
            popup_type = "error"
        elif should_block:
            popup_title = "⚠️ Warning - Distracting Content"
            popup_message = f"This YouTube content may be distracting. Consider closing this tab to stay focused."
            popup_type = "warning"
        else:
            popup_title = "ℹ️ Content Monitoring"
            popup_message = f"You're browsing YouTube. Keep your study goals in mind!"
            popup_type = "info" 
        
        # Enhanced result for extension
        extension_result = {
            **result,  # Include all original analysis
            "should_warn": should_warn,
            "should_block": should_block,
            "should_close": should_close,
            "warning_message": f"WorkSpace AI detected you're browsing {site_name}. Time to focus!",
            "block_message": f"This site ({site_name}) is distracting you from your goals.",
            "site_name": site_name,
            "warning_level": "high" if should_close else "medium" if should_block else "low" if should_warn else "none",
            "recommended_action": "close_tab" if should_close else "show_overlay" if should_block else "show_banner" if should_warn else "none",
            "popup_title": popup_title,
            "popup_message": popup_message,
            "popup_type": popup_type
        }
        
        # If this looks educational (not a distraction) and is a YouTube URL, remember it as last educational
        try:
            if not is_distraction and ("youtube." in site_name or "youtu.be" in payload.url.lower()):
                global LAST_EDU_URL
                LAST_EDU_URL = payload.url
                logger.info(f"🎓 Remembered LAST_EDU_URL (from analyze_tab): {LAST_EDU_URL}")
        except Exception as _e:
            pass

        # Log the decision
        action = "🚨 CLOSE" if should_close else "🔒 BLOCK" if should_block else "⚠️ WARN" if should_warn else "✅ ALLOW"
        logger.info(f"📊 Tab analysis result: {action} ({site_name})")
        
        # Do not schedule tab closure to avoid closing tabs; redirect is handled by the extension
        
        resp = {
            "success": True,
            "analysis_type": "browser_tab",
            "result": extension_result,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        # cache last tab result
        try:
            global LAST_TAB_RESULT
            LAST_TAB_RESULT = resp
        except Exception:
            pass
        return resp
        
    except Exception as e:
        logger.error(f"❌ Tab analysis error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "result": {
                "is_distraction": False,
                "should_warn": False,
                "should_block": False,
                "should_close": False,
                "warning_message": "Analysis failed",
                "site_name": "unknown",
                "warning_level": "none",
                "recommended_action": "none"
            }
        }

@app.get("/api/last-tab")
def get_last_tab():
    """Return the last tab analysis cached by /api/analyze-tab"""
    try:
        return LAST_TAB_RESULT
    except Exception as e:
        logger.error(f"❌ last-tab error: {e}")
        return {"success": False, "result": {}}

@app.get("/api/extension-status")
def get_extension_status():
    """Get current extension status and statistics"""
    try:
        # You can implement actual statistics storage here
        # For now, return mock data
        stats = {
            "blocked_today": 5,
            "focus_time_minutes": 120,
            "distractions_prevented": 8,
            "most_blocked_site": "youtube.com",
            "focus_sessions": 3
        }
        
        return {
            "success": True,
            "enabled": True,
            "focus_mode": True,
            "blocked_sites": [
                "youtube.com", "facebook.com", "instagram.com", 
                "twitter.com", "tiktok.com", "reddit.com",
                "netflix.com", "twitch.tv"
            ],
            "stats": stats,
            "settings": {
                "warning_delay": 30,  # seconds
                "block_delay": 120,   # seconds
                "close_delay": 300,   # seconds
                "notifications_enabled": True
            },
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"❌ Extension status error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "enabled": False
        }

@app.post("/api/extension-stats")
def update_extension_stats(payload: ExtensionStatsRequest):
    """Update extension statistics (blocked sites, focus time, etc.)"""
    try:
        action = payload.action
        site = payload.site
        duration = payload.duration
        
        logger.info(f"📊 Extension stat update: {action} - {site} ({duration}s)")
        
        # Here you would typically update a database
        # For now, just log the action
        
        response_data = {
            "success": True,
            "action_recorded": action,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        
        if action == "site_blocked":
            response_data["message"] = f"Recorded blocking of {site}"
        elif action == "focus_time":
            response_data["message"] = f"Recorded {duration} seconds of focus time"
        elif action == "distraction_prevented":
            response_data["message"] = f"Recorded distraction prevention on {site}"
        
        return response_data
        
    except Exception as e:
        logger.error(f"❌ Extension stats error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/block-site")
def block_site(payload: dict):
    """Manually block a site (for future system-level blocking)"""
    try:
        site = payload.get('site', '')
        duration = payload.get('duration', 3600)  # Default 1 hour
        
        logger.info(f"🚫 Manual site block request: {site} for {duration} seconds")
        
        # You can implement system-level blocking logic here
        # This could integrate with hosts file modification or other blocking tools
        
        return {
            "success": True,
            "message": f"Block request registered for {site}",
            "blocked_site": site,
            "duration_seconds": duration,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"❌ Site blocking error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# ==============================
# Session management endpoints
# ==============================
@app.post("/api/session/start")
def start_session(payload: SessionStartRequest, authorization: Optional[str] = None):
    """Start a new study session"""
    try:
        claims = clerk_dependency(authorization)
        user_id = claims.get("sub") if claims else payload.user_id or "guest"
        
        session_id = f"session_{int(__import__('time').time() * 1000)}"
        now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
        
        session = {
            "id": session_id,
            "user_id": user_id,
            "subject": payload.subject,
            "goal_minutes": payload.goal_minutes,
            "status": "active",
            "start_time": now,
            "end_time": None,
            "average_focus": 0,
            "scores": [],
            "timeline": [],
            "sites": []
        }
        
        SESSIONS_STORE[session_id] = session
        logger.info(f"✅ Session started: {session_id} for user {user_id}")
        
        return {
            "success": True,
            "data": {
                "session": session
            }
        }
    except Exception as e:
        logger.error(f"❌ Start session error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/session/{session_id}")
def get_session(session_id: str, authorization: Optional[str] = None):
    """Get session by ID"""
    try:
        if session_id not in SESSIONS_STORE:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = SESSIONS_STORE[session_id]
        return {
            "success": True,
            "data": {
                "session": session
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/session/{session_id}/end")
def end_session(session_id: str, payload: SessionEndRequest, authorization: Optional[str] = None):
    """End a session and save results"""
    try:
        if session_id not in SESSIONS_STORE:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = SESSIONS_STORE[session_id]
        now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
        
        session.update({
            "status": "completed",
            "end_time": now,
            "average_focus": payload.average_focus,
            "scores": payload.scores,
            "timeline": payload.timeline or [],
            "sites": payload.sites or []
        })
        
        SESSIONS_STORE[session_id] = session
        logger.info(f"✅ Session ended: {session_id}, avg focus: {payload.average_focus:.1f}%")
        
        return {
            "success": True,
            "data": {
                "session": session
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ End session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/user/{user_id}")
def get_user_sessions(user_id: str, authorization: Optional[str] = None):
    """Get all sessions for a user"""
    try:
        claims = clerk_dependency(authorization)
        # In production, validate user_id matches claims
        user_sessions = [s for s in SESSIONS_STORE.values() if s.get("user_id") == user_id]
        return {
            "success": True,
            "data": {
                "sessions": user_sessions
            }
        }
    except Exception as e:
        logger.error(f"❌ Get user sessions error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/focus-session")
def get_focus_session():
    """Get current focus session information (legacy endpoint for compatibility)"""
    # Return the most recent active session if any
    active_sessions = [s for s in SESSIONS_STORE.values() if s.get("status") == "active"]
    if active_sessions:
        latest = max(active_sessions, key=lambda x: x.get("start_time", ""))
        start_time = latest.get("start_time", "")
        try:
            # Parse ISO format with Z timezone
            from datetime import datetime
            if start_time.endswith("Z"):
                dt_start = datetime.fromisoformat(start_time[:-1])
            else:
                dt_start = datetime.fromisoformat(start_time.replace("+00:00", ""))
            elapsed = (datetime.utcnow() - dt_start).total_seconds() / 60
        except Exception:
            elapsed = 0
        
        return {
            "success": True,
            "session_active": True,
            "session_start": start_time,
            "elapsed_minutes": int(elapsed),
            "target_minutes": latest.get("goal_minutes", 120),
            "distractions_blocked": 0,  # Can be calculated from sites
            "productivity_score": latest.get("average_focus", 0)
        }
    
    return {
        "success": True,
        "session_active": False,
        "session_start": None,
        "elapsed_minutes": 0,
        "target_minutes": 120,
        "distractions_blocked": 0,
        "productivity_score": 0
    }

# ==============================
# Background task functions
# ==============================
def log_tab_closure(site_name: str, url: str):
    """Background task to log tab closures"""
    logger.info(f"🚨 Tab closure executed: {site_name} ({url})")
    # Here you could update statistics, send notifications, etc.

def trigger_system_notification(message: str, title: str = "WorkSpace AI"):
    """Background task to show system notifications"""
    try:
        import plyer
        plyer.notification.notify(
            title=title,
            message=message,
            timeout=5
        )
        logger.info(f"📬 Notification sent: {message}")
    except Exception as e:
        logger.warning(f"⚠️ Notification failed: {e}")

# ==============================
# Development and testing endpoints
# ==============================
@app.get("/api/test-extension")
def test_extension_integration():
    """Test endpoint to verify extension integration"""
    test_cases = [
        {"url": "https://youtube.com", "expected": "should_block"},
        {"url": "https://facebook.com", "expected": "should_block"},
        {"url": "https://stackoverflow.com", "expected": "should_allow"},
        {"url": "https://github.com", "expected": "should_allow"}
    ]
    
    results = []
    for case in test_cases:
        # Simulate tab analysis
        payload = TabAnalyzeRequest(
            url=case["url"],
            title=f"Test page - {case['url']}",
            timestamp=1234567890
        )
        
        # This would normally call analyze_tab but we'll do a quick test
        window_info = {
            "title": payload.title,
            "url": payload.url,
            "active_time": 30
        }
        
        result = analyze_distraction_from_window(window_info)
        
        results.append({
            "url": case["url"],
            "expected": case["expected"],
            "is_distraction": result.get("is_distraction", False),
            "distraction_score": result.get("distraction_score", 0),
            "detected_indicators": result.get("detected_indicators", [])
        })
    
    return {
        "success": True,
        "test_results": results,
        "backend_status": "operational",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
    }

# ==============================
# Development helper endpoints
# ==============================
class SimulateBlockPayload(BaseModel):
    site: str = "example.com"

@app.post("/api/dev/simulate-block")
def simulate_block(payload: SimulateBlockPayload):
    """Simulate a blocking tab decision so the extension can be tested."""
    global LAST_TAB_RESULT
    site_name = payload.site or "example.com"
    LAST_TAB_RESULT = {
        "success": True,
        "analysis_type": "browser_tab",
        "result": {
            "is_distraction": True,
            "should_warn": False,
            "should_block": True,
            "should_close": False,
            "warning_message": f"Blocking simulated for {site_name}",
            "block_message": f"This site ({site_name}) is distracting you from your goals.",
            "site_name": site_name,
            "warning_level": "medium",
            "recommended_action": "show_overlay"
        },
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
    }
    logger.info(f"🧪 Simulated block set for {site_name}")
    return {"success": True, "message": "Simulated block stored", "result": LAST_TAB_RESULT}

# ==============================
# Main application runner
# ==============================
if __name__ == "__main__":
    port = int(os.getenv("PYTHON_PORT", "8000"))
    logger.info(f"🚀 Starting WorkSpace AI Backend on port {port}")
    logger.info("🔌 Browser extension endpoints enabled")
    # When launched by Node's PythonBridge, it runs `python3 app.py` with cwd set here
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
