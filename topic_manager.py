"""
Manual Queue Manager.

Manages topics and scripts queued in topics_queue.txt.
Format per line:
    topic|short|The mystery of black holes explained
    topic|long|How the Roman Empire really fell
    script|short|Did you know octopuses have three hearts? ...

Processed entries are moved from topics_queue.txt to used_topics.txt.
"""
from typing import Optional, Dict, Any, List
import config
import db_manager


def _read_lines() -> List[str]:
    """Reads all lines from the topic queue file."""
    if not config.TOPIC_QUEUE_FILE.exists():
        config.TOPIC_QUEUE_FILE.touch()
        return []
    with open(config.TOPIC_QUEUE_FILE, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def _write_lines(lines: List[str]) -> None:
    """Overwrites the topic queue file with the remaining lines."""
    with open(config.TOPIC_QUEUE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def _mark_used(raw_line: str) -> None:
    """Appends consumed entry to used_topics.txt log."""
    with open(config.USED_TOPICS_FILE, "a", encoding="utf-8") as f:
        f.write(raw_line + "\n")


def get_next_manual_entry(video_format: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the next matching manual topic or script entry for the specified video format.
    Checks SQLite database queue first, falling back to topics_queue.txt.
    """
    # 1. Check SQLite database queue first
    db_entry = db_manager.get_next_manual_entry(video_format)
    if db_entry:
        db_manager.mark_queue_entry_status(db_entry["id"], "completed")
        return {
            "type": db_entry["entry_type"],
            "format": db_entry["video_format"],
            "content": db_entry["content"],
            "db_id": db_entry["id"]
        }

    # 2. Check text file topics_queue.txt
    lines = _read_lines()
    remaining: List[str] = []
    found: Optional[Dict[str, Any]] = None

    for line in lines:
        stripped = line.strip()
        if found is not None or not stripped or stripped.startswith("#"):
            remaining.append(line)
            continue

        parts = stripped.split("|", 2)
        if len(parts) != 3:
            remaining.append(line)
            continue

        entry_type, entry_format, content = parts
        entry_type = entry_type.strip().lower()
        entry_format = entry_format.strip().lower()

        if entry_format == video_format and entry_type in ("topic", "script"):
            found = {"type": entry_type, "format": entry_format, "content": content.strip()}
            _mark_used(line)
        else:
            remaining.append(line)

    if found is not None:
        _write_lines(remaining)

    return found


def add_topic(content: str, video_format: str = "short", entry_type: str = "topic") -> None:
    """Programmatically enqueues a new topic or script entry to both DB and topics_queue.txt."""
    db_manager.enqueue_manual_entry(entry_type, video_format, content)
    lines = _read_lines()
    lines.append(f"{entry_type}|{video_format}|{content}")
    _write_lines(lines)
