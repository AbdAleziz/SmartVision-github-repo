# -*- coding: utf-8 -*-
"""ماسح المستندات: اكتشاف حدود الورقة، تصحيح المنظور، التحسين، وحفظ PDF."""

import os
import re
import time

try:
    import numpy as np
except Exception:
    np = None

try:
    import cv2
except Exception:
    # التطبيق يجب أن يفتح حتى على جهاز بلا OpenCV
    cv2 = None

from .config import SCAN_DIR, ensure_dirs
from .pdfwriter import PdfWriter
from .utils import ensure_dir, safe_filename
from .utils import stamp as utils_stamp


def _timestamp():
    """يعيد طابعًا زمنيًا بصيغة YYYYMMDD_HHMMSS مع بديل آمن."""
    try:
        value = utils_stamp()
        if isinstance(value, str) and re.match(r"^\d{8}_\d{6}$", value):
            return value
    except Exception:
        pass
    try:
        return time.strftime("%Y%m%d_%H%M%S")
    except Exception:
        return "00000000_000000"


def _safe_int(value, default=0):
    try:
        number = int(value)
        if number > 0:
            return number
    except Exception:
        pass
    return default


def _order_corners(points):
    """يرتّب أربع نقاط بالترتيب: أعلى-يسار، أعلى-يمين، أسفل-يمين، أسفل-يسار."""
    result = np.zeros((4, 2), dtype=np.int32)
    try:
        arr = np.asarray(points, dtype=np.float32).reshape(-1, 2)
        if arr.shape[0] != 4:
            return result
        sums = arr[:, 0] + arr[:, 1]
        diffs = arr[:, 1] - arr[:, 0]
        indexes = [int(np.argmin(sums)), int(np.argmin(diffs)),
                   int(np.argmax(sums)), int(np.argmax(diffs))]
        if len(set(indexes)) != 4:
            # عند تصادم النقاط نستخدم ترتيب الزاوية حول مركز الشكل
            center = arr.mean(axis=0)
            angles = np.arctan2(arr[:, 1] - center[1], arr[:, 0] - center[0])
            order = [int(i) for i in np.argsort(angles)]
            start = int(np.argmin(sums))
            order = order[order.index(start):] + order[:order.index(start)]
            indexes = order
        for position in range(4):
            result[position] = np.round(arr[indexes[position]]).astype(np.int32)
        return result
    except Exception:
        return result


def _detect_corners(frame):
    """الخوارزمية الأساسية لاكتشاف زوايا الورقة داخل إطار الكاميرا."""
    if cv2 is None:
        return None
    try:
        if frame is None:
            return None
        image = np.asarray(frame)
        if image.size == 0 or image.ndim < 2:
            return None
        height, width = image.shape[:2]
        if height < 10 or width < 10:
            return None
        frame_area = float(height * width)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        # ندمج حواف Canny مع عتبة تكيّفية لتغطية الورق على خلفية فاتحة
        edges = cv2.Canny(blur, 50, 150)
        try:
            threshold = cv2.adaptiveThreshold(
                blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 21, 7)
            mask = cv2.bitwise_or(edges, threshold)
        except Exception:
            mask = edges
        # الإغلاق يملأ الفجوات بين حواف الورقة المتقطعة
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        found = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = found[-2] if len(found) == 2 else found[1]
        if not contours:
            return None
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 0.12 * frame_area:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            # نجرّب قيم epsilon متزايدة حتى نحصل على رباعي
            for factor in (0.02, 0.025, 0.03, 0.04, 0.05, 0.06):
                approx = cv2.approxPolyDP(contour, factor * perimeter, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    points = np.array(approx, dtype=np.float32).reshape(4, 2)
                    return _order_corners(points)
        return None
    except Exception:
        return None


def detect_document_corners(frame):
    """واجهة مستقلة لاكتشاف زوايا المستند تستخدمها واجهة التطبيق."""
    try:
        return _detect_corners(frame)
    except Exception:
        return None


class DocumentScanner(object):
    """ماسح مستندات: كشف الورقة، تصحيح المنظور، التحسين، وحفظ PDF."""

    def __init__(self, out_dir=None):
        try:
            self.out_dir = str(out_dir) if out_dir else str(SCAN_DIR)
        except Exception:
            self.out_dir = "."
        self._pages = []
        try:
            ensure_dirs()
        except Exception:
            pass
        try:
            ensure_dir(self.out_dir)
        except Exception:
            pass

    @property
    def pages(self):
        """قائمة صور الصفحات المخزنة (arrays BGR)."""
        try:
            return list(self._pages)
        except Exception:
            return []

    def detect_document(self, frame):
        """يعيد زوايا الورقة كـ array (4,2) int32 أو None عند الفشل."""
        try:
            return _detect_corners(frame)
        except Exception:
            return None

    def order_corners(self, pts):
        """يرتّب أربع نقاط إلى TL, TR, BR, BL ويعيد array (4,2) int32."""
        try:
            return _order_corners(pts)
        except Exception:
            return np.zeros((4, 2), dtype=np.int32)

    def warp(self, frame, corners, out_w=1240, out_h=1754):
        """يصحح المنظور ويعيد الصورة مستوية بإطار أبيض، أو None."""
        try:
            if cv2 is None or frame is None:
                return None
            source = np.asarray(corners, dtype=np.float32).reshape(4, 2)
            width = _safe_int(out_w, 1240)
            height = _safe_int(out_h, 1754)
            if width <= 0 or height <= 0:
                return None
            target = np.array([[0, 0], [width - 1, 0],
                               [width - 1, height - 1], [0, height - 1]],
                              dtype=np.float32)
            matrix = cv2.getPerspectiveTransform(source, target)
            result = cv2.warpPerspective(
                frame, matrix, (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255))
            if result is None:
                return None
            return result
        except Exception:
            return None

    def enhance(self, img):
        """يزيل الظلال ويحدّد التباين مع الحفاظ على الألوان."""
        try:
            if cv2 is None or img is None:
                return None
            image = np.asarray(img)
            if image.size == 0:
                return None
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            height, width = image.shape[:2]
            # تقدير الخلفية عبر تصغير + طمس قوي (سريع) ثم التقسيم عليه
            small = cv2.resize(image, (max(1, width // 16), max(1, height // 16)),
                               interpolation=cv2.INTER_AREA)
            background = cv2.GaussianBlur(small, (0, 0), 0)
            background = cv2.resize(background, (width, height),
                                    interpolation=cv2.INTER_LINEAR)
            # +1 لتجنّب القسمة على صفر
            background = np.clip(background.astype(np.int16) + 1, 0, 255).astype(np.uint8)
            flat = cv2.divide(image, background, scale=255)
            gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            sharp = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
            # دمج 70% لون + 30% تفاصيل رمادية حادة => ألوان kept وحواف واضحة
            return cv2.addWeighted(flat, 0.7, sharp, 0.3, 0)
        except Exception:
            return None

    def scan(self, frame):
        """ينفّذ الكشف والتصحيح والتحسين ويعيد نتيجة موحّدة."""
        try:
            corners = self.detect_document(frame)
            if corners is None:
                return {"ok": False, "corners": None, "image": None,
                        "reason": "لم يتم العثور على حدود المستند"}
            warped = self.warp(frame, corners)
            if warped is None:
                return {"ok": False, "corners": corners, "image": None,
                        "reason": "تعذر تصحيح المنظور"}
            enhanced = self.enhance(warped)
            if enhanced is None:
                enhanced = warped
            return {"ok": True, "corners": corners, "image": enhanced, "reason": ""}
        except Exception:
            return {"ok": False, "corners": None, "image": None,
                    "reason": "حدث خطأ غير متوقع أثناء المسح"}

    def add_page(self, img):
        """يخزّن صفحة جديدة ويعيد عدد الصفحات المخزنة."""
        try:
            if img is None:
                return len(self._pages)
            self._pages.append(np.array(img, copy=True))
            return len(self._pages)
        except Exception:
            return len(self._pages)

    def clear(self):
        """يحذف كل الصفحات المخزنة."""
        try:
            self._pages = []
        except Exception:
            pass

    def save_pdf(self, filename=None):
        """يحفظ الصفحات في PDF متعدد الصفحات ويعيد المسار الكامل أو ""."""
        try:
            if not self._pages:
                return ""
            name = str(filename) if filename else ("scan_%s.pdf" % _timestamp())
            try:
                cleaned = safe_filename(name)
                if isinstance(cleaned, str) and cleaned:
                    name = cleaned
            except Exception:
                pass
            if not name.lower().endswith(".pdf"):
                name += ".pdf"
            try:
                ensure_dir(self.out_dir)
            except Exception:
                pass
            path = os.path.join(self.out_dir, name)
            writer = PdfWriter()
            for page in self._pages:
                data = PdfWriter.encode_jpeg(page)
                if not data:
                    continue
                height, width = page.shape[:2]
                writer.add_jpeg(data, width, height)
            pdf = writer.build()
            if not pdf:
                return ""
            with open(path, "wb") as handle:
                handle.write(pdf)
            return path
        except Exception:
            return ""

    def save_png(self, img, filename=None):
        """يحفظ صورة PNG ويعيد المسار الكامل أو ""."""
        try:
            if cv2 is None or img is None:
                return ""
            name = str(filename) if filename else ("scan_%s.png" % _timestamp())
            try:
                cleaned = safe_filename(name)
                if isinstance(cleaned, str) and cleaned:
                    name = cleaned
            except Exception:
                pass
            if not name.lower().endswith(".png"):
                name += ".png"
            try:
                ensure_dir(self.out_dir)
            except Exception:
                pass
            path = os.path.join(self.out_dir, name)
            ok, buffer = cv2.imencode(".png", np.asarray(img))
            if not ok:
                return ""
            buffer.tofile(path)
            return path
        except Exception:
            return ""

    @staticmethod
    def jpeg_bytes(img):
        """يعيد بايتات JPEG للصورة (b"" عند الفشل أو غياب OpenCV)."""
        try:
            return PdfWriter.encode_jpeg(img)
        except Exception:
            return b""
