"""
Định nghĩa layout (tọa độ) của phiếu trả lời trắc nghiệm chuẩn hoá cho app.
Layout được tính trên một canvas kích thước cố định (CANVAS_W x CANVAS_H).
Cả module vẽ phiếu (template.py) và module đọc phiếu (omr.py) đều dùng
CHUNG hàm build_layout() này để đảm bảo toạ độ luôn khớp nhau.
"""

from dataclasses import dataclass

CANVAS_W = 1240
CANVAS_H = 2150
MARKER_SIZE = 34
MARGIN = 36
BUBBLE_R = 11  # bán kính ô tròn khi vẽ / lấy mẫu

CHARS_PART3 = [str(d) for d in range(10)] + ["-", ","]  # 12 ký tự có thể tô


def marker_positions():
    """Toạ độ góc trên-trái của 4 ô vuông mốc (dùng để căn chỉnh ảnh chụp)."""
    return {
        "tl": (MARGIN, MARGIN),
        "tr": (CANVAS_W - MARGIN - MARKER_SIZE, MARGIN),
        "bl": (MARGIN, CANVAS_H - MARGIN - MARKER_SIZE),
        "br": (CANVAS_W - MARGIN - MARKER_SIZE, CANVAS_H - MARGIN - MARKER_SIZE),
    }


def build_layout(structure):
    """
    Trả về dict mô tả toạ độ tâm (x, y) của mọi ô tròn cần tô trên phiếu,
    tính theo hệ toạ độ canvas chuẩn CANVAS_W x CANVAS_H.
    """
    layout = {
        "canvas": (CANVAS_W, CANVAS_H),
        "exam_code_bubbles": [],   # 2 cột (chục, đơn vị) x 10 hàng (0-9)
        "sbd_bubbles": [],         # 6 cột số báo danh x 10 hàng (0-9)
        "part1": [],
        "part2": [],
        "part3": [],
    }

    # ---------- Mã đề thi: 2 cột x 10 hàng ----------
    x0, y0 = CANVAS_W - 170, 150
    col_gap, row_gap = 46, 30
    for col in range(2):
        bubbles = []
        for row in range(10):
            cx = x0 + col * col_gap
            cy = y0 + row * row_gap
            bubbles.append((cx, cy, str(row)))
        layout["exam_code_bubbles"].append(bubbles)

    # ---------- Số báo danh: 6 cột x 10 hàng ----------
    x0s, y0s = 90, 150
    for col in range(6):
        bubbles = []
        for row in range(10):
            cx = x0s + col * col_gap
            cy = y0s + row * row_gap
            bubbles.append((cx, cy, str(row)))
        layout["sbd_bubbles"].append(bubbles)

    # ---------- Phần I: chọn 1 trong 4 đáp án A-D ----------
    n1 = structure.part1_count
    start_x, start_y = 90, 470
    row_gap1, col_width1, per_col = 32, 260, 15
    for i in range(n1):
        col = i // per_col
        row = i % per_col
        base_x = start_x + col * col_width1
        base_y = start_y + row * row_gap1
        choices = []
        for j, label in enumerate(["A", "B", "C", "D"]):
            cx = base_x + 55 + j * 32
            choices.append((cx, base_y, label))
        layout["part1"].append({"cau": i + 1, "bubbles": choices, "label_pos": (base_x, base_y)})

    # ---------- Phần II: Đúng/Sai, mỗi câu 4 ý a-d ----------
    n2 = structure.part2_count
    start_x2, start_y2 = 90, 990
    block_h = 78
    for i in range(n2):
        base_y = start_y2 + i * block_h
        subs = []
        for j in range(4):
            cx = start_x2 + 150 + j * 68
            subs.append({
                "y": chr(ord('a') + j),
                "dung": (cx, base_y),
                "sai": (cx, base_y + 26),
            })
        layout["part2"].append({"cau": i + 1, "subs": subs, "label_pos": (start_x2, base_y)})

    # ---------- Phần III: trả lời ngắn, mỗi câu 4 ký tự x 12 hàng ----------
    n3 = structure.part3_count
    digits = structure.part3_digits
    start_x3, start_y3 = 90, 1330
    cols_per_row = 3
    block_w = 350
    block_h3 = 390
    slot_w = 34
    row_gap3 = 24
    for i in range(n3):
        grp_row = i // cols_per_row
        grp_col = i % cols_per_row
        base_x = start_x3 + grp_col * block_w
        base_y = start_y3 + grp_row * block_h3
        slots = []
        for d in range(digits):
            slot_bubbles = []
            for r, ch in enumerate(CHARS_PART3):
                cx = base_x + 60 + d * slot_w
                cy = base_y + 22 + r * row_gap3
                slot_bubbles.append((cx, cy, ch))
            slots.append(slot_bubbles)
        layout["part3"].append({"cau": i + 1, "slots": slots, "label_pos": (base_x, base_y - 14)})

    return layout
