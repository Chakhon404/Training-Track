import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form
from modules.analytics import render_analytics

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="The Tank Log",
    page_icon="🏋️",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION ---
if "workout_session" not in st.session_state:
    st.session_state.workout_session = False
if "custom_exercises" not in st.session_state:
    st.session_state.custom_exercises = [""]

# --- APP HEADER ---
st.title("🛡️ The Tank Log v1.0")
st.markdown("Automated Training & Biohacking Log System")

# --- NAVIGATION ROUTER ---
tabs = st.tabs(["🏋️ Workout", "🏃 Engine", "💊 Biohack", "🧠 AI Data"])

with tabs[0]:
    render_workout_form()

with tabs[1]:
    render_running_form()

with tabs[2]:
    render_biohack_form()

with tabs[3]:
    render_analytics()
