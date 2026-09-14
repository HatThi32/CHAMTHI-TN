"""
Script tự kiểm thử phần LÕI xử lý (không cần điện thoại, không cần Kivy).
Chạy: python selftest.py

Kiểm tra toàn bộ luồng: sinh phiếu (kèm QR nếu có lib 'qrcode') -> mô phỏng
ảnh chụp (xoay/nghiêng/thu nhỏ/phóng to độ phân giải camera) -> đọc phiếu
(OMR + QR) -> chấm điểm -> vẽ ảnh minh hoạ đúng/sai -> so sánh với kỳ vọng.
"""
import sys
sys.path.insert(0, ".")

from PIL import Image, ImageOps

from core.config import ExamStructure, AnswerKey
from core.template import generate_template, QRCODE_AVAILABLE
from core.omr import read_sheet, _QR_BACKEND
from core.grading import grade_student
from core.review import annotate_result_image

print("=" * 70)
print(f"Thư viện 'qrcode' (tạo QR) có sẵn: {QRCODE_AVAILABLE}")
print(f"Backend giải mã QR đang dùng     : {_QR_BACKEND}")
print("=" * 70)

structure = ExamStructure(part1_count=12, part2_count=4, part3_count=6)

key = AnswerKey(
    exam_code="21",
    part1=["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D"],
    part2=[
        [True, False, True, True],
        [False, False, False, False],
        [True, True, True, True],
        [True, False, True, False],
    ],
    part3=["12,5", "-3", "0,25", "100", "7", "-1,5"],
)

student = {
    "part1": ["A", "B", "C", "D", "A", "B", "C", "A", "A", "B", "C", "D"],  # sai câu 8
    "part2": [
        [True, False, True, True],
        [False, False, False, True],
        [True, True, False, True],
        [True, False, True, False],
    ],
    "part3": ["12,5", "-3", "0,3", "100", "7", "-1,5"],  # sai câu 3
}

sbd = "000123"
img = generate_template(structure, exam_code=key.exam_code, sbd=sbd, filled_answers=student)
img.save("test_filled_sheet.png")

# Mô phỏng ảnh chụp điện thoại: xoay nhẹ + thu nhỏ + viền trắng + phóng to
# lên độ phân giải camera thật (~12MP)
rotated = img.rotate(2.5, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
padded = ImageOps.expand(rotated, border=100, fill=(255, 255, 255))
big = padded.resize((3024, int(3024 * padded.size[1] / padded.size[0])), Image.BICUBIC)
big.save("test_simulated_photo.jpg", quality=90)

read = read_sheet(big, structure)
print("\nKẾT QUẢ ĐỌC PHIẾU:")
print("  Mã đề     :", read["exam_code"], " (kỳ vọng:", key.exam_code, ")")
print("  SBD       :", read["sbd"], " (kỳ vọng:", sbd, ")")
print("  Dùng QR?  :", read["qr_used"],
      "(True nếu QR thật được tạo & giải mã đúng; False = đã tự chuyển sang đọc qua ô tô)")

assert read["exam_code"] == key.exam_code, "SAI mã đề!"
assert read["answers"]["part1"] == student["part1"], "SAI phần I!"
assert read["answers"]["part2"] == student["part2"], "SAI phần II!"
assert [a.replace(".", ",") for a in read["answers"]["part3"]] == student["part3"], "SAI phần III!"

result = grade_student(structure, key, read["answers"])
print("\nKẾT QUẢ CHẤM ĐIỂM:")
print("  Điểm phần I  :", result["part1_score"])
print("  Điểm phần II :", result["part2_score"])
print("  Điểm phần III:", result["part3_score"])
print("  TỔNG ĐIỂM    :", result["total"], "/", structure.max_score())
assert result["total"] == 8.25, "Sai tổng điểm kỳ vọng!"

annotated = annotate_result_image(read["warped_image"], structure, key, read["answers"], result)
annotated.save("test_annotated_result.png")
print("\nĐã lưu ảnh minh hoạ đúng/sai tại: test_annotated_result.png")

print("\n>>> SELF-TEST PASSED OK <<<")
if not QRCODE_AVAILABLE:
    print("\n[Lưu ý] Chưa cài thư viện 'qrcode' trong môi trường này nên phiếu test")
    print("chưa có QR thật (đã tự chuyển sang đọc qua ô tô số, vẫn cho kết quả")
    print("đúng). Sau khi `pip install -r requirements.txt` đầy đủ, chạy lại")
    print("script này để kiểm tra luôn cả đường QR thật.")
