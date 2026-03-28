from flask import Flask, render_template, request
import os
import cv2
import mediapipe as mp
import numpy as np

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=0,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# منطقة الاهتمام عند الحوض/الصنبور
ROI_X1 = 80
ROI_Y1 = 60
ROI_X2 = 560
ROI_Y2 = 420

# معدل تدفق تقديري للماء (لتر/ثانية)
FLOW_RATE_LPS = 0.10


def point_in_roi(x, y):
    return ROI_X1 <= x <= ROI_X2 and ROI_Y1 <= y <= ROI_Y2


def hand_near_sink(frame_rgb, frame_w, frame_h):
    results = hands.process(frame_rgb)

    if not results.multi_hand_landmarks:
        return False

    for hand_landmarks in results.multi_hand_landmarks:
        wrist = hand_landmarks.landmark[0]
        index_tip = hand_landmarks.landmark[8]

        points = [
            (int(wrist.x * frame_w), int(wrist.y * frame_h)),
            (int(index_tip.x * frame_w), int(index_tip.y * frame_h)),
        ]

        for px, py in points:
            if point_in_roi(px, py):
                return True

    return False


def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps if total_frames > 0 else 0

    back_sub = cv2.createBackgroundSubtractorMOG2(
        history=100,
        varThreshold=25,
        detectShadows=False
    )

    frame_count = 0
    analyzed_frames = 0
    hand_frames = 0
    waste_frames = 0
    max_analyzed_frames = 120

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # تحليل كل 8 فريمات فقط لتخفيف الحمل
            if frame_count % 8 != 0:
                continue

            if analyzed_frames >= max_analyzed_frames:
                break

            analyzed_frames += 1

            frame = cv2.resize(frame, (640, 480))
            frame_h, frame_w = frame.shape[:2]

            # قص منطقة الحوض/الصنبور
            roi = frame[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]

            # اكتشاف الحركة داخل المنطقة
            fg_mask = back_sub.apply(roi)
            _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

            motion_pixels = cv2.countNonZero(thresh)
            motion_ratio = motion_pixels / float(thresh.shape[0] * thresh.shape[1])
            motion_active = motion_ratio > 0.015

            # اكتشاف اليد
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hand_present = hand_near_sink(frame_rgb, frame_w, frame_h)

            # منطق التحليل
            if hand_present and motion_active:
                hand_frames += 1
            elif motion_active and not hand_present:
                waste_frames += 1

    except Exception as e:
        return {"error": str(e)}

    finally:
        cap.release()

    usage_time = round(hand_frames * 8 / fps, 2)
    waste_time = round(waste_frames * 8 / fps, 2)

    used_water = round(usage_time * FLOW_RATE_LPS, 2)
    wasted_water = round(waste_time * FLOW_RATE_LPS, 2)

    total_measured_water = used_water + wasted_water
    if total_measured_water > 0:
        waste_percentage = round((wasted_water / total_measured_water) * 100, 1)
    else:
        waste_percentage = 0.0

    efficiency = round(100 - waste_percentage, 1)

    return {
        "video_duration": round(video_duration, 2),
        "usage_time": usage_time,
        "waste_time": waste_time,
        "used_water": used_water,
        "wasted_water": wasted_water,
        "waste_percentage": waste_percentage,
        "efficiency": efficiency,
        "analyzed_frames": analyzed_frames,
        "message": "تم التحليل بنجاح"
    }


@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("upload.html", error="لم يتم اختيار ملف")

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            return render_template(
                "upload.html",
                error="حجم الفيديو كبير جدًا، ارفعي فيديو أصغر من 10MB"
            )

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        result = analyze_video(filepath)

        if "error" in result:
            return render_template("upload.html", error=result["error"])

        return render_template("result.html", result=result)

    return render_template("upload.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)