import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

DB_PATH = "memory.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            session_id TEXT,
            role TEXT,
            content TEXT,
            ts TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_summary (
            session_id TEXT PRIMARY KEY,
            summary_text TEXT,
            summarized_checkpoint INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    return conn    

def save_message(session_id: str, role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO history (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def summarize_batch(existing_summary: str, messages: list[dict]) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    prompt = f"""Existing summary of the conversation so far:
    {existing_summary or "(none yet)"}
    New messages to fold into the summary:{conversation_text}
    Write an updated, concise summary that captures the key facts, decisions, and context from both the existing summary and the new messages. Keep it short."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def get_context(session_id: str, window_size: int = 10) -> str:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM history WHERE session_id = ? ORDER BY ts ASC",
        (session_id,),
    ).fetchall()
    total_count = len(rows)

    summary_row = conn.execute(
        "SELECT summary_text, summarized_checkpoint FROM session_summary WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    existing_summary = summary_row[0] if summary_row else ""
    checkpoint = summary_row[1] if summary_row else 0

    if total_count - checkpoint >= window_size:
        batch = [
            {"role": role, "content": content}
            for role, content in rows[checkpoint:checkpoint + window_size]
        ]
        existing_summary = summarize_batch(existing_summary, batch)
        checkpoint += window_size
        conn.execute(
            """INSERT INTO session_summary (session_id, summary_text, summarized_checkpoint, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   summary_text=excluded.summary_text,
                   summarized_checkpoint=excluded.summarized_checkpoint,
                   updated_at=excluded.updated_at""",
            (session_id, existing_summary, checkpoint, datetime.now().isoformat()),
        )
        conn.commit()

    if checkpoint == 0:
        raw_messages = rows[0:total_count]
    elif total_count % window_size == 0:
        raw_messages = rows[total_count - 1:total_count]
    else:
        raw_messages = rows[checkpoint:]
    conn.close()

    if not existing_summary:
        return "\n".join(f"{role}: {content}" for role, content in raw_messages)
    return f"Summary of earlier conversation: {existing_summary}\n\n" + "\n".join(
        f"{role}: {content}" for role, content in raw_messages
    )
