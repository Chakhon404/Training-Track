import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import get_db

def get_timestamp(log_date, log_time):
    return f"{log_date} {log_time.strftime('%H:%M:%S')}"

def render_plan_builder():
    db = get_db()
    st.header("🛠️ Training Plan Builder")
    st.info("Define recurring training templates. Plans are stored in Supabase.")
    
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
                    exercises = [{"name": ex["name"].strip(), "type": ex["type"]} for ex in ex_data if ex["name"].strip()]
                    if exercises:
                        if db.add_plan({"name": plan_name.strip(), "exercises": exercises}):
                            st.success(f"Plan '{plan_name}' saved!")
                            st.rerun()
                    else:
                        st.warning("Add at least one exercise label.")

    # 2. Existing Plans Management
    st.subheader("📋 Active Plans")
    plans = db.fetch_plans()
    if plans:
        for p in plans:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"### {p['name']}")
                if c2.button("🗑️ Delete", key=f"del_{p['id']}"):
                    if db.delete_plan(p['id']):
                        st.rerun()
                
                # Show preview of exercises
                ex_list = ", ".join([f"{ex['name']} ({ex['type']})" for ex in p['exercises']])
                st.caption(ex_list)
    else:
        st.info("No plans found. Build your first one above!")

def render_workout_form():
    db = get_db()
    st.subheader("🏋️ Training Logger")
    
    plans = db.fetch_plans()
    if not plans:
        st.warning("No plans found. Use the 'Plan Builder' in the System sidebar to get started.")
        return
        
    plan_names = [p['name'] for p in plans]
    selected_plan_name = st.selectbox("Select Training Plan", plan_names)
    selected_plan = next(p for p in plans if p['name'] == selected_plan_name)
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="tr_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="tr_time")
    
    log_ts = get_timestamp(l_date, l_time)

    with st.form(key=f"workout_form_{selected_plan['id']}"):
        session_results = []
        for i, ex in enumerate(selected_plan['exercises']):
            ex_n = ex['name']
            ex_t = ex['type']
            
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
                    final_rows.append({
                        "log_ts": log_ts,
                        "plan_name": selected_plan_name,
                        "exercise": item["name"],
                        "weight": item["w"],
                        "sets": item["s"],
                        "reps": item["r"],
                        "rpe": item["rpe"],
                        "volume": volume
                    })
            
            if final_rows and db.save_workout(final_rows):
                st.success(f"Session saved: {len(final_rows)} exercises logged.")

def render_running_form():
    db = get_db()
    st.subheader("🏃 Movement Tracker")
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="run_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="run_time")
    
    log_ts = get_timestamp(l_date, l_time)

    with st.form(key="run_form_v2"):
        cat = st.selectbox("Activity Category", ["Easy", "Tempo", "Interval", "Long", "Walk"])
        
        c1, c2 = st.columns(2)
        dist = c1.number_input("Distance (km)", min_value=0.0, step=0.1)
        dur = st.text_input("Duration (MM:SS)", value="00:00")
        
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
                
                run_data = {
                    "log_ts": log_ts,
                    "distance": dist,
                    "duration": dur,
                    "pace": pace_s,
                    "hr": hr,
                    "hrr": hrr,
                    "category": cat
                }
                if db.save_run(run_data):
                    st.success("Movement session logged.")
            except:
                st.error("Use MM:SS format for duration.")

def render_biohack_form():
    db = get_db()
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
            nut_data = {
                "log_ts": log_ts,
                "calories": cal,
                "protein_g": p_g,
                "carbs_g": c_g,
                "fat_g": f_g,
                "creatine": crea,
                "protein_powder": prot,
                "multivitamin": vit,
                "omega3": omg
            }
            if db.save_nutrition(nut_data):
                st.success("Nutrition data saved.")
