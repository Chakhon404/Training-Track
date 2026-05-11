import os
import requests
import json
from datetime import datetime, timedelta, timezone
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
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Bangkok Timezone (UTC+7)
    tz_bkk = timezone(timedelta(hours=7))
    now_bkk = datetime.now(tz_bkk)
    today = now_bkk.strftime("%Y-%m-%d")
    
    # 1. Fetch Latest Profile
    profile_res = supabase.table("user_profile").select("*").order("updated_at", desc=True).limit(1).execute()
    if not profile_res.data:
        return None, None
    profile = profile_res.data[0]
    
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
        return "ไม่พบข้อมูลโปรไฟล์หรือโภชนาการสำหรับวันนี้"

    def get_diff(current, goal):
        goal = goal or 0
        current = current or 0
        diff = goal - current
        return max(0, diff)

    msg = f"ชาคร\nสรุปโภชนาการวันนี้:\n"
    
    # Calories
    goal_cal = profile.get('goal_calories') or 0
    diff_cal = get_diff(stats['calories'], goal_cal)
    msg += f"- แคลอรี่: {int(stats['calories'])}/{int(goal_cal)} kcal (ขาดอีก {int(diff_cal)} kcal)\n"
    
    # Protein
    goal_p = profile.get('goal_protein_g') or 0
    diff_p = get_diff(stats['protein_g'], goal_p)
    msg += f"- โปรตีน: {int(stats['protein_g'])}/{int(goal_p)} g (ขาดอีก {int(diff_p)} g)\n"
    
    # Carbs
    goal_c = profile.get('goal_carbs_g') or 0
    diff_c = get_diff(stats['carbs_g'], goal_c)
    msg += f"- คาร์บ: {int(stats['carbs_g'])}/{int(goal_c)} g (ขาดอีก {int(diff_c)} g)\n"
    
    # Fat
    goal_f = profile.get('goal_fat_g') or 0
    diff_f = get_diff(stats['fat_g'], goal_f)
    msg += f"- ไขมัน: {int(stats['fat_g'])}/{int(goal_f)} g (ขาดอีก {int(diff_f)} g)\n"
    
    msg += f"\nสถิติร่างกาย:\n"
    msg += f"- น้ำหนัก: {profile.get('weight_kg', 0)} kg\n"
    msg += f"- ไขมัน: {profile.get('body_fat_pct', 0)}%\n"
    
    if stats['missing_supplements']:
        msg += f"\nอาหารเสริมที่ยังไม่ได้ทาน:\n"
        for sup in stats['missing_supplements']:
            msg += f"- {sup}\n"
    
    msg += f"\nสู้ๆ นะครับ!"
    return msg

def send_line_message(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    res = requests.post(url, headers=headers, data=json.dumps(payload))
    return res.status_code == 200

if __name__ == "__main__":
    if not all([SUPABASE_URL, SUPABASE_KEY, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID]):
        print("Error: Missing environment variables.")
        exit(1)
        
    profile, stats = get_daily_status()
    msg = generate_summary_message(profile, stats)
    if send_line_message(msg):
        print(f"Reminder sent successfully:\n{msg}")
    else:
        print("Failed to send reminder.")
