import os
import logging
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import instaloader
from urllib.parse import urlparse
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ig-scraper")

app = FastAPI(title="IG Post/Reel Fetcher", version="1.0")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://allvideodownloader.tech",
    "https://videodow01.netlify.app",
    "http://92.113.16.59",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
IG_USERNAME = os.getenv("IG_USERNAME")        # optional if using session file
SESSION_FILE_PATH = os.getenv("IG_SESSION_FILE")  # e.g., ".session-your_username"
PROXY_URL = os.getenv("IG_PROXY")            # optional proxy

class FetchRequest(BaseModel):
    url: str

def get_loader():
    L = instaloader.Instaloader(
        download_videos=False,
        download_pictures=False,
        download_video_thumbnails=False,
        download_geotags=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    # Optional proxy
    if PROXY_URL:
        L.context._session.proxies.update({"https": PROXY_URL})
        logger.info(f"Using proxy: {PROXY_URL}")

    # Load session file if exists
    if SESSION_FILE_PATH and os.path.exists(SESSION_FILE_PATH):
        try:
            L.load_session_from_file(IG_USERNAME, filename=SESSION_FILE_PATH)
            logger.info("Session file loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load session file: {e}")

    # Else try login if credentials provided
    elif IG_USERNAME:
        try:
            IG_PASSWORD = os.getenv("IG_PASSWORD")
            if IG_PASSWORD:
                L.login(IG_USERNAME, IG_PASSWORD)
                logger.info("Logged in to Instagram successfully")
        except Exception as e:
            logger.warning(f"Login failed: {e}. Proceeding anonymously.")

    return L

def extract_shortcode(url: str) -> str:
    try:
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in ["p", "reel"]:
            return parts[1]
    except Exception:
        pass
    raise HTTPException(status_code=400, detail="Invalid Instagram URL")

def serialize_post(p: instaloader.Post):
    return {
        "shortcode": p.shortcode,
        "owner": p.owner_username,
        "url": f"https://www.instagram.com/p/{p.shortcode}/",
        "is_video": p.is_video,
        "display_url": getattr(p, "url", None),
        "video_url": getattr(p, "video_url", None),
        "caption": p.caption or "",
        "likes": getattr(p, "likes", 0),
        "comments": getattr(p, "comments", 0),
    }

@app.post("/api/fetch")
async def fetch_post(req: FetchRequest):
    shortcode = extract_shortcode(req.url)
    L = get_loader()

    # Try fetching post
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return serialize_post(post)
    except instaloader.exceptions.ConnectionException as e:
        logger.warning(f"Connection issue, trying anonymous fetch: {e}")
        try:
            # Retry with anonymous loader
            anon_loader = instaloader.Instaloader(quiet=True)
            post = instaloader.Post.from_shortcode(anon_loader.context, shortcode)
            return serialize_post(post)
        except Exception as e2:
            logger.error("Anonymous fetch failed: %s", e2)
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Server error: {e2}")
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        raise HTTPException(status_code=403, detail="Private post. Login required or follow the user.")
    except Exception as e:
        logger.error("Error fetching post: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

@app.get("/api/media-proxy/")
async def media_proxy(url: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "application/octet-stream")
            return StreamingResponse(resp.aiter_bytes(), media_type=content_type)
    except Exception as e:
        logger.error("Media proxy failed: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch media: {e}")

@app.get("/health")
async def health():
    return {"ok": True}
