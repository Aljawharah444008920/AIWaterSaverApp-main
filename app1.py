from flask import Flask, render_template, request, redirect, url_for, session
import os
import cv2
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "ai_water_saver_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 7 * 1024 * 1024  # 7MB
FLOW_RATE = 0.12  # معدل تدفق الماء (لتر/ثانية)
DB_FILE = "users.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            video_duration REAL,
            usage_time REAL,
            waste_time REAL,
            used_water REAL,
            wasted_water REAL,
            waste_percentage REAL,
            efficiency REAL,
            message TEXT,
            advice TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


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

            if frame_count % sampling_step != 0:
                continue

            frame = cv2.resize(frame, (320, 240))
            h, w = frame.shape[:2]

            # منطقة الاهتمام في منتصف المشهد تقريبًا
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

            if motion_ratio > 0.03:
                active_frames += 1
            elif motion_ratio > 0.01:
                idle_frames += 0.5
            else:
                idle_frames += 1

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

    if efficiency > 80:
        message = "استخدام ممتاز للمياه 💧"
        advice = "استمر بنفس الطريقة، استخدامك للمياه فعّال جدًا."
    elif efficiency > 50:
        message = "يوجد هدر متوسط ⚠️"
        advice = "حاول تقليل وقت فتح الماء بدون استخدام فعلي."
    else:
        message = "هدر مرتفع يجب الانتباه 🚨"
        advice = "يجب إغلاق الماء أثناء فرك اليدين لتقليل الهدر."

    return {
        "video_duration": round(duration, 2),
        "usage_time": usage_time,
        "waste_time": waste_time,
        "used_water": used_water,
        "wasted_water": wasted_water,
        "waste_percentage": waste_percentage,
        "efficiency": efficiency,
        "message": message,
        "advice": advice
    }


def save_analysis(user_id, result):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO analyses (
            user_id, created_at, video_duration, usage_time, waste_time,
            used_water, wasted_water, waste_percentage, efficiency, message, advice
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        str(datetime.now()),
        result["video_duration"],
        result["usage_time"],
        result["waste_time"],
        result["used_water"],
        result["wasted_water"],
        result["waste_percentage"],
        result["efficiency"],
        result["message"],
        result["advice"]
    ))

    conn.commit()
    conn.close()


def is_logged_in():
    return "user_id" in session


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("register.html", error="الرجاء تعبئة جميع الحقول")

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="اسم المستخدم موجود مسبقًا")

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def upload():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("upload.html", error="لم يتم اختيار ملف", username=session.get("username"))

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            return render_template(
                "upload.html",
                error="حجم الفيديو كبير جدًا، ارفعي فيديو أقل من 7MB",
                username=session.get("username")
            )

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        result = analyze_video(filepath)

        if "error" in result:
            return render_template("upload.html", error=result["error"], username=session.get("username"))

        save_analysis(session["user_id"], result)

        return render_template("result.html", result=result, username=session.get("username"))

    return render_template("upload.html", username=session.get("username"))


@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cur.fetchone()["total_users"]

    cur.execute("SELECT COUNT(*) AS total_analyses FROM analyses")
    total_analyses = cur.fetchone()["total_analyses"]

    cur.execute("""
        SELECT AVG(efficiency) AS avg_efficiency,
               AVG(waste_percentage) AS avg_waste
        FROM analyses
    """)
    stats = cur.fetchone()

    cur.execute("""
        SELECT * FROM analyses
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (session["user_id"],))
    recent_results = cur.fetchall()

    conn.close()

    avg_efficiency = round(stats["avg_efficiency"], 1) if stats["avg_efficiency"] is not None else 0
    avg_waste = round(stats["avg_waste"], 1) if stats["avg_waste"] is not None else 0

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        total_users=total_users,
        total_analyses=total_analyses,
        avg_efficiency=avg_efficiency,
        avg_waste=avg_waste,
        recent_results=recent_results
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)