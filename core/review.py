"""
Vẽ chú giải chấm điểm trực tiếp lên ảnh phiếu đã chuẩn hoá (warped), để
giáo viên/học sinh xem lại: khoanh XANH = học sinh chọn ĐÚNG, khoanh ĐỎ =
học sinh chọn SAI, khoanh XANH DƯƠNG (viền) = đáp án đúng học sinh bỏ lỡ.
"""

from PIL import Image, ImageDraw, ImageFont

from .layout import build_layout, BUBBLE_R

COLOR_CORRECT = (0, 170, 0)       # xanh lá - học sinh chọn đúng
COLOR_WRONG = (220, 0, 0)         # đỏ - học sinh chọn sai
COLOR_MISSED_KEY = (0, 90, 220)   # xanh dương - đáp án đúng bị bỏ lỡ
RING_WIDTH = 4


def _font(size=13):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _ring(draw, cx, cy, color, r=BUBBLE_R + 4):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=RING_WIDTH)


def annotate_result_image(warped_img, structure, key, student_answers, grade_result):
    """
    warped_img: ảnh PIL đã được chuẩn hoá về canvas chuẩn (kết quả của
                omr.find_markers_and_warp).
    Trả về một ảnh PIL mới (copy) đã vẽ chú giải.
    """
    img = warped_img.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    layout = build_layout(structure)
    font = _font(12)

    # ----- Phần I -----
    for i, item in enumerate(layout["part1"]):
        given = student_answers["part1"][i] if i < len(student_answers["part1"]) else None
        correct = key.part1[i]
        bubble_map = {label: (cx, cy) for (cx, cy, label) in item["bubbles"]}
        if given == correct:
            _ring(draw, *bubble_map[correct], COLOR_CORRECT)
        else:
            if given in bubble_map:
                _ring(draw, *bubble_map[given], COLOR_WRONG)
            _ring(draw, *bubble_map[correct], COLOR_MISSED_KEY)

    # ----- Phần II -----
    for i, item in enumerate(layout["part2"]):
        given_row = student_answers["part2"][i] if i < len(student_answers["part2"]) else [None] * 4
        correct_row = key.part2[i]
        for j, sub in enumerate(item["subs"]):
            given_val = given_row[j] if j < len(given_row) else None
            correct_val = correct_row[j]
            pos = sub["dung"] if correct_val else sub["sai"]
            given_pos = sub["dung"] if given_val else sub["sai"]
            if given_val is not None and given_val == correct_val:
                _ring(draw, *given_pos, COLOR_CORRECT)
            else:
                if given_val is not None:
                    _ring(draw, *given_pos, COLOR_WRONG)
                _ring(draw, *pos, COLOR_MISSED_KEY)

    # ----- Phần III -----
    for i, item in enumerate(layout["part3"]):
        given = student_answers["part3"][i] if i < len(student_answers["part3"]) else ""
        correct = key.part3[i]
        detail = grade_result["part3_detail"][i]
        lx, ly = item["label_pos"]
        color = COLOR_CORRECT if detail["ket_qua"] else COLOR_WRONG
        draw.rectangle([lx - 4, ly - 2, lx + 70, ly + 16], outline=color, width=2)
        if not detail["ket_qua"]:
            draw.text((lx, ly + 20), f"Đáp án đúng: {correct}", font=font, fill=COLOR_MISSED_KEY)

    # ----- Nhãn tổng điểm ở đầu ảnh -----
    total = grade_result["total"]
    draw.rectangle([0, 0, 260, 40], fill=(255, 255, 255))
    draw.text((10, 8), f"TỔNG ĐIỂM: {total}", font=_font(20), fill=(0, 0, 0))

    return img
