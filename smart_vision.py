# -*- coding: utf-8 -*-
"""
Smart Vision Studio
===================
تطبيق سطح مكتب يجمع أدوات الرؤية الذكية في شاشة واحدة (Python 3.8 + Windows 7):

  1) كشف الحركة            Motion Detection
  2) كشف الوجوه            Face Detection (Haar Cascade)
  3) التحكم بالماوس باليد  Gesture Control (تتبع لون + PyAutoGUI)
  4) قارئ QR والباركود     Barcode / QR Reader (محسّن: عدة أكواد + تدوير)
  5) عدّاد الأشخاص         People Counter (خط عبور يحدده المستخدم)
  6) التعرف على الوجوه     Face Recognition + سجل حضور Excel
  7) الرسم بالهوا           Draw in the Air (قلم ملوّن)
  8) التحكم بالشرائح       Slide Control (حركة اليد)
  9) القفل التلقائي        Auto Lock (Windows) مع إشعار تيليجرام
 10) ماسح المستندات        Document Scanner (تصحيح زاوية + PDF)
 11) بوث الصور             Photo Booth (عدّ تنازلي + فلاتر + تمويه وجه)
 12) لوحة الإحصائيات       Stats Dashboard (رسم بياني)
 13) ثيم فاتح/غامق + واجهة عربية/إنجليزية

المتطلبات (متوافقة مع Windows 7 و Python 3.8):
    pip install -r requirements.txt

ملاحظات:
  - الواجهة تعتمد على Tkinter القياسية (لا تحتاج Pillow ولا CustomTkinter).
  - PIL اختياري: بدونه تعمل كل الوظائف لكن معاينات الصور تُعرض كنص.
  - opencv-contrib-python اختياري: بدونه يعمل التعرف على الوجوه بالوضع
    البديل (أضعف دقة) وبدونه لا يعمل تيليجرام؟ (لا، تيليجرام مستقل).
  - لقراءة الباركود الخطي: pyzbar (يحتاج VC++ redistributable).
  - لتحويل البرنامج إلى EXE شغّل الملف build_exe.bat.
"""

import os
import sys
import traceback


def _crash(title, text):
    """يكتب الخطأ في crash.log بجانب البرنامج ويعرض نافذة، ثم ينتظر."""
    try:
        base = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                               else os.path.abspath(__file__))
        with open(os.path.join(base, "crash.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text[-1500:], title, 0x10)
    except Exception:
        pass
    try:
        print(text)
        input("Press Enter to close...")
    except UnicodeEncodeError:
        # مطبوعات ويندوز القديمة (cp1252) لا تقبل العربية
        try:
            print(text.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    except Exception:
        pass


def _ensure_path():
    """يضم مجلد البرنامج إلى مسار الاستيراد (مهم عند التشغيل من مجلد آخر)."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


if __name__ == "__main__":
    try:
        _ensure_path()
        from svcore.app import App
    except Exception:
        _crash("Smart Vision - import error", traceback.format_exc())
        sys.exit(1)

    try:
        App().mainloop()
    except Exception:              # آخر شبكة أمان: سجل الخطأ بدل الإغلاق بصمت
        _crash("Smart Vision - fatal error", traceback.format_exc())
        sys.exit(1)
