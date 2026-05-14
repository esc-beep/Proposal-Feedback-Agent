"""Persistence for feedback runs."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


def build_item_scores(feedback_json: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    scores: Dict[str, Dict[str, int]] = {}
    for key, item in (feedback_json.get("항목별") or {}).items():
        scores[key] = {
            "점수": int(item.get("점수", 0)),
            "만점": int(item.get("만점", 0)),
        }
    return scores


class FeedbackRunStore:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("DATABASE_URL이 설정되지 않았어요.")
        self.database_url = database_url
        self._sqlite_connection: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def initialize(self) -> None:
        if self._is_sqlite:
            with self._lock:
                connection = self._sqlite()
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        team_name TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        total_score INTEGER NOT NULL,
                        max_score INTEGER NOT NULL,
                        item_scores TEXT NOT NULL,
                        feedback_json TEXT NOT NULL,
                        feedback_markdown TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.commit()
            return

        with self._postgres() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_runs (
                    id BIGSERIAL PRIMARY KEY,
                    team_name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    total_score INTEGER NOT NULL,
                    max_score INTEGER NOT NULL,
                    item_scores JSONB NOT NULL,
                    feedback_json JSONB NOT NULL,
                    feedback_markdown TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    def save_feedback_result(self, feedback_json: Dict[str, Any], feedback_markdown: str) -> int:
        item_scores = build_item_scores(feedback_json)
        values = {
            "team_name": str(feedback_json.get("팀명", "")),
            "mode": str(feedback_json.get("모드", "")),
            "total_score": int(feedback_json.get("총점", 0)),
            "max_score": int(feedback_json.get("만점", 0)),
            "item_scores": item_scores,
            "feedback_json": feedback_json,
            "feedback_markdown": feedback_markdown,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if self._is_sqlite:
            with self._lock:
                cursor = self._sqlite().execute(
                    """
                    INSERT INTO feedback_runs (
                        team_name, mode, total_score, max_score, item_scores,
                        feedback_json, feedback_markdown, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["team_name"],
                        values["mode"],
                        values["total_score"],
                        values["max_score"],
                        json.dumps(values["item_scores"], ensure_ascii=False),
                        json.dumps(values["feedback_json"], ensure_ascii=False),
                        values["feedback_markdown"],
                        values["created_at"],
                    ),
                )
                self._sqlite().commit()
                return int(cursor.lastrowid)

        from psycopg.types.json import Jsonb

        with self._postgres() as connection:
            row = connection.execute(
                """
                INSERT INTO feedback_runs (
                    team_name, mode, total_score, max_score, item_scores,
                    feedback_json, feedback_markdown
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    values["team_name"],
                    values["mode"],
                    values["total_score"],
                    values["max_score"],
                    Jsonb(values["item_scores"]),
                    Jsonb(values["feedback_json"]),
                    values["feedback_markdown"],
                ),
            ).fetchone()
            return int(row[0])

    def list_submissions(self) -> list[Dict[str, Any]]:
        columns = "id, team_name, mode, total_score, max_score, item_scores, created_at"
        if self._is_sqlite:
            rows = self._sqlite().execute(
                f"SELECT {columns} FROM feedback_runs ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._summary_from_row(row) for row in rows]

        with self._postgres() as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM feedback_runs ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._summary_from_tuple(row) for row in rows]

    def get_submission(self, run_id: int) -> Optional[Dict[str, Any]]:
        columns = (
            "id, team_name, mode, total_score, max_score, item_scores, "
            "feedback_json, feedback_markdown, created_at"
        )
        if self._is_sqlite:
            row = self._sqlite().execute(
                f"SELECT {columns} FROM feedback_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            return self._detail_from_row(row) if row else None

        with self._postgres() as connection:
            row = connection.execute(
                f"SELECT {columns} FROM feedback_runs WHERE id = %s",
                (run_id,),
            ).fetchone()
            return self._detail_from_tuple(row) if row else None

    def close(self) -> None:
        if self._sqlite_connection is not None:
            self._sqlite_connection.close()
            self._sqlite_connection = None

    @property
    def _is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite://")

    def _sqlite(self) -> sqlite3.Connection:
        if self._sqlite_connection is None:
            path = self.database_url.removeprefix("sqlite:///")
            self._sqlite_connection = sqlite3.connect(path, check_same_thread=False)
            self._sqlite_connection.row_factory = sqlite3.Row
        return self._sqlite_connection

    def _postgres(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL 사용을 위해 psycopg[binary]를 설치해주세요.") from exc

        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")
        return psycopg.connect(url)

    def _summary_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "team_name": row["team_name"],
            "mode": row["mode"],
            "total_score": int(row["total_score"]),
            "max_score": int(row["max_score"]),
            "item_scores": json.loads(row["item_scores"]),
            "created_at": row["created_at"],
        }

    def _detail_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        summary = self._summary_from_row(row)
        summary.update(
            {
                "feedback_json": json.loads(row["feedback_json"]),
                "feedback_markdown": row["feedback_markdown"],
            }
        )
        return summary

    def _summary_from_tuple(self, row: Iterable[Any]) -> Dict[str, Any]:
        id_, team_name, mode, total_score, max_score, item_scores, created_at = row
        return {
            "id": int(id_),
            "team_name": team_name,
            "mode": mode,
            "total_score": int(total_score),
            "max_score": int(max_score),
            "item_scores": item_scores,
            "created_at": _isoformat(created_at),
        }

    def _detail_from_tuple(self, row: Iterable[Any]) -> Dict[str, Any]:
        (
            id_,
            team_name,
            mode,
            total_score,
            max_score,
            item_scores,
            feedback_json,
            feedback_markdown,
            created_at,
        ) = row
        return {
            "id": int(id_),
            "team_name": team_name,
            "mode": mode,
            "total_score": int(total_score),
            "max_score": int(max_score),
            "item_scores": item_scores,
            "feedback_json": feedback_json,
            "feedback_markdown": feedback_markdown,
            "created_at": _isoformat(created_at),
        }


def _isoformat(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
