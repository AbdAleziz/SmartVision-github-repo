# -*- coding: utf-8 -*-
"""
تحويل إطارات OpenCV إلى صور Tkinter بدون Pillow.

نستخدم صيغة PPM مباشرة لأن Tk 8.6 يقرأها أصلاً، فلا نضيف أي مكتبة جديدة.
إن توفّرت Pillow نستعملها لأنها أسرع في تحجيم الصور الكبيرة.
"""

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

try:
    import tkinter as tk
except Exception:          # pragma: no cover
    tk = None

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False


def scale(frame, max_w=None, max_h=None):
    """يصغّر الإطار مع الحفاظ على النسبة."""
    if frame is None or cv2 is None:
        return None
    try:
        h, w = frame.shape[:2]
        if max_w and max_h:
            ratio = min(float(max_w) / w, float(max_h) / h)
        elif max_w:
            ratio = float(max_w) / w
        elif max_h:
            ratio = float(max_h) / h
        else:
            ratio = 1.0
        if ratio < 1.0:
            frame = cv2.resize(frame, (int(w * ratio), int(h * ratio)),
                               interpolation=cv2.INTER_AREA)
        return frame
    except Exception:
        return frame


def to_photo(frame, max_w=None, max_h=None):
    """يعيد (tk.PhotoImage, width, height) أو (None, 0, 0) عند الفشل."""
    if frame is None or cv2 is None or tk is None:
        return None, 0, 0
    frame = scale(frame, max_w, max_h)
    if frame is None:
        return None, 0, 0
    try:
        if HAS_PIL:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            return ImageTk.PhotoImage(pil), pil.width, pil.height
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        header = b"P6\n%d %d\n255\n" % (w, h)
        photo = tk.PhotoImage(data=header + rgb.tobytes(), format="PPM")
        return photo, w, h
    except Exception:
        return None, 0, 0


def show_on(label, frame, max_w=None, max_h=None):
    """يعرض إطاراً داخل Tk Label (يحتفظ بمرجع الصورة)."""
    photo, w, h = to_photo(frame, max_w, max_h)
    if photo is None:
        label.config(image="", text="")
        return False
    label._photo_ref = photo          # مرجع ضروري حتى لا تحذف الصورة
    label.config(image=photo, text="")
    return True
