"""
Main Orchestration Script.

Pipeline workflow:
1. Checks manual queue in topics_queue.txt.
2. Auto-generates topics/scripts via Google Gemini if the queue is empty.
3. Generates voiceover audio via Edge-TTS / gTTS.
4. Builds SRT captions with modern YouTube Shorts styling.
5. Fetches stock visuals from Pexels API.
6. Renders final MP4 video via FFmpeg.
7. Uploads video to YouTube via YouTube Data API v3.
"""
import os
import sys
import shutil
import logging
import warnings
import traceback
import datetime
from pathlib import Path

# Suppress non-critical third-party warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Ensure UTF-8 output encoding for terminal logging on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import config
import db_manager
import topic_manager
import script_generator
import tts_generator
import visual_fetcher
import video_builder
import youtube_uploader

# Configure logging format and handler
log_file_path = config.LOGS_DIR / "run.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("yt_automation")

FORMAT_SETTINGS = {
    "short": {
        "orientation": "portrait",
        "size": config.SHORTS_SIZE,
        "segment_duration": 4,
        "target_duration": 45,
    },
    "long": {
        "orientation": "landscape",
        "size": config.LONGFORM_SIZE,
        "segment_duration": 8,
        "target_duration": 300,
    },
}


def produce_one_video(video_format: str) -> str:
    """Produces and uploads a single video for the given format ('short' or 'long')."""
    settings = FORMAT_SETTINGS[video_format]
    run_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{video_format}"
    work_dir = config.OUTPUT_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Resolve Topic & Script (Check manual queue first)
    manual = topic_manager.get_next_manual_entry(video_format)
    if manual and manual["type"] == "script":
        logger.info(f"[{run_id}] Manual script entry found. Processing custom script...")
        topic = manual["content"][:60]
        script_data = script_generator.generate_script(topic, video_format)
        script_data["script"] = manual["content"]
    elif manual and manual["type"] == "topic":
        topic = manual["content"]
        logger.info(f"[{run_id}] Manual topic entry found: '{topic}'")
        script_data = script_generator.generate_script(topic, video_format)
    else:
        logger.info(f"[{run_id}] Manual queue empty. Generating topic via AI...")
        topic = script_generator.generate_topic(video_format)
        logger.info(f"[{run_id}] AI-generated topic: '{topic}'")
        script_data = script_generator.generate_script(topic, video_format)

    title = script_data["title"]
    script_text = script_data["script"]
    description = script_data.get("description", "")
    tags = script_data.get("tags", [])
    logger.info(f"[{run_id}] Generated Title: '{title}'")

    # Step 2: Voiceover Generation
    audio_path = work_dir / "voiceover.mp3"
    word_boundaries = tts_generator.generate_voiceover(script_text, str(audio_path))
    duration = video_builder.get_audio_duration(str(audio_path))
    logger.info(f"[{run_id}] Voiceover generated successfully. Duration: {duration:.1f}s")

    # Step 3: Subtitle SRT Generation
    srt_path = work_dir / "captions.srt"
    video_builder.build_srt(word_boundaries, srt_path, words_per_caption=3)

    # Step 4: Visual Assets Retrieval
    num_clips = max(3, int(duration // settings["segment_duration"]) + 1)
    clips_dir = work_dir / "clips"
    clips = visual_fetcher.fetch_visuals_for_script(script_text, num_clips, settings["orientation"], clips_dir)
    logger.info(f"[{run_id}] Retrieved {len(clips)} visual assets from Pexels.")

    per_segment = duration / len(clips)

    # Step 5: Video Assembly & Rendering
    final_path = work_dir / f"{run_id}.mp4"
    video_builder.build_video(
        clips, per_segment, settings["size"], str(audio_path), srt_path, final_path, work_dir / "segments"
    )
    logger.info(f"[{run_id}] Video rendering completed: {final_path}")

    # Step 6: YouTube Upload
    video_id = youtube_uploader.upload_video(
        str(final_path), title, description, tags, is_short=(video_format == "short")
    )
    logger.info(f"[{run_id}] Successfully uploaded to YouTube. Video ID: {video_id}")

    # Step 7: Record Execution History to Database
    tags_str = ",".join(tags) if isinstance(tags, list) else str(tags)
    db_manager.record_video_history(
        run_id=run_id,
        video_format=video_format,
        topic=topic,
        title=title,
        script=script_text,
        description=description,
        tags=tags_str,
        youtube_video_id=video_id
    )

    # Cleanup temporary directories
    shutil.rmtree(clips_dir, ignore_errors=True)
    shutil.rmtree(work_dir / "segments", ignore_errors=True)

    return video_id


def main() -> int:
    """Executes the daily video production pipeline."""
    db_manager.init_db()
    logger.info("=== Starting Daily Pipeline Run ===")
    jobs = (
        [("short", i) for i in range(config.DAILY_SHORTS_COUNT)] +
        [("long", i) for i in range(config.DAILY_LONGFORM_COUNT)]
    )

    success_count = 0
    failed_count = 0

    for video_format, idx in jobs:
        try:
            produce_one_video(video_format)
            success_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to produce {video_format} video #{idx}: {e}")
            logger.error(traceback.format_exc())
            continue

    logger.info(f"=== Daily Pipeline Finished | Success: {success_count}, Failed: {failed_count} ===")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
