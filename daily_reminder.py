import os
import requests
from supabase import create_client
from datetime import datetime, timedelta, timezone
import pytz
import json
from dotenv import load_dotenv

# Load local .env for testing
load_dotenv()

def debug_report():
    # Bangkok Timezone (UTC+7)
    tz = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(tz)
    today = now_bkk.strftime("%Y-%m-%d")
    print(f"🔍 DEBUG: กำลังตรวจสอบข้อมูลวันที่ {today}")

    # 1. ทดสอบเชื่อมต่อ Supabase
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            print("❌ Error: Missing SUPABASE_URL or SUPABASE_KEY")
            return
            
        supabase = create_client(url, key)
        print("✅ Step 1: เชื่อมต่อ Supabase สำเร็จ")

        # 2. ตรวจสอบตาราง Profiles
        # จาก schema ที่ตรวจพบ ใช้ชื่อตาราง 'user_profile'
        target_table = "user_profile" 
        prof_res = supabase.table(target_table).select("*").order("updated_at", desc=True).limit(1).maybe_single().execute()
        
        if not prof_res.data:
            print(f"❌ Step 2: ไม่พบข้อมูลในตาราง '{target_table}'")
            return "ไม่พบข้อมูลโปรไฟล์ใน Database"
        
        print(f"✅ Step 2: พบข้อมูลโปรไฟล์คุณ {target_table} ล่าสุด")
        profile = prof_res.data

        # 3. ตรวจสอบตาราง Nutrition
        # จาก schema ใช้คอลัมน์ log_ts (timestamp)
        nut_res = supabase.table("nutrition").select("*").gte("log_ts", f"{today}T00:00:00").execute()
        if not nut_res.data:
            print(f"⚠️ Step 3: วันนี้ ({today}) ยังไม่มีการบันทึกข้อมูลในตาราง nutrition")
            msg = f"แจ้งเตือนคุณชาคร: วันนี้ยังไม่มีข้อมูลบันทึกเลยครับ!"
        else:
            print(f"✅ Step 3: พบข้อมูลการกินของวันนี้ ({len(nut_res.data)} รายการ)")
            msg = "รายงานคุณชาคร: วันนี้วินัยยอดเยี่ยมครับ (ทดสอบ)"

        # 4. ทดสอบส่ง LINE พร้อมเช็ค Error
        token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        user_id = os.getenv('LINE_USER_ID')
        
        print(f"🔍 DEBUG: ความยาว Token = {len(token) if token else 0}")
        print(f"🔍 DEBUG: User ID ขึ้นต้นด้วย U หรือไม่ = {str(user_id).startswith('U')}")

        if not token or not user_id:
            print("❌ Error: Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID")
            return

        line_url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": msg}]
        }
        
        line_res = requests.post(line_url, headers=headers, json=payload)
        
        if line_res.status_code == 200:
            print("✅ Step 4: ส่ง LINE สำเร็จแล้ว!")
        else:
            print(f"❌ Step 4: LINE ปฏิเสธ (Status {line_res.status_code})")
            print(f"📝 รายละเอียด Error จาก LINE: {line_res.text}")

    except Exception as e:
        print(f"💥 เกิดข้อผิดพลาดร้ายแรง: {str(e)}")

if __name__ == "__main__":
    debug_report()
