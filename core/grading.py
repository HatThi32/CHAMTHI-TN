"""
Chấm điểm theo quy chế đề thi tốt nghiệp THPT 2025:
  - Phần I : mỗi câu đúng được part1_point điểm.
  - Phần II: mỗi câu có 4 ý (a,b,c,d); điểm câu tính theo SỐ Ý ĐÚNG
             (tra trong structure.part2_points), không có điểm cho từng ý riêng lẻ.
  - Phần III: mỗi câu đúng được part3_point điểm (so khớp giá trị số,
             không phân biệt dấu phẩy/chấm thập phân).
"""

from .config import ExamStructure, AnswerKey


def normalize_short_answer(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return round(float(s), 6)
    except ValueError:
        return s.upper()


def grade_student(structure: ExamStructure, key: AnswerKey, student_answers: dict) -> dict:
    result = {
        "part1_detail": [], "part2_detail": [], "part3_detail": [],
        "part1_score": 0.0, "part2_score": 0.0, "part3_score": 0.0,
    }

    # Phần I
    sp1 = student_answers.get("part1", [])
    for i in range(structure.part1_count):
        given = sp1[i] if i < len(sp1) else None
        correct = key.part1[i]
        is_correct = given is not None and given == correct
        if is_correct:
            result["part1_score"] += structure.part1_point
        result["part1_detail"].append(
            {"cau": i + 1, "dap_an": given, "dung": correct, "ket_qua": is_correct}
        )

    # Phần II
    sp2 = student_answers.get("part2", [])
    for i in range(structure.part2_count):
        given = sp2[i] if i < len(sp2) else [None, None, None, None]
        correct = key.part2[i]
        num_correct = sum(1 for g, c in zip(given, correct) if g is not None and g == c)
        point = float(structure.part2_points.get(str(num_correct), 0.0))
        result["part2_score"] += point
        result["part2_detail"].append(
            {"cau": i + 1, "dap_an": given, "dung": correct, "so_y_dung": num_correct, "diem": point}
        )

    # Phần III
    sp3 = student_answers.get("part3", [])
    for i in range(structure.part3_count):
        given = sp3[i] if i < len(sp3) else ""
        correct = key.part3[i]
        is_correct = normalize_short_answer(given) is not None and \
            normalize_short_answer(given) == normalize_short_answer(correct)
        if is_correct:
            result["part3_score"] += structure.part3_point
        result["part3_detail"].append(
            {"cau": i + 1, "dap_an": given, "dung": correct, "ket_qua": is_correct}
        )

    result["part1_score"] = round(result["part1_score"], 2)
    result["part2_score"] = round(result["part2_score"], 2)
    result["part3_score"] = round(result["part3_score"], 2)
    result["total"] = round(result["part1_score"] + result["part2_score"] + result["part3_score"], 2)
    return result
