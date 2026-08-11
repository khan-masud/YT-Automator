"""
YouTube Uploader Module.

Uploads videos to YouTube using YouTube Data API v3.
Handles OAuth2 credentials authentication and token caching.
"""
from typing import List, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials() -> Credentials:
    """Retrieves or refreshes valid OAuth2 credentials for YouTube Data API v3."""
    creds = None
    if config.YOUTUBE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(config.YOUTUBE_TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.YOUTUBE_CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        config.YOUTUBE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_video(video_path: str, title: str, description: str, tags: List[str],
                 is_short: bool, privacy_status: Optional[str] = None) -> str:
    """
    Uploads a video to YouTube and returns the assigned Video ID.
    """
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    if is_short:
        if "#shorts" not in title.lower():
            title = f"{title} #Shorts"
        if "#shorts" not in description.lower():
            description = f"{description}\n\n#Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "27",  # Education category
        },
        "status": {
            "privacyStatus": privacy_status or config.YOUTUBE_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()

    return response.get("id", "")
