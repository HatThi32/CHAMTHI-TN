"""
Đọc ảnh phiếu trả lời đã tô. Phiên bản này CHỈ dùng Python thuần + Pillow -
KHÔNG dùng NumPy/OpenCV - để loại bỏ hoàn toàn các lỗi build liên quan đến
thư viện native khi đóng gói APK Android (đây là nguyên nhân gây lỗi build
nhiều nhất khi dùng Buildozer/python-for-android).

Quy trình:
  1. Tìm 4 ô vuông đen ở 4 góc ảnh (mốc căn chỉnh) bằng flood-fill vùng tối
     trong từng góc ảnh.
  2. Giải hệ phương trình phối cảnh (homography) bằng phép khử Gauss thuần
     Python, dùng PIL Image.transform(..., Image.PERSPECTIVE, coeffs) để
     "duỗi thẳng" ảnh về đúng kích thước canvas chuẩn.
  3. Lấy mẫu từng ô tròn theo layout chuẩn (dùng PIL.Image.histogram() để
     tính ngưỡng Otsu và tỉ lệ điểm ảnh tối - không cần mảng số).
"""

import json
from PIL import Image

from .layout import build_layout, marker_positions, CANVAS_W, CANVAS_H, MARKER_SIZE, BUBBLE_R, CHARS_PART3

FILL_THRESHOLD = 0.45  # tỉ lệ pixel tối tối thiểu để coi là "đã tô"


class OMRError(Exception):
    pass


# ---------------------------------------------------------------- Giải mã QR
try:
    from pyzbar import pyzbar as _pyzbar
    _QR_BACKEND = "pyzbar"
except Exception:
    try:
        import cv2 as _cv2  # noqa
        _QR_BACKEND = "opencv"
    except Exception:
        _QR_BACKEND = None


def decode_qr(pil_img):
    """Thử tìm và giải mã QR trên ảnh (ảnh gốc, CHƯA warp). Trả về dict
    {'exam_code':.., 'sbd':..} hoặc None nếu không tìm/giải mã được."""
    if _QR_BACKEND is None:
        return None
    try:
        if _QR_BACKEND == "pyzbar":
            results = _pyzbar.decode(pil_img.convert("L"))
            for r in results:
                try:
                    data = json.loads(r.data.decode("utf-8"))
                    if "exam_code" in data:
                        return data
                except Exception:
                    continue
            return None
        else:  # opencv
            import numpy as np
            arr = np.array(pil_img.convert("RGB"))[:, :, ::-1]
            detector = _cv2.QRCodeDetector()
            data, points, _ = detector.detectAndDecode(arr)
            if data:
                try:
                    parsed = json.loads(data)
                    if "exam_code" in parsed:
                        return parsed
                except Exception:
                    return None
            return None
    except Exception:
        return None


# ---------------------------------------------------------------- Otsu (thuần Python)
def _otsu_threshold(gray_img):
    hist = gray_img.histogram()
    total = sum(hist)
    if total == 0:
        return 128
    sum_all = float(sum(i * hist[i] for i in range(256)))
    w_b = 0.0
    sum_b = 0.0
    best_t, max_var = 128, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var, best_t = var_between, t
    return best_t


# ---------------------------------------------------------------- Tìm mốc góc
def _all_dark_blobs(gray_img, threshold):
    w, h = gray_img.size
    pix = gray_img.load()
    visited = [[False] * w for _ in range(h)]
    blobs = []
    for y in range(h):
        for x in range(w):
            if visited[y][x] or pix[x, y] >= threshold:
                continue
            stack = [(y, x)]
            visited[y][x] = True
            ys_all, xs_all = [], []
            while stack:
                cy, cx = stack.pop()
                ys_all.append(cy)
                xs_all.append(cx)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if (0 <= ny < h and 0 <= nx < w and not visited[ny][nx]
                            and pix[nx, ny] < threshold):
                        visited[ny][nx] = True
                        stack.append((ny, nx))
            area = len(ys_all)
            bbox_w = max(xs_all) - min(xs_all) + 1
            bbox_h = max(ys_all) - min(ys_all) + 1
            blobs.append((sum(xs_all) / area, sum(ys_all) / area, area, bbox_w, bbox_h))
    return blobs


def _find_corner_marker(gray_img_full, corner, region_frac=0.30):
    w, h = gray_img_full.size
    rw, rh = int(w * region_frac), int(h * region_frac)
    if corner == "tl":
        box, ox, oy = (0, 0, rw, rh), 0, 0
    elif corner == "tr":
        box, ox, oy = (w - rw, 0, w, rh), w - rw, 0
    elif corner == "bl":
        box, ox, oy = (0, h - rh, rw, h), 0, h - rh
    else:
        box, ox, oy = (w - rw, h - rh, w, h), w - rw, h - rh

    if rw <= 0 or rh <= 0:
        return None
    sub = gray_img_full.crop(box)
    t = _otsu_threshold(sub)
    area_img = sub.size[0] * sub.size[1]
    blobs = _all_dark_blobs(sub, t)
    if not blobs:
        return None

    best = None
    for (cx, cy, area, bbox_w, bbox_h) in blobs:
        if area < area_img * 0.0008 or area > area_img * 0.30:
            continue
        if bbox_h == 0:
            continue
        aspect = bbox_w / float(bbox_h)
        if not (0.6 < aspect < 1.6):
            continue
        solidity = area / float(bbox_w * bbox_h)
        if solidity < 0.55:
            continue
        if best is None or area > best[2]:
            best = (cx, cy, area, bbox_w, bbox_h)

    if best is None:
        return None
    cx, cy, area, bbox_w, bbox_h = best
    return (cx + ox, cy + oy)


# ---------------------------------------------------------------- Homography
def _compute_perspective_coeffs(dst_pts, src_pts):
    n = 8
    A = []
    for (X, Y), (x, y) in zip(dst_pts, src_pts):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y, x])
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y, y])

    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(A[r][col]))
        A[col], A[pivot_row] = A[pivot_row], A[col]
        pivot_val = A[col][col]
        if abs(pivot_val) < 1e-9:
            raise OMRError("Không thể tính toán chỉnh phối cảnh (4 mốc góc bất thường).")
        for c in range(col, n + 1):
            A[col][c] /= pivot_val
        for r in range(n):
            if r == col:
                continue
            factor = A[r][col]
            if factor != 0:
                for c in range(col, n + 1):
                    A[r][c] -= factor * A[col][c]

    return tuple(A[r][n] for r in range(n))


def find_markers_and_warp(pil_img):
    pil_img = pil_img.convert("RGB")
    gray_full = pil_img.convert("L")
    w, h = gray_full.size

    max_dim = 900
    scale = min(1.0, max_dim / float(max(w, h)))
    if scale < 1.0:
        small_img = gray_full.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    else:
        small_img = gray_full
        scale = 1.0

    src_pts_small = {}
    for c in ["tl", "tr", "bl", "br"]:
        pt = _find_corner_marker(small_img, c)
        if pt is None:
            raise OMRError(
                f"Không tìm thấy mốc góc '{c}' trên ảnh. Hãy chụp đủ 4 góc phiếu, "
                "đủ sáng, không bị mờ/loá, và dùng đúng phiếu do app tạo."
            )
        src_pts_small[c] = pt

    src_pts_full = {k: (x / scale, y / scale) for k, (x, y) in src_pts_small.items()}

    mpos = marker_positions()
    half = MARKER_SIZE / 2.0
    dst_pts = [
        (mpos["tl"][0] + half, mpos["tl"][1] + half),
        (mpos["tr"][0] + half, mpos["tr"][1] + half),
        (mpos["br"][0] + half, mpos["br"][1] + half),
        (mpos["bl"][0] + half, mpos["bl"][1] + half),
    ]
    src_pts = [src_pts_full["tl"], src_pts_full["tr"], src_pts_full["br"], src_pts_full["bl"]]

    coeffs = _compute_perspective_coeffs(dst_pts, src_pts)
    warped = pil_img.transform((CANVAS_W, CANVAS_H), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)
    return warped


# ---------------------------------------------------------------- Đọc ô tròn
def _fill_ratio(gray_img, cx, cy, r=BUBBLE_R):
    w, h = gray_img.size
    x1, y1 = max(0, int(cx - r)), max(0, int(cy - r))
    x2, y2 = min(w, int(cx + r)), min(h, int(cy + r))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    patch = gray_img.crop((x1, y1, x2, y2))
    t = _otsu_threshold(patch)
    hist = patch.histogram()
    dark = sum(hist[:t])
    total = patch.size[0] * patch.size[1]
    return dark / float(total) if total else 0.0


def _pick_best(gray_img, bubbles, allow_none=True):
    scored = [(_fill_ratio(gray_img, cx, cy), label) for (cx, cy, label) in bubbles]
    scored.sort(reverse=True)
    if not scored:
        return None
    best_ratio, best_label = scored[0]
    if best_ratio < FILL_THRESHOLD:
        return None if allow_none else best_label
    return best_label


def read_sheet(pil_img, structure):
    qr_data = decode_qr(pil_img)

    warped = find_markers_and_warp(pil_img)
    gray = warped.convert("L")
    layout = build_layout(structure)

    if qr_data is not None and qr_data.get("exam_code"):
        exam_code = str(qr_data["exam_code"])
        sbd = str(qr_data.get("sbd") or "")
        qr_used = True
        if not sbd:
            sbd_digits = []
            for col_bubbles in layout["sbd_bubbles"]:
                digit = _pick_best(gray, col_bubbles, allow_none=False)
                sbd_digits.append(digit or "0")
            sbd = "".join(sbd_digits)
    else:
        qr_used = False
        code_digits = []
        for col_bubbles in layout["exam_code_bubbles"]:
            digit = _pick_best(gray, col_bubbles, allow_none=False)
            code_digits.append(digit or "0")
        exam_code = "".join(code_digits)

        sbd_digits = []
        for col_bubbles in layout["sbd_bubbles"]:
            digit = _pick_best(gray, col_bubbles, allow_none=False)
            sbd_digits.append(digit or "0")
        sbd = "".join(sbd_digits)

    part1 = [_pick_best(gray, item["bubbles"]) for item in layout["part1"]]

    part2 = []
    for item in layout["part2"]:
        row = []
        for sub in item["subs"]:
            gx, gy = sub["dung"]
            sx, sy = sub["sai"]
            ratio_d = _fill_ratio(gray, gx, gy)
            ratio_s = _fill_ratio(gray, sx, sy)
            if ratio_d < FILL_THRESHOLD and ratio_s < FILL_THRESHOLD:
                row.append(None)
            elif ratio_d >= ratio_s:
                row.append(True)
            else:
                row.append(False)
        part2.append(row)

    part3 = []
    for item in layout["part3"]:
        chars = []
        for slot_bubbles in item["slots"]:
            ch = _pick_best(gray, slot_bubbles)
            if ch is not None:
                chars.append(ch)
        part3.append("".join(chars))

    return {
        "exam_code": exam_code,
        "sbd": sbd,
        "qr_used": qr_used,
        "warped_image": warped,
        "answers": {"part1": part1, "part2": part2, "part3": part3},
    }
