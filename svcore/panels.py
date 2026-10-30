# -*- coding: utf-8 -*-
"""
لوحات التبويبات (Tabs): العدّاد، التعرف على الوجوه، الماسح، بوث الصور،
الإحصائيات، الرسم، الإعدادات.

كل لوحة تبني عناصرها بنفسها وتستدعي app.t() للترجمة، فتكفي تغيير اللغة
أو الثيم بإعادة بناء الواجهة كلها.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from .config import (CAPTURE_DIR, DATA_DIR, DRAW_DIR, FACES_DIR, LOG_DIR,
                     MODELS_DIR, PHOTOBOOTH_DIR, SCAN_DIR)
from .utils import open_with_default_app


class PanelBase(tk.Frame):
    """لوحة أساسية: تبني نفسها وتُحدَّث دورياً."""

    def __init__(self, app, parent):
        tk.Frame.__init__(self, parent, bg=app.theme.bg)
        self.app = app
        self.build()

    # ----- اختصارات -----
    def t(self, key, **kwargs):
        return self.app.t(key, **kwargs)

    @property
    def theme(self):
        return self.app.theme

    # ----- نقاط التوسعة -----
    def build(self):
        pass

    def refresh(self):
        """تُستدعى كل ~500ms لتحديث الأرقام."""

    def card(self, parent=None, title=""):
        """يعيد بطاقة (Frame) بعنوان."""
        parent = parent or self
        box = tk.Frame(parent, bg=self.theme.card)
        if title:
            tk.Label(box, text=title, bg=self.theme.card, fg=self.theme.text,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        return box

    def button(self, parent, text, command, bg=None, fg=None, width=None):
        th = self.theme
        bg = bg or th.btn
        fg = fg or th.text
        btn = tk.Button(parent, text=text, bg=bg, fg=fg, relief=tk.FLAT,
                        activebackground=th.btn_h, activeforeground=fg,
                        font=("Segoe UI", 9, "bold"), command=command,
                        cursor="hand2", bd=0, highlightthickness=0)
        if width:
            btn.configure(width=width)
        btn.bind("<Enter>", lambda e: btn.config(bg=th.btn_h))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn


# ===========================================================================
# تبويب العدّاد
# ===========================================================================
class CounterPanel(PanelBase):
    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("counter.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("counter.reset"), self.reset).pack(side=tk.RIGHT)

        tk.Label(self, text=self.t("counter.hint"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9), wraplength=640, justify="left"
                 ).pack(anchor="w", padx=12, pady=(6, 0))

        # بطاقتا الأرقام
        row = tk.Frame(self, bg=th.bg)
        row.pack(fill=tk.X, padx=12, pady=12)
        self.in_var = tk.StringVar(value="0")
        self.out_var = tk.StringVar(value="0")
        self.inside_var = tk.StringVar(value="0")
        for title, var, color in (("counter.in", self.in_var, th.ok),
                                  ("counter.out", self.out_var, th.danger),
                                  ("counter.current", self.inside_var, th.accent)):
            box = tk.Frame(row, bg=th.card, width=190, height=92)
            box.pack(side=tk.LEFT, padx=(0, 10))
            box.pack_propagate(False)
            tk.Label(box, text=self.t(title), bg=th.card, fg=th.muted,
                     font=("Segoe UI", 9)).pack(pady=(10, 0))
            tk.Label(box, textvariable=var, bg=th.card, fg=color,
                     font=("Segoe UI", 26, "bold")).pack()

        # سجل الأحداث
        tk.Label(self, text=self.t("counter.log"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
        text_frame = tk.Frame(self, bg=th.card)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
        self.log = tk.Text(text_frame, height=8, bg=th.card, fg=th.text, bd=0,
                           insertbackground=th.text, relief=tk.FLAT, wrap="word",
                           font=("Consolas", 9), padx=10, pady=8,
                           highlightthickness=0)
        scroll = ttk.Scrollbar(text_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def reset(self):
        self.app.counter.reset()
        self.app.set_status(self.t("counter.reset"))

    def add_event(self, text):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def refresh(self):
        counts = self.app.counter.counts
        self.in_var.set(str(counts["in"]))
        self.out_var.set(str(counts["out"]))
        self.inside_var.set(str(self.app.counter.inside))


# ===========================================================================
# تبويب التعرف على الوجوه
# ===========================================================================
class FaceIDPanel(PanelBase):
    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("faceid.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("faceid.export_csv"),
                    lambda: self.app.export_attendance("csv")).pack(side=tk.RIGHT, padx=(0, 6))
        self.button(top, self.t("faceid.export_xlsx"),
                    lambda: self.app.export_attendance("xlsx")).pack(side=tk.RIGHT, padx=(0, 6))
        self.button(top, self.t("faceid.open_folder"),
                    lambda: open_with_default_app(DATA_DIR)).pack(side=tk.RIGHT)

        tk.Label(self, text=self.t("faceid.enroll_hint"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9), wraplength=640, justify="left"
                 ).pack(anchor="w", padx=12, pady=(6, 0))

        # التسجيل
        enroll = tk.Frame(self, bg=th.card)
        enroll.pack(fill=tk.X, padx=12, pady=(8, 10))
        tk.Label(enroll, text=self.t("faceid.name"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(12, 6))
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(enroll, textvariable=self.name_var, width=26,
                                   bg=th.input_bg, fg=th.text, insertbackground=th.text,
                                   bd=0, highlightthickness=1, highlightbackground=th.border,
                                   highlightcolor=th.accent, font=("Segoe UI", 10))
        self.name_entry.pack(side=tk.LEFT, ipady=4)
        self.button(enroll, self.t("faceid.enroll"), self.start_enroll,
                    bg=th.accent, fg="white").pack(side=tk.LEFT, padx=8)
        self.enroll_status = tk.StringVar(value="")
        tk.Label(enroll, textvariable=self.enroll_status, bg=th.card, fg=th.muted,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(4, 12))

        # حساسية التعرّف (مسافة LBPH): أصغر = أدق وأصرم
        thr = tk.Frame(enroll, bg=th.card)
        thr.pack(side=tk.RIGHT, padx=(0, 12))
        tk.Label(thr, text=self.t("faceid.threshold"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 6))
        self.threshold_var = tk.IntVar(
            value=int(self.app.settings.get("faceid.threshold", 72)))
        self.threshold_box = tk.Spinbox(thr, from_=30, to=160, increment=2, width=5,
                                        textvariable=self.threshold_var,
                                        bg=th.input_bg, fg=th.text, bd=0,
                                        highlightthickness=1,
                                        highlightbackground=th.border,
                                        highlightcolor=th.accent,
                                        font=("Segoe UI", 9))
        self.threshold_box.pack(side=tk.LEFT)
        self.button(thr, self.t("app.apply"), self.save_threshold).pack(
            side=tk.LEFT, padx=(6, 0))

        # الوجوه المسجّلة
        left = tk.Frame(self, bg=th.bg)
        left.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        right = tk.Frame(left, bg=th.bg)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(left, text=self.t("faceid.known_faces"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tree_frame = tk.Frame(left, bg=th.card)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.tree = ttk.Treeview(tree_frame, columns=("name", "samples"),
                                  show="headings", height=6, style="Treeview")
        self.tree.heading("name", text=self.t("faceid.name"))
        self.tree.heading("samples", text="Samples")
        self.tree.column("name", width=150)
        self.tree.column("samples", width=70, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        tk.Label(right, text=self.t("faceid.attendance"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        att_frame = tk.Frame(right, bg=th.card)
        att_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.att = ttk.Treeview(att_frame, columns=("time", "name", "event", "dur"),
                                 show="headings", height=10, style="Treeview")
        for col, label in (("time", "Time"), ("name", self.t("faceid.name")),
                           ("event", "Event"), ("dur", "Minutes")):
            self.att.heading(col, text=label)
        self.att.column("time", width=80)
        self.att.column("name", width=140)
        self.att.column("event", width=70, anchor="center")
        self.att.column("dur", width=70, anchor="center")
        self.att.pack(fill=tk.BOTH, expand=True)
        self.reload_people()

    # ----- الإجراءات -----
    def save_threshold(self):
        try:
            value = int(self.threshold_var.get())
        except Exception:
            return
        self.app.settings.set("faceid.threshold", value)
        self.app.settings.save()
        if self.app.face_db is not None:
            self.app.face_db.threshold = value
        self.app.set_status(self.t("app.saved_to") % "settings.json")

    def start_enroll(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showinfo(self.t("faceid.enroll"), self.t("faceid.name"))
            return
        self.app.start_enrollment(name, self.enroll_status)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        if messagebox.askyesno(self.t("faceid.delete"),
                               self.t("faceid.deleted_msg").replace("%s", name)):
            self.app.delete_face(name)
            self.reload_people()

    def reload_people(self):
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            for name in self.app.face_db.names():
                self.tree.insert("", tk.END, values=(name, self.app.face_db.sample_count(name)))
        except Exception:
            pass

    def reload_attendance(self):
        try:
            for item in self.att.get_children():
                self.att.delete(item)
            for row in self.app.attendance.rows_today():
                if len(row) >= 5:
                    self.att.insert("", tk.END, values=(row[1], row[2], row[3], row[4]))
        except Exception:
            pass

    def refresh(self):
        self.reload_attendance()


# ===========================================================================
# تبويب الماسح
# ===========================================================================
class ScannerPanel(PanelBase):
    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("scanner.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("scanner.open_folder"),
                    lambda: open_with_default_app(SCAN_DIR)).pack(side=tk.RIGHT)

        tk.Label(self, text=self.t("scanner.hint"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9), wraplength=640, justify="left"
                 ).pack(anchor="w", padx=12, pady=(6, 0))

        actions = tk.Frame(self, bg=th.bg)
        actions.pack(fill=tk.X, padx=12, pady=10)
        self.button(actions, self.t("scanner.capture"), self.capture,
                    bg=th.accent, fg="white").pack(side=tk.LEFT, padx=(0, 8))
        self.button(actions, self.t("scanner.save_pdf"), self.save_pdf).pack(side=tk.LEFT)
        self.pages_var = tk.StringVar(value=self.t("scanner.pages") % 0)
        tk.Label(actions, textvariable=self.pages_var, bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=12)

        self.preview = tk.Label(self, text="", bg=th.canvas_bg, fg=th.muted,
                                font=("Segoe UI", 11), height=12, width=60)
        self.preview.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

    def capture(self):
        self.app.scan_document()

    def save_pdf(self):
        self.app.save_scan_pdf()

    def show(self, image, path=""):
        """يعرض الصورة المصحّحة في المعاينة."""
        if image is None:
            return
        try:
            import cv2
            from PIL import Image, ImageTk      # اختياري
        except Exception:
            self.preview.config(text=path or "", image="")
            return
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            pil.thumbnail((520, 420))
            self._photo = ImageTk.PhotoImage(pil)
            self.preview.config(image=self._photo, text="")
        except Exception:
            self.preview.config(text=path or "", image="")

    def refresh(self):
        self.pages_var.set(self.t("scanner.pages") % len(self.app.scanner.pages))


# ===========================================================================
# تبويب بوث الصور
# ===========================================================================
class PhotoBoothPanel(PanelBase):
    FILTERS = (("none", "photobooth.f.none"), ("bw", "photobooth.f.bw"),
               ("sepia", "photobooth.f.sepia"), ("cool", "photobooth.f.cool"),
               ("warm", "photobooth.f.warm"), ("vignette", "photobooth.f.vignette"))

    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("photobooth.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("photobooth.open_folder"),
                    lambda: open_with_default_app(PHOTOBOOTH_DIR)).pack(side=tk.RIGHT)

        left = tk.Frame(self, bg=th.bg)
        left.pack(fill=tk.X, padx=12, pady=(8, 0))

        # الفلاتر
        box = tk.Frame(left, bg=th.card)
        box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        tk.Label(box, text=self.t("photobooth.filter"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.filter_var = tk.StringVar(value=self.app.settings.get("photobooth.filter", "none"))
        for key, label in self.FILTERS:
            tk.Radiobutton(box, text=self.t(label), value=key, variable=self.filter_var,
                           bg=th.card, fg=th.text, selectcolor=th.btn, activebackground=th.card,
                           activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                           highlightthickness=0, anchor="w").pack(fill=tk.X, padx=12)

        # خيارات
        opts = tk.Frame(left, bg=th.card)
        opts.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(opts, text=self.t("photobooth.frame"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 0))
        self.frame_var = tk.BooleanVar(value=bool(self.app.settings.get("photobooth.frame", True)))
        tk.Checkbutton(opts, variable=self.frame_var, bg=th.card, fg=th.text,
                       selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0).pack(anchor="w", padx=12)
        tk.Label(opts, text=self.t("photobooth.blur"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 0))
        self.blur_var = tk.BooleanVar(value=bool(self.app.settings.get("photobooth.blur", True)))
        tk.Checkbutton(opts, variable=self.blur_var, bg=th.card, fg=th.text,
                       selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0).pack(anchor="w", padx=12)

        self.preview = tk.Label(self, text="", bg=th.canvas_bg, fg=th.muted,
                                font=("Segoe UI", 11), height=10, width=60)
        self.preview.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.count_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.count_var, bg=th.bg, fg=th.accent,
                 font=("Segoe UI", 22, "bold")).pack(pady=(0, 8))

        self.button(self, self.t("photobooth.shoot"), self.shoot,
                    bg=th.accent, fg="white").pack(pady=(0, 14))

    def shoot(self):
        self.app.capture_photo(self.filter_var.get(), self.frame_var.get(),
                               self.blur_var.get())

    def show(self, image, path=""):
        if image is None:
            return
        try:
            import cv2
            from PIL import Image, ImageTk
        except Exception:
            self.preview.config(text=path or "", image="")
            return
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            pil.thumbnail((520, 400))
            self._photo = ImageTk.PhotoImage(pil)
            self.preview.config(image=self._photo, text="")
        except Exception:
            self.preview.config(text=path or "", image="")

    def set_countdown(self, n):
        self.count_var.set(str(n) if n else "")


# ===========================================================================
# تبويب الإحصائيات
# ===========================================================================
class StatsPanel(PanelBase):
    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("stats.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("stats.excel"),
                    lambda: self.app.export_stats()).pack(side=tk.RIGHT)

        row = tk.Frame(self, bg=th.bg)
        row.pack(fill=tk.X, padx=12, pady=10)
        self.motions_var = tk.StringVar(value="0")
        self.peak_var = tk.StringVar(value="-")
        self.people_var = tk.StringVar(value="0")
        for title, var, color in (("stats.today_motions", self.motions_var, th.accent),
                                  ("stats.peak_hour", self.peak_var, th.ok),
                                  ("stats.people_today", self.people_var, th.chart_alt)):
            box = tk.Frame(row, bg=th.card, width=200, height=84)
            box.pack(side=tk.LEFT, padx=(0, 10))
            box.pack_propagate(False)
            tk.Label(box, text=self.t(title), bg=th.card, fg=th.muted,
                     font=("Segoe UI", 9)).pack(pady=(10, 0))
            tk.Label(box, textvariable=var, bg=th.card, fg=color,
                     font=("Segoe UI", 22, "bold")).pack()

        tk.Label(self, text=self.t("stats.hourly"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
        self.canvas = tk.Canvas(self, height=170, bg=th.canvas_bg,
                                highlightthickness=1, highlightbackground=th.border)
        self.canvas.pack(fill=tk.X, padx=12, pady=(4, 10))

        tk.Label(self, text=self.t("stats.week"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
        self.week_text = tk.Text(self, height=6, bg=th.card, fg=th.text, bd=0,
                                 relief=tk.FLAT, font=("Consolas", 9), padx=10,
                                 pady=6, highlightthickness=0)
        self.week_text.pack(fill=tk.X, padx=12, pady=(4, 12))

    def refresh(self):
        try:
            stats = self.app.stats_store
            self.motions_var.set(str(stats.total_today("motion")))
            peak = stats.peak_hour("motion")
            self.peak_var.set("%02d:00" % peak if peak >= 0 else "-")
            self.people_var.set("%d / %d" % (stats.total_today("people_in"),
                                             stats.total_today("people_out")))
            self._draw_chart(stats.hourly("motion"))
            rows = stats.daily_totals("motion", 7)
            self.week_text.delete("1.0", tk.END)
            if not rows:
                self.week_text.insert(tk.END, self.t("stats.no_data"))
            for date, count in rows:
                bar = "#" * min(40, count)
                self.week_text.insert(tk.END, "%s   %4d   %s\n" % (date, count, bar))
        except Exception as e:
            self.app.set_status(str(e))

    def _draw_chart(self, values):
        th = self.theme
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1:
            return
        mx, my = 34, 14
        maxv = max(values) if values else 0
        if maxv <= 0:
            c.create_text(w // 2, h // 2, text=self.t("stats.no_data"),
                          fill=th.muted, font=("Segoe UI", 9))
            return
        bw = (w - mx - 10) / 24.0
        for i, v in enumerate(values):
            x = mx + i * bw
            bh = (h - my - 22) * (v / float(maxv))
            color = th.chart if v else th.border
            c.create_rectangle(x + 1, h - my - bh, x + bw - 2, h - my,
                               fill=color, outline="")
            if i % 3 == 0:
                c.create_text(x + bw / 2.0, h - my + 10, text=str(i),
                              fill=th.muted, font=("Segoe UI", 7))
        c.create_line(mx, h - my, w - 6, h - my, fill=th.border)
        c.create_text(10, my + 6, text=str(maxv), fill=th.muted, font=("Segoe UI", 7))


# ===========================================================================
# تبويب الرسم
# ===========================================================================
class DrawPanel(PanelBase):
    def build(self):
        th = self.theme
        top = tk.Frame(self, bg=th.bg)
        top.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(top, text=self.t("draw.title"), bg=th.bg, fg=th.text,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self.button(top, self.t("draw.open_folder"),
                    lambda: open_with_default_app(DRAW_DIR)).pack(side=tk.RIGHT)

        tk.Label(self, text=self.t("draw.hint"), bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9), wraplength=640, justify="left"
                 ).pack(anchor="w", padx=12, pady=(8, 0))

        row = tk.Frame(self, bg=th.bg)
        row.pack(fill=tk.X, padx=12, pady=12)
        self.button(row, self.t("draw.save"), self.save, bg=th.accent,
                    fg="white").pack(side=tk.LEFT, padx=(0, 8))
        self.button(row, self.t("draw.clear"), self.clear).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status, bg=th.bg, fg=th.muted,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 12))

    def save(self):
        path = self.app.save_drawing()
        self.status.set(self.t("draw.saved") % (os.path.basename(path) if path else "-"))

    def clear(self):
        self.app.clear_drawing()
        self.status.set("")


# ===========================================================================
# تبويب الإعدادات
# ===========================================================================
class SettingsPanel(PanelBase):
    def build(self):
        th = self.theme
        s = self.app.settings

        wrap = tk.Frame(self, bg=th.bg)
        wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(10, 12))

        # ---------------- تيليجرام ----------------
        tg = tk.Frame(wrap, bg=th.card)
        tg.pack(fill=tk.X, pady=(0, 10))
        tk.Label(tg, text=self.t("telegram.title"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self.tg_enabled = tk.BooleanVar(value=bool(s.get("telegram.enabled", False)))
        tk.Checkbutton(tg, text=self.t("telegram.enable"), variable=self.tg_enabled,
                       bg=th.card, fg=th.text, selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0, command=self.save_telegram
                       ).pack(anchor="w", padx=12, pady=(6, 0))

        tk.Label(tg, text=self.t("telegram.token"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 0))
        self.tg_token = tk.Entry(tg, width=52, bg=th.input_bg, fg=th.text,
                                 insertbackground=th.text, bd=0, highlightthickness=1,
                                 highlightbackground=th.border, highlightcolor=th.accent,
                                 font=("Segoe UI", 10))
        self.tg_token.insert(0, s.get("telegram.token", "") or "")
        self.tg_token.pack(anchor="w", padx=12, ipady=3)

        tk.Label(tg, text=self.t("telegram.chat_id"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 0))
        self.tg_chat = tk.Entry(tg, width=52, bg=th.input_bg, fg=th.text,
                                insertbackground=th.text, bd=0, highlightthickness=1,
                                highlightbackground=th.border, highlightcolor=th.accent,
                                font=("Segoe UI", 10))
        self.tg_chat.insert(0, s.get("telegram.chat_id", "") or "")
        self.tg_chat.pack(anchor="w", padx=12, ipady=3)

        checks = tk.Frame(tg, bg=th.card)
        checks.pack(fill=tk.X, padx=12, pady=8)
        self.tg_notify = {}
        for key, label in (("notify_motion", "telegram.notify_motion"),
                           ("notify_unknown_face", "telegram.notify_unknown_face"),
                           ("notify_attendance", "telegram.notify_attendance"),
                           ("notify_count", "telegram.notify_count")):
            var = tk.BooleanVar(value=bool(s.get("telegram." + key, True)))
            self.tg_notify[key] = var
            tk.Checkbutton(checks, text=self.t(label), variable=var, bg=th.card,
                           fg=th.text, selectcolor=th.btn, activebackground=th.card,
                           activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                           highlightthickness=0, command=self.save_telegram
                           ).pack(side=tk.LEFT, padx=(0, 14))

        row = tk.Frame(tg, bg=th.card)
        row.pack(fill=tk.X, padx=12, pady=(4, 8))
        self.button(row, self.t("telegram.test"), self.test_telegram,
                    bg=th.accent, fg="white").pack(side=tk.LEFT, padx=(0, 8))
        self.button(row, self.t("app.save"), self.save_telegram).pack(side=tk.LEFT)
        tk.Label(tg, text=self.t("telegram.hint"), bg=th.card, fg=th.muted,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(0, 10))

        # ---------------- القفل التلقائي ----------------
        al = tk.Frame(wrap, bg=th.card)
        al.pack(fill=tk.X, pady=(0, 10))
        tk.Label(al, text=self.t("autolock.title"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self.al_enabled = tk.BooleanVar(value=bool(s.get("autolock.enabled", False)))
        tk.Checkbutton(al, text=self.t("autolock.enable"), variable=self.al_enabled,
                       bg=th.card, fg=th.text, selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0, command=self.save_autolock
                       ).pack(anchor="w", padx=12, pady=(6, 0))

        row2 = tk.Frame(al, bg=th.card)
        row2.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(row2, text=self.t("autolock.idle_seconds"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.al_seconds = tk.Spinbox(row2, from_=5, to=600, increment=5, width=7,
                                     bg=th.input_bg, fg=th.text, buttonbackground=th.btn,
                                     relief=tk.FLAT, highlightthickness=1,
                                     highlightbackground=th.border,
                                     highlightcolor=th.accent, font=("Segoe UI", 10))
        self.al_seconds.delete(0, tk.END)
        self.al_seconds.insert(0, str(s.get("autolock.idle_seconds", 15)))
        self.al_seconds.pack(side=tk.LEFT, padx=10)
        self.button(row2, self.t("autolock.lock_now"), self.lock_now,
                    bg=th.stop, fg="white").pack(side=tk.LEFT, padx=(6, 0))

        self.al_recognize = tk.BooleanVar(value=bool(s.get("autolock.recognize_only", True)))
        tk.Checkbutton(al, text=self.t("autolock.recognize_only"), variable=self.al_recognize,
                       bg=th.card, fg=th.text, selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0, command=self.save_autolock
                       ).pack(anchor="w", padx=12)

        self.al_autotype = tk.BooleanVar(value=bool(s.get("autolock.auto_type_password", False)))
        tk.Checkbutton(al, text=self.t("autolock.auto_type"), variable=self.al_autotype,
                       bg=th.card, fg=th.text, selectcolor=th.btn, activebackground=th.card,
                       activeforeground=th.text, font=("Segoe UI", 9), bd=0,
                       highlightthickness=0, command=self.save_autolock
                       ).pack(anchor="w", padx=12, pady=(6, 0))
        tk.Label(al, text=self.t("autolock.password"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12)
        self.al_password = tk.Entry(al, width=32, show="*", bg=th.input_bg, fg=th.text,
                                    insertbackground=th.text, bd=0, highlightthickness=1,
                                    highlightbackground=th.border, highlightcolor=th.accent,
                                    font=("Segoe UI", 10))
        self.al_password.insert(0, s.get("autolock.password", "") or "")
        self.al_password.pack(anchor="w", padx=12, ipady=3)
        tk.Label(al, text=self.t("autolock.warning"), bg=th.card, fg=th.danger,
                 font=("Segoe UI", 8), wraplength=620, justify="left"
                 ).pack(anchor="w", padx=12, pady=(6, 10))
        self.button(al, self.t("app.save"), self.save_autolock).pack(anchor="w",
                                                                       padx=12, pady=(0, 10))

        # ---------------- الصوت والمجلدات ----------------
        misc = tk.Frame(wrap, bg=th.card)
        misc.pack(fill=tk.X)
        tk.Label(misc, text=self.t("voice.title"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        row3 = tk.Frame(misc, bg=th.card)
        row3.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(row3, text=self.t("voice.trigger"), bg=th.card, fg=th.text,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.voice_trigger = ttk.Combobox(row3, state="readonly", width=12,
                                          values=("palm", "fist", "point"))
        self.voice_trigger.set(s.get("voice.trigger", "palm"))
        self.voice_trigger.pack(side=tk.LEFT, padx=10)
        self.button(row3, self.t("app.save"), self.save_voice).pack(side=tk.LEFT)

        tk.Label(misc, text=self.t("voice.hint"), bg=th.card, fg=th.muted,
                 font=("Segoe UI", 8), wraplength=620, justify="left"
                 ).pack(anchor="w", padx=12, pady=(0, 10))

        row4 = tk.Frame(misc, bg=th.card)
        row4.pack(fill=tk.X, padx=12, pady=(0, 10))
        for label, path in (("captures", CAPTURE_DIR), ("photobooth", PHOTOBOOTH_DIR),
                            ("scans", SCAN_DIR), ("drawings", DRAW_DIR),
                            ("logs", LOG_DIR), ("models", MODELS_DIR),
                            ("faces", FACES_DIR)):
            b = tk.Button(row4, text=label, bg=th.btn, fg=th.text, relief=tk.FLAT,
                          font=("Segoe UI", 8), cursor="hand2", bd=0,
                          highlightthickness=0,
                          command=lambda p=path: open_with_default_app(p))
            b.pack(side=tk.LEFT, padx=(0, 5), ipady=3)
        self.button(row4, self.t("app.reset"), self.reset_all,
                    bg=th.stop, fg="white").pack(side=tk.RIGHT)

    # ----- الحفظ -----
    def save_telegram(self):
        s = self.app.settings
        s.set("telegram.enabled", bool(self.tg_enabled.get()))
        s.set("telegram.token", self.tg_token.get().strip())
        s.set("telegram.chat_id", self.tg_chat.get().strip())
        for key, var in self.tg_notify.items():
            s.set("telegram." + key, bool(var.get()))
        s.save()
        self.app.apply_telegram()
        self.app.set_status(self.t("app.saved_to") % "settings.json")

    def test_telegram(self):
        self.save_telegram()
        self.app.test_telegram()

    def save_autolock(self):
        s = self.app.settings
        s.set("autolock.enabled", bool(self.al_enabled.get()))
        try:
            s.set("autolock.idle_seconds", int(float(self.al_seconds.get())))
        except Exception:
            pass
        s.set("autolock.recognize_only", bool(self.al_recognize.get()))
        s.set("autolock.auto_type_password", bool(self.al_autotype.get()))
        s.set("autolock.password", self.al_password.get())
        s.save()
        self.app.set_status(self.t("app.saved_to") % "settings.json")

    def save_voice(self):
        s = self.app.settings
        s.set("voice.trigger", self.voice_trigger.get())
        s.save()
        self.app.set_status(self.t("app.saved_to") % "settings.json")

    def lock_now(self):
        self.save_autolock()
        self.app.lock_now()

    def reset_all(self):
        if messagebox.askyesno(self.t("app.reset"),
                               self.t("app.reset") + "?"):
            self.app.reset_settings()
