# -*- coding: utf-8 -*-
"""
اختبارات ذاتية للمشروع (لا تحتاج OpenCV ولا Tkinter).

    python tools/selftest.py

تغطي: الترجمة، الإعدادات، CSV، العدّاد، سجل الحضور، الأوامر الصوتية،
كاتب PDF، الإحصائيات، القفل التلقائي، تيليجرام، واستيراد الواجهة.
"""

import os
import re
import sys
import tempfile


def _setup_console():
    """يجعل المخرجات UTF-8 حتى لا يسقط البرنامج على ويندوز (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_setup_console()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUBS = os.path.join(ROOT, "tools", "stubs")

# لو لم يكن Tkinter موجوداً نستخدم بديل الاستيراد للاختبارات فقط
try:
    import tkinter          # noqa: F401
except Exception:
    sys.path.insert(0, STUBS)

sys.path.insert(0, ROOT)

FAILURES = []
CHECKS = [0]


def check(label, condition, extra=""):
    CHECKS[0] += 1
    if condition:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s %s" % (label, extra))
        FAILURES.append(label)
    try:
        sys.stdout.flush()      # ترتيب السجل صحيح في CI
    except Exception:
        pass


def section(title):
    print("\n== %s ==" % title)


# ---------------------------------------------------------------------------
def test_i18n():
    section("الترجمة")
    from svcore import i18n
    keys = set(i18n.STRINGS.keys())
    check("كل مدخل له نصان", all(len(v) == 2 for v in i18n.STRINGS.values()))
    empty_ar = [k for k, v in i18n.STRINGS.items() if not v[0].strip()]
    empty_en = [k for k, v in i18n.STRINGS.items() if not v[1].strip()]
    check("لا نص عربي فارغ", not empty_ar, empty_ar[:5])
    check("لا نص إنجليزي فارغ", not empty_en, empty_en[:5])
    same = [k for k, v in i18n.STRINGS.items() if v[0].strip() == v[1].strip()]
    check("لا نص مترجم ناقص", len(same) <= 5, same[:5])
    check("الترجمة ترجع النص", i18n.t("app.title", i18n.AR) != "app.title")
    check("الترجمة تختار اللغة",
          i18n.t("app.title", i18n.AR) != i18n.t("app.title", i18n.EN))
    check("مفتاح مجهول", i18n.t("no.such.key", i18n.AR) == "no.such.key")
    check("صيغة %s تعمل", i18n.t("scanner.pages", i18n.AR, n=3) == "الصفحات الملتقطة: 3")

    # كل مفتاح مستعمل في الواجهة موجود
    used = set()
    pattern = re.compile(r"""(?:\.|^)t\(\s*["']([a-zA-Z0-9_.]+)["']""")
    for base, dirs, files in os.walk(os.path.join(ROOT, "svcore")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            with open(os.path.join(base, name), "r", encoding="utf-8") as f:
                for line in f:
                    if '"' in line or "'" in line:
                        for m in pattern.findall(line):
                            used.add(m)
    unknown = sorted(k for k in used if k not in keys)
    check("كل مفتاح مستعمل معرّف", not unknown, unknown[:8])
    print("     (المفاتيح: %d، المستعملة: %d)" % (len(keys), len(used)))


def test_config():
    section("الإعدادات")
    from svcore.config import Settings, DEFAULTS
    tmp = tempfile.mkdtemp(prefix="svcfg_")
    path = os.path.join(tmp, "settings.json")
    s = Settings(path)
    check("اللغة الافتراضية عربية", s.get("language") == "ar")
    s.set("telegram.token", "123:ABC")
    s.set("autolock.idle_seconds", 42)
    check("حفظ قيمة متداخلة", s.get("telegram.token") == "123:ABC")
    check("حفظ عدد", s.get("autolock.idle_seconds") == 42)
    check("الحفظ نجح", s.save())
    s2 = Settings(path)
    check("التحميل يستعيد التوكن", s2.get("telegram.token") == "123:ABC")
    check("التحميل يستعيد الثواني", s2.get("autolock.idle_seconds") == 42)
    check("القيم الافتراضية سليمة", DEFAULTS["counter"]["line"] == [0.5, 0.0, 0.5, 1.0])
    s2.reset()
    check("إعادة الضبط", s2.get("telegram.token", "") == "")


def test_utils():
    section("الأدوات")
    from svcore.utils import append_csv, read_csv, safe_filename, iou, RateLimiter
    tmp = tempfile.mkdtemp(prefix="svutil_")
    path = os.path.join(tmp, "t.csv")
    append_csv(path, ["timestamp", "value"], ["1", "2"])
    append_csv(path, ["timestamp", "value"], ["=cmd", "x"])
    rows = read_csv(path)
    check("CSV فيه صفان", len(rows) == 2, rows)
    check("CSV يتجاهل الترويسة", rows and rows[0][0] == "1", rows)
    check("منع تنفيذ المعادلات", rows and rows[1][0].startswith("'"), rows)
    check("اسم ملف آمن", safe_filename("a/b:c*") == "a_b_c_", safe_filename("a/b:c*"))
    check("اسم عربي محفوظ", safe_filename("أحمد") == "أحمد")
    check("IoU صحيح", abs(iou((0, 0, 10, 10), (0, 0, 10, 10)) - 1.0) < 1e-6)
    check("IoW صفري", iou((0, 0, 10, 10), (50, 50, 10, 10)) == 0.0)
    lim = RateLimiter(10)
    check("RateLimiter يسمح مرة", lim.allow())
    check("RateLimiter يمنع الثاني", not lim.allow())


def test_counter():
    section("عدّاد الأشخاص")
    from svcore.counter import PeopleCounter
    c = PeopleCounter()
    c.set_line((0.0, 0.5), (1.0, 0.5))     # خط أفقي في منتصف الإطار
    check("حفظ الخط", c.get_line() == [0.0, 0.5, 1.0, 0.5])
    check("الجهة السفلى موجبة (جهة الدخول)",
          PeopleCounter.side_of((0, 100, 200, 100), 100, 150) > 0)
    check("الجهة العليا سالبة",
          PeopleCounter.side_of((0, 100, 200, 100), 100, 50) < 0)

    # شخص يعبر الخط من الأعلى إلى الأسفل = دخول (على خطوات)
    events = c.update([(90, 30, 40, 40)], (200, 200), now=100.0)
    check("لا حدث قبل العبور", not events, events)
    events = c.update([(90, 70, 40, 40)], (200, 200), now=101.0)
    check("لا حدث قبل استقرار الجانب", not events, events)
    events = c.update([(90, 110, 40, 40)], (200, 200), now=102.0)
    check("لا حدث قبل استقرار الجهة", not events, events)
    events = c.update([(90, 110, 40, 40)], (200, 200), now=103.0)
    check("حدث دخول", events and events[0]["event"] == "in", events)
    check("العداد = 1", c.counts["in"] == 1, c.counts)

    # العودة للجهة الأصلية = خروج
    c.update([(90, 70, 40, 40)], (200, 200), now=104.0)
    events = c.update([(90, 30, 40, 40)], (200, 200), now=105.0)
    check("حدث خروج", events and events[0]["event"] == "out", events)
    check("العدّاد النهائي", c.counts == {"in": 1, "out": 1}, c.counts)
    c.reset()
    check("إعادة الضبط", c.counts == {"in": 0, "out": 0})


def test_faceid():
    section("قاعدة بيانات الوجوه")
    from svcore.faceid import FaceDatabase
    tmp = tempfile.mkdtemp(prefix="svface_")
    db = FaceDatabase(faces_dir=os.path.join(tmp, "faces"),
                      models_dir=os.path.join(tmp, "models"))
    check("لا وجوه مسجّلة", db.names() == [], db.names())
    name, dist = db.identify(None)
    check("لا تعرّف بدون صور", name == "" and dist > 100, (name, dist))
    check("العتب الافتراضي", db.threshold == 72, db.threshold)
    db.threshold = 40
    check("تغيير العتب", db.threshold == 40)
    ok, msg = db.enroll("أحمد", [])
    check("رفض عينات قليلة", ok is False, msg)


def test_attendance():
    section("سجل الحضور")
    import datetime
    from svcore.faceid import AttendanceTracker
    tmp = tempfile.mkdtemp(prefix="svatt_")
    at = AttendanceTracker(gap_seconds=10, log_dir=tmp)
    # نستخدم تاريخاً واقعياً لا أرقام طابع زمنية: أنظمة ويندوز تفشل
    # timestamp() لأي تاريخ قبل 1970 (mktime) وهذا كان يسقط الاختبار.
    t0 = datetime.datetime(2024, 5, 1, 10, 0, 0)
    events = at.update(["أحمد"], now=t0)
    check("تسجيل دخول", events and events[0]["event"] == "in", events)
    check("الاسم صحيح", events and events[0]["name"] == "أحمد")
    events = at.update(["أحمد"], now=t0 + datetime.timedelta(seconds=1))
    check("لا تكرار أثناء التواجد", not events, events)
    events = at.update([], now=t0 + datetime.timedelta(seconds=5))
    check("لا خروج قبل الفجوة", not events, events)
    events = at.update([], now=t0 + datetime.timedelta(seconds=30))
    check("خروج بعد الفجوة", events and events[0]["event"] == "out", events)
    check("المدة محسوبة", events and events[0]["duration_min"] >= 0)
    rows = at.rows_today()
    check("صفوف في السجل", len(rows) >= 2, rows)
    csv_path = at.export_csv()
    check("تصدير CSV", bool(csv_path) and os.path.isfile(csv_path))
    try:
        import openpyxl                       # noqa
        xlsx = at.export_xlsx()
        check("تصدير Excel", bool(xlsx) and os.path.isfile(xlsx))
    except ImportError:
        check("تصدير Excel (بدون openpyxl)", at.export_xlsx() == "")
    except Exception as e:
        check("تصدير Excel", False, "%s: %s" % (type(e).__name__, e))

    # تاريخ قبل 1970: يجب ألّا يسقط أبداً (ويندوز)
    try:
        old = datetime.datetime(1969, 6, 1, 12, 0, 0)
        at2 = AttendanceTracker(gap_seconds=5, log_dir=tmp)
        ev = at2.update(["سعيد"], now=old)
        check("تاريخ قبل 1970 لا يسقط", bool(ev), ev)
    except Exception as e:
        check("تاريخ قبل 1970 لا يسقط", False, "%s: %s" % (type(e).__name__, e))


def test_voice():
    section("الأوامر الصوتية")
    from svcore.voice import match_command, COMMANDS
    check("كل الأوامر لها كلمات", all(COMMANDS.values()))
    check("تطابق عربي", match_command("يا برنامج اقفل الجهاز")[0] == "lock")
    check("تطابق إنجليزي", match_command("please take a photo")[0] == "photo")
    check("أمر غير معروف", match_command("what time is it")[0] is None)
    check("نص فارغ", match_command("")[0] is None)


def test_textdraw():
    section("رسم النصوص")
    from svcore.textdraw import shape_arabic, to_latin
    shaped = shape_arabic("أحمد")
    check("التشكيل يحوّل الحروف", "ﺣ" in shaped or "ﺎ" in shaped, shaped)
    check("الترجمة اللاتينية", to_latin("أحمد") == "ahmd", to_latin("أحمد"))


def test_qr_engine():
    section("محرك الأكواد")
    from svcore.qr_engine import CodeEngine
    engine = CodeEngine()
    check("تعرّف على الروابط", engine.is_url("https://example.com"))
    check("ليس رابطاً", not engine.is_url("hello"))
    check("الكود الجديد يُبلَّغ", engine.is_new("ABC"))
    check("نفس الكود لا يُبلَّغ", not engine.is_new("ABC"))
    engine2 = CodeEngine(dedupe_seconds=0)
    check("بعد انتهاء النافذة يعود جديداً", engine2.is_new("ABC"))


def test_pdfwriter():
    section("كاتب PDF")
    from svcore.pdfwriter import PdfWriter, SimplePdfWriter
    fake = b"\xff\xd8\xff\xe0" + b"jpegdata" * 20
    writer = PdfWriter()
    check("إضافة صفحة", writer.add_jpeg(fake, 100, 200) == 1)
    check("إضافة صفحة ثانية", writer.add_jpeg(fake, 100, 200) == 2)
    data = writer.build()
    check("PDF غير فارغ", len(data) > 300, len(data))
    check("ترويسة PDF", data.startswith(b"%PDF-1.4"))
    check("نهاية PDF", data.rstrip().endswith(b"%%EOF"))
    check("عدد الصفحات", b"/Count 2" in data)
    markers = re.findall(rb"startxref\s+(\d+)\s*%%EOF\s*$", data)
    check("وجود startxref", bool(markers))
    if markers:
        off = int(markers[-1])
        check("موضع xref صحيح", data[off:off + 4] == b"xref")
        entries = re.findall(rb"(\d{10}) (\d{5}) ([nf])", data[off:])
        good = True
        for i, entry in enumerate(entries):
            if entry[2] != b"n":
                continue
            offset = int(entry[0])
            if data[offset:offset + len(b"%d 0 obj" % i)] != (b"%d 0 obj" % i):
                good = False
        check("كل إزاحات xref صحيحة", good)
    check("PDF فارغ بلا صفحات", PdfWriter().build() == b"")
    check("SimplePdfWriter يعمل",
          SimplePdfWriter.build([{"jpeg": fake, "w": 10, "h": 20}]).startswith(b"%PDF"))
    check("SimplePdfWriter يتجاهل الفارغ", SimplePdfWriter.build([]) == b"")


def test_stats():
    section("الإحصائيات")
    from svcore.stats import StatsStore
    import datetime
    tmp = tempfile.mkdtemp(prefix="svstats_")
    store = StatsStore(tmp)
    base = datetime.datetime(2024, 5, 1, 10, 30)
    store.record("motion", 3, base)
    store.record("motion", 2, base)
    store.record("face", 1, base.replace(hour=11))
    hourly = store.hourly("motion", "2024-05-01")
    check("24 خانة", len(hourly) == 24)
    check("الساعة 10 فيها 5", hourly[10] == 5, hourly)
    check("ساعة الذروة", store.peak_hour("motion", "2024-05-01") == 10)
    check("لا بيانات = -1", store.peak_hour("motion", "1999-01-01") == -1)
    totals = store.totals_by_kind("2024-05-01")
    check("مجموع motion = 5", totals["motion"] == 5, totals)
    days = store.daily_totals("motion", 3)
    check("3 أيام", len(days) == 3)
    check("الأقدم أولاً", days[0][0] < days[-1][0])
    store.record("motion", 4)
    check("م.count اليوم", store.total_today("motion") == 4, store.counts_today())
    store2 = StatsStore(tmp)
    check("البيانات تبقى بعد إعادة التشغيل", store2.total_today("motion") == 4)
    path = store2.export_csv()
    check("تصدير CSV", bool(path) and os.path.isfile(path))
    with open(path, "r", encoding="utf-8") as f:
        head = f.readline().strip()
    check("ترويسة CSV", head.startswith("date,hour,kind,count"), head)


def test_autolock():
    section("القفل التلقائي")
    from svcore.autolock import AutoLockManager

    class FakeSettings(object):
        def __init__(self, data):
            self.data = data

        def get(self, key, default=None):
            return self.data.get(key, default)

    events = []
    mgr = AutoLockManager(FakeSettings({
        "autolock.enabled": True,
        "autolock.idle_seconds": 1,
        "autolock.recognize_only": True,
    }), on_event=events.append)
    t0 = 1000000.0
    ev = mgr.update(face_present=True, recognized=None, now=t0)
    check("بدء العد التنازلي", ev and ev["type"] == "countdown", ev)
    check("الحالة countdown", mgr.state == "countdown")
    check("الوقت المتبقي", mgr.seconds_left == 1, mgr.seconds_left)
    ev = mgr.update(face_present=False, recognized=None, now=t0 + 2)
    check("حدث القفل", ev and ev["type"] == "locked", ev)
    check("الحالة locked", mgr.is_locked)
    ev = mgr.update(face_present=True, recognized=["أحمد"], now=t0 + 3)
    check("حدث التعرف", ev and ev["type"] == "recognized", ev)
    check("الاسم في الحدث", ev and ev["name"] == "أحمد")
    check("on_event نُطق", len(events) >= 3, len(events))
    ok = mgr.lock_now()
    check("lock_now يعيد bool", isinstance(ok, bool))
    if os.name != "nt":
        check("lock_now يفشل بهدوء على لينكس", ok is False)
    mgr.reset()
    check("reset يرجع للوضع العادي", mgr.state == "idle")

    off = AutoLockManager(FakeSettings({"autolock.enabled": False}))
    check("معطّل لا يعيد أحداثاً", off.update(face_present=False, now=t0) is None)
    check("معطّل يبقى idle", off.state == "idle")

    # الوجه المجهول يُعامل كغياب عند recognize_only
    mgr2 = AutoLockManager(FakeSettings({
        "autolock.enabled": True, "autolock.idle_seconds": 5,
        "autolock.recognize_only": True}))
    ev = mgr2.update(face_present=True, recognized=[], now=t0)
    check("وجه مجهول = غياب", ev and ev["type"] == "countdown", ev)
    mgr3 = AutoLockManager(FakeSettings({
        "autolock.enabled": True, "autolock.idle_seconds": 5,
        "autolock.recognize_only": False}))
    ev = mgr3.update(face_present=True, recognized=[], now=t0)
    check("وجه مجهول مع تعطيل الصرامة = حضور", ev and ev["type"] == "presence", ev)


def test_telegram():
    section("تيليجرام")
    from svcore.telegram import TelegramBot, build_multipart, send_telegram
    fields = {"chat_id": "123456", "caption": "مرحبا"}
    files = [("photo", "photo.jpg", "image/jpeg", b"\xff\xd8\xff\xe0binary")]
    body, boundary = build_multipart(fields, files)
    sep = ("--" + boundary).encode("ascii")
    check("الجسم bytes", isinstance(body, bytes))
    check("يبدأ بالحد", body.startswith(sep + b"\r\n"))
    check("ينتهي بالحد الختامي", body.endswith(sep + b"--\r\n"))
    check("عدد الحدود", body.count(sep) == 4, body.count(sep))
    check("حقل chat_id", b'name="chat_id"' in body)
    check("اسم الملف", b'filename="photo.jpg"' in body)
    check("نوع المحتوى", b"Content-Type: image/jpeg" in body)
    check("بيانات الصورة", b"\xff\xd8\xff\xe0binary" in body)
    check("فاصل CRLF مزدوج", b"\r\n\r\n" in body)
    bot = TelegramBot("", "")
    check("غير مفعّل", bot.enabled is False)
    check("send_text يفشل بهدوء", bot.send_text("x")[0] is False)
    check("send_photo يفشل بهدوء", bot.send_photo(b"\xff\xd8")[0] is False)
    ok, msg = send_telegram("", "", "hello")
    check("send_telegram لا يرمي", ok is False and isinstance(msg, str))


def test_imports():
    section("استيراد الواجهة")
    try:
        from svcore import app          # noqa: F401
        from svcore import panels       # noqa: F401
        from svcore import theme        # noqa: F401
        from svcore import camera       # noqa: F401
        from svcore import vision       # noqa: F401
        check("كل الوحدات تُستورد", True)
    except Exception as e:
        check("كل الوحدات تُستورد", False, "%s: %s" % (type(e).__name__, e))
    try:
        from svcore import scanner, photobooth, pdfwriter, telegram, autolock, stats
        check("الوحدات الاختيارية تُستورد", True)
    except Exception as e:
        check("الوحدات الاختيارية تُستورد", False, str(e))
    try:
        from svcore.vision import M_MOTION, M_FACE, M_GESTURE, M_QR, M_COUNTER
        from svcore.vision import M_FACEID, M_DRAW, M_SLIDES, M_VOICE, M_ALL
        check("كل الأنماط معرّفة", True)
    except Exception as e:
        check("كل الأنماط معرّفة", False, str(e))


def main():
    print("Smart Vision - اختبارات ذاتية")
    for fn in (test_i18n, test_config, test_utils, test_counter, test_faceid,
               test_attendance, test_voice, test_textdraw, test_qr_engine,
               test_pdfwriter, test_stats, test_autolock, test_telegram,
               test_imports):
        try:
            fn()
        except Exception as e:
            import traceback
            # نطبع الـ traceback داخل سطر الفشل حتى لا يضيع في سجل CI
            check("استثناء في %s" % fn.__name__, False,
                  "\n" + traceback.format_exc())
    print("\n%d فحص - فشل: %d" % (CHECKS[0], len(FAILURES)))
    if FAILURES:
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("كل الاختبارات نجحت ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
