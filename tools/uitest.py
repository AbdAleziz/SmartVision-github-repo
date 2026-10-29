# -*- coding: utf-8 -*-
"""
دخانة اختبار الواجهة (smoke test).

يبني النافذة كاملة باستخدام بديل Tkinter ويشغّل أهم المسارات
(بناء اللوحات، تبديل اللغة/الثيم، الأحداث، الإجراءات) للتأكد من عدم وجود
أخطاء في الربط بين الواجهة والنواة.

    python tools/uitest.py
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUBS = os.path.join(ROOT, "tools", "stubs")

try:
    import tkinter          # noqa: F401
    REAL_TK = True
except Exception:
    REAL_TK = False

# نستخدم بديل Tkinter دائماً حتى تكون الاختبارات بلا نوافذ وبدون شاشة
# (نفسها تُنفَّذ على CI بلا مكتب رسومي).
if os.environ.get("SMARTVISION_REAL_TK") != "1":
    sys.path.insert(0, STUBS)
    REAL_TK = False

FAILURES = []
COUNT = [0]


def check(label, condition, extra=""):
    COUNT[0] += 1
    if condition:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s %s" % (label, extra))
        FAILURES.append(label)


def prepare_sandbox():
    """نسخة مؤقتة من المشروع حتى لا نلوّث مجلد المشروع بالإعدادات والبيانات."""
    tmp = tempfile.mkdtemp(prefix="svui_")
    project = os.path.join(tmp, "project")
    shutil.copytree(ROOT, project,
                    ignore=shutil.ignore_patterns("__pycache__", ".git", "data",
                                                 "*.pyc", "settings.json"))
    sys.path.insert(0, project)
    os.chdir(project)
    return project


def main():
    prepare_sandbox()

    from svcore import app as appmod

    print("== بناء النافذة ==")
    app = appmod.App()
    check("النافذة بُنيت", app is not None)
    check("اللغة الافتراضية عربية", app.lang == "ar")
    check("عدد التبويبات", len(app.panels) == 8, list(app.panels.keys()))
    check("أزرار الأنماط", len(app.mode_buttons) == 10, len(app.mode_buttons))
    check("لوحات مبنية", all(p is not None for p in app.panels.values()))

    print("\n== تبديل اللغة ==")
    app.toggle_language()
    check("انتقلت للإنجليزية", app.lang == "en", app.lang)
    check("العنوان بالإنجليزية", app.title() == "Smart Vision Studio", app.title())
    app.toggle_language()
    check("رجعت للعربية", app.lang == "ar")

    print("\n== تبديل الثيم ==")
    app.toggle_theme()
    check("الثيم فاتح", app.theme.name == "light", app.theme.name)
    app.toggle_theme()
    check("الثيم غامق", app.theme.name == "dark")

    print("\n== الأنماط ==")
    for mode in (appmod.M_MOTION, appmod.M_FACE, appmod.M_QR, appmod.M_COUNTER,
                 appmod.M_FACEID, appmod.M_DRAW, appmod.M_SLIDES, appmod.M_VOICE,
                 appmod.M_ALL):
        app.set_mode(mode)
        check("نمط %s" % mode, app.mode == mode, app.mode)
    app.set_mode(appmod.M_MOTION)
    check("تفعيل النمط", app.mode == appmod.M_MOTION, app.mode)
    app.set_mode(appmod.M_MOTION)
    check("إلغاء النمط بالنقر مرتين", app.mode is None, app.mode)

    print("\n== الأحداث ==")
    app.events.put((app.wid, "started", ()))
    app.events.put((app.wid, "code", ("HELLO-123", "QRCODE")))
    app.events.put((app.wid, "saved", ("motion_test.jpg",)))
    app.events.put((app.wid, "log", ("رسالة سجل",)))
    app.events.put((app.wid, "counter", ("in", 1, {"in": 1, "out": 0})))
    app.events.put((app.wid, "attendance", ({"event": "in", "name": "أحمد",
                                             "time": "10:00", "duration_min": 0},)))
    app.events.put((app.wid, "countdown", (3,)))
    app.events.put((app.wid, "shot", ("photo.jpg",)))
    app.events.put((app.wid, "draw", ("drawing.png",)))
    app.events.put((app.wid, "slides", ("next",)))
    app.events.put((app.wid, "lock", ({"type": "countdown", "seconds": 5},)))
    app.events.put((app.wid, "lock", ({"type": "locked", "message": "قفل"},)))
    app.events.put((app.wid, "lock", ({"type": "recognized", "name": "أحمد"},)))
    app.events.put((app.wid, "voice_trigger", ("palm",)))
    app.events.put((app.wid, "voice_result", (True, "lock")))
    app.events.put((app.wid, "stopped", ()))
    try:
        app._drain_events()
        check("معالجة كل الأحداث بلا خطأ", True)
    except Exception as e:
        check("معالجة كل الأحداث بلا خطأ", False, "%s: %s" % (type(e).__name__, e))
    check("الكود محفوظ", app.last_code == "HELLO-123", app.last_code)

    print("\n== الإجراءات ==")
    for name, fn in (("نسخ النص", app.copy_text),
                     ("فتح الرابط", app.open_last_link),
                     ("حفظ الرسم", app.save_drawing),
                     ("مسح الرسم", app.clear_drawing),
                     ("تصدير الحضور CSV", lambda: app.export_attendance("csv")),
                     ("تصدير الإحصائيات", app.export_stats),
                     ("ماسح المستند", app.scan_document),
                     ("حفظ PDF", app.save_scan_pdf),
                     ("التقط صورة", lambda: app.capture_photo("bw", True, True)),
                     ("قفل الآن", app.lock_now),
                     ("اختبار تيليجرام", app.test_telegram)):
        try:
            fn()
            check(name, True)
        except Exception as e:
            check(name, False, "%s: %s" % (type(e).__name__, e))

    print("\n== الحفظ والإغلاق ==")
    try:
        app.on_close()
        check("إغلاق نظيف", True)
    except Exception as e:
        check("إغلاق نظيف", False, str(e))

    print("\n%d فحص - فشل: %d" % (COUNT[0], len(FAILURES)))
    if FAILURES:
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("دخانة الواجهة نجحت ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
