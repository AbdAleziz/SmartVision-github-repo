# -*- coding: utf-8 -*-
"""
الواجهة الرئيسية لتطبيق Smart Vision Studio.

النافذة مقسومة إلى:
  - شريط جانبي: الكاميرا، الأنماط، إعدادات سريعة، تبديل اللغة والثيم.
  - مساحة رئيسية على شكل تبويبات: المعاهدة، العدّاد، التعرف على الوجوه،
    الماسح، بوث الصور، الإحصائيات، الرسم، الإعدادات.
"""

import os
import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

from .camera import CameraWorker
from .config import CSV_PATH, DATA_DIR, Settings, ensure_dirs
from .i18n import AR, EN
from .i18n import t as translate
from .panels import (CounterPanel, DrawPanel, FaceIDPanel, PhotoBoothPanel,
                     ScannerPanel, SettingsPanel, StatsPanel)
from .theme import FONT_UI, apply_ttk_style, get_theme
from .utils import open_with_default_app
from .vision import (M_ALL, M_COUNTER, M_DRAW, M_FACE, M_FACEID, M_GESTURE,
                      M_MOTION, M_QR, M_SLIDES, M_VOICE)

# وحدات اختيارية (إن غابت لا يتعطّل البرنامج)
try:
    from .telegram import TelegramBot
except Exception:
    TelegramBot = None
try:
    from .stats import StatsStore
except Exception:
    StatsStore = None
try:
    from .scanner import DocumentScanner
except Exception:
    DocumentScanner = None
try:
    from .photobooth import PhotoBooth
except Exception:
    PhotoBooth = None
try:
    from .voice import VoiceController
except Exception:
    VoiceController = None


class _NullScanner(object):
    """بديل بسيط لو تعذّر تحميل وحدة الماسح."""

    def __init__(self):
        self.pages = []

    def scan(self, frame):
        return {"ok": False, "reason": "scanner module missing"}

    def add_page(self, img):
        self.pages.append(img)
        return len(self.pages)

    def clear(self):
        self.pages = []

    def save_pdf(self, filename=None):
        return ""


class _NullPhotoBooth(object):
    def __init__(self):
        self.last = None

    def make(self, frame, faces=None, filter_name="none", frame_on=True,
             blur=True, stamp=None):
        return {"ok": False, "image": None, "path": ""}


class _NoopPanel(object):
    """لوحة بلا محتوى (تُستخدم لتبويب المعاهدة)."""

    def refresh(self):
        pass


class App(tk.Tk):
    MODES = [
        (M_MOTION, "mode.motion"),
        (M_FACE, "mode.face"),
        (M_GESTURE, "mode.gesture"),
        (M_QR, "mode.qr"),
        (M_COUNTER, "mode.counter"),
        (M_FACEID, "mode.faceid"),
        (M_DRAW, "mode.draw"),
        (M_SLIDES, "mode.slides"),
        (M_VOICE, "mode.voice"),
        (M_ALL, "mode.all"),
    ]

    # ================================================================== التهيئة
    def __init__(self):
        tk.Tk.__init__(self)
        ensure_dirs()
        self.settings = Settings()
        self.theme = get_theme(self.settings.get("theme", "dark"))
        self.lang = self.settings.get("language", AR)
        if self.lang not in (AR, EN):
            self.lang = AR

        self.title(translate("app.title", self.lang))
        self.configure(bg=self.theme.bg)
        self.minsize(1080, 700)
        w, h = 1240, 840
        x = max((self.winfo_screenwidth() - w) // 2, 0)
        y = max((self.winfo_screenheight() - h) // 2 - 20, 0)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

        # ---- الحالة ----
        self.events = queue.Queue()
        self.worker = None
        self.wid = 0
        self.mode = None
        self.photo = None
        self.last_code = None
        self.last_code_time = 0.0
        self.last_info = ""
        self.enroll = None
        self.enroll_last = 0.0
        self.last_urls = []

        # ---- المحرّكات ----
        self.face_db = None
        self.attendance = None
        self.counter = None
        self.stats_store = None
        self.telegram = None
        self.voice = None
        self.scanner = DocumentScanner() if DocumentScanner else _NullScanner()
        self.photobooth = PhotoBooth() if PhotoBooth else _NullPhotoBooth()
        self._init_services()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()

    def _init_services(self):
        """يهيّئ الخدمات التي قد تكون غير متوفرة."""
        try:
            from .faceid import AttendanceTracker, FaceDatabase
            self.face_db = FaceDatabase()
            self.attendance = AttendanceTracker()
            try:
                self.face_db.threshold = float(
                    self.settings.get("faceid.threshold", 72))
            except Exception:
                pass
        except Exception:
            self.face_db = None
            self.attendance = None
        try:
            from .counter import PeopleCounter
            self.counter = PeopleCounter(self.settings)
        except Exception:
            self.counter = None
        if StatsStore is not None:
            try:
                self.stats_store = StatsStore()
            except Exception:
                self.stats_store = None
        if TelegramBot is not None:
            try:
                self.telegram = TelegramBot(
                    self.settings.get("telegram.token", ""),
                    self.settings.get("telegram.chat_id", ""))
            except Exception:
                self.telegram = None
        if VoiceController is not None:
            try:
                # الأمر الصوتي يصل من خيط الاستماع → نمرّره لقائمة الأحداث
                # حتى يُنفَّذ في الخيط الرئيسي (Tk غير آمن مع الخيوط).
                self.voice = VoiceController(on_command=self._queue_voice_command)
            except Exception:
                self.voice = None

    # ------------------------------------------------------------- الترجمة
    def t(self, key, **kwargs):
        return translate(key, self.lang, **kwargs)

    # ============================================================ بناء الواجهة
    def _build_ui(self):
        th = self.theme
        self.configure(bg=th.bg)
        apply_ttk_style(self, th)

        # ---------------- الشريط الجانبي ----------------
        side = tk.Frame(self, bg=th.side, width=280)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        head = tk.Frame(side, bg=th.side)
        head.pack(fill=tk.X, padx=18, pady=(18, 4))
        tk.Label(head, text="\u25C9", bg=th.side, fg=th.accent,
                 font=(FONT_UI, 22)).pack(side=tk.LEFT)
        titles = tk.Frame(head, bg=th.side)
        titles.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(titles, text="Smart Vision", bg=th.side, fg=th.text,
                 font=(FONT_UI, 15, "bold")).pack(anchor="w")
        tk.Label(titles, text=self.t("app.subtitle"), bg=th.side, fg=th.muted,
                 font=(FONT_UI, 9)).pack(anchor="w")

        # أزرار اللغة والثيم
        tools = tk.Frame(side, bg=th.side)
        tools.pack(fill=tk.X, padx=18, pady=(10, 0))
        lang_text = "EN" if self.lang == AR else "ع"
        b_lang = tk.Button(tools, text=lang_text, bg=th.btn, fg=th.text, relief=tk.FLAT,
                           activebackground=th.btn_h, font=(FONT_UI, 9, "bold"),
                           command=self.toggle_language, cursor="hand2", bd=0,
                           highlightthickness=0, width=6)
        b_lang.pack(side=tk.LEFT, padx=(0, 6))
        theme_text = "\u2600" if th.is_dark() else "\u263D"
        b_theme = tk.Button(tools, text=theme_text, bg=th.btn, fg=th.text, relief=tk.FLAT,
                            activebackground=th.btn_h, font=(FONT_UI, 11),
                            command=self.toggle_theme, cursor="hand2", bd=0,
                            highlightthickness=0, width=6)
        b_theme.pack(side=tk.LEFT)

        tk.Frame(side, bg=th.border, height=1).pack(fill=tk.X, padx=18, pady=(12, 0))

        # ---------------- الكاميرا ----------------
        self._section(side, self.t("app.camera"))
        row = tk.Frame(side, bg=th.side)
        row.pack(fill=tk.X, padx=18)
        tk.Label(row, text=self.t("app.device_index"), bg=th.side, fg=th.text,
                 font=(FONT_UI, 9)).pack(side=tk.LEFT)
        self.cam_var = tk.StringVar(value=str(self.settings.get("camera_index", 0)))
        self.cam_box = ttk.Combobox(row, textvariable=self.cam_var, state="readonly",
                                    values=["0", "1", "2", "3"], width=4)
        self.cam_box.pack(side=tk.RIGHT)
        self.cam_box.bind("<<ComboboxSelected>>", self.on_camera_index_changed)

        self.btn_cam = tk.Button(side, text="\u25B6  " + self.t("app.start_camera"),
                                 bg=th.start, fg="white", activebackground=th.start_h,
                                 activeforeground="white", relief=tk.FLAT,
                                 font=(FONT_UI, 10, "bold"), command=self.toggle_camera,
                                 cursor="hand2", bd=0, highlightthickness=0)
        self.btn_cam.pack(fill=tk.X, padx=18, pady=(10, 0), ipady=7)

        # ---------------- الأنماط ----------------
        self._section(side, self.t("modes.title"))
        self.mode_buttons = {}
        for i, (key, label) in enumerate(self.MODES):
            b = tk.Button(side, text="%d  %s" % (i + 1, self.t(label)), bg=th.btn,
                          fg=th.text, anchor="w", activebackground=th.btn_active,
                          activeforeground="white", relief=tk.FLAT,
                          font=(FONT_UI, 9), padx=12, cursor="hand2", bd=0,
                          highlightthickness=0,
                          command=lambda k=key: self.set_mode(k))
            b.pack(fill=tk.X, padx=18, pady=2, ipady=5)
            self.mode_buttons[key] = b

        # ---------------- إعدادات سريعة ----------------
        self._section(side, self.t("settings.title"))
        tk.Label(side, text=self.t("settings.motion_sensitivity"), bg=th.side,
                 fg=th.muted, wraplength=235, justify="left",
                 font=(FONT_UI, 8)).pack(anchor="w", padx=18)
        self.area_var = tk.IntVar(value=int(self.settings.get("motion_min_area", 1500)))
        tk.Scale(side, from_=300, to=8000, orient=tk.HORIZONTAL, variable=self.area_var,
                 bg=th.side, fg=th.text, highlightthickness=0, troughcolor=th.btn,
                 activebackground=th.accent, bd=0, sliderrelief=tk.FLAT,
                 font=(FONT_UI, 8), command=self.on_area_changed).pack(fill=tk.X, padx=18)

        self.click_var = tk.BooleanVar(value=bool(self.settings.get("fist_click", True)))
        tk.Checkbutton(side, text=self.t("settings.fist_click"), variable=self.click_var,
                       bg=th.side, fg=th.text, selectcolor=th.btn, activebackground=th.side,
                       activeforeground=th.text, font=(FONT_UI, 9), bd=0,
                       highlightthickness=0, command=self.on_click_toggle
                       ).pack(anchor="w", padx=14, pady=(6, 0))

        self.snap_var = tk.BooleanVar(value=bool(self.settings.get("save_snapshots", True)))
        tk.Checkbutton(side, text=self.t("settings.save_snapshots"), variable=self.snap_var,
                       bg=th.side, fg=th.text, selectcolor=th.btn, activebackground=th.side,
                       activeforeground=th.text, font=(FONT_UI, 9), bd=0,
                       highlightthickness=0, command=self.on_snapshot_toggle
                       ).pack(anchor="w", padx=14)

        b = tk.Button(side, text=self.t("settings.reset_hand_color"), bg=th.btn,
                      fg=th.text, relief=tk.FLAT, activebackground=th.btn_h,
                      activeforeground=th.text, font=(FONT_UI, 9), bd=0,
                      highlightthickness=0, cursor="hand2", command=self.reset_hand_color)
        b.pack(fill=tk.X, padx=18, pady=(10, 0), ipady=4)

        has_pyzbar = False
        has_pyauto = False
        has_face = False
        try:
            from .qr_engine import HAS_PYZBAR
            has_pyzbar = HAS_PYZBAR
        except Exception:
            pass
        try:
            from .vision import HAS_PYAUTOGUI
            has_pyauto = HAS_PYAUTOGUI
        except Exception:
            pass
        try:
            from .faceid import HAS_CVFACE
            has_face = HAS_CVFACE
        except Exception:
            pass
        tk.Label(side, text=self.t("settings.deps") % (
            "ON" if has_pyzbar else "OFF", "ON" if has_pyauto else "OFF",
            "ON" if has_face else "fallback"), bg=th.side, fg=th.muted,
            font=(FONT_UI, 8), wraplength=240, justify="left"
        ).pack(side=tk.BOTTOM, anchor="w", padx=18, pady=12)

        # ---------------- المساحة الرئيسية ----------------
        main = tk.Frame(self, bg=th.bg)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14, pady=14)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.panels = {}
        self._add_tab("tabs.live", self._build_live_tab)
        self._add_tab("tabs.counter", lambda p: CounterPanel(self, p))
        self._add_tab("tabs.faceid", lambda p: FaceIDPanel(self, p))
        self._add_tab("tabs.scanner", lambda p: ScannerPanel(self, p))
        self._add_tab("tabs.photobooth", lambda p: PhotoBoothPanel(self, p))
        self._add_tab("tabs.stats", lambda p: StatsPanel(self, p))
        self._add_tab("tabs.draw", lambda p: DrawPanel(self, p))
        self._add_tab("tabs.settings", lambda p: SettingsPanel(self, p))

    def _add_tab(self, key, builder):
        th = self.theme
        frame = tk.Frame(self.notebook, bg=th.bg)
        self.notebook.add(frame, text=self.t(key))
        panel = builder(frame)
        if panel is None:
            panel = _NoopPanel()
        self.panels[key] = panel
        return panel

    def _section(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=self.theme.side, fg=self.theme.muted,
                 font=(FONT_UI, 8, "bold")).pack(anchor="w", padx=18, pady=(16, 4))

    # ------------------------------------------------------- تبويب المعاهدة
    def _build_live_tab(self, parent):
        th = self.theme
        top = tk.Frame(parent, bg=th.bg)
        top.pack(fill=tk.X)
        tk.Label(top, text=self.t("tabs.live"), bg=th.bg, fg=th.text,
                 font=(FONT_UI, 14, "bold")).pack(side=tk.LEFT)
        self.chip = tk.Label(top, text="\u25CF  " + self.t("app.offline"), bg=th.card,
                             fg=th.muted, font=(FONT_UI, 8, "bold"), padx=10, pady=3)
        self.chip.pack(side=tk.RIGHT)

        body = tk.Frame(parent, bg=th.bg)
        body.pack(fill=tk.BOTH, expand=True)

        video_box = tk.Frame(body, bg="black", width=640, height=480,
                             highlightbackground=th.border, highlightthickness=2)
        video_box.pack(side=tk.LEFT, pady=(10, 0))
        video_box.pack_propagate(False)
        self.video = tk.Label(video_box, text=self.t("app.camera_off"), bg="black",
                              fg=th.muted, font=(FONT_UI, 11), justify="center")
        self.video.place(relx=0.5, rely=0.5, anchor="center")
        self.video.bind("<Button-1>", self.on_video_click)

        side = tk.Frame(body, bg=th.bg, width=320)
        side.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        side.pack_propagate(False)

        card = tk.Frame(side, bg=th.card)
        card.pack(fill=tk.X)
        self.status_var = tk.StringVar(value=self.t("app.ready"))
        tk.Label(card, textvariable=self.status_var, bg=th.card, fg=th.text, anchor="w",
                 font=(FONT_UI, 10, "bold"), wraplength=420, justify="left"
                 ).pack(fill=tk.X, padx=12, pady=(8, 0))
        self.info_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.info_var, bg=th.card, fg=th.accent, anchor="w",
                 font=(FONT_UI, 9), wraplength=420, justify="left"
                 ).pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(side, text=self.t("qr.title"), bg=th.bg, fg=th.muted, anchor="w",
                 font=(FONT_UI, 9, "bold")).pack(fill=tk.X, pady=(12, 4))
        code_frame = tk.Frame(side, bg=th.card)
        code_frame.pack(fill=tk.BOTH, expand=True)
        self.txt = tk.Text(code_frame, height=6, bg=th.card, fg=th.text, bd=0,
                           insertbackground=th.text, relief=tk.FLAT, wrap="word",
                           font=("Consolas", 9), padx=10, pady=8,
                           selectbackground=th.accent, highlightthickness=0)
        scroll = ttk.Scrollbar(code_frame, command=self.txt.yview)
        self.txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btns = tk.Frame(side, bg=th.bg)
        btns.pack(fill=tk.X, pady=(8, 0))
        for text, cmd in ((self.t("app.copy"), self.copy_text),
                          (self.t("app.clear"), lambda: self.txt.delete("1.0", tk.END)),
                          (self.t("qr.open_link"), self.open_last_link),
                          (self.t("qr.scan_image"), self.scan_image_file),
                          (self.t("qr.open_csv"), self.open_log)):
            bt = tk.Button(btns, text=text, bg=th.btn, fg=th.text, relief=tk.FLAT,
                           activebackground=th.btn_h, activeforeground=th.text,
                           font=(FONT_UI, 8, "bold"), command=cmd, cursor="hand2",
                           bd=0, highlightthickness=0)
            bt.pack(side=tk.LEFT, padx=(0, 5), ipady=4)

        tk.Label(side, text=self.t("app.log"), bg=th.bg, fg=th.muted, anchor="w",
                 font=(FONT_UI, 9, "bold")).pack(fill=tk.X, pady=(12, 4))
        log_frame = tk.Frame(side, bg=th.card)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_txt = tk.Text(log_frame, height=5, bg=th.card, fg=th.muted, bd=0,
                               relief=tk.FLAT, wrap="word", font=("Consolas", 8),
                               padx=10, pady=6, highlightthickness=0)
        self.log_txt.pack(fill=tk.BOTH, expand=True)

    # ============================================================ تبديل اللغة/الثيم
    def toggle_language(self):
        self.lang = EN if self.lang == AR else AR
        self.settings.set("language", self.lang)
        self.settings.save()
        self.rebuild()

    def toggle_theme(self):
        name = "light" if self.theme.is_dark() else "dark"
        self.theme = get_theme(name)
        self.settings.set("theme", name)
        self.settings.save()
        self.rebuild()

    def rebuild(self):
        """يعيد بناء الواجهة بالكامل (بعد تغيير اللغة أو الثيم)."""
        try:
            self.stop_camera()
        except Exception:
            pass
        for child in self.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self.photo = None
        self.mode_buttons = {}
        self.panels = {}
        self.title(translate("app.title", self.lang))   # العنوان يتبع اللغة
        self._build_ui()
        self.set_status(self.t("app.ready"))

    # ============================================================ الكاميرا
    def toggle_camera(self):
        if self.worker is None:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        try:
            index = int(self.cam_var.get())
        except ValueError:
            index = 0
        self.wid += 1
        self.worker = CameraWorker(index, self.events, self.wid, self.mode,
                                   self.area_var.get(), self.settings)
        self.worker.processor.click_enabled = self.click_var.get()
        self.apply_telegram()
        self.worker.start()
        th = self.theme
        self.btn_cam.config(text="\u25A0  " + self.t("app.stop_camera"), bg=th.stop,
                             activebackground=th.stop_h)
        self.chip.config(text="\u25CF  " + self.t("app.live"), fg=th.ok)
        self.set_status(self.t("app.opening_camera") % index)

    def stop_camera(self):
        old = self.worker
        self.worker = None
        self.wid += 1
        if old is not None:
            try:
                old.stop()
                old.join(timeout=2.0)
            except Exception:
                pass
        self._ui_camera_off()

    def _ui_camera_off(self):
        th = self.theme
        self.worker = None
        self.btn_cam.config(text="\u25B6  " + self.t("app.start_camera"), bg=th.start,
                             activebackground=th.start_h)
        self.chip.config(text="\u25CF  " + self.t("app.offline"), fg=th.muted)
        self.video.config(image="", text=self.t("app.camera_off"))
        self.photo = None
        self.info_var.set("")

    def on_camera_index_changed(self, _event=None):
        if self.worker is not None:
            self.stop_camera()
            self.start_camera()

    # ============================================================ الأنماط
    def set_mode(self, mode):
        from .vision import HAS_PYAUTOGUI
        if mode == M_GESTURE and not HAS_PYAUTOGUI:
            messagebox.showwarning("PyAutoGUI missing",
                                   "pip install pyautogui==0.9.53")
            return
        self.mode = None if self.mode == mode else mode
        if self.worker is not None:
            self.worker.mode = self.mode
        for key, btn in self.mode_buttons.items():
            btn.config(bg=self.theme.btn_active if key == self.mode else self.theme.btn)

        if self.mode == M_GESTURE:
            self.set_status(self.t("mode.gesture_help"))
        elif self.mode == M_QR:
            self.set_status(self.t("mode.qr_help"))
        elif self.mode == M_COUNTER:
            self.set_status(self.t("mode.counter_help"))
        elif self.mode == M_FACEID:
            self.set_status(self.t("mode.faceid_help"))
        elif self.mode == M_DRAW:
            self.set_status(self.t("mode.draw_help"))
        elif self.mode == None:
            self.set_status(self.t("mode.off"))
        else:
            self.set_status(self.t("mode.active"))
        if self.worker is None and self.mode is not None:
            self.start_camera()

    def on_area_changed(self, value):
        self.settings.set("motion_min_area", int(float(value)))
        self.settings.save()
        if self.worker is not None:
            self.worker.processor.min_area = int(float(value))

    def on_click_toggle(self):
        self.settings.set("fist_click", bool(self.click_var.get()))
        self.settings.save()
        if self.worker is not None:
            self.worker.processor.click_enabled = bool(self.click_var.get())

    def on_snapshot_toggle(self):
        self.settings.set("save_snapshots", bool(self.snap_var.get()))
        self.settings.save()

    def on_video_click(self, event):
        """نقرة على الفيديو: معايرة لون اليد أو تحديد خط العبور."""
        if self.worker is None:
            return
        proc = self.worker.processor
        if self.mode == M_GESTURE:
            proc.skin.calibrate(self._current_frame(), event.x, event.y)
            self.set_status(self.t("settings.reset_hand_color"))
        elif self.mode == M_DRAW:
            proc.pen.calibrate(self._current_frame(), event.x, event.y)
            self.set_status(self.t("draw.title"))
        elif self.mode == M_COUNTER:
            self._counter_click(event)

    def _counter_click(self, event):
        frame = self._current_frame()
        if frame is None:
            return
        h, w = frame.shape[:2]
        point = (event.x / float(w), event.y / float(h))
        if not hasattr(self, "_line_points"):
            self._line_points = []
        self._line_points.append(point)
        if len(self._line_points) >= 2:
            if self.counter is not None:
                self.counter.set_line(self._line_points[0], self._line_points[1])
                try:
                    self.settings.set("counter.line", self.counter.get_line())
                    self.settings.save()
                except Exception:
                    pass
            self._line_points = []
            self.set_status(self.t("counter.line_saved"))

    def _current_frame(self):
        if self.worker is None:
            return None
        try:
            return self.worker.peek_frame()
        except Exception:
            return None

    def reset_hand_color(self):
        if self.worker is not None:
            self.worker.processor.skin.reset()
        self.set_status(self.t("settings.reset_hand_color"))

    # ============================================================ الأكواد
    def add_code(self, text, kind):
        now = time.time()
        if text == self.last_code and now - self.last_code_time < 3.0:
            self.last_code_time = now
            return
        self.last_code, self.last_code_time = text, now
        stamp = time.strftime("%H:%M:%S")
        self.txt.insert(tk.END, "[%s] (%s)\n%s\n\n" % (stamp, kind, text))
        self.txt.see(tk.END)
        try:
            from .qr_engine import CodeEngine
            if CodeEngine.is_url(text):
                self.last_urls.append(text)
        except Exception:
            pass
        self._log_csv(kind, text)
        self._record_stat("qr")

    def _log_csv(self, kind, text):
        try:
            from .utils import append_csv
            safe = text.replace("\r", " ").replace("\n", " ")
            append_csv(CSV_PATH, ["timestamp", "type", "text"],
                        [time.strftime("%Y-%m-%d %H:%M:%S"), kind, safe])
        except Exception:
            pass

    def open_log(self):
        try:
            if os.path.isfile(CSV_PATH):
                open_with_default_app(CSV_PATH)
            else:
                self.set_status(self.t("qr.no_codes"))
        except Exception as e:
            self.set_status(str(e))

    def copy_text(self):
        try:
            if self.txt.tag_ranges(tk.SEL):
                data = self.txt.get(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                data = self.last_code or ""
            if not data:
                self.set_status(self.t("app.nothing_to_copy"))
                return
            self.clipboard_clear()
            self.clipboard_append(data)
            self.update()
            self.set_status(self.t("app.copied"))
        except Exception as e:
            self.set_status(str(e))

    def open_last_link(self):
        try:
            import webbrowser
            url = self.last_urls[-1] if self.last_urls else self.last_code
            if url and str(url).lower().startswith(("http://", "https://")):
                webbrowser.open(url)
                self.set_status(url)
            else:
                self.set_status(self.t("qr.no_codes"))
        except Exception as e:
            self.set_status(str(e))

    def scan_image_file(self):
        try:
            path = filedialog.askopenfilename(
                title=self.t("qr.scan_image"),
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                           ("All files", "*.*")])
            if not path:
                return
            from .qr_engine import CodeEngine
            engine = CodeEngine()
            codes = engine.scan_file(path)
            if not codes:
                self.set_status(self.t("qr.no_codes"))
                return
            for c in codes:
                self.add_code(c["text"], c.get("kind", "CODE"))
            self.set_status(self.t("qr.decoded"))
        except Exception as e:
            self.set_status(str(e))

    # ============================================================ الماسح
    def scan_document(self):
        frame = None
        if self.worker is not None:
            frame = self.worker.get_raw() or self.worker.peek_frame()
        if frame is None:
            self.set_status(self.t("app.camera_off"))
            return
        result = self.scanner.scan(frame)
        if not result.get("ok"):
            self.set_status(self.t("scanner.no_page"))
            return
        self.scanner.add_page(result["image"])
        panel = self.panels.get("tabs.scanner")
        if panel is not None:
            panel.show(result["image"])
        self.set_status(self.t("scanner.pages") % len(self.scanner.pages))
        self._record_stat("scan")

    def save_scan_pdf(self):
        path = self.scanner.save_pdf()
        if path:
            self.set_status(self.t("scanner.pdf_ok") % os.path.basename(path))
        else:
            self.set_status(self.t("scanner.no_page"))

    # ============================================================ بوث الصور
    def capture_photo(self, filter_name="none", frame_on=True, blur=True):
        if self.worker is None:
            self.set_status(self.t("app.camera_off"))
            return
        self.run_countdown(int(self.settings.get("photobooth.countdown", 3)),
                           lambda: self._do_capture(filter_name, frame_on, blur))

    def run_countdown(self, seconds, callback):
        """عدّ تنازلي في خيط ثم تنفيذ الإجراء."""
        panel = self.panels.get("tabs.photobooth")

        def job():
            for i in range(int(seconds), 0, -1):
                self.events.put((self.wid, "countdown", (i,)))
                time.sleep(1.0)
            self.events.put((self.wid, "countdown", (0,)))
            try:
                callback()
            except Exception:
                pass

        if panel is not None:
            try:
                self.notebook.select(self.panels["tabs.photobooth"].master)
            except Exception:
                pass
        t = threading.Thread(target=job, name="countdown", daemon=True)
        t.start()

    def _do_capture(self, filter_name, frame_on, blur):
        if self.worker is None:
            return
        frame = self.worker.get_raw() or self.worker.peek_frame()
        if frame is None:
            return
        faces = []
        try:
            proc = self.worker.processor
            faces = list(proc.last_faces)
        except Exception:
            faces = []
        result = self.photobooth.make(frame, faces=faces, filter_name=filter_name,
                                      frame_on=frame_on, blur=blur)
        if result.get("ok"):
            path = result.get("path") or ""
            if not path:
                # make() لا تكتب على القرص، فنحفظ الصورة هنا
                try:
                    path = self.photobooth.save(result.get("image"))
                except Exception:
                    path = ""
            # مهم: لا نلمس عناصر Tk من هذا الخيط ( Tk غير آمن مع الخيوط )
            # نترك المعاينة والرسالة للمعالج الرئيسي عبر قائمة الأحداث.
            self.events.put((self.wid, "shot", (path or "", result.get("image"))))
            self._record_stat("shot")

    # ============================================================ الرسم
    def save_drawing(self):
        if self.worker is None:
            self.set_status(self.t("app.camera_off"))
            return ""
        path = self.worker.processor.save_drawing()
        if path:
            self.set_status(self.t("draw.saved") % os.path.basename(path))
            self._record_stat("draw")
        else:
            self.set_status(self.t("draw.no_pen"))
        return path

    def clear_drawing(self):
        if self.worker is not None:
            self.worker.processor.clear_drawing()

    # ============================================================ تيليجرام
    def apply_telegram(self):
        token = self.settings.get("telegram.token", "")
        chat = self.settings.get("telegram.chat_id", "")
        if self.telegram is not None:
            try:
                self.telegram.configure(token, chat)
            except Exception:
                pass
        if self.worker is not None:
            try:
                self.worker.processor.set_telegram(token, chat)
            except Exception:
                pass

    def test_telegram(self):
        if self.telegram is None:
            self.set_status(self.t("telegram.test_fail") % "module missing")
            return
        ok, msg = self.telegram.test()
        if ok:
            self.set_status(self.t("telegram.test_ok"))
        else:
            self.set_status(self.t("telegram.test_fail") % msg)

    # ============================================================ القفل التلقائي
    def lock_now(self):
        if self.worker is None:
            self.set_status(self.t("app.camera_off"))
            return
        proc = self.worker.processor
        if proc.autolock is None:
            self.set_status(self.t("app.error"))
            return
        proc.autolock.lock_now()
        self.set_status(self.t("autolock.locked"))

    # ============================================================ تسجيل الوجوه
    def start_enrollment(self, name, status_var):
        if self.worker is None:
            self.set_status(self.t("app.camera_off"))
            if status_var is not None:
                status_var.set(self.t("app.camera_off"))
            return
        if self.face_db is None:
            return
        self.enroll = {"name": name, "samples": [], "until": time.time() + 12,
                       "status": status_var}
        self.set_status(self.t("faceid.enroll"))

    def _collect_enrollment(self):
        """يجمع عيّنات الوجه أثناء التسجيل."""
        if not self.enroll or self.worker is None:
            return
        now = time.time()
        if now - self.enroll_last < 0.35:
            return
        self.enroll_last = now
        proc = self.worker.processor
        frame = self.worker.peek_frame()
        if frame is None:
            return
        # نُجبر كشف الوجوه أثناء التسجيل حتى لو كان النمط الحالي لا يكتشف وجوهاً
        try:
            faces = proc._detect_faces(frame)
        except Exception:
            faces = proc.last_faces
        if faces:
            x, y, w, h = faces[0]
            crop = proc._crop_face(frame, x, y, w, h)
            if crop is not None and len(self.enroll["samples"]) < 30:
                self.enroll["samples"].append(crop)
        if now >= self.enroll["until"]:
            self._finish_enrollment()

    def _finish_enrollment(self):
        if not self.enroll:
            return
        data = self.enroll
        self.enroll = None
        if self.face_db is None:
            return
        ok, msg = self.face_db.enroll(data["name"], data["samples"])
        status = data.get("status")
        if ok:
            text = self.t("faceid.enroll_ok") % (data["name"], len(data["samples"]))
            self.set_status(text)
            if status is not None:
                status.set(text)
            panel = self.panels.get("tabs.faceid")
            if panel is not None:
                panel.reload_people()
        else:
            text = self.t("faceid.enroll_fail")
            self.set_status(text)
            if status is not None:
                status.set(text)

    def delete_face(self, name):
        if self.face_db is None:
            return
        self.face_db.delete(name)
        panel = self.panels.get("tabs.faceid")
        if panel is not None:
            panel.reload_people()

    # ============================================================ التصدير
    def export_attendance(self, kind="csv"):
        if self.attendance is None:
            return
        path = ""
        try:
            if kind == "xlsx":
                path = self.attendance.export_xlsx()
                if not path:
                    self.set_status("openpyxl is not installed")
                    return
            else:
                path = self.attendance.export_csv()
        except Exception as e:
            self.set_status(str(e))
            return
        if path:
            open_with_default_app(path)

    def export_stats(self):
        if self.stats_store is None:
            return
        path = self.stats_store.export_csv()
        if path:
            open_with_default_app(path)

    def reset_settings(self):
        self.settings.reset()
        self.set_status(self.t("app.ready"))
        self.rebuild()

    # ============================================================ الصوت
    def _queue_voice_command(self, key):
        """يستقبل الأمر الصوتي من خيط الاستماع ويحوّله لحدث في الخيط الرئيسي."""
        try:
            self.events.put((self.wid, "voice_command", (key,)))
        except Exception:
            pass

    def run_voice_command(self, key):
        """ينفّذ أمراً صوتياً."""
        try:
            if key == "lock":
                self.lock_now()
            elif key == "photo":
                self.capture_photo()
            elif key == "scan":
                self.scan_document()
            elif key in ("next", "prev"):
                if self.worker is not None:
                    self.worker.processor._key("pagedown" if key == "next" else "pageup")
            elif key == "draw":
                self.set_mode(M_DRAW)
            elif key == "stats":
                try:
                    self.notebook.select(self.panels["tabs.stats"].master)
                except Exception:
                    pass
            elif key == "unlock":
                self.set_status(self.t("autolock.unlock_detected") % "")
            self.set_status(self.t("voice.executed") % key)
        except Exception as e:
            self.set_status(str(e))

    # ============================================================ أدوات
    def set_status(self, text):
        try:
            self.status_var.set(text)
        except Exception:
            pass

    def log(self, text):
        try:
            self.log_txt.insert(tk.END, "[%s] %s\n" % (time.strftime("%H:%M:%S"), text))
            self.log_txt.see(tk.END)
        except Exception:
            pass

    def _record_stat(self, kind, count=1):
        if self.stats_store is None:
            return
        try:
            self.stats_store.record(kind, count)
        except Exception:
            pass

    # ============================================================ الحلقة
    def _tick(self):
        try:
            self._drain_events()
            self._collect_enrollment()
            if self.worker is not None:
                frame = self.worker.get_frame()
                if frame is not None:
                    self._show(frame)
                info = self.worker.processor.info
                if info != self.last_info:
                    self.last_info = info
                    self.info_var.set(info)
            self._refresh_panels()
        except Exception as e:
            self.set_status("UI error: %s" % e)
        self.after(30, self._tick)

    def _refresh_panels(self):
        """تحديث خفيف كل نصف ثانية."""
        now = time.time()
        if getattr(self, "_last_panel_refresh", 0) and now - self._last_panel_refresh < 0.5:
            return
        self._last_panel_refresh = now
        for panel in list(self.panels.values()):
            try:
                panel.refresh()
            except Exception:
                pass

    def _show(self, frame):
        try:
            from .imgtk import to_photo
            photo, _w, _h = to_photo(frame)
            if photo is None:
                return
            self.photo = photo
            self.video.config(image=photo, text="")
        except Exception as e:
            self.set_status(str(e))

    # ------------------------------------------------------- الأحداث
    def _drain_events(self):
        while True:
            try:
                wid, kind, args = self.events.get_nowait()
            except queue.Empty:
                break
            if wid != self.wid:
                continue
            if kind == "started":
                self.set_status(self.t("app.camera_running"))
            elif kind == "code":
                self.add_code(args[0], args[1])
            elif kind == "saved":
                self.set_status(self.t("app.saved_to") % ("captures/%s" % args[0]))
            elif kind == "log":
                self.set_status(args[0])
                self.log(args[0])
            elif kind == "error":
                messagebox.showwarning(self.t("app.error"), args[0])
                self.set_status(args[0].split("\n")[0])
            elif kind == "failsafe":
                self.mode = None
                if self.worker is not None:
                    self.worker.mode = None
                for btn in self.mode_buttons.values():
                    btn.config(bg=self.theme.btn)
                self.set_status(self.t("mode.gesture_help"))
            elif kind == "stopped":
                self._ui_camera_off()
            elif kind == "counter":
                self._handle_counter(args)
            elif kind == "attendance":
                self._handle_attendance(args[0])
            elif kind == "lock":
                self._handle_lock(args[0])
            elif kind == "countdown":
                panel = self.panels.get("tabs.photobooth")
                if panel is not None:
                    panel.set_countdown(args[0])
            elif kind == "shot":
                path = args[0] if args else ""
                image = args[1] if len(args) > 1 else None
                panel = self.panels.get("tabs.photobooth")
                if panel is not None and image is not None:
                    panel.show(image)
                if path:
                    self.set_status(self.t("photobooth.shot_ok") %
                                    os.path.basename(path))
                else:
                    self.set_status(self.t("photobooth.title"))
            elif kind == "draw":
                self.set_status(self.t("draw.saved") % args[0])
            elif kind == "slides":
                key = "slides.next" if args[0] == "next" else "slides.prev"
                self.set_status(self.t("slides.swiped") % self.t(key))
            elif kind == "voice_trigger":
                self._handle_voice_trigger(args[0])
            elif kind == "voice_result":
                ok, info = args[0], args[1]
                if ok:
                    self.set_status(self.t("voice.executed") % info)
                else:
                    self.set_status(self.t("voice.unknown_cmd") % info)
            elif kind == "voice_command":
                self.run_voice_command(args[0])

    def _handle_counter(self, args):
        event, count, counts = args[0], args[1], args[2]
        label = self.t("counter.enter") if event == "in" else self.t("counter.exit")
        text = label % count
        self.set_status(text)
        self.log(text)
        panel = self.panels.get("tabs.counter")
        if panel is not None:
            panel.add_event(text)
        self._record_stat("people_in" if event == "in" else "people_out")
        try:
            if self.telegram is not None and \
                    self.settings.get("telegram.notify_count", True):
                self.telegram.send_text("Counter: %s = %d" % (event, count))
        except Exception:
            pass

    def _handle_attendance(self, event):
        text = self.t("faceid.attendance_ok") % ("%s %s" % (
            event.get("name", ""), event.get("event", "")))
        self.set_status(text)
        self.log(text)
        panel = self.panels.get("tabs.faceid")
        if panel is not None:
            panel.reload_attendance()

    def _handle_lock(self, event):
        etype = event.get("type", "")
        if etype == "locked":
            self.set_status(self.t("autolock.locked"))
            self.log(self.t("autolock.locked"))
        elif etype == "recognized":
            name = event.get("name", "")
            self.set_status(self.t("autolock.unlock_detected") % name)
            self.log(self.t("autolock.unlock_detected") % name)
        elif etype == "countdown":
            self.set_status(self.t("autolock.absent") % int(event.get("seconds", 0)))
        try:
            # نُشعر تيليجرام فقط بالأحداث المهمة (لا بكل ثانية من العد التنازلي)
            if etype in ("locked", "recognized") and self.telegram is not None and \
                    self.settings.get("telegram.notify_system", True):
                msg = event.get("message") or self.t("autolock.locked")
                self.telegram.send_text(str(msg))
        except Exception:
            pass

    def _handle_voice_trigger(self, pose):
        self.set_status(self.t("voice.listening"))
        if self.voice is None:
            self.set_status(self.t("voice.title"))
            return
        if not self.voice.available():
            # بدون speech_recognition نفتح الإدخال الصوتي في ويندوز
            hotkey = self.settings.get("voice.hotkey", "win+h")
            self.voice.hotkey(hotkey)
            self.set_status(self.t("voice.listening"))
            return
        lang = self.settings.get("voice.lang", "ar")

        def done(ok, info):
            self.events.put((self.wid, "voice_result", (ok, info)))

        self.voice.listen_async(timeout=6, lang=lang, on_result=done)

    # ------------------------------------------------------- الإغلاق
    def on_close(self):
        try:
            self.settings.save()
        except Exception:
            pass
        try:
            self.stop_camera()
        finally:
            self.destroy()
