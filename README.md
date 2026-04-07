# 💧 AI Water Saver App

## 📖 Overview
AI Water Saver is a smart web application designed to **reduce water waste during hand washing** using video analysis and artificial intelligence techniques.

The system allows users to upload a short video of hand washing, then analyzes it to measure water usage efficiency and provide personalized feedback.

---

## 🎯 Objectives
- Promote water conservation 💧  
- Raise awareness about daily water usage  
- Apply AI in a real-world environmental problem  
- Provide users with actionable insights  

---

## ⚙️ How It Works
1. User registers or logs into the system  
2. Uploads a short video (max 15 seconds)  
3. The system processes the video using OpenCV  
4. Extracts key metrics:
   - Actual usage time  
   - Water waste time  
   - Amount of water used  
   - Efficiency percentage  
5. Displays results with improvement tips  

---

## 🧠 Technologies Used
- Python  
- Flask (Web Framework)  
- OpenCV (Video Processing)  
- SQLite (Database)  
- Rasa (Chatbot Integration)  

---

## 📊 Data & Analysis
This project does **not rely on pre-collected datasets**. Instead, it performs **real-time video analysis**:

- Frame-by-frame processing  
- Motion detection using:
  - Background Subtraction  
  - Frame Differencing  
- Classification of frames into:
  - Active water usage  
  - Water waste  

### 🔢 Calculations:
- Water flow rate: `0.12 L/sec`  
- Used Water = Usage Time × Flow Rate  
- Waste Percentage = (Wasted Water ÷ Total Water)  

---

## 📁 Project Structure/
│
├── app.py # Main Flask application
├── actions.py # Rasa custom actions
├── config.yml # Rasa configuration
├── domain.yml # Bot intents & responses
├── endpoints.yml # Action server endpoint
│
├── data/ # Rasa training data
│ ├── nlu.yml
│ ├── stories.yml
│ └── rules.yml
│
├── templates/ # HTML pages
├── uploads/ # Temporary video storage
├── users.db # Database
└── models/ # Trained Rasa models


---

## ▶️ Running the Project

### 1. Run the Flask app
```bash
python app.py
2. Train and run Rasa
rasa train
rasa run
3. Run Action Server
rasa run actions
🚀 Features
Smart video-based water usage analysis
User authentication system
Real-time feedback and tips
Waste detection and efficiency calculation
Dashboard with user statistics

📌 Notes
Maximum video length: 15 seconds
