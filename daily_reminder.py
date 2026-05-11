import os
import requests
import json
from datetime import datetime
from google import genai
from supabase import create_client, Client
from dotenv import load_dotenv

# Load local .env for testing; GitHub Actions and Streamlit use their own secret managers
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def get_daily_status():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Check Weight
    weight_res = supabase.table("weight").select("*").gte("log_ts", f"{today}T00:00:00").execute()
    has_weight = len(weight_res.data) > 0
    
    # 2. Check Nutrition (Protein & Supplements)
    nut_res = supabase.table("nutrition").select("*").gte("log_ts", f"{today}T00:00:00").execute()
    
    total_protein = sum(item.get("protein_g", 0) for item in nut_res.data)
    
    # Target supplements from requirements
    target_sups = {
        "creatine": "Creatine",
        "fish_oil": "Fish Oil",
        "astaxanthin": "Astaxanthin",
        "magnesium": "Magnesium",
        "zinc": "Zinc",
        "protein_powder": "Protein Powder",
        "multivitamin": "Multi-Vitamin"
    }
    
    sups_status = {k: False for k in target_sups.keys()}
    
    for entry in nut_res.data:
        for sup in sups_status.keys():
            db_key = "multivitamin" if sup == "multivitamin" else sup
            if entry.get(db_key):
                sups_status[sup] = True
                
    missing = []
    if not has_weight: 
        missing.append("ชั่งน้ำหนัก (Weight)")
    if total_protein < 150: 
        missing.append(f"โปรตีน (Protein) - ปัจจุบัน {total_protein}g / เป้าหมาย 150g")
    
    for sup_key, taken in sups_status.items():
        if not taken:
            missing.append(f"อาหารเสริม: {target_sups[sup_key]}")
            
    return missing

def generate_coach_message(missing_items):
    if not missing_items:
        return "วันนี้ทำดีมากไอ้เสือ! ครบถ้วนทุกอย่าง ลุยต่อพรุ่งนี้! 🥊"
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are a tough but caring Thai boxing coach. 
    The player missed these tasks: {', '.join(missing_items)}. 
    Write a motivating and slightly aggressive reminder in Thai to send via LINE. 
    Keep it concise but powerful. Use boxing metaphors.
    """
    
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt
    )
    return response.text.strip()

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
    if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID]):
        print("Error: Missing environment variables.")
        exit(1)
        
    missing = get_daily_status()
    msg = generate_coach_message(missing)
    if send_line_message(msg):
        print(f"Reminder sent successfully: {msg}")
    else:
        print("Failed to send reminder.")
