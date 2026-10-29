# -*- coding: utf-8 -*-
"""الترجمة العربية / الإنجليزية.

كل نص في الواجهة يمر من هنا عبر  t("key")  حتى نبدّل اللغة بضغطة زر.
اللغة الافتراضية العربية، والاتجاه من اليمين لليسار عند العربية.
"""

AR = "ar"
EN = "en"

STRINGS = {
    # ------------------------------------------------------------------ عام
    "app.title": ("ستوديو الرؤية الذكية", "Smart Vision Studio"),
    "app.subtitle": ("ستوديو", "Studio"),
    "app.ready": ("جاهز.", "Ready."),
    "app.language": ("اللغة", "Language"),
    "app.theme": ("الثيم", "Theme"),
    "app.theme.dark": ("غامق", "Dark"),
    "app.theme.light": ("فاتح", "Light"),
    "app.camera": ("الكاميرا", "Camera"),
    "app.device_index": ("رقم الكاميرا", "Device index"),
    "app.start_camera": ("تشغيل الكاميرا", "Start Camera"),
    "app.stop_camera": ("إيقاف الكاميرا", "Stop Camera"),
    "app.opening_camera": ("جارٍ فتح الكاميرا %d ...", "Opening camera %d ..."),
    "app.camera_running": ("الكاميرا تعمل.", "Camera running."),
    "app.camera_off": ("الكاميرا مغلقة\nاضغط «تشغيل الكاميرا» أو اختر نمطاً",
                       "Camera is off\nPress Start Camera or pick a mode"),
    "app.live": ("مباشر", "LIVE"),
    "app.offline": ("متوقف", "OFFLINE"),
    "app.status": ("الحالة", "Status"),
    "app.log": ("السجل", "Log"),
    "app.close": ("إغلاق", "Close"),
    "app.cancel": ("إلغاء", "Cancel"),
    "app.save": ("حفظ", "Save"),
    "app.open": ("فتح", "Open"),
    "app.reset": ("تصفير", "Reset"),
    "app.apply": ("تطبيق", "Apply"),
    "app.copy": ("نسخ", "Copy"),
    "app.clear": ("مسح", "Clear"),
    "app.copied": ("تم النسخ إلى الحافظة.", "Copied to clipboard."),
    "app.nothing_to_copy": ("لا يوجد ما يُنسخ.", "Nothing to copy."),
    "app.saved_to": ("تم الحفظ في %s", "Saved to %s"),
    "app.error": ("خطأ", "Error"),
    "app.ok": ("تم", "OK"),
    "app.yes": ("نعم", "Yes"),
    "app.no": ("لا", "No"),
    "app.on": ("مفعّل", "ON"),
    "app.off": ("معطّل", "OFF"),
    "app.enabled": ("مفعّل", "Enabled"),
    "app.disabled": ("معطّل", "Disabled"),

    # -------------------------------------------------------------- الأنماط
    "modes.title": ("الأنماط", "Modes"),
    "mode.motion": ("كشف الحركة", "Motion Detection"),
    "mode.face": ("كشف الوجوه", "Face Detection"),
    "mode.gesture": ("التحكم بالماوس باليد", "Gesture Mouse Control"),
    "mode.qr": ("قراءة QR والباركود", "QR / Barcode Reader"),
    "mode.counter": ("عدّاد الأشخاص", "People Counter"),
    "mode.faceid": ("التعرف على الوجوه", "Face Recognition"),
    "mode.draw": ("الرسم بالهوا", "Draw in the Air"),
    "mode.slides": ("التحكم بالشرائح", "Slide Control"),
    "mode.voice": ("إشارة اليد للصوت", "Hand Signal to Voice"),
    "mode.all": ("النمط الشامل", "All-in-One"),
    "mode.off": ("النمط متوقف.", "Mode off."),
    "mode.active": ("النمط يعمل.", "Mode active."),
    "mode.gesture_help": ("اضغط على يدك داخل الفيديو لمعايرة اللون. "
                          "حرّك الماوس الحقيقي إلى الزاوية العلوية للإيقاف.",
                          "Click your hand in the video to calibrate the color. "
                          "Move the real mouse to the top-left corner to stop."),
    "mode.qr_help": ("قراءة QR فقط (ثبّت pyzbar لقراءة الباركود الخطي).",
                     "QR only (install pyzbar for 1D barcodes)."),
    "mode.counter_help": ("اضغط على الفيديو لرسم خط العبور، ثم يت counted الدخول والخروج.",
                           "Click in the video to set the crossing line, then people "
                           "are counted as they cross it."),
    "mode.faceid_help": ("سجّل وجوهك من تبويب «التعرف على الوجوه» ثم شغّل النمط.",
                          "Register your faces in the Face ID tab, then start this mode."),
    "mode.draw_help": ("حرّك قلم ملوّن أمام الكاميرا للرسم. احفظ الرسم أو امسحه.",
                       "Move a colored pen in front of the camera to draw. Save or clear."),

    # -------------------------------------------------------------- الإعدادات
    "settings.title": ("الإعدادات", "Settings"),
    "settings.motion_sensitivity": ("حساسية الحركة (أعلى = أقل حساسية)",
                                     "Motion sensitivity (higher = less sensitive)"),
    "settings.fist_click": ("نقرة بإغلاق القبضة", "Fist click (close hand = click)"),
    "settings.save_snapshots": ("حفظ لقطات الحركة تلقائياً", "Save motion snapshots"),
    "settings.reset_hand_color": ("إعادة ضبط لون اليد", "Reset hand color"),
    "settings.deps": ("pyzbar: %s | PyAutoGUI: %s | FaceID: %s",
                      "pyzbar: %s | PyAutoGUI: %s | FaceID: %s"),

    # ----------------------------------------------------------- تيليجرام
    "telegram.title": ("إشعارات تيليجرام", "Telegram notifications"),
    "telegram.enable": ("تفعيل الإشعارات", "Enable notifications"),
    "telegram.token": ("توكن البوت", "Bot token"),
    "telegram.chat_id": ("Chat ID", "Chat ID"),
    "telegram.test": ("إرسال رسالة اختبار", "Send test message"),
    "telegram.test_ok": ("وصلت رسالة تيليجرام ✅", "Telegram test message delivered"),
    "telegram.test_fail": ("فشل إرسال تيليجرام: %s", "Telegram send failed: %s"),
    "telegram.hint": ("توكن البوت من @BotFather، و Chat ID من @userinfobot.",
                      "Bot token from @BotFather, Chat ID from @userinfobot."),
    "telegram.notify_motion": ("عند اكتشاف حركة", "On motion detected"),
    "telegram.notify_unknown_face": ("عند وجه غير معروف", "On unknown face"),
    "telegram.notify_attendance": ("عند تسجيل حضور/انصراف", "On attendance entry"),
    "telegram.notify_count": ("عند تغيّر عدّاد الأشخاص", "On people counter change"),

    # --------------------------------------------------------- القفل التلقائي
    "autolock.title": ("القفل التلقائي للجهاز", "Automatic device lock"),
    "autolock.enable": ("تفعيل القفل عند غيابك", "Lock when nobody is in front"),
    "autolock.idle_seconds": ("ثواني الغياب قبل القفل", "Seconds away before locking"),
    "autolock.recognize_only": ("افتح فقط للوجه المسجّل", "Unlock only for known faces"),
    "autolock.auto_type": ("كتابة كلمة المرور تلقائياً عند التعرف",
                            "Type the password automatically when recognized"),
    "autolock.password": ("كلمة مرور ويندوز", "Windows password"),
    "autolock.warning": ("تحذير: تخزين كلمة المرور محلياً خطر أمني. "
                         "اتركها فارغة واستعمل «إشعار فقط».",
                         "Warning: storing a password locally is a security risk. "
                         "Leave it empty and use notify-only."),
    "autolock.lock_now": ("اقفل الآن", "Lock now"),
    "autolock.locked": ("تم قفل الجهاز.", "Device locked."),
    "autolock.unlock_detected": ("تعرف على %s — تم إشعارك.", "Recognized %s — you were notified."),
    "autolock.presence_ok": ("ما زال والدك أمام الكاميرا.", "Still present in front of the camera."),
    "autolock.absent": ("لا يوجد وجه — سيُقفل الجهاز خلال %d ثانية.",
                        "No face detected — locking in %d seconds."),

    # ------------------------------------------------------------- الواجهة
    "tabs.live": ("المعاهدة", "Live"),
    "tabs.counter": ("العدّاد", "Counter"),
    "tabs.faceid": ("التعرف على الوجوه", "Face ID"),
    "tabs.scanner": ("الماسح", "Scanner"),
    "tabs.photobooth": ("بوث الصور", "Photo Booth"),
    "tabs.stats": ("الإحصائيات", "Stats"),
    "tabs.draw": ("الرسم", "Drawing"),
    "tabs.settings": ("الإعدادات", "Settings"),

    # ------------------------------------------------------------- العدّاد
    "counter.title": ("عدّاد الأشخاص", "People counter"),
    "counter.hint": ("اضغط داخل الفيديو نقرتين لتحديد خط العبور.",
                     "Click twice inside the video to set the crossing line."),
    "counter.in": ("دخول", "IN"),
    "counter.out": ("خروج", "OUT"),
    "counter.current": ("داخل الآن", "Inside now"),
    "counter.reset": ("تصفير العدّاد", "Reset counter"),
    "counter.log": ("سجل الأحداث", "Event log"),
    "counter.line_saved": ("تم ضبط خط العبور.", "Crossing line saved."),
    "counter.enter": ("دخول: %s", "Entered: %s"),
    "counter.exit": ("خروج: %s", "Left: %s"),

    # -------------------------------------------------------- التعرف على الوجوه
    "faceid.title": ("التعرف على الوجوه وسجل الحضور", "Face recognition & attendance"),
    "faceid.enroll": ("تسجيل وجه جديد", "Register a new face"),
    "faceid.enroll_hint": ("اكتب اسم الشخص ثم اضغط «تسجيل» — تبقى أمام الكاميرا "
                           "لثوانٍ حتى تُلتقط العينات.",
                           "Type the person's name then press Register — stay in front "
                           "of the camera for a few seconds."),
    "faceid.name": ("الاسم", "Name"),
    "faceid.threshold": ("حساسية التعرّف", "Match threshold"),
    "faceid.known_faces": ("الوجوه المسجّلة", "Registered faces"),
    "faceid.delete": ("حذف", "Delete"),
    "faceid.attendance": ("سجل الحضور", "Attendance log"),
    "faceid.export_csv": ("تصدير CSV", "Export CSV"),
    "faceid.export_xlsx": ("تصدير Excel", "Export Excel"),
    "faceid.open_folder": ("فتح مجلد البيانات", "Open data folder"),
    "faceid.enroll_ok": ("تم تسجيل %s (%d عينة).", "Registered %s (%d samples)."),
    "faceid.enroll_fail": ("لم يتم التقاط عينات كافية للوجه.", "Not enough face samples captured."),
    "faceid.deleted": ("تم حذف %s.", "Deleted %s."),
    "faceid.deleted_msg": ("حذف %s وكل صوره؟", "Delete %s and all its photos?"),
    "faceid.attendance_ok": ("تم تسجيل الحضور: %s", "Attendance recorded: %s"),
    "faceid.unknown": ("وجه غير معروف", "Unknown face"),
    "faceid.no_faces": ("لا يوجد وجه مسجّل بعد.", "No registered faces yet."),
    "faceid.model_missing": ("النموذج غير موجود — سجّل وجهاً واحداً على الأقل.",
                             "Model missing — register at least one face."),

    # --------------------------------------------------------------- الماسح
    "scanner.title": ("ماسح المستندات", "Document scanner"),
    "scanner.hint": ("ضع الورقة أمام الكاميرا ثم اضغط «التقط وصحّح».",
                     "Put the page in front of the camera then press Capture & fix."),
    "scanner.capture": ("التقط وصحّح", "Capture & fix"),
    "scanner.save_pdf": ("احفظ PDF", "Save PDF"),
    "scanner.pages": ("الصفحات الملتقطة: %d", "Pages captured: %d"),
    "scanner.no_page": ("لم يتم العثور على حواف الورقة. جرّب إضاءة أفضل أو "
                        "حطّ الورقة على خلفية داكنة.",
                        "No page edges found. Try better lighting or a dark background."),
    "scanner.pdf_ok": ("تم حفظ الملف %s", "PDF saved: %s"),
    "scanner.open_folder": ("فتح مجلد المسح", "Open scans folder"),

    # ----------------------------------------------------------- بوث الصور
    "photobooth.title": ("نمط بوث الصور", "Photo booth"),
    "photobooth.filter": ("الفلتر", "Filter"),
    "photobooth.f.none": ("بدون", "None"),
    "photobooth.f.bw": ("أبيض وأسود", "B&W"),
    "photobooth.f.sepia": ("سيبيا", "Sepia"),
    "photobooth.f.cool": ("بارد", "Cool"),
    "photobooth.f.warm": ("دافئ", "Warm"),
    "photobooth.f.vignette": ("إطار داكن", "Vignette"),
    "photobooth.frame": ("إطار زخرفي", "Decorative frame"),
    "photobooth.blur": ("تمويه الوجه للخصوصية", "Blur faces for privacy"),
    "photobooth.shoot": ("التقط صورة", "Take photo"),
    "photobooth.countdown": ("3 - 2 - 1", "3 - 2 - 1"),
    "photobooth.shot_ok": ("تم حفظ الصورة %s", "Photo saved: %s"),
    "photobooth.open_folder": ("فتح مجلد الصور", "Open photos folder"),

    # ---------------------------------------------------------- الإحصائيات
    "stats.title": ("لوحة الإحصائيات", "Statistics dashboard"),
    "stats.today_motions": ("حركات اليوم", "Motions today"),
    "stats.peak_hour": ("أكثر ساعة نشاطاً", "Busiest hour"),
    "stats.today_events": ("أحداث اليوم", "Events today"),
    "stats.people_today": ("دخول/خروج اليوم", "People in/out today"),
    "stats.hourly": ("الحركات حسب الساعة", "Motions by hour"),
    "stats.week": ("آخر 7 أيام", "Last 7 days"),
    "stats.no_data": ("لا توجد بيانات بعد — شغّل الكاميرا أولاً.",
                      "No data yet — start the camera first."),
    "stats.excel": ("تصدير Excel", "Export Excel"),

    # ------------------------------------------------------------- الرسم
    "draw.title": ("الرسم بالهوا", "Draw in the air"),
    "draw.hint": ("وجّه قلماً ملوّناً أمام الكاميرا. احفظ الرسم كصورة.",
                  "Point a colored pen at the camera. Save the drawing as an image."),
    "draw.clear": ("امسح الرسم", "Clear drawing"),
    "draw.save": ("احفظ الرسم", "Save drawing"),
    "draw.saved": ("تم حفظ الرسم %s", "Drawing saved: %s"),
    "draw.no_pen": ("لم يتم العثور على قلم ملوّن.", "No colored pen detected."),
    "draw.open_folder": ("فتح مجلد الرسومات", "Open drawings folder"),

    # ----------------------------------------------------------- الشرائح
    "slides.title": ("التحكم بالشرائح", "Slide control"),
    "slides.hint": ("حرّك يدك يميناً ويساراً قلب الشرائح (Page Down / Page Up).",
                    "Move your hand left and right to flip slides (Page Down / Page Up)."),
    "slides.next": ("الشريحة التالية", "Next slide"),
    "slides.prev": ("الشريحة السابقة", "Previous slide"),
    "slides.swiped": ("انتقال: %s", "Slide: %s"),

    # ------------------------------------------------------------- الصوت
    "voice.title": ("التحكم بالصوت بإشارة اليد", "Voice control by hand signal"),
    "voice.hint": ("ارفع يدك (أو الإشارة المختارة) لبدء الإدخال الصوتي.",
                   "Raise your hand (or the selected gesture) to start voice input."),
    "voice.listening": ("أستمع الآن...", "Listening..."),
    "voice.command": ("الأمر: %s", "Command: %s"),
    "voice.executed": ("تم تنفيذ: %s", "Executed: %s"),
    "voice.unknown_cmd": ("أمر غير معروف: %s", "Unknown command: %s"),
    "voice.trigger": ("الإشارة", "Trigger"),
    "voice.g.palm": ("راحة اليد", "Open palm"),
    "voice.g.fist": ("القبضة", "Fist"),
    "voice.g.point": ("الإشارة", "Pointing"),

    # ---------------------------------------------------------- أكواد QR
    "qr.title": ("قراءة QR والباركود", "QR & barcode reader"),
    "qr.hint": ("وجّه الكاميرا نحو الكود. تُقرأ عدة أكواد في نفس الإطار.",
                "Point the camera at the code. Multiple codes per frame are supported."),
    "qr.decoded": ("تم قراءة الكود", "Code decoded"),
    "qr.copied": ("تم نسخ محتوى الكود.", "Code content copied."),
    "qr.open_link": ("فتح الرابط", "Open link"),
    "qr.scan_image": ("مسح ملف صورة", "Scan an image file"),
    "qr.no_codes": ("لم يُقرأ أي كود.", "No code decoded."),
    "qr.history": ("سجل الأكواد", "Code history"),
    "qr.open_csv": ("فتح سجل CSV", "Open CSV log"),

    # -------------------------------------------------------------- رسائل
    "msg.camera_error": ("لا يمكن فتح الكاميرا %d. تحقق من الكابل أو الرقم "
                         "أو أن برنامجاً آخر يستخدمها.",
                         "Cannot open camera %d. Check the USB cable, the index, "
                         "or whether another program is using it."),
    "msg.camera_lost": ("انقطع الاتصال بالكاميرا.", "Camera connection lost."),
    "msg.face_cascade_missing": ("ملف haarcascade_frontalface_default.xml غير موجود. "
                                 "ضعه بجانب البرنامج.", "Face cascade file "
                                 "(haarcascade_frontalface_default.xml) was not found. "
                                 "Put it next to this script."),
    "msg.csv_open": ("ملف CSV مفتوح في برنامج آخر - أغلقه للاستمرار في التسجيل.",
                     "CSV is open in another program - close it to keep logging."),
    "msg.unknown_face": ("وجه غير معروف", "Unknown face"),
    "msg.motion": ("حركة مكتشفة", "Motion detected"),
}

# رسائل نظام (لا تُترجم: أسماء أخطاء)
SYSTEM_MESSAGES = {}


def t(key, lang="ar", **kwargs):
    """يرجم المفتاح ويعيد النص المنسّق.

    كل مدخل في STRINGS زوج: (النص العربي، النص الإنجليزي).
    """
    entry = STRINGS.get(key)
    if entry is None:
        return key
    if isinstance(entry, (tuple, list)):
        index = 0 if lang == AR else 1
        text = entry[index] if index < len(entry) else entry[0]
    else:
        text = entry
    if kwargs:
        try:
            return text % kwargs
        except Exception:
            try:
                # نص مثل "%d" مع قيمة واحدة: % tuple من القيم
                return text % tuple(kwargs.values())
            except Exception:
                return text
    return text


def is_rtl(lang):
    return lang == AR


def available_langs():
    return (AR, EN)
