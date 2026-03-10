import cv2
import numpy as np
import os

class StripColorDetector:
    def __init__(self, image_folder, output_folder, reference_path,
                 min_gap=35, color_threshold=4.5, center_margin_percent=0.25,
                 valid_exts=(".png", ".jpg", ".jpeg", ".bmp", ".tif")): #uv:20,w:4

        self.image_folder = image_folder
        self.output_folder = output_folder
        self.reference_path = reference_path
        self.min_gap = min_gap
        self.color_threshold = color_threshold
        self.center_margin_percent = center_margin_percent
        self.valid_exts = valid_exts

        os.makedirs(self.output_folder, exist_ok=True)

        self.good_reference = np.load(self.reference_path)

        self.reference_strip_count = len(self.good_reference)

        print("Reference strips:", self.reference_strip_count)

    # ---------------- STRIP DETECTION ----------------
    def detect_strips(self, img):

        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        if np.mean(thresh) > 140:
            thresh = cv2.bitwise_not(thresh)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 3))
        mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        projection = np.sum(mask > 0, axis=1)

        projection = np.convolve(projection, np.ones(25) / 25, mode='same')

        candidates = np.argsort(projection)[::-1]

        strips = []

        for y in candidates:

            if projection[y] < 0.55 * np.max(projection):
                break

            if all(abs(y - c) > self.min_gap for c in strips):
                strips.append(y)

        strips = sorted(strips)

        print("Centers:", strips)

        return strips, projection

    # ---------------- COLOR CHECK ----------------
    def check_strip_color(self, strip_img, ref_a, ref_b):

        strip = cv2.GaussianBlur(strip_img, (5, 5), 0)

        pixels = strip.reshape(-1, 3)

        pixels = pixels[pixels[:, 0] > 40]

        mean_lab = np.mean(pixels, axis=0)

        cur_a = mean_lab[1]
        cur_b = mean_lab[2]

        distance = np.sqrt((cur_a - ref_a) ** 2 + (cur_b - ref_b) ** 2)

        return distance, cur_a, cur_b

    # ---------------- PROCESS IMAGE ----------------
    def process_image(self, img_input):

        # ---------------- READ IMAGE ----------------
        if isinstance(img_input, str):
            img = cv2.imread(img_input)
            filename = os.path.basename(img_input)
        else:
            img = img_input.copy()
            filename = "camera_frame.jpg"

        if img is None:
            return "error", None, None

        img = cv2.resize(img, (640, 480))
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

        h, w = img.shape[:2]

        output = img.copy()

        lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        strips, projection = self.detect_strips(img)

        if len(strips) != self.reference_strip_count:
            print("Strip count mismatch")
            return "error", output, strips

        defect_found = False

        for i, cy in enumerate(strips):

            peak = projection[cy]
            thresh_val = peak * 0.5

            y1 = cy
            y2 = cy

            while y1 > 0 and projection[y1] > thresh_val:
                y1 -= 1

            while y2 < h - 1 and projection[y2] > thresh_val:
                y2 += 1

            margin = int(w * self.center_margin_percent)

            x1 = margin
            x2 = w - margin

            strip = lab_img[y1:y2, x1:x2]

            if strip.size == 0:
                continue

            distance, cur_a, cur_b = self.check_strip_color(
                strip,
                self.good_reference[i][1],
                self.good_reference[i][2]
            )

            print(
                f"Strip {i+1} | ref_a={self.good_reference[i][1]:.2f} "
                f"ref_b={self.good_reference[i][2]:.2f} "
                f"cur_a={cur_a:.2f} cur_b={cur_b:.2f} "
                f"dist={distance:.2f}"
            )

            if distance > self.color_threshold:

                color = (0, 0, 255)
                label = f"Strip {i+1} BAD {distance:.2f}"

                defect_found = True

            else:

                color = (0, 255, 0)
                label = f"Strip {i+1} GOOD {distance:.2f}"

            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

            cv2.putText(
                output,
                label,
                (x1 + 5, max(20, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

        save_path = os.path.join(self.output_folder, filename)

        # cv2.imwrite(save_path, output)

        print("Processed:", filename)

        if defect_found:
            # cv2.imwrite(save_path, output)
            return "defect", output, strips
        else:
            return "good", output, strips