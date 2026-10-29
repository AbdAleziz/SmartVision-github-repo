# -*- coding: utf-8 -*-
"""
بديل مبسّط لمكتبة tkinter للاستخدام في اختبارات وحدة الاستيراد فقط.

لا يُستخدم في التطبيق الحقيقي — هدفه فقط أن يسمح بتشغيل
`python tools/selftest.py` على بيئة بلا tkinter (مثل CI أو خادم).
"""

import sys
import types


class _Dummy(object):
    """قيمة وهمية تقبل العمليات الحسابية حتى لا تنهار اختبارات الواجهة."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Dummy()

    def __call__(self, *args, **kwargs):
        return _Dummy()

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return iter([])

    def __add__(self, other):
        return other if isinstance(other, (int, float)) else 0

    def __radd__(self, other):
        return other if isinstance(other, (int, float)) else 0

    def __sub__(self, other):
        return -other if isinstance(other, (int, float)) else 0

    def __rsub__(self, other):
        return other if isinstance(other, (int, float)) else 0

    def __mul__(self, other):
        return 0

    def __rmul__(self, other):
        return 0

    def __floordiv__(self, other):
        return 0

    def __mod__(self, other):
        return 0

    def __getitem__(self, item):
        return _Dummy()

    def __setitem__(self, item, value):
        return None

    def __eq__(self, other):
        return False

    def __hash__(self):
        return 0


class _Widget(_Dummy):
    """سلوك يشبه الواجهة الحقيقية بما يكفي для اختبارات الاستيراد."""

    def __init__(self, *args, **kwargs):
        self._children = []
        self._config = {}

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def title(self, value=None):
        if value is not None:
            self._title = value
        return getattr(self, "_title", "")

    def winfo_width(self):
        return 640

    def winfo_height(self):
        return 480

    def pack(self, *args, **kwargs):
        return self

    def grid(self, *args, **kwargs):
        return self

    def place(self, *args, **kwargs):
        return self

    def pack_forget(self, *args, **kwargs):
        return self

    def pack_propagate(self, *args, **kwargs):
        return self

    def grid_propagate(self, *args, **kwargs):
        return self

    def config(self, *args, **kwargs):
        return self

    configure = config

    def cget(self, name):
        return self._config.get(name)

    def bind(self, *args, **kwargs):
        return self

    def after(self, *args, **kwargs):
        return None

    def update(self):
        return None

    def winfo_children(self):
        return []

    def destroy(self):
        return None

    def mainloop(self):
        return None


def _make(name, base=_Widget):
    return type(name, (base,), {})


Tk = _make("Tk")
Toplevel = _make("Toplevel")
Frame = _make("Frame")
Label = _make("Label")
Button = _make("Button")
Entry = _make("Entry")
Text = _make("Text")
Canvas = _make("Canvas")
Scrollbar = _make("Scrollbar")
Menu = _make("Menu")
Listbox = _make("Listbox")
Checkbutton = _make("Checkbutton")
Radiobutton = _make("Radiobutton")
Scale = _make("Scale")
Spinbox = _make("Spinbox")
PhotoImage = _make("PhotoImage")
StringVar = _make("StringVar")
IntVar = _make("IntVar")
BooleanVar = _make("BooleanVar")
DoubleVar = _make("DoubleVar")
TkVersion = "8.6"

FLAT = "flat"
LEFT = "left"
RIGHT = "right"
TOP = "top"
BOTTOM = "bottom"
BOTH = "both"
X = "x"
Y = "y"
NW = "nw"
N = "n"
NE = "ne"
W = "w"
CENTER = "center"
END = "end"
WORD = "word"
CHAR = "char"
NONE = "none"
ACTIVE = "active"
NORMAL = "normal"
DISABLED = "disabled"
INSERT = "insert"
SELECTED = "selected"
HORIZONTAL = "horizontal"
VERTICAL = "vertical"
RAISED = "raised"
SUNKEN = "sunken"
GROOVE = "groove"
RIDGE = "ridge"

SEL = "sel"
SEL_FIRST = "sel.first"
SEL_LAST = "sel.last"
END = "end"
INSERT = "insert"

# Tkinter حقيقي يعرّف هذه الثوابت كـ ints، لكن الأرقام لا تهم في الاستيراد
for _name in ("NO", "YES", "OK", "CANCEL", "YESNO", "OKCANCEL", "QUESTION",
              "WARNING", "ERROR", "INFO", "ABORT", "RETRY", "IGNORE"):
    globals()[_name] = 1

ttk = types.ModuleType("tkinter.ttk")


class _TtkWidget(_Widget):
    pass


for _name in ("Style", "Combobox", "Notebook", "Treeview", "Scrollbar",
              "Progressbar", "Label", "Frame", "Button", "Entry", "Checkbutton",
              "Radiobutton", "Separator", "Sizegrip"):
    setattr(ttk, _name, _make(_name, _TtkWidget))

sys.modules.setdefault("tkinter.ttk", ttk)
ttk = ttk
