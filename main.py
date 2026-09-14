# -*- coding: utf-8 -*-
"""
App Chấm Thi Trắc Nghiệm - BẢN MOBILE (Kivy/Android)
Cấu trúc đề thi tốt nghiệp THPT 2025 + quét mã QR + xem ảnh minh hoạ kết quả
+ xuất Excel.

LƯU Ý: file này được viết để build ra APK Android bằng Buildozer (xem
buildozer.spec và README_MOBILE.md). Môi trường soạn app này KHÔNG cài được
Kivy (không có mạng), nên phần giao diện Kivy dưới đây CHƯA được chạy thử
trực tiếp - chỉ phần lõi xử lý (core/) đã được kiểm thử kỹ (xem selftest.py
và các bước tự test đã thực hiện). Nếu gặp lỗi nhỏ khi build/chạy thật, đó
nhiều khả năng nằm ở lớp giao diện này, hãy phản hồi lại để chỉnh tiếp.
"""

import os
import io
import json
import traceback
from functools import partial

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
from kivy.uix.image import Image as KivyImage
from kivy.uix.progressbar import ProgressBar
from kivy.uix.filechooser import FileChooserIconView
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp

from PIL import Image as PILImage

from core.config import ExamStructure, AnswerKey, ExamProject
from core.template import generate_template
from core.omr import read_sheet, OMRError
from core.grading import grade_student
from core.review import annotate_result_image
from core.storage import ResultStore
from core.export import export_results_to_excel

try:
    from plyer import camera, filechooser
    PLYER_OK = True
except Exception:
    PLYER_OK = False

try:
    from android.storage import primary_external_storage_path  # noqa
    ANDROID = True
except Exception:
    ANDROID = False


def app_dir():
    """Thư mục lưu dữ liệu app (cấu hình, kết quả, ảnh)."""
    try:
        from kivy.app import App as _A
        d = _A.get_running_app().user_data_dir
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".thpt_grading_app")
        os.makedirs(d, exist_ok=True)
        return d


def pil_to_kivy_texture(pil_img):
    """Chuyển ảnh PIL sang texture Kivy để hiển thị trong widget Image."""
    pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="png")
    buf.seek(0)
    core_img = CoreImage(buf, ext="png")
    return core_img.texture


def show_message(title, message):
    content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    content.add_widget(Label(text=message))
    btn = Button(text="Đóng", size_hint=(1, None), height=dp(44))
    content.add_widget(btn)
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.5))
    btn.bind(on_release=popup.dismiss)
    popup.open()
    return popup


def confirm_dialog(title, message, on_yes):
    content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    content.add_widget(Label(text=message))
    row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
    btn_yes = Button(text="Đồng ý")
    btn_no = Button(text="Hủy")
    row.add_widget(btn_yes)
    row.add_widget(btn_no)
    content.add_widget(row)
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.4))
    btn_no.bind(on_release=popup.dismiss)

    def _yes(*a):
        popup.dismiss()
        on_yes()

    btn_yes.bind(on_release=_yes)
    popup.open()


# ==================================================================== STATE
class AppState:
    """Trạng thái dùng chung toàn app (cấu hình đề thi, đáp án, kết quả)."""

    def __init__(self):
        self.project = ExamProject()
        self.project_path = os.path.join(app_dir(), "exam_project.json")
        self.store = ResultStore(db_path=os.path.join(app_dir(), "results.db"))
        self.images_dir = os.path.join(app_dir(), "graded_images")
        os.makedirs(self.images_dir, exist_ok=True)
        self.load_project_if_exists()

    def load_project_if_exists(self):
        if os.path.exists(self.project_path):
            try:
                self.project = ExamProject.load(self.project_path)
            except Exception:
                traceback.print_exc()

    def save_project(self):
        self.project.save(self.project_path)


STATE = AppState()


# ==================================================================== NAV BAR
def build_nav_bar(sm, active):
    bar = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(2))
    items = [("config", "1. Đề thi"), ("scan", "2. Quét bài"), ("results", "3. Kết quả")]
    for name, label in items:
        btn = ToggleButton(text=label, group="nav", state="down" if name == active else "normal")
        btn.bind(on_release=partial(lambda n, *a: setattr(sm, "current", n), name))
        bar.add_widget(btn)
    return bar


# ==================================================================== SCREEN 1: CONFIG
class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)
        self._build()

    def _build(self):
        self.root_box.clear_widgets()
        self.root_box.add_widget(build_nav_bar(self.manager, "config"))

        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, padding=dp(10), spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        self.root_box.add_widget(scroll)

        s = STATE.project.structure
        grid.add_widget(Label(text="CẤU TRÚC ĐỀ THI", bold=True, size_hint_y=None, height=dp(30)))

        self.subject_in = self._row(grid, "Tên môn thi", s.subject)
        self.p1_count_in = self._row(grid, "Phần I - Số câu", str(s.part1_count))
        self.p1_point_in = self._row(grid, "Phần I - Điểm/câu", str(s.part1_point))
        self.p2_count_in = self._row(grid, "Phần II - Số câu", str(s.part2_count))
        self.p2_1_in = self._row(grid, "Phần II - Điểm nếu đúng 1 ý", str(s.part2_points.get("1", 0.1)))
        self.p2_2_in = self._row(grid, "Phần II - Điểm nếu đúng 2 ý", str(s.part2_points.get("2", 0.25)))
        self.p2_3_in = self._row(grid, "Phần II - Điểm nếu đúng 3 ý", str(s.part2_points.get("3", 0.5)))
        self.p2_4_in = self._row(grid, "Phần II - Điểm nếu đúng 4 ý", str(s.part2_points.get("4", 1.0)))
        self.p3_count_in = self._row(grid, "Phần III - Số câu", str(s.part3_count))
        self.p3_point_in = self._row(grid, "Phần III - Điểm/câu", str(s.part3_point))
        self.p3_digits_in = self._row(grid, "Phần III - Số ký tự đáp án", str(s.part3_digits))

        apply_btn = Button(text="Áp dụng & Lưu cấu trúc", size_hint_y=None, height=dp(48))
        apply_btn.bind(on_release=lambda *a: self._apply())
        grid.add_widget(apply_btn)

        self.max_score_label = Label(text=f"Tổng điểm tối đa: {s.max_score()}", size_hint_y=None, height=dp(28))
        grid.add_widget(self.max_score_label)

        grid.add_widget(Label(text="MÃ ĐỀ & ĐÁP ÁN ĐÚNG", bold=True, size_hint_y=None, height=dp(30)))

        add_key_btn = Button(text="+ Thêm mã đề mới", size_hint_y=None, height=dp(44))
        add_key_btn.bind(on_release=lambda *a: self._add_exam_code())
        grid.add_widget(add_key_btn)

        self.keys_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        self.keys_box.bind(minimum_height=self.keys_box.setter("height"))
        grid.add_widget(self.keys_box)
        self._refresh_keys()

        blank_btn = Button(text="In phiếu trắng (lưu ảnh PNG)", size_hint_y=None, height=dp(44))
        blank_btn.bind(on_release=lambda *a: self._export_blank())
        grid.add_widget(blank_btn)

    def _row(self, grid, label, value):
        box = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        box.add_widget(Label(text=label, size_hint_x=0.6))
        ti = TextInput(text=value, multiline=False, size_hint_x=0.4)
        box.add_widget(ti)
        grid.add_widget(box)
        return ti

    def _apply(self):
        try:
            s = ExamStructure(
                subject=self.subject_in.text or "Môn thi",
                part1_count=int(self.p1_count_in.text),
                part1_point=float(self.p1_point_in.text),
                part2_count=int(self.p2_count_in.text),
                part2_points={
                    "1": float(self.p2_1_in.text), "2": float(self.p2_2_in.text),
                    "3": float(self.p2_3_in.text), "4": float(self.p2_4_in.text),
                },
                part3_count=int(self.p3_count_in.text),
                part3_point=float(self.p3_point_in.text),
                part3_digits=int(self.p3_digits_in.text),
            )
        except ValueError:
            show_message("Lỗi", "Giá trị cấu trúc đề thi không hợp lệ. Vui lòng kiểm tra lại.")
            return
        STATE.project.structure = s
        STATE.save_project()
        self.max_score_label.text = f"Tổng điểm tối đa: {s.max_score()}"
        show_message("OK", "Đã áp dụng & lưu cấu trúc đề thi.")

    def _refresh_keys(self):
        self.keys_box.clear_widgets()
        for code in sorted(STATE.project.answer_keys.keys()):
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
            row.add_widget(Label(text=f"Mã đề {code}"))
            edit_btn = Button(text="Sửa", size_hint_x=0.3)
            edit_btn.bind(on_release=partial(self._edit_exam_code, code))
            del_btn = Button(text="Xóa", size_hint_x=0.3)
            del_btn.bind(on_release=partial(self._delete_exam_code, code))
            row.add_widget(edit_btn)
            row.add_widget(del_btn)
            self.keys_box.add_widget(row)

    def _add_exam_code(self):
        code = f"{len(STATE.project.answer_keys) + 1:02d}"
        key = AnswerKey.blank(STATE.project.structure, code)
        STATE.project.answer_keys[code] = key
        self._edit_exam_code(code)

    def _edit_exam_code(self, code, *a):
        self.manager.get_screen("answerkey").load(code)
        self.manager.current = "answerkey"

    def _delete_exam_code(self, code, *a):
        def do_delete():
            STATE.project.answer_keys.pop(code, None)
            STATE.save_project()
            self._refresh_keys()

        confirm_dialog("Xác nhận", f"Xóa mã đề {code}?", do_delete)

    def _export_blank(self):
        img = generate_template(STATE.project.structure, exam_code="")
        path = os.path.join(app_dir(), "phieu_trang.png")
        img.save(path)
        show_message("Đã tạo", f"Đã lưu phiếu trắng tại:\n{path}")

    def on_pre_enter(self, *a):
        self._build()


# ==================================================================== SCREEN 1b: ANSWER KEY EDIT
class AnswerKeyScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.code = None
        self.layout = BoxLayout(orientation="vertical")
        self.add_widget(self.layout)

    def load(self, code):
        self.code = code
        self.layout.clear_widgets()
        s = STATE.project.structure
        key = STATE.project.answer_keys[code]

        top = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(6), padding=dp(6))
        top.add_widget(Label(text="Mã đề:", size_hint_x=0.3))
        self.code_in = TextInput(text=key.exam_code, multiline=False)
        top.add_widget(self.code_in)
        self.layout.add_widget(top)

        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(10), padding=dp(10))
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        self.layout.add_widget(scroll)

        grid.add_widget(Label(text="PHẦN I - chọn 1 đáp án đúng", bold=True, size_hint_y=None, height=dp(28)))
        self.p1_spinners = []
        for i in range(s.part1_count):
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
            row.add_widget(Label(text=f"Câu {i + 1}", size_hint_x=0.4))
            val = key.part1[i] if i < len(key.part1) else "A"
            sp = Spinner(text=val, values=["A", "B", "C", "D"], size_hint_x=0.6)
            row.add_widget(sp)
            grid.add_widget(row)
            self.p1_spinners.append(sp)

        grid.add_widget(Label(text="PHẦN II - Đúng/Sai (bấm để đổi Đ/S)", bold=True, size_hint_y=None, height=dp(28)))
        self.p2_toggles = []
        for i in range(s.part2_count):
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
            row.add_widget(Label(text=f"C{i + 1}", size_hint_x=0.15))
            existing = key.part2[i] if i < len(key.part2) else [False] * 4
            toggles = []
            for j, letter in enumerate(["a", "b", "c", "d"]):
                is_true = bool(existing[j])
                tb = ToggleButton(text=f"{letter}:{'Đ' if is_true else 'S'}",
                                   state="down" if is_true else "normal", size_hint_x=0.2125)
                tb.bind(on_release=partial(self._toggle_p2, tb, letter))
                row.add_widget(tb)
                toggles.append(tb)
            grid.add_widget(row)
            self.p2_toggles.append(toggles)

        grid.add_widget(Label(text="PHẦN III - đáp án dạng số (ví dụ: 12,5  -3  0,25)",
                               bold=True, size_hint_y=None, height=dp(28)))
        self.p3_inputs = []
        for i in range(s.part3_count):
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
            row.add_widget(Label(text=f"Câu {i + 1}", size_hint_x=0.4))
            val = key.part3[i] if i < len(key.part3) else ""
            ti = TextInput(text=val, multiline=False, size_hint_x=0.6)
            row.add_widget(ti)
            grid.add_widget(row)
            self.p3_inputs.append(ti)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(8), padding=dp(6))
        save_btn = Button(text="Lưu đáp án")
        save_btn.bind(on_release=lambda *a: self._save())
        back_btn = Button(text="Quay lại")
        back_btn.bind(on_release=lambda *a: setattr(self.manager, "current", "config"))
        btn_row.add_widget(save_btn)
        btn_row.add_widget(back_btn)
        self.layout.add_widget(btn_row)

    def _toggle_p2(self, tb, letter, *a):
        is_true = tb.state == "down"
        tb.text = f"{letter}:{'Đ' if is_true else 'S'}"

    def _save(self):
        new_code = self.code_in.text.strip()
        if not new_code:
            show_message("Lỗi", "Vui lòng nhập mã đề.")
            return
        part1 = [sp.text for sp in self.p1_spinners]
        part2 = [[tb.state == "down" for tb in row] for row in self.p2_toggles]
        part3 = [ti.text.strip() for ti in self.p3_inputs]
        new_key = AnswerKey(exam_code=new_code, part1=part1, part2=part2, part3=part3)
        STATE.project.answer_keys.pop(self.code, None)
        STATE.project.answer_keys[new_code] = new_key
        STATE.save_project()
        show_message("OK", f"Đã lưu đáp án cho mã đề {new_code}.")
        self.manager.current = "config"


# ==================================================================== SCREEN 2: SCAN
class ScanScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queued = []  # list of local file paths chờ chấm
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)
        self._build()

    def _build(self):
        self.root_box.clear_widgets()
        self.root_box.add_widget(build_nav_bar(self.manager, "scan"))

        btn_row = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(6), padding=dp(6))
        cam_btn = Button(text="📷 Chụp ảnh")
        cam_btn.bind(on_release=lambda *a: self._take_photo())
        gallery_btn = Button(text="🖼 Chọn ảnh có sẵn")
        gallery_btn.bind(on_release=lambda *a: self._pick_images())
        btn_row.add_widget(cam_btn)
        btn_row.add_widget(gallery_btn)
        self.root_box.add_widget(btn_row)

        self.queue_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(4), padding=dp(6))
        self.queue_box.bind(minimum_height=self.queue_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.queue_box)
        self.root_box.add_widget(scroll)

        bottom = BoxLayout(size_hint=(1, None), height=dp(60), spacing=dp(6), padding=dp(6))
        grade_btn = Button(text="Bắt đầu chấm")
        grade_btn.bind(on_release=lambda *a: self._process_queue())
        clear_btn = Button(text="Xóa danh sách", size_hint_x=0.4)
        clear_btn.bind(on_release=lambda *a: self._clear_queue())
        bottom.add_widget(grade_btn)
        bottom.add_widget(clear_btn)
        self.root_box.add_widget(bottom)

        self.progress = ProgressBar(max=1, value=0, size_hint=(1, None), height=dp(10))
        self.root_box.add_widget(self.progress)

    def _refresh_queue_ui(self):
        self.queue_box.clear_widgets()
        for path, status in self.queued:
            row = BoxLayout(size_hint_y=None, height=dp(36))
            row.add_widget(Label(text=os.path.basename(path), size_hint_x=0.6, shorten=True))
            row.add_widget(Label(text=status, size_hint_x=0.4))
            self.queue_box.add_widget(row)

    def _take_photo(self):
        if not PLYER_OK:
            show_message("Thiếu thư viện", "Cần thư viện 'plyer' để dùng camera. Hãy kiểm tra requirements.")
            return
        path = os.path.join(app_dir(), f"capture_{len(self.queued) + 1}.jpg")
        try:
            camera.take_picture(filename=path, on_complete=self._on_photo_taken)
        except NotImplementedError:
            show_message("Không hỗ trợ", "Thiết bị/nền tảng hiện tại không hỗ trợ chụp ảnh qua plyer.")

    def _on_photo_taken(self, path):
        def add_it(dt):
            if path and os.path.exists(path):
                self.queued.append([path, "Chờ xử lý"])
                self._refresh_queue_ui()
        Clock.schedule_once(add_it, 0)

    def _pick_images(self):
        if PLYER_OK:
            try:
                filechooser.open_file(on_selection=self._on_images_picked, multiple=True,
                                       filters=[["Ảnh", "*.jpg", "*.jpeg", "*.png"]])
                return
            except Exception:
                pass
        # Dự phòng: dùng FileChooser của Kivy nếu plyer không khả dụng (ví dụ khi test trên desktop)
        self._open_kivy_filechooser()

    def _on_images_picked(self, selection):
        def add_it(dt):
            for p in selection or []:
                self.queued.append([p, "Chờ xử lý"])
            self._refresh_queue_ui()
        Clock.schedule_once(add_it, 0)

    def _open_kivy_filechooser(self):
        content = BoxLayout(orientation="vertical")
        chooser = FileChooserIconView(filters=["*.png", "*.jpg", "*.jpeg"])
        content.add_widget(chooser)
        btn_row = BoxLayout(size_hint=(1, None), height=dp(48))
        ok_btn = Button(text="Chọn")
        cancel_btn = Button(text="Hủy")
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)
        popup = Popup(title="Chọn ảnh", content=content, size_hint=(0.95, 0.95))

        def do_ok(*a):
            for p in chooser.selection:
                self.queued.append([p, "Chờ xử lý"])
            self._refresh_queue_ui()
            popup.dismiss()

        ok_btn.bind(on_release=do_ok)
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _clear_queue(self):
        self.queued = []
        self._refresh_queue_ui()

    def _process_queue(self):
        if not STATE.project.answer_keys:
            show_message("Chưa có đáp án", "Hãy khai báo ít nhất một mã đề & đáp án ở Tab 1 trước.")
            return
        if not self.queued:
            show_message("Danh sách trống", "Hãy chụp/chọn ảnh phiếu trả lời trước.")
            return
        self.progress.max = len(self.queued)
        self.progress.value = 0
        Clock.schedule_once(lambda dt: self._process_one(0), 0.05)

    def _process_one(self, idx):
        if idx >= len(self.queued):
            self._refresh_queue_ui()
            show_message("Hoàn tất", "Đã xử lý xong. Xem kết quả ở Tab 3.")
            return
        path, _ = self.queued[idx]
        try:
            pil_img = PILImage.open(path).convert("RGB")
            read = read_sheet(pil_img, STATE.project.structure)
            exam_code, sbd = read["exam_code"], read["sbd"]
            key = STATE.project.answer_keys.get(exam_code)
            if key is None:
                self.queued[idx][1] = f"Lỗi: chưa có đáp án mã đề '{exam_code}'"
            else:
                result = grade_student(STATE.project.structure, key, read["answers"])
                annotated = annotate_result_image(read["warped_image"], STATE.project.structure,
                                                   key, read["answers"], result)
                img_name = f"{sbd}_{exam_code}_{idx}.png"
                img_path = os.path.join(STATE.images_dir, img_name)
                annotated.save(img_path)
                STATE.store.add_result(sbd, exam_code, result, source_image=img_path)
                self.queued[idx][1] = f"OK - {result['total']} điểm" + (" (QR)" if read["qr_used"] else "")
        except OMRError as e:
            self.queued[idx][1] = f"Lỗi OMR: {e}"
        except Exception as e:
            traceback.print_exc()
            self.queued[idx][1] = f"Lỗi: {e}"
        self.progress.value = idx + 1
        self._refresh_queue_ui()
        Clock.schedule_once(lambda dt: self._process_one(idx + 1), 0.02)

    def on_pre_enter(self, *a):
        self._refresh_queue_ui()


# ==================================================================== SCREEN 3: RESULTS
class ResultsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)
        self._build()

    def _build(self):
        self.root_box.clear_widgets()
        self.root_box.add_widget(build_nav_bar(self.manager, "results"))

        btn_row = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(6), padding=dp(6))
        refresh_btn = Button(text="Làm mới")
        refresh_btn.bind(on_release=lambda *a: self._refresh())
        export_btn = Button(text="Xuất Excel")
        export_btn.bind(on_release=lambda *a: self._export())
        clear_btn = Button(text="Xóa hết")
        clear_btn.bind(on_release=lambda *a: self._clear_all())
        btn_row.add_widget(refresh_btn)
        btn_row.add_widget(export_btn)
        btn_row.add_widget(clear_btn)
        self.root_box.add_widget(btn_row)

        self.list_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(4), padding=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.list_box)
        self.root_box.add_widget(scroll)
        self._refresh()

    def _refresh(self):
        self.list_box.clear_widgets()
        rows = STATE.store.all_results()
        header = BoxLayout(size_hint_y=None, height=dp(30))
        for text, w in [("SBD", 0.25), ("Mã đề", 0.15), ("Điểm", 0.15), ("Thời gian", 0.25), ("", 0.2)]:
            header.add_widget(Label(text=text, bold=True, size_hint_x=w))
        self.list_box.add_widget(header)
        for row in rows:
            _id, sbd, exam_code, p1, p2, p3, total, source_image, created_at = row
            item = BoxLayout(size_hint_y=None, height=dp(40))
            item.add_widget(Label(text=sbd, size_hint_x=0.25))
            item.add_widget(Label(text=exam_code, size_hint_x=0.15))
            item.add_widget(Label(text=str(total), size_hint_x=0.15))
            item.add_widget(Label(text=str(created_at)[:16], size_hint_x=0.25, font_size="11sp"))
            view_btn = Button(text="Xem ảnh", size_hint_x=0.2)
            view_btn.bind(on_release=partial(self._view_image, source_image, sbd, exam_code, total))
            item.add_widget(view_btn)
            self.list_box.add_widget(item)

    def _view_image(self, image_path, sbd, exam_code, total, *a):
        if not image_path or not os.path.exists(image_path):
            show_message("Không có ảnh", "Không tìm thấy ảnh minh hoạ cho kết quả này.")
            return
        content = BoxLayout(orientation="vertical")
        pil_img = PILImage.open(image_path)
        texture = pil_to_kivy_texture(pil_img)
        img_widget = KivyImage(texture=texture, allow_stretch=True)
        content.add_widget(img_widget)
        close_btn = Button(text="Đóng", size_hint=(1, None), height=dp(48))
        content.add_widget(close_btn)
        popup = Popup(title=f"SBD {sbd} - Mã đề {exam_code} - {total} điểm",
                       content=content, size_hint=(0.97, 0.97))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _export(self):
        rows = STATE.store.all_results()
        if not rows:
            show_message("Không có dữ liệu", "Chưa có kết quả nào để xuất.")
            return
        path = os.path.join(app_dir(), "ket_qua_cham_thi.xlsx")
        export_results_to_excel(rows, path)
        show_message("Đã xuất", f"Đã lưu file Excel tại:\n{path}\n\n"
                                 "Dùng ứng dụng Quản lý file trên điện thoại để mở/chia sẻ file này.")

    def _clear_all(self):
        def do_clear():
            STATE.store.clear()
            self._refresh()
        confirm_dialog("Xác nhận", "Xóa toàn bộ kết quả đã chấm?", do_clear)

    def on_pre_enter(self, *a):
        self._refresh()


# ==================================================================== APP
class ThptGradingApp(App):
    def build(self):
        self.title = "Chấm Thi Trắc Nghiệm"
        Window.softinput_mode = "below_target"
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(AnswerKeyScreen(name="answerkey"))
        sm.add_widget(ScanScreen(name="scan"))
        sm.add_widget(ResultsScreen(name="results"))
        sm.current = "config"
        return sm


if __name__ == "__main__":
    ThptGradingApp().run()
