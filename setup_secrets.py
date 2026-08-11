"""
Setup Secrets Module for CI/CD environment (GitHub Actions).

Reads GitHub Secrets from environment variables and writes them to local
configuration files (.env, client_secrets.json, youtube_token.json).
"""
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("setup_secrets")


def setup_secrets() -> None:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    yt_client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS", "").strip()
    yt_token = os.getenv("YOUTUBE_TOKEN", "").strip()

    missing_secrets = []
    if not gemini_key:
        missing_secrets.append("GEMINI_API_KEY")
    if not pexels_key:
        missing_secrets.append("PEXELS_API_KEY")
    if not yt_client_secrets:
        missing_secrets.append("YOUTUBE_CLIENT_SECRETS")
    if not yt_token:
        missing_secrets.append("YOUTUBE_TOKEN")

    if missing_secrets:
        logger.error(f"Missing required GitHub Secrets: {', '.join(missing_secrets)}")
        logger.error(
            "Action Required: Please go to GitHub Repository -> Settings -> Secrets and variables -> Actions "
            "and add the missing secret keys."
        )
        sys.exit(1)

    # Write .env file
    with open(".env", "w", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={gemini_key}\n")
        f.write(f"PEXELS_API_KEY={pexels_key}\n")
        f.write("CHANNEL_NICHE=interesting facts and educational content for a general audience\n")
        f.write("DAILY_SHORTS_COUNT=1\n")
        f.write("DAILY_LONGFORM_COUNT=1\n")
        privacy_status = os.getenv("YOUTUBE_PRIVACY_STATUS", "public").strip()
        f.write(f"YOUTUBE_PRIVACY_STATUS={privacy_status}\n")

    # Write client_secrets.json
    with open("client_secrets.json", "w", encoding="utf-8") as f:
        f.write(yt_client_secrets)

    # Write youtube_token.json
    with open("youtube_token.json", "w", encoding="utf-8") as f:
        f.write(yt_token)

    logger.info("Successfully configured environment files for CI/CD execution.")


if __name__ == "__main__":
    setup_secrets()
