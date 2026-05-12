import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form, render_plan_builder, render_weight_form, render_profile_form, process_pending_workout, process_pending_run, process_pending_nutrition, process_pending_weight
from modules.analytics import render_analytics, render_overview, render_nutrition_analysis, render_data_manager, render_export_section, render_wellness
from modules.database import get_db
from datetime import date, datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Training Track",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    """Silent Login with optional Setup Mode."""
    if st.session_state.get("password_correct"):
        return True

    token = st.query_params.get("token")
    # เพิ่มบรรทัดนี้เพื่อเช็คโหมดติดตั้ง
    is_setup = st.query_params.get("setup") == "true"

    if token and token == st.secrets.get("app_token"):
        st.session_state["password_correct"] = True
        
        # ถ้าไม่ใช่โหมด setup ให้ล้าง URL ปกติ แต่ถ้าใช่ ให้ค้างไว้ให้กด Add to Home Screen
        if not is_setup:
            st.query_params.clear()
            st.rerun()
        else:
            st.info("📱 **Setup Mode**: กด 'Add to Home Screen' ได้เลยครับ (URL จะไม่ถูกลบ)")
            return True

    st.error("Access Denied: Valid token required in URL.")
    st.stop()
    
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

   # ── NUTRITION ─────────────────────────────────────────
    if st.session_state.get("nut_confirm_overwrite"):
        date_str = str(st.session_state.get("nut_date", ""))
        if st.session_state.pop("nut_do_overwrite", False):
            db.delete_nutrition_by_date(date_str)
        st.session_state.pop("nut_confirm_overwrite", None)
        process_pending_nutrition(db, st.session_state)

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

    # ── handle confirmations BEFORE tabs render ──
    _handle_pending_confirmations(db)

    # ── show pending success/warning messages ──
    if "_pending_success" in st.session_state:
        st.success(st.session_state.pop("_pending_success"))
    if "_pending_warning" in st.session_state:
        st.warning(st.session_state.pop("_pending_warning"))

    # --- SIDEBAR STATUS ---
    with st.sidebar:
        st.title("⚙️ System Management")
        if db.is_connected():
            st.success("Database Online")
        else:
            st.error("Database Offline")
        
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
            show_plan_builder = st.toggle("🛠️ Open Plan Builder", value=False)
            show_profile = st.toggle("👤 Edit Profile & Goals", value=False)
        else:
            show_plan_builder = False
            show_profile = False

    # --- APP HEADER ---
    st.title("🎯 Training & Health Track")
    st.markdown("---")

    if show_profile:
        render_profile_form()
        st.stop()

    if show_plan_builder:
        render_plan_builder()
        st.stop()

    # --- NAVIGATION ---
    tabs = st.tabs(["🏠 Overview", "🏋️ Training", "🏃 Movement", "⚖️ Weight", "🍱 Nutrition", "🔋 Wellness", "🗂️ Data"])

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
        render_wellness()

    with tabs[6]:
        render_data_manager()

if __name__ == "__main__":
    main()
