from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=3)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class VideoInfoRequest(BaseModel):
    url: str

class VideoFormat(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    format_note: Optional[str] = None

class VideoInfoResponse(BaseModel):
    title: str
    thumbnail: str
    duration: int
    formats: List[VideoFormat]
    video_id: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str

class DownloadResponse(BaseModel):
    download_url: str
    title: str
    ext: str


# Routes
@api_router.get("/")
async def root():
    return {"message": "VidSaver API"}


def get_video_info_sync(url: str) -> dict:
    """Synchronous function to get video info using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        raise Exception(f"Failed to extract video info: {str(e)}")


@api_router.post("/video/info", response_model=VideoInfoResponse)
async def get_video_info(request: VideoInfoRequest):
    """Get video information and available formats"""
    try:
        # Run blocking operation in thread pool
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_video_info_sync, request.url)
        
        # Extract relevant formats (video with audio or video only with reasonable quality)
        formats = []
        seen_resolutions = set()
        
        for fmt in info.get('formats', []):
            if fmt.get('vcodec') != 'none':  # Has video
                resolution = fmt.get('resolution') or f"{fmt.get('height', 'unknown')}p"
                format_note = fmt.get('format_note', '')
                
                # Prefer formats with both video and audio
                if resolution not in seen_resolutions or fmt.get('acodec') != 'none':
                    formats.append(VideoFormat(
                        format_id=fmt['format_id'],
                        ext=fmt['ext'],
                        resolution=resolution,
                        filesize=fmt.get('filesize'),
                        format_note=format_note
                    ))
                    seen_resolutions.add(resolution)
        
        # Sort by quality (height)
        def get_resolution_height(format_obj):
            if not format_obj.resolution:
                return 0
            resolution = format_obj.resolution
            try:
                # Handle formats like "720p"
                if 'p' in resolution:
                    return int(resolution.replace('p', ''))
                # Handle formats like "256x144"
                elif 'x' in resolution:
                    return int(resolution.split('x')[1])
                # Handle "unknown" or other formats
                else:
                    return 0
            except (ValueError, IndexError):
                return 0
        
        formats.sort(key=get_resolution_height, reverse=True)
        
        return VideoInfoResponse(
            title=info.get('title', 'Unknown'),
            thumbnail=info.get('thumbnail', ''),
            duration=info.get('duration', 0),
            formats=formats[:10],  # Limit to top 10 formats
            video_id=info.get('id', '')
        )
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


def get_download_url_sync(url: str, format_id: str) -> dict:
    """Synchronous function to get direct download URL using yt-dlp"""
    ydl_opts = {
        'format': format_id,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get the direct download URL
            download_url = info.get('url')
            title = info.get('title', 'video')
            ext = info.get('ext', 'mp4')
            
            return {
                'download_url': download_url,
                'title': title,
                'ext': ext
            }
    except Exception as e:
        raise Exception(f"Failed to get download URL: {str(e)}")


@api_router.post("/video/download", response_model=DownloadResponse)
async def get_download_link(request: DownloadRequest):
    """Get direct download link for video without downloading to server"""
    try:
        # Run blocking operation in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            get_download_url_sync,
            request.url,
            request.format_id
        )
        
        return DownloadResponse(
            download_url=result['download_url'],
            title=result['title'],
            ext=result['ext']
        )
    except Exception as e:
        logger.error(f"Error getting download link: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_executor():
    executor.shutdown(wait=True)
