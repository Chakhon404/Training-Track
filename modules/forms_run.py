import streamlit as st
import time
import pytz
from datetime import datetime
from modules.database import get_db, fetch_today_summary_cached

# ปรับให้รองรับ log_time_str ที่เป็น String รูปแบบ HH:MM
def get_timestamp(log_date, log_time_str):
    return f"{log_date} {log_time_str}:00"

@st.fragment
def render_running_form():
    db = get_db()
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:20px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:16px;">Movement Tracker</div>', unsafe_allow_html=True)
    form_key = f"draft_run_{st.session_state.get('user_id', 'default')}"

    if "run_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk).replace(microsecond=0)
        
        # Load date
        if "date" in draft and isinstance(draft["date"], str):
            try:
                st.session_state.run_date = datetime.strptime(draft["date"], "%Y-%m-%d").date()
            except ValueError:
                st.session_state.run_date = _now.date()
        else:
            st.session_state.run_date = _now.date()

        # Load time ให้เก็บเป็น String "HH:MM" เพื่อเลี่ยงบัค React
        if "time" in draft and isinstance(draft["time"], str):
            st.session_state.run_time = draft["time"][:5]
        else:
            st.session_state.run_time = _now.strftime("%H:%M")
            
        st.session_state.run_cat = draft.get("cat", "Easy")
        st.session_state.run_dist = float(draft.get("dist", 0.0))
        st.session_state.run_dur = draft.get("dur", "00:00")
        st.session_state.run_hr = int(draft.get("hr", 0))
        # ลบการอ้างอิงถึง hrr ออก
        st.session_state.run_draft_loaded = True

    def save_run_draft():
        if "run_cat" not in st.session_state:
            return
        now = time.time()
        if now - st.session_state.get("_last_run_draft_save", 0) < 3:
            return

        data = {
            "date": str(st.session_state.run_date),
            "time": f"{st.session_state.run_time}:00" if len(st.session_state.run_time) == 5 else "00:00:00",
            "cat": st.session_state.run_cat,
            "dist": st.session_state.run_dist,
            "dur": st.session_state.run_dur,
            "hr": st.session_state.run_hr
            # ลบการส่งค่า hrr เข้า draft
        }
        db.save_draft(form_key, data)
        st.session_state["_last_run_draft_save"] = now

    # --- Standardized Widget Initialization ---
    _bkk = pytz.timezone("Asia/Bangkok")
    _now = datetime.now(_bkk).replace(microsecond=0)
    if "run_date" not in st.session_state:
        st.session_state.run_date = _now.date()
    if "run_time" not in st.session_state:
        st.session_state.run_time = _now.strftime("%H:%M")
    if "run_cat" not in st.session_state:
        st.session_state.run_cat = "Easy"
    if "run_dist" not in st.session_state:
        st.session_state.run_dist = 0.0
    if "run_dur" not in st.session_state:
        st.session_state.run_dur = "00:00"
    if "run_hr" not in st.session_state:
        st.session_state.run_hr = 0
    # ลบการ Initialize hrr ออก

    # สร้างฟังก์ชัน Callback สำหรับปุ่ม Now
    def set_time_to_now():
        _now = datetime.now(pytz.timezone("Asia/Bangkok"))
        st.session_state.run_date = _now.date()
        st.session_state.run_time = _now.strftime("%H:%M")
        # บังคับบันทึกดราฟต์ทันที
        save_run_draft()

    # --- Row 1: Date & Time ---
    r1_c1, r1_c2, r1_c3 = st.columns([4, 4, 2])
    with r1_c1:
        l_date = st.date_input("Date", key="run_date", on_change=save_run_draft)
    with r1_c2:
        l_time = st.text_input("Time (HH:MM)", key="run_time", on_change=save_run_draft)
    with r1_c3:
        st.markdown('<div style="font-size:14px; color:#F0EFE8; margin-bottom:8px; font-family:Inter, sans-serif;">Quick Set Time</div>', unsafe_allow_html=True)
        # เรียกใช้ callback (on_click) แทนการเขียนลอจิกซ้อนใน if
        st.button("Now", key="Use Current Time", use_container_width=True, on_click=set_time_to_now)

    # --- Row 2: Category & Distance ---
    r2_c1, r2_c2 = st.columns(2)
    with r2_c1:
        cat = st.selectbox("Activity Category", ["Sprint", "Zone-2", "Easy", "Tempo", "Interval", "Long", "Walk"], key="run_cat", on_change=save_run_draft)
    with r2_c2:
        dist = st.number_input("Distance (km)", min_value=0.0, step=0.1, key="run_dist", on_change=save_run_draft)

    # --- Row 3: Metrics (ปรับเหลือ 2 คอลัมน์ เพราะเอา hrr ออก) ---
    r3_c1, r3_c2 = st.columns(2)
    with r3_c1:
        dur = st.text_input("Duration (MM:SS)", key="run_dur", on_change=save_run_draft)
    with r3_c2:
        hr = st.number_input("Avg Heart Rate", min_value=0, step=1, key="run_hr", on_change=save_run_draft)

    st.markdown('<div style="margin-bottom:10px;"></div>', unsafe_allow_html=True)
    submitted = st.button("Log Movement", use_container_width=True)

    # Step 1: on submit
    if submitted:
        date_str = str(l_date)
        
        # ตรวจสอบรูปแบบเวลาก่อนบันทึกเพื่อป้องกัน Error
        if len(l_time) != 5 or ":" not in l_time:
            st.error("Please enter time in HH:MM format (e.g., 06:36)")
            return

        dup_count = db.check_duplicate_run(date_str)
        if dup_count > 0:
            st.session_state.run_show_confirm = True
            st.session_state.run_pending_date = date_str
        else:
            log_ts = get_timestamp(l_date, l_time)
            try:
                p = dur.split(":")
                mins, secs = (float(p[0]), float(p[1])) if len(p) == 2 else (0.0, 0.0)
                duration_min = mins + (secs / 60.0)

                pace_s = "0:00"
                if float(dist) > 0:
                    pace_decimal = duration_min / float(dist)
                    p_mins = int(pace_decimal)
                    p_secs = int((pace_decimal - p_mins) * 60)
                    pace_s = f"{p_mins}:{p_secs:02d}"

                run_data = {
                    "log_ts": log_ts,
                    "distance": dist,
                    "duration": dur,
                    "pace": pace_s,
                    "hr": hr,
                    "hrr": 0,
                    "category": cat
                    # ลบ hrr ออกจาก Dictionary ที่ส่งเข้า Database
                }
                if db.save_run(run_data):
                    st.success("Movement session logged.")
                    db.clear_draft(form_key)
                    st.session_state.pop("run_draft_loaded", None)
                    st.rerun()
            except Exception:
                st.error("Use MM:SS format for duration.")

    # Step 2: Confirmation UI
    if st.session_state.get("run_show_confirm"):
        date_str = st.session_state.get("run_pending_date", "")
        st.markdown(f"""
        <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);
        border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:Inter, sans-serif;">
        Duplicate entries found on {date_str}.</div>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        if col1.button("Save Anyway", key="run_save_anyway"):
            st.session_state.run_confirm_overwrite = True
            st.session_state.pop("run_show_confirm", None)
            st.rerun()
            
        st.markdown("""<style>div:has(> button[key="run_overwrite"]) > button { background:#C8F135 !important; color:#0D0D0F !important; }</style>""", unsafe_allow_html=True)
        if col2.button("Overwrite", key="run_overwrite"):
            st.session_state.run_confirm_overwrite = True
            st.session_state.run_do_overwrite = True
            st.session_state.pop("run_show_confirm", None)
            st.rerun()
            
        st.markdown("""<style>div:has(> button[key="run_cancel"]) > button { color:#F13568 !important; border-color:rgba(241,53,104,0.3) !important; }</style>""", unsafe_allow_html=True)
        if col3.button("Cancel", key="run_cancel"):
            st.session_state.pop("run_show_confirm", None)
            st.session_state.pop("run_pending_date", None)
            st.rerun()

def process_pending_run(db, session_state):
    """Constructs and saves run/movement data from session state."""
    run_date = session_state.get("run_date")
    run_time = session_state.get("run_time")
    _dist = float(session_state.get("run_dist", 0.0))
    _dur = str(session_state.get("run_dur", "00:00"))
    _hr = int(session_state.get("run_hr", 0))
    # ลบการอ้างอิง hrr
    _cat = str(session_state.get("run_cat", "Easy"))

    if run_date and run_time:
        # ใช้ run_time แบบ String เชื่อมต่อได้เลย ไม่ต้องใช้ .strftime()
        log_ts = f"{run_date} {run_time}:00"
        try:
            p = _dur.split(":")
            mins, secs = (float(p[0]), float(p[1])) if len(p) == 2 else (0.0, 0.0)
            duration_min = mins + (secs / 60.0)

            pace_s = "0:00"
            if float(_dist) > 0:
                pace_decimal = duration_min / float(_dist)
                p_mins = int(pace_decimal)
                p_secs = int((pace_decimal - p_mins) * 60)
                pace_s = f"{p_mins}:{p_secs:02d}"

            run_data = {
                "log_ts": log_ts, "distance": _dist, "duration": _dur,
                "pace": pace_s, "hr": _hr, "category": _cat
                # ลบ hrr ออกจาก Dictionary ที่เตรียมเซฟ
            }
            form_key = f"draft_run_{session_state.get('user_id', 'default')}"
            if db.save_run(run_data):
                session_state["_pending_success"] = "Movement session logged."
                db.clear_draft(form_key)
                session_state.pop("run_draft_loaded", None)
        except Exception:
            session_state["_pending_warning"] = "Use MM:SS format for duration."