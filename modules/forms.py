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

    # ── ทุกอย่างอยู่ใน form เดียว ป้องกัน re-run reset ──
    with st.form(key="workout_form"):
        selected_plan_name = st.selectbox("Select Training Plan", plan_names)
        selected_plan = next(p for p in plans if p['name'] == selected_plan_name)

        col_d, col_t = st.columns(2)
        with col_d:
            l_date = st.date_input("Date", datetime.now().date())
        with col_t:
            l_time = st.time_input("Time", datetime.now().time())

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

        submitted = st.form_submit_button("💾 Save Training Session")

    # ── handle submit นอก form (best practice) ──
    if submitted:
        log_ts = get_timestamp(l_date, l_time)
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

        if final_rows:
            if db.save_workout(final_rows):
                st.success(f"✅ Session saved: {len(final_rows)} exercises logged.")
        else:
            st.warning("No exercises with sets > 0. Nothing saved.")

def render_running_form():
    db = get_db()
    st.subheader("🏃 Movement Tracker")
    form_key = f"draft_run_{st.session_state.get('user_id', 'default')}"

    if "run_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        st.session_state.run_date = datetime.strptime(draft.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
        st.session_state.run_time = datetime.strptime(draft.get("time", datetime.now().strftime("%H:%M:%S")), "%H:%M:%S").time()
        st.session_state.run_cat = draft.get("cat", "Easy")
        st.session_state.run_dist = draft.get("dist", 0.0)
        st.session_state.run_dur = draft.get("dur", "00:00")
        st.session_state.run_hr = draft.get("hr", 0)
        st.session_state.run_hrr = draft.get("hrr", 0)
        st.session_state.run_draft_loaded = True

    def save_run_draft():
        data = {
            "date": str(st.session_state.run_date),
            "time": st.session_state.run_time.strftime("%H:%M:%S"),
            "cat": st.session_state.run_cat,
            "dist": st.session_state.run_dist,
            "dur": st.session_state.run_dur,
            "hr": st.session_state.run_hr,
            "hrr": st.session_state.run_hrr
        }
        db.save_draft(form_key, data)

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="run_date", on_change=save_run_draft)
    with col_t:
        l_time = st.time_input("Time", key="run_time", on_change=save_run_draft)

    cat = st.selectbox("Activity Category", ["Easy", "Tempo", "Interval", "Long", "Walk"], key="run_cat", on_change=save_run_draft)

    c1, c2 = st.columns(2)
    dist = c1.number_input("Distance (km)", min_value=0.0, step=0.1, key="run_dist", on_change=save_run_draft)
    dur = st.text_input("Duration (MM:SS)", key="run_dur", on_change=save_run_draft)

    c3, c4 = st.columns(2)
    hr = c3.number_input("Avg Heart Rate", min_value=0, step=1, key="run_hr", on_change=save_run_draft)
    hrr = c4.number_input("Recovery Delta", min_value=0, step=1, key="run_hrr", on_change=save_run_draft)

    submitted = st.button("💾 Log Movement")

    if submitted:
        log_ts = get_timestamp(l_date, l_time)
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
                st.success("✅ Movement session logged.")
                db.clear_draft(form_key)
                del st.session_state.run_draft_loaded
        except Exception:
            st.error("Use MM:SS format for duration.")

def render_biohack_form():
    db = get_db()
    st.subheader("🍱 Nutrition Log")
    form_key = f"draft_nutrition_{st.session_state.get('user_id', 'default')}"

    if "nut_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        st.session_state.nut_date = datetime.strptime(draft.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
        st.session_state.nut_time = datetime.strptime(draft.get("time", datetime.now().strftime("%H:%M:%S")), "%H:%M:%S").time()
        st.session_state.nut_crea = draft.get("crea", False)
        st.session_state.nut_prot = draft.get("prot", False)
        st.session_state.nut_vit = draft.get("vit", False)
        st.session_state.nut_omg = draft.get("omg", False)
        st.session_state.nut_cal = draft.get("cal", 0)
        st.session_state.nut_pg = draft.get("p_g", 0)
        st.session_state.nut_cg = draft.get("c_g", 0)
        st.session_state.nut_fg = draft.get("f_g", 0)
        st.session_state.nut_draft_loaded = True

    def save_nut_draft():
        data = {
            "date": str(st.session_state.nut_date),
            "time": st.session_state.nut_time.strftime("%H:%M:%S"),
            "crea": st.session_state.nut_crea,
            "prot": st.session_state.nut_prot,
            "vit": st.session_state.nut_vit,
            "omg": st.session_state.nut_omg,
            "cal": st.session_state.nut_cal,
            "p_g": st.session_state.nut_pg,
            "c_g": st.session_state.nut_cg,
            "f_g": st.session_state.nut_fg
        }
        db.save_draft(form_key, data)

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="nut_date", on_change=save_nut_draft)
    with col_t:
        l_time = st.time_input("Time", key="nut_time", on_change=save_nut_draft)

    st.markdown("### Supplements")
    c1, c2, c3, c4 = st.columns(4)
    crea = c1.checkbox("Creatine", key="nut_crea", on_change=save_nut_draft)
    prot = c2.checkbox("Protein Powder", key="nut_prot", on_change=save_nut_draft)
    vit = c3.checkbox("Multi-Vitamin", key="nut_vit", on_change=save_nut_draft)
    omg = c4.checkbox("Omega 3", key="nut_omg", on_change=save_nut_draft)

    st.divider()
    st.markdown("### Energy & Macros")
    n1, n2, n3, n4 = st.columns(4)
    cal = n1.number_input("Calories", min_value=0, step=50, key="nut_cal", on_change=save_nut_draft)
    p_g = n2.number_input("Protein (g)", min_value=0, step=1, key="nut_pg", on_change=save_nut_draft)
    c_g = n3.number_input("Carbs (g)", min_value=0, step=1, key="nut_cg", on_change=save_nut_draft)
    f_g = n4.number_input("Fat (g)", min_value=0, step=1, key="nut_fg", on_change=save_nut_draft)

    submitted = st.button("✅ Save Nutrition")

    if submitted:
        log_ts = get_timestamp(l_date, l_time)
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
            st.success("✅ Nutrition data saved.")
            db.clear_draft(form_key)
            del st.session_state.nut_draft_loaded