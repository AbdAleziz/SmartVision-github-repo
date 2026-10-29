# -*- coding: utf-8 -*-
"""
التعرف على الوجوه (Face ID) + سجل الحضور.

يعتمد على opencv-contrib (LBPHFaceRecognizer). إن لم تكن المكتبة متوفرة
يعمل البرنامج بوضع بديل: وصف إحصائي للوجه (32x32 مطبّع) ومقارنة تشابه
تجميعية — أضعف من LBPH لكنه يمنع أن تتعطّل الميزة كلياً.
"""

import json
import os
import re
import shutil

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

from .config import FACES_DIR, MODELS_DIR, ensure_dirs
from .utils import append_csv, ensure_dir, safe_filename, stamp

try:
    cv2.face
    HAS_CVFACE = True
except Exception:
    HAS_CVFACE = False


def _slug(name):
    """اسم مجلد آمن للوجه مع الحفاظ على الحروف العربية."""
    s = safe_filename(name, "face")
    s = re.sub(r"\s+", "_", s)
    return s or "face"


class FaceDatabase(object):
    """قاعدة بيانات الوجوه: صور + نموذج تعرّف."""

    def __init__(self, faces_dir=None, models_dir=None):
        self.faces_dir = faces_dir or FACES_DIR
        self.models_dir = models_dir or MODELS_DIR
        self.model_path = os.path.join(self.models_dir, "faces.yml")
        self.labels_path = os.path.join(self.models_dir, "labels.json")
        self.recognizer = None
        self.labels = {}                 # int -> name
        self.descriptors = {}            # name -> [descriptor, ...]  (للوضع البديل)
        self.threshold = 72
        self._load()

    # ------------------------------------------------------------ housekeeping
    def _load(self):
        ensure_dir(self.faces_dir)
        ensure_dir(self.models_dir)
        self.labels = {}
        self.descriptors = {}
        try:
            if os.path.isfile(self.labels_path):
                with open(self.labels_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    self.labels[int(k)] = v
        except Exception:
            pass
        self._load_descriptors()
        if HAS_CVFACE:
            try:
                rec = self._new_recognizer()
                if rec is not None and os.path.isfile(self.model_path):
                    rec.read(self.model_path)
                    self.recognizer = rec
            except Exception:
                self.recognizer = None

    @staticmethod
    def _new_recognizer():
        try:
            return cv2.face.LBPHFaceRecognizer_create()
        except Exception:
            try:
                return cv2.face.LBPHFaceRecognizer()
            except Exception:
                return None

    def names(self):
        """أسماء كل الوجوه المسجّلة."""
        result = []
        try:
            for entry in sorted(os.listdir(self.faces_dir)):
                full = os.path.join(self.faces_dir, entry)
                if os.path.isdir(full):
                    name = entry.replace("_", " ")
                    if name not in result:
                        result.append(name)
        except Exception:
            pass
        return result

    def face_dir(self, name):
        return os.path.join(self.faces_dir, _slug(name))

    def sample_count(self, name):
        try:
            return len([f for f in os.listdir(self.face_dir(name))
                        if f.lower().endswith((".png", ".jpg"))])
        except Exception:
            return 0

    # --------------------------------------------------------------- الوصف
    @staticmethod
    def describe(face_gray):
        """وصف ثابت الطول للوجه (للوضع البديل)."""
        if cv2 is None or face_gray is None:
            return None
        try:
            small = cv2.resize(face_gray, (32, 32), interpolation=cv2.INTER_AREA)
            eq = cv2.equalizeHist(small)
            vec = eq.astype(np.float32).reshape(-1)
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception:
            return None

    def _load_descriptors(self):
        """يعيد بناء أوصاف البديل من الصور المحفوظة."""
        self.descriptors = {}
        if cv2 is None:
            return
        for name in self.names():
            vec = []
            folder = self.face_dir(name)
            try:
                files = [f for f in sorted(os.listdir(folder))
                         if f.lower().endswith((".png", ".jpg"))]
            except Exception:
                files = []
            for fn in files:
                try:
                    img = cv2.imread(os.path.join(folder, fn), cv2.IMREAD_GRAYSCALE)
                    if img is None:
                        continue
                    d = self.describe(img)
                    if d is not None:
                        vec.append(d)
                except Exception:
                    pass
            if vec:
                self.descriptors[name] = vec

    # ------------------------------------------------------------- التسجيل
    def enroll(self, name, samples):
        """يحفظ عينات الوجه ويعيد (ok, message)."""
        name = (name or "").strip()
        if not name:
            return False, "empty name"
        if cv2 is None:
            return False, "opencv missing"
        samples = [s for s in (samples or []) if s is not None]
        if len(samples) < 3:
            return False, "not enough samples"

        folder = self.face_dir(name)
        ensure_dir(folder)
        saved = 0
        for i, sample in enumerate(samples):
            try:
                img = sample
                if img.ndim == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA)
                img = cv2.equalizeHist(img)
                path = os.path.join(folder, "sample_%03d.png" % i)
                ok, buf = cv2.imencode(".png", img)
                if ok:
                    buf.tofile(path)        # يعمل مع المسارات العربية
                    saved += 1
            except Exception:
                continue
        if saved < 3:
            return False, "not enough samples"
        self.train()
        return True, "%d samples" % saved

    def train(self):
        """يعيد بناء النموذج من كل الصور المحفوظة."""
        if cv2 is None:
            return False, "opencv missing"
        ensure_dirs()
        images = []
        ids = []
        labels = {}
        self._load_descriptors()
        names = self.names()
        for idx, name in enumerate(names):
            folder = self.face_dir(name)
            try:
                files = [f for f in sorted(os.listdir(folder))
                         if f.lower().endswith((".png", ".jpg"))]
            except Exception:
                files = []
            for fn in files:
                try:
                    img = cv2.imread(os.path.join(folder, fn), cv2.IMREAD_GRAYSCALE)
                    if img is None:
                        continue
                    img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA)
                    images.append(img)
                    ids.append(idx)
                except Exception:
                    continue
            labels[idx] = name
        if not images:
            return False, "no samples"

        # حفظ الوصف البديل دائماً (حتى لو تعذّر LBPH)
        self.descriptors = {}
        for name in names:
            vec = []
            folder = self.face_dir(name)
            try:
                files = [f for f in sorted(os.listdir(folder))
                         if f.lower().endswith((".png", ".jpg"))]
            except Exception:
                files = []
            for fn in files:
                try:
                    img = cv2.imread(os.path.join(folder, fn), cv2.IMREAD_GRAYSCALE)
                    d = self.describe(img) if img is not None else None
                    if d is not None:
                        vec.append(d)
                except Exception:
                    pass
            if vec:
                self.descriptors[name] = vec

        # حفظ خريطة الأسماء
        try:
            with open(self.labels_path, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in labels.items()}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.labels = labels

        # نموذج LBPH (إن توفّرت opencv-contrib)
        if HAS_CVFACE:
            try:
                rec = self._new_recognizer()
                if rec is not None:
                    rec.train(images, np.array(ids))
                    rec.save(self.model_path)
                    self.recognizer = rec
                    return True, "LBPH trained on %d samples" % len(images)
            except Exception as e:
                return True, "fallback descriptors: %s" % e
        return True, "fallback descriptors on %d samples" % len(images)

    # ---------------------------------------------------------- التعرّف
    def identify(self, face_gray):
        """يعيد (name, distance). الاسم فارغ إذا لم يُعرف."""
        if cv2 is None or face_gray is None:
            return "", 999.0
        try:
            img = face_gray
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA)
        except Exception:
            return "", 999.0

        # 1) LBPH
        if self.recognizer is not None:
            try:
                label, distance = self.recognizer.predict(img)
                name = self.labels.get(int(label), "")
                # مهم: لا نعتبر الوجه معروفاً إلا إذا كانت المسافة ضمن الحد
                if name and float(distance) <= self.threshold:
                    return name, float(distance)
            except Exception:
                pass

        # 2) الوصف البديل
        desc = self.describe(img)
        if desc is None or not self.descriptors:
            return "", 999.0
        best_name = ""
        best_score = -1.0
        for name, vecs in self.descriptors.items():
            for v in vecs:
                try:
                    score = float(np.dot(desc, v))
                except Exception:
                    score = 0.0
                if score > best_score:
                    best_score = score
                    best_name = name
        distance = 100.0 * (1.0 - max(0.0, best_score))
        if distance <= self.threshold:
            return best_name, distance
        return "", distance

    # -------------------------------------------------------------- الحذف
    def delete(self, name):
        folder = self.face_dir(name)
        try:
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass
        self.train()
        return True

    def delete_all(self):
        try:
            shutil.rmtree(self.faces_dir, ignore_errors=True)
        except Exception:
            pass
        ensure_dir(self.faces_dir)
        self.train()
        return True


# ---------------------------------------------------------------------------
# سجل الحضور
# ---------------------------------------------------------------------------
class AttendanceTracker(object):
    """يسجّل دخول/خروج كل شخص معروف ويكتب ملف CSV يفتحه Excel مباشرة."""

    def __init__(self, gap_seconds=45.0, log_dir=None):
        self.gap_seconds = gap_seconds
        self.log_dir = log_dir or os.path.join(os.path.dirname(FACES_DIR), "attendance")
        self.state = {}                 # name -> {"first","last","present"}
        self.rows = []                  # صفوف اليوم
        self.day = None
        ensure_dir(self.log_dir)

    # ------------------------------------------------------------- الملفات
    def _day_str(self, when=None):
        import datetime
        d = when or datetime.datetime.now()
        return d.strftime("%Y-%m-%d")

    @staticmethod
    def _to_datetime(when=None):
        """يقبل datetime أو طابعاً زمنياً (float) أو None."""
        import datetime
        if when is None:
            return datetime.datetime.now()
        if isinstance(when, datetime.datetime):
            return when
        if isinstance(when, datetime.date):
            return datetime.datetime.combine(when, datetime.time())
        try:
            return datetime.datetime.fromtimestamp(float(when))
        except Exception:
            return datetime.datetime.now()

    def csv_path(self, day=None):
        return os.path.join(self.log_dir, "attendance_%s.csv" % (day or self._day_str()))

    def _load_day(self, day):
        """يحمّل صفوف اليوم من الملف (ليتابع الترقيم بعد إعادة التشغيل)."""
        if self.day == day:
            return
        self.day = day
        self.rows = []
        path = self.csv_path(day)
        try:
            if os.path.isfile(path):
                import csv as _csv
                with open(path, "r", newline="", encoding="utf-8-sig") as f:
                    for i, row in enumerate(_csv.reader(f)):
                        if i == 0 and row and row[0].lower() in ("date", "التاريخ"):
                            continue
                        if len(row) >= 4:
                            self.rows.append(row)
        except Exception:
            pass

    # -------------------------------------------------------------- التحديث
    def update(self, visible_names, now=None):
        """يستقبل أسماء الموجودين حالياً ويعيد قائمة أحداث (دخول/خروج)."""
        import datetime
        now = self._to_datetime(now)
        ts = now.timestamp()
        day = self._day_str(now)
        self._load_day(day)
        visible = set(visible_names or [])
        events = []

        # دخول
        for name in visible:
            st = self.state.get(name)
            if st is None or not st.get("present"):
                st = {"first": ts, "last": ts, "present": True}
                self.state[name] = st
                events.append(self._record(name, "in", ts, 0, now))
            else:
                st["last"] = ts

        # خروج (اختفى فترة أطول من الحد)
        for name, st in list(self.state.items()):
            if st.get("present") and name not in visible:
                if ts - st.get("last", ts) >= self.gap_seconds:
                    duration = ts - st.get("first", ts)
                    st["present"] = False
                    events.append(self._record(name, "out", ts, duration, now))
        return events

    def _record(self, name, event, ts, duration, now):
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        minutes = int(round(duration / 60.0)) if duration else 0
        row = [date_str, time_str, name, event, minutes]
        self.rows.append(row)
        append_csv(self.csv_path(self.day),
                   ["date", "time", "name", "event", "duration_min"], row)
        return {"event": event, "name": name, "time": time_str,
                "duration_min": minutes, "duration_sec": int(duration)}

    # --------------------------------------------------------------- التصدير
    def rows_today(self):
        """صفوف اليوم المحميل حالياً (يُحمَّل تلقائياً عند أول استدعاء)."""
        if self.day is None:
            self._load_day(self._day_str())
        return list(self.rows)

    def export_csv(self, path=None):
        path = path or self.csv_path()
        try:
            import csv as _csv
            ensure_dir(os.path.dirname(path))
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = _csv.writer(f)
                w.writerow(["date", "time", "name", "event", "duration_min"])
                for row in self.rows:
                    w.writerow(row)
            return path
        except Exception:
            return ""

    def export_xlsx(self, path=None):
        """ملف Excel حقيقي إن توفّرت مكتبة openpyxl، وإلا يعيد نصاً فارغاً."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except Exception:
            return ""
        path = path or os.path.join(self.log_dir,
                                    "attendance_%s.xlsx" % self._day_str())
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Attendance"
            head = ["date", "time", "name", "event", "duration_min"]
            ws.append(head)
            for c in range(1, len(head) + 1):
                ws.cell(row=1, column=c).font = Font(bold=True)
            for row in self.rows:
                ws.append(row)
            for col, width in zip("ABCDE", (12, 10, 24, 8, 14)):
                ws.column_dimensions[col].width = width
            wb.save(path)
            return path
        except Exception:
            return ""
