import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_api import batch_append

WORKOUT_TEMPLATES = {
    "Upper Power": ["Incline Bench Press", "Flat DB Bench", "Weighted Pull Ups", "Pendlay Row", "Shoulder Press", "Barbell Curls", "Skull Crushers"],
    "Lower Strength": ["Squat", "Deadlift", "Leg Press", "Leg Curls", "Calf Raises"],
    "Upper Volume": ["DB Incline Bench", "Cable Flyes", "Lat Pull Down", "Seated Row", "Lateral Raises", "Hammer Curls", "Tricep Pushdowns"],
    "Full Body Power": ["Squat", "Bench Press", "Deadlift", "Overhead Press", "Barbell Row"],
    "Custom": []
}

def render_workout_form():
    st.header("💪 Log Workout")
    
    template_name = st.selectbox("Select Template", list(WORKOUT_TEMPLATES.keys()))
    exercises = WORKOUT_TEMPLATES[template_name]
    
    if template_name == "Custom":
        if "custom_exercises" not in st.session_state:
            st.session_state.custom_exercises = [""]
        
        for i in range(len(st.session_state.custom_exercises)):
            st.session_state.custom_exercises[i] = st.text_input(f"Exercise {i+1}", value=st.session_state.custom_exercises[i], key=f"custom_ex_{i}")
        
        if st.button("➕ Add Exercise Row"):
            st.session_state.custom_exercises.append("")
            st.rerun()
        exercises = [ex for ex in st.session_state.custom_exercises if ex.strip()]

    with st.form("workout_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.now())
        workout_data = []
        
        for ex in exercises:
            st.subheader(ex)
            col1, col2, col3 = st.columns(3)
            weight = col1.number_input(f"Weight (kg) - {ex}", min_value=0.0, step=0.5, key=f"w_{ex}")
            sets = col2.number_input(f"Sets - {ex}", min_value=0, step=1, key=f"s_{ex}")
            reps = col3.number_input(f"Reps - {ex}", min_value=0, step=1, key=f"r_{ex}")
            volume = weight * sets * reps
            workout_data.append([date.strftime("%Y-%m-%d"), template_name, ex, weight, sets, reps, volume])
            
        submitted = st.form_submit_button("Submit Workout")
        if submitted:
            if not workout_data:
                st.error("No exercises to log!")
            else:
                batch_append("Workouts", workout_data)
                st.success(f"Logged {len(workout_data)} exercises!")
                if template_name == "Custom":
                    st.session_state.custom_exercises = [""]

def render_running_form():
    st.header("🏃 Log Running")
    with st.form("running_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.now())
        distance = st.number_input("Distance (km)", min_value=0.0, step=0.1)
        duration = st.number_input("Duration (min)", min_value=0.0, step=0.1)
        
        pace = 0.0
        if distance > 0:
            pace = duration / distance
            
        st.info(f"Calculated Pace: {pace:.2f} min/km")
        
        submitted = st.form_submit_button("Submit Run")
        if submitted:
            batch_append("Running", [[date.strftime("%Y-%m-%d"), distance, duration, pace]])
            st.success("Run logged!")

def render_biohack_form():
    st.header("🧬 Biohacking & Status")
    with st.form("biohack_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.now())
        
        st.subheader("Supplements")
        col1, col2 = st.columns(2)
        creatine = col1.checkbox("Creatine")
        protein = col2.checkbox("Protein Powder")
        multivit = col1.checkbox("Multivitamin")
        omega3 = col2.checkbox("Omega-3")
        
        st.subheader("Physical Status")
        pppd = st.slider("PPPD Symptoms (1-10)", 1, 10, 5)
        shoulder = st.slider("Shoulder Pain (1-10)", 1, 10, 1)
        
        st.subheader("Macros")
        c1, c2, c3 = st.columns(3)
        calories = c1.number_input("Calories", min_value=0, step=50)
        protein_g = c2.number_input("Protein (g)", min_value=0, step=5)
        weight_kg = c3.number_input("Body Weight (kg)", min_value=0.0, step=0.1)
        
        submitted = st.form_submit_button("Submit Status")
        if submitted:
            data = [[
                date.strftime("%Y-%m-%d"),
                int(creatine), int(protein), int(multivit), int(omega3),
                pppd, shoulder, calories, protein_g, weight_kg
            ]]
            batch_append("Biohacking", data)
            st.success("Status logged!")
