# -*- coding: utf-8 -*-
"""
فاحص خفيف للكود (mini-pyflakes) — يكتشف الأسماء غير المعرّفة.

يعمل بلا أي مكتبة خارجية (ast فقط)، ويُستخدم للتحقق من المشروع قبل التسليم
خصوصاً أن بيئة التطوير قد لا تحتوي OpenCV ولا Tkinter.

الاستخدام:
    python tools/lint.py
"""

import ast
import builtins
import os
import sys


def _setup_console():
    """يجعل المخرجات UTF-8 حتى لا يسقط البرنامج على ويندوز (cp1252).

    بدون هذا السطر، طباعة العربي على GitHub Actions ترمي UnicodeEncodeError.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_setup_console()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__",
                                 "__spec__", "__loader__", "__builtins__", "WindowsError"}


class Scope(object):
    """نطاق بسيط: أسماء معرّفة + نطاق الأب."""

    def __init__(self, parent=None, kind="module"):
        self.names = set()
        self.parent = parent
        self.kind = kind

    def define(self, name):
        if name:
            self.names.add(name)

    def has(self, name):
        scope = self
        while scope is not None:
            if name in scope.names:
                return True
            scope = scope.parent
        return False


class Checker(ast.NodeVisitor):
    """يجمع الأسماء المعرّفة ويبلّغ عن الأسماء المستخدمة والمجهولة."""

    def __init__(self):
        self.scopes = [Scope()]
        self.problems = []
        self.collect_only = False

    # ---------- أدوات النطاق ----------
    @property
    def scope(self):
        return self.scopes[-1]

    def push(self, kind="function"):
        self.scopes.append(Scope(self.scope, kind))

    def pop(self):
        self.scopes.pop()

    def bind_target(self, node):
        if isinstance(node, ast.Name):
            self.scope.define(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for el in node.elts:
                self.bind_target(el)
        elif isinstance(node, ast.Starred):
            self.bind_target(node.value)

    def check_name(self, node):
        if isinstance(node.ctx, ast.Load):
            name = node.id
            if (not self.collect_only and not self.scope.has(name)
                    and name not in BUILTINS):
                self.problems.append((node.lineno, "اسم غير معرّف: %s" % name))

    # ---------- الزوار ----------
    def visit_Import(self, node):
        for alias in node.names:
            self.scope.define(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self.scope.define(alias.asname or alias.name)

    def visit_FunctionDef(self, node):
        self.scope.define(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        self._function_body(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _function_body(self, node):
        self.push("function")
        args = node.args
        for arg in (list(args.posonlyargs) + list(args.args) +
                    list(args.kwonlyargs)):
            self.scope.define(arg.arg)
        if args.vararg:
            self.scope.define(args.vararg.arg)
        if args.kwarg:
            self.scope.define(args.kwarg.arg)
        for stmt in node.body:
            self.visit(stmt)
        self.pop()

    def visit_Lambda(self, node):
        self.push("function")
        args = node.args
        for arg in list(args.args) + list(args.kwonlyargs):
            self.scope.define(arg.arg)
        if args.vararg:
            self.scope.define(args.vararg.arg)
        if args.kwarg:
            self.scope.define(args.kwarg.arg)
        self.visit(node.body)
        self.pop()

    def visit_ClassDef(self, node):
        self.scope.define(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        for base in node.bases:
            self.visit(base)
        class_scope = Scope(self.scope, "class")
        self.scopes.append(class_scope)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.scope.define(stmt.name)      # اسم الدالة مرئي داخل الصنف
                continue
            self.visit(stmt)
        self.scopes.pop()
        # دوال الصنف ترى أسماء الصنف (self.x غير مطلوب لكن الاسم المجرد شائع)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._method_body(stmt, class_scope)

    def _method_body(self, node, parent_scope):
        self.scopes.append(Scope(parent_scope, "function"))
        args = node.args
        for arg in (list(args.posonlyargs) + list(args.args) +
                    list(args.kwonlyargs)):
            self.scope.define(arg.arg)
        if args.vararg:
            self.scope.define(args.vararg.arg)
        if args.kwarg:
            self.scope.define(args.kwarg.arg)
        for stmt in node.body:
            self.visit(stmt)
        self.scopes.pop()

    def visit_Assign(self, node):
        self.visit(node.value)
        for target in node.targets:
            self.bind_target(target)

    def visit_AnnAssign(self, node):
        if node.value:
            self.visit(node.value)
        self.bind_target(node.target)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        self.bind_target(node.target)

    def visit_For(self, node):
        self.visit(node.iter)
        self.bind_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.bind_target(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node):
        if node.type:
            self.visit(node.type)
        if node.name:
            self.scope.define(node.name)
        for stmt in node.body:
            self.visit(stmt)

    def visit_Global(self, node):
        for name in node.names:
            self.scope.define(name)

    def visit_Nonlocal(self, node):
        for name in node.names:
            self.scope.define(name)

    def _comprehension(self, node):
        self.push("function")
        for gen in node.generators:
            self.bind_target(gen.target)
            self.visit(gen.iter)
            for cond in gen.ifs:
                self.visit(cond)
        self.visit(node.elt)
        self.pop()

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_GeneratorExp = _comprehension

    def visit_DictComp(self, node):
        self.push("function")
        for gen in node.generators:
            self.bind_target(gen.target)
            self.visit(gen.iter)
            for cond in gen.ifs:
                self.visit(cond)
        self.visit(node.key)
        self.visit(node.value)
        self.pop()

    def visit_Name(self, node):
        self.check_name(node)

    def visit_Attribute(self, node):
        self.generic_visit(node)


def check_file(path):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)

    # المرور 1: جمع أسماء المستوى الأعلى (لتفادي أخطاء ترتيب التعريف)
    pre = Checker()
    pre.collect_only = True
    pre.visit(tree)
    module_names = set(pre.scopes[0].names)

    # المرور 2: الفحص الفعلي
    checker = Checker()
    checker.scopes[0].names.update(module_names)
    checker.visit(tree)
    return checker.problems


def rel(path):
    return os.path.relpath(path, ROOT)


def main():
    targets = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "stubs",
                                                "build", "dist", "data")]
        for name in files:
            if name.endswith(".py"):
                targets.append(os.path.join(base, name))

    total = 0
    for path in sorted(targets):
        try:
            problems = check_file(path)
        except SyntaxError as e:
            print("%s: خطأ صياغة: %s (سطر %s)" % (rel(path), e.msg, e.lineno))
            total += 1
            continue
        for lineno, msg in problems:
            print("%s:%s: %s" % (rel(path), lineno, msg))
            total += 1
    print("\nفُحص %d ملف - مشاكل: %d" % (len(targets), total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
