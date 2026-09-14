# App Chấm Thi Trắc Nghiệm - BẢN ĐIỆN THOẠI (Android)

Chấm bài trắc nghiệm theo **cấu trúc đề thi tốt nghiệp THPT 2025** (3 dạng câu
hỏi), quét **mã QR** để nhận mã đề/số báo danh, chụp/quét ảnh phiếu trả lời,
xem lại **ảnh đã chấm có khoanh đúng/sai**, và xuất kết quả ra **Excel** -
tất cả chạy trực tiếp trên điện thoại, không cần mạng khi chấm bài.

## ⚠️ Vì sao mình gửi CODE thay vì file APK cài đặt sẵn?

Môi trường mình dùng để soạn code này **không có kết nối mạng và không có bộ
công cụ Android SDK/NDK**, nên không thể tự build ra file `.apk` ngay được.
Cách thực tế nhất là dùng **GitHub Actions** (dịch vụ build miễn phí của
GitHub) để biên dịch APK giúp bạn trên "máy chủ ảo" có đầy đủ công cụ -
bạn chỉ cần làm theo các bước dưới đây, khoảng 15-30 phút (không cần biết
lập trình Android).

## Phần nào đã được kiểm thử, phần nào chưa?

✅ **Đã kiểm thử kỹ (chạy thật, đối chiếu kết quả đúng 100%)**, nằm trong
thư mục `core/`:
- Sinh phiếu trả lời + mã QR (`template.py`)
- Đọc phiếu: tìm 4 mốc góc, chỉnh phối cảnh, giải mã QR, đọc từng ô tô
  (`omr.py`) - đã test với ảnh xoay nghiêng, thu nhỏ, độ phân giải cao
  (giả lập ảnh chụp điện thoại thật) và đều cho kết quả đúng.
- Chấm điểm theo quy chế 2025 (`grading.py`)
- Vẽ ảnh minh hoạ đúng/sai lên bài đã chấm (`review.py`)
- Xuất Excel (`export.py`), lưu kết quả (`storage.py`)

⚠️ **Chưa chạy thử được** (do máy soạn code không cài được Kivy - thiếu
mạng): lớp giao diện điện thoại trong `main.py`. Mình đã viết cẩn thận theo
đúng API chuẩn của Kivy, nhưng CÓ THỂ có vài lỗi nhỏ về giao diện (layout,
tên hàm callback...) chỉ lộ ra khi chạy thật. Nếu build lỗi hoặc app chạy bị
lỗi ở đâu, gửi lại thông báo lỗi cho mình để mình sửa tiếp - đây là chuyện
bình thường với phần chưa test được trực tiếp.

## 1. Cách lấy file APK cài vào điện thoại

### Bước 1 - Tạo tài khoản & repo GitHub (nếu chưa có)
1. Vào https://github.com , tạo tài khoản miễn phí nếu chưa có.
2. Bấm **New repository**, đặt tên (ví dụ `cham-thi-trac-nghiem`), để ở chế
   độ **Public** hoặc **Private** đều được, bấm **Create repository**.

### Bước 2 - Tải toàn bộ code lên GitHub
Cách đơn giản nhất (không cần dùng lệnh `git`):
1. Giải nén file `.zip` mình gửi ra một thư mục trên máy tính.
2. Trên trang repo vừa tạo, bấm **"uploading an existing file"** (hoặc
   **Add file → Upload files**).
3. Kéo TOÀN BỘ file/thư mục đã giải nén vào (bao gồm cả thư mục ẩn
   `.github/` - nếu trình duyệt không kéo được thư mục ẩn, xem cách dùng
   GitHub Desktop ở khung "Cách khác" dưới đây).
4. Bấm **Commit changes**.

> **Cách khác (khuyên dùng nếu bước trên khó)**: cài **GitHub Desktop**
> (https://desktop.github.com), chọn "Add local repository", chọn thư mục đã
> giải nén, rồi bấm "Publish repository". Cách này tải lên đầy đủ cả thư mục
> `.github/workflows/` mà không bị thiếu.

### Bước 3 - Chờ GitHub tự build APK
1. Vào tab **Actions** trên trang repo của bạn.
2. Sẽ thấy 1 workflow tên **"Build Android APK"** đang chạy (tự chạy ngay
   sau khi bạn tải code lên). Nếu chưa thấy, bấm workflow đó → **Run
   workflow**.
3. Chờ khoảng 15-30 phút (lần build đầu tiên luôn lâu nhất vì phải tải công
   cụ Android). Nếu thấy dấu ✅ xanh là build thành công.

### Bước 4 - Tải file APK về điện thoại
1. Bấm vào lượt chạy vừa xong (dòng có dấu ✅), kéo xuống phần **Artifacts**.
2. Bấm tải file **"cham-thi-trac-nghiem-apk"** (đây là file `.zip` chứa file
   `.apk` bên trong) - có thể tải trực tiếp bằng trình duyệt điện thoại nếu
   bạn đăng nhập GitHub trên điện thoại, hoặc tải về máy tính rồi chuyển qua
   điện thoại (USB, Zalo gửi cho mình, Google Drive...).
3. Giải nén file `.zip`, được file `.apk`.

### Bước 5 - Cài đặt trên điện thoại Android
1. Vào **Cài đặt → Bảo mật (Security)**, bật **"Cho phép cài ứng dụng từ
   nguồn không xác định" (Install unknown apps)** cho ứng dụng bạn dùng để
   mở file (ví dụ Trình quản lý file, hoặc Chrome).
2. Mở file `.apk` vừa tải, bấm **Cài đặt (Install)**.
3. Mở app **"Cham Thi Trac Nghiem"** vừa cài.

## 2. Nếu build bị LỖI trên GitHub Actions

Lỗi hay gặp nhất là ở bước biên dịch thư viện đọc mã QR (`pyzbar`/`zbar`).
Cách khắc phục:
1. Mở file `buildozer.spec` trong repo (bấm vào file → bấm biểu tượng bút ✏️
   để sửa trực tiếp trên GitHub).
2. Tìm dòng bắt đầu bằng `requirements = `.
3. Xoá `pyzbar,zbar` khỏi dòng đó, thêm `opencv` vào cuối. Ví dụ:
   ```
   requirements = python3,kivy==2.3.0,pillow,numpy,openpyxl,plyer,qrcode,opencv
   ```
4. Bấm **Commit changes** - GitHub sẽ tự build lại. Lần này app vẫn đọc
   được mã QR (code đã tự chuyển sang dùng OpenCV), nhưng file APK sẽ nặng
   hơn (150-250MB) và build lâu hơn (có thể 45-90 phút).

Nếu gặp lỗi khác, copy dòng lỗi (trong log của Actions, phần cuối cùng có
chữ "Error") gửi lại cho mình để mình xem giúp.

## 3. Cách dùng app trên điện thoại

### Bước 1 - Cấu hình đề thi & đáp án (Tab "1. Đề thi")
1. Điền số câu mỗi phần, điểm mỗi câu/mỗi mức đúng-sai → bấm **"Áp dụng &
   Lưu cấu trúc"**.
2. Bấm **"+ Thêm mã đề mới"**, nhập đáp án đúng cho mã đề đó (có thể thêm
   nhiều mã đề khác nhau - app tự nhận diện qua QR để chấm đúng đáp án).
3. Bấm **"In phiếu trắng"** để lưu ảnh phiếu trả lời trống ra máy - gửi file
   này đi in (photocopy) phát cho học sinh.

### Bước 2 - Quét & chấm bài (Tab "2. Quét bài")
1. Bấm **"📷 Chụp ảnh"** để chụp trực tiếp phiếu trả lời đã tô, hoặc **"🖼
   Chọn ảnh có sẵn"** nếu bạn đã có ảnh chụp/scan từ trước (chọn được nhiều
   ảnh một lúc).
2. Bấm **"Bắt đầu chấm"**. App sẽ tự:
   - Quét mã QR trên phiếu để biết mã đề + số báo danh (nếu phiếu không có
     QR hoặc quét không được, app tự chuyển sang đọc qua ô tô số như cách
     truyền thống).
   - Đọc đáp án cả 3 phần, so với đáp án đúng, chấm điểm.
   - Lưu lại một ảnh có khoanh xanh (đúng)/đỏ (sai)/xanh dương (đáp án đúng
     bị bỏ lỡ) để xem lại.
3. Ảnh lỗi (không thấy đủ 4 mốc góc, mã đề chưa có đáp án...) sẽ hiện dòng
   trạng thái lỗi cụ thể ngay trong danh sách.

### Bước 3 - Xem & xuất kết quả (Tab "3. Kết quả")
- Xem danh sách tất cả bài đã chấm (số báo danh, mã đề, điểm).
- Bấm **"Xem ảnh"** ở từng dòng để xem lại ảnh bài thi đã khoanh đúng/sai.
- Bấm **"Xuất Excel"** để lưu file `.xlsx` bảng điểm (mở bằng app Quản lý
  file hoặc Excel/Google Sheets trên điện thoại để xem/chia sẻ).

## 4. Lưu ý khi chụp ảnh phiếu trả lời

- Dùng đúng phiếu do app tạo ra (có 4 ô vuông đen ở 4 góc) - không dùng
  phiếu trả lời chính thức của Bộ GD&ĐT vì bố cục khác.
- Chụp lấy đủ 4 góc phiếu vào khung hình, đủ sáng, không mờ/loá.
- App đã được kiểm thử chịu được nghiêng nhẹ, thu nhỏ nhẹ do chụp tay.

## 5. Chạy thử trên máy tính trước khi build APK (khuyên làm)

Nếu bạn có máy tính (Windows/Mac/Linux), nên **chạy thử trên máy tính
trước** để phát hiện sớm các lỗi giao diện (nếu có) mà không cần chờ build
APK mỗi lần:

```bash
pip install -r requirements.txt
python main.py
```

Trên máy tính, tính năng camera/chọn ảnh qua `plyer` có thể không hoạt động
đầy đủ như trên điện thoại (đây là hạn chế của plyer trên desktop, không
phải lỗi) - app sẽ tự chuyển sang dùng bộ chọn file thông thường của Kivy.
Các màn hình khác (cấu hình đề, đáp án, xem kết quả, xuất Excel) chạy được
bình thường trên máy tính.

## 6. Cấu trúc mã nguồn

```
main.py                   # Giao diện Kivy (4 màn hình)
buildozer.spec            # Cấu hình build APK Android
.github/workflows/        # Tự build APK trên GitHub Actions
core/
  layout.py                # Toạ độ chuẩn mọi ô tô trên phiếu
  template.py                # Sinh ảnh phiếu (kèm mã QR)
  omr.py                       # Đọc ảnh phiếu: mốc góc, QR, các ô tô
  config.py                      # Cấu trúc đề thi + đáp án đúng
  grading.py                       # Chấm điểm theo quy chế THPT 2025
  review.py                          # Vẽ ảnh minh hoạ đúng/sai
  storage.py                           # Lưu kết quả (SQLite)
  export.py                              # Xuất Excel
selftest.py                # Script tự kiểm thử phần lõi (không cần điện thoại)
```

Cứ nhắn lại nếu bạn cần mình chỉnh sửa hoặc bổ sung thêm gì nhé!
