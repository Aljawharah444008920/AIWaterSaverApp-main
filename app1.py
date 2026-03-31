from flask import Flask, render_template, request, redirect, session
import os
import cv2
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 7 * 1024 * 1024  # 7MB
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}
FLOW_RATE = 0.12  # لتر/ثانية


# =========================
# Database
# =========================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        efficiency REAL,
        waste REAL,
        usage_time REAL,
        waste_time REAL,
        used_water REAL,
        wasted_water REAL,
        confidence REAL,
        advice TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# Helpers
# =========================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# Improved OpenCV analysis
# =========================
def analyze_video(path):
    cap = cv2.VideoCapture(path)

    if not cap.isOpened():
        return {"error": "تعذر فتح ملف الفيديو"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if total_frames > 0 else 0

    max_duration = 15  # ثواني
    if duration > max_duration:
        cap.release()
        return {"error": "الفيديو طويل، الحد الأقصى 15 ثانية"}

    back_sub = cv2.createBackgroundSubtractorMOG2(
        history=200,
        varThreshold=16,
        detectShadows=False
    )

    prev_gray = None
    active_frames = 0
    waste_frames = 0
    processed_frames = 0

    sampling_step = 6  # أخف على السيرفر

    try:
        frame_index = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_index += 1

            if frame_index % sampling_step != 0:
                continue

            processed_frames += 1

            # تصغير أكبر لتخفيف الحمل
            frame = cv2.resize(frame, (240, 180))
            h, w = frame.shape[:2]

            # ROI في منتصف وأسفل المشهد
            x1 = int(w * 0.22)
            y1 = int(h * 0.28)
            x2 = int(w * 0.78)
            y2 = int(h * 0.95)

            roi = frame[y1:y2, x1:x2]

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)

            fg_mask = back_sub.apply(gray)
            _, fg_thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
            fg_motion = cv2.countNonZero(fg_thresh)

            diff_motion = 0
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                _, diff_thresh = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
                diff_thresh = cv2.medianBlur(diff_thresh, 5)
                diff_motion = cv2.countNonZero(diff_thresh)

            prev_gray = gray.copy()

            total_pixels = gray.shape[0] * gray.shape[1]
            fg_ratio = fg_motion / total_pixels if total_pixels else 0
            diff_ratio = diff_motion / total_pixels if total_pixels else 0

            motion_score = (fg_ratio * 0.6) + (diff_ratio * 0.4)

            if motion_score > 0.05:
                active_frames += 1
            elif motion_score > 0.02:
                waste_frames += 0.5
            else:
                waste_frames += 1

    except Exception as e:
        return {"error": str(e)}

    finally:
        cap.release()

    if processed_frames == 0:
        return {"error": "لم يتمكن النظام من تحليل الفيديو"}

    usage_time = round(active_frames * sampling_step / fps, 2)
    waste_time = round(waste_frames * sampling_step / fps, 2)

    used_water = round(usage_time * FLOW_RATE, 2)
    wasted_water = round(waste_time * FLOW_RATE, 2)

    total_water = used_water + wasted_water
    waste_percentage = round((wasted_water / total_water) * 100, 1) if total_water > 0 else 0
    efficiency = round(100 - waste_percentage, 1)

    if processed_frames >= 25:
        confidence = 90
    elif processed_frames >= 12:
        confidence = 80
    else:
        confidence = 70

    if efficiency >= 80:
        message = "استخدام ممتاز للمياه 💧"
        advice = "استمر بنفس الطريقة، استخدامك للمياه فعّال جدًا."
    elif efficiency >= 50:
        message = "يوجد هدر متوسط ⚠️"
        advice = "حاول تقليل وقت فتح الماء بدون استخدام فعلي."
    else:
        message = "هدر مرتفع يجب الانتباه 🚨"
        advice = "يفضل إغلاق الماء أثناء فرك اليدين لتقليل الهدر."

    return {
        "video_duration": round(duration, 2),
        "usage_time": usage_time,
        "waste_time": waste_time,
        "used_water": used_water,
        "wasted_water": wasted_water,
        "waste_percentage": waste_percentage,
        "efficiency": efficiency,
        "confidence": confidence,
        "message": message,
        "advice": advice
    }


# =========================
# Auth
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"].strip()
        pw = request.form["password"].strip()

        if len(user) < 3:
            return render_template("register.html", error="اسم المستخدم قصير جدًا")

        if len(pw) < 6:
            return render_template("register.html", error="كلمة المرور يجب أن تكون 6 أحرف أو أكثر")

        pw_hash = generate_password_hash(pw)

        conn = sqlite3.connect("users.db")
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users (username,password) VALUES (?,?)", (user, pw_hash))
            conn.commit()
        except:
            conn.close()
            return render_template("register.html", error="اسم المستخدم موجود مسبقًا")

        conn.close()
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"].strip()
        pw = request.form["password"].strip()

        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (user,))
        data = cur.fetchone()
        conn.close()

        if data and check_password_hash(data[2], pw):
            session["user_id"] = data[0]
            session["username"] = data[1]
            return redirect("/")
        else:
            return render_template("login.html", error="بيانات الدخول غير صحيحة")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# Main
# =========================
@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("upload.html", username=session["username"], error="لم يتم اختيار ملف")

        if not allowed_file(file.filename):
            return render_template("upload.html", username=session["username"], error="صيغة الملف غير مدعومة")

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            return render_template("upload.html", username=session["username"], error="حجم الفيديو أكبر من 7MB")

        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        result = analyze_video(path)

        # حذف الملف بعد التحليل لتخفيف التخزين
        try:
            os.remove(path)
        except:
            pass

        if "error" in result:
            return render_template("upload.html", username=session["username"], error=result["error"])

        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO results (
            user_id, efficiency, waste, usage_time, waste_time,
            used_water, wasted_water, confidence, advice, date
        )
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            session["user_id"],
            result["efficiency"],
            result["waste_percentage"],
            result["usage_time"],
            result["waste_time"],
            result["used_water"],
            result["wasted_water"],
            result["confidence"],
            result["advice"],
            str(datetime.now())
        ))
        conn.commit()
        conn.close()

        return render_template("result.html", result=result, username=session["username"])

    return render_template("upload.html", username=session["username"])


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM results")
    total_results = cur.fetchone()[0]

    cur.execute("SELECT AVG(efficiency) FROM results")
    avg_efficiency = cur.fetchone()[0]
    avg_efficiency = round(avg_efficiency, 1) if avg_efficiency else 0

    cur.execute("SELECT AVG(waste) FROM results")
    avg_waste = cur.fetchone()[0]
    avg_waste = round(avg_waste, 1) if avg_waste else 0

    cur.execute("""
        SELECT efficiency, waste, usage_time, wasted_water, confidence, date
        FROM results
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))
    data = cur.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        data=data,
        username=session["username"],
        total_users=total_users,
        total_results=total_results,
        avg_efficiency=avg_efficiency,
        avg_waste=avg_waste
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)