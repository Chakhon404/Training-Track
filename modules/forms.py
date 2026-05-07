import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_api import batch_append, fetch_all_records, update_worksheet

def get_timestamp(log_date, log_time):
    return f"{log_date} {log_time.strftime('%H:%M')}"

def render_plan_builder():
    st.header("🛠️ Training Plan Builder")
    st.info("Define recurring training templates. Plans are stored in the 'Training_Plans' tab.")
    
    # 1. New Plan Form
    with st.expander("➕ Create New Plan", expanded=True):
        with st.form("new_plan_form"):
            plan_name = st.text_input("Plan Name", placeholder="e.g., Upper Body A")
            st.write("List up to 10 exercises per plan:")
            
            ex_data = []
            for i in range(10):
                c1, c2 = st.columns([3, 1])
                name = c1.text_input(f"Exercise {i+1}", key=f"ex_n_{i}")
                etype = c2.selectbox("Type", ["Heavy", "Bodyweight"], key=f"ex_t_{i}")
                ex_data.append({"name": name, "type": etype})
            
            if st.form_submit_button("💾 Save Plan"):
                if not plan_name.strip():
                    st.error("Please provide a plan name.")
                else:
                    new_rows = []
                    for ex in ex_data:
                        if ex["name"].strip():
                            new_rows.append([plan_name.strip(), ex["name"].strip(), ex["type"]])
                    
                    if new_rows:
                        if batch_append("training_plans", new_rows):
                            st.success(f"Plan '{plan_name}' saved!")
                            st.rerun()
                    else:
                        st.warning("Add at least one exercise label.")

    # 2. Existing Plans Management
    st.subheader("📋 Active Plans")
    raw_plans = fetch_all_records("training_plans")
    if raw_plans:
        df_p = pd.DataFrame(raw_plans)
        if 'Plan Name' in df_p.columns:
            unique_plans = df_p['Plan Name'].unique()
            for p_name in unique_plans:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"### {p_name}")
                    if c2.button("🗑️ Delete", key=f"del_{p_name}"):
                        remaining = df_p[df_p['Plan Name'] != p_name]
                        # Re-attach headers and overwrite
                        matrix = [df_p.columns.tolist()] + remaining.values.tolist()
                        if update_worksheet("training_plans", matrix):
                            st.rerun()
                    
                    # Show preview of exercises
                    p_exercises = df_p[df_p['Plan Name'] == p_name]
                    ex_list = ", ".join([f"{r['Exercise']} ({r['Type']})" for _, r in p_exercises.iterrows()])
                    st.caption(ex_list)
    else:
        st.info("No plans found. Build your first one above!")

def render_workout_form():
    st.subheader("🏋️ Training Logger")
    
    # Fetch plans from DB
    raw_plans = fetch_all_records("training_plans")
    if not raw_plans:
        st.warning("No plans found. Use the 'Plan Builder' in the System sidebar to get started.")
        return
        
    df_p = pd.DataFrame(raw_plans)
    if 'Plan Name' not in df_p.columns:
        st.error("Training Plans tab structure is invalid.")
        return
        
    plan_names = df_p['Plan Name'].unique().tolist()
    selected_plan = st.selectbox("Select Training Plan", plan_names)
    
    # Filter exercises
    plan_ex = df_p[df_p['Plan Name'] == selected_plan]
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="tr_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="tr_time")
    
    log_ts = get_timestamp(l_date, l_time)

    with st.form(key=f"workout_form_{selected_plan}"):
        session_results = []
        for i, row in plan_ex.iterrows():
            ex_n = row['Exercise']
            ex_t = row['Type']
            
            st.markdown(f"#### {ex_n} ({ex_t})")
            
            if ex_t == "Heavy":
                c1, c2, c3 = st.columns(3)
                w = c1.number_input("Weight (kg)", min_value=0.0, step=0.5, key=f"w_{i}")
                s = c2.number_input("Sets", min_value=0, step=1, key=f"s_{i}")
                r = c3.number_input("Reps", min_value=0, step=1, key=f"r_{i}")
            else:
                c1, c2 = st.columns(2)
                s = c1.number_input("Sets", min_value=0, step=1, key=f"s_{i}")
                r = c2.number_input("Reps", min_value=0, step=1, key=f"r_{i}")
                w = 0.0
            
            rpe = st.slider("Intensity (RPE)", 1.0, 10.0, 7.0, 0.5, key=f"rpe_{i}")
            session_results.append({"name": ex_n, "type": ex_t, "w": w, "s": s, "r": r, "rpe": rpe})
            st.divider()

        if st.form_submit_button("💾 Save Training Session"):
            final_rows = []
            for item in session_results:
                if item["s"] > 0:
                    volume = item["w"] * item["s"] * item["r"] if item["type"] == "Heavy" else 0
                    # [Date, Plan, Exercise, Weight, Sets, Reps, RPE, Volume]
                    final_rows.append([log_ts, selected_plan, item["name"], item["w"], item["s"], item["r"], item["rpe"], volume])
            
            if final_rows and batch_append("workouts", final_rows):
                st.success(f"Session saved: {len(final_rows)} exercises logged.")

def render_running_form():
    st.subheader("🏃 Movement Tracker")
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="run_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="run_time")
    
    log_ts = get_timestamp(l_date, l_time)

    with st.form(key="run_form_v2"):
        # New Category Selection
        cat = st.selectbox("Activity Category", ["Easy", "Tempo", "Interval", "Long", "Walk"])
        
        c1, c2 = st.columns(2)
        dist = c1.number_input("Distance (km)", min_value=0.0, step=0.1)
        dur = c2.text_input("Duration (MM:SS)", value="00:00")
        
        c3, c4 = st.columns(2)
        hr = c3.number_input("Avg Heart Rate", min_value=0, step=1)
        hrr = c4.number_input("Recovery Delta", min_value=0, step=1)
            
        if st.form_submit_button("💾 Log Movement"):
            try:
                p = dur.split(":")
                mins, secs = (int(p[0]), int(p[1])) if len(p) == 2 else (0, 0)
                tot_s = mins * 60 + secs
                
                pace_s = "0:00"
                if dist > 0:
                    p_s = tot_s / dist
                    pace_s = f"{int(p_s // 60)}:{int(p_s % 60):02d}"
                
                # Appending [Date, Dist, Dur, Pace, HR, HRR, Category]
                if batch_append("running", [[log_ts, dist, dur, pace_s, hr, hrr, cat]]):
                    st.success("Movement session logged.")
            except:
                st.error("Use MM:SS format for duration.")

def render_biohack_form():
    st.subheader("🍱 Nutrition Log")
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="nut_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="nut_time")
    
    log_ts = get_timestamp(l_date, l_time)

    with st.form(key="nut_form"):
        st.markdown("### Supplements")
        c1, c2, c3, c4 = st.columns(4)
        crea = c1.checkbox("Creatine")
        prot = c2.checkbox("Protein Powder")
        vit = c3.checkbox("Multi-Vitamin")
        omg = c4.checkbox("Omega 3")
            
        st.divider()
        st.markdown("### Energy & Macros")
        n1, n2, n3, n4 = st.columns(4)
        cal = n1.number_input("Calories", min_value=0, step=50)
        p_g = n2.number_input("Protein (g)", min_value=0, step=1)
        c_g = n3.number_input("Carbs (g)", min_value=0, step=1)
        f_g = n4.number_input("Fat (g)", min_value=0, step=1)

        if st.form_submit_button("✅ Save Nutrition"):
            # The Great Purge: PPPD, Shoulder, Weight padded with 0/0.0
            # Sheet mapping: [Date, Creatine, Prot_P, MultiV, Omega3, PPPD, Shoulder, Calories, Prot_g, Carb_g, Fat_g, Weight_kg]
            row = [[log_ts, int(crea), int(prot), int(vit), int(omg), 0, 0, cal, p_g, c_g, f_g, 0.0]]
            if batch_append("biohack", row):
                st.success("Nutrition data saved.")
