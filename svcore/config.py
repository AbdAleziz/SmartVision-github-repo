# -*- coding: utf-8 -*-
"""
إعدادات Smart Vision + مسارات المجلدات.

كل الإعدادات تُحفظ في settings.json بجانب البرنامج حتى تبقى بعد الإغلاق.
المسارات كلها داخل مجلد التطبيق (أو بجانب ملف EXE) حتى يعمل البرنامج من
أي مكان بدون صلاحيات مدير (Administrator).
"""

import copy
import json
import os
import sys


# ---------------------------------------------------------------------------
# المسارات
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):        # يعمل كملف EXE
    BASE_DIR = os.path.dirname(sys.executable)
    RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RES_DIR = BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "data")
CAPTURE_DIR = os.path.join(DATA_DIR, "captures")
FACES_DIR = os.path.join(DATA_DIR, "faces")
MODELS_DIR = os.path.join(DATA_DIR, "models")
PHOTOBOOTH_DIR = os.path.join(DATA_DIR, "photobooth")
SCAN_DIR = os.path.join(DATA_DIR, "scans")
DRAW_DIR = os.path.join(DATA_DIR, "drawings")
STATS_DIR = os.path.join(DATA_DIR, "stats")
LOG_DIR = os.path.join(DATA_DIR, "logs")

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
CSV_PATH = os.path.join(LOG_DIR, "codes_log.csv")

ALL_DIRS = (DATA_DIR, CAPTURE_DIR, FACES_DIR, MODELS_DIR, PHOTOBOOTH_DIR,
            SCAN_DIR, DRAW_DIR, STATS_DIR, LOG_DIR)


def ensure_dirs():
    """ينشئ كل مجلدات البيانات إن لم تكن موجودة."""
    for d in ALL_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# القيم الافتراضية
# ---------------------------------------------------------------------------
DEFAULTS = {
    # عام
    "language": "ar",                 # ar | en
    "theme": "dark",                  # dark | light
    "camera_index": 0,
    "motion_min_area": 1500,
    "fist_click": True,
    "save_snapshots": True,
    "snapshot_cooldown": 2.0,

    # تيليجرام
    "telegram": {
        "enabled": False,
        "token": "",
        "chat_id": "",
        "notify_motion": True,
        "notify_unknown_face": True,
        "notify_attendance": True,
        "notify_count": True,
        "notify_system": True,
    },

    # القفل التلقائي
    "autolock": {
        "enabled": False,
        "idle_seconds": 15,           # ثواني بلا وجه قبل القفل
        "recognize_only": True,       # فقط الوجوه المسجّلة تفتح
        "auto_type_password": False,  # محاولة كتابة كلمة المرور تلقائياً
        "password": "",
        "notify": True,
    },

    # عدّاد الأشخاص
    "counter": {
        "line": [0.5, 0.0, 0.5, 1.0],  # خط العبور بالإحداثيات النسبية
        "min_area": 900,
        "cooldown": 2.0,
    },

    # التعرف على الوجوه
    "faceid": {
        "threshold": 72,               # مسافة LBPH (أقل = أدق تشابه، أكبر = تساهل)
        "auto_enroll": False,
        "enroll_samples": 15,
    },

    # بوث الصور
    "photobooth": {
        "filter": "none",              # none|bw|sepia|cool|warm|vignette|blur
        "frame": True,
        "blur_faces": True,
        "countdown": 3,
    },

    # الرسم بالهوا
    "draw": {
        "mode": "auto",                # auto | color
        "color": [0, 0, 255],          # BGR
        "width": 6,
    },

    # التحكم بالشرائح
    "slides": {
        "cooldown": 1.2,
        "threshold": 0.16,             # نسبةmovement على عرض الإطار
    },

    # التحكم الصوتي بإشارة اليد
    "voice": {
        "enabled": True,
        "trigger": "palm",             # palm | fist | point
        "hotkey": "win+h",             # يفتح الإدخال الصوتي في ويندوز
        "lang": "ar",
    },
}


class Settings(object):
    """حقيبة إعدادات بسيطة مع حفظ/تحميل من JSON."""

    def __init__(self, path=None):
        self.path = path or SETTINGS_PATH
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    # ---- تحميل ----
    def load(self):
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._merge(self.data, loaded)
        except Exception:
            pass   # ملف تالف = نبدأ بالقيم الافتراضية
        return self.data

    # ---- دمج متداخل (لا نمسح فروع القيم الافتراضية غير المذكورة) ----
    @staticmethod
    def _merge(base, new):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                Settings._merge(base[k], v)
            else:
                base[k] = v

    # ---- حفظ ----
    def save(self):
        ensure_dirs()
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except Exception:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False

    # ---- الوصول بمسار نصي: "telegram.token" ----
    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur

    def set(self, dotted, value):
        parts = dotted.split(".")
        cur = self.data
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value
        return value

    def reset(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.save()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)
