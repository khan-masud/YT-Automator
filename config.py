"""
Configuration module for YouTube Automation.
Loads settings, API keys, and environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# API Keys & Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
YOUTUBE_CLIENT_SECRETS_FILE = BASE_DIR / os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE = BASE_DIR / "youtube_token.json"

# Channel & Production Settings
CHANNEL_NICHE = os.getenv("CHANNEL_NICHE", "interesting facts and educational content")
DAILY_SHORTS_COUNT = int(os.getenv("DAILY_SHORTS_COUNT", "1"))
DAILY_LONGFORM_COUNT = int(os.getenv("DAILY_LONGFORM_COUNT", "1"))
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")

# Directory Paths
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "yt_automator.db"
TOPIC_QUEUE_FILE = BASE_DIR / "topics_queue.txt"
USED_TOPICS_FILE = BASE_DIR / "used_topics.txt"

# Voice & Video Specifications
TTS_VOICE = "en-US-ChristopherNeural"
SHORTS_SIZE = (1080, 1920)   # 9:16 aspect ratio
LONGFORM_SIZE = (1920, 1080)  # 16:9 aspect ratio

# Ensure necessary directories exist
for directory in (OUTPUT_DIR, LOGS_DIR, ASSETS_DIR, DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)
