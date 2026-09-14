"""
Đọc ảnh phiếu trả lời đã tô (chụp bằng điện thoại) và trả về đáp án của học
sinh. Phiên bản này CHỈ dùng Pillow + NumPy (không dùng OpenCV) để gói APK
Android nhẹ và dễ build hơn (OpenCV rất nặng và khó build cho di động).

Quy trình:
  1. Tìm 4 ô vuông đen ở 4 góc ảnh (mốc căn chỉnh) bằng flood-fill vùng tối
     trong từng góc ảnh (không cần OpenCV).
  2. Giải hệ phương trình homography (biến đổi phối cảnh) bằng NumPy, dùng
     PIL Image.transform(..., Image.PERSPECTIVE, coeffs) để "duỗi thẳng"
     ảnh về đúng kích thước canvas chuẩn.
  3. Lấy mẫu từng ô tròn theo layout chuẩn, tính tỉ lệ điểm ảnh tối để biết
     ô nào đã được tô.
"""

import json
import numpy as np
from PIL import Image

from .layout import build_layout, marker_positions, CANVAS_W, CANVAS_H, MARKER_SIZE, BUBBLE_R, CHARS_PART3
from .template import QR_BOX

FILL_THRESHOLD = 0.45  # tỉ lệ pixel tối tối thiểu để coi là "đã tô"

# ---------------------------------------------------------------- Giải mã QR
# Ưu tiên pyzbar (nhẹ, nhanh); nếu môi trường (ví dụ khi build Android) không
# có pyzbar, thử dùng OpenCV (cv2.QRCodeDetector) như phương án dự phòng.
# Nếu cả hai đều không có, app vẫn hoạt động bằng cách đọc mã đề/SBD qua các
# ô tô số như phiên bản trước (xem read_sheet()).
try:
    from pyzbar import pyzbar as _pyzbar
    _QR_BACKEND = "pyzbar"
except Exception:
    try:
        import cv2 as _cv2
        _QR_BACKEND = "opencv"
    except Exception:
        _QR_BACKEND = None


def decode_qr(pil_img):
    """Thử tìm và giải mã QR trên ảnh (ảnh gốc, CHƯA warp, vì QR tự có khả
    năng chịu góc nghiêng/xoay nhẹ). Trả về dict {'exam_code':.., 'sbd':..}
    hoặc None nếu không tìm/giải mã được."""
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
            arr = np.array(pil_img.convert("RGB"))[:, :, ::-1]  # RGB -> BGR
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



class OMRError(Exception):
    pass


# ---------------------------------------------------------------- Otsu (numpy)
def _otsu_threshold(gray_arr):
    """Tính ngưỡng đen/trắng tối ưu (thuật toán Otsu) chỉ bằng NumPy."""
    hist, _ = np.histogram(gray_arr, bins=256, range=(0, 256))
    total = gray_arr.size
    if total == 0:
        return 128
    sum_all = float(np.dot(hist, np.arange(256)))
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
def _all_dark_blobs(binary, max_components=4000):
    """binary: mảng bool 2D (True = tối). Trả về danh sách các thành phần
    liên thông (cx, cy, area, bbox_w, bbox_h), dùng flood-fill (BFS) thuần
    Python. Trả về TẤT CẢ để bên gọi tự chọn theo hình dạng phù hợp nhất,
    vì thành phần có diện tích lớn nhất không chắc là hình vuông mốc."""
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    blobs = []
    for y in range(h):
        xs = np.nonzero(binary[y] & ~visited[y])[0]
        for x in xs:
            if visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = True
            ys_all, xs_all = [], []
            while stack:
                cy, cx = stack.pop()
                ys_all.append(cy)
                xs_all.append(cx)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            area = len(ys_all)
            bbox_w = max(xs_all) - min(xs_all) + 1
            bbox_h = max(ys_all) - min(ys_all) + 1
            blobs.append((sum(xs_all) / area, sum(ys_all) / area, area, bbox_w, bbox_h))
            if len(blobs) >= max_components:
                break
        if len(blobs) >= max_components:
            break
    return blobs


def _find_corner_marker(gray_arr, corner, region_frac=0.30):
    h, w = gray_arr.shape
    rh, rw = int(h * region_frac), int(w * region_frac)
    if corner == "tl":
        sub, ox, oy = gray_arr[0:rh, 0:rw], 0, 0
    elif corner == "tr":
        sub, ox, oy = gray_arr[0:rh, w - rw:w], w - rw, 0
    elif corner == "bl":
        sub, ox, oy = gray_arr[h - rh:h, 0:rw], 0, h - rh
    else:
        sub, ox, oy = gray_arr[h - rh:h, w - rw:w], w - rw, h - rh

    if sub.size == 0:
        return None
    t = _otsu_threshold(sub)
    binary = sub < t
    area_img = sub.size
    blobs = _all_dark_blobs(binary)
    if not blobs:
        return None

    # Chọn blob tốt nhất: phải gần vuông (marker) và có diện tích hợp lý;
    # trong các blob đạt tiêu chí, ưu tiên blob có diện tích lớn nhất
    # (mốc thường là hình đặc lớn hơn các nét chữ/ô tròn xung quanh).
    best = None
    for (cx, cy, area, bbox_w, bbox_h) in blobs:
        if area < area_img * 0.0008 or area > area_img * 0.30:
            continue
        if bbox_h == 0:
            continue
        aspect = bbox_w / float(bbox_h)
        if not (0.6 < aspect < 1.6):
            continue
        # Độ "đặc" (fill ratio trong bounding box) phải cao vì marker là
        # hình vuông tô đặc, khác với các ký tự/đường viền ô tròn thưa.
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
    """Giải hệ 8 phương trình tuyến tính để tìm hệ số phối cảnh, dùng cho
    PIL Image.transform(size, Image.PERSPECTIVE, coeffs). coeffs map từ
    toạ độ ĐÍCH (canvas chuẩn) sang toạ độ NGUỒN (ảnh chụp gốc)."""
    A, B = [], []
    for (X, Y), (x, y) in zip(dst_pts, src_pts):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        B.append(x)
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
        B.append(y)
    A = np.array(A, dtype=np.float64)
    B = np.array(B, dtype=np.float64)
    coeffs = np.linalg.solve(A, B)
    return tuple(coeffs)


def find_markers_and_warp(pil_img):
    """Tìm 4 mốc góc trên ảnh chụp và trả về ảnh PIL đã "duỗi thẳng" về
    đúng kích thước canvas chuẩn (CANVAS_W x CANVAS_H)."""
    pil_img = pil_img.convert("RGB")
    gray_full = np.array(pil_img.convert("L"), dtype=np.uint8)

    # Tìm nhanh trên ảnh thu nhỏ để đỡ tốn thời gian, sau đó quy đổi lại
    # toạ độ về ảnh gốc.
    h, w = gray_full.shape
    max_dim = 900
    scale = min(1.0, max_dim / float(max(w, h)))
    if scale < 1.0:
        small_img = pil_img.convert("L").resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        gray_small = np.array(small_img, dtype=np.uint8)
    else:
        gray_small = gray_full
        scale = 1.0

    src_pts_small = {}
    for c in ["tl", "tr", "bl", "br"]:
        pt = _find_corner_marker(gray_small, c)
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
def _fill_ratio(gray_arr, cx, cy, r=BUBBLE_R):
    h, w = gray_arr.shape
    x1, y1 = max(0, int(cx - r)), max(0, int(cy - r))
    x2, y2 = min(w, int(cx + r)), min(h, int(cy + r))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    patch = gray_arr[y1:y2, x1:x2]
    t = _otsu_threshold(patch)
    dark = int(np.count_nonzero(patch < t))
    return dark / float(patch.size)


def _pick_best(gray_arr, bubbles, allow_none=True):
    scored = [(_fill_ratio(gray_arr, cx, cy), label) for (cx, cy, label) in bubbles]
    scored.sort(reverse=True)
    if not scored:
        return None
    best_ratio, best_label = scored[0]
    if best_ratio < FILL_THRESHOLD:
        return None if allow_none else best_label
    return best_label


def read_sheet(pil_img, structure):
    """Đọc toàn bộ phiếu. `pil_img` là ảnh PIL (RGB) chụp/scan phiếu đã tô.
    Trả về dict {'exam_code', 'sbd', 'qr_used', 'answers': {'part1','part2','part3'}}."""
    qr_data = decode_qr(pil_img)

    warped = find_markers_and_warp(pil_img)
    gray = np.array(warped.convert("L"), dtype=np.uint8)
    layout = build_layout(structure)

    if qr_data is not None and qr_data.get("exam_code"):
        exam_code = str(qr_data["exam_code"])
        sbd = str(qr_data.get("sbd") or "")
        qr_used = True
        if not sbd:
            # QR không mang SBD (phiếu dùng chung theo mã đề) -> vẫn đọc SBD qua ô tô
            sbd_digits = []
            for col_bubbles in layout["sbd_bubbles"]:
                digit = _pick_best(gray, col_bubbles, allow_none=False)
                sbd_digits.append(digit or "0")
            sbd = "".join(sbd_digits)
    else:
        qr_used = False
        # Không đọc được QR (thiếu thư viện, QR mờ/bị che...) -> dự phòng bằng
        # cách đọc mã đề/SBD qua các ô tô số như phiên bản gốc.
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

    # Phần I
    part1 = [_pick_best(gray, item["bubbles"]) for item in layout["part1"]]

    # Phần II
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

    # Phần III
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
