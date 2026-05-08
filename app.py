import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form, render_plan_builder, render_weight_form
from modules.analytics import render_analytics, render_overview, render_nutrition_analysis
from modules.database import get_db

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Training Track",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    """Returns True if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Secure Access")
    pwd = st.text_input("Access Key", type="password")
    if st.button("Unlock Dashboard"):
        if pwd == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Invalid Key.")
    return False

def main():
    """Main application entry point."""
    if not check_password():
        st.stop()

    db = get_db()

    # --- SIDEBAR STATUS ---
    with st.sidebar:
        st.title("⚙️ System Management")
        if db.is_connected():
            st.success("Database Online")
        else:
            st.error("Database Offline")
        
        if st.button("🔄 Refresh Data"):
            for key in ["work_draft_loaded", "run_draft_loaded", "nut_draft_loaded", "weight_draft_loaded"]:
                st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        if db.is_connected():
            show_plan_builder = st.toggle("🛠️ Open Plan Builder", value=False)
        else:
            show_plan_builder = False

    # --- APP HEADER ---
    st.title("🎯 Training & Health Track")
    st.markdown("---")

    if show_plan_builder:
        render_plan_builder()
        st.stop()

    # --- NAVIGATION ---
    tabs = st.tabs(["🏠 Overview", "🏋️ Training", "🏃 Movement", "⚖️ Weight", "📉 Analytics", "🍱 Nutrition"])

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
        render_weight_form()

    with tabs[4]:
        render_analytics()

    with tabs[5]:
        render_nutrition_analysis()
        st.divider()
        render_biohack_form()

if __name__ == "__main__":
    main()
