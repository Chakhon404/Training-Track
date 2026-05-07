import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form
from modules.analytics import render_analytics, render_overview, render_nutrition_analysis

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide"
)

def check_password():
    """Returns True if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Access Key", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Access Key", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Access Denied.")
        return False
    else:
        # Password correct.
        return True

def main():
    """Main application entry point."""
    if not check_password():
        st.stop()  # Halt execution until authenticated

    # --- SESSION STATE INITIALIZATION ---
    if "workout_session" not in st.session_state:
        st.session_state.workout_session = False
    if "custom_exercises" not in st.session_state:
        st.session_state.custom_exercises = [""]

    # --- APP HEADER ---
    st.title("📊 Personal Activity Dashboard")
    st.markdown("Automated Routine & Health Management System")

    # --- NAVIGATION ROUTER ---
    # Rebranded tabs for discretion and professional tone
    tabs = st.tabs(["Overview", "Weight", "Training", "Running", "Nutrients"])

    with tabs[0]:
        render_overview()

    with tabs[1]:
        render_analytics()

    with tabs[2]:
        render_workout_form()

    with tabs[3]:
        render_running_form()

    with tabs[4]:
        render_nutrition_analysis()
        st.divider()
        render_biohack_form()

if __name__ == "__main__":
    main()
