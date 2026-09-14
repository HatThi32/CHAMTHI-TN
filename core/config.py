"""
Cấu hình cấu trúc đề thi & đáp án đúng.
Chuẩn hoá theo cấu trúc đề thi tốt nghiệp THPT 2025 (3 dạng câu hỏi):
  - Phần I : Trắc nghiệm nhiều lựa chọn (chọn 1 trong 4: A/B/C/D)
  - Phần II: Trắc nghiệm Đúng/Sai (mỗi câu có 4 ý a,b,c,d)
  - Phần III: Trắc nghiệm trả lời ngắn (đáp án dạng số)
"""

import json
import os
from dataclasses import dataclass, field, asdict


@dataclass
class ExamStructure:
    subject: str = "Môn thi"
    part1_count: int = 12
    part1_point: float = 0.25
    part2_count: int = 4
    # điểm theo số ý đúng trong 1 câu Đúng/Sai: 1 ý=0.1, 2 ý=0.25, 3 ý=0.5, 4 ý=1.0
    part2_points: dict = field(default_factory=lambda: {"1": 0.1, "2": 0.25, "3": 0.5, "4": 1.0})
    part3_count: int = 6
    part3_point: float = 0.5
    part3_digits: int = 4  # số ký tự tối đa của đáp án phần III

    def max_score(self):
        return round(
            self.part1_count * self.part1_point
            + self.part2_count * self.part2_points.get("4", 1.0)
            + self.part3_count * self.part3_point,
            2,
        )


@dataclass
class AnswerKey:
    exam_code: str
    part1: list             # ['A', 'B', 'C', ...] dài part1_count
    part2: list             # list[list[bool]] dài part2_count, mỗi phần tử 4 bool (a,b,c,d) True=Đúng
    part3: list             # list[str] dài part3_count, đáp án số dạng chuỗi, ví dụ "12.5", "-3", "0,25"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return AnswerKey(**d)

    @staticmethod
    def blank(structure: ExamStructure, exam_code: str):
        return AnswerKey(
            exam_code=exam_code,
            part1=["A"] * structure.part1_count,
            part2=[[False, False, False, False] for _ in range(structure.part2_count)],
            part3=[""] * structure.part3_count,
        )


class ExamProject:
    """Gói toàn bộ 1 kỳ thi: cấu trúc đề + nhiều mã đề (mỗi mã đề có đáp án riêng)."""

    def __init__(self, structure: ExamStructure = None, answer_keys: dict = None):
        self.structure = structure or ExamStructure()
        self.answer_keys = answer_keys or {}  # {exam_code: AnswerKey}

    def save(self, path: str):
        data = {
            "structure": asdict(self.structure),
            "answer_keys": {code: k.to_dict() for code, k in self.answer_keys.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "ExamProject":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        structure = ExamStructure(**data["structure"])
        keys = {code: AnswerKey.from_dict(k) for code, k in data.get("answer_keys", {}).items()}
        return ExamProject(structure, keys)
