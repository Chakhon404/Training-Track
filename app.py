import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form, render_plan_builder, render_weight_form, render_profile_form, process_pending_workout, process_pending_run, process_pending_weight, render_exercise_history_card
from modules.analytics import render_analytics, render_overview, render_nutrition_analysis, render_data_manager, render_export_section
from modules.database import get_db
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Training Track",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    """ระบบล็อกอิน 2 ทาง: ผ่าน Token จาก URL หรือพิมพ์ Password เอง"""
    
    # 1. ถ้าเคยล็อกอินผ่านแล้วใน Session นี้ ให้ผ่านไปเลย
    if st.session_state.get("password_correct"):
        return True

    # 2. ตรวจสอบกุญแจ (Token) จาก URL
    token = st.query_params.get("token")
    if token:
        if token == st.secrets.get("app_token"):
            st.session_state["password_correct"] = True
            st.query_params.clear() # ล้าง URL ให้สะอาด
            st.rerun()
        else:
            st.error("Invalid Token link.")
            st.stop()

    # 3. ถ้าไม่มี Token หรือ Token ไม่ถูกต้อง -> แสดงหน้ากรอกรหัสผ่าน (Manual Login)
    st.markdown('<div style="font-family:Syne;font-size:32px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:20px;">Secure Access</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        pwd = st.text_input("Access Key", type="password", placeholder="กรอกรหัสผ่านเพื่อเข้าใช้งาน")
        submitted = st.form_submit_button("Unlock Dashboard")

    if submitted:
        if pwd == st.secrets.get("app_password"):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Invalid Key.")

    return False

def _handle_pending_confirmations(db):
    """
    Runs on every rerun before tabs are rendered.
    Handles all post-confirmation saves for all 4 forms.
    """

    # ── WORKOUT ──────────────────────────────────────────
    if st.session_state.get("workout_confirm_overwrite"):
        date_str = str(st.session_state.get("work_date", ""))
        if st.session_state.pop("workout_do_overwrite", False):
            db.delete_workouts_by_date(date_str)
        st.session_state.pop("workout_confirm_overwrite", None)
        process_pending_workout(db, st.session_state)

    # ── RUNNING ──────────────────────────────────────────
    if st.session_state.get("run_confirm_overwrite"):
        date_str = str(st.session_state.get("run_date", ""))
        if st.session_state.pop("run_do_overwrite", False):
            db.delete_runs_by_date(date_str)
        st.session_state.pop("run_confirm_overwrite", None)
        process_pending_run(db, st.session_state)

    # ── WEIGHT ────────────────────────────────────────────
    if st.session_state.get("weight_confirm_overwrite"):
        date_str = str(st.session_state.get("weight_date", ""))
        if st.session_state.pop("weight_do_overwrite", False):
            db.delete_weight_by_date(date_str)
        st.session_state.pop("weight_confirm_overwrite", None)
        process_pending_weight(db, st.session_state)

def main():
    """Main application entry point."""
    if not check_password():
        st.stop()

    db = get_db()

    # --- GLOBAL CSS INJECTION ---
    st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
    <style>
        .stApp, [data-testid="stAppViewContainer"] {
            background: #0D0D0F; color: #F0EFE8;
        }

        [data-testid="stHeader"] {
            background: #0D0D0F; border-bottom: 0.5px solid rgba(255,255,255,0.07);
        }

        [data-testid="stSidebar"] {
            background: #0D0D0F !important;
            border-right: 0.5px solid rgba(255,255,255,0.07);
        }

        [data-testid="stSidebar"] .stButton > button {
            background: #1A1A1F; border: 0.5px solid rgba(255,255,255,0.07);
            color: #888880; border-radius: 8px; width: 100%;
        }

        [data-testid="stSidebarContent"] .stToggle label {
            color: #888880; font-family: 'DM Sans';
        }

        .stTabs [data-baseweb="tab-list"] {
            background: #1A1A1F; border-radius: 8px; padding: 3px; gap: 2px;
            border-bottom: none;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent; color: #888880;
            font-family: 'DM Sans'; font-size: 13px; font-weight: 500;
            border-radius: 6px; padding: 6px 14px; border: none;
        }

        .stTabs [aria-selected="true"] {
            background: #1F1F26 !important; color: #C8F135 !important;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        [data-testid="stMetric"] {
            background: #141417; border: 0.5px solid rgba(255,255,255,0.07);
            border-radius: 10px; padding: 14px; margin-bottom: 4px;
        }

        [data-testid="stMetricLabel"] {
            font-family: 'DM Sans'; font-size: 10px; color: #888880;
            text-transform: uppercase; letter-spacing: 0.04em;
        }

        [data-testid="stMetricValue"] {
            font-family: 'Syne'; font-size: 22px; font-weight: 700;
            color: #F0EFE8; letter-spacing: -0.03em;
        }

        [data-testid="stMetricDelta"] [data-testid="stMetricDeltaIcon-Up"] ~ div,
        [data-testid="stMetricDelta"] [class*="positive"] {
            color: #3FD47A !important;
        }

        [data-testid="stMetricDelta"] [data-testid="stMetricDeltaIcon-Down"] ~ div,
        [data-testid="stMetricDelta"] [class*="negative"] {
            color: #F13568 !important;
        }

        h1, h2, h3 {
            font-family: 'Syne'; letter-spacing: -0.03em; color: #F0EFE8;
        }

        [data-testid="stMarkdownContainer"] h3 {
            font-family: 'Syne'; font-weight: 700; color: #F0EFE8;
        }

        .stButton > button {
            background: #1A1A1F; border: 0.5px solid rgba(255,255,255,0.07);
            color: #F0EFE8; border-radius: 8px; font-family: 'DM Sans';
            font-weight: 500; transition: all 0.15s;
        }

        .stButton > button:hover {
            border-color: rgba(200,241,53,0.3); color: #C8F135;
        }

        .stButton > button[kind="primary"], .stButton > button[data-testid*="save"],
        button.save-btn {
            background: #C8F135 !important; color: #0D0D0F !important;
            font-family: 'Syne' !important; font-weight: 800 !important;
            border: none !important;
        }

        .stTextInput input, .stNumberInput input, .stSelectbox select,
        [data-baseweb="select"] > div, [data-baseweb="input"] > div,
        [data-testid="stDateInput"] input, [data-testid="stTimeInput"] input {
            background: #1A1A1F !important; border: 0.5px solid rgba(255,255,255,0.07) !important;
            color: #F0EFE8 !important; border-radius: 8px !important;
        }

        [data-baseweb="select"] > div:focus-within,
        [data-baseweb="input"] > div:focus-within {
            border-color: rgba(200,241,53,0.4) !important;
        }

        [data-baseweb="popover"] [role="listbox"] {
            background: #1A1A1F; border: 0.5px solid rgba(255,255,255,0.07);
        }

        [data-baseweb="option"]:hover {
            background: #1F1F26;
        }

        [data-testid="stForm"] {
            background: #141417; border: 0.5px solid rgba(255,255,255,0.07);
            border-radius: 12px; padding: 16px !important;
        }

        [data-testid="stExpander"] {
            background: #141417 !important;
            border: 0.5px solid rgba(255,255,255,0.07) !important;
            border-radius: 10px !important;
        }

        [data-testid="stExpander"] summary {
            color: #F0EFE8; font-family: 'DM Sans'; font-weight: 500;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #141417 !important;
            border-color: rgba(255,255,255,0.07) !important;
            border-radius: 12px !important;
        }

        .stDataFrame {
            background: #141417; border-radius: 10px; overflow: hidden;
        }

        .stDataFrame [data-testid="glideDataEditorContainer"] {
            background: #141417 !important;
        }

        .stAlert {
            border-radius: 8px; border-left-width: 2px;
        }

        [data-testid="stSuccessMessage"] {
            background: rgba(63,212,122,0.08);
            border-color: rgba(63,212,122,0.3); color: #3FD47A;
        }

        [data-testid="stWarningMessage"] {
            background: rgba(239,159,39,0.08);
            border-color: rgba(239,159,39,0.3); color: #EF9F27;
        }

        [data-testid="stErrorMessage"] {
            background: rgba(241,53,104,0.08);
            border-color: rgba(241,53,104,0.3); color: #F13568;
        }

        [data-testid="stInfoMessage"] {
            background: rgba(53,200,241,0.08);
            border-color: rgba(53,200,241,0.3); color: #35C8F1;
        }

        .stSlider [data-baseweb="slider"] [role="slider"] {
            background: #C8F135;
        }

        .stSlider [data-testid="stSlider"] > div > div > div > div {
            background: #C8F135;
        }

        .stCheckbox label span {
            color: #888880; font-family: 'DM Sans';
        }

        .stCheckbox [data-testid="stCheckbox"] span[aria-checked="true"] {
            background: #C8F135; border-color: #C8F135;
        }

        .stDivider {
            border-color: rgba(255,255,255,0.07);
        }

        ::-webkit-scrollbar {
            width: 4px; height: 4px;
        }
        ::-webkit-scrollbar-track {
            background: #0D0D0F;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.1); border-radius: 2px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(200,241,53,0.3);
        }
    </style>
    """, unsafe_allow_html=True)

    # ── handle confirmations BEFORE tabs render ──
    _handle_pending_confirmations(db)

    # ── show pending success/warning messages ──
    if "_pending_success" in st.session_state:
        st.success(st.session_state.pop("_pending_success"))
    if "_pending_warning" in st.session_state:
        st.warning(st.session_state.pop("_pending_warning"))

    # --- SIDEBAR REDESIGN ---
    with st.sidebar:
        st.markdown("""
        <div style="padding:8px 0 16px;">
          <span style="font-family:Syne;font-weight:800;font-size:20px;
          color:#C8F135;letter-spacing:-0.03em;">Training
          <span style="color:#F0EFE8;">Track</span></span>
        </div>""", unsafe_allow_html=True)
        
        if db.is_connected():
            st.markdown("""<span style="font-size:11px;color:#3FD47A;background:rgba(63,212,122,0.1);
            border:0.5px solid rgba(63,212,122,0.2);padding:4px 10px;border-radius:20px;">
            ● Database Online</span>""", unsafe_allow_html=True)
        else:
            st.markdown("""<span style="font-size:11px;color:#F13568;background:rgba(241,53,104,0.1);
            border:0.5px solid rgba(241,53,104,0.2);padding:4px 10px;border-radius:20px;">
            ● Database Offline</span>""", unsafe_allow_html=True)
        
        st.write("") # Spacer

        if st.button("🔄 Refresh Data"):
            for key in [
                "work_draft_loaded", "run_draft_loaded", "nut_draft_loaded", "weight_draft_loaded",
                "workout_show_confirm", "run_show_confirm", "nut_show_confirm", "weight_show_confirm",
                "workout_pending_date", "run_pending_date", "nut_pending_date", "weight_pending_date",
                "_pending_success", "_pending_warning"
            ]:
                st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        if db.is_connected():
            show_history = st.toggle("📊 Open Exercise History", value=False)
            show_plan_builder = st.toggle("🛠️ Open Plan Builder", value=False)
            show_profile = st.toggle("👤 Edit Profile & Goals", value=False)
        else:
            show_history = False
            show_plan_builder = False
            show_profile = False
            st.warning("Database offline. Cannot load sidebar tools.")

    # --- APP HEADER ---
    st.markdown("""<div style="font-family:Syne;font-size:26px;font-weight:800;
    color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">Training & Health Track</div>""", unsafe_allow_html=True)
    st.divider()

    # ── FULL-SCREEN TOOL ROUTING ──
    if show_profile:
        render_profile_form()
        st.stop()

    if show_history:
        render_exercise_history_card()
        st.stop()

    if show_plan_builder:
        render_plan_builder()
        st.stop()

    # --- NAVIGATION ---
    tabs = st.tabs(["🏠 Overview", "🏋️ Training", "🏃 Movement", "⚖️ Weight", "🍱 Nutrition", "🗂️ Data"])

    with tabs[0]:
        render_overview()

    with tabs[1]:
        if db.is_connected():
            render_workout_form()
        else:
            st.warning("Database offline. Cannot load training plans.")

    with tabs[2]:
        render_running_form()

    with tabs[3]:
        render_analytics()

    with tabs[4]:
        render_nutrition_analysis()
        st.divider()
        render_biohack_form()

    with tabs[5]:
        render_data_manager()

if __name__ == "__main__":
    main()
