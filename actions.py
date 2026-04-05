from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from app import analyze_video  # استدعاء دالة تحليل الفيديو من Flask app

class ActionCheckWaterUsage(Action):
    def name(self) -> str:
        return "action_check_water_usage"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # هنا نحدد مسار الفيديو للتحليل
        # ممكن يكون الفيديو مرفوع مسبقًا أو اسم ثابت للتجربة
        video_path = "uploads/test.mp4"

        result = analyze_video(video_path)

        if "error" in result:
            dispatcher.utter_message(text=f"❌ حدث خطأ: {result['error']}")
        else:
            message = (
                f"💧 استهلاك الماء: {result['used_water']} لتر\n"
                f"⏱️ مدة الاستخدام الفعلي: {result['usage_time']} ثانية\n"
                f"⏱️ مدة الهدر: {result['waste_time']} ثانية\n"
                f"📊 الكفاءة: {result['efficiency']}%\n"
                f"⚠️ النصيحة: {result['advice']}"
            )
            dispatcher.utter_message(text=message)

        return []