"""
Sinh ảnh phiếu trả lời trắc nghiệm (trống, để in ra cho học sinh tô) theo
đúng toạ độ trong layout.py. Phiếu có 4 ô vuông đen ở 4 góc làm mốc căn
chỉnh cho module OMR khi đọc ảnh chụp/scan lại.
"""

import json
from PIL import Image, ImageDraw, ImageFont

from .layout import build_layout, marker_positions, CANVAS_W, CANVAS_H, MARKER_SIZE, BUBBLE_R, CHARS_PART3
from .config import ExamStructure

try:
    import qrcode
    QRCODE_AVAILABLE = True
except Exception:
    QRCODE_AVAILABLE = False

QR_BOX = (CANVAS_W // 2 - 90, 100, 180, 180)  # (x, y, w, h)


def _draw_qr(img, exam_code, sbd=None):
    """Vẽ mã QR chứa {"exam_code":..., "sbd":...} vào giữa đầu phiếu, để
    app quét nhận diện mã đề/SBD nhanh và chính xác hơn tô bong bóng số.
    Nếu thư viện `qrcode` chưa được cài, vẽ khung placeholder thay thế
    (phiếu vẫn tạo được, chỉ là chưa có QR thật)."""
    x, y, w, h = QR_BOX
    if not QRCODE_AVAILABLE:
        d = ImageDraw.Draw(img)
        d.rectangle([x, y, x + w, y + h], outline=(0, 0, 0), width=2)
        d.text((x + 10, y + h // 2 - 10), "(Chưa cài qrcode)", font=_font(11), fill=(150, 0, 0))
        return
    payload = json.dumps({"exam_code": exam_code or "", "sbd": sbd or ""}, ensure_ascii=False)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((w, h), Image.NEAREST)
    img.paste(qr_img, (x, y))


def _font(size=16, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_bubble(draw, cx, cy, label, filled=False):
    r = BUBBLE_R
    outline = (0, 0, 0)
    fill = (0, 0, 0) if filled else None
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=outline, fill=fill, width=2)
    f = _font(11)
    tw = draw.textlength(label, font=f)
    text_color = (255, 255, 255) if filled else (0, 0, 0)
    draw.text((cx - tw / 2, cy - 7), label, font=f, fill=text_color)


def generate_template(structure: ExamStructure, exam_code: str = "", out_path: str = None,
                       filled_answers: dict = None, sbd: str = None):
    """
    Vẽ phiếu trả lời trống. Nếu truyền filled_answers (định dạng giống
    student_answers trong grading.py) thì sẽ tô sẵn để phục vụ TỰ KIỂM THỬ
    module OMR (mô phỏng một phiếu đã được học sinh tô).
    `sbd`: nếu có, sẽ được nhúng vào mã QR (và tô sẵn ô số báo danh) để in
    phiếu riêng cho từng học sinh.
    """
    layout = build_layout(structure)
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(img)

    # 4 mốc góc
    for (mx, my) in marker_positions().values():
        draw.rectangle([mx, my, mx + MARKER_SIZE, my + MARKER_SIZE], fill=(0, 0, 0))

    title_font = _font(22, bold=True)
    label_font = _font(14, bold=True)
    small_font = _font(12)

    draw.text((CANVAS_W / 2 - 160, 55), f"PHIẾU TRẢ LỜI TRẮC NGHIỆM - {structure.subject}",
              font=title_font, fill=(0, 0, 0))

    # Số báo danh
    draw.text((90, 105), "Số báo danh", font=label_font, fill=(0, 0, 0))
    filled_sbd = sbd.zfill(6) if sbd else None
    for col_idx, col_bubbles in enumerate(layout["sbd_bubbles"]):
        for (cx, cy, ch) in col_bubbles:
            fill = filled_sbd is not None and col_idx < len(filled_sbd) and filled_sbd[col_idx] == ch
            draw_bubble(draw, cx, cy, ch, filled=fill)

    # Mã QR (chứa mã đề + SBD, để quét nhận diện nhanh)
    _draw_qr(img, exam_code, sbd)

    # Mã đề
    draw.text((CANVAS_W - 170, 105), "Mã đề thi", font=label_font, fill=(0, 0, 0))
    filled_code = exam_code.zfill(2) if exam_code else None
    for col_idx, col_bubbles in enumerate(layout["exam_code_bubbles"]):
        for (cx, cy, ch) in col_bubbles:
            fill = filled_code is not None and filled_code[col_idx] == ch
            draw_bubble(draw, cx, cy, ch, filled=fill)

    # Phần I
    draw.text((90, 435), "Phần I. Trắc nghiệm nhiều lựa chọn (chọn 1 đáp án)", font=label_font, fill=(0, 0, 0))
    p1_given = filled_answers.get("part1") if filled_answers else None
    for item in layout["part1"]:
        lx, ly = item["label_pos"]
        draw.text((lx, ly - 7), f"Câu {item['cau']}", font=small_font, fill=(0, 0, 0))
        given = p1_given[item["cau"] - 1] if p1_given else None
        for (cx, cy, label) in item["bubbles"]:
            draw_bubble(draw, cx, cy, label, filled=(given == label))

    # Phần II
    draw.text((90, 960), "Phần II. Đúng/Sai (mỗi câu 4 ý a, b, c, d)", font=label_font, fill=(0, 0, 0))
    p2_given = filled_answers.get("part2") if filled_answers else None
    for item in layout["part2"]:
        lx, ly = item["label_pos"]
        draw.text((lx, ly - 7), f"Câu {item['cau']}", font=small_font, fill=(0, 0, 0))
        given_row = p2_given[item["cau"] - 1] if p2_given else None
        for j, sub in enumerate(item["subs"]):
            gx, gy = sub["dung"]
            sx, sy = sub["sai"]
            draw.text((gx - 26, gy - 17), sub["y"], font=small_font, fill=(0, 0, 0))
            draw.text((gx + 16, gy - 6), "Đ", font=small_font, fill=(0, 0, 0))
            draw.text((sx + 16, sy - 6), "S", font=small_font, fill=(0, 0, 0))
            val = given_row[j] if given_row else None
            draw_bubble(draw, gx, gy, "", filled=(val is True))
            draw_bubble(draw, sx, sy, "", filled=(val is False))

    # Phần III
    draw.text((90, 1300), "Phần III. Trả lời ngắn (tô đáp án dạng số)", font=label_font, fill=(0, 0, 0))
    p3_given = filled_answers.get("part3") if filled_answers else None
    for item in layout["part3"]:
        lx, ly = item["label_pos"]
        draw.text((lx, ly - 7), f"Câu {item['cau']}", font=small_font, fill=(0, 0, 0))
        ans = (p3_given[item["cau"] - 1] if p3_given else "") or ""
        ans = ans.replace(".", ",")
        for d, slot_bubbles in enumerate(item["slots"]):
            ch_at_pos = ans[d] if d < len(ans) else None
            for (cx, cy, ch) in slot_bubbles:
                draw_bubble(draw, cx, cy, ch, filled=(ch_at_pos == ch))

    if out_path:
        img.save(out_path)
    return img
