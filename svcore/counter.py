# -*- coding: utf-8 -*-
"""
عدّاد الأشخاص: يحسب الدخول والخروج عبر خط يحدده المستخدم على الشاشة.

المنطق:
  - كل شخص يُتتبَّع كـ"مسار" (track) عبر الإطارات بمطابقة التشابه (IoU).
  - لكل مسار نحتفظ بجهته الحالية بالنسبة للخط (+ أو -).
  - عند تغيّر الجهة مع بقاء الشخص في نفس الجهة briefly نعتبره عبوراً ونعدّه.
"""

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

from .utils import iou


class PeopleCounter(object):
    """عدّاد عبر خط، يدعم عدة أشخاص في نفس الوقت."""

    def __init__(self, settings=None):
        self.settings = settings
        self.tracks = []
        self.next_id = 1
        self.count_in = 0
        self.count_out = 0
        self.events = []
        line = [0.5, 0.0, 0.5, 1.0]
        if settings is not None:
            try:
                line = settings.get("counter.line", line)
            except Exception:
                line = [0.5, 0.0, 0.5, 1.0]
        self.line = list(line)              # [x1, y1, x2, y2] نسبية 0..1

    # ------------------------------------------------------------- الخط
    def set_line(self, p1, p2):
        """يضبط خط العبور من نقطتين نسبيتين (0..1)."""
        try:
            self.line = [float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])]
            return True
        except Exception:
            return False

    def get_line(self):
        return list(self.line)

    def reset(self):
        self.tracks = []
        self.count_in = 0
        self.count_out = 0
        self.events = []

    @property
    def inside(self):
        """عدد الأشخاص الذين في الجانب الداخلي حالياً."""
        return max(0, self.count_in - self.count_out)

    @property
    def counts(self):
        return {"in": self.count_in, "out": self.count_out}

    # ------------------------------------------------------------- الحساب
    @staticmethod
    def side_of(line, x, y):
        """إشارة الجهة: موجبة = جهة واحدة، سالبة = الأخرى."""
        x1, y1, x2, y2 = line
        return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)

    def update(self, detections, frame_size, now=None):
        """يستقبل قائمة مربعات الأشخاص ويعيد أحداث العبور."""
        import time
        now = time.time() if now is None else now
        w, h = frame_size
        line_px = (self.line[0] * w, self.line[1] * h,
                   self.line[2] * w, self.line[3] * h)
        events = []
        # أقصى مسافة يُعتبر فيها الشخصان نفس الشخص (لأن الشخص قد يتحرك
        # بسرعة بين إطارين متتاليين)
        max_dist = max(24.0, w * 0.25)

        # 1) مطابقة المسارات
        used = set()
        for det in detections:
            best = None
            best_iou = 0.25
            for tr in self.tracks:
                if tr["id"] in used:
                    continue
                score = iou(tr["bbox"], det)
                if score > best_iou:
                    best_iou = score
                    best = tr
            if best is None:
                # مطابقة احتياطية بالمركز: الشخص قد يتحرك بسرعة بين إطارين
                cx0 = det[0] + det[2] / 2.0
                cy0 = det[1] + det[3] / 2.0
                for tr in self.tracks:
                    if tr["id"] in used or not tr.get("center"):
                        continue
                    dist = ((tr["center"][0] - cx0) ** 2 +
                            (tr["center"][1] - cy0) ** 2) ** 0.5
                    if dist > max_dist:
                        continue
                    old_area = max(1, tr["bbox"][2] * tr["bbox"][3])
                    new_area = max(1, det[2] * det[3])
                    ratio = new_area / float(old_area)
                    if ratio < 0.6 or ratio > 1.7:
                        continue          # الحجم تغيّر كثيراً = شخص آخر
                    best = tr
                    break
            if best is None:
                tr = {"id": self.next_id, "bbox": det, "center": None,
                      "side": 0, "side_since": now, "last_seen": now,
                      "counted": False, "misses": 0, "pending_side": None,
                      "pending_since": 0.0}
                self.next_id += 1
                self.tracks.append(tr)
                used.add(tr["id"])
                best = tr
            else:
                used.add(best["id"])
                best["bbox"] = det
                best["last_seen"] = now
                best["misses"] = 0

            cx = det[0] + det[2] / 2.0
            cy = det[1] + det[3] / 2.0
            best["center"] = (cx, cy)
            side = 1 if self.side_of(line_px, cx, cy) >= 0 else -1
            if best["side"] == 0:
                best["side"] = side
                best["side_since"] = now
            elif side != best["side"]:
                # تغيّرت الجهة: ننتظر أن يستقر على الجانب الجديد قبل العدّ
                if best.get("pending_side") == side and \
                        now - best.get("pending_since", now) >= 0.4:
                    entering = (side > 0 and best["side"] < 0)
                    if entering:
                        self.count_in += 1
                        events.append({"event": "in", "count": self.count_in})
                    else:
                        self.count_out += 1
                        events.append({"event": "out", "count": self.count_out})
                    best["side"] = side
                    best["side_since"] = now
                    best["pending_side"] = None
                else:
                    best["pending_side"] = side
                    best["pending_since"] = now
            else:
                best["pending_side"] = None

        # 2) مسارات اختفت
        alive = []
        for tr in self.tracks:
            if now - tr["last_seen"] > 2.0:
                continue
            alive.append(tr)
        self.tracks = alive
        self.events.extend(events)
        return events

    # --------------------------------------------------------------- الرسم
    def draw(self, out, frame_size):
        """يرسم خط العبور وأسهم الاتجاه."""
        if cv2 is None:
            return out
        w, h = frame_size
        p1 = (int(self.line[0] * w), int(self.line[1] * h))
        p2 = (int(self.line[2] * w), int(self.line[3] * h))
        cv2.line(out, p1, p2, (0, 220, 255), 3)
        # سهم يشير إلى جهة "الدخول" (نفس اتجاه زيادة قيمة side)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length > 10:
            ux, uy = dx / length, dy / length
            nx, ny = -uy, ux           # العمود الطبيعي لجهة الدخول
            tipx, tipy = int(p1[0] + nx * 28), int(p1[1] + ny * 28)
            cv2.arrowedLine(out, p1, (tipx, tipy), (0, 220, 255), 3,
                            tipLength=0.4)
            lblx = int(p1[0] + nx * 26)
            lbly = int(p1[1] + ny * 26)
            cv2.putText(out, "IN", (lblx, lbly), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 220, 255), 2)
        for tr in self.tracks:
            x, y, bw, bh = tr["bbox"]
            cv2.rectangle(out, (x, y), (x + bw, y + bh), (255, 200, 0), 1)
        return out
