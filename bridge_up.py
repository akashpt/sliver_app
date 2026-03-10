import os
import cv2
import base64
import numpy as np
import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
from predict_d import StripColorDetector
from train_d import GoodStripReferenceGenerator

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

    trainingStatus = pyqtSignal(str)
    trainingFinished = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # -------------------------
        # PATHS / TRAINING CONFIG
        # -------------------------
        self.reference_path = r"D:\sliver_app\new.npy"

        # base folder where captured training images will be saved
        self.training_base_folder = r"D:\sliver_app\training_data"

        # current selected training color folder name
        self.training_color_name = "orange"

        # full training folder path
        self.training_folder = os.path.join(
            self.training_base_folder,
            self.training_color_name
        )

        # reference output path
        self.reference_save_path = os.path.join(
            self.training_folder,
            "good_lab_reference.npy"
        )

        # training state
        self.training_running = False
        self.training_capture_interval = 3.0       # seconds
        self.training_last_save_time = 0.0
        self.training_saved_count = 0

        self.detector = StripColorDetector(
            image_folder=".",
            output_folder="defects_image",
            reference_path=self.reference_path,
            color_threshold=1.5
        )

        self.hCamera = None
        self.pFrameBuffer = None
        self.frame_buffer_size = 0
        self.camera_open = False
        self.mono = False

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
        self.stopDetection()

        try:
            devs = mvsdk.CameraEnumerateDevice()

            if not devs:
                print("No camera found")
                self.trainingStatus.emit("No camera found")
                return

            dev = devs[0]
            self.hCamera = mvsdk.CameraInit(dev, -1, -1)

            cap = mvsdk.CameraGetCapability(self.hCamera)
            self.mono = (cap.sIspCapacity.bMonoSensor != 0)

            if self.mono:
                mvsdk.CameraSetIspOutFormat(
                    self.hCamera,
                    mvsdk.CAMERA_MEDIA_TYPE_MONO8
                )
            else:
                mvsdk.CameraSetIspOutFormat(
                    self.hCamera,
                    mvsdk.CAMERA_MEDIA_TYPE_BGR8
                )

            # acquisition settings
            mvsdk.CameraSetTriggerMode(self.hCamera, 0)
            mvsdk.CameraSetAeState(self.hCamera, 0)
            mvsdk.CameraSetExposureTime(self.hCamera, 64068)

            if not self.mono:
                try:
                    mvsdk.CameraSetGain(self.hCamera, 100, 100, 100)
                    mvsdk.CameraSetColorCorrection(self.hCamera, 1)
                except Exception as e:
                    print("ISP config error:", e)

            mvsdk.CameraPlay(self.hCamera)

            if not self.mono:
                self.set_color_temp_mode()

            wmax = cap.sResolutionRange.iWidthMax
            hmax = cap.sResolutionRange.iHeightMax

            self.frame_buffer_size = int(wmax * hmax * (1 if self.mono else 3))

            self.pFrameBuffer = mvsdk.CameraAlignMalloc(
                self.frame_buffer_size,
                16
            )

            self.camera_open = True
            self.last_frame = None

            self.preview_timer.start(80)
            self.detector_timer.start()

            print("Camera started")
            self.trainingStatus.emit("Camera started")

        except Exception as e:
            print("Camera start error:", e)
            self.trainingStatus.emit(f"Camera start error: {e}")
            self.stopDetection()

    # -------------------------
    # STOP CAMERA
    # -------------------------
    @pyqtSlot()
    def stopDetection(self):
        self.preview_timer.stop()
        self.detector_timer.stop()

        try:
            if self.hCamera:
                mvsdk.CameraUnInit(self.hCamera)
        except Exception as e:
            print("Camera uninit error:", e)

        try:
            if self.pFrameBuffer:
                mvsdk.CameraAlignFree(self.pFrameBuffer)
        except Exception as e:
            print("Buffer free error:", e)

        self.hCamera = None
        self.pFrameBuffer = None
        self.frame_buffer_size = 0
        self.camera_open = False
        self.last_frame = None
        self.mono = False

        # if camera stopped during training, cancel training capture
        self.training_running = False

        print("Camera stopped")

    # -------------------------
    # ONE-TIME WHITE BALANCE
    # -------------------------
    def set_color_temp_mode(self):
        if not self.hCamera:
            return

        try:
            mvsdk.CameraSetWbMode(self.hCamera, 0)
            mvsdk.CameraSetOnceWB(self.hCamera)
            print("Status: WB Once (One-shot)")
        except Exception as e:
            print(f"Status: WB set failed: {e}")

    # -------------------------
    # FRAME CAPTURE
    # -------------------------
    def get_frame(self):
        if not self.hCamera or not self.pFrameBuffer:
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

            if self.mono:
                frame = frame.reshape(
                    FrameHead.iHeight,
                    FrameHead.iWidth
                )
            else:
                frame = frame.reshape(
                    FrameHead.iHeight,
                    FrameHead.iWidth,
                    3
                )

            return frame.copy()

        except Exception as e:
            print("Frame error:", e)
            return None

    # -------------------------
    # SAVE TRAINING FRAME
    # -------------------------
    def save_training_frame(self, frame):
        try:
            os.makedirs(self.training_folder, exist_ok=True)

            filename = f"{self.training_color_name}_{self.training_saved_count + 1:04d}.png"
            save_path = os.path.join(self.training_folder, filename)

            ok = cv2.imwrite(save_path, frame)
            if ok:
                self.training_saved_count += 1

                msg = f"Captured image {self.training_saved_count}: {filename}"
                print(msg)
                self.trainingStatus.emit(msg)

                # show only the saved training image in live feed
                ok2, jpg = cv2.imencode(".jpg", frame)
                if ok2:
                    b64 = base64.b64encode(jpg).decode("utf-8")
                    self.frameUpdate.emit("data:image/jpeg;base64," + b64)

            else:
                self.trainingStatus.emit(f"Failed to save image: {filename}")

        except Exception as e:
            print("Training frame save error:", e)
            self.trainingStatus.emit(f"Training frame save error: {e}")

    # -------------------------
    # PREVIEW
    # -------------------------
    def grab_preview(self):
        frame = self.get_frame()

        if frame is None:
            return

        self.last_frame = frame

        # training capture every 0.3 sec
        if self.training_running:
            now = time.time()
            if (now - self.training_last_save_time) >= self.training_capture_interval:
                self.training_last_save_time = now
                self.save_training_frame(frame)
            return

        ok, jpg = cv2.imencode(".jpg", frame)
        if ok:
            b64 = base64.b64encode(jpg).decode("utf-8")
            self.frameUpdate.emit("data:image/jpeg;base64," + b64)

    # -------------------------
    # DETECTION
    # -------------------------
    def run_detection(self):
        if not self.camera_open or self.last_frame is None:
            return

        frame = self.last_frame.copy()

        status, processed_img, _ = self.detector.process_image(frame)

        if status == "good":
            self.good_count += 1
        elif status == "defect":
            self.bad_count += 1
            if processed_img is not None:
                ok, jpg = cv2.imencode(".jpg", processed_img)
                if ok:
                    self.defectFound.emit(
                        "data:image/jpeg;base64," +
                        base64.b64encode(jpg).decode("utf-8")
                    )

        

        self.inspected += 1

        self.statsUpdate.emit(
            self.inspected,
            self.good_count,
            self.bad_count
        )

    # -------------------------
    # START TRAINING
    # -------------------------
    @pyqtSlot()
    def startTraining(self):
        print("startTraining called, camera_open =", self.camera_open)

        if self.training_running:
            print("Training already running")
            self.trainingStatus.emit("Training already running")
            return

        # Auto-start camera if not already running
        if not self.camera_open:
            print("Camera not started. Starting camera now...")
            self.trainingStatus.emit("Camera not started. Starting camera now...")
            self.startDetection()

        # Check again after trying to start
        if not self.camera_open:
            print("Failed to start camera")
            self.trainingStatus.emit("Failed to start camera")
            return

        # prepare training folder
        self.training_folder = os.path.join(
            self.training_base_folder,
            self.training_color_name
        )

        os.makedirs(self.training_folder, exist_ok=True)

        self.reference_save_path = os.path.join(
            self.training_folder,
            "good_lab_reference.npy"
        )

        self.training_running = True
        self.training_saved_count = 0
        self.training_last_save_time = 0.0

        msg = f"Training capture started. Saving every 0.3 sec to: {self.training_folder}"
        print(msg)
        self.trainingStatus.emit(msg)

    # -------------------------
    # STOP TRAINING
    # -------------------------
    @pyqtSlot()
    def stopTraining(self):
        if not self.training_running:
            print("Training is not running")
            self.trainingStatus.emit("Training is not running")
            return

        self.training_running = False
        self.trainingStatus.emit("Training capture stopped. Generating reference...")
        print("Training capture stopped. Generating reference...")

        self.run_training_generator()

    # -------------------------
    # RUN GENERATOR
    # -------------------------
    def run_training_generator(self):
        try:
            image_files = [
                f for f in os.listdir(self.training_folder)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif"))
            ]

            if not image_files:
                msg = "Training failed: no captured images found"
                print(msg)
                self.trainingStatus.emit(msg)
                return

            generator = GoodStripReferenceGenerator(
                good_image_folder=self.training_folder,
                reference_save_path=self.reference_save_path,
                expected_strips=8,
                min_gap=35,
                center_margin_percent=0.25
            )

            good_reference = generator.generate_reference()

            msg = f"Training completed. Reference saved: {self.reference_save_path}"
            print(msg)
            print("Reference strips:", len(good_reference))

            self.trainingFinished.emit(msg)
            self.trainingStatus.emit(msg)

        except Exception as e:
            err = f"Training failed: {e}"
            print(err)
            self.trainingStatus.emit(err)