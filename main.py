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
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return L

class FetchRequest(BaseModel):
    url: str

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
    try:
        shortcode = extract_shortcode(req.url)
        L = get_loader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        data = serialize_post(post)
        return data
    except instaloader.exceptions.ProfileNotExistsException:
        raise HTTPException(status_code=404, detail="Post not found")
    except Exception as e:
        logger.error("Error fetching post: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/media-proxy/")
async def media_proxy(url: str, filename: str = "instagram_reel.mp4"):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "application/octet-stream")

            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"'
            }

            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers=headers
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch media: {e}")


@app.get("/health")
async def health():
    return {"ok": True}
