[app]
title = Cham Thi Trac Nghiem
package.name = chamthitracnghiem
package.domain = org.thptgrading

source.dir = .
source.include_exts = py,png,jpg,jpeg,json,ttf

version = 0.1.0

# ---------------------------------------------------------------------------
# THƯ VIỆN CẦN THIẾT.
# - "pyzbar" + "zbar": dùng để giải mã QR, NHẸ và build NHANH hơn nếu recipe
#   build thành công trên máy/CI của bạn. Đây là lựa chọn ưu tiên (mặc định).
# - Nếu build LỖI ngay ở bước biên dịch "zbar" hoặc "pyzbar": hãy xoá 2 dòng
#   "pyzbar" và "zbar" dưới đây, rồi thêm "opencv" vào cuối danh sách. Code
#   trong core/omr.py đã tự động dùng OpenCV để đọc QR nếu pyzbar không có,
#   không cần sửa gì thêm. Lưu ý: dùng opencv sẽ khiến APK nặng hơn nhiều
#   (150-250MB) và build lâu hơn (có thể 45-90 phút thay vì ~15-20 phút).
# ---------------------------------------------------------------------------
requirements = python3,kivy==2.3.0,pillow,numpy,openpyxl,plyer,qrcode,opencv

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png

android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET

android.api = 33
android.minapi = 23
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
