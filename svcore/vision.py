# -*- coding: utf-8 -*-
"""
محرّك الرؤية: يجمع كل الخوارزميات في مكان واحد ويجهّز الإطار المعروض.

كل نمط يعمل داخل try مستقل حتى لا يُسقط فشلُ نمطٍ النمطَ الباقي.
المعالج لا يعرف شيئاً عن الواجهة: يتواصل معها عبر دالة emit(kind, *args).
"""

import os
import time

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

try:
    import pyautogui
    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except Exception:
    pyautogui = None
    HAS_PYAUTOGUI = False

from .counter import PeopleCounter
from .faceid import AttendanceTracker, FaceDatabase
from .hand import ColorPenTracker, SkinTracker, hand_pose
from .qr_engine import CodeEngine

# أسماء الأنماط
M_MOTION = "motion"
M_FACE = "face"
M_GESTURE = "gesture"
M_QR = "qr"
M_COUNTER = "counter"
M_FACEID = "faceid"
M_DRAW = "draw"
M_SLIDES = "slides"
M_VOICE = "voice"
M_ALL = "all"

# ألوان OpenCV (BGR)
GREEN = (0, 220, 0)
RED = (0, 0, 255)
BLUE = (255, 140, 0)
YELLOW = (0, 220, 255)
CYAN = (255, 255, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX if cv2 is not None else None

# الإعدادات العامة
FRAME_W = 640
SAVE_COOLDOWN = 2.0
GESTURE_MIN_AREA = 2500
GESTURE_MARGIN = 0.18
GESTURE_SMOOTH = 4.0
CLICK_COOLDOWN = 0.7


class VisionProcessor(object):
    """يحلّل الإطارات ويطبّق النمط المطلوب."""

    def __init__(self, emit, settings=None, min_area=1500):
        self.emit = emit                # دالة إرسال الأحداث إلى الواجهة
        self.settings = settings
        self.min_area = min_area
        self.current_mode = None
        self.info = ""
        self.last_save = 0.0
        self.reported = set()

        # ---- Cascades ----
        self.face_cascade = None
        self.cascade_failed = False
        self.body_cascade = None

        # ---- محرّكات ----
        self.code_engine = CodeEngine()
        self.skin = SkinTracker()
        self.pen = ColorPenTracker()
        self.counter = PeopleCounter(settings)
        self.faces_db = FaceDatabase()
        self.attendance = AttendanceTracker()
        self.autolock = None
        self._tg_last = {}                # آخر وقت إشعار لكل نوع (منع التكرار)
        try:
            from .autolock import AutoLockManager
            self.autolock = AutoLockManager(settings)
        except Exception:
            self.autolock = None
        self.screen_size = (1280, 720)
        if HAS_PYAUTOGUI:
            try:
                self.screen_size = tuple(pyautogui.size())
            except Exception:
                pass

        # ---- حالة داخلية ----
        self.reset_state()

    # ------------------------------------------------------------- الحالة
    def reset_state(self):
        self.prev_gray = None
        self.last_faces = []
        self.face_counter = 0
        self.last_codes = []
        self.qr_counter = 0
        self.smooth_pos = None
        self.fist_closed = False
        self.close_count = 0
        self.pos_hist = []
        self.canvas = None               # لوحة الرسم بالهوا
        self.draw_last = None
        self.draw_points = []
        self.slide_anchor = None
        self.slide_last = 0.0
        self.voice_pose = None
        self.voice_since = 0.0
        self.voice_fired = False
        self.visible_names = set()
        self.enroll_samples = []
        self.enroll_until = 0.0
        self.enroll_target = ""

    def _report_once(self, name, err):
        key = "%s:%s" % (name, err)
        if key not in self.reported:
            self.reported.add(key)
            self.emit("log", "%s error: %s" % (name, err))

    # ================================================================ الحلقة
    def process(self, frame, mode):
        if mode != self.current_mode:
            self.current_mode = mode
            self.reset_state()
            self.info = ""

        out = frame.copy()
        if frame is None:
            return out

        info = []

        # ---- القفل التلقائي يعمل في كل الأحوال (حضور أم لا) ----
        try:
            self._watch_presence(frame, out)
        except Exception as e:
            self._report_once("autolock", e)

        if mode is None:
            self.info = "  |  ".join(info)
            return out

        if mode in (M_MOTION, M_ALL):
            try:
                moved = self._motion(frame, out)
                info.append("Motion: %s" % ("YES" if moved else "no"))
            except Exception as e:
                self._report_once("motion", e)

        if mode in (M_FACE, M_ALL):
            try:
                n = self._faces(frame, out)
                info.append("Faces: %d" % n)
            except Exception as e:
                self._report_once("face", e)

        if mode == M_FACEID:
            try:
                info.append(self._faceid(frame, out))
            except Exception as e:
                self._report_once("faceid", e)

        if mode in (M_QR, M_ALL):
            try:
                n = self._codes(frame, out)
                info.append("Codes: %d" % n)
            except Exception as e:
                self._report_once("qr", e)

        if mode == M_COUNTER:
            try:
                info.append(self._counter(frame, out))
            except Exception as e:
                self._report_once("counter", e)

        if mode == M_GESTURE:
            try:
                info.append(self._gesture(frame, out))
            except Exception as e:
                self._report_once("gesture", e)

        if mode == M_DRAW:
            try:
                info.append(self._draw(frame, out))
            except Exception as e:
                self._report_once("draw", e)

        if mode == M_SLIDES:
            try:
                info.append(self._slides(frame, out))
            except Exception as e:
                self._report_once("slides", e)

        if mode == M_VOICE:
            try:
                info.append(self._voice(frame, out))
            except Exception as e:
                self._report_once("voice", e)

        self.info = "  |  ".join(info)
        return out

    # ================================================================= الحركة
    def _motion(self, frame, out):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.prev_gray is None or self.prev_gray.shape != gray.shape:
            self.prev_gray = gray
            return False

        delta = cv2.absdiff(self.prev_gray, gray)
        self.prev_gray = gray
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)[-2]
        moved = False
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(out, (x, y), (x + w, y + h), GREEN, 2)
            moved = True

        if moved:
            cv2.putText(out, "Motion Detected", (10, 30), FONT, 0.9, GREEN, 2)
            self._save_snapshot(out)
            self._notify_motion(out)
            self.record_stat("motion")
        return moved

    def _save_snapshot(self, img):
        if self.settings is not None:
            try:
                if not self.settings.get("save_snapshots", True):
                    return
            except Exception:
                pass
        now = time.time()
        if now - self.last_save < SAVE_COOLDOWN:
            return
        self.last_save = now
        try:
            from .config import CAPTURE_DIR
            os.makedirs(CAPTURE_DIR, exist_ok=True)
            name = time.strftime("motion_%Y%m%d_%H%M%S.jpg")
            path = os.path.join(CAPTURE_DIR, name)
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                buf.tofile(path)
                self.emit("saved", name)
        except Exception as e:
            self._report_once("save", e)

    # ================================================================== الوجوه
    def _load_cascade(self, names):
        if cv2 is None:
            return None
        try:
            folders = []
            folders.append(os.path.join(cv2.data.haarcascades, ""))
            folders.append(os.path.join(os.path.dirname(cv2.__file__), "data"))
            from .config import RES_DIR, BASE_DIR
            folders.append(RES_DIR)
            folders.append(BASE_DIR)
        except Exception:
            folders = []
        for name in names:
            for folder in folders:
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    try:
                        cascade = cv2.CascadeClassifier(path)
                        if not cascade.empty():
                            return cascade
                    except Exception:
                        continue
        return None

    def _detect_faces(self, frame):
        """يعيد قائمة مربعات الوجوه (كل إطارين لتوفير المعالج)."""
        if self.face_cascade is None:
            if self.cascade_failed:
                return self.last_faces
            self.face_cascade = self._load_cascade([
                "haarcascade_frontalface_default.xml",
                "haarcascade_frontalface_alt2.xml",
                "haarcascade_frontalface_alt_tree.xml",
            ])
            if self.face_cascade is None:
                self.cascade_failed = True
                self.emit("error", "Face cascade file (haarcascade_frontalface_default.xml) "
                                   "was not found.\nPut it next to this script.")
                return self.last_faces

        self.face_counter += 1
        if self.face_counter % 2 == 1:
            small = cv2.resize(frame, None, fx=0.5, fy=0.5)
            gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            try:
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 5,
                                                           minSize=(30, 30))
            except Exception:
                faces = []
            self.last_faces = [(int(x * 2), int(y * 2), int(w * 2), int(h * 2))
                               for (x, y, w, h) in faces]
        return self.last_faces

    def _faces(self, frame, out):
        faces = self._detect_faces(frame)
        for (x, y, w, h) in faces:
            cv2.rectangle(out, (x, y), (x + w, y + h), RED, 2)
        cv2.putText(out, "Faces: %d" % len(faces), (10, 60), FONT, 0.8, RED, 2)
        return len(faces)

    def _faceid(self, frame, out):
        """يتعرّف على الوجوه ويعرض الأسماء ويسجّل الحضور."""
        faces = self._detect_faces(frame)
        names = []
        for (x, y, w, h) in faces:
            crop = self._crop_face(frame, x, y, w, h)
            name, dist = self.faces_db.identify(crop)
            if name:
                names.append(name)
                self._draw_name(out, name, x, y, w, h, dist)
            else:
                cv2.rectangle(out, (x, y), (x + w, y + h), YELLOW, 2)
                cv2.putText(out, "Unknown", (x, max(15, y - 6)), FONT, 0.55, YELLOW, 2)
                self._notify_unknown_face(out)

        # تسجيل الحضور
        events = self.attendance.update(names)
        for ev in events:
            self.emit("attendance", ev)
            self._notify_attendance(ev)
        self.visible_names = set(names)
        return "Faces: %d  |  Known: %d" % (len(faces), len(names))

    def _crop_face(self, frame, x, y, w, h):
        """قص الوجه مع هامش بسيط (يساعد على ثبات التعرّف)."""
        try:
            hh, ww = frame.shape[:2]
            mx, my = int(w * 0.15), int(h * 0.15)
            x0 = max(0, x - mx)
            y0 = max(0, y - my)
            x1 = min(ww, x + w + mx)
            y1 = min(hh, y + h + my)
            crop = frame[y0:y1, x0:x1]
            return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        except Exception:
            return None

    def _draw_name(self, out, name, x, y, w, h, dist):
        cv2.rectangle(out, (x, y), (x + w, y + h), GREEN, 2)
        try:
            from .textdraw import draw_label
            draw_label(out, name, x, max(16, y - 6), color=GREEN, scale=0.55,
                       bg=(0, 0, 0))
        except Exception:
            cv2.putText(out, name, (x, max(15, y - 6)), FONT, 0.55, GREEN, 2)

    # ================================================================== الأكواد
    def _codes(self, frame, out):
        codes = self.code_engine.scan(frame)
        self.last_codes = codes
        for c in codes:
            if c.get("is_new"):
                self.emit("code", c["text"], c.get("kind", "CODE"))
        self.code_engine.draw(out, codes)
        if codes:
            cv2.putText(out, "Codes: %d" % len(codes), (10, 90), FONT, 0.8, BLUE, 2)
        return len(codes)

    # ================================================================== العدّاد
    def _detect_people(self, frame):
        """مربعات الأشخاص: cascades للجسم إن وُجدت، وإلا الوجوه."""
        if self.body_cascade is None:
            self.body_cascade = self._load_cascade([
                "haarcascade_fullbody.xml",
                "haarcascade_upperbody.xml",
            ])
        boxes = []
        if self.body_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                found = self.body_cascade.detectMultiScale(gray, 1.1, 5,
                                                           minSize=(40, 80))
                boxes = [(int(a), int(b), int(c), int(d)) for (a, b, c, d) in found]
            except Exception:
                boxes = []
        if not boxes:
            boxes = list(self._detect_faces(frame))
        return boxes

    def _counter(self, frame, out):
        h, w = frame.shape[:2]
        boxes = self._detect_people(frame)
        events = self.counter.update(boxes, (w, h))
        for ev in events:
            self.emit("counter", ev["event"], ev["count"], self.counter.counts)
        self.counter.draw(out, (w, h))
        counts = self.counter.counts
        cv2.putText(out, "IN: %d   OUT: %d" % (counts["in"], counts["out"]),
                    (10, 30), FONT, 0.8, YELLOW, 2)
        return "People: %d" % len(boxes)

    # ================================================================== اليد
    def _gesture(self, frame, out):
        result = self.skin.detect(frame)
        h, w = frame.shape[:2]

        mx, my = int(w * GESTURE_MARGIN), int(h * GESTURE_MARGIN)
        cv2.rectangle(out, (mx, my), (w - mx, h - my), YELLOW, 1)

        if not result["found"]:
            return "Gesture: no hand"

        cx, cy = result["cx"], result["cy"]
        cv2.circle(out, (cx, cy), 9, RED, -1)

        pose = hand_pose(result)
        solidity = result["solidity"]
        if not self.fist_closed:
            self.close_count = self.close_count + 1 if solidity >= 0.86 else 0
            if self.close_count >= 3:
                self.fist_closed = True
                self.close_count = 0
                self._click()
        elif solidity <= 0.80:
            self.fist_closed = False

        if self.fist_closed:
            cv2.circle(out, (cx, cy), 16, YELLOW, 3)
            cv2.putText(out, "CLICK", (10, 30), FONT, 0.9, YELLOW, 2)
            return "Gesture: fist"

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
        if len(self.pos_hist) > 6:
            self.pos_hist.pop(0)
        self._mouse(pyautogui.moveTo, int(self.smooth_pos[0]), int(self.smooth_pos[1]))
        return "Gesture: tracking"

    def _mouse(self, func, *args):
        try:
            func(*args, _pause=False)
            return True
        except Exception as e:
            if HAS_PYAUTOGUI and isinstance(e, pyautogui.FailSafeException):
                self.emit("failsafe")
            else:
                self._report_once("mouse", e)
            return False

    def _click(self):
        now = time.time()
        enabled = True
        if self.settings is not None:
            try:
                enabled = self.settings.get("fist_click", True)
            except Exception:
                enabled = True
        if (not enabled or not self.pos_hist or now - getattr(self, "last_click", 0) < CLICK_COOLDOWN):
            return False
        self.last_click = now
        x, y = self.pos_hist[0]
        self.smooth_pos = (x, y)
        return self._mouse(pyautogui.click, int(x), int(y))

    # ================================================================== الرسم
    def _draw(self, frame, out):
        h, w = frame.shape[:2]
        if self.canvas is None or self.canvas.shape[:2] != (h, w):
            self.canvas = np.zeros((h, w, 3), np.uint8)
            self.draw_last = None

        result = self.pen.detect(frame)
        if result["found"]:
            pt = (result["cx"], result["cy"])
            if self.draw_last is not None:
                color = (0, 255, 255)
                width = 6
                if self.settings is not None:
                    try:
                        width = int(self.settings.get("draw.width", 6))
                    except Exception:
                        pass
                cv2.line(self.canvas, self.draw_last, pt, color, width)
            self.draw_last = pt
            self.draw_points.append(pt)
            if len(self.draw_points) > 2000:
                self.draw_points.pop(0)
            cv2.circle(out, pt, 10, (0, 255, 255), -1)
            cv2.putText(out, "Drawing", (10, 30), FONT, 0.8, (0, 255, 255), 2)
        else:
            self.draw_last = None

        # دمج اللوحة فوق الفيديو
        try:
            out = cv2.add(out, self.canvas)
        except Exception:
            pass
        return "Draw: %s" % ("pen found" if result["found"] else "no pen")

    def clear_drawing(self):
        if self.canvas is not None:
            self.canvas[:] = 0
        self.draw_last = None
        self.draw_points = []

    def save_drawing(self):
        if self.canvas is None:
            return ""
        try:
            from .config import DRAW_DIR
            os.makedirs(DRAW_DIR, exist_ok=True)
            name = time.strftime("drawing_%Y%m%d_%H%M%S.png")
            path = os.path.join(DRAW_DIR, name)
            ok, buf = cv2.imencode(".png", self.canvas)
            if ok:
                buf.tofile(path)
                self.emit("draw", name)
                return path
        except Exception as e:
            self._report_once("draw_save", e)
        return ""

    # ================================================================= الشرائح
    def _slides(self, frame, out):
        h, w = frame.shape[:2]
        result = self.skin.detect(frame)
        if not result["found"]:
            self.slide_anchor = None
            return "Slides: no hand"

        cx = result["cx"]
        if self.slide_anchor is None:
            self.slide_anchor = cx
            return "Slides: ready"

        threshold = 0.16
        cooldown = 1.2
        if self.settings is not None:
            try:
                threshold = float(self.settings.get("slides.threshold", threshold))
                cooldown = float(self.settings.get("slides.cooldown", cooldown))
            except Exception:
                pass

        delta = cx - self.slide_anchor
        moved = ""
        now = time.time()
        if abs(delta) > w * threshold and now - self.slide_last > cooldown:
            if delta > 0:
                self._key("pagedown")
                moved = "next"
            else:
                self._key("pageup")
                moved = "prev"
            self.slide_last = now
            self.slide_anchor = cx
            self.emit("slides", moved)
        cv2.circle(out, (cx, result["cy"]), 12, CYAN, 2)
        cv2.putText(out, "Slides: %d" % cx, (10, 30), FONT, 0.7, CYAN, 2)
        return "Slides: %s" % (moved or "tracking")

    def _key(self, key):
        if not HAS_PYAUTOGUI:
            return False
        try:
            pyautogui.press(key, _pause=False)
            return True
        except Exception as e:
            self._report_once("keys", e)
            return False

    # ================================================================== الصوت
    def _voice(self, frame, out):
        """إشارة اليد (راحة/قبضة) تُطلق الإدخال الصوتي."""
        result = self.skin.detect(frame)
        if not result["found"]:
            self.voice_pose = None
            self.voice_fired = False
            return "Voice: waiting for hand"

        pose = hand_pose(result)
        trigger = "palm"
        if self.settings is not None:
            try:
                trigger = self.settings.get("voice.trigger", "palm")
            except Exception:
                trigger = "palm"

        now = time.time()
        matched = (pose == trigger)
        if matched:
            if self.voice_pose != pose:
                self.voice_pose = pose
                self.voice_since = now
                self.voice_fired = False
            if not self.voice_fired and now - self.voice_since >= 1.0:
                self.voice_fired = True
                self.emit("voice_trigger", pose)
        else:
            self.voice_pose = None
            self.voice_fired = False

        cv2.putText(out, "Voice: %s" % pose, (10, 30), FONT, 0.7, (0, 255, 255), 2)
        return "Voice: %s" % pose

    # ============================================================ حضور/قفل
    def _watch_presence(self, frame, out):
        """ي-feed معلومات الوجوه لمدير القفل التلقائي."""
        if self.autolock is None:
            return
        try:
            if self.settings is not None and not self.settings.get("autolock.enabled", False):
                return
        except Exception:
            return
        # كشف الوجوه كل 3 إطارات فقط: الحضور لا يحتاج دقة كل إطار
        self.presence_counter = getattr(self, "presence_counter", 0) + 1
        if self.presence_counter % 3 != 1:
            return
        faces = self._detect_faces(frame)
        names = []
        for (x, y, w, h) in faces:
            crop = self._crop_face(frame, x, y, w, h)
            name, _ = self.faces_db.identify(crop)
            if name:
                names.append(name)
        event = self.autolock.update(bool(faces), names)
        if event:
            self.emit("lock", event)

    # ============================================================== تيليجرام
    def _telegram(self):
        try:
            from .telegram import TelegramBot
        except Exception:
            return None
        if not hasattr(self, "_tg"):
            self._tg = TelegramBot()
            if self.settings is not None:
                try:
                    self._tg.configure(self.settings.get("telegram.token", ""),
                                       self.settings.get("telegram.chat_id", ""))
                except Exception:
                    pass
        return self._tg

    def set_telegram(self, token, chat_id):
        """يحدّث إعدادات بوت تيليجرام أثناء التشغيل."""
        try:
            from .telegram import TelegramBot
            if getattr(self, "_tg", None) is None:
                self._tg = TelegramBot()
            self._tg.configure(token, chat_id)
        except Exception as e:
            self._report_once("telegram", e)

    def _tg_enabled(self, key):
        try:
            if self.settings is None:
                return False
            return bool(self.settings.get("telegram.enabled", False)) and \
                bool(self.settings.get(key, True))
        except Exception:
            return False

    def _tg_allow(self, key, seconds):
        """يسمح بإشعار واحد كل فترة لكل نوع (منع إغراق تيليجرام)."""
        now = time.time()
        last = self._tg_last.get(key, 0.0)
        if now - last < seconds:
            return False
        self._tg_last[key] = now
        return True

    def _notify_motion(self, img):
        if not self._tg_enabled("telegram.notify_motion"):
            return
        if not self._tg_allow("motion", 20):
            return
        bot = self._telegram()
        if bot is None:
            return
        try:
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                bot.send_photo_bytes(buf.tobytes(), "Motion detected")
        except Exception as e:
            self._report_once("telegram", e)

    def _notify_unknown_face(self, img):
        if not self._tg_enabled("telegram.notify_unknown_face"):
            return
        if not self._tg_allow("unknown_face", 30):
            return
        bot = self._telegram()
        if bot is None:
            return
        try:
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                bot.send_photo_bytes(buf.tobytes(), "Unknown face detected")
        except Exception as e:
            self._report_once("telegram", e)

    def _notify_attendance(self, event):
        if not self._tg_enabled("telegram.notify_attendance"):
            return
        bot = self._telegram()
        if bot is None:
            return
        try:
            bot.send_text("Attendance: %s %s" % (event.get("name", ""),
                                                  event.get("event", "")))
        except Exception as e:
            self._report_once("telegram", e)

    # ============================================================== الإحصائيات
    def record_stat(self, kind, count=1):
        try:
            from .stats import StatsStore
            if not hasattr(self, "_stats"):
                self._stats = StatsStore()
            self._stats.record(kind, count)
        except Exception as e:
            self._report_once("stats", e)
