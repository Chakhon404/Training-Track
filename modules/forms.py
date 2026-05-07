import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_api import batch_append

# --- CONFIG & TEMPLATES ---
WORKOUT_TEMPLATES = {
    "Custom": [],
    "Day 1: Upper Power": ["Pull Up", "Incline DB Press", "DB Push Press", "One Arm Row", "Band Rotational Punch"],
    "Day 2: Lower Strength": ["Box Jump", "Squat", "RDL", "Bulgarian Split Squat", "Leg Curl", "Calf Raise"],
    "Day 4: Upper Volume": ["Shoulder Press", "Lateral Raise", "Rear Delt", "Lat Pulldown", "Curls", "Tricep Pushdown"],
    "Day 5: Full Body Power": ["Deadlift", "DB Snatch", "Jump Squat", "Plyo Push Up", "Woodchopper"]
}

def render_workout_form():
    st.subheader("🏋️ Hypertrophy Session")
    
    # Template Selection
    selected_template = st.selectbox("Load Template", list(WORKOUT_TEMPLATES.keys()))
    
    # Initialize session state for custom exercises
    if "custom_exercises" not in st.session_state:
        st.session_state.custom_exercises = [""]

    # Use .date() for clean date objects
    log_date = st.date_input("Session Date", datetime.now().date(), key="workout_date_picker")

    with st.form(key=f"workout_form_{selected_template}"):
        exercises = WORKOUT_TEMPLATES[selected_template] if selected_template != "Custom" else st.session_state.custom_exercises
        
        session_data = []
        
        for i, ex_name in enumerate(exercises):
            st.markdown(f"### {ex_name if ex_name else f'Exercise {i+1}'}")
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                name = st.text_input("Exercise Name", value=ex_name, key=f"name_{selected_template}_{i}")
            with col2:
                weight = st.number_input("Weight (kg)", min_value=0.0, step=0.5, key=f"w_{selected_template}_{i}")
            with col3:
                sets = st.number_input("Sets", min_value=0, step=1, key=f"s_{selected_template}_{i}")
            with col4:
                reps = st.number_input("Reps", min_value=0, step=1, key=f"r_{selected_template}_{i}")
            
            # RPE Slider as requested
            rpe = st.slider("RPE (Intensity)", 1.0, 10.0, 7.0, 0.5, key=f"rpe_{selected_template}_{i}")
            
            session_data.append({
                "name": name,
                "weight": weight,
                "sets": sets,
                "reps": reps,
                "rpe": rpe
            })
            st.divider()

        submitted = st.form_submit_button("🔥 Save Entire Session")
        
        if submitted:
            final_rows = []
            for item in session_data:
                if item["name"].strip():
                    volume = item["weight"] * item["sets"] * item["reps"]
                    final_rows.append([
                        str(log_date),
                        selected_template,
                        item["name"],
                        item["weight"],
                        item["sets"],
                        item["reps"],
                        item["rpe"],
                        volume
                    ])
            
            if final_rows:
                # Use standardized lowercase key
                if batch_append("workouts", final_rows):
                    st.balloons()
                    st.success(f"Successfully logged {len(final_rows)} exercises!")
            else:
                st.warning("Please enter at least one exercise name.")

    # Custom row management outside the form
    if selected_template == "Custom":
        if st.button("➕ Add Exercise"):
            st.session_state.custom_exercises.append("")
            st.rerun()

def render_running_form():
    st.subheader("🏃 Engine Session")
    
    # Use .date() for clean date objects
    log_date = st.date_input("Run Date", datetime.now().date(), key="run_date_picker")

    with st.form(key="running_form_v1"):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.number_input("Distance (km)", min_value=0.0, step=0.1, key="run_dist")
            dur = st.text_input("Duration (MM:SS)", value="00:00", key="run_dur")
        with col2:
            hr = st.number_input("Avg Heart Rate (bpm)", min_value=0, step=1, key="run_hr")
            hrr = st.number_input("HR Recovery (1 min drop)", min_value=0, step=1, key="run_hrr")
            
        submitted = st.form_submit_button("💾 Save Run")

        if submitted:
            # Basic duration to pace calculation
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
                
                run_row = [[str(log_date), dist, dur, pace_str, hr, hrr]]
                # Use standardized lowercase key
                if batch_append("running", run_row):
                    st.success("Run log updated!")
            except ValueError:
                st.error("Invalid duration format. Use MM:SS (e.g., 25:30)")

def render_biohack_form():
    st.subheader("💊 Biohack & System Status")
    
    # Use .date() for clean date objects
    log_date = st.date_input("Log Date", datetime.now().date(), key="bio_date_picker")

    with st.form(key="biohack_form_v1"):
        st.markdown("### Supplements")
        c1, c2, c3 = st.columns(3)
        with c1:
            fish_oil = st.checkbox("Fish Oil", key="bio_fish")
            astax = st.checkbox("Astaxanthin", key="bio_astax")
        with c2:
            mag = st.checkbox("Magnesium", key="bio_mag")
            zinc = st.checkbox("Zinc", key="bio_zinc")
        with c3:
            b_comp = st.checkbox("B-Complex", key="bio_bcomp")
            creatine = st.checkbox("Creatine", key="bio_creatine")
        
        st.divider()
        st.markdown("### System Status (1-10)")
        s1, s2 = st.columns(2)
        with s1:
            shoulder = st.slider("Left Shoulder Stability", 1, 10, 5, key="bio_shoulder")
        with s2:
            pppd = st.slider("PPPD / Dizziness", 1, 10, 1, key="bio_pppd")
            
        st.divider()
        st.markdown("### Nutrition")
        n1, n2 = st.columns(2)
        with n1:
            protein = st.number_input("Protein (g)", min_value=0, step=1, key="bio_protein")
        with n2:
            cal_status = st.selectbox("Calorie Status", ["Deficit", "Maintenance", "Surplus"], key="bio_cal")

        submitted = st.form_submit_button("✅ Save Daily Biohack")
        
        if submitted:
            bio_row = [[
                str(log_date), 
                int(fish_oil), int(astax), int(mag), int(zinc), int(b_comp), int(creatine),
                shoulder, pppd, protein, cal_status
            ]]
            # Use standardized lowercase key
            if batch_append("biohack", bio_row):
                st.success("Biohack status saved!")
