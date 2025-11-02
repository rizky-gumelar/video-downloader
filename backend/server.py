from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor
import shutil

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create downloads directory
DOWNLOADS_DIR = ROOT_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=3)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

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
    download_id: str
    filename: str
    status: str


# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "VidSaver API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


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
        formats.sort(key=lambda x: int(x.resolution.replace('p', '').replace('unknown', '0')) if x.resolution else 0, reverse=True)
        
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


def download_video_sync(url: str, format_id: str, output_path: str) -> str:
    """Synchronous function to download video using yt-dlp"""
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            return output_path
    except Exception as e:
        raise Exception(f"Failed to download video: {str(e)}")


@api_router.post("/video/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """Download video with specified format"""
    try:
        download_id = str(uuid.uuid4())
        output_path = str(DOWNLOADS_DIR / f"{download_id}.%(ext)s")
        
        # Run blocking download in thread pool
        loop = asyncio.get_event_loop()
        downloaded_file = await loop.run_in_executor(
            executor,
            download_video_sync,
            request.url,
            request.format_id,
            output_path
        )
        
        # Get the actual filename
        filename = Path(downloaded_file).name if downloaded_file else f"{download_id}.mp4"
        
        return DownloadResponse(
            download_id=download_id,
            filename=filename,
            status="completed"
        )
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/video/file/{filename}")
async def get_video_file(filename: str):
    """Serve downloaded video file"""
    file_path = DOWNLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


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
async def shutdown_db_client():
    client.close()
    executor.shutdown(wait=True)
