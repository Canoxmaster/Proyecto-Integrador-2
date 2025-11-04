import time
import cv2

class CameraManager:
    def __init__(self):
        self.cap = None

    def open(self):
        if self.cap is not None and self.cap.isOpened():
            return True
        preferred_backends = [
            getattr(cv2, "CAP_DSHOW", 700),
            getattr(cv2, "CAP_MSMF", 1400),
            0,
        ]
        for backend in preferred_backends:
            cap = None
            try:
                cap = cv2.VideoCapture(0, backend) if backend != 0 else cv2.VideoCapture(0)
                if not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                    continue
                try:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                start = time.time()
                while time.time() - start < 0.25:
                    cap.grab()
                self.cap = cap
                return True
            except Exception:
                try:
                    if cap:
                        cap.release()
                except Exception:
                    pass
                continue
        return False

    def read(self):
        if self.cap is None or not self.cap.isOpened():
            if not self.open():
                return False, None
        try:
            self.cap.grab()
        except Exception:
            pass
        return self.cap.read()

    def release(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

# Shared instance
camera = CameraManager()
