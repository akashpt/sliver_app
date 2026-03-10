import cv2
import numpy as np
import os


class GoodStripReferenceGenerator:
    def __init__(self,
                 good_image_folder,
                 reference_save_path,
                 expected_strips=3,
                 min_gap=35,
                 center_margin_percent=0.25,
                 valid_exts=(".png", ".jpg", ".jpeg", ".bmp", ".tif")):

        self.good_image_folder = good_image_folder
        self.reference_save_path = reference_save_path
        self.expected_strips = expected_strips
        self.min_gap = min_gap
        self.center_margin_percent = center_margin_percent
        self.valid_exts = valid_exts

    # ---------------- STRIP DETECTION ----------------
    def detect_strips(self, img):

        img = cv2.resize(img, (640, 480))
        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        if np.mean(thresh) > 150:
            thresh = cv2.bitwise_not(thresh)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 3))
        mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        projection = np.sum(mask > 0, axis=1)
        projection = np.convolve(projection, np.ones(15) / 15, mode="same")

        candidates = np.argsort(projection)[::-1]
        centers = []

        for y in candidates:

            if projection[y] < 0.55 * np.max(projection):
                break

            if all(abs(y - c) > self.min_gap for c in centers):
                centers.append(y)

            if len(centers) == self.expected_strips:
                break

        centers = sorted(centers)

        return centers, projection, img

    # ---------------- EXTRACT LAB ----------------
    def extract_strip_means(self, img):

        centers, projection, img = self.detect_strips(img)

        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

        h, w = img.shape[:2]
        lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        strip_means = []

        for cy in centers:

            y1 = cy
            y2 = cy

            peak = projection[cy]
            thresh_val = peak * 0.5

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

            strip = cv2.GaussianBlur(strip, (5, 5), 0)

            pixels = strip.reshape(-1, 3)
            pixels = pixels[pixels[:, 0] > 40]

            mean_lab = np.mean(pixels, axis=0)

            strip_means.append(mean_lab)

        print("Centers:", centers)

        return np.array(strip_means), centers

    # ---------------- GENERATE REFERENCE ----------------
    def generate_reference(self):

        all_strips = []
        strip_counts = []

        for filename in os.listdir(self.good_image_folder):

            if filename.lower().endswith(self.valid_exts):

                path = os.path.join(self.good_image_folder, filename)

                img = cv2.imread(path)

                if img is None:
                    continue

                means, centers = self.extract_strip_means(img)

                strip_counts.append(len(centers))

                print(filename, "→ strips:", len(centers))

                all_strips.append(means)

        all_strips = np.array(all_strips)

        good_reference = np.mean(all_strips, axis=0)

        np.save(self.reference_save_path, good_reference)

        print("\n✅ GOOD reference saved")
        print("Strip count:", len(good_reference))

        return good_reference


if __name__ == "__main__":

    generator = GoodStripReferenceGenerator(

        good_image_folder=r"D:\Camera_SDK\ui_mind_vision\snapshots\3",

        reference_save_path=r"D:\sliver_app\new.npy",

        expected_strips=8,

        min_gap=35,

        center_margin_percent=0.25
    )

    generator.generate_reference()



