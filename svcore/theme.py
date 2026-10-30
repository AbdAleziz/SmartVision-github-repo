# -*- coding: utf-8 -*-
"""الثيمات (فاتح / غامق) — ألوان الواجهة."""

import tkinter as tk


class Theme(object):
    """مجموعة ألوان للواجهة. كل الحقول تُستعمل كـ attributes."""

    def __init__(self, name, bg, side, card, btn, btn_h, btn_active, start, start_h,
                 stop, stop_h, accent, text, muted, ok, border, input_bg, danger,
                 chart, chart_alt, canvas_bg):
        self.name = name
        self.bg = bg
        self.side = side
        self.card = card
        self.btn = btn
        self.btn_h = btn_h
        self.btn_active = btn_active
        self.start = start
        self.start_h = start_h
        self.stop = stop
        self.stop_h = stop_h
        self.accent = accent
        self.text = text
        self.muted = muted
        self.ok = ok
        self.border = border
        self.input_bg = input_bg
        self.danger = danger
        self.chart = chart
        self.chart_alt = chart_alt
        self.canvas_bg = canvas_bg

    def is_dark(self):
        return self.name == "dark"


DARK = Theme(
    name="dark",
    bg="#12141c",
    side="#1a1d28",
    card="#222637",
    btn="#2a2f45",
    btn_h="#353c5a",
    btn_active="#16a34a",
    start="#2563eb",
    start_h="#3b82f6",
    stop="#dc2626",
    stop_h="#ef4444",
    accent="#6d83f2",
    text="#eef0f8",
    muted="#8f98b3",
    ok="#22c55e",
    border="#2f3550",
    input_bg="#1b1f2e",
    danger="#f87171",
    chart="#6d83f2",
    chart_alt="#22c55e",
    canvas_bg="#0d0f16",
)

LIGHT = Theme(
    name="light",
    bg="#f2f4f9",
    side="#ffffff",
    card="#ffffff",
    btn="#e6e9f2",
    btn_h="#d8dceb",
    btn_active="#16a34a",
    start="#2563eb",
    start_h="#3b82f6",
    stop="#dc2626",
    stop_h="#ef4444",
    accent="#4338ca",
    text="#1b1f2e",
    muted="#5c6480",
    ok="#15803d",
    border="#cbd2e4",
    input_bg="#ffffff",
    danger="#dc2626",
    chart="#4338ca",
    chart_alt="#15803d",
    canvas_bg="#e9edf6",
)

THEMES = {"dark": DARK, "light": LIGHT}
FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"


def get_theme(name):
    """يعيد الثيم المطلوب (أو الغامق افتراضياً)."""
    if isinstance(name, Theme):
        return name
    return THEMES.get(str(name).lower(), DARK)


def apply_ttk_style(root, theme):
    """يجعل قوائم ttk تتناسق مع الثيم (Combobox / Scrollbar / Notebook)."""
    style = tk.ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TCombobox", fieldbackground=theme.input_bg, background=theme.input_bg,
                    foreground=theme.text, arrowcolor=theme.text, bordercolor=theme.border,
                    lightcolor=theme.input_bg, darkcolor=theme.input_bg,
                    selectbackground=theme.btn, selectforeground=theme.text)
    style.map("TCombobox", fieldbackground=[("readonly", theme.input_bg)],
              foreground=[("readonly", theme.text)],
              selectbackground=[("readonly", theme.btn)])
    style.configure("Vertical.TScrollbar", background=theme.btn, troughcolor=theme.bg,
                    bordercolor=theme.bg, arrowcolor=theme.muted,
                    lightcolor=theme.btn, darkcolor=theme.btn)
    style.configure("TNotebook", background=theme.bg, bordercolor=theme.border,
                    lightcolor=theme.bg, darkcolor=theme.bg)
    style.configure("TNotebook.Tab", background=theme.btn, foreground=theme.text,
                    bordercolor=theme.border, padding=(14, 7), font=(FONT_UI, 9))
    style.map("TNotebook.Tab",
              background=[("selected", theme.card)],
              foreground=[("selected", theme.accent)])
    style.configure("Treeview", background=theme.card, fieldbackground=theme.card,
                    foreground=theme.text, bordercolor=theme.border,
                    rowheight=26, font=(FONT_UI, 9))
    style.configure("Treeview.Heading", background=theme.btn, foreground=theme.text,
                    bordercolor=theme.border, font=(FONT_UI, 9, "bold"))
    style.map("Treeview", background=[("selected", theme.accent)],
              foreground=[("selected", "#ffffff")])
    style.configure("TProgressbar", background=theme.accent, troughcolor=theme.btn,
                    bordercolor=theme.border, lightcolor=theme.accent, darkcolor=theme.accent)
    root.option_add("*TCombobox*Listbox.background", theme.input_bg)
    root.option_add("*TCombobox*Listbox.foreground", theme.text)
    root.option_add("*TCombobox*Listbox.selectBackground", theme.accent)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    return style
