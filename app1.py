from flask import Flask, render_template, request
import os
import cv2
import numpy as np

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 3 * 1024 * 1024  # 3MB لتخفيف الضغط على الاستضافة

# منطقة الاهتمام عند الحوض/الصنبور
ROI_X1 = 80
ROI_Y1 = 60
ROI_X2 = 560
ROI_Y2 = 420

# معدل تدفق تقديري للماء (لتر/ثانية)
FLOW_RATE_LPS = 0.10


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
    active_frames = 0
    idle_frames = 0
    max_analyzed_frames = 15

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # تحليل كل 20 فريم فقط
            if frame_count % 20 != 0:
                continue

            if analyzed_frames >= max_analyzed_frames:
                break

            analyzed_frames += 1

            frame = cv2.resize(frame, (256, 192))

            h, w = frame.shape[:2]

            # ضبط الـ ROI بحيث يناسب المقاس الجديد
            x1 = min(ROI_X1, w - 1)
            y1 = min(ROI_Y1, h - 1)
            x2 = min(ROI_X2, w)
            y2 = min(ROI_Y2, h)

            if x2 <= x1 or y2 <= y1:
                continue

            roi = frame[y1:y2, x1:x2]

            fg_mask = back_sub.apply(roi)
            _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

            motion_pixels = cv2.countNonZero(thresh)
            motion_ratio = motion_pixels / float(thresh.shape[0] * thresh.shape[1])

            # وجود حركة واضحة داخل منطقة الحوض
            if motion_ratio > 0.02:
                active_frames += 1
            else:
                idle_frames += 1

    except Exception as e:
        return {"error": str(e)}

    finally:
        cap.release()

    usage_time = round(active_frames * 20 / fps, 2)
    waste_time = round(idle_frames * 20 / fps * 0.3, 2)

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
                error="حجم الفيديو كبير جدًا، ارفع فيديو قصير جدًا وأصغر من 3MB"
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