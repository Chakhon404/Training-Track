import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form
from modules.analytics import render_analytics

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- AUTHENTICATION ---
def check_password():
    \"\"\"Returns `True` if the user had the correct password.\"\"\"

    def password_entered():
        \"\"\"Checks whether a password entered by the user is correct.\"\"\"
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
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

# --- MAIN APP ---
def main():
    if check_password():
        # --- SESSION STATE INITIALIZATION ---
        if "workout_session" not in st.session_state:
            st.session_state.workout_session = False
        if "custom_exercises" not in st.session_state:
            st.session_state.custom_exercises = [""]

        # --- APP HEADER ---
        st.title("📊 Personal Activity Dashboard")
        st.markdown("Automated Routine & Health Management System")

        # --- NAVIGATION ROUTER ---
        # Renamed tabs for discretion
        tabs = st.tabs(["📝 Training Logs", "🏃 Movement Logs", "💊 Health & Routine", "📈 Insights & Trends"])

        with tabs[0]:
            render_workout_form()

        with tabs[1]:
            render_running_form()

        with tabs[2]:
            render_biohack_form()

        with tabs[3]:
            render_analytics()

if __name__ == "__main__":
    main()
