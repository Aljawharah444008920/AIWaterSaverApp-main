# 📊 Data Overview – AI Water Saver Chatbot

## 📖 Description
This folder contains the training data used for the chatbot built with Rasa.  
The data is designed to help the chatbot understand user inputs related to water usage analysis and provide appropriate responses.

---

## 📁 Files Included

### 1. `nlu.yml`
Contains Natural Language Understanding (NLU) training data:
- Defines user intents (what the user wants)
- Provides example phrases for each intent

#### Example intents:
- `greet` → Greetings from the user  
- `goodbye` → Ending conversation  
- `check_water_usage` → Asking about water usage analysis  

---

### 2. `stories.yml`
Defines conversation flows (dialogue paths):
- Shows how the chatbot should respond step-by-step
- Connects user intents to actions or responses  

---

### 3. `rules.yml`
Defines strict rules for predictable responses:
- Used for simple interactions like greetings and goodbyes  
- Ensures consistent behavior  

---

## 🧠 How the Data Works

The chatbot processes user input in the following way:

1. The user sends a message  
2. The NLU model classifies the intent  
3. Based on the intent:
   - A predefined response is triggered  
   - Or a custom action is executed  

---

## 🔗 Integration with the System

- The intent `check_water_usage` is linked to a custom action:
-  This action connects the chatbot with the video analysis system (Flask + OpenCV)

---

## ✨ Data Design Approach

- Simple and focused intents  
- Realistic Arabic user inputs  
- Designed specifically for:
- Water usage analysis  
- User assistance  
- Error handling  

---
