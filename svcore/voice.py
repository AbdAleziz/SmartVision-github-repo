# -*- coding: utf-8 -*-
"""
التحكم الصوتي بإشارة اليد.

إشارة اليد (راحة اليد / القبضة) تُطلق أمراً صوتياً. وله طريقتان للتشغيل:
  1. "الإدخال الصوتي" في ويندوز (Win+H) — يعمل دائماً تقريباً.
  2. تعرّف على أوامر منطوقة — يعمل إن كانت مكتبة speech_recognition مثبتة
     (مع pyaudio). إن لم تكن موجودة نعرض رسالة واضحة ولا نفشل بصمت.
"""

import threading
import time

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except Exception:
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    import speech_recognition as sr
    HAS_SR = True
except Exception:
    sr = None
    HAS_SR = False


# ---------------------------------------------------------------------------
# الأوامر المدعومة (بالعربية والإنجليزية)
# ---------------------------------------------------------------------------
COMMANDS = {
    "lock": {"ar": ("قفل", "اقفل الجهاز"), "en": ("lock", "lock the device")},
    "unlock": {"ar": ("فتح", "افتح"), "en": ("unlock", "open")},
    "photo": {"ar": ("صورة", "التقط صورة"), "en": ("photo", "take photo", "snapshot")},
    "scan": {"ar": ("مسح", "امسح", "ماسح"), "en": ("scan", "scan document")},
    "next": {"ar": ("التالي",), "en": ("next", "next slide")},
    "prev": {"ar": ("السابق",), "en": ("prev", "previous", "back")},
    "record": {"ar": ("تسجيل", "سجّل"), "en": ("record", "start recording")},
    "stop": {"ar": ("اوقف", "توقف"), "en": ("stop", "stop")},
    "draw": {"ar": ("رسم", "ارسم"), "en": ("draw", "draw")},
    "stats": {"ar": ("احصائيات", "إحصائيات"), "en": ("stats", "statistics")},
}


def _keywords_for(key, lang="ar"):
    data = COMMANDS.get(key, {})
    words = []
    for lang_key in ([lang] if lang in data else []) + ["ar", "en"]:
        entry = data.get(lang_key)
        if entry:
            words.extend(list(entry))
    return words


def match_command(text, lang="ar"):
    """يربط النص المنطوق بأمر. يعيد (key, matched_keyword) أو (None, None)."""
    if not text:
        return None, None
    low = str(text).lower().strip()
    best = None
    for key in COMMANDS:
        for word in _keywords_for(key, lang):
            if word and word.lower() in low:
                if best is None or len(word) > len(best[1]):
                    best = (key, word)
    return best if best else (None, None)


class VoiceController(object):
    """ينفّذ الأوامر الصوتية ويحذّر إن كانت المكتبة غير متوفرة."""

    def __init__(self, translate=None, on_command=None):
        self.translate = translate        # دالة ترجمة (اختياري)
        self.on_command = on_command      # تُستدعى عند تنفيذ أمر
        self.listening = False

    # ----------------------------------------------------------- الأساسيات
    def hotkey(self, combo="win+h"):
        """يشغّل اختصار ويندوز (افتح الإدخال الصوتي)."""
        if not HAS_PYAUTOGUI:
            return False
        try:
            parts = [p.strip().lower() for p in str(combo).split("+") if p.strip()]
            if not parts:
                return False
            pyautogui.hotkey(*parts, _pause=False)
            return True
        except Exception:
            return False

    def press(self, key):
        if not HAS_PYAUTOGUI:
            return False
        try:
            pyautogui.press(key, _pause=False)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------- الاستماع
    def listen(self, timeout=6, lang="ar"):
        """يستمع لأمر منطوق. يعيد (ok, text_or_error)."""
        if not HAS_SR:
            return False, ("speech_recognition is not installed. "
                           "pip install SpeechRecognition pyaudio")
        result = {"text": "", "error": None}
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = recognizer.listen(source, timeout=timeout)
            code = "ar-SA" if str(lang).lower().startswith("ar") else "en-US"
            try:
                result["text"] = recognizer.recognize_google(audio, language=code)
            except Exception:
                result["text"] = recognizer.recognize_google(audio)
        except Exception as e:
            result["error"] = str(e)
        if result["error"]:
            return False, result["error"]
        return True, result["text"]

    def listen_and_run(self, timeout=6, lang="ar"):
        """يستمع ثم ينفّذ الأمر المطابق. يعيد (ok, info)."""
        self.listening = True
        try:
            ok, text = self.listen(timeout, lang)
        finally:
            self.listening = False
        if not ok:
            return False, text
        key, word = match_command(text, lang)
        if key is None:
            return False, text
        self.execute(key)
        return True, key

    def listen_async(self, timeout=6, lang="ar", on_result=None):
        """يشغّل الاستماع في خيط حتى لا تتجمد الواجهة."""

        def job():
            ok, info = self.listen_and_run(timeout, lang)
            if on_result:
                try:
                    on_result(ok, info)
                except Exception:
                    pass

        t = threading.Thread(target=job, name="voice", daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------- التنفيذ
    def execute(self, key):
        """ينفّذ أمراً: يرسل الحدث للواجهة (التي تنفّذ pyautogui فعلياً)."""
        if self.on_command:
            try:
                self.on_command(key)
                return True
            except Exception:
                return False
        return False

    @staticmethod
    def available():
        return HAS_SR
