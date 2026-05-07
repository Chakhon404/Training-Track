import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_api import batch_append

# --- CONFIG & TEMPLATES ---
WORKOUT_TEMPLATES = {
    "Custom": [],
    "Routine A: Upper Power": ["Pull Up", "Incline DB Press", "DB Push Press", "One Arm Row", "Band Rotational Punch"],
    "Routine B: Lower Strength": ["Box Jump", "Squat", "RDL", "Bulgarian Split Squat", "Leg Curl", "Calf Raise"],
    "Routine C: Upper Volume": ["Shoulder Press", "Lateral Raise", "Rear Delt", "Lat Pulldown", "Curls", "Tricep Pushdown"],
    "Routine D: Full Body Power": ["Deadlift", "DB Snatch", "Jump Squat", "Plyo Push Up", "Woodchopper"]
}

def render_workout_form():
    st.subheader("🏋️ Training Logs")
    
    # Template Selection
    selected_template = st.selectbox("Load Routine", list(WORKOUT_TEMPLATES.keys()))
    
    # Initialize session state for custom entries
    if "custom_exercises" not in st.session_state:
        st.session_state.custom_exercises = [""]

    # Use .date() and .time() for clean date and time objects
    col_d, col_t = st.columns(2)
    with col_d:
        log_date = st.date_input("Log Date", datetime.now().date(), key="workout_date_picker")
    with col_t:
        log_time = st.time_input("Log Time", datetime.now().time(), key="workout_time_picker")
    log_datetime = f"{log_date} {log_time.strftime('%H:%M')}"

    with st.form(key=f"workout_form_{selected_template}"):
        exercises = WORKOUT_TEMPLATES[selected_template] if selected_template != "Custom" else st.session_state.custom_exercises
        
        session_data = []
        
        for i, ex_name in enumerate(exercises):
            st.markdown(f"### {ex_name if ex_name else f'Entry {i+1}'}")
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                name = st.text_input("Label", value=ex_name, key=f"name_{selected_template}_{i}")
            with col2:
                weight = st.number_input("Unit Value", min_value=0.0, step=0.5, key=f"w_{selected_template}_{i}")
            with col3:
                sets = st.number_input("Sets", min_value=0, step=1, key=f"s_{selected_template}_{i}")
            with col4:
                reps = st.number_input("Reps", min_value=0, step=1, key=f"r_{selected_template}_{i}")
            
            # Intensity Slider
            rpe = st.slider("Intensity (1-10)", 1.0, 10.0, 7.0, 0.5, key=f"rpe_{selected_template}_{i}")
            
            session_data.append({
                "name": name,
                "weight": weight,
                "sets": sets,
                "reps": reps,
                "rpe": rpe
            })
            st.divider()

        submitted = st.form_submit_button("💾 Save Logs")
        
        if submitted:
            final_rows = []
            for item in session_data:
                if item["name"].strip():
                    volume = item["weight"] * item["sets"] * item["reps"]
                    final_rows.append([
                        log_datetime,
                        selected_template,
                        item["name"],
                        item["weight"],
                        item["sets"],
                        item["reps"],
                        item["rpe"],
                        volume
                    ])
            
            if final_rows:
                if batch_append("workouts", final_rows):
                    st.success(f"Successfully saved {len(final_rows)} entries.")
            else:
                st.warning("Please provide at least one entry label.")

    if selected_template == "Custom":
        if st.button("➕ Add Entry Row"):
            st.session_state.custom_exercises.append("")
            st.rerun()

def render_running_form():
    st.subheader("🏃 Movement Logs")
    
    col_d, col_t = st.columns(2)
    with col_d:
        log_date = st.date_input("Date", datetime.now().date(), key="run_date_picker")
    with col_t:
        log_time = st.time_input("Time", datetime.now().time(), key="run_time_picker")
    log_datetime = f"{log_date} {log_time.strftime('%H:%M')}"

    with st.form(key="running_form_v1"):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.number_input("Distance", min_value=0.0, step=0.1, key="run_dist")
            dur = st.text_input("Duration (MM:SS)", value="00:00", key="run_dur")
        with col2:
            hr = st.number_input("Avg Heart Rate", min_value=0, step=1, key="run_hr")
            hrr = st.number_input("Recovery Delta", min_value=0, step=1, key="run_hrr")
            
        submitted = st.form_submit_button("💾 Save Activity")

        if submitted:
            try:
                mins, secs = map(int, dur.split(":"))
                total_secs = mins * 60 + secs
                if dist > 0:
                    pace_secs = total_secs / dist
                    pace_min = int(pace_secs // 60)
                    pace_sec = int(pace_secs % 60)
                    pace_str = f"{pace_min}:{pace_sec:02d}"
                else:
                    pace_str = "0:00"
                
                run_row = [[log_datetime, dist, dur, pace_str, hr, hrr]]
                if batch_append("running", run_row):
                    st.success("Activity log updated.")
            except ValueError:
                st.error("Invalid format. Use MM:SS.")

def render_biohack_form():
    st.subheader("💊 Health & Routine")
    
    col_d, col_t = st.columns(2)
    with col_d:
        log_date = st.date_input("Date", datetime.now().date(), key="bio_date_picker")
    with col_t:
        log_time = st.time_input("Time", datetime.now().time(), key="bio_time_picker")
    log_datetime = f"{log_date} {log_time.strftime('%H:%M')}"

    with st.form(key="biohack_form_v1"):
        st.markdown("### Supplements & Basics")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            creatine = st.checkbox("Creatine", key="bio_creatine")
        with c2:
            protein_p = st.checkbox("Protein Powder", key="bio_protein_p")
        with c3:
            multiv = st.checkbox("Multi-Vitamin", key="bio_multiv")
        with c4:
            omega3 = st.checkbox("Omega 3", key="bio_omega3")
        
        st.divider()
        st.markdown("### Status Monitoring (1-10)")
        s1, s2 = st.columns(2)
        with s1:
            pppd = st.slider("Equilibrium Score (PPPD)", 1, 10, 1, key="bio_pppd")
        with s2:
            shoulder = st.slider("Stability Score (Shoulder)", 1, 10, 5, key="bio_shoulder")
            
        st.divider()
        st.markdown("### Macronutrient Distribution & Energy Balance")
        n1, n2, n3, n4 = st.columns(4)
        with n1:
            calories = st.number_input("Calories (kcal)", min_value=0, step=50, key="bio_calories")
        with n2:
            protein_g = st.number_input("Protein (g)", min_value=0, step=1, key="bio_protein_g")
        with n3:
            carb_g = st.number_input("Carbs (g)", min_value=0, step=1, key="bio_carb_g")
        with n4:
            fat_g = st.number_input("Fat (g)", min_value=0, step=1, key="bio_fat_g")
            
        weight_kg = st.number_input("Weight (kg)", min_value=0.0, step=0.1, key="bio_weight_kg")

        submitted = st.form_submit_button("✅ Update Health Log")
        
        if submitted:
            # Order: [Date, Creatine, Protein_P, MultiV, Omega3, PPPD, Shoulder, Calories, Protein_g, Carb_g, Fat_g, Weight_kg]
            bio_row = [[
                log_datetime, 
                int(creatine), int(protein_p), int(multiv), int(omega3),
                pppd, shoulder, 
                calories, protein_g, carb_g, fat_g, weight_kg
            ]]
            if batch_append("biohack", bio_row):
                st.success("Daily routine updated.")
