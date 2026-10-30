# -*- coding: utf-8 -*-
"""رسم النصوص فوق الفيديو (يدعم العربية إن توفّرت PIL).

OpenCV's putText لا يدعم الحروف العربية إطلاقاً، لذلك:
  1. إن توفّرت Pillow نرسم النص بخط TrueType.
  2. إن لم تتوفّر، نحاول تشكيل العربية يدوياً (forms) ثم نرسمها بـ putText.
  3. إن فشل كل شيء، نعرض الاسم بحروف لاتينية (transliteration مبسّط).
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
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# تشكيل العربية (مبسّط: أشكال الحروف + لام-ألف)
# ---------------------------------------------------------------------------
_ARABIC_FORMS = {
    u"ء": (u"ء", u"ء"),
    u"آ": (u"آ", u"آ"),
    u"أ": (u"أ", u"أ"),
    u"إ": (u"إ", u"إ"),
    u"ؤ": (u"ؤ", u"ؤ"),
    u"ئ": (u"ئ", u"ئ"),
    u"ا": (u"ا", u"ا"),
    u"ب": (u"ﺑ", u"ﺐ"),
    u"ة": (u"ﺓ", u"ﺔ"),
    u"ت": (u"ﺗ", u"ﺘ"),
    u"ث": (u"ﺛ", u"ﺜ"),
    u"ج": (u"ﺟ", u"ﺠ"),
    u"ح": (u"ﺣ", u"ﺤ"),
    u"خ": (u"ﺧ", u"ﺨ"),
    u"د": (u"ﺩ", u"ﺪ"),
    u"ذ": (u"ﺫ", u"ﺬ"),
    u"ر": (u"ﺭ", u"ﺮ"),
    u"ز": (u"ﺯ", u"ﺰ"),
    u"س": (u"ﺳ", u"ﺴ"),
    u"ش": (u"ﺷ", u"ﺸ"),
    u"ص": (u"ﺻ", u"ﺼ"),
    u"ض": (u"ﺿ", u"ﻀ"),
    u"ط": (u"ﻃ", u"ﻄ"),
    u"ظ": (u"ﻅ", u"ﻆ"),
    u"ع": (u"ﻋ", u"ﻌ"),
    u"غ": (u"ﻍ", u"ﻎ"),
    u"ف": (u"ﻑ", u"ﻒ"),
    u"ق": (u"ﻕ", u"ﻖ"),
    u"ك": (u"ﻙ", u"ﻚ"),
    u"ل": (u"ﻝ", u"ﻞ"),
    u"م": (u"ﻡ", u"ﻢ"),
    u"ن": (u"ﻥ", u"ﻦ"),
    u"ه": (u"ﻩ", u"ﻪ"),
    u"و": (u"ﻭ", u"ﻮ"),
    u"ى": (u"ﻯ", u"ﻰ"),
    u"ي": (u"ﻱ", u"ﻲ"),
    u"ة ": (u"ة", u"ة"),
}

_LAM_ALEF = {
    u"لا": u"ﻻ",
    u"لآ": u"ﻷ",
    u"لأ": u"ﻹ",
    u"لإ": u"ﻻ",
}

_ARABIC_RANGE = (u"ؠ", u"ي")


def _is_arabic(ch):
    return _ARABIC_RANGE[0] <= ch <= _ARABIC_RANGE[1]


def shape_arabic(text):
    """يحوّل النص العربي إلى صورته المتصلة (Presenter Forms) تقريباً."""
    if not text:
        return text
    try:
        chars = list(text)
        out = []
        n = len(chars)
        for i, ch in enumerate(chars):
            if ch == u"ل" and i + 1 < n and chars[i + 1] in _LAM_ALEF:
                out.append(_LAM_ALEF[chars[i + 1]])
                out.append(None)      # علامة لتفادي تكرار الألف
                continue
            if ch in _ARABIC_FORMS:
                prev_is_letter = i > 0 and _is_arabic(chars[i - 1]) and chars[i - 1] != u" "
                next_is_letter = (i + 1 < n and _is_arabic(chars[i + 1])
                                  and not (chars[i + 1] == u"ا" and i + 2 < n
                                           and chars[i + 2] == u" "))
                if not _is_arabic(ch):
                    pass
                elif prev_is_letter and next_is_letter:
                    out.append(_ARABIC_FORMS[ch][0])      # وسط
                elif prev_is_letter:
                    out.append(_ARABIC_FORMS[ch][1])      # آخر
                else:
                    out.append(_ARABIC_FORMS[ch][0])      # أول
            else:
                out.append(ch)
        cleaned = []
        for item in out:
            if item is None:
                continue
            cleaned.append(item)
        # ترتيب من اليمين لليسار (putText يرسم من اليسار لليمين)
        return u"".join(cleaned)[::-1]
    except Exception:
        return text


_TRANSLIT = {
    u"ا": "a", u"أ": "a", u"إ": "i", u"آ": "a", u"ب": "b", u"ت": "t", u"ث": "th",
    u"ج": "j", u"ح": "h", u"خ": "kh", u"د": "d", u"ذ": "z", u"ر": "r", u"ز": "z",
    u"س": "s", u"ش": "sh", u"ص": "s", u"ض": "d", u"ط": "t", u"ظ": "z", u"ع": "a",
    u"غ": "gh", u"ف": "f", u"ق": "q", u"ك": "k", u"ل": "l", u"م": "m", u"ن": "n",
    u"ه": "h", u"و": "w", u"ي": "y", u"ى": "a", u"ة": "h", u"ء": "", u"ؤ": "u",
    u"ئ": "i", u"ھ": "h", u" ": " ",
}


def to_latin(text):
    """ترجمة مبسّطة للأسماء العربية لتُعرض فوق الوجه عند غياب PIL."""
    out = []
    for ch in text or "":
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("?")
    return u"".join(out).strip()


# ---------------------------------------------------------------------------
# الرسم
# ---------------------------------------------------------------------------
def _find_font(size):
    if not HAS_PIL:
        return None
    candidates = [
        "arial.ttf", "arialbd.ttf", "segoeui.ttf", "tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return None


def draw_text(img, text, org, color=(255, 255, 255), scale=0.6, thickness=2,
              bg=None, mirror=False):
    """يرسم نصاً فوق صورة OpenCV (BGR).

    org = (x, y) لنقطةBaseline الأفقية.
    mirror = True نحتاجه للنص العربي (يُرسم من اليمين لليسار).
    """
    if cv2 is None or not text:
        return img
    text = str(text)
    has_arabic = any(_is_arabic(c) for c in text)

    if HAS_PIL:
        try:
            return _draw_with_pil(img, text, org, color, scale, bg, mirror, has_arabic)
        except Exception:
            pass

    # بديل: putText مع تشكيل عربي مبسّط
    try:
        if has_arabic:
            text = shape_arabic(text)
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), base = cv2.getTextSize(text, font, scale, thickness)
        x, y = org
        if bg is not None:
            cv2.rectangle(img, (x - 2, y - th - base + 2), (x + tw + 2, y + base), bg, -1)
        cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)
        return img
    except Exception:
        return img


def _draw_with_pil(img, text, org, color, scale, bg, mirror, has_arabic):
    # تحويل صورة OpenCV إلى PIL
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    size = max(10, int(22 * scale / 0.6))
    font = _find_font(size)
    if font is None:
        raise RuntimeError("no font")
    draw = ImageDraw.Draw(pil)
    x, y = org
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if has_arabic:
        # Pillow بدون raqm لا يوصل الحروف، لذا نستخدم التشكيل المبسّط
        text = shape_arabic(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    if bg is not None:
        draw.rectangle([x - 3, y - th - 4, x + tw + 3, y + 4], fill=(bg[2], bg[1], bg[0]))
    draw.text((x, y - th - 2), text, font=font, fill=(color[2], color[1], color[0]))
    out = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return out


def draw_label(img, text, x, y, color=(255, 255, 255), scale=0.55,
               thickness=2, bg=(0, 0, 0)):
    """يرسم تسمية فوق مستطيل (أسفل يمين المستطيل عادةً)."""
    if cv2 is None or not text:
        return img
    has_arabic = any(_is_arabic(c) for c in text)
    shown = text
    if not HAS_PIL and has_arabic:
        shown = to_latin(text)          # putText لا يرسم العربية
    try:
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), base = cv2.getTextSize(shown, font, scale, thickness)
        if has_arabic and HAS_PIL:
            x = max(0, x - tw)
        cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y + base), bg, -1)
        cv2.putText(img, shown, (x + 3, y + base - 3), font, scale, color, thickness,
                    cv2.LINE_AA)
    except Exception:
        pass
    return img
