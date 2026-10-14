"""YouTube uploader for the Happy Little Stars automation pipeline.

Uses a pre-authorized OAuth token in local or GitHub Actions runs. Never starts
an interactive browser login in CI; refresh failures are reported clearly.
"""
from pathlib import Path
from typing import List, Optional
import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials() -> Credentials:
    """Load or refresh pre-authorized OAuth credentials without interactive login."""
    token_file = Path(config.YOUTUBE_TOKEN_FILE)
    client_file = Path(config.YOUTUBE_CLIENT_SECRETS_FILE)

    if not token_file.is_file():
        raise RuntimeError(
            f"YouTube token file not found: {token_file}. Configure the YOUTUBE_TOKEN "
            "GitHub Actions secret with the complete authorized-user token JSON."
        )

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    except Exception as exc:
        raise RuntimeError(
            "Could not read youtube_token.json. Ensure YOUTUBE_TOKEN contains the "
            "complete authorized-user token JSON, not the OAuth client-secrets JSON."
        ) from exc

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as exc:
            raise RuntimeError(
                "YouTube OAuth token refresh failed. Re-authorize the YouTube account, "
                "then update the YOUTUBE_TOKEN GitHub Actions secret with the new token JSON. "
                "No browser login can run inside GitHub Actions."
            ) from exc

    if not client_file.is_file():
        raise RuntimeError(
            f"OAuth client file not found: {client_file}. Check the YOUTUBE_CLIENT_SECRETS secret."
        )

    # Do not start InstalledAppFlow/run_local_server in a headless CI runner.
    raise RuntimeError(
        "YouTube credentials are missing, invalid, or have no refresh token. "
        "Create a valid authorized-user token locally with the YouTube upload scope, "
        "then update the YOUTUBE_TOKEN GitHub Actions secret."
    )


def upload_video(video_path: str, title: str, description: str, tags: List[str],
                 is_short: bool, privacy_status: Optional[str] = None) -> str:
    """Upload a video; preschool content is marked as made for kids."""
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    if is_short:
        if "#shorts" not in title.lower():
            title = f"{title} #Shorts"
        if "#shorts" not in description.lower():
            description = f"{description}\n\n#Shorts"

    status = privacy_status or config.YOUTUBE_PRIVACY_STATUS
    if status not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": status,
            "selfDeclaredMadeForKids": True,
        },
    }

    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id", "")
    if not video_id:
        raise RuntimeError("YouTube upload completed without returning a video ID")
    return video_id
