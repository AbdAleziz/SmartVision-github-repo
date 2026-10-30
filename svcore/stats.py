# -*- coding: utf-8 -*-
"""إحصائيات النشاط (تجميع ساعي/يومي) مع تصدير CSV و Excel.

لماذا هذا الملف؟
----------------
التطبيق يحتاج أرقاماً خفيفة تُحفظ بين الجلسات (كم حركة، كم وجه، كم
لقطة...) بدون قاعدة بيانات. الحل: ملف CSV واحد داخل مجلد الإحصائيات،
تُقرأ صفوفه في الذاكرة عند بدء التطبيق وتُضاف إليها صفوف جديدة.

مخطط الملف stats.csv:
    date,hour,kind,count
    2024-05-01,10,motion,5

(date = تاريخ محلي بصيغة ISO، hour = 0..23، kind = نوع الحدث، count = العدد)
"""

import csv
import datetime
import os
import threading

try:
    from .config import STATS_DIR
except Exception:
    # في حال تعذّر استيراد الإعدادات نستخدم مساراً احتياطياً
    STATS_DIR = os.path.join(os.path.expanduser("~"), "SmartVision", "stats")

try:
    from .utils import append_csv
except Exception:
    append_csv = None

try:
    from .utils import ensure_dir
except Exception:
    ensure_dir = None

try:
    from .utils import safe_filename
except Exception:
    safe_filename = None

try:
    from .utils import stamp
except Exception:
    stamp = None

try:
    import inspect as _inspect
    _APPEND_PARAMS = (list(_inspect.signature(append_csv).parameters.keys())
                      if append_csv is not None else [])
except Exception:
    _APPEND_PARAMS = []

__all__ = ["StatsStore", "EVENT_KINDS", "STATS_HEADER", "CSV_NAME"]

# أنواع الأحداث المدعومة
EVENT_KINDS = (
    "motion", "face", "unknown_face", "people_in", "people_out",
    "shot", "scan", "qr", "draw",
)
# ترويسة ملف الإحصائيات
STATS_HEADER = ["date", "hour", "kind", "count"]
CSV_NAME = "stats.csv"


def _ensure_dir(path):
    """ينشئ مجلداً إن لم يكن موجوداً."""
    try:
        if ensure_dir is not None:
            ensure_dir(path)
            return True
    except Exception:
        pass
    try:
        if path and not os.path.isdir(path):
            os.makedirs(path)
        return True
    except Exception:
        return False


def _safe_name(name):
    """اسم ملف آمن."""
    try:
        if safe_filename is not None:
            return safe_filename(name)
    except Exception:
        pass
    return name


def _stamp():
    """طابع زمني لاسم ملف التصدير."""
    if stamp is not None:
        try:
            value = stamp()
            if value:
                return "%s" % (value,)
        except Exception:
            pass
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class StatsStore(object):
    """مخزن إحصائيات مبني على ملف CSV واحد."""

    KINDS = EVENT_KINDS
    HEADER = STATS_HEADER
    FILENAME = CSV_NAME

    def __init__(self, stats_dir=None):
        try:
            self.dir = stats_dir or STATS_DIR
        except Exception:
            self.dir = os.path.join(os.getcwd(), "stats")
        self.dir = "%s" % (self.dir,)
        self.path = os.path.join(self.dir, self.FILENAME)
        self._data = {}          # {(date, hour, kind): count}
        self._lock = threading.RLock()
        self.last_error = ""
        _ensure_dir(self.dir)
        self._load()

    # ------------------- القراءة والكتابة -------------------
    def _load(self):
        """يقرأ الملف الموجود مسبقاً إلى الذاكرة (يبقى العدّ بعد إعادة التشغيل)."""
        try:
            if not os.path.isfile(self.path):
                return
            rows = []
            with open(self.path, "r", newline="", encoding="utf-8",
                      errors="replace") as handle:
                for row in csv.reader(handle):
                    if row:
                        rows.append(row)
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return
        for row in rows:
            if len(row) < 4:
                continue
            date_str = ("%s" % (row[0],)).strip().lstrip("\ufeff")
            kind = ("%s" % (row[2],)).strip()
            try:
                hour = int(row[1])
                count = int(row[3])
            except Exception:
                continue      # السطر الأول (الترويسة) يُتجاهل هنا
            if not date_str or not kind or hour < 0 or hour > 23:
                continue
            key = (date_str, hour, kind)
            self._data[key] = self._data.get(key, 0) + count

    def _append_args(self, row):
        """يبني قائمة الوسائط المناسبة لـ utils.append_csv حسب توقيعها."""
        params = list(_APPEND_PARAMS)
        if not params:
            return (self.path, row)
        args = [self.path]
        has_row = False
        for name in params[1:]:
            if name in ("row", "rows", "values", "record", "records", "data",
                        "cells", "line"):
                args.append(row)
                has_row = True
                break
            # أي وسيط آخر نعامله كترويسة أعمدة
            args.append(list(self.HEADER))
        if not has_row:
            args.append(row)
        return tuple(args)

    def _append_row(self, row):
        """يضيف صفاً واحداً إلى الملف."""
        with self._lock:
            if append_csv is not None:
                attempts = [self._append_args(row),
                            (self.path, list(self.HEADER), row)]
                for args in attempts:
                    try:
                        append_csv(*args)
                        return True
                    except TypeError:
                        continue      # توقيع مختلف → نجرّب صيغة أخرى
                    except Exception as exc:
                        self.last_error = "%s" % (exc,)
                        return False
            try:
                with open(self.path, "a", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerow(row)
                return True
            except Exception as exc:
                self.last_error = "%s" % (exc,)
                return False

    def _rewrite_file(self):
        """يعيد كتابة الملف كاملاً من الذاكرة."""
        rows = self._rows()
        tmp = "%s.tmp" % (self.path,)
        try:
            with open(tmp, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(self.HEADER)
                for row in rows:
                    writer.writerow(row)
            os.replace(tmp, self.path)
            return True
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False

    def _rows(self):
        """كل الصفوف مرتبة (تاريخ، ساعة، نوع)."""
        with self._lock:
            keys = sorted(self._data.keys())
            return [[key[0], key[1], key[2], self._data[key]] for key in keys]

    def record(self, kind, count=1, when=None):
        """يسجّل حدثاً.

        :param kind: نوع الحدث (motion/face/unknown_face/...).
        :param count: عدد الأحداث (عادةً 1).
        :param when: datetime أو طابع زمني؛ الافتراضي الآن.
        """
        try:
            kind = ("%s" % (kind or "",)).strip() or "unknown"
            count = self._as_int(count, 1)
            moment = self._to_datetime(when)
            date_str = moment.strftime("%Y-%m-%d")
            hour = int(moment.hour)
            with self._lock:
                key = (date_str, hour, kind)
                self._data[key] = self._data.get(key, 0) + count
            self._append_row([date_str, hour, kind, count])
        except Exception as exc:
            self.last_error = "%s" % (exc,)

    # ------------------- استعلامات -------------------
    def counts_today(self):
        """عدّاد كل الأنواع لليوم."""
        return self.totals_by_kind(datetime.date.today())

    def total_today(self, kind="motion"):
        """مجموع نوع واحد اليوم."""
        return self.counts_today().get(kind, 0)

    def hourly(self, kind="motion", date=None):
        """قائمة من 24 عنصراً (عدد الأحداث في كل ساعة)."""
        date_str = self._to_date_str(date)
        values = [0] * 24
        with self._lock:
            for key, count in self._data.items():
                if key[0] == date_str and key[2] == kind and 0 <= key[1] <= 23:
                    values[key[1]] += count
        return values

    def peak_hour(self, kind="motion", date=None):
        """ساعة الذروة (0..23) أو -1 إن لم توجد بيانات."""
        values = self.hourly(kind, date)
        best = -1
        best_value = 0
        for hour in range(24):
            if values[hour] > best_value:
                best_value = values[hour]
                best = hour
        return best

    def daily_totals(self, kind="motion", days=7):
        """[(date_str, count), ...] من الأقدم إلى الأحدث (يشمل الأيام الفارغة)."""
        try:
            days = int(days)
        except Exception:
            days = 7
        if days < 1:
            days = 1
        today = datetime.date.today()
        result = []
        with self._lock:
            for offset in range(days - 1, -1, -1):
                day = (today - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                total = 0
                for key, count in self._data.items():
                    if key[0] == day and key[2] == kind:
                        total += count
                result.append((day, total))
        return result

    def totals_by_kind(self, date=None):
        """مجموع كل الأنواع ليوم معيّن."""
        date_str = self._to_date_str(date)
        result = {}
        for name in self.KINDS:
            result[name] = 0
        with self._lock:
            for key, count in self._data.items():
                if key[0] == date_str:
                    result[key[2]] = result.get(key[2], 0) + count
        return result

    def clear(self, date=None):
        """يمسح بيانات يوم (أو اليوم الحالي) من الذاكرة ومن الملف."""
        try:
            date_str = self._to_date_str(date)
            with self._lock:
                for key in [k for k in list(self._data.keys()) if k[0] == date_str]:
                    del self._data[key]
                self._rewrite_file()
        except Exception as exc:
            self.last_error = "%s" % (exc,)

    # ------------------- التصدير -------------------
    def export_csv(self, path=None):
        """يصدّر كل البيانات إلى CSV ويعيد المسار ("" عند الفشل)."""
        try:
            target = path or self._default_export_path("csv")
            target = os.path.abspath(os.path.expanduser(target))
            folder = os.path.dirname(target)
            if folder:
                _ensure_dir(folder)
            with open(target, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(self.HEADER)
                for row in self._rows():
                    writer.writerow(row)
            return target
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            return ""

    def export_xlsx(self, path=None):
        """يصدّر إلى Excel (xlsx) عبر openpyxl.

        إن لم تكن openpyxl مثبّتة نُعيد "" ولا ننشئ أي ملف.
        """
        try:
            try:
                import openpyxl
            except Exception:
                self.last_error = "مكتبة openpyxl غير مثبّتة على هذا الجهاز"
                return ""
            target = path or self._default_export_path("xlsx")
            target = os.path.abspath(os.path.expanduser(target))
            folder = os.path.dirname(target)
            if folder:
                _ensure_dir(folder)

            book = openpyxl.Workbook()
            sheet = book.active
            sheet.title = "raw"
            sheet.append(list(self.HEADER))
            for row in self._rows():
                sheet.append(row)

            daily = book.create_sheet("daily")
            daily.append(["date", "kind", "count"])
            for day, totals in self._daily_by_kind():
                for kind, count in totals.items():
                    daily.append([day, kind, count])

            book.save(target)
            return target
        except Exception as exc:
            self.last_error = "%s" % (exc,)
            try:
                if path and os.path.isfile("%s" % (path,)):
                    os.remove("%s" % (path,))
            except Exception:
                pass
            return ""

    # ------------------- أدوات -------------------
    def _default_export_path(self, extension):
        name = _safe_name("stats_export_%s.%s" % (_stamp(), extension))
        return os.path.join(self.dir, name)

    def _daily_by_kind(self):
        """[(date_str, {kind: count}), ...] مرتبة بالتاريخ."""
        with self._lock:
            days = {}
            for key, count in self._data.items():
                bucket = days.setdefault(key[0], {})
                bucket[key[2]] = bucket.get(key[2], 0) + count
        return [(day, days[day]) for day in sorted(days.keys())]

    @staticmethod
    def _as_int(value, default=0):
        """يحوّل قيمة إلى int بهدوء."""
        try:
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return default

    @staticmethod
    def _to_datetime(when):
        """يحوّل when إلى datetime (يدعم datetime/date/رقم/نص)."""
        if when is None:
            return datetime.datetime.now()
        if isinstance(when, datetime.datetime):
            return when
        if isinstance(when, datetime.date):
            return datetime.datetime.combine(when, datetime.time())
        if isinstance(when, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(float(when))
            except Exception:
                return datetime.datetime.now()
        text = ("%s" % (when,)).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(text, fmt)
            except Exception:
                continue
        return datetime.datetime.now()

    @staticmethod
    def _to_date_str(date=None):
        """يحوّل تاريخاً إلى نص ISO YYYY-MM-DD."""
        if date is None:
            return datetime.date.today().strftime("%Y-%m-%d")
        if isinstance(date, datetime.datetime):
            return date.strftime("%Y-%m-%d")
        if isinstance(date, datetime.date):
            return date.strftime("%Y-%m-%d")
        text = ("%s" % (date,)).strip()
        if len(text) >= 10:
            text = text[:10]
        return text
