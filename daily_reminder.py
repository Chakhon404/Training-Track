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

def get_daily_status():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, None
        
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Bangkok Timezone (UTC+7)
    tz_bkk = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(tz_bkk)
    today = now_bkk.strftime("%Y-%m-%d")

    # 1. Fetch Latest Profile
    profile_res = supabase.table("user_profile").select("*").order("updated_at", desc=True).limit(1).maybe_single().execute()  
    if not profile_res.data:
        return None, None
    profile = profile_res.data

    # 2. Fetch Today's Nutrition
    nut_res = supabase.table("nutrition").select("*").gte("log_ts", f"{today}T00:00:00").execute()

    # Aggregate macros
    stats = {
        "calories": sum(item.get("calories", 0) or 0 for item in nut_res.data),
        "protein_g": sum(item.get("protein_g", 0) or 0 for item in nut_res.data),
        "carbs_g": sum(item.get("carbs_g", 0) or 0 for item in nut_res.data),
        "fat_g": sum(item.get("fat_g", 0) or 0 for item in nut_res.data),
    }

    # Check supplements
    default_sups = profile.get("default_supplements", [])
    taken_sups = set()
    for entry in nut_res.data:
        for sup in default_sups:
            if entry.get(sup):
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

    def get_diff(current, goal):
        goal = goal or 0
        current = current or 0
        diff = goal - current
        return max(0, diff)

    def format_val(val):
        return round(float(val or 0), 1)

    msg = f"🥊 สรุปรายงานวินัย: {today_str}\n"
    msg += f"────────────────\n"
    msg += f"สวัสดีครับคุณชาคร! วันนี้สู้ได้ดีแค่ไหน มาดูกัน!\n\n"
    
    msg += f"⚡ สรุปโภชนาการ (Macros)\n"
    
    # Calories
    goal_cal = profile.get('goal_calories') or 0
    curr_cal = stats['calories']
    diff_cal = get_diff(curr_cal, goal_cal)
    status_cal = "✅" if diff_cal == 0 else "⏳"
    msg += f"{status_cal} แคลอรี่: {format_val(curr_cal)}/{format_val(goal_cal)} kcal\n"
    if diff_cal > 0: msg += f"   └ ขาดอีก: {format_val(diff_cal)} kcal\n"
    
    # Protein
    goal_p = profile.get('goal_protein_g') or 0
    curr_p = stats['protein_g']
    diff_p = get_diff(curr_p, goal_p)
    status_p = "✅" if diff_p == 0 else "⏳"
    msg += f"{status_p} โปรตีน: {format_val(curr_p)}/{format_val(goal_p)} g\n"
    if diff_p > 0: msg += f"   └ ขาดอีก: {format_val(diff_p)} g\n"
    
    # Carbs
    goal_c = profile.get('goal_carbs_g') or 0
    curr_c = stats['carbs_g']
    diff_c = get_diff(curr_c, goal_c)
    status_c = "✅" if diff_c == 0 else "⏳"
    msg += f"{status_c} คาร์บ: {format_val(curr_c)}/{format_val(goal_c)} g\n"
    if diff_c > 0: msg += f"   └ ขาดอีก: {format_val(diff_c)} g\n"
    
    # Fat
    goal_f = profile.get('goal_fat_g') or 0
    curr_f = stats['fat_g']
    diff_f = get_diff(curr_f, goal_f)
    status_f = "✅" if diff_f == 0 else "⏳"
    msg += f"{status_f} ไขมัน: {format_val(curr_f)}/{format_val(goal_f)} g\n"
    if diff_f > 0: msg += f"   └ ขาดอีก: {format_val(diff_f)} g\n"
    
    msg += f"\n⚖️ สถิติร่างกาย\n"
    msg += f"• น้ำหนัก: {format_val(profile.get('weight_kg'))} kg\n"
    msg += f"• ไขมัน: {format_val(profile.get('body_fat_pct'))}%\n"
    
    msg += f"\n💊 การทานอาหารเสริม\n"
    if stats['missing_supplements']:
        for sup in stats['missing_supplements']:
            msg += f"• ⏳ {sup}\n"
    else:
        msg += f"🎉 สุดยอด! ทานอาหารเสริมครบทุกรายการ\n"
    
    msg += f"────────────────\n"
    msg += f"🎯 วินัยคือหัวใจ ลุยต่อ!"
    
    return msg

def send_line_message(message):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        return False
        
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        return res.status_code == 200
    except Exception:
        return False

if __name__ == "__main__":
    if not all([SUPABASE_URL, SUPABASE_KEY, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID]):
        print("Error: Missing environment variables.")
        exit(1)

    profile, stats = get_daily_status()
    msg = generate_summary_message(profile, stats)
    if send_line_message(msg):
        print("Reminder sent successfully.")
    else:
        print("Failed to send reminder.")
