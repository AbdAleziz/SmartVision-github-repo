# -*- coding: utf-8 -*-
"""القفل التلقائي للجهاز عند غياب المستخدم + التعرّف على عودته.

لماذا هذا الملف؟
----------------
هذا الملف ينفّذ "قفل ويندوز" الحقيقي، وهو غير متاح إلا على ويندوز؛
لذلك كل نداءات النظام (ctypes / rundll32) مكتوبة بشكل دفاعي: على نظام
آخر تُرجع False بدل أن ترمي استثناءً.

كما أنه لا يستورد tkinter لأنه يعمل داخل خيط عامل.

المبدأ:
    - الوجه المجهول (شخص لا نعرفه) لا يُبقي الجهاز مفتوحاً عندما يكون
      الخيار recognize_only مفعّلاً.
    - الجهاز يُقفل فعلياً بعد idle_seconds من غياب الوجوه.
    - عودة وجه معروف أثناء القفل تُطلق محاولة فتح القفل؛ إن لم تكن
      محاولة الفتح ممكنة نُبلغ المستخدم عبر تيليجرام فقط.
"""

import ctypes      # آمن الاستيراد على كل المنصات (windll غير موجود خارج ويندوز)
import datetime
import math
import os
import subprocess
import time

__all__ = ["AutoLockManager"]

# نُجرّب أكثر من اسم داخل قسم "autolock" لأن الإعدادات قد استعملت
# تسميات مختلفة بين الإصدارات.
_KEY_ENABLED = ["autolock.enabled", "autolock.active", "autolock.enable"]
_KEY_IDLE = [
    "autolock.idle_seconds",
    "autolock.timeout_seconds",
    "autolock.idle",
    "autolock.timeout",
]
_KEY_RECOGNIZE_ONLY = [
    "autolock.recognize_only",
    "autolock.only_known",
    "autolock.require_known",
]
_KEY_AUTO_TYPE = ["autolock.auto_type_password", "autolock.type_password"]
_KEY_PASSWORD = ["autolock.password", "autolock.pass"]


class AutoLockManager(object):
    """آلة حالات صغيرة: idle -> countdown -> locked -> recognized."""

    STATES = ("idle", "countdown", "locked", "recognized")

    def __init__(self, settings=None, translate=None, on_event=None):
        self.settings = settings
        self.translate = translate if callable(translate) else None
        self.on_event = on_event if callable(on_event) else None
        self.lang = "ar"
        self.last_error = ""
        self._state = "idle"
        self._countdown_end = None   # نهاية العد التنازلي (طابع زمني)
        self._clock = time.time()    # آخر ساعة معروفة (يسمح بساعة وهمية)
        self._locked = False         # هل القفل مطبَّق فعلياً على ويندوز؟
        self._last_seconds = None    # آخر عدد ثوانٍ أبلغنا عنه (لتجنب التكرار)
        self._present = False        # آخر حالة حضور (لإطلاق حدث presence مرة واحدة)

    # ------------------- خصائص -------------------
    @property
    def state(self):
        """الحالة الحالية: idle / countdown / locked / recognized."""
        return self._state

    @property
    def seconds_left(self):
        """الثواني المتبقية قبل القفل أثناء countdown (و0 في غيرها)."""
        if self._state != "countdown" or self._countdown_end is None:
            return 0
        remaining = self._countdown_end - self._clock
        if remaining <= 0:
            return 0
        return int(math.ceil(remaining))

    @property
    def is_locked(self):
        """هل حالة الآلة هي locked؟"""
        return self._state == "locked"

    @property
    def system_locked(self):
        """هل القفل مطبَّق فعلياً على ويندوز؟"""
        return bool(self._locked)

    # ------------------- الإعدادات -------------------
    def _setting(self, keys, default=None):
        """يقرأ إعداداً من settings بأمان (أو يعيد الافتراضي)."""
        if self.settings is None:
            return default
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            try:
                value = self.settings.get(key, None)
            except TypeError:
                try:
                    value = self.settings.get(key)
                except Exception:
                    value = None
            except Exception:
                value = None
            if value is not None:
                return value
        return default

    @staticmethod
    def _as_bool(value, default=False):
        """يحوّل قيمة إعداد إلى bool (يدعم true/1/نعم)."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = ("%s" % (value,)).strip().lower()
        if text in ("1", "true", "yes", "on", "y", "نعم", "فعال"):
            return True
        if text in ("0", "false", "no", "off", "n", "لا", "معطل"):
            return False
        return default

    @staticmethod
    def _as_int(value, default=0):
        """يحوّل قيمة إعداد إلى int بهدوء."""
        try:
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return default

    def _enabled(self):
        """هل الميزة مفعّلة؟ بلا إعدادات نعتبرها معطّلة (أأمن)."""
        if self.settings is None:
            return False
        value = self._setting(_KEY_ENABLED, None)
        if value is None:
            return True
        return self._as_bool(value, True)

    def _idle_seconds(self):
        """مدة الغياب المسموحة قبل القفل (بالثواني، وبحد أدنى 1)."""
        value = self._as_int(self._setting(_KEY_IDLE, 300), 300)
        if value < 1:
            value = 1
        return value

    # ------------------- الترجمة -------------------
    def _t(self, keys, default, **kwargs):
        """يترجم نصاً ويعود للقيمة الافتراضية إن لم يوجد المفتاح."""
        func = self.translate if callable(self.translate) else None
        if func is None:
            return default
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            value = self._call_translator(func, key, **kwargs)
            if value and value != key:
                return "%s" % (value,)
        return default

    def _call_translator(self, func, key, **kwargs):
        # نحاول عدة صيغ استدعاء لأن دوال الترجمة قد تختلف التوقيع
        attempts = (
            lambda: func(key, self.lang, **kwargs),
            lambda: func(key, **kwargs),
            lambda: func(key),
        )
        for attempt in attempts:
            try:
                value = attempt()
            except Exception:
                continue
            if value:
                return value
        return None

    # ------------------- الأحداث -------------------
    def _event(self, kind, seconds, name, message):
        """يبني قاموس الحدث ويبلّغ on_event بنسخة منه."""
        event = {
            "type": kind,
            "seconds": int(seconds),
            "name": name or "",
            "message": message or "",
        }
        if self.on_event is not None:
            try:
                self.on_event(dict(event))
            except Exception:
                # لا نسمح لخطأ في المستدعي بأن يُسقط التطبيق
                pass
        return event

    @staticmethod
    def _to_clock(now):
        """يحوّل now إلى طابع زمني (يقبل datetime أو رقم)."""
        if now is None:
            return time.time()
        if isinstance(now, datetime.datetime):
            try:
                return now.timestamp()
            except Exception:
                return time.time()
        if isinstance(now, datetime.date):
            try:
                return datetime.datetime.combine(now, datetime.time()).timestamp()
            except Exception:
                return time.time()
        try:
            return float(now)
        except Exception:
            return time.time()

    # ------------------- الآلة الأساسية -------------------
    def update(self, face_present=False, recognized=None, now=None):
        """تُستدعى مع كل إطار معالجة.

        :param face_present: هل يوجد وجه في الصورة؟
        :param recognized: None (لا معلومات) أو قائمة أسماء معروفة
                           أو [] (وجوه موجودة لكن مجهولة).
        :param now: ساعة اختيارية (datetime أو رقم) لتسهيل الاختبار.
        :return: قاموس حدث أو None.
        """
        try:
            return self._update(face_present, recognized, now)
        except Exception as exc:
            # لا نسمح بأي استثناء بالوصول إلى المستدعي
            self.last_error = "%s" % (exc,)
            self._state = "idle"
            self._countdown_end = None
            self._last_seconds = None
            return None

    def _update(self, face_present, recognized, now):
        clock = self._to_clock(now)
        self._clock = clock

        if not self._enabled():
            self._state = "idle"
            self._countdown_end = None
            self._last_seconds = None
            self._locked = False
            self._present = False
            return None

        names = []
        if recognized is not None:
            try:
                for item in recognized:
                    text = ("%s" % (item,)).strip()
                    if text:
                        names.append(text)
            except Exception:
                names = []

        recognize_only = self._as_bool(self._setting(_KEY_RECOGNIZE_ONLY, True), True)
        present = bool(face_present)
        known = bool(names)

        # مع recognize_only مفعّلاً: الوجه المجهول يُعامل كغياب.
        if present and (known or not recognize_only):
            return self._handle_presence(names)

        self._present = False
        return self._handle_absence(clock)

    def _handle_presence(self, names):
        """حالة وجود إنسان (معروف أو غير معروف حسب الإعداد)."""
        name = names[0] if names else ""
        was_locked = self._state == "locked"
        self._countdown_end = None
        self._last_seconds = None

        if was_locked:
            unlocked = False
            if self._locked:
                # محاولة فتح القفل فعلياً (قد تفشل إن لم تتوفر الأدوات)
                unlocked = self.unlock_now(name)
                if unlocked:
                    self._locked = False
            self._state = "recognized"
            if unlocked:
                message = self._t(
                    ["autolock.recognized"],
                    "تم التعرّف على %s وجارٍ فتح القفل" % (name,),
                    name=name,
                )
            else:
                message = self._t(
                    ["autolock.recognized_manual"],
                    "تم التعرّف على %s - افتح القفل يدوياً" % (name,),
                    name=name,
                )
            return self._event("recognized", 0, name, message)

        self._state = "idle"
        if not self._present:
            self._present = True
            message = self._t(
                ["autolock.presence"], "تم رصد وجود شخص أمام الكاميرا", name=name,
            )
            return self._event("presence", 0, name, message)
        return None

    def _handle_absence(self, clock):
        """حالة الغياب: بدء/استمرار العد التنازلي ثم القفل."""
        if self._state == "locked":
            return None

        idle = self._idle_seconds()
        if self._countdown_end is None:
            self._countdown_end = clock + idle
            self._state = "countdown"
            self._last_seconds = idle
            message = self._t(
                ["autolock.countdown"],
                "سيتم قفل الجهاز تلقائياً بعد %s ثانية" % (idle,),
                seconds=idle,
            )
            return self._event("countdown", idle, "", message)

        remaining = self._countdown_end - clock
        if remaining <= 0:
            self._countdown_end = None
            self._last_seconds = None
            self._state = "locked"
            ok = self.lock_now()
            if ok:
                message = self._t(["autolock.locked"], "تم قفل الجهاز تلقائياً")
            else:
                message = self._t(
                    ["autolock.locked_failed"],
                    "تم الانتقال إلى وضع القفل (تعذّر قفل ويندوز على هذا النظام)",
                )
            return self._event("locked", 0, "", message)

        seconds = int(math.ceil(remaining))
        self._state = "countdown"
        if seconds != self._last_seconds:
            # نُبلغ مرة واحدة فقط في الثانية لتفادي إغراق الواجهة
            self._last_seconds = seconds
            message = self._t(
                ["autolock.countdown"],
                "سيتم قفل الجهاز تلقائياً بعد %s ثانية" % (seconds,),
                seconds=seconds,
            )
            return self._event("countdown", seconds, "", message)
        return None

    # ------------------- القفل والفتح -------------------
    def lock_now(self):
        """يقفل محطة العمل فوراً. يعيد True عند النجاح."""
        if os.name != "nt":
            # خارج ويندوز لا يوجد قفل للشاشة؛ نُرجع False بدل الاستثناء
            self.last_error = "القفل التلقائي متاح على ويندوز فقط"
            return False
        try:
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                raise AttributeError("windll غير متاح")
            result = windll.user32.LockWorkStation()
            if result:
                self._locked = True
                return True
            self.last_error = "فشل قفل الجلسة (قد تكون هناك جلسة أخرى نشطة)"
        except Exception as exc:
            self.last_error = "%s" % (exc,)

        # بديل: نفس الدالة لكن عبر rundll32 (يعمل حتى لو تعطّل ctypes)
        try:
            proc = subprocess.Popen(
                ["rundll32.exe", "user32.dll,LockWorkStation"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            self._locked = True
            return True
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return False

    def unlock_now(self, name=""):
        """محاولة فتح القفل (غير مضمونة أمنياً).

        تعمل فقط إذا كان auto_type_password مفعّلاً وكان هناك كلمة مرور
        مخزّنة و pyautogui متاحاً. في غير ذلك نُبلغ المستخدم عبر
        تيليجرام فقط ونُعيد False.

        ملاحظة أمنية: لا تُطبع كلمة المرور ولا تُخزَّن في السجلات.
        """
        try:
            auto_type = self._as_bool(self._setting(_KEY_AUTO_TYPE, False), False)
            password = self._setting(_KEY_PASSWORD, "")
            if not auto_type:
                return False
            if not password:
                return False
            try:
                import pyautogui
            except Exception:
                # pyautogui اختياري؛ نُبلغ المستخدم بدل الفتح الآمن
                self.last_error = "pyautogui غير متاح لفتح القفل تلقائياً"
                return False
            try:
                pyautogui.write("%s" % (password,))
                pyautogui.press("enter")
                return True
            except Exception as exc:
                self.last_error = "%s" % (exc,)
                return False
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return False

    def reset(self):
        """يلغي العد التنازلي ويمسح علامة القفل."""
        self._state = "idle"
        self._countdown_end = None
        self._last_seconds = None
        self._locked = False
        self._present = False
