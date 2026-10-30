# -*- coding: utf-8 -*-
"""بديل tkinter.ttk للاستيراد فقط."""
from . import _make, _TtkWidget  # noqa: F401

Style = _make("Style", _TtkWidget)
Combobox = _make("Combobox", _TtkWidget)
Notebook = _make("Notebook", _TtkWidget)
Treeview = _make("Treeview", _TtkWidget)
Scrollbar = _make("Scrollbar", _TtkWidget)
Progressbar = _make("Progressbar", _TtkWidget)
Label = _make("Label", _TtkWidget)
Frame = _make("Frame", _TtkWidget)
Button = _make("Button", _TtkWidget)
Entry = _make("Entry", _TtkWidget)
Checkbutton = _make("Checkbutton", _TtkWidget)
Radiobutton = _make("Radiobutton", _TtkWidget)
Separator = _make("Separator", _TtkWidget)
Sizegrip = _make("Sizegrip", _TtkWidget)
