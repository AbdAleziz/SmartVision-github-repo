# -*- coding: utf-8 -*-
"""استوديو الصور (بوث الصور): فلاتر، زخارف، تمويه الوجوه، وحفظ النتائج."""

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

from .config import PHOTOBOOTH_DIR, ensure_dirs
from .utils import ensure_dir, safe_filename
from .utils import stamp as utils_stamp


# الفلاتر المتاحة في واجهة المستخدم
FILTERS = ("none", "bw", "sepia", "cool", "warm", "vignette")


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


def _add_stamp(image, text):
    """يضيف شريطًا أبيض أسفل الصورة ويكتب النص فوقه."""
    try:
        if cv2 is None or image is None:
            return image
        height, width = image.shape[:2]
        strip = max(22, int(height * 0.09))
        canvas = np.full((height + strip, width, 3), 255, dtype=np.uint8)
        canvas[:height, :width] = image
        scale = max(0.4, min(1.2, strip / 40.0))
        thickness = max(1, int(round(scale * 2)))
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        text_width = size[0][0] if size and size[0] else 0
        text_height = size[0][1] if size and size[0] else 10
        position = (max(6, (width - text_width) // 2),
                    height + int((strip + text_height) / 2))
        cv2.putText(canvas, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (30, 30, 30), thickness, cv2.LINE_AA)
        return canvas
    except Exception:
        return image


class PhotoBooth(object):
    """استوديو صور: فلاتر سريعة، تمويه وجوه، إطار زخرفي، وحفظ JPEG."""

    def __init__(self, out_dir=None):
        try:
            self.out_dir = str(out_dir) if out_dir else str(PHOTOBOOTH_DIR)
        except Exception:
            self.out_dir = "."
        try:
            ensure_dirs()
        except Exception:
            pass
        try:
            ensure_dir(self.out_dir)
        except Exception:
            pass

    def apply_filter(self, img, name="none"):
        """يطبّق الفلتر المطلوب ويعيد صورة جديدة."""
        try:
            if img is None:
                return None
            image = np.asarray(img)
            if image.size == 0:
                return None
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if cv2 is not None \
                    else np.repeat(image[:, :, None], 3, axis=2)
            key = str(name or "none").strip().lower()
            if key not in FILTERS:
                key = "none"

            if key == "none":
                return image.copy()

            if key == "bw":
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            source = image.astype(np.float32)
            if key == "sepia":
                # مصفوفة سيبيا الكلاسيكية بقنوات BGR
                blue = source[:, :, 0]
                green = source[:, :, 1]
                red = source[:, :, 2]
                out = np.empty_like(source)
                out[:, :, 0] = np.clip(0.131 * blue + 0.534 * green + 0.272 * red, 0, 255)
                out[:, :, 1] = np.clip(0.168 * blue + 0.686 * green + 0.349 * red, 0, 255)
                out[:, :, 2] = np.clip(0.189 * blue + 0.769 * green + 0.393 * red, 0, 255)
                return out.astype(np.uint8)

            if key in ("cool", "warm"):
                shifted = image.astype(np.int16)
                if key == "cool":
                    shifted[:, :, 0] += 20      # زيادة الأزرق
                    shifted[:, :, 2] -= 16      # 감소 الأحمر
                else:
                    shifted[:, :, 2] += 18      # زيادة الأحمر
                    shifted[:, :, 1] += 6       # زيادة الأصفر
                    shifted[:, :, 0] -= 12      # 감소 الأزرق
                return np.clip(shifted, 0, 255).astype(np.uint8)

            # vignette: تظليل الأطراف بتدرّج شعاعي مبني بـ numpy (بدون PIL)
            height, width = image.shape[:2]
            yy, xx = np.ogrid[0:height, 0:width]
            center_x = width * 0.5
            center_y = height * 0.5
            distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
            maximum = np.sqrt(center_x * center_x + center_y * center_y)
            factor = 1.0 - 0.45 * np.clip(distance / max(maximum, 1e-6), 0.0, 1.0) ** 2
            return np.clip(source * factor[:, :, None], 0, 255).astype(np.uint8)
        except Exception:
            try:
                return np.asarray(img).copy()
            except Exception:
                return None

    def blur_faces(self, img, faces=None):
        """يموّه الوجوه (x,y,w,h) بالبكسلنة؛ ويموّه الصورة كلّها إذا كانت None."""
        try:
            if img is None:
                return None
            image = np.asarray(img)
            if image.size == 0:
                return None
            result = image.copy()
            if faces is None:
                # لا توجد بيانات وجوه: نستخدم تمويهًا عام خفيف
                if cv2 is None:
                    return result
                return cv2.GaussianBlur(result, (5, 5), 0)
            height, width = result.shape[:2]
            for face in faces:
                try:
                    x, y, face_w, face_h = [int(value) for value in face[:4]]
                except Exception:
                    continue
                if face_w <= 0 or face_h <= 0:
                    continue
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(width, x + face_w)
                y2 = min(height, y + face_h)
                if x2 - x1 < 4 or y2 - y1 < 4:
                    continue
                region = result[y1:y2, x1:x2]
                tiny = cv2.resize(region,
                                   (max(1, (x2 - x1) // 10), max(1, (y2 - y1) // 10)),
                                   interpolation=cv2.INTER_AREA)
                pixelated = cv2.resize(tiny, (x2 - x1, y2 - y1),
                                       interpolation=cv2.INTER_NEAREST)
                result[y1:y2, x1:x2] = pixelated
            return result
        except Exception:
            try:
                return np.asarray(img).copy()
            except Exception:
                return None

    def add_frame(self, img, width=26):
        """يضيف إطارًا زخرفيًا متدرجًا مع زخارف الزوايا وخط داخلي رفيع."""
        try:
            if img is None:
                return None
            image = np.asarray(img)
            if image.size == 0:
                return None
            border = int(width) if width else 26
            if border < 1:
                return image.copy()
            height, image_width = image.shape[:2]
            total_h = height + 2 * border
            total_w = image_width + 2 * border
            if total_h <= 0 or total_w <= 0:
                return image.copy()
            yy, xx = np.ogrid[0:total_h, 0:total_w]
            mix = ((xx.astype(np.float32) / max(total_w - 1, 1)) +
                   (yy.astype(np.float32) / max(total_h - 1, 1))) * 0.5
            start_color = np.array([235.0, 190.0, 60.0], dtype=np.float32)
            end_color = np.array([80.0, 40.0, 150.0], dtype=np.float32)
            canvas = (start_color[None, None, :] * (1.0 - mix[:, :, None]) +
                      end_color[None, None, :] * mix[:, :, None])
            canvas = np.clip(canvas, 0, 255).astype(np.uint8)
            canvas[border:border + height, border:border + image_width] = image
            # خط رفيع داخلي يحدّد الصورة داخل الإطار
            cv2.rectangle(canvas, (border - 1, border - 1),
                          (border + image_width, border + height),
                          (255, 255, 255), 1)
            # زخارف دائرية في الزوايا الأربع
            accent = (250, 250, 250)
            radius = max(2, border // 2)
            cv2.circle(canvas, (border // 2, border // 2), radius, accent, -1)
            cv2.circle(canvas, (total_w - border // 2 - 1, border // 2), radius, accent, -1)
            cv2.circle(canvas, (total_w - border // 2 - 1, total_h - border // 2 - 1),
                       radius, accent, -1)
            cv2.circle(canvas, (border // 2, total_h - border // 2 - 1), radius, accent, -1)
            return canvas
        except Exception:
            try:
                return np.asarray(img).copy()
            except Exception:
                return None

    def make(self, frame, faces=None, filter_name="none", frame_on=True, blur=True,
             stamp=None):
        """فلتر ← تمويه ← إطار ← شريط الوقت، ويعيد {"ok","image","path"}.

        ملاحظة: هذه الدالة لا تكتب على القرص؛ استخدم save() afterwards.
        """
        try:
            if frame is None:
                return {"ok": False, "image": None, "path": ""}
            image = self.apply_filter(frame, filter_name)
            if image is None:
                return {"ok": False, "image": None, "path": ""}
            if blur:
                blurred = self.blur_faces(image, faces)
                if blurred is not None:
                    image = blurred
            if frame_on:
                decorated = self.add_frame(image)
                if decorated is None:
                    return {"ok": False, "image": None, "path": ""}
                image = decorated
            if stamp:
                image = _add_stamp(image, str(stamp))
            return {"ok": True, "image": image, "path": ""}
        except Exception:
            return {"ok": False, "image": None, "path": ""}

    def save(self, img, prefix="photo"):
        """يحفظ الصورة باسم prefix_YYYYMMDD_HHMMSS.jpg ويعيد المسار أو ""."""
        try:
            if cv2 is None or img is None:
                return ""
            try:
                ensure_dir(self.out_dir)
            except Exception:
                pass
            base = str(prefix) if prefix else "photo"
            name = "%s_%s.jpg" % (base, _timestamp())
            try:
                cleaned = safe_filename(name)
                if isinstance(cleaned, str) and cleaned:
                    name = cleaned
            except Exception:
                pass
            if not name.lower().endswith(".jpg"):
                name += ".jpg"
            path = os.path.join(self.out_dir, name)
            ok, buffer = cv2.imencode(".jpg", np.asarray(img))
            if not ok:
                return ""
            buffer.tofile(path)     # يعمل حتى لو احتوى المسار على حروف عربية
            return path
        except Exception:
            return ""
