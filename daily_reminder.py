import os
import requests
import json
from datetime import datetime
import pytz
from supabase import create_client, Client
from dotenv import load_dotenv

# Load local .env for testing; GitHub Actions and Streamlit use their own secret managers
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def get_daily_status(supabase_client: Client = None):
    if not supabase_client:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return None, None
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        supabase = supabase_client

    # 1. จัดการเรื่องวันที่ (Bangkok Time)
    tz_bkk = pytz.timezone('Asia/Bangkok')
    today = datetime.now(tz_bkk).strftime("%Y-%m-%d")

    # 2. ดึง Profile ล่าสุด
    profile_res = supabase.table("user_profile").select("*").order("updated_at", desc=True).limit(1).maybe_single().execute()
    if not profile_res or not profile_res.data:
        return None, None
    profile = profile_res.data

    # 3. ดึงข้อมูล Nutrition โดยใช้ log_ts เป็นช่วงเวลา
    start_time = f"{today} 00:00:00"
    end_time = f"{today} 23:59:59"
    nut_res = supabase.table("nutrition").select("*").gte("log_ts", start_time).lte("log_ts", end_time).execute()

    # 4. สรุปผล Macros
    stats = {
        "calories": sum(item.get("calories", 0) or 0 for item in nut_res.data),
        "protein_g": sum(item.get("protein_g", 0) or 0 for item in nut_res.data),
        "carbs_g": sum(item.get("carbs_g", 0) or 0 for item in nut_res.data),
        "fat_g": sum(item.get("fat_g", 0) or 0 for item in nut_res.data),
    }

    # 5. เช็ครายการอาหารเสริม (Supplements)
    from modules.constants import SUPPLEMENT_MAP
    default_sups = profile.get("default_supplements", [])
    taken_sups = set()

    for entry in nut_res.data:
        for sup in default_sups:
            # sup is the json_key, we need the db_column from SUPPLEMENT_MAP
            db_col = SUPPLEMENT_MAP.get(sup, [None, None, sup])[2]
            if bool(entry.get(db_col)):
                taken_sups.add(sup)

    missing_sups = [s for s in default_sups if s not in taken_sups]
    stats["missing_supplements"] = missing_sups

    return profile, stats

def generate_summary_message(profile, stats):
    if not profile or not stats:
        return "❌ ไม่พบข้อมูลโปรไฟล์หรือโภชนาการสำหรับวันนี้"

    # Bangkok Timezone (UTC+7)
    tz_bkk = pytz.timezone('Asia/Bangkok')
    today_str = datetime.now(tz_bkk).strftime("%d/%m/%Y")

    def format_val(val):
        """ลบทศนิยมถ้าเป็น .0 และใส่ลูกน้ำ"""
        num = float(val or 0)
        return f"{int(num):,}" if num.is_integer() else f"{num:,.1f}"

    def create_progress_bar(current, goal, length=10):
        """สร้าง Text-based Progress Bar"""
        goal = goal or 1 # ป้องกันหารด้วย 0
        current = current or 0
        percent = min(current / goal, 1.0)
        filled_len = int(length * percent)
        bar = '█' * filled_len + '░' * (length - filled_len)
        # คำนวณ % จริงโชว์ด้านหลัง เผื่อกินทะลุ 100%
        actual_percent = int((current / goal) * 100)
        return f"[{bar}] {actual_percent}%"

    def get_status_text(current, goal, unit):
        """เช็คสถานะ ขาด/พอดี/เกิน"""
        goal = goal or 0
        current = current or 0
        diff = goal - current
        
        if diff > 0:
            return f"   ⏳ (ขาดอีก: {format_val(diff)} {unit})"
        elif diff < 0:
            return f"   ⚠️ (ทะลุเป้าไป: {format_val(abs(diff))} {unit})"
        else:
            return f"   ✅ (พอดีเป้าหมายเป๊ะ!)"

    msg = f"📊 Daily Check-in: {today_str}\n"
    msg += f"สวัสดีครับคุณชาคร! มาดูผลลัพธ์ของวันนี้กันครับ 💪\n\n"

    msg += f"🎯 สรุปโภชนาการ (Macros)\n"

    # Calories
    goal_cal = profile.get('goal_calories') or 0
    curr_cal = stats['calories']
    msg += f"🔥 แคลอรี่: {format_val(curr_cal)} / {format_val(goal_cal)} kcal\n"
    msg += f"   {create_progress_bar(curr_cal, goal_cal)}\n"
    msg += f"{get_status_text(curr_cal, goal_cal, 'kcal')}\n\n"

    # Protein
    goal_p = profile.get('goal_protein_g') or 0
    curr_p = stats['protein_g']
    msg += f"🥩 โปรตีน: {format_val(curr_p)} / {format_val(goal_p)} g\n"
    msg += f"   {create_progress_bar(curr_p, goal_p)}\n"
    msg += f"{get_status_text(curr_p, goal_p, 'g')}\n\n"

    # Carbs
    goal_c = profile.get('goal_carbs_g') or 0
    curr_c = stats['carbs_g']
    msg += f"🍚 คาร์บ: {format_val(curr_c)} / {format_val(goal_c)} g\n"
    msg += f"   {create_progress_bar(curr_c, goal_c)}\n"
    msg += f"{get_status_text(curr_c, goal_c, 'g')}\n\n"

    # Fat
    goal_f = profile.get('goal_fat_g') or 0
    curr_f = stats['fat_g']
    msg += f"🥑 ไขมัน: {format_val(curr_f)} / {format_val(goal_f)} g\n"
    msg += f"   {create_progress_bar(curr_f, goal_f)}\n"
    msg += f"{get_status_text(curr_f, goal_f, 'g')}\n"

    # Supplements
    missing = stats.get("missing_supplements", [])
    msg += f"\n💊 อาหารเสริม (Supplements)\n"
    if not missing:
        msg += f"✅ ทานครบทุกรายการแล้ว สุดยอดครับ!\n"
    else:
        msg += f"⚠️ ยังขาดอีก {len(missing)} รายการ:\n"
        from modules.constants import SUPPLEMENT_MAP
        for m in missing:
            display_name = SUPPLEMENT_MAP.get(m, [m, None, None])[0]
            msg += f"   - {display_name}\n"

    msg += f"\n✨ ลุยต่อไปครับ พรุ่งนี้เอาใหม่ให้ดีกว่าเดิม! 🚀"
    
    return msg

def send_line_notification(message):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE configuration missing.")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("Notification sent successfully.")
        return True
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return False

if __name__ == "__main__":
    profile, stats = get_daily_status()
    if profile:
        message = generate_summary_message(profile, stats)
        send_line_notification(message)
    else:
        print("Could not fetch daily status.")