"""Lưu kết quả chấm bài vào SQLite để xem lại / xuất báo cáo."""

import sqlite3
import json
import os


class ResultStore:
    def __init__(self, db_path="results.db"):
        self.db_path = db_path
        self._ensure()

    def _ensure(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sbd TEXT,
                exam_code TEXT,
                part1_score REAL,
                part2_score REAL,
                part3_score REAL,
                total REAL,
                detail_json TEXT,
                source_image TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def add_result(self, sbd, exam_code, result, source_image=""):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO results (sbd, exam_code, part1_score, part2_score, part3_score, total, detail_json, source_image)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sbd, exam_code, result["part1_score"], result["part2_score"], result["part3_score"],
             result["total"], json.dumps(result, ensure_ascii=False), source_image),
        )
        conn.commit()
        conn.close()

    def all_results(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT id, sbd, exam_code, part1_score, part2_score, part3_score, total, source_image, created_at "
            "FROM results ORDER BY id"
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM results")
        conn.commit()
        conn.close()
