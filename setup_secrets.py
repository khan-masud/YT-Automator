"""Validate and materialize GitHub Actions secrets for CI/CD runs.

In safe generation-only mode, only GEMINI_API_KEY is required.
YouTube OAuth secrets are validated and materialized only when uploads are enabled.
"""
import json
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("setup_secrets")


def _parse_json_secret(name: str, value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        logger.error("GitHub secret %s is not valid JSON. Paste the complete JSON file contents, not a filename or a partial secret.", name)
        raise SystemExit(1) from exc
    if not isinstance(parsed, dict):
        logger.error("GitHub secret %s must contain a JSON object.", name)
        sys.exit(1)
    return parsed


def setup_secrets() -> None:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    upload_to_youtube = os.getenv("UPLOAD_TO_YOUTUBE", "false").strip().lower() in {"1", "true", "yes", "on"}
    yt_client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS", "").strip()
    yt_token = os.getenv("YOUTUBE_TOKEN", "").strip()

    if not gemini_key:
        logger.error("Missing required GitHub Actions secret: GEMINI_API_KEY")
        sys.exit(1)

    privacy_status = os.getenv("YOUTUBE_PRIVACY_STATUS", "private").strip().lower()
    if privacy_status not in {"private", "unlisted", "public"}:
        logger.error("YOUTUBE_PRIVACY_STATUS must be private, unlisted, or public.")
        sys.exit(1)

    client_data = None
    token_data = None
    if upload_to_youtube:
        missing = [name for name, value in (("YOUTUBE_CLIENT_SECRETS", yt_client_secrets), ("YOUTUBE_TOKEN", yt_token)) if not value]
        if missing:
            logger.error("Uploads are enabled but these GitHub Actions secrets are missing: %s", ", ".join(missing))
            sys.exit(1)
        client_data = _parse_json_secret("YOUTUBE_CLIENT_SECRETS", yt_client_secrets)
        token_data = _parse_json_secret("YOUTUBE_TOKEN", yt_token)
        if not ("installed" in client_data or "web" in client_data):
            logger.error("YOUTUBE_CLIENT_SECRETS must contain an 'installed' or 'web' object.")
            sys.exit(1)
        if not token_data.get("refresh_token") or not token_data.get("client_id") or not token_data.get("client_secret"):
            logger.error("YOUTUBE_TOKEN must be an authorized-user token JSON with refresh_token, client_id, and client_secret.")
            sys.exit(1)
    else:
        logger.info("UPLOAD_TO_YOUTUBE=false: YouTube OAuth secrets are not required; no upload will be attempted.")

    Path(".env").write_text(
        f"GEMINI_API_KEY={gemini_key}\n"
        "CHANNEL_NICHE=preschool nursery rhymes and early learning songs for children ages 2 to 6\n"
        f"DAILY_SHORTS_COUNT={os.getenv('DAILY_SHORTS_COUNT', '1')}\n"
        f"DAILY_LONGFORM_COUNT={os.getenv('DAILY_LONGFORM_COUNT', '0')}\n"
        f"UPLOAD_TO_YOUTUBE={'true' if upload_to_youtube else 'false'}\n"
        f"YOUTUBE_PRIVACY_STATUS={privacy_status}\n",
        encoding="utf-8",
    )
    # These files exist only on the temporary runner; never commit credentials.
    if upload_to_youtube:
        Path("client_secrets.json").write_text(json.dumps(client_data), encoding="utf-8")
        Path("youtube_token.json").write_text(json.dumps(token_data), encoding="utf-8")
    logger.info("Environment configured. Upload enabled: %s", upload_to_youtube)


if __name__ == "__main__":
    setup_secrets()
