# -*- coding: utf-8 -*-
"""خيط الكاميرا: يقرأ الإطارات في الخلفية حتى لا تتجمد الواجهة."""

import os
import threading
import time

try:
    import cv2
except Exception:          # pragma: no cover
    cv2 = None

from .vision import FRAME_W, VisionProcessor


class CameraWorker(threading.Thread):
    """يقرأ من الكاميرا ويمرّر الإطارات للمعالج."""

    def __init__(self, index, events, wid, mode, min_area, settings=None):
        threading.Thread.__init__(self, name="camera", daemon=True)
        self.index = index
        self.events = events
        self.wid = wid
        self.mode = mode
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.raw = None
        self.settings = settings
        self.processor = VisionProcessor(self.emit, min_area, settings)

    # ------------------------------------------------------------- الأحداث
    def emit(self, kind, *args):
        try:
            self.events.put((self.wid, kind, args))
        except Exception:
            pass

    def stop(self):
        self.stop_event.set()

    def get_frame(self):
        """آخر إطار مُعالَج (مرة واحدة)."""
        with self.lock:
            frame, self.latest = self.latest, None
        return frame

    def peek_frame(self):
        with self.lock:
            return self.latest

    def get_raw(self):
        """آخر إطار خام من الكاميرا (بدون رسم Consensus) — لالتقاط الصور."""
        with self.lock:
            return self.raw

    # ------------------------------------------------------------- الكاميرا
    def _open(self):
        if cv2 is None:
            return None
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(self.index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    return cap
                cap.release()
            except Exception:
                continue
        return None

    @staticmethod
    def _fit(frame):
        h, w = frame.shape[:2]
        if w != FRAME_W:
            frame = cv2.resize(frame, (FRAME_W, max(1, int(h * FRAME_W / float(w)))))
        return frame

    # --------------------------------------------------------------- التشغيل
    def run(self):
        cap = None
        try:
            cap = self._open()
            if cap is None:
                self.emit("error", "Cannot open camera %d.\nCheck the USB cable, the camera "
                                   "index, or whether another program is using it." % self.index)
                return
            self.emit("started")
            fails = 0
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    fails += 1
                    if fails >= 30:
                        self.emit("error", "Camera connection lost.")
                        break
                    time.sleep(0.03)
                    continue
                fails = 0
                with self.lock:
                    self.raw = frame.copy()
                frame = self._fit(frame)
                try:
                    out = self.processor.process(frame, self.mode)
                except Exception as e:
                    self.processor._report_once("process", e)
                    out = frame
                with self.lock:
                    self.latest = out
        except Exception as e:
            self.emit("error", "Camera error: %s" % e)
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            self.emit("stopped")
