# -*- coding: utf-8 -*-
"""
Smart Vision Studio - النواة (svcore).

كل وحدة مسؤولة عن مهمة واحدة:
    config      الإعدادات والمسارات
    utils       أدوات مشتركة (CSV، ملفات، خيوط)
    i18n        الترجمة عربي/إنجليزي
    theme       ثيم فاتح/غامق
    camera      خيط الكاميرا
    vision      محرّك الرؤية (يجمع كل الخوارزميات)
    hand        تتبّع اليد والقلم
    qr_engine   قراءة الأكواد المحسّنة
    faceid      التعرف على الوجوه + الحضور
    counter     عدّاد الأشخاص
    telegram    إشعارات تيليجرام
    autolock    القفل التلقائي للويندوز
    scanner     ماسح المستندات
    photobooth  بوث الصور
    stats       الإحصائيات
    voice       التحكم الصوتي
    panels      لوحات التبويبات
    app         النافذة الرئيسية
"""

__version__ = "2.0.0"
__all__ = ["config", "utils", "i18n", "theme", "camera", "vision", "hand",
           "qr_engine", "faceid", "counter", "telegram", "autolock", "scanner",
           "photobooth", "stats", "voice", "panels", "app"]
