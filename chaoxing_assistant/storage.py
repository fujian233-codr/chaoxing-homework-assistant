from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import Assignment, Course
from .utils import timestamp


DEFAULT_DB_PATH = Path("data/assistant.sqlite3")


SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    account_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    cpi TEXT NOT NULL,
    name TEXT NOT NULL,
    teacher TEXT DEFAULT '',
    isretire INTEGER DEFAULT 0,
    end_date TEXT DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (account_id, course_id)
);
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    remaining_seconds INTEGER,
    detail_url TEXT DEFAULT '',
    requirements TEXT DEFAULT '',
    output_path TEXT DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (account_id, assignment_id)
);
CREATE TABLE IF NOT EXISTS ai_tasks (
    assignment_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT NOT NULL,
    draft_path TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT DEFAULT '',
    PRIMARY KEY (account_id, assignment_id)
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    ran_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    overall_ok INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS run_account_results (
    run_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    ok INTEGER NOT NULL,
    message TEXT DEFAULT '',
    course_count INTEGER DEFAULT 0,
    assignment_count INTEGER DEFAULT 0,
    pending_ai_count INTEGER DEFAULT 0,
    PRIMARY KEY (run_id, account_id)
);
CREATE INDEX IF NOT EXISTS idx_assignments_account_course ON assignments(account_id, course_id);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_account ON ai_tasks(account_id);
"""


class Storage:
    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def upsert_course(self, course: Course) -> None:
        now = timestamp()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO courses (
                    account_id, course_id, class_id, cpi, name, teacher,
                    isretire, end_date, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, course_id) DO UPDATE SET
                    class_id=excluded.class_id,
                    cpi=excluded.cpi,
                    name=excluded.name,
                    teacher=excluded.teacher,
                    isretire=excluded.isretire,
                    end_date=excluded.end_date,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    course.account_id,
                    course.course_id,
                    course.class_id,
                    course.cpi,
                    course.name,
                    course.teacher,
                    course.isretire,
                    course.end_date,
                    now,
                    now,
                ),
            )

    def upsert_assignment(self, assignment: Assignment, output_path: str = "") -> None:
        now = timestamp()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO assignments (
                    assignment_id, account_id, course_id, title, status,
                    remaining_seconds, detail_url, requirements, output_path,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, assignment_id) DO UPDATE SET
                    course_id=excluded.course_id,
                    title=excluded.title,
                    status=excluded.status,
                    remaining_seconds=excluded.remaining_seconds,
                    detail_url=excluded.detail_url,
                    requirements=CASE
                        WHEN excluded.requirements != '' THEN excluded.requirements
                        ELSE assignments.requirements
                    END,
                    output_path=CASE
                        WHEN excluded.output_path != '' THEN excluded.output_path
                        ELSE assignments.output_path
                    END,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    assignment.assignment_id,
                    assignment.account_id,
                    assignment.course_id,
                    assignment.title,
                    assignment.status,
                    assignment.remaining_seconds,
                    assignment.detail_url,
                    assignment.requirements,
                    output_path or assignment.output_path,
                    now,
                    now,
                ),
            )

    def get_assignment(self, account_id: str, assignment_id: str) -> Assignment | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM assignments WHERE account_id=? AND assignment_id=?",
                (account_id, assignment_id),
            ).fetchone()
            if not row:
                return None
            course_row = connection.execute(
                "SELECT * FROM courses WHERE account_id=? AND course_id=?",
                (account_id, row["course_id"]),
            ).fetchone()
        course_name = course_row["name"] if course_row else ""
        class_id = course_row["class_id"] if course_row else ""
        cpi = course_row["cpi"] if course_row else ""
        return Assignment(
            assignment_id=row["assignment_id"],
            account_id=row["account_id"],
            course_id=row["course_id"],
            class_id=class_id,
            cpi=cpi,
            course_name=course_name,
            title=row["title"],
            status=row["status"],
            remaining_seconds=row["remaining_seconds"],
            detail_url=row["detail_url"],
            requirements=row["requirements"],
            output_path=row["output_path"],
            checked_at=row["last_seen_at"],
        )

    def latest_assignments(self, account_id: str) -> list[Assignment]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT a.*, c.name AS course_name, c.class_id, c.cpi
                FROM assignments a
                LEFT JOIN courses c
                    ON c.account_id = a.account_id AND c.course_id = a.course_id
                WHERE a.account_id = ?
                ORDER BY a.last_seen_at DESC, a.title
                """,
                (account_id,),
            ).fetchall()
        return [
            Assignment(
                assignment_id=row["assignment_id"],
                account_id=row["account_id"],
                course_id=row["course_id"],
                class_id=row["class_id"] or "",
                cpi=row["cpi"] or "",
                course_name=row["course_name"] or "",
                title=row["title"],
                status=row["status"],
                remaining_seconds=row["remaining_seconds"],
                detail_url=row["detail_url"],
                requirements=row["requirements"],
                output_path=row["output_path"],
                checked_at=row["last_seen_at"],
            )
            for row in rows
        ]

    def latest_account_status(self, account_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT r.ok, r.message
                FROM run_account_results r
                JOIN runs ON runs.run_id = r.run_id
                WHERE r.account_id = ?
                ORDER BY runs.ran_at DESC
                LIMIT 1
                """,
                (account_id,),
            ).fetchone()
        return {"ok": bool(row["ok"]), "message": row["message"]} if row else None

    def record_ai_task(
        self,
        account_id: str,
        assignment_id: str,
        status: str,
        output_path: str,
        draft_path: str = "",
        error: str = "",
    ) -> None:
        now = timestamp()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_tasks (
                    assignment_id, account_id, status, output_path,
                    draft_path, created_at, updated_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, assignment_id) DO UPDATE SET
                    status=excluded.status,
                    output_path=excluded.output_path,
                    draft_path=excluded.draft_path,
                    updated_at=excluded.updated_at,
                    error=excluded.error
                """,
                (assignment_id, account_id, status, output_path, draft_path, now, now, error),
            )

    def record_run(
        self,
        run_id: str,
        mode: str,
        overall_ok: bool,
        account_results: list[dict[str, Any]],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(run_id, ran_at, mode, overall_ok) VALUES (?, ?, ?, ?)",
                (run_id, timestamp(), mode, int(overall_ok)),
            )
            connection.executemany(
                """
                INSERT INTO run_account_results(
                    run_id, account_id, ok, message, course_count,
                    assignment_count, pending_ai_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        result["account_id"],
                        int(result["ok"]),
                        result.get("message", ""),
                        result.get("course_count", 0),
                        result.get("assignment_count", 0),
                        result.get("pending_ai_count", 0),
                    )
                    for result in account_results
                ],
            )

    def update_assignment_output(self, account_id: str, assignment_id: str, output_path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE assignments SET output_path=? WHERE account_id=? AND assignment_id=?",
                (output_path, account_id, assignment_id),
            )
