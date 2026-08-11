# YT Automator

An automated end-to-end YouTube content generation and publishing pipeline. **YT Automator** produces, renders, and uploads YouTube Shorts (9:16) and Long-form (16:9) educational content using Google Gemini AI, Microsoft Edge-TTS, Pexels API, FFmpeg, and YouTube Data API v3.

---

## Technical Overview

YT Automator is designed for lightweight, high-performance automated content workflows. Unlike traditional video processing frameworks that rely on heavy Python video wrappers (e.g., MoviePy), YT Automator leverages direct native FFmpeg subprocess pipelines. This eliminates memory leaks, minimizes CPU consumption, and guarantees fast rendering times.

```
+-------------------+      +-------------------+      +-------------------+
| Topic Resolution  | ---> | Script Generation | ---> | TTS Voiceover     |
| (Manual / AI)     |      | (Google Gemini)   |      | (Edge-TTS / gTTS) |
+-------------------+      +-------------------+      +-------------------+
                                                                |
+-------------------+      +-------------------+                v
| YouTube Upload    | <--- | FFmpeg Assembly   | <--- +-------------------+
| (YouTube Data API)|      | & Subtitle Burn   |      | Visual Fetching   |
+-------------------+      +-------------------+      | (Pexels API)      |
                                                      +-------------------+
```

---

## Core Capabilities

- **Intelligent Topic & Script Synthesis**: Leverages Google Gemini models to generate engaging scripts, high-CTR titles, SEO-optimized descriptions, and tags.
- **Manual Override Queue**: Accepts custom topics or pre-written scripts via `topics_queue.txt` before falling back to AI generation.
- **Synchronized Subtitle Overlays**: Produces dynamic word-by-word SRT captions styled with modern yellow text and solid black outlines for YouTube Shorts and Reels.
- **Context-Aware Asset Retrieval**: Queries Pexels API for relevant stock footage and high-resolution images with Ken Burns zoom effects.
- **Direct FFmpeg Rendering**: Composes 30 FPS MP4 video streams, merges AAC voiceover audio, and burns subtitle layers directly via FFmpeg.
- **Automated YouTube Publishing**: Handles OAuth2 authentication, token renewal, and video uploads using YouTube Data API v3.
- **GitHub Actions CI/CD Integration**: Supports 100% cloud-hosted daily execution via scheduled GitHub Actions workflows.

---

## Directory Architecture

```text
yt_automation/
├── .github/
│   └── workflows/
│       └── daily_upload.yml       # Scheduled GitHub Actions CI/CD workflow
├── assets/                        # Local temporary asset storage
├── logs/                          # Pipeline execution log files
├── output/                        # Rendered MP4 output directories
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git exclusion rules for secrets and outputs
├── config.py                      # Centralized configuration and path loader
├── main.py                        # Main pipeline orchestrator script
├── script_generator.py            # Gemini API topic and script generator
├── topic_manager.py               # Manual queue manager
├── tts_generator.py               # Audio voiceover and boundary timing engine
├── video_builder.py               # FFmpeg video assembly and caption builder
├── visual_fetcher.py              # Pexels stock video and photo downloader
├── youtube_uploader.py            # YouTube Data API v3 upload module
├── requirements.txt               # Python package dependencies
├── topics_queue.txt               # Manual override topic queue file
└── README.md                      # Project documentation
```

---

## Prerequisites

- **Python**: Version 3.10 or higher
- **FFmpeg & FFprobe**: Must be installed and accessible in your system `PATH`
- **Google Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com/apikey)
- **Pexels API Key**: Obtain from [Pexels Developer Portal](https://www.pexels.com/api/)
- **Google Cloud Console OAuth Credentials**: Configured for YouTube Data API v3 (Desktop App)

---

## Installation & Setup

### 1. Clone Repository and Environment Setup

```bash
git clone https://github.com/YOUR_USERNAME/yt-automator.git
cd yt-automator

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows PowerShell: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the `.env.example` template to create your local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
GEMINI_API_KEY=your_actual_gemini_api_key
PEXELS_API_KEY=your_actual_pexels_api_key
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
CHANNEL_NICHE=interesting facts and educational content for a general audience
DAILY_SHORTS_COUNT=1
DAILY_LONGFORM_COUNT=1
YOUTUBE_PRIVACY_STATUS=private
```

### 3. YouTube API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable **YouTube Data API v3**.
3. Configure the OAuth Consent Screen and create **OAuth 2.0 Client IDs** (Application type: *Desktop App*).
4. Download the client secret JSON file and save it as `client_secrets.json` in the root directory.

---

## Pipeline Execution

### Local Execution

Run the main orchestrator script:

```bash
python main.py
```

Upon initial execution, a browser tab will prompt you to authenticate your YouTube channel. A `youtube_token.json` credential token will be cached locally for future automated runs.

### Manual Queue Override (`topics_queue.txt`)

To supply custom topics or scripts, add entries to `topics_queue.txt` using the pipe (`|`) delimiter:

```text
# Topic entry: AI writes the script for the specified format
topic|short|Why octopuses have three hearts
topic|long|The history of ancient Roman aqueducts

# Script entry: Uses your custom text directly
script|short|Did you know your brain uses 20 percent of your body energy? That's more than any other organ...
```

Processed queue items are automatically archived to `used_topics.txt`.

---

## Cloud Deployment (GitHub Actions)

YT Automator includes a pre-configured GitHub Actions workflow located at `.github/workflows/daily_upload.yml`.

### Setup Instructions

1. Push your repository to GitHub.
2. In your GitHub repository, navigate to **Settings -> Secrets and variables -> Actions**.
3. Define the following Repository Secrets:

| Secret Name | Description / Value |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API Key |
| `PEXELS_API_KEY` | Your Pexels API Key |
| `YOUTUBE_CLIENT_SECRETS` | Full raw contents of your `client_secrets.json` file |
| `YOUTUBE_TOKEN` | Full raw contents of your generated `youtube_token.json` file |

Once configured, GitHub Actions will automatically execute daily at **12:00 UTC** without requiring active local machines or servers.

---

## Security

- All local secrets (`.env`, `client_secrets.json`, `youtube_token.json`) are excluded from Git tracking via `.gitignore`.
- Video media outputs (`output/`) and log files (`logs/`) are strictly ignored to prevent sensitive data leakage.

---

## License

Distributed under the MIT License. See `LICENSE` for details.
