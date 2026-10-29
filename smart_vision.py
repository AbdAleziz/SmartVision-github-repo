# -*- coding: utf-8 -*-
"""
Smart Vision Studio
===================
تطبيق سطح مكتب يجمع 4 أدوات ذكية في شاشة واحدة (Python 3.8 + Windows 7):
  1) كشف الحركة            Motion Detection
  2) كشف الوجوه            Face Detection (Haar Cascade)
  3) التحكم بالماوس باليد  Gesture Control (تتبع اللون + PyAutoGUI)
  4) قارئ QR والباركود     Barcode / QR Reader
  5) النمط الشامل          All-in-One (حركة + وجوه + أكواد)

المتطلبات (متوافقة مع Windows 7 و Python 3.8):
    pip install numpy==1.21.6 opencv-python==4.5.5.64 pyautogui==0.9.53
    pip install pyzbar==0.1.9        <- اختياري (للباركود الخطي؛ بدونه يعمل QR فقط)

ملاحظات:
  - الواجهة تعتمد على Tkinter القياسية (لا تحتاج Pillow ولا CustomTkinter)،
    وهذا يضمن أعلى توافق مع ويندوز 7.
  - تم استبدال MediaPipe بتتبع اللون (YCrCb / HSV) لأنه غير مدعوم على ويندوز 7.
  - الصور الملتقطة تُحفظ في مجلد captures بجانب الملف.
  - كل كود يُقرأ يُسجّل تلقائياً في ملف codes_log.csv (يُفتح في Excel بالعربية).
  - في نمط اليد: إغلاق القبضة = نقرة ماوس يسار (يمكن تعطيلها من مربع Fist click).
  - لتحويل البرنامج إلى EXE شغّل الملف build_exe.bat.
"""

import os
import sys
import csv
import time
import queue
import threading
import datetime
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import cv2

# ---------------------------------------------------------------------------
# استيراد المكتبات الاختيارية (لا يتوقف البرنامج إذا لم تكن مثبتة)
# ---------------------------------------------------------------------------
try:
    import pyautogui
    pyautogui.PAUSE = 0          # بدون تأخير بين الأوامر
    pyautogui.FAILSAFE = True    # تحريك الماوس الحقيقي إلى الزاوية العلوية اليسرى يوقف التحكم
    HAS_PYAUTOGUI = True
except Exception:
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except Exception:
    pyzbar = None
    HAS_PYZBAR = False

# ---------------------------------------------------------------------------
# الثوابت العامة
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):       # عند التشغيل كملف EXE
    BASE_DIR = os.path.dirname(sys.executable)           # مكان الحفظ بجانب البرنامج
    RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)         # مكان الملفات المدمجة
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = BASE_DIR
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")   # مجلد حفظ صور الحركة
CSV_PATH = os.path.join(BASE_DIR, "codes_log.csv") # سجل الأكواد المقروءة
FRAME_W = 640                # عرض الإطار المعروض والمعالج
SAVE_COOLDOWN = 2.0          # أقل فترة (ثواني) بين صورتين محفوظتين
GESTURE_MIN_AREA = 2500      # أصغر مساحة تُعتبر يداً
GESTURE_MARGIN = 0.18        # هامش المنطقة النشطة داخل الإطار
GESTURE_SMOOTH = 4.0         # قيمة أكبر = حركة أنعم وأبطأ
FIST_CLOSE_RATIO = 0.86      # نسبة (المساحة / الغلاف المحدب) فوقها تُعتبر قبضة
FIST_OPEN_RATIO = 0.80       # ونسبة تحتها تُعتبر يداً مفتوحة (فرق الحدّين يمنع الاهتزاز)
FIST_FRAMES = 3              # عدد الإطارات المتتالية لتأكيد القبضة
CLICK_COOLDOWN = 0.7         # أقل فترة (ثواني) بين نقرتين

# ألوان OpenCV بصيغة BGR
GREEN = (0, 220, 0)
RED = (0, 0, 255)
BLUE = (255, 140, 0)
YELLOW = (0, 220, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX

# أسماء الأنماط
M_MOTION = "motion"
M_FACE = "face"
M_GESTURE = "gesture"
M_QR = "qr"
M_ALL = "all"

# ألوان الواجهة
C_BG = "#12141c"          # خلفية النافذة
C_SIDE = "#1a1d28"        # الشريط الجانبي
C_CARD = "#222637"        # البطاقات
C_BTN = "#2a2f45"
C_BTN_H = "#353c5a"
C_BTN_ACTIVE = "#16a34a"
C_START = "#2563eb"
C_START_H = "#3b82f6"
C_STOP = "#dc2626"
C_STOP_H = "#ef4444"
C_ACCENT = "#6d83f2"
C_TEXT = "#eef0f8"
C_MUTED = "#8f98b3"
C_OK = "#22c55e"
C_BORDER = "#2f3550"
FONT_UI = "Segoe UI"


# ===========================================================================
# معالج الرؤية: كل خوارزميات OpenCV هنا (بدون أي كود واجهة)
# ===========================================================================
class VisionProcessor:
    def __init__(self, emit, min_area=1500):
        self.emit = emit                  # دالة لإرسال أحداث إلى الواجهة
        self.min_area = min_area          # حساسية كشف الحركة
        self.current_mode = None
        self.info = ""                    # نص الحالة المعروض أسفل الفيديو
        self.last_save = 0.0
        self.reported = set()             # لمنع تكرار رسائل الخطأ نفسها

        # مصنف الوجوه (يُحمّل عند أول استخدام)
        self.face_cascade = None
        self.cascade_failed = False

        # كاشف QR المدمج في OpenCV
        self.qr_detector = cv2.QRCodeDetector()

        # حالة التحكم بالماوس
        self.calib_request = None         # نقطة نقر المستخدم لمعايرة لون اليد
        self.calib_hsv = None             # مجال HSV المعاير (low, high)
        self.click_enabled = True         # النقر بإغلاق القبضة
        self.last_click = 0.0
        self.screen_size = (1280, 720)
        if HAS_PYAUTOGUI:
            try:
                self.screen_size = tuple(pyautogui.size())
            except Exception:
                pass

        self.reset_state()

    # ----- إعادة ضبط الحالة عند تغيير النمط -----
    def reset_state(self):
        self.prev_gray = None
        self.last_faces = []
        self.face_counter = 0
        self.last_codes = []
        self.qr_counter = 0
        self.smooth_pos = None
        self.fist_closed = False          # هل اليد مغلقة الآن؟
        self.close_count = 0
        self.pos_hist = deque(maxlen=6)   # آخر مواضع المؤشر (لتثبيت موضع النقرة)

    # ----- تسجيل الخطأ مرة واحدة فقط لكل رسالة -----
    def _report_once(self, name, err):
        key = "%s:%s" % (name, err)
        if key not in self.reported:
            self.reported.add(key)
            self.emit("log", "%s error: %s" % (name, err))

    # ----- الدالة الرئيسية: تأخذ إطاراً وتعيد إطاراً مرسوماً عليه -----
    def process(self, frame, mode):
        if mode != self.current_mode:
            self.current_mode = mode
            self.reset_state()
            self.info = ""

        out = frame.copy()
        if mode is None:
            return out

        info = []
        # كل نمط داخل try مستقل حتى لا يؤثر فشل أحدها على الباقي
        if mode in (M_MOTION, M_ALL):
            try:
                moved = self._motion(frame, out)
                info.append("Motion: YES" if moved else "Motion: no")
            except Exception as e:
                self._report_once("motion", e)
        if mode in (M_FACE, M_ALL):
            try:
                n = self._faces(frame, out)
                info.append("Faces: %d" % n)
            except Exception as e:
                self._report_once("face", e)
        if mode in (M_QR, M_ALL):
            try:
                n = self._codes(frame, out)
                info.append("Codes: %d" % n)
            except Exception as e:
                self._report_once("qr", e)
        if mode == M_GESTURE:
            try:
                info.append(self._gesture(frame, out))
            except Exception as e:
                self._report_once("gesture", e)

        self.info = "  |  ".join(info)
        return out

    # -----------------------------------------------------------------------
    # 1) كشف الحركة: مقارنة الإطار الحالي بالسابق
    # -----------------------------------------------------------------------
    def _motion(self, frame, out):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)       # تقليل الضجيج
        if self.prev_gray is None or self.prev_gray.shape != gray.shape:
            self.prev_gray = gray
            return False

        delta = cv2.absdiff(self.prev_gray, gray)        # الفرق بين إطارين متتاليين
        self.prev_gray = gray
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        # [-2] يجعل الكود يعمل مع OpenCV 3 و 4
        contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)[-2]
        moved = False
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(out, (x, y), (x + w, y + h), GREEN, 2)   # إطار أخضر
            moved = True

        if moved:
            cv2.putText(out, "Motion Detected", (10, 30), FONT, 0.9, GREEN, 2)
            self._save_snapshot(out)
        return moved

    # ----- حفظ صورة تلقائياً (مع فاصل زمني لتجنب ملء القرص) -----
    def _save_snapshot(self, img):
        now = time.time()
        if now - self.last_save < SAVE_COOLDOWN:
            return
        self.last_save = now
        try:
            os.makedirs(CAPTURE_DIR, exist_ok=True)
            name = datetime.datetime.now().strftime("motion_%Y%m%d_%H%M%S.jpg")
            path = os.path.join(CAPTURE_DIR, name)
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                buf.tofile(path)       # يعمل حتى لو احتوى المسار على حروف عربية
                self.emit("saved", name)
        except Exception as e:
            self._report_once("save", e)

    # -----------------------------------------------------------------------
    # 2) كشف الوجوه بمصنف Haar Cascade
    # -----------------------------------------------------------------------
    def _load_cascade(self):
        name = "haarcascade_frontalface_default.xml"
        candidates = []
        try:
            candidates.append(os.path.join(cv2.data.haarcascades, name))
        except AttributeError:
            pass
        candidates.append(os.path.join(os.path.dirname(cv2.__file__), "data", name))
        candidates.append(os.path.join(RES_DIR, name))       # نسخة مدمجة/بجانب الملف
        candidates.append(os.path.join(BASE_DIR, name))
        for path in candidates:
            if os.path.isfile(path):
                cascade = cv2.CascadeClassifier(path)
                if not cascade.empty():
                    return cascade
        return None

    def _faces(self, frame, out):
        if self.face_cascade is None:
            if self.cascade_failed:
                return 0
            self.face_cascade = self._load_cascade()
            if self.face_cascade is None:
                self.cascade_failed = True
                self.emit("error", "Face cascade file (haarcascade_frontalface_default.xml) "
                                   "was not found.\nPut it next to this script.")
                return 0

        # الكشف كل إطارين على صورة مصغّرة للحفاظ على السرعة
        self.face_counter += 1
        if self.face_counter % 2 == 1:
            small = cv2.resize(frame, None, fx=0.5, fy=0.5)
            gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            self.last_faces = [(int(x * 2), int(y * 2), int(w * 2), int(h * 2))
                               for (x, y, w, h) in faces]

        for (x, y, w, h) in self.last_faces:
            cv2.rectangle(out, (x, y), (x + w, y + h), RED, 2)     # مربع أحمر
        cv2.putText(out, "Faces: %d" % len(self.last_faces), (10, 60), FONT, 0.8, RED, 2)
        return len(self.last_faces)

    # -----------------------------------------------------------------------
    # 4) قراءة QR والباركود
    # -----------------------------------------------------------------------
    def _codes(self, frame, out):
        self.qr_counter += 1
        if self.qr_counter % 3 == 1:          # فحص كل 3 إطارات لتخفيف الحمل
            found = []
            if HAS_PYZBAR:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    for obj in pyzbar.decode(gray):
                        text = obj.data.decode("utf-8", errors="replace")
                        pts = [(p.x, p.y) for p in obj.polygon]
                        found.append((text, obj.type, pts))
                except Exception as e:
                    self._report_once("pyzbar", e)
            if not found:                      # بديل: كاشف QR المدمج
                try:
                    text, pts, _ = self.qr_detector.detectAndDecode(frame)
                    if text and pts is not None:
                        pts = [(int(p[0]), int(p[1])) for p in pts.reshape(-1, 2)]
                        found.append((text, "QRCODE", pts))
                except Exception as e:
                    self._report_once("qr_detector", e)
            self.last_codes = found
            for text, kind, _ in found:
                self.emit("code", text, kind)

        for text, kind, pts in self.last_codes:
            if len(pts) >= 2:
                arr = np.array(pts, np.int32).reshape(-1, 1, 2)
                cv2.polylines(out, [arr], True, BLUE, 3)
                cv2.putText(out, kind, (pts[0][0], max(15, pts[0][1] - 8)),
                            FONT, 0.6, BLUE, 2)
        if self.last_codes:
            cv2.putText(out, "Code found", (10, 90), FONT, 0.8, BLUE, 2)
        return len(self.last_codes)

    # -----------------------------------------------------------------------
    # 3) التحكم بالماوس عبر تتبع اليد (لون البشرة أو لون معاير بالنقر)
    # -----------------------------------------------------------------------
    def _gesture(self, frame, out):
        h, w = frame.shape[:2]
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)

        # معايرة اللون: المستخدم ينقر على يده في الفيديو
        if self.calib_request is not None:
            x, y = self.calib_request
            self.calib_request = None
            x0, x1 = max(0, x - 6), min(w, x + 7)
            y0, y1 = max(0, y - 6), min(h, y + 7)
            if x1 > x0 and y1 > y0:
                patch = cv2.cvtColor(blurred[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
                med = np.median(patch, axis=0)
                low = np.array([max(0, med[0] - 12), max(30, med[1] - 70),
                                max(30, med[2] - 70)], np.uint8)
                high = np.array([min(179, med[0] + 12), 255, 255], np.uint8)
                self.calib_hsv = (low, high)

        if self.calib_hsv is not None:
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.calib_hsv[0], self.calib_hsv[1])
        else:   # اللون الافتراضي: لون البشرة في فضاء YCrCb
            ycc = cv2.cvtColor(blurred, cv2.COLOR_BGR2YCrCb)
            mask = cv2.inRange(ycc, np.array([0, 133, 77], np.uint8),
                               np.array([255, 173, 127], np.uint8))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.dilate(mask, kernel, iterations=2)

        # المنطقة النشطة (حركة اليد داخلها تغطي كامل الشاشة)
        mx, my = int(w * GESTURE_MARGIN), int(h * GESTURE_MARGIN)
        cv2.rectangle(out, (mx, my), (w - mx, h - my), YELLOW, 1)

        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        if not contours:
            return "Gesture: no hand"
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < GESTURE_MIN_AREA:
            return "Gesture: no hand"

        m = cv2.moments(c)
        if m["m00"] == 0:
            return "Gesture: no hand"
        cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
        cv2.drawContours(out, [c], -1, GREEN, 2)
        cv2.circle(out, (cx, cy), 9, RED, -1)

        # كشف القبضة: نسبة مساحة اليد إلى مساحة غلافها المحدب (Solidity)
        # اليد المفتوحة ~0.65-0.80 والقبضة ~0.88 فأكثر
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = cv2.contourArea(c) / hull_area if hull_area > 0 else 0.0
        clicked = False
        if not self.fist_closed:
            self.close_count = self.close_count + 1 if solidity >= FIST_CLOSE_RATIO else 0
            if self.close_count >= FIST_FRAMES:
                self.fist_closed = True
                self.close_count = 0
                clicked = self._click()
        elif solidity <= FIST_OPEN_RATIO:
            self.fist_closed = False

        if self.fist_closed:               # أثناء القبضة يُثبّت المؤشر ولا يتحرك
            cv2.circle(out, (cx, cy), 16, YELLOW, 3)
            cv2.putText(out, "CLICK" if clicked else "FIST", (10, 30), FONT, 0.9, YELLOW, 2)
            return "Gesture: fist"

        # تحويل موضع اليد إلى موضع الماوس (مع عكس المحور الأفقي)
        sw, sh = self.screen_size
        tx = float(np.interp(cx, [mx, w - mx], [sw - 3, 2]))
        ty = float(np.interp(cy, [my, h - my], [2, sh - 3]))
        if self.smooth_pos is None:
            self.smooth_pos = (tx, ty)
        else:
            sx, sy = self.smooth_pos
            self.smooth_pos = (sx + (tx - sx) / GESTURE_SMOOTH,
                               sy + (ty - sy) / GESTURE_SMOOTH)
        self.pos_hist.append(self.smooth_pos)
        self._mouse(pyautogui.moveTo, int(self.smooth_pos[0]), int(self.smooth_pos[1]))
        return "Gesture: tracking"

    # ----- استدعاء آمن لأوامر الماوس (مع معالجة زاوية الأمان) -----
    def _mouse(self, func, *args):
        try:
            func(*args, _pause=False)
            return True
        except Exception as e:
            if HAS_PYAUTOGUI and isinstance(e, pyautogui.FailSafeException):
                self.emit("failsafe")          # المستخدم أوقف التحكم بالزاوية
            else:
                self._report_once("mouse", e)
            return False

    # ----- نقرة عند إغلاق القبضة (في الموضع قبل إغلاق اليد بقليل) -----
    def _click(self):
        now = time.time()
        if (not self.click_enabled or not self.pos_hist
                or now - self.last_click < CLICK_COOLDOWN):
            return False
        self.last_click = now
        x, y = self.pos_hist[0]               # أقدم موضع محفوظ = قبل تحرك اليد بسبب الإغلاق
        self.smooth_pos = (x, y)
        return self._mouse(pyautogui.click, int(x), int(y))


# ===========================================================================
# خيط الكاميرا: يقرأ ويعالج الإطارات في الخلفية فلا تتجمد الواجهة
# ===========================================================================
class CameraWorker(threading.Thread):
    def __init__(self, index, events, wid, mode, min_area):
        super().__init__(daemon=True)
        self.index = index
        self.events = events
        self.wid = wid
        self.mode = mode
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.processor = VisionProcessor(self.emit, min_area)

    def emit(self, kind, *args):
        self.events.put((self.wid, kind, args))

    def stop(self):
        self.stop_event.set()

    def get_frame(self):
        """يعيد آخر إطار جاهز مرة واحدة فقط (أو None)."""
        with self.lock:
            frame, self.latest = self.latest, None
        return frame

    # ----- فتح الكاميرا (DirectShow أولاً لأنه الأسرع على ويندوز) -----
    def _open(self):
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(self.index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    return cap
                cap.release()
            except Exception:
                continue
        return None

    @staticmethod
    def _fit(frame):
        h, w = frame.shape[:2]
        if w != FRAME_W:
            frame = cv2.resize(frame, (FRAME_W, max(1, int(h * FRAME_W / float(w)))))
        return frame

    def run(self):
        cap = None
        try:
            cap = self._open()
            if cap is None:
                self.emit("error", "Cannot open camera %d.\nCheck the USB cable, the camera "
                                   "index, or whether another program is using it." % self.index)
                return
            self.emit("started")
            fails = 0
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:          # فقدان الاتصال بالكاميرا
                    fails += 1
                    if fails >= 30:
                        self.emit("error", "Camera connection lost.")
                        break
                    time.sleep(0.03)
                    continue
                fails = 0
                frame = self._fit(frame)
                try:
                    out = self.processor.process(frame, self.mode)
                except Exception as e:
                    self.processor._report_once("process", e)
                    out = frame
                with self.lock:
                    self.latest = out
        except Exception as e:
            self.emit("error", "Camera error: %s" % e)
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            self.emit("stopped")


# ===========================================================================
# الواجهة الرسومية
# ===========================================================================
class App(tk.Tk):
    MODES = [
        (M_MOTION, "1  Motion Detection"),
        (M_FACE, "2  Face Detection"),
        (M_GESTURE, "3  Gesture Mouse Control"),
        (M_QR, "4  QR / Barcode Reader"),
        (M_ALL, "5  All-in-One Mode"),
    ]

    def __init__(self):
        super().__init__()
        self.title("Smart Vision Studio")
        self.configure(bg=C_BG)
        self.minsize(960, 760)
        w, h = 1020, 800
        x = max((self.winfo_screenwidth() - w) // 2, 0)
        y = max((self.winfo_screenheight() - h) // 2 - 20, 0)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

        self.events = queue.Queue()     # قناة الاتصال بين خيط الكاميرا والواجهة
        self.worker = None
        self.wid = 0                    # رقم الخيط الحالي (لتجاهل أحداث الخيوط القديمة)
        self.mode = None
        self.photo = None
        self.last_code = None
        self.last_code_time = 0.0
        self.last_info = ""

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()

    # ----- أدوات مساعدة للشكل -----
    _HOVER = {C_BTN: C_BTN_H, C_START: C_START_H, C_STOP: C_STOP_H}
    _UNHOVER = {v: k for k, v in _HOVER.items()}

    def _hoverable(self, btn):
        """تأثير مرور الماوس (يحترم لون الزر الحالي: نشط / تشغيل / إيقاف)."""
        def enter(_e):
            c = str(btn.cget("bg"))
            if c in self._HOVER:
                btn.config(bg=self._HOVER[c])

        def leave(_e):
            c = str(btn.cget("bg"))
            if c in self._UNHOVER:
                btn.config(bg=self._UNHOVER[c])

        btn.bind("<Enter>", enter)
        btn.bind("<Leave>", leave)
        btn.config(cursor="hand2", bd=0, highlightthickness=0)
        return btn

    def _section(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=C_SIDE, fg=C_MUTED,
                 font=(FONT_UI, 8, "bold")).pack(anchor="w", padx=18, pady=(16, 4))

    # ----- بناء الواجهة -----
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=C_BTN, background=C_BTN,
                        foreground=C_TEXT, arrowcolor=C_TEXT, bordercolor=C_BORDER,
                        lightcolor=C_BTN, darkcolor=C_BTN, selectbackground=C_BTN,
                        selectforeground=C_TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", C_BTN)],
                  foreground=[("readonly", C_TEXT)])
        style.configure("Vertical.TScrollbar", background=C_BTN, troughcolor=C_BG,
                        bordercolor=C_BG, arrowcolor=C_MUTED, lightcolor=C_BTN,
                        darkcolor=C_BTN)
        self.option_add("*TCombobox*Listbox.background", C_BTN)
        self.option_add("*TCombobox*Listbox.foreground", C_TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", C_ACCENT)

        # ---------------- الشريط الجانبي ----------------
        side = tk.Frame(self, bg=C_SIDE, width=270)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        head = tk.Frame(side, bg=C_SIDE)
        head.pack(fill=tk.X, padx=18, pady=(20, 4))
        tk.Label(head, text="\u25C9", bg=C_SIDE, fg=C_ACCENT,
                 font=(FONT_UI, 22)).pack(side=tk.LEFT)
        titles = tk.Frame(head, bg=C_SIDE)
        titles.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(titles, text="Smart Vision", bg=C_SIDE, fg=C_TEXT,
                 font=(FONT_UI, 16, "bold")).pack(anchor="w")
        tk.Label(titles, text="Studio", bg=C_SIDE, fg=C_MUTED,
                 font=(FONT_UI, 9)).pack(anchor="w")
        tk.Frame(side, bg=C_BORDER, height=1).pack(fill=tk.X, padx=18, pady=(14, 0))

        # الكاميرا
        self._section(side, "Camera")
        row = tk.Frame(side, bg=C_SIDE)
        row.pack(fill=tk.X, padx=18)
        tk.Label(row, text="Device index", bg=C_SIDE, fg=C_TEXT,
                 font=(FONT_UI, 9)).pack(side=tk.LEFT)
        self.cam_var = tk.StringVar(value="0")
        self.cam_box = ttk.Combobox(row, textvariable=self.cam_var, state="readonly",
                                    values=["0", "1", "2", "3"], width=4)
        self.cam_box.pack(side=tk.RIGHT)
        self.cam_box.bind("<<ComboboxSelected>>", self.on_camera_index_changed)

        self.btn_cam = tk.Button(side, text="\u25B6  Start Camera", bg=C_START, fg="white",
                                 activebackground=C_START_H, activeforeground="white",
                                 relief=tk.FLAT, font=(FONT_UI, 10, "bold"),
                                 command=self.toggle_camera)
        self.btn_cam.pack(fill=tk.X, padx=18, pady=(10, 0), ipady=7)
        self._hoverable(self.btn_cam)

        # الأنماط
        self._section(side, "Modes")
        self.mode_buttons = {}
        for key, label in self.MODES:
            b = tk.Button(side, text=label, bg=C_BTN, fg=C_TEXT, anchor="w",
                          activebackground=C_BTN_ACTIVE, activeforeground="white",
                          relief=tk.FLAT, font=(FONT_UI, 10), padx=14,
                          command=lambda k=key: self.set_mode(k))
            b.pack(fill=tk.X, padx=18, pady=3, ipady=6)
            self._hoverable(b)
            self.mode_buttons[key] = b

        # الإعدادات
        self._section(side, "Settings")
        tk.Label(side, text="Motion sensitivity (higher = less sensitive)", bg=C_SIDE,
                 fg=C_MUTED, wraplength=225, justify="left", font=(FONT_UI, 8)
                 ).pack(anchor="w", padx=18)
        self.area_var = tk.IntVar(value=1500)
        tk.Scale(side, from_=300, to=8000, orient=tk.HORIZONTAL, variable=self.area_var,
                 bg=C_SIDE, fg=C_TEXT, highlightthickness=0, troughcolor=C_BTN,
                 activebackground=C_ACCENT, bd=0, sliderrelief=tk.FLAT,
                 command=self.on_area_changed).pack(fill=tk.X, padx=18)

        self.click_var = tk.BooleanVar(value=True)
        tk.Checkbutton(side, text="Fist click (close hand = click)", variable=self.click_var,
                       bg=C_SIDE, fg=C_TEXT, selectcolor=C_BTN, activebackground=C_SIDE,
                       activeforeground=C_TEXT, font=(FONT_UI, 9), bd=0, highlightthickness=0,
                       command=self.on_click_toggle).pack(anchor="w", padx=14, pady=(8, 0))

        b = tk.Button(side, text="Reset hand color", bg=C_BTN, fg=C_TEXT, relief=tk.FLAT,
                      activebackground=C_BTN_H, activeforeground=C_TEXT,
                      font=(FONT_UI, 9), command=self.reset_hand_color)
        b.pack(fill=tk.X, padx=18, pady=(10, 0), ipady=4)
        self._hoverable(b)

        tk.Label(side, text="pyzbar: %s   |   PyAutoGUI: %s" % (
            "ON" if HAS_PYZBAR else "OFF (QR only)", "ON" if HAS_PYAUTOGUI else "OFF"),
            bg=C_SIDE, fg=C_MUTED, font=(FONT_UI, 8), wraplength=235, justify="left"
        ).pack(side=tk.BOTTOM, anchor="w", padx=18, pady=12)

        # ---------------- المنطقة الرئيسية ----------------
        main = tk.Frame(self, bg=C_BG)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=16)

        top = tk.Frame(main, bg=C_BG)
        top.pack(fill=tk.X)
        tk.Label(top, text="Live View", bg=C_BG, fg=C_TEXT,
                 font=(FONT_UI, 14, "bold")).pack(side=tk.LEFT)
        self.chip = tk.Label(top, text="\u25CF  OFFLINE", bg=C_CARD, fg=C_MUTED,
                             font=(FONT_UI, 8, "bold"), padx=10, pady=3)
        self.chip.pack(side=tk.RIGHT)

        video_box = tk.Frame(main, bg="black", width=FRAME_W, height=480,
                             highlightbackground=C_BORDER, highlightthickness=2)
        video_box.pack(pady=(10, 0))
        video_box.pack_propagate(False)
        self.video = tk.Label(video_box, text="Camera is off\nPress  Start Camera  or pick a mode",
                              bg="black", fg=C_MUTED, font=(FONT_UI, 12), justify="center")
        self.video.place(relx=0.5, rely=0.5, anchor="center")
        self.video.bind("<Button-1>", self.on_video_click)     # معايرة لون اليد

        # بطاقة الحالة
        card = tk.Frame(main, bg=C_CARD)
        card.pack(fill=tk.X, pady=(10, 0))
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(card, textvariable=self.status_var, bg=C_CARD, fg=C_TEXT, anchor="w",
                 font=(FONT_UI, 10, "bold"), wraplength=640, justify="left"
                 ).pack(fill=tk.X, padx=12, pady=(8, 0))
        self.info_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.info_var, bg=C_CARD, fg=C_ACCENT, anchor="w",
                 font=(FONT_UI, 9)).pack(fill=tk.X, padx=12, pady=(0, 8))

        # مربع نص الأكواد
        tk.Label(main, text="Decoded QR / Barcode text", bg=C_BG, fg=C_MUTED, anchor="w",
                 font=(FONT_UI, 9, "bold")).pack(fill=tk.X, pady=(12, 4))
        text_frame = tk.Frame(main, bg=C_CARD)
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.txt = tk.Text(text_frame, height=6, bg=C_CARD, fg=C_TEXT, bd=0,
                           insertbackground=C_TEXT, relief=tk.FLAT, wrap="word",
                           font=("Consolas", 10), padx=10, pady=8,
                           selectbackground=C_ACCENT, highlightthickness=0)
        scroll = ttk.Scrollbar(text_frame, command=self.txt.yview)
        self.txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btns = tk.Frame(main, bg=C_BG)
        btns.pack(fill=tk.X, pady=(8, 0))
        for text, bg, fg, cmd, w in (
                ("Copy", C_START, "white", self.copy_text, 12),
                ("Clear", C_BTN, C_TEXT, lambda: self.txt.delete("1.0", tk.END), 12),
                ("Open CSV Log", C_BTN, C_TEXT, self.open_log, 14)):
            bt = tk.Button(btns, text=text, bg=bg, fg=fg, relief=tk.FLAT, width=w,
                           activebackground=bg, activeforeground=fg,
                           font=(FONT_UI, 9, "bold"), command=cmd)
            bt.pack(side=tk.LEFT, padx=(0, 6), ipady=4)
            self._hoverable(bt)

    # ----- التحكم بالكاميرا -----
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
        self.worker = CameraWorker(index, self.events, self.wid, self.mode, self.area_var.get())
        self.worker.processor.click_enabled = self.click_var.get()
        self.worker.start()
        self.btn_cam.config(text="\u25A0  Stop Camera", bg=C_STOP, activebackground=C_STOP_H)
        self.chip.config(text="\u25CF  LIVE", fg=C_OK)
        self.status_var.set("Opening camera %d ..." % index)

    def stop_camera(self):
        old = self.worker
        self.worker = None
        self.wid += 1                      # تجاهل أي أحداث متأخرة من الخيط القديم
        if old is not None:
            old.stop()
            old.join(timeout=2.0)          # انتظار قصير لتحرير الكاميرا
        self._ui_camera_off()

    def _ui_camera_off(self):
        self.worker = None
        self.btn_cam.config(text="\u25B6  Start Camera", bg=C_START, activebackground=C_START_H)
        self.chip.config(text="\u25CF  OFFLINE", fg=C_MUTED)
        self.video.config(image="", text="Camera is off\nPress  Start Camera  or pick a mode")
        self.photo = None
        self.info_var.set("")

    def on_camera_index_changed(self, _event=None):
        if self.worker is not None:        # إعادة التشغيل على الكاميرا الجديدة
            self.stop_camera()
            self.start_camera()

    # ----- الأنماط -----
    def set_mode(self, mode):
        if mode == M_GESTURE and not HAS_PYAUTOGUI:
            messagebox.showwarning("PyAutoGUI missing",
                                   "Install it first:\n\npip install pyautogui==0.9.53")
            return
        self.mode = None if self.mode == mode else mode      # الضغط مرة أخرى يلغي النمط
        if self.worker is not None:
            self.worker.mode = self.mode
        for key, btn in self.mode_buttons.items():
            btn.config(bg=C_BTN_ACTIVE if key == self.mode else C_BTN)

        if self.mode == M_GESTURE:
            self.status_var.set("Gesture: click your hand in the video to calibrate color. "
                                "Move the real mouse to the top-left corner to stop.")
        elif self.mode == M_QR and not HAS_PYZBAR:
            self.status_var.set("QR only (install pyzbar for 1D barcodes).")
        elif self.mode is None:
            self.status_var.set("Mode off.")
        else:
            self.status_var.set("Mode active.")
        if self.worker is None and self.mode is not None:     # تشغيل الكاميرا تلقائياً
            self.start_camera()

    def on_area_changed(self, value):
        if self.worker is not None:
            self.worker.processor.min_area = int(float(value))

    def on_click_toggle(self):
        if self.worker is not None:
            self.worker.processor.click_enabled = self.click_var.get()

    def on_video_click(self, event):
        if self.worker is not None and self.mode == M_GESTURE:
            self.worker.processor.calib_request = (event.x, event.y)
            self.status_var.set("Hand color calibrated.")

    def reset_hand_color(self):
        if self.worker is not None:
            self.worker.processor.calib_hsv = None
            self.status_var.set("Hand color reset to default skin tone.")

    # ----- نص الأكواد -----
    def add_code(self, text, kind):
        now = time.time()
        if text == self.last_code and now - self.last_code_time < 3.0:
            self.last_code_time = now      # نفس الكود ما زال أمام الكاميرا: لا تكرار
            return
        self.last_code, self.last_code_time = text, now
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt.insert(tk.END, "[%s] (%s)\n%s\n\n" % (stamp, kind, text))
        self.txt.see(tk.END)
        self._log_csv(kind, text)

    # ----- تسجيل الكود في ملف CSV (يُنشأ تلقائياً مع صف العناوين) -----
    def _log_csv(self, kind, text):
        try:
            safe = text.replace("\r", " ").replace("\n", " ")
            if safe[:1] in ("=", "+", "-", "@"):
                safe = "'" + safe            # منع تنفيذ المعادلات عند فتح الملف في Excel
            is_new = not os.path.isfile(CSV_PATH)
            with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(["timestamp", "type", "text"])
                writer.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 kind, safe])
        except PermissionError:
            self.status_var.set("CSV is open in another program - close it to keep logging.")
        except Exception as e:
            self.status_var.set("CSV log failed: %s" % e)

    def open_log(self):
        try:
            if os.path.isfile(CSV_PATH):
                os.startfile(CSV_PATH)       # ويندوز فقط
            else:
                self.status_var.set("No log yet - scan a code first.")
        except Exception as e:
            self.status_var.set("Cannot open log: %s" % e)

    def copy_text(self):
        try:
            if self.txt.tag_ranges(tk.SEL):                    # النص المحدد أولاً
                data = self.txt.get(tk.SEL_FIRST, tk.SEL_LAST)
            else:                                              # وإلا آخر كود مقروء
                data = self.last_code or ""
            if not data:
                self.status_var.set("Nothing to copy.")
                return
            self.clipboard_clear()
            self.clipboard_append(data)
            self.update()
            self.status_var.set("Copied to clipboard.")
        except Exception as e:
            self.status_var.set("Copy failed: %s" % e)

    # ----- حلقة التحديث (كل ~30ms) -----
    def _tick(self):
        try:
            self._drain_events()
            if self.worker is not None:
                frame = self.worker.get_frame()
                if frame is not None:
                    self._show(frame)
                info = self.worker.processor.info
                if info != self.last_info:
                    self.last_info = info
                    self.info_var.set(info)
        except Exception as e:
            self.status_var.set("UI error: %s" % e)
        self.after(30, self._tick)

    def _show(self, frame):
        # عرض الإطار بصيغة PPM مباشرة (بدون Pillow)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        header = b"P6\n%d %d\n255\n" % (w, h)
        self.photo = tk.PhotoImage(data=header + rgb.tobytes(), format="PPM")
        self.video.config(image=self.photo, text="")

    def _drain_events(self):
        while True:
            try:
                wid, kind, args = self.events.get_nowait()
            except queue.Empty:
                break
            if wid != self.wid:
                continue                    # حدث من خيط قديم
            if kind == "started":
                self.status_var.set("Camera running.")
            elif kind == "code":
                self.add_code(args[0], args[1])
            elif kind == "saved":
                self.status_var.set("Snapshot saved: captures/%s" % args[0])
            elif kind == "log":
                self.status_var.set(args[0])
            elif kind == "error":
                messagebox.showwarning("Smart Vision", args[0])
                self.status_var.set(args[0].split("\n")[0])
            elif kind == "failsafe":
                self.mode = None
                if self.worker is not None:
                    self.worker.mode = None
                for btn in self.mode_buttons.values():
                    btn.config(bg=C_BTN)
                self.status_var.set("Gesture control stopped (fail-safe corner).")
            elif kind == "stopped":
                self._ui_camera_off()

    def on_close(self):
        try:
            self.stop_camera()
        finally:
            self.destroy()


# ===========================================================================
# نقطة التشغيل
# ===========================================================================
if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception as exc:       # آخر شبكة أمان حتى لا يُغلق البرنامج بصمت
        try:
            messagebox.showerror("Smart Vision", "Fatal error:\n%s" % exc)
        except Exception:
            print("Fatal error:", exc)
