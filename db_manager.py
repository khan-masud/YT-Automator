"""
Database Manager Module for YT Automator.

Provides SQLite persistence for video generation history, duplicate topic prevention,
and manual topic/script queue management. Designed for REST API and Web Dashboard UI integration.
"""
import sqlite3
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
import config

logger = logging.getLogger("db_manager")


def _get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection configured with dict rows."""
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes SQLite database tables and indices if they do not exist."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                video_format TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                video_format TEXT NOT NULL,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                script TEXT NOT NULL,
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                youtube_video_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_format ON video_history(video_format)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_format_status ON topics_queue(video_format, status)")
        conn.commit()
    logger.info(f"Database initialized at {config.DB_FILE}")


def get_past_topics_for_format(video_format: str) -> List[str]:
    """Retrieves all past topics used for a specific video format (short vs long)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT topic FROM video_history WHERE video_format = ? ORDER BY id DESC",
            (video_format.lower(),)
        )
        rows = cursor.fetchall()
        return [row["topic"] for row in rows if row["topic"]]


def is_topic_duplicate(topic: str, video_format: str, threshold: float = 0.70) -> bool:
    """
    Checks whether a candidate topic is an exact, fuzzy ratio, or keyword overlap duplicate
    against past topics used for the specified video format.
    """
    if not topic:
        return False

    candidate_clean = topic.strip().lower()
    past_topics = get_past_topics_for_format(video_format)
    stop_words = {"is", "are", "the", "a", "an", "in", "on", "of", "to", "for", "and", "or", "it", "you", "your", "why", "how"}
    cand_words = {w for w in candidate_clean.split() if w not in stop_words and len(w) > 2}

    for past in past_topics:
        past_clean = past.strip().lower()
        if candidate_clean == past_clean:
            logger.warning(f"Exact duplicate topic detected for [{video_format}]: '{topic}'")
            return True

        similarity = SequenceMatcher(None, candidate_clean, past_clean).ratio()
        if similarity >= threshold:
            logger.warning(
                f"Fuzzy duplicate topic detected ({similarity:.2%} match) for [{video_format}]: "
                f"'{topic}' matches past topic '{past}'"
            )
            return True

        past_words = {w for w in past_clean.split() if w not in stop_words and len(w) > 2}
        if cand_words and past_words:
            overlap = len(cand_words.intersection(past_words)) / len(cand_words.union(past_words))
            if overlap >= 0.50:
                logger.warning(
                    f"Keyword overlap duplicate topic detected ({overlap:.2%} overlap) for [{video_format}]: "
                    f"'{topic}' matches past topic '{past}'"
                )
                return True

    return False


def record_video_history(
    run_id: str,
    video_format: str,
    topic: str,
    title: str,
    script: str,
    description: str = "",
    tags: str = "",
    youtube_video_id: str = ""
) -> int:
    """Records a completed video and YouTube publishing metadata into video_history table."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO video_history
            (run_id, video_format, topic, title, script, description, tags, youtube_video_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                video_format.lower(),
                topic.strip(),
                title.strip(),
                script.strip(),
                description.strip(),
                tags.strip(),
                youtube_video_id.strip()
            )
        )
        conn.commit()
        record_id = cursor.lastrowid
        logger.info(f"Recorded video history entry #{record_id} for run_id '{run_id}'")
        return record_id


def get_history(video_format: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches video execution history records, suitable for REST API and Web UI endpoints."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        if video_format:
            cursor.execute(
                """
                SELECT * FROM video_history
                WHERE video_format = ?
                ORDER BY id DESC LIMIT ?
                """,
                (video_format.lower(), limit)
            )
        else:
            cursor.execute("SELECT * FROM video_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def enqueue_manual_entry(entry_type: str, video_format: str, content: str) -> int:
    """Enqueues a manual topic or script entry into topics_queue table."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO topics_queue (entry_type, video_format, content, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (entry_type.lower(), video_format.lower(), content.strip())
        )
        conn.commit()
        entry_id = cursor.lastrowid
        logger.info(f"Enqueued manual {entry_type} entry #{entry_id} for format '{video_format}'")
        return entry_id


def get_next_manual_entry(video_format: str) -> Optional[Dict[str, Any]]:
    """Retrieves the oldest pending manual queue entry for the given format."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM topics_queue
            WHERE video_format = ? AND status = 'pending'
            ORDER BY id ASC LIMIT 1
            """,
            (video_format.lower(),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def mark_queue_entry_status(entry_id: int, status: str) -> None:
    """Updates the processing status of a topics_queue entry."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE topics_queue SET status = ? WHERE id = ?", (status, entry_id))
        conn.commit()
