# -*- coding: utf-8 -*-
"""
تتبّع اليد وتتبّع القلم الملوّن.

وحدة واحدة تخدم عدة وضعيات:
  - التحكم بالماوس باليد      (تتبّع جلد)
  - الرسم بالهوا              (تتبّع لون مشبع = قلم)
  - التحكم بالشرائح           (اتجاه حركة اليد)
  - إشارة اليد للصوت          (وضعية اليد: راحة/قبضة)

كل التتبّع يتم في فضاء HSV لأنه أكثر ثباتاً من RGB تحت تغيّر الإضاءة.
"""

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None


# مجال لون البشرة في HSV (نطاق واسع يغطي ألوان البشرة المختلفة)
SKIN_LOW = np.array([0, 40, 60], np.uint8)
SKIN_HIGH = np.array([25, 180, 255], np.uint8)
# مساحة أعرض للبشرة الداكنة أو الضوء الخافت
SKIN_LOW_DARK = np.array([0, 25, 30], np.uint8)
SKIN_HIGH_DARK = np.array([30, 255, 255], np.uint8)

MIN_BLOB_AREA = 1200          # أصغر مساحة تُعتبر يداً
PEN_MIN_AREA = 400            # أصغر مساحة تُعتبر قلماً

# عتبات وضعية اليد (نسبة مساحة الشكل إلى غلافه المحدّب)
FIST_RATIO = 0.86
OPEN_RATIO = 0.80


def _safe_hsv(frame):
    try:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    except Exception:
        return None


class BlobTracker(object):
    """متعقب عام: أكبر بقعة ملوّنة في قناع معيّن."""

    def __init__(self, min_area=MIN_BLOB_AREA, blur=7):
        self.min_area = min_area
        self.blur = blur
        self.mask = None
        self.last = None

    def _clean(self, mask):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask

    def detect(self, frame):
        """يعيد قاموس: found, cx, cy, area, bbox, solidity, mask."""
        empty = {"found": False, "cx": 0, "cy": 0, "area": 0, "bbox": None,
                 "solidity": 0.0, "mask": None}
        if cv2 is None or frame is None:
            return empty
        mask = self.build_mask(frame)
        if mask is None:
            return empty
        self.mask = mask
        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)[-2]
        if not contours:
            self.last = empty
            return empty
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < self.min_area:
            self.last = empty
            return empty
        m = cv2.moments(c)
        if m["m00"] == 0:
            self.last = empty
            return empty
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        x, y, w, h = cv2.boundingRect(c)
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = (area / hull_area) if hull_area > 0 else 0.0
        result = {"found": True, "cx": cx, "cy": cy, "area": float(area),
                  "bbox": (x, y, w, h), "solidity": float(solidity), "mask": mask}
        self.last = result
        return result

    def build_mask(self, frame):        # تُOverride فيâu الكلاسات الفرعية
        raise NotImplementedError


class SkinTracker(BlobTracker):
    """تتبّع اليد بلون البشرة (أو بلون معاير يدوياً)."""

    def __init__(self, min_area=MIN_BLOB_AREA):
        BlobTracker.__init__(self, min_area)
        self.hsv_range = None            # (low, high) عند المعايرة اليدوية

    def reset(self):
        self.hsv_range = None

    def calibrate(self, frame, x, y, patch=13):
        """يأخذ عيّنة حول النقطة (نقرة المستخدم) ويبني مجال HSV."""
        if cv2 is None or frame is None:
            return False
        h, w = frame.shape[:2]
        x0, x1 = max(0, x - patch), min(w, x + patch + 1)
        y0, y1 = max(0, y - patch), min(h, y + patch + 1)
        if x1 <= x0 or y1 <= y0:
            return False
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        patch_img = cv2.cvtColor(blurred[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        med = np.median(patch_img.reshape(-1, 3), axis=0)
        low = np.array([max(0, med[0] - 12), max(25, med[1] - 75),
                        max(30, med[2] - 75)], np.uint8)
        high = np.array([min(179, med[0] + 12), 255, 255], np.uint8)
        self.hsv_range = (low, high)
        return True

    def build_mask(self, frame):
        if cv2 is None:
            return None
        blurred = cv2.GaussianBlur(frame, (self.blur, self.blur), 0)
        hsv = _safe_hsv(blurred)
        if hsv is None:
            return None
        if self.hsv_range is not None:
            low, high = self.hsv_range
            mask = cv2.inRange(hsv, low, high)
        else:
            # دمج مجالَي البشرة الواسع والداكن حتى لا نضيع اليد الداكنة
            m1 = cv2.inRange(hsv, SKIN_LOW, SKIN_HIGH)
            m2 = cv2.inRange(hsv, SKIN_LOW_DARK, SKIN_HIGH_DARK)
            mask = cv2.bitwise_or(m1, m2)
        return self._clean(mask)


class ColorPenTracker(BlobTracker):
    """
    تتبّع قلم ملوّن (أي جسم مشبع اللون).

    في الوضع التلقائي نختار لوناً ساطعاً غير قريب من لون البشرة:
    نبني مدرّج التدرّج (hue histogram) ونختار القمة بعيدة عن نطاق البشرة.
    """

    def __init__(self, min_area=PEN_MIN_AREA):
        BlobTracker.__init__(self, min_area)
        self.hsv_range = None
        self.auto = True
        self.auto_range = None

    def reset(self):
        self.hsv_range = None
        self.auto_range = None

    def calibrate(self, frame, x, y, patch=11):
        """يعاير على لون القلم المحدد بالنقر."""
        if cv2 is None or frame is None:
            return False
        h, w = frame.shape[:2]
        x0, x1 = max(0, x - patch), min(w, x + patch + 1)
        y0, y1 = max(0, y - patch), min(h, y + patch + 1)
        if x1 <= x0 or y1 <= y0:
            return False
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        patch_img = cv2.cvtColor(blurred[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        med = np.median(patch_img.reshape(-1, 3), axis=0)
        low = np.array([max(0, med[0] - 14), max(90, med[1] - 90),
                        max(60, med[2] - 90)], np.uint8)
        high = np.array([min(179, med[0] + 14), 255, 255], np.uint8)
        self.hsv_range = (low, high)
        self.auto = False
        return True

    # ----- الوضع التلقائي: اكتشاف لون القلم نفسه -----
    def _detect_auto_range(self, hsv):
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        strong = (sat > 110) & (val > 70)
        if not strong.any():
            return None
        hues = hsv[:, :, 0][strong]
        weights = (sat[strong].astype(np.float32) *
                   val[strong].astype(np.float32) / 255.0)
        hist = np.zeros(180, np.float32)
        np.add.at(hist, hues, weights)
        # نستبعد نطاق البشرة (0..25 و 160..179) لنفضّل ألوان الأقلام
        hist[0:26] = 0
        hist[158:180] = 0
        idx = int(np.argmax(hist))
        if hist[idx] <= 0:
            return None
        # نبحث عن أفضل مركز附近的 (نجمع النطاق المحيط)
        best_score = -1.0
        best_center = idx
        for center in range(26, 158):
            lo = (center - 13) % 180
            hi = (center + 13) % 180
            if lo < hi:
                score = hist[lo:hi].sum()
            else:
                score = hist[lo:180].sum() + hist[0:hi].sum()
            if score > best_score:
                best_score = score
                best_center = center
        low = np.array([max(0, best_center - 14), 90, 60], np.uint8)
        high = np.array([min(179, best_center + 14), 255, 255], np.uint8)
        return (low, high)

    def build_mask(self, frame):
        if cv2 is None:
            return None
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = _safe_hsv(blurred)
        if hsv is None:
            return None
        if self.hsv_range is not None:
            low, high = self.hsv_range
            mask = cv2.inRange(hsv, low, high)
        else:
            if self.auto_range is None:
                self.auto_range = self._detect_auto_range(hsv)
            if self.auto_range is None:
                return None
            low, high = self.auto_range
            mask = cv2.inRange(hsv, low, high)
        return self._clean(mask)


# ---------------------------------------------------------------------------
# وضعية اليد
# ---------------------------------------------------------------------------
def hand_pose(result):
    """يحوّل نتيجة التتبّع إلى وضعية: 'fist' | 'open' | 'unknown'."""
    if not result or not result.get("found"):
        return "unknown"
    solidity = result.get("solidity", 0.0)
    if solidity >= FIST_RATIO:
        return "fist"
    if solidity <= OPEN_RATIO:
        return "open"
    return "unknown"


def draw_blob(out, result, color=(0, 220, 0), label=""):
    """يرسم البقعة المكتشفة على الإطار."""
    if cv2 is None or not result or not result.get("found"):
        return out
    x, y, w, h = result["bbox"]
    cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
    cv2.circle(out, (result["cx"], result["cy"]), 8, (0, 0, 255), -1)
    if label:
        cv2.putText(out, label, (x, max(15, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return out
