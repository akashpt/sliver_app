import os
import cv2
import base64
import numpy as np
import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
from predict_d import StripColorDetector

import importlib.util

# ----------------------------
# Load MVSDK
# ----------------------------
MVSDK_PY = r"mvsdk\demo\python_demo\mvsdk.py"

spec = importlib.util.spec_from_file_location("mvsdk", MVSDK_PY)
mvsdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mvsdk)


class Bridge(QObject):

    frameUpdate = pyqtSignal(str)
    statsUpdate = pyqtSignal(int, int, int)
    defectFound = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        self.reference_path = r"D:\sliver_app\good_lab_reference.npy"

        self.detector = StripColorDetector(
            image_folder=".",
            output_folder="defects_image",
            reference_path=self.reference_path,
            color_threshold=20
        )

        self.hCamera = None
        self.pFrameBuffer = None
        self.camera_open = False

        self.inspected = 0
        self.good_count = 0
        self.bad_count = 0

        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.grab_preview)

        self.detector_timer = QTimer()
        self.detector_timer.setInterval(5000)
        self.detector_timer.timeout.connect(self.run_detection)

        self.last_frame = None

    # -------------------------
    # START CAMERA
    # -------------------------
    @pyqtSlot()
    def startDetection(self):

        devs = mvsdk.CameraEnumerateDevice()

        if not devs:
            print("No camera found")
            return

        dev = devs[0]

        self.hCamera = mvsdk.CameraInit(dev, -1, -1)

        cap = mvsdk.CameraGetCapability(self.hCamera)

        mono = (cap.sIspCapacity.bMonoSensor != 0)

        if mono:
            mvsdk.CameraSetIspOutFormat(
                self.hCamera,
                mvsdk.CAMERA_MEDIA_TYPE_MONO8
            )
        else:
            mvsdk.CameraSetIspOutFormat(
                self.hCamera,
                mvsdk.CAMERA_MEDIA_TYPE_BGR8
            )

        # ⭐ FIX PIPELINE
        mvsdk.CameraSetTriggerMode(self.hCamera, 0)
        mvsdk.CameraSetAeState(self.hCamera, 0)
        mvsdk.CameraSetExposureTime(self.hCamera, 64068)

        if not mono:
            try:
                # HARD ISP COLOR LOCK (VERY IMPORTANT)
                mvsdk.CameraSetGain(self.hCamera, 100, 100, 100)
                mvsdk.CameraSetWbMode(self.hCamera, 2)
                mvsdk.CameraSetOnceWB(self.hCamera)
                mvsdk.CameraSetColorCorrection(self.hCamera, 1)
            except Exception as e:
                print("ISP config error:", e)

        mvsdk.CameraPlay(self.hCamera)
        self.set_color_temp_mode()

        wmax = cap.sResolutionRange.iWidthMax
        hmax = cap.sResolutionRange.iHeightMax

        self.frame_buffer_size = int(wmax * hmax * (1 if mono else 3))

        self.pFrameBuffer = mvsdk.CameraAlignMalloc(
            self.frame_buffer_size,
            16
        )

        self.camera_open = True

        self.preview_timer.start(80)
        self.detector_timer.start()

        print("Camera started")

    # -------------------------
    # STOP CAMERA
    # -------------------------
    def stopDetection(self):

        self.preview_timer.stop()
        self.detector_timer.stop()

        try:
            if self.hCamera:
                mvsdk.CameraUnInit(self.hCamera)
        except:
            pass

        try:
            if self.pFrameBuffer:
                mvsdk.CameraAlignFree(self.pFrameBuffer)
        except:
            pass

        self.hCamera = None
        self.pFrameBuffer = None
        self.camera_open = False

        print("Camera stopped")

    # -------------------------
    # FRAME CAPTURE
    # -------------------------
    def get_frame(self):

        if not self.hCamera:
            return None

        try:

            pRawData, FrameHead = mvsdk.CameraGetImageBuffer(
                self.hCamera,
                200
            )

            mvsdk.CameraImageProcess(
                self.hCamera,
                pRawData,
                self.pFrameBuffer,
                FrameHead
            )

            mvsdk.CameraReleaseImageBuffer(self.hCamera, pRawData)

            if os.name == "nt":
                mvsdk.CameraFlipFrameBuffer(
                    self.pFrameBuffer,
                    FrameHead,
                    1
                )

            frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(
                self.pFrameBuffer
            )

            frame = np.frombuffer(frame_data, dtype=np.uint8)

            frame = frame.reshape(
                FrameHead.iHeight,
                FrameHead.iWidth,
                3
            )

            # ⭐ COLOR FIX FINAL
            frame = frame[:, :, ::-1]

            return frame.copy()

        except Exception as e:
            print("Frame error:", e)
            return None

    # -------------------------
    # PREVIEW
    # -------------------------
    def grab_preview(self):

        frame = self.get_frame()

        if frame is None:
            return

        self.last_frame = frame

        ok, jpg = cv2.imencode(".jpg", frame)

        if ok:

            b64 = base64.b64encode(jpg).decode("utf-8")

            self.frameUpdate.emit(
                "data:image/jpeg;base64," + b64
            )

    # -------------------------
    # DETECTION
    # -------------------------
    def run_detection(self):

        if not self.camera_open or self.last_frame is None:
            return

        frame = self.last_frame.copy()

        status, processed_img, _ = self.detector.process_image(frame)

        if processed_img is not None:

            ok, jpg = cv2.imencode(".jpg", processed_img)

            if ok:
                self.defectFound.emit(
                    "data:image/jpeg;base64," +
                    base64.b64encode(jpg).decode("utf-8")
                )

        if status == "good":
            self.good_count += 1
        elif status == "defect":
            self.bad_count += 1

        self.inspected += 1

        self.statsUpdate.emit(
            self.inspected,
            self.good_count,
            self.bad_count
        )
    def set_color_temp_mode(self):
        if not self.hCamera:
            return

        try:
            mvsdk.CameraSetWbMode(self.hCamera, 0)   # disable continuous WB
            mvsdk.CameraSetOnceWB(self.hCamera)      # run one-time WB
            print("Status: WB Once (One-shot)")
        except Exception as e:
            print(f"Status: WB set failed: {e}")