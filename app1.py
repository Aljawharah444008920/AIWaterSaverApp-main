from flask import Flask, render_template, request
import os
import cv2
import numpy as np

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 7 * 1024 * 1024  # 7MB

FLOW_RATE = 0.12  # معدل تدفق الماء (لتر/ثانية)


def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if total_frames > 0 else 0

    back_sub = cv2.createBackgroundSubtractorMOG2(
        history=150,
        varThreshold=20,
        detectShadows=False
    )

    frame_count = 0
    active_frames = 0
    idle_frames = 0

    sampling_step = 5  # تحليل كل 5 فريمات

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # تحليل كامل الفيديو لكن بعينات
            if frame_count % sampling_step != 0:
                continue

            frame = cv2.resize(frame, (320, 240))
            h, w = frame.shape[:2]

            # ROI ذكي (وسط الحوض تقريبًا)
            x1 = int(w * 0.25)
            y1 = int(h * 0.30)
            x2 = int(w * 0.75)
            y2 = int(h * 0.90)

            roi = frame[y1:y2, x1:x2]

            fg_mask = back_sub.apply(roi)
            _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

            motion_pixels = cv2.countNonZero(thresh)
            total_pixels = thresh.shape[0] * thresh.shape[1]

            motion_ratio = motion_pixels / total_pixels

            # 👇 منطق ذكي محسّن
            if motion_ratio > 0.03:
                active_frames += 1  # استخدام فعلي
            elif motion_ratio > 0.01:
                idle_frames += 0.5  # حركة ضعيفة (هدر محتمل)
            else:
                idle_frames += 1  # هدر واضح

    except Exception as e:
        return {"error": str(e)}

    finally:
        cap.release()

    usage_time = round(active_frames * sampling_step / fps, 2)
    waste_time = round(idle_frames * sampling_step / fps, 2)

    used_water = round(usage_time * FLOW_RATE, 2)
    wasted_water = round(waste_time * FLOW_RATE, 2)

    total = used_water + wasted_water

    waste_percentage = round((wasted_water / total) * 100, 1) if total > 0 else 0
    efficiency = round(100 - waste_percentage, 1)

    # 👇 رسالة ذكية حسب الأداء
    if efficiency > 80:
        message = "استخدام ممتاز للمياه 💧"
    elif efficiency > 50:
        message = "يوجد هدر متوسط ⚠️"
    else:
        message = "هدر مرتفع يجب الانتباه 🚨"

    return {
        "video_duration": round(duration, 2),
        "usage_time": usage_time,
        "waste_time": waste_time,
        "used_water": used_water,
        "wasted_water": wasted_water,
        "waste_percentage": waste_percentage,
        "efficiency": efficiency,
        "message": message
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
                error="حجم الفيديو كبير جدًا، ارفعي فيديو أقل من 7MB"
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
    app.run(host="0.0.0.0", port=port)