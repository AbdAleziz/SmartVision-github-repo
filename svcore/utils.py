# -*- coding: utf-8 -*-
"""أدوات مشتركة صغيرة: مجلدات، CSV، فتح الملفات، خيوط خلفية."""

import csv
import datetime
import os
import re
import threading
import time


# ---------------------------------------------------------------------------
# الملفات والمجلدات
# ---------------------------------------------------------------------------
def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def safe_filename(text, fallback="file"):
    """اسم ملف آمن يحافظ على الحروف العربية (Windows يسمح بها)."""
    text = str(text or "").strip()
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    return text[:80]


def stamp(fmt="%Y%m%d_%H%M%S"):
    return datetime.datetime.now().strftime(fmt)


def human_time(seconds):
    """ثواني -> نص مقروء (1h 05m)."""
    try:
        seconds = int(max(0, seconds))
    except Exception:
        return "0s"
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)


def open_with_default_app(path):
    """يفتح ملف/مجلد بالبرنامج الافتراضي في النظام."""
    try:
        if not os.path.exists(path):
            return False
        if os.name == "nt":
            os.startfile(path)          # noqa: S606  (وظيفة ويندوز)
        else:
            import subprocess
            opener = "open" if sys_platform_is_mac() else "xdg-open"
            subprocess.Popen([opener, path])
        return True
    except Exception:
        return False


def sys_platform_is_mac():
    import sys
    return sys.platform.startswith("darwin")


# ---------------------------------------------------------------------------
# CSV (متوافق مع Excel العربية)
# ---------------------------------------------------------------------------
def append_csv(path, header, row):
    """يضيف صفاً إلى ملف CSV. يضيف صف عناوين تلقائياً، ويمنع تنفيذ المعادلات."""
    try:
        ensure_dir(os.path.dirname(path))
        is_new = not os.path.isfile(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(header)
            clean = []
            for cell in row:
                s = "" if cell is None else str(cell)
                s = s.replace("\r", " ").replace("\n", " ")
                if s[:1] in ("=", "+", "-", "@"):
                    s = "'" + s
                clean.append(s)
            writer.writerow(clean)
        return True
    except Exception:
        return False


def read_csv(path):
    """يقرأ CSV كقائمة صفوف (بدون صف العناوين)."""
    rows = []
    try:
        if not os.path.isfile(path):
            return rows
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            for i, row in enumerate(csv.reader(f)):
                if i == 0 and row and row[0].lower() in (
                        "timestamp", "date", "الوقت", "التاريخ"):
                    continue
                rows.append(row)
    except Exception:
        pass
    return rows


# ---------------------------------------------------------------------------
# خيوط خلفية
# ---------------------------------------------------------------------------
class BackgroundJob(object):
    """يشغّل دالة في خيط منفصل حتى لا تتجمد الواجهة.

        job = BackgroundJob(func, args=(), on_done=None)
        job.start()
    """

    def __init__(self, func, args=(), on_done=None, on_error=None, name="job"):
        self.func = func
        self.args = tuple(args)
        self.on_done = on_done
        self.on_error = on_error
        self.name = name
        self.result = None
        self.error = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        try:
            self.result = self.func(*self.args)
            if self.on_done:
                try:
                    self.on_done(self.result)
                except Exception:
                    pass
        except Exception as e:
            self.error = e
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception:
                    pass

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()


class RateLimiter(object):
    """يسمح بحدث واحد كل فترة محددة (بالثواني)."""

    def __init__(self, seconds):
        self.seconds = float(seconds)
        self.last = 0.0

    def allow(self):
        now = time.time()
        if now - self.last >= self.seconds:
            self.last = now
            return True
        return False

    def reset(self):
        self.last = 0.0


def clamp(value, low, high):
    try:
        v = float(value)
    except Exception:
        return low
    return max(low, min(high, v))


def lerp(a, b, t):
    return a + (b - a) * t


def distance(p1, p2):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def iou(box_a, box_b):
    """تقاطع على اتحاد بين مربعين (x, y, w, h)."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / float(union) if union > 0 else 0.0
