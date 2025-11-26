# api/index.py
import os
import tempfile
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Header, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from yt_dlp import YoutubeDL
import httpx
import asyncio
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

# Logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("reels-downloader")

app = FastAPI(title="Instagram Reels Downloader")

# Rate limiter (default 10/minute)
RATE = os.getenv("RATE_LIMIT", "10/minute")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS
origins_env = os.getenv("CORS_ORIGINS", "*")
if origins_env == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

BASE_YDL_OPTS = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
}

async def extract_info_with_ydl(url: str, ydl_opts: dict):
    loop = asyncio.get_running_loop()
    def _extract():
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    try:
        info = await loop.run_in_executor(None, _extract)
        return info
    except Exception as e:
        logger.exception("yt-dlp extraction failed")
        raise HTTPException(status_code=400, detail=f"Failed to extract info: {e}")

def pick_best_media_url(info: dict) -> str:
    if isinstance(info, dict) and "entries" in info and info["entries"]:
        first = info["entries"][0]
    elif isinstance(info, dict):
        first = info
    else:
        raise HTTPException(status_code=500, detail="Unexpected extractor response")

    if first.get("url"):
        return first["url"]

    formats = first.get("formats") or []
    if formats:
        formats_sorted = sorted(formats, key=lambda f: f.get("height") or f.get("tbr") or 0, reverse=True)
        for f in formats_sorted:
            if f.get("url"):
                return f["url"]

    raise HTTPException(status_code=500, detail="Could not find direct media URL")

async def prepare_ydl_opts_from_credentials(username: Optional[str]=None,
                                            password: Optional[str]=None,
                                            cookies_file_path: Optional[str]=None):
    opts = BASE_YDL_OPTS.copy()
    if username:
        opts["username"] = username
    if password:
        opts["password"] = password
    if cookies_file_path:
        opts["cookiefile"] = cookies_file_path
    return opts

async def stream_generator(url: str, chunk_size: int = 1024 * 32):
    timeout = httpx.Timeout(60.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            resp = await client.get(url, stream=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.exception("Failed fetching media")
            raise HTTPException(status_code=502, detail=f"Failed to fetch media: {e}")

        async for chunk in resp.aiter_bytes(chunk_size):
            yield chunk

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

@app.get("/")
async def root():
    return {"message": "Instagram Reels Downloader — gunakan /download (GET or POST)"}

@app.get("/download")
@limiter.limit(RATE)
async def download_get(
    insta_url: str = Query(..., description="URL Instagram Reels / post publik"),
    x_cookies: Optional[str] = Header(None, alias="X-Cookies"),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_password: Optional[str] = Header(None, alias="X-Password"),
):
    cookiefile_path = None
    if x_cookies:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(x_cookies.encode("utf-8"))
        tmp.flush()
        tmp.close()
        cookiefile_path = tmp.name

    try:
        ydl_opts = await prepare_ydl_opts_from_credentials(username=x_username, password=x_password, cookies_file_path=cookiefile_path)
        info = await extract_info_with_ydl(insta_url, ydl_opts)
        media_url = pick_best_media_url(info)

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            head = await client.head(media_url)
            content_type = head.headers.get("content-type") or "application/octet-stream"
            cd = head.headers.get("content-disposition")
            filename = "reel"
            if cd and "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"')
            else:
                ext = "mp4"
                if "/" in content_type:
                    ext_part = content_type.split("/")[-1]
                    if ext_part:
                        ext = ext_part
                filename = f"reel.{ext}"

        return StreamingResponse(stream_generator(media_url), media_type=content_type,
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    finally:
        if cookiefile_path and os.path.exists(cookiefile_path):
            try:
                os.unlink(cookiefile_path)
            except Exception:
                pass

@app.post("/download")
@limiter.limit(RATE)
async def download_post(
    insta_url: str = Query(..., description="URL Instagram Reels / post publik"),
    cookies: Optional[UploadFile] = File(None, description="(optional) upload cookies.txt (Netscape)"),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_password: Optional[str] = Header(None, alias="X-Password"),
):
    cookiefile_path = None
    if cookies:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        content = await cookies.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()
        cookiefile_path = tmp.name

    try:
        ydl_opts = await prepare_ydl_opts_from_credentials(username=x_username, password=x_password, cookies_file_path=cookiefile_path)
        info = await extract_info_with_ydl(insta_url, ydl_opts)
        media_url = pick_best_media_url(info)

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            head = await client.head(media_url)
            content_type = head.headers.get("content-type") or "application/octet-stream"
            cd = head.headers.get("content-disposition")
            filename = "reel"
            if cd and "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"')
            else:
                ext = "mp4"
                if "/" in content_type:
                    ext_part = content_type.split("/")[-1]
                    if ext_part:
                        ext = ext_part
                filename = f"reel.{ext}"

        return StreamingResponse(stream_generator(media_url), media_type=content_type,
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    finally:
        if cookiefile_path and os.path.exists(cookiefile_path):
            try:
                os.unlink(cookiefile_path)
            except Exception:
                pass