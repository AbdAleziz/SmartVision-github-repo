# -*- coding: utf-8 -*-
"""كاتب PDF متعدد الصفحات بلا أي مكتبات خارجية (بدون PIL / reportlab).

يبني ملف PDF صالح من صور JPEG جاهزة فقط، لأن التطبيق يعمل على أجهزة قديمة
لا يمكن تثبيت مكتبات جديدة عليها. كل كائنات PDF تُكتب يدويًا مع حساب
إزاحة (offset) كل كائن داخل الذاكرة النهائية، حتى يكون جدول xref صحيحًا
تفتحه كل برامج القراءة.
"""

import re

try:
    import cv2
except Exception:
    # بدون OpenCV يبقى الملف قابلًا للاستيراد
    cv2 = None


def _safe_int(value, default=0):
    """يحوّل القيمة إلى عدد صحيح موجب، أو يعيد الافتراضي عند الفشل."""
    try:
        number = int(value)
        if number > 0:
            return number
    except Exception:
        pass
    return default


def _pdf_number(value):
    """يحوّل الرقم إلى نص صالح داخل PDF بدون كسور عشرية زائدة."""
    try:
        number = float(value)
    except Exception:
        return "0"
    if abs(number - round(number)) < 0.000001:
        return "%d" % int(round(number))
    return ("%.4f" % number).rstrip("0").rstrip(".")


def _self_check(pdf, expect_objs=0):
    """فحص ذاتي سريع: ترويسة صحيحة، عدد الكائنات، وصحة كل إزاحة في xref."""
    try:
        data = bytes(pdf)
        if not data.startswith(b"%PDF-1.4"):
            return False
        if b"%%EOF" not in data[-64:]:
            return False
        markers = re.findall(rb"startxref\s+(\d+)\s*%%EOF\s*$", data)
        if not markers:
            return False
        xref_offset = int(markers[-1])
        if xref_offset <= 0 or xref_offset >= len(data):
            return False
        if data[xref_offset:xref_offset + 4] != b"xref":
            return False
        entries = re.findall(rb"(\d{10}) (\d{5}) ([nf])", data[xref_offset:])
        if not entries:
            return False
        used = 0
        for index in range(len(entries)):
            kind = entries[index][2]
            if kind != b"n":
                continue
            used += 1
            offset = int(entries[index][0])
            if offset <= 0 or offset >= len(data):
                return False
            # كل إزاحة يجب أن تشير فعلًا إلى بداية الكائن المقابل لها
            expected = b"%d 0 obj" % index
            if data[offset:offset + len(expected)] != expected:
                return False
        sizes = re.findall(rb"/Size\s+(\d+)", data[-512:])
        if not sizes:
            return False
        if int(sizes[-1]) != used + 1:
            return False
        if expect_objs and used != expect_objs:
            return False
        return True
    except Exception:
        return False


def _build_pdf(pages):
    """يبني بايتات PDF كاملة انطلاقًا من قائمة صفحات {"jpeg","w","h"}."""
    out = bytearray()
    offsets = {}

    def add_object(number, body):
        """يكتب كائنًا واحدًا ويحفظ إزاحته الحقيقية داخل المخزن المؤقت."""
        offsets[number] = len(out)
        out.extend(b"%d 0 obj\n" % number)
        out.extend(body)
        out.extend(b"\nendobj\n")

    out.extend(b"%PDF-1.4\n")
    # تعليق ثنائي يُعلم القارئ أن الملف يحتوي بيانات ثنائية (شرط PDF 1.4)
    out.extend(b"%\xe2\xe3\xcf\xd3\n")

    count = len(pages)
    total = 2 + 3 * count

    # 1 = الفهرس (Catalog) ، 2 = شجرة الصفحات (Pages)
    add_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = []
    for index in range(count):
        kids.append("%d 0 R" % (3 + 3 * index))
    pages_body = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                  % (" ".join(kids), count)).encode("ascii")
    add_object(2, pages_body)

    for index in range(count):
        page = pages[index]
        jpeg = page.get("jpeg") or b""
        width = _safe_int(page.get("w"), 1240)
        height = _safe_int(page.get("h"), 1754)
        # لكل صفحة ثلاثة كائنات: الصفحة + المحتوى + الصورة
        page_number = 3 + 3 * index
        content_number = page_number + 1
        image_number = page_number + 2

        page_body = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %s %s] "
            "/Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>"
            % (_pdf_number(width), _pdf_number(height), image_number, content_number)
        ).encode("ascii")
        add_object(page_number, page_body)

        # مصفوفة التحويل تمدّ الصورة على كامل الصفحة
        content = ("q\n%s 0 0 %s 0 0 cm\n/Im0 Do\nQ\n"
                   % (_pdf_number(width), _pdf_number(height))).encode("ascii")
        content_body = (b"<< /Length " + ("%d" % len(content)).encode("ascii")
                        + b" >>\nstream\n" + content + b"endstream")
        add_object(content_number, content_body)

        # DCTDecode تعني أن بيانات JPEG تُدرج كما هي دون إعادة ترميز
        image_header = (
            "<< /Type /XObject /Subtype /Image /Width %s /Height %s "
            "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
            "/Length %d >>\nstream\n"
            % (_pdf_number(width), _pdf_number(height), len(jpeg))
        ).encode("ascii")
        add_object(image_number, image_header + jpeg + b"\nendstream")

    xref_offset = len(out)
    out.extend(b"xref\n")
    out.extend(("0 %d\n" % total).encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for number in range(1, total + 1):
        out.extend(("%010d %05d n \n" % (offsets.get(number, 0), 0)).encode("ascii"))
    out.extend(b"trailer\n")
    out.extend(("<< /Size %d /Root 1 0 R >>\n" % (total + 1)).encode("ascii"))
    out.extend(b"startxref\n")
    out.extend(("%d\n" % xref_offset).encode("ascii"))
    out.extend(b"%%EOF\n")
    return bytes(out)


class PdfWriter(object):
    """كاتب PDF متعدد الصفحات يستقبل صور JPEG الخام فقط."""

    def __init__(self, pages_w=1240, pages_h=1754):
        self.pages_w = _safe_int(pages_w, 1240)
        self.pages_h = _safe_int(pages_h, 1754)
        self._pages = []

    def add_jpeg(self, jpeg_bytes, width, height):
        """يضيف صفحة من بايتات JPEG ويعيد رقم الصفحة (يبدأ من 1)."""
        try:
            if not jpeg_bytes:
                return 0
            page = {
                "jpeg": bytes(jpeg_bytes),
                "w": _safe_int(width, self.pages_w) or self.pages_w,
                "h": _safe_int(height, self.pages_h) or self.pages_h,
            }
            self._pages.append(page)
            return len(self._pages)
        except Exception:
            return 0

    def build(self):
        """يعيد بايتات ملف PDF كامل، أو b"" عند أي فشل (لا يرفع استثناءات)."""
        try:
            if not self._pages:
                return b""
            data = _build_pdf(self._pages)
            # لا نسلّم ملفًا غير صحيح إلى واجهة المستخدم
            if not _self_check(data, 2 + 3 * len(self._pages)):
                return b""
            return data
        except Exception:
            return b""

    @staticmethod
    def encode_jpeg(img_bgr):
        """يحوّل صورة numpy إلى بايتات JPEG (b"" عند غياب OpenCV أو الفشل)."""
        try:
            if cv2 is None or img_bgr is None:
                return b""
            ok, buffer = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ok or buffer is None:
                return b""
            return bytes(buffer.tobytes())
        except Exception:
            return b""


class SimplePdfWriter(object):
    """واجهة مختصرة: تبني PDF من قائمة صفحات جاهزة {"jpeg","w","h"}."""

    @staticmethod
    def build(pages):
        """يعيد بايتات PDF، أو b"" عند الفشل أو غياب الصفحات."""
        try:
            items = []
            for page in (pages or []):
                try:
                    jpeg = page.get("jpeg")
                except Exception:
                    continue
                if not jpeg:
                    continue
                items.append({
                    "jpeg": bytes(jpeg),
                    "w": _safe_int(page.get("w"), 1240),
                    "h": _safe_int(page.get("h"), 1754),
                })
            if not items:
                return b""
            data = _build_pdf(items)
            if not _self_check(data, 2 + 3 * len(items)):
                return b""
            return data
        except Exception:
            return b""
