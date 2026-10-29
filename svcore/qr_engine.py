# -*- coding: utf-8 -*-
"""
محرك قراءة الأكواد (QR + باركود) — نسخة محسّنة.

التحسينات مقارنة بالنسخة السابقة:
  1. قراءة عدة أكواد في نفس الإطار (QRDetectorMulti + pyzbar).
  2. تدوير الصورة 90/180/270 عند فشل القراءة (الكود مقلوب أو جانبي).
  3. محاولات تحسين الصورة: تكبير ×2، تباين تكيّفي، CLAHE.
  4. كشف الأكواد من ملفات الصور (وليس من الكاميرا فقط).
  5. كتم التكرار: نفس الكود لا يُسجَّل مرتين خلال نافذة زمنية.
  6. تعرّف على الروابط (http/https) لتسهيل الفتح.
  7. دعم WeChatQRCode إن توفّرت (opencv-contrib) بدون أخطاء إن لم تتوفّر.
"""

import os
import time

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except Exception:
    pyzbar = None
    HAS_PYZBAR = False

# دعم WeChatQRCode (openCV contrib 4.5.2+): متعدد الأكواد ودقيق جداً
WEAT_CHAT = None
if cv2 is not None:
    try:
        if hasattr(cv2, "wechat_qrcode"):
            WEAT_CHAT = cv2.wechat_qrcode_WeChatQRCode()
    except Exception:
        WEAT_CHAT = None


def _norm_points(pts):
    """يحوّل نقاط أي شكل (N,1,2) إلى قائمة (x, y)."""
    try:
        arr = np.array(pts).reshape(-1, 2)
        return [(int(p[0]), int(p[1])) for p in arr]
    except Exception:
        return []


class CodeEngine(object):
    """يقرأ الأكواد من إطارات الكاميرا ومن ملفات الصور."""

    def __init__(self, dedupe_seconds=3.0):
        self.dedupe_seconds = dedupe_seconds
        self.detector = cv2.QRCodeDetector() if cv2 is not None else None
        self.frame_count = 0
        self.recent = {}                 # text -> آخر وقت ظهور
        self.has_pyzbar = HAS_PYZBAR
        self.has_wechat = WEAT_CHAT is not None

    # ------------------------------------------------------------------ عام
    def is_new(self, text, now=None):
        """هل هذا النص جديد (لم يُرَ خلال نافذة التكرار)؟"""
        now = time.time() if now is None else now
        last = self.recent.get(text, 0.0)
        if now - last >= self.dedupe_seconds:
            self.recent[text] = now
            return True
        self.recent[text] = last
        return False

    @staticmethod
    def is_url(text):
        low = (text or "").strip().lower()
        return low.startswith("http://") or low.startswith("https://")

    # ------------------------------------------------------- المحاولات الأساسية
    def _decode_qr(self, image):
        """محاولة قراءة QR (متعدد + مفرد). تعيد قائمة أكواد."""
        found = []
        if self.detector is None or image is None:
            return found

        # 1) عدة أكواد
        try:
            res = self.detector.detectAndDecodeMulti(image)
            if res and len(res) >= 3 and res[0]:
                info = res[1]
                points = res[2]
                if info is not None and points is not None:
                    n = min(len(info), len(points))
                    for i in range(n):
                        text = info[i]
                        if text:
                            found.append({"text": text, "kind": "QRCODE",
                                          "points": _norm_points(points[i])})
        except Exception:
            pass

        # 2) كود واحد
        if not found:
            try:
                text, points, _ = self.detector.detectAndDecode(image)
                if text and points is not None:
                    found.append({"text": text, "kind": "QRCODE",
                                  "points": _norm_points(points)})
            except Exception:
                pass
        return found

    def _decode_barcodes(self, image):
        """قراءة الباركود (كل الأنواع) عبر pyzbar إن توفّر."""
        found = []
        if not HAS_PYZBAR or image is None:
            return found
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            for obj in pyzbar.decode(gray):
                try:
                    text = obj.data.decode("utf-8", errors="replace")
                except Exception:
                    text = str(obj.data)
                found.append({"text": text, "kind": str(obj.type),
                              "points": [(int(p.x), int(p.y)) for p in obj.polygon]})
        except Exception:
            pass
        return found

    def _decode_wechat(self, image):
        """WeChatQRCode اختياري (يتطلب opencv-contrib)."""
        found = []
        if WEAT_CHAT is None or image is None:
            return found
        try:
            res, points = WEAT_CHAT.detectAndDecode(image)
            if res and points is not None:
                for i, text in enumerate(res):
                    if text:
                        pts = _norm_points(points[i]) if i < len(points) else []
                        found.append({"text": text, "kind": "QRCODE", "points": pts})
        except Exception:
            pass
        return found

    # --------------------------------------------------------- تحسين الصور
    @staticmethod
    def _variants(image):
        """نسخ محسّنة من الإطار تُجرَّب عند فشل القراءة الأولى."""
        out = []
        if cv2 is None or image is None:
            return out
        try:
            h, w = image.shape[:2]
            big = cv2.resize(image, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            out.append(big)
        except Exception:
            pass
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
            out.append(cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR))
        except Exception:
            pass
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            binimg = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 31, 5)
            out.append(cv2.cvtColor(binimg, cv2.COLOR_GRAY2BGR))
        except Exception:
            pass
        return out

    @staticmethod
    def _rotations(image):
        """نسخ مُدوّرة 90 و180 و270 درجة."""
        out = []
        if cv2 is None or image is None:
            return out
        try:
            out.append(cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE))
            out.append(cv2.rotate(image, cv2.ROTATE_180))
            out.append(cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE))
        except Exception:
            pass
        return out

    # -------------------------------------------------------------- الواجهة
    def scan(self, frame, deep_every=3):
        """يقرأ كل الأكواد الظاهرة في الإطار ويعيد قائمة قواميس."""
        self.frame_count += 1
        results = []
        if frame is None or cv2 is None:
            return results

        # المسار السريع: قراءة مباشرة
        codes = self._decode_qr(frame)
        if not codes and HAS_PYZBAR:
            codes = self._decode_barcodes(frame)

        # المسار العميق (كل عدة إطارات): محاولات إضافية
        if not codes and (self.frame_count % max(1, deep_every) == 0):
            for variant in self._variants(frame):
                codes = self._decode_qr(variant)
                if codes:
                    break
                if HAS_PYZBAR:
                    codes = self._decode_barcodes(variant)
                    if codes:
                        break
            if not codes:
                for rot in self._rotations(frame):
                    codes = self._decode_qr(rot)
                    if codes:
                        break
                    if HAS_PYZBAR:
                        codes = self._decode_barcodes(rot)
                        if codes:
                            break
            if not codes and self.has_wechat:
                codes = self._decode_wechat(frame)

        seen = set()
        for c in codes:
            text = c.get("text") or ""
            if not text or text in seen:
                continue
            seen.add(text)
            pts = c.get("points") or []
            if pts:
                cx = int(sum(p[0] for p in pts) / len(pts))
                cy = int(sum(p[1] for p in pts) / len(pts))
            else:
                h, w = frame.shape[:2]
                cx, cy = w // 2, h // 2
            c["center"] = (cx, cy)
            c["is_url"] = self.is_url(text)
            c["is_new"] = self.is_new(text)
            results.append(c)
        return results

    def scan_file(self, path):
        """يقرأ الأكواد من ملف صورة على القرص."""
        results = []
        if cv2 is None or not path or not os.path.isfile(path):
            return results
        try:
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8),
                                 cv2.IMREAD_COLOR)
        except Exception:
            image = None
        if image is None:
            try:
                image = cv2.imread(path, cv2.IMREAD_COLOR)
            except Exception:
                image = None
        if image is None:
            return results

        codes = self._decode_qr(image)
        if not codes and HAS_PYZBAR:
            codes = self._decode_barcodes(image)
        if not codes:
            for variant in self._variants(image):
                codes = self._decode_qr(variant)
                if not codes and HAS_PYZBAR:
                    codes = self._decode_barcodes(variant)
                if codes:
                    break
        if not codes:
            for rot in self._rotations(image):
                codes = self._decode_qr(rot)
                if codes:
                    break

        h, w = image.shape[:2]
        for c in codes:
            pts = c.get("points") or []
            if pts:
                c["center"] = (int(sum(p[0] for p in pts) / len(pts)),
                               int(sum(p[1] for p in pts) / len(pts)))
            else:
                c["center"] = (w // 2, h // 2)
            c["is_url"] = self.is_url(c.get("text", ""))
            c["is_new"] = True
            results.append(c)
        return results

    # ------------------------------------------------------------- الرسم
    @staticmethod
    def draw(out, codes):
        """يرسم حدود الأكواد على الإطار."""
        if cv2 is None or not codes:
            return out
        for c in codes:
            pts = c.get("points") or []
            if len(pts) >= 2:
                arr = np.array(pts, np.int32).reshape(-1, 1, 2)
                cv2.polylines(out, [arr], True, (255, 140, 0), 3)
            cx, cy = c.get("center", (0, 0))
            label = c.get("kind", "CODE")
            cv2.putText(out, label, (cx - 20, max(15, cy - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 140, 0), 2)
        return out
