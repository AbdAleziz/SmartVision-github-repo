# -*- coding: utf-8 -*-
"""إشعارات تيليجرام (Telegram) بدون أي مكتبات خارجية.

لماذا هذا الملف؟
----------------
التطبيق يُثبَّت على أجهزة المستخدم بدون إنترنت مضمون وبدون أي حقن
pip install، لذلك بُني عميل التليجرام على urllib.request من المكتبة
القياسية فقط (وليس requests).

كما أن هذه الوحدة لا تستورد tkinter لأنها تُستدعى من خيط عامل
(BackgroundJob) وليس من واجهة الرسوميات.
"""

import io
import json
import os
import socket
import uuid
from urllib import error as _urlerror
from urllib import request as _urlrequest
from urllib.parse import urlencode

__all__ = [
    "TelegramBot",
    "send_telegram",
    "set_translator",
    "get_translator",
    "build_multipart",
    "API_BASE",
    "DEFAULT_TIMEOUT",
]

# نقطة النهاية الرسمية لبوت تيليجرام
API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 12
USER_AGENT = "SmartVision/2.0 (telegram-notifier)"
# أقصى طول للوصف المسموح به في تيليجرام
MAX_CAPTION = 1024

# الترجمة العامة: تُسجَّل مرة واحدة من الواجهة عبر set_translator.
# نتجنّب استيراد i18n هنا حتى لا يحدث استيراد دوري.
_TRANSLATOR = None


def set_translator(func):
    """يسجّل دالة ترجمة عامة للاستخدام في كل النسخ.

    التوقيع المتوقع: func(key, lang, **kwargs) -> str
    أي خطأ داخل الدالة يُبتلع حتى لا يسقط التطبيق بسبب الترجمة.
    """
    global _TRANSLATOR
    _TRANSLATOR = func if callable(func) else None
    return _TRANSLATOR


def get_translator():
    """يعيد دالة الترجمة العامة الحالية أو None."""
    return _TRANSLATOR


def _new_boundary():
    """يولّد حداً (boundary) فريداً لنموذج multipart/form-data."""
    return "----SmartVisionBoundary%s" % uuid.uuid4().hex


def build_multipart(fields, files, boundary=None):
    """يبني جسم multipart/form-data يدوياً كـ bytes.

    :param fields: قاموس {اسم_الحقل: قيمة} (نص أو bytes).
    :param files: قائمة رباعية (اسم_الحقل، اسم_الملف، نوع_المحتوى، البيانات).
    :param boundary: حد اختياري؛ يُولَّد تلقائياً إن لم يُمرَّر.
    :return: (الجسم بالـ bytes، الحد المستخدم).
    """
    if boundary is None:
        boundary = _new_boundary()
    if not isinstance(boundary, str):
        boundary = "%s" % (boundary,)

    sep = ("--" + boundary).encode("ascii")
    crlf = b"\r\n"
    buf = io.BytesIO()

    for name, value in (fields or {}).items():
        buf.write(sep)
        buf.write(crlf)
        buf.write(('Content-Disposition: form-data; name="%s"' % (name,)).encode("utf-8"))
        buf.write(crlf)
        buf.write(crlf)
        if isinstance(value, (bytes, bytearray)):
            buf.write(bytes(value))
        else:
            buf.write(("%s" % (value,)).encode("utf-8"))
        buf.write(crlf)

    for item in (files or []):
        try:
            fname, filename, ctype, data = item
        except Exception:
            continue
        buf.write(sep)
        buf.write(crlf)
        buf.write(
            (
                'Content-Disposition: form-data; name="%s"; filename="%s"'
                % (fname, filename)
            ).encode("utf-8")
        )
        buf.write(crlf)
        buf.write(("Content-Type: %s" % (ctype or "application/octet-stream",)).encode("ascii"))
        buf.write(crlf)
        buf.write(crlf)
        if isinstance(data, str):
            data = data.encode("utf-8")
        elif isinstance(data, bytearray):
            data = bytes(data)
        buf.write(data if isinstance(data, bytes) else b"")
        buf.write(crlf)

    # الحد الختامي
    buf.write(sep)
    buf.write(b"--")
    buf.write(crlf)
    return buf.getvalue(), boundary


class TelegramBot(object):
    """عميل تيليجرام بسيط. كل الدوال العامة لا ترمي استثناءات نحو المستدعي."""

    def __init__(self, token="", chat_id="", timeout=DEFAULT_TIMEOUT, translate=None):
        self.token = ""
        self.chat_id = ""
        self.timeout = DEFAULT_TIMEOUT
        self.translate = None
        self.lang = "ar"
        self.last_error = ""
        self.configure(token, chat_id)
        try:
            value = float(timeout)
            if value > 0:
                self.timeout = value
        except Exception:
            pass
        if callable(translate):
            self.translate = translate

    # ------------------- خصائص -------------------
    @property
    def enabled(self):
        """True فقط إذا كان التوكن ومعرّف المحادثة موجودين معاً."""
        return bool(self.token) and bool(self.chat_id)

    def configure(self, token, chat_id):
        """يحدّث بيانات الاتصال (يُستدعى عند حفظ الإعدادات)."""
        try:
            self.token = ("%s" % (token,)).strip() if token else ""
        except Exception:
            self.token = ""
        try:
            self.chat_id = ("%s" % (chat_id,)).strip() if chat_id is not None else ""
        except Exception:
            self.chat_id = ""

    # ------------------- الترجمة -------------------
    def _t(self, keys, default, **kwargs):
        """يترجم نصاً ويعود للقيمة الافتراضية إذا لم يوجد المفتاح."""
        func = self.translate if callable(self.translate) else _TRANSLATOR
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

    # ------------------- الإرسال -------------------
    def send_text(self, text):
        """يرسل رسالة نصية. يعيد (ok, message)."""
        try:
            if not self.enabled:
                return (False, self._t(
                    ["telegram.not_configured"],
                    "التليجرام غير مفعّل: لا يوجد توكن أو معرّف محادثة",
                ))
            if text is None:
                text = ""
            elif not isinstance(text, str):
                text = "%s" % (text,)
            url = "%s/bot%s/sendMessage" % (API_BASE, self.token)
            payload = urlencode({
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": USER_AGENT,
            }
            return self._post(url, payload, headers)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return (False, "%s" % (exc,))

    def send_photo(self, path, caption=""):
        """يرسل صورة.

        path قد يكون مسار ملف على القرص أو بيانات JPEG خام (bytes/bytearray)؛
        نكتشف النوع تلقائياً.
        """
        try:
            if not self.enabled:
                return (False, self._t(
                    ["telegram.not_configured"],
                    "التليجرام غير مفعّل: لا يوجد توكن أو معرّف محادثة",
                ))
            if isinstance(path, (bytes, bytearray)):
                return self.send_photo_bytes(bytes(path), caption)
            if path is None:
                return (False, self._t(
                    ["telegram.no_file"], "لم يتم تحديد صورة لإرسالها",
                ))
            try:
                real_path = os.fspath(path)
            except Exception:
                real_path = "%s" % (path,)
            if not os.path.isfile(real_path):
                return (False, self._t(
                    ["telegram.file_missing"],
                    "الملف غير موجود: %s" % (real_path,),
                    path=real_path,
                ))
            try:
                with open(real_path, "rb") as handle:
                    data = handle.read()
            except Exception as exc:
                self.last_error = "%s" % (exc,)
                return (False, "%s" % (exc,))
            return self.send_photo_bytes(data, caption)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return (False, "%s" % (exc,))

    def send_photo_bytes(self, jpeg_bytes, caption=""):
        """يرسل بيانات JPEG خاماً. يعيد (ok, message)."""
        try:
            if not self.enabled:
                return (False, self._t(
                    ["telegram.not_configured"],
                    "التليجرام غير مفعّل: لا يوجد توكن أو معرّف محادثة",
                ))
            if jpeg_bytes is None:
                return (False, self._t(
                    ["telegram.no_file"], "لا توجد بيانات صورة لإرسالها",
                ))
            if isinstance(jpeg_bytes, bytearray):
                jpeg_bytes = bytes(jpeg_bytes)
            if not isinstance(jpeg_bytes, bytes):
                try:
                    jpeg_bytes = bytes(jpeg_bytes)
                except Exception:
                    return (False, self._t(
                        ["telegram.bad_image"], "بيانات الصورة غير صالحة",
                    ))
            if not jpeg_bytes:
                return (False, self._t(
                    ["telegram.empty_image"], "الصورة فارغة",
                ))

            fields = {"chat_id": self.chat_id}
            text = "" if caption is None else "%s" % (caption,)
            if len(text) > MAX_CAPTION:
                text = text[:MAX_CAPTION]
            if text:
                fields["caption"] = text

            files = [("photo", "photo.jpg", "image/jpeg", jpeg_bytes)]
            body, boundary = build_multipart(fields, files)

            url = "%s/bot%s/sendPhoto" % (API_BASE, self.token)
            headers = {
                "Content-Type": "multipart/form-data; boundary=%s" % (boundary,),
                "User-Agent": USER_AGENT,
            }
            return self._post(url, body, headers)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return (False, "%s" % (exc,))

    def test(self):
        """يرسل رسالة اختبار قصيرة للتأكد من عمل الإعدادات."""
        try:
            text = self._t(
                ["telegram.test_message"],
                "Smart Vision: تم إرسال رسالة الاختبار بنجاح.",
            )
            return self.send_text(text)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return (False, "%s" % (exc,))

    # ------------------- الشبكة -------------------
    def _post(self, url, data, headers):
        """ينفّذ طلب POST ويحوّل النتيجة إلى (ok, message)."""
        try:
            request = _urlrequest.Request(
                url, data=data, headers=headers, method="POST"
            )
            response = _urlrequest.urlopen(request, timeout=self.timeout)
            try:
                raw = response.read()
                status = getattr(response, "status", None)
                if status is None:
                    try:
                        status = response.getcode()
                    except Exception:
                        status = 200
            finally:
                try:
                    response.close()
                except Exception:
                    pass
            return self._parse_answer(raw, status)
        except _urlerror.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
            except Exception:
                pass
            message = self._error_from_body(body)
            if not message:
                message = "%s" % (exc,)
            self.last_error = message
            return (False, message)
        except _urlerror.URLError as exc:
            message = "%s" % (getattr(exc, "reason", exc),)
            self.last_error = message
            return (False, message)
        except socket.timeout:
            message = self._t(
                ["telegram.timeout"], "انتهت مهلة الاتصال بخادم تيليجرام",
            )
            self.last_error = message
            return (False, message)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return (False, "%s" % (exc,))

    def _parse_answer(self, raw, status=200):
        """يحلّل رد تيليجرام: نجاح فقط عند ok=true."""
        try:
            if isinstance(raw, (bytes, bytearray)):
                text = bytes(raw).decode("utf-8", "replace")
            else:
                text = "%s" % (raw,)
            data = json.loads(text)
        except Exception:
            message = self._t(
                ["telegram.bad_response"], "تعذّر قراءة الرد من خادم تيليجرام",
            )
            self.last_error = message
            return (False, message)
        if not isinstance(data, dict):
            message = self._t(
                ["telegram.bad_response"], "رد غير متوقع من خادم تيليجرام",
            )
            self.last_error = message
            return (False, message)
        if data.get("ok") is True:
            return (True, self._t(["telegram.sent"], "تم الإرسال بنجاح"))
        description = data.get("description")
        if not description:
            description = self._t(["telegram.failed"], "فشل إرسال الرسالة")
        self.last_error = "%s" % (description,)
        return (False, "%s" % (description,))

    def _error_from_body(self, body):
        """يستخرج حقل description من جسم خطأ HTTP."""
        try:
            text = bytes(body).decode("utf-8", "replace")
            data = json.loads(text)
            if isinstance(data, dict):
                return "%s" % (data.get("description") or data.get("error_code") or "")
        except Exception:
            pass
        return ""


def send_telegram(token, chat_id, text, timeout=DEFAULT_TIMEOUT):
    """اختصار سريع: ينشئ كائناً مؤقتاً ويرسل رسالة واحدة."""
    try:
        bot = TelegramBot(token, chat_id, timeout)
        return bot.send_text(text)
    except Exception as exc:
        return (False, "%s" % (exc,))
