import streamlit as st
import pandas as pd
import json
from datetime import datetime
from modules.database import get_db

# json_key → (display_name, session_key, db_column)
SUPPLEMENT_MAP = {
    "creatine":       ("Creatine",       "nut_crea",         "creatine"),
    "protein_powder": ("Protein Powder", "nut_prot",         "protein_powder"),
    "multi_vitamin":  ("Multi-Vitamin",  "nut_vit",          "multivitamin"),
    "omega_3":        ("Omega-3",        "nut_omg",          "omega3"),
    "fish_oil":       ("Fish Oil",       "nut_fish_oil",     "fish_oil"),
    "astaxanthin":    ("Astaxanthin",    "nut_astaxanthin",  "astaxanthin"),
    "magnesium":      ("Magnesium",      "nut_magnesium",    "magnesium"),
    "zinc":           ("Zinc",           "nut_zinc",         "zinc"),
    "vitamin_d3":     ("Vitamin D3",     "nut_vitamin_d3",   "vitamin_d3"),
    "vitamin_c":      ("Vitamin C",      "nut_vitamin_c",    "vitamin_c"),
    "bcaa_eaa":       ("BCAA/EAA",       "nut_bcaa_eaa",     "bcaa_eaa"),
    "pre_workout":    ("Pre-Workout",    "nut_pre_workout",  "pre_workout"),
    "caffeine":       ("Caffeine",       "nut_caffeine",     "caffeine"),
    "probiotics":     ("Probiotics",     "nut_probiotics",   "probiotics"),
    "b_complex":      ("B-Complex",      "nut_b_complex",    "b_complex"),
}

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
                etype = c2.selectbox("Type", ["Heavy", "Bodyweight", "Timed"], key=f"ex_t_{i}")
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
    form_key = f"draft_workout_{st.session_state.get('user_id', 'default')}"

    if "work_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        st.session_state.work_date = datetime.strptime(draft.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
        st.session_state.work_time = datetime.strptime(draft.get("time", datetime.now().strftime("%H:%M:%S")), "%H:%M:%S").time()
        
        saved_plan = draft.get("plan_name")
        st.session_state.work_plan_name = saved_plan if saved_plan in plan_names else plan_names[0]
        
        dyn_fields = draft.get("exercises", {})
        for k, v in dyn_fields.items():
            st.session_state[k] = v
            
        st.session_state.work_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "work_date" not in st.session_state:
        st.session_state.work_date = datetime.now().date()
    if "work_time" not in st.session_state:
        st.session_state.work_time = datetime.now().time()
    if "work_plan_name" not in st.session_state:
        st.session_state.work_plan_name = plan_names[0]

    def save_workout_draft():
        curr_plan = st.session_state.get("work_plan_name")
        if not curr_plan:
            return
        selected_plan = next((p for p in plans if p['name'] == curr_plan), None)
        
        ex_data = {}
        if selected_plan:
            for i, ex in enumerate(selected_plan['exercises']):
                if ex['type'] == "Heavy":
                    ex_data[f"work_w_{i}"] = st.session_state.get(f"work_w_{i}", 0.0)
                elif ex['type'] == "Timed":
                    ex_data[f"work_d_{i}"] = st.session_state.get(f"work_d_{i}", 0)
                ex_data[f"work_s_{i}"] = st.session_state.get(f"work_s_{i}", 0)
                ex_data[f"work_r_{i}"] = st.session_state.get(f"work_r_{i}", 0)
                ex_data[f"work_rpe_{i}"] = st.session_state.get(f"work_rpe_{i}", 7.0)

        data = {
            "date": str(st.session_state.work_date),
            "time": st.session_state.work_time.strftime("%H:%M:%S"),
            "plan_name": curr_plan,
            "exercises": ex_data
        }
        db.save_draft(form_key, data)

    selected_plan_name = st.selectbox("Select Training Plan", plan_names, key="work_plan_name", on_change=save_workout_draft)
    selected_plan = next(p for p in plans if p['name'] == selected_plan_name)

    # Fetch latest weight for volume calculation
    latest_weight_entry = db.fetch_weight()
    if latest_weight_entry:
        import pandas as pd
        df_w = pd.DataFrame(latest_weight_entry)
        df_w['log_ts'] = pd.to_datetime(df_w['log_ts'], format='ISO8601')
        bodyweight_kg = float(df_w.sort_values('log_ts').iloc[-1]['weight'])
    else:
        profile = db.fetch_profile() or {}
        bodyweight_kg = float(profile.get('weight_kg') or 0.0)
    
    st.session_state["bodyweight_kg"] = bodyweight_kg

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="work_date", on_change=save_workout_draft)
    with col_t:
        l_time = st.time_input("Time", key="work_time", on_change=save_workout_draft)

    session_results = []
    for i, ex in enumerate(selected_plan['exercises']):
        ex_n = ex['name']
        ex_t = ex['type']

        # --- Standardized Widget Initialization ---
        if f"work_s_{i}" not in st.session_state:
            st.session_state[f"work_s_{i}"] = 0
        if f"work_r_{i}" not in st.session_state:
            st.session_state[f"work_r_{i}"] = 0
        if ex_t == "Heavy":
            if f"work_w_{i}" not in st.session_state:
                st.session_state[f"work_w_{i}"] = 0.0
        elif ex_t == "Timed":
            if f"work_d_{i}" not in st.session_state:
                st.session_state[f"work_d_{i}"] = 0

        st.markdown(f"#### {ex_n} ({ex_t})")
        history = db.fetch_exercise_history(ex_n)
        if history:
            import pandas as pd
            hist_str = " → ".join([
                f"{h['weight']}kg × {h['sets']}×{h['reps']} @ RPE {h['rpe']}"
                if h['weight'] > 0 else
                f"{h['sets']}×{h['reps']} @ RPE {h['rpe']}"
                for h in history
            ])
            st.caption(f"📊 Last {len(history)}: {hist_str}")

        if ex_t == "Heavy":
            c1, c2, c3 = st.columns(3)
            w = c1.number_input("Weight (kg)", min_value=0.0, step=0.5, key=f"work_w_{i}", on_change=save_workout_draft)
            s = c2.number_input("Sets", min_value=0, step=1, key=f"work_s_{i}", on_change=save_workout_draft)
            r = c3.number_input("Reps", min_value=0, step=1, key=f"work_r_{i}", on_change=save_workout_draft)
            d = 0
        elif ex_t == "Timed":
            c1, c2 = st.columns(2)
            s = c1.number_input("Sets", min_value=0, step=1, key=f"work_s_{i}", on_change=save_workout_draft)
            d = c2.number_input("Duration per set (sec)", min_value=0, step=5, key=f"work_d_{i}", on_change=save_workout_draft)
            r = 0
            w = 0.0
        else:
            c1, c2 = st.columns(2)
            s = c1.number_input("Sets", min_value=0, step=1, key=f"work_s_{i}", on_change=save_workout_draft)
            r = c2.number_input("Reps", min_value=0, step=1, key=f"work_r_{i}", on_change=save_workout_draft)
            w = 0.0
            d = 0

        rpe_key = f"work_rpe_{i}"
        if rpe_key not in st.session_state:
            st.session_state[rpe_key] = 7.0
        rpe = st.slider("Intensity (RPE)", 1.0, 10.0, step=0.5, key=rpe_key, on_change=save_workout_draft)
        session_results.append({"name": ex_n, "type": ex_t, "w": w, "s": s, "r": r, "d": d, "rpe": rpe})
        st.divider()

    submitted = st.button("💾 Save Training Session")

    # Step 1: on submit, check duplicate and set show_confirm flag
    if submitted:
        date_str = str(l_date)
        dup_count = db.check_duplicate_workout(date_str)
        if dup_count > 0:
            st.session_state.workout_show_confirm = True
            st.session_state.workout_pending_date = date_str
        else:
            # No duplicate — save directly
            log_ts = get_timestamp(l_date, l_time)
            final_rows = []
            for item in session_results:
                if item["s"] > 0:
                    if item["type"] == "Bodyweight":
                        volume = bodyweight_kg * item["s"] * item["r"]
                    elif item["type"] == "Timed":
                        volume = bodyweight_kg * item["s"] * (item["d"] / 60)
                    else:
                        volume = item["w"] * item["s"] * item["r"]
                    final_rows.append({
                        "log_ts": log_ts,
                        "plan_name": selected_plan_name,
                        "exercise": item["name"],
                        "weight": item["w"],
                        "sets": item["s"],
                        "reps": item["r"],
                        "rpe": item["rpe"],
                        "volume": volume,
                        "duration_sec": item.get("d", 0)
                    })

            if final_rows:
                if db.save_workout(final_rows):
                    st.success(f"✅ Session saved: {len(final_rows)} exercises logged.")
                    db.clear_draft(form_key)
                    st.session_state.pop("work_draft_loaded", None)
            else:
                st.warning("No exercises with sets > 0. Nothing saved.")

    # Step 2: show confirmation UI OUTSIDE if submitted — persists across reruns
    if st.session_state.get("workout_show_confirm"):
        date_str = st.session_state.get("workout_pending_date", "")
        st.warning(f"⚠️ Duplicate entries found on {date_str}.")
        col1, col2, col3 = st.columns(3)
        if col1.button("💾 Save Anyway", key="workout_save_anyway"):
            st.session_state.workout_confirm_overwrite = True
            st.session_state.pop("workout_show_confirm", None)
            st.rerun()
        if col2.button("🔄 Overwrite (delete old first)", key="workout_overwrite"):
            st.session_state.workout_confirm_overwrite = True
            st.session_state.workout_do_overwrite = True
            st.session_state.pop("workout_show_confirm", None)
            st.rerun()
        if col3.button("❌ Cancel", key="workout_cancel"):
            st.session_state.pop("workout_show_confirm", None)
            st.session_state.pop("workout_pending_date", None)
            st.rerun()

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

    # --- Standardized Widget Initialization ---
    if "run_date" not in st.session_state:
        st.session_state.run_date = datetime.now().date()
    if "run_time" not in st.session_state:
        st.session_state.run_time = datetime.now().time()
    if "run_cat" not in st.session_state:
        st.session_state.run_cat = "Easy"
    if "run_dist" not in st.session_state:
        st.session_state.run_dist = 0.0
    if "run_dur" not in st.session_state:
        st.session_state.run_dur = "00:00"
    if "run_hr" not in st.session_state:
        st.session_state.run_hr = 0
    if "run_hrr" not in st.session_state:
        st.session_state.run_hrr = 0

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

    # Step 1: on submit, check duplicate and set show_confirm flag
    if submitted:
        date_str = str(l_date)
        dup_count = db.check_duplicate_run(date_str)
        if dup_count > 0:
            st.session_state.run_show_confirm = True
            st.session_state.run_pending_date = date_str
        else:
            log_ts = get_timestamp(l_date, l_time)
            try:
                p = dur.split(":")
                mins, secs = (float(p[0]), float(p[1])) if len(p) == 2 else (0.0, 0.0)
                duration_min = mins + (secs / 60.0)

                pace_s = "0:00"
                if float(dist) > 0:
                    pace_decimal = duration_min / float(dist)
                    p_mins = int(pace_decimal)
                    p_secs = int((pace_decimal - p_mins) * 60)
                    pace_s = f"{p_mins}:{p_secs:02d}"

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
                    st.session_state.pop("run_draft_loaded", None)
            except Exception:
                st.error("Use MM:SS format for duration.")

    # Step 2: show confirmation UI OUTSIDE if submitted
    if st.session_state.get("run_show_confirm"):
        date_str = st.session_state.get("run_pending_date", "")
        st.warning(f"⚠️ Duplicate entries found on {date_str}.")
        col1, col2, col3 = st.columns(3)
        if col1.button("💾 Save Anyway", key="run_save_anyway"):
            st.session_state.run_confirm_overwrite = True
            st.session_state.pop("run_show_confirm", None)
            st.rerun()
        if col2.button("🔄 Overwrite (delete old first)", key="run_overwrite"):
            st.session_state.run_confirm_overwrite = True
            st.session_state.run_do_overwrite = True
            st.session_state.pop("run_show_confirm", None)
            st.rerun()
        if col3.button("❌ Cancel", key="run_cancel"):
            st.session_state.pop("run_show_confirm", None)
            st.session_state.pop("run_pending_date", None)
            st.rerun()

def render_biohack_form():
    db = get_db()
    st.subheader("🍱 Nutrition Log")
    form_key = f"draft_nutrition_{st.session_state.get('user_id', 'default')}"

    # ── JSON Quick Fill ──────────────────────────────────
    with st.expander("⚡ Quick Fill", expanded=False):
        st.caption("Paste JSON from your Gemini Gem to auto-fill the form below.")
        
        json_input = st.text_area(
            "Paste JSON here",
            height=200,
            placeholder='{\n  "log_date": "2026-05-11",\n  "log_time": "12:30",\n  "supplements": {\n    "creatine": true,\n    "protein_powder": false,\n    "multi_vitamin": true,\n    "omega_3": true\n  },\n  "energy_macros": {\n    "calories": 2100,\n    "protein_g": 145,\n    "carbs_g": 210,\n    "fat_g": 65\n  },\n  "meal_score": 8\n}',
            key="nut_json_input"
        )

        if st.button("📋 Fill Form from JSON", key="nut_json_fill"):
            if json_input.strip():
                try:
                    data = json.loads(json_input)

                    # Parse date
                    if "log_date" in data:
                        st.session_state.nut_date = datetime.strptime(
                            data["log_date"], "%Y-%m-%d"
                        ).date()

                    # Parse time
                    if "log_time" in data:
                        st.session_state.nut_time = datetime.strptime(
                            data["log_time"], "%H:%M"
                        ).time()

                    # Parse supplements (map key names)
                    sups = data.get("supplements", {})
                    for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                        if json_key in sups:
                            st.session_state[sess_key] = bool(sups[json_key])

                    # food_name (JSON uses "name_food")
                    if "name_food" in data:
                        st.session_state.nut_food_name = str(data["name_food"])
                    elif "food_name" in data:
                        st.session_state.nut_food_name = str(data["food_name"])

                    # Parse macros
                    macros = data.get("energy_macros", {})
                    st.session_state.nut_cal = int(macros.get("calories", st.session_state.get("nut_cal", 0)))
                    st.session_state.nut_pg  = int(macros.get("protein_g", st.session_state.get("nut_pg", 0)))
                    st.session_state.nut_cg  = int(macros.get("carbs_g", st.session_state.get("nut_cg", 0)))
                    st.session_state.nut_fg  = int(macros.get("fat_g", st.session_state.get("nut_fg", 0)))

                    # Parse meal_score
                    if "meal_score" in data:
                        st.session_state.nut_meal_score = int(data["meal_score"])

                    st.success("✅ Form filled! Review below and click Save.")
                    st.rerun()

                except json.JSONDecodeError:
                    st.error("❌ Invalid JSON format. Please check and try again.")
                except Exception as e:
                    st.error(f"❌ Error parsing JSON: {e}")
            else:
                st.warning("Please paste a JSON first.")

    if "nut_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        st.session_state.nut_date = datetime.strptime(draft.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
        st.session_state.nut_time = datetime.strptime(draft.get("time", datetime.now().strftime("%H:%M:%S")), "%H:%M:%S").time()
        
        # food_name
        st.session_state.nut_food_name = draft.get("food_name", "")
        
        # Load default supplements from user profile if no draft exists
        if not draft:
            profile = db.fetch_profile() or {}
            default_sups = profile.get("default_supplements") or []
        else:
            default_sups = []

        for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
            draft_val = draft.get(db_col)
            if draft_val is not None:
                st.session_state[sess_key] = bool(draft_val)
            else:
                st.session_state[sess_key] = json_key in default_sups
        
        st.session_state.nut_cal = draft.get("cal", 0)
        st.session_state.nut_pg = draft.get("p_g", 0)
        st.session_state.nut_cg = draft.get("c_g", 0)
        st.session_state.nut_fg = draft.get("f_g", 0)
        st.session_state.nut_meal_score = draft.get("meal_score", 5)
        st.session_state.nut_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "nut_date" not in st.session_state:
        st.session_state.nut_date = datetime.now().date()
    if "nut_time" not in st.session_state:
        st.session_state.nut_time = datetime.now().time()
    if "nut_food_name" not in st.session_state:
        st.session_state.nut_food_name = ""
    if "nut_cal" not in st.session_state:
        st.session_state.nut_cal = 0
    if "nut_pg" not in st.session_state:
        st.session_state.nut_pg = 0
    if "nut_cg" not in st.session_state:
        st.session_state.nut_cg = 0
    if "nut_fg" not in st.session_state:
        st.session_state.nut_fg = 0
    if "nut_meal_score" not in st.session_state:
        st.session_state.nut_meal_score = 5

    def save_nut_draft():
        data = {
            "date": str(st.session_state.nut_date),
            "time": st.session_state.nut_time.strftime("%H:%M:%S"),
            "food_name": st.session_state.get("nut_food_name", ""),
            "meal_score": st.session_state.get("nut_meal_score", 5),
            "cal": st.session_state.nut_cal,
            "p_g": st.session_state.nut_pg,
            "c_g": st.session_state.nut_cg,
            "f_g": st.session_state.nut_fg,
        }
        for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
            data[db_col] = st.session_state.get(sess_key, False)
        db.save_draft(form_key, data)

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="nut_date", on_change=save_nut_draft)
    with col_t:
        l_time = st.time_input("Time", key="nut_time", on_change=save_nut_draft)

    food_name = st.text_input(
        "🍽️ Food Name / Description",
        key="nut_food_name",
        placeholder="e.g. โอ๊ตเต็มใบ 30g + โยเกิร์ต 1 ถ้วย",
        on_change=save_nut_draft
    )

    st.markdown("### 💊 Supplements")

    # Load profile supplements
    profile = db.fetch_profile() or {}
    default_sups = profile.get("default_supplements") or []

    # Filter to only show supplements in profile
    sup_keys = [k for k in SUPPLEMENT_MAP.keys() if k in default_sups]

    if not sup_keys:
        st.info("💡 No supplements configured. Go to ⚙️ System → 👤 Edit Profile & Goals to add your supplements.")
    else:
        cols_per_row = 4
        for row_start in range(0, len(sup_keys), cols_per_row):
            row_keys = sup_keys[row_start:row_start + cols_per_row]
            cols = st.columns(len(row_keys))
            for col, json_key in zip(cols, row_keys):
                display, sess_key, db_col = SUPPLEMENT_MAP[json_key]
                if sess_key not in st.session_state:
                    st.session_state[sess_key] = json_key in default_sups
                col.checkbox(display, key=sess_key, on_change=save_nut_draft)

    st.divider()
    st.markdown("### Energy & Macros")
    n1, n2, n3, n4 = st.columns(4)
    cal = n1.number_input("Calories", min_value=0, step=50, key="nut_cal", on_change=save_nut_draft)
    p_g = n2.number_input("Protein (g)", min_value=0, step=1, key="nut_pg", on_change=save_nut_draft)
    c_g = n3.number_input("Carbs (g)", min_value=0, step=1, key="nut_cg", on_change=save_nut_draft)
    f_g = n4.number_input("Fat (g)", min_value=0, step=1, key="nut_fg", on_change=save_nut_draft)

    st.divider()
    st.markdown("### ⭐ Meal Score")
    meal_score = st.slider(
        "Rate today's nutrition (1 = terrible, 10 = perfect)",
        min_value=1, max_value=10,
        step=1,
        key="nut_meal_score",
        on_change=save_nut_draft
    )

    submitted = st.button("✅ Save Nutrition")

    # Step 1: on submit
    if submitted:
        date_str = str(l_date)
        dup_count = db.check_duplicate_nutrition(date_str)
        if dup_count > 0:
            st.session_state.nut_show_confirm = True
            st.session_state.nut_pending_date = date_str
        else:
            log_ts = get_timestamp(l_date, l_time)
            nut_data = {
                "log_ts": log_ts,
                "food_name": st.session_state.get("nut_food_name", ""),
                "calories": cal,
                "protein_g": p_g,
                "carbs_g": c_g,
                "fat_g": f_g,
                "meal_score": int(st.session_state.get("nut_meal_score", 5)),
            }
            for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                nut_data[db_col] = bool(st.session_state.get(sess_key, False))
            
            if db.save_nutrition(nut_data):
                st.success("✅ Nutrition data saved.")
                db.clear_draft(form_key)
                st.session_state.pop("nut_draft_loaded", None)

    # Step 2: show confirmation UI OUTSIDE if submitted
    if st.session_state.get("nut_show_confirm"):
        date_str = st.session_state.get("nut_pending_date", "")
        st.warning(f"⚠️ Duplicate entries found on {date_str}.")
        col1, col2, col3 = st.columns(3)
        if col1.button("💾 Save Anyway", key="nut_save_anyway"):
            st.session_state.nut_confirm_overwrite = True
            st.session_state.pop("nut_show_confirm", None)
            st.rerun()
        if col2.button("🔄 Overwrite (delete old first)", key="nut_overwrite"):
            st.session_state.nut_confirm_overwrite = True
            st.session_state.nut_do_overwrite = True
            st.session_state.pop("nut_show_confirm", None)
            st.rerun()
        if col3.button("❌ Cancel", key="nut_cancel"):
            st.session_state.pop("nut_show_confirm", None)
            st.session_state.pop("nut_pending_date", None)
            st.rerun()

def render_weight_form():
    db = get_db()
    st.subheader("⚖️ Weight Log")
    form_key = f"draft_weight_{st.session_state.get('user_id', 'default')}"

    if "weight_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        st.session_state.weight_date = datetime.strptime(draft.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
        st.session_state.weight_time = datetime.strptime(draft.get("time", datetime.now().strftime("%H:%M:%S")), "%H:%M:%S").time()
        st.session_state.weight_kg = draft.get("weight_kg", 0.0)
        st.session_state.weight_bf = draft.get("weight_bf", 0.0)
        st.session_state.weight_notes = draft.get("weight_notes", "")
        st.session_state.weight_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "weight_date" not in st.session_state:
        st.session_state.weight_date = datetime.now().date()
    if "weight_time" not in st.session_state:
        st.session_state.weight_time = datetime.now().time()
    if "weight_kg" not in st.session_state:
        st.session_state.weight_kg = 0.0
    if "weight_notes" not in st.session_state:
        st.session_state.weight_notes = ""

    def save_weight_draft():
        data = {
            "date": str(st.session_state.weight_date),
            "time": st.session_state.weight_time.strftime("%H:%M:%S"),
            "weight_kg": st.session_state.weight_kg,
            "weight_notes": st.session_state.weight_notes
        }
        db.save_draft(form_key, data)

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="weight_date", on_change=save_weight_draft)
    with col_t:
        l_time = st.time_input("Time", key="weight_time", on_change=save_weight_draft)

    weight_val = st.number_input("Weight (kg)", min_value=0.0, step=0.1, key="weight_kg", on_change=save_weight_draft)
    notes = st.text_input("Notes (optional)", key="weight_notes", on_change=save_weight_draft)

    submitted = st.button("💾 Log Weight")

    # Step 1: on submit
    if submitted:
        date_str = str(l_date)
        dup_count = db.check_duplicate_weight(date_str)
        if dup_count > 0:
            st.session_state.weight_show_confirm = True
            st.session_state.weight_pending_date = date_str
        else:
            log_ts = get_timestamp(l_date, l_time)
            weight_data = {
                "log_ts": log_ts,
                "weight": weight_val,
                "notes": notes
            }
            if db.save_weight(weight_data):
                st.success("✅ Weight logged.")
                db.clear_draft(form_key)
                st.session_state.pop("weight_draft_loaded", None)

    # Step 2: show confirmation UI OUTSIDE if submitted
    if st.session_state.get("weight_show_confirm"):
        date_str = st.session_state.get("weight_pending_date", "")
        st.warning(f"⚠️ Duplicate entries found on {date_str}.")
        col1, col2, col3 = st.columns(3)
        if col1.button("💾 Save Anyway", key="weight_save_anyway"):
            st.session_state.weight_confirm_overwrite = True
            st.session_state.pop("weight_show_confirm", None)
            st.rerun()
        if col2.button("🔄 Overwrite (delete old first)", key="weight_overwrite"):
            st.session_state.weight_confirm_overwrite = True
            st.session_state.weight_do_overwrite = True
            st.session_state.pop("weight_show_confirm", None)
            st.rerun()
        if col3.button("❌ Cancel", key="weight_cancel"):
            st.session_state.pop("weight_show_confirm", None)
            st.session_state.pop("weight_pending_date", None)
            st.rerun()

def process_pending_workout(db, session_state):
    """Constructs and saves workout data from session state."""
    plans = db.fetch_plans()
    curr_plan = session_state.get("work_plan_name", "")
    selected_plan_obj = next((p for p in plans if p["name"] == curr_plan), None)
    work_date = session_state.get("work_date")
    work_time = session_state.get("work_time")

    if selected_plan_obj and work_date and work_time:
        log_ts = f"{work_date} {work_time.strftime('%H:%M:%S')}"
        
        bw = session_state.get("bodyweight_kg")
        if not bw or float(bw) == 0.0:
            profile = db.fetch_profile()
            bodyweight_kg = float(profile.get("weight_kg", 0.0)) if profile else 0.0
        else:
            bodyweight_kg = float(bw)

        final_rows = []
        for i, ex in enumerate(selected_plan_obj["exercises"]):
            ex_t = ex["type"]
            s = int(session_state.get(f"work_s_{i}", 0))
            r = int(session_state.get(f"work_r_{i}", 0))
            d = int(session_state.get(f"work_d_{i}", 0))
            w = float(session_state.get(f"work_w_{i}", 0.0)) if ex_t == "Heavy" else 0.0
            rpe = float(session_state.get(f"work_rpe_{i}", 7.0))
            if s > 0:
                if ex_t == "Bodyweight":
                    volume = bodyweight_kg * s * r
                elif ex_t == "Timed":
                    volume = bodyweight_kg * s * (d / 60)
                else:
                    volume = w * s * r
                final_rows.append({
                    "log_ts": log_ts,
                    "plan_name": curr_plan,
                    "exercise": ex["name"],
                    "weight": w,
                    "sets": s,
                    "reps": r,
                    "rpe": rpe,
                    "volume": volume,
                    "duration_sec": d
                })
        if final_rows:
            form_key = f"draft_workout_{session_state.get('user_id', 'default')}"
            if db.save_workout(final_rows):
                session_state["_pending_success"] = f"✅ Session saved: {len(final_rows)} exercises logged."
                db.clear_draft(form_key)
                session_state.pop("work_draft_loaded", None)
        else:
            session_state["_pending_warning"] = "No exercises with sets > 0. Nothing saved."

def process_pending_run(db, session_state):
    """Constructs and saves run/movement data from session state."""
    run_date = session_state.get("run_date")
    run_time = session_state.get("run_time")
    _dist = float(session_state.get("run_dist", 0.0))
    _dur = str(session_state.get("run_dur", "00:00"))
    _hr = int(session_state.get("run_hr", 0))
    _hrr = int(session_state.get("run_hrr", 0))
    _cat = str(session_state.get("run_cat", "Easy"))

    if run_date and run_time:
        log_ts = f"{run_date} {run_time.strftime('%H:%M:%S')}"
        try:
            p = _dur.split(":")
            mins, secs = (float(p[0]), float(p[1])) if len(p) == 2 else (0.0, 0.0)
            duration_min = mins + (secs / 60.0)

            pace_s = "0:00"
            if float(_dist) > 0:
                pace_decimal = duration_min / float(_dist)
                p_mins = int(pace_decimal)
                p_secs = int((pace_decimal - p_mins) * 60)
                pace_s = f"{p_mins}:{p_secs:02d}"

            run_data = {
                "log_ts": log_ts, "distance": _dist, "duration": _dur,
                "pace": pace_s, "hr": _hr, "hrr": _hrr, "category": _cat
            }
            form_key = f"draft_run_{session_state.get('user_id', 'default')}"
            if db.save_run(run_data):
                session_state["_pending_success"] = "✅ Movement session logged."
                db.clear_draft(form_key)
                session_state.pop("run_draft_loaded", None)
        except Exception:
            session_state["_pending_warning"] = "Use MM:SS format for duration."

def process_pending_nutrition(db, session_state):
    """Constructs and saves nutrition data from session state."""
    nut_date = session_state.get("nut_date")
    nut_time = session_state.get("nut_time")

    if nut_date and nut_time:
        log_ts = f"{nut_date} {nut_time.strftime('%H:%M:%S')}"
        nut_data = {
            "log_ts": log_ts,
            "food_name": str(session_state.get("nut_food_name", "")),
            "calories": int(session_state.get("nut_cal", 0)),
            "protein_g": int(session_state.get("nut_pg", 0)),
            "carbs_g": int(session_state.get("nut_cg", 0)),
            "fat_g": int(session_state.get("nut_fg", 0)),
            "meal_score": int(session_state.get("nut_meal_score", 5)),
        }
        for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
            nut_data[db_col] = bool(session_state.get(sess_key, False))

        form_key = f"draft_nutrition_{session_state.get('user_id', 'default')}"
        if db.save_nutrition(nut_data):
            session_state["_pending_success"] = "✅ Nutrition data saved."
            db.clear_draft(form_key)
            session_state.pop("nut_draft_loaded", None)

def process_pending_weight(db, session_state):
    """Constructs and saves weight data from session state."""
    weight_date = session_state.get("weight_date")
    weight_time = session_state.get("weight_time")

    if weight_date and weight_time:
        log_ts = f"{weight_date} {weight_time.strftime('%H:%M:%S')}"
        weight_data = {
            "log_ts": log_ts,
            "weight": float(session_state.get("weight_kg", 0.0)),
            "notes": str(session_state.get("weight_notes", ""))
        }
        form_key = f"draft_weight_{session_state.get('user_id', 'default')}"
        if db.save_weight(weight_data):
            session_state["_pending_success"] = "✅ Weight logged."
            db.clear_draft(form_key)
            session_state.pop("weight_draft_loaded", None)

def render_profile_form():
    db = get_db()
    st.header("👤 User Profile & Goals")
    st.caption("Your physical stats and nutrition goals. Used across all tabs.")

    profile = db.fetch_profile() or {}

    with st.form("profile_form"):
        st.markdown("### 📏 Physical Stats")
        c1, c2, c3 = st.columns(3)
        weight_kg = c1.number_input(
            "Current Weight (kg)", min_value=0.0, step=0.1,
            value=float(profile.get("weight_kg") or 0.0)
        )
        height_cm = c2.number_input(
            "Height (cm)", min_value=0.0, step=0.5,
            value=float(profile.get("height_cm") or 0.0)
        )
        body_fat = c3.number_input(
            "Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1,
            value=float(profile.get("body_fat_pct") or 0.0)
        )

        # Auto-calculate BMI and lean mass
        if height_cm > 0 and weight_kg > 0:
            bmi = weight_kg / ((height_cm / 100) ** 2)
            lean_mass = weight_kg * (1 - body_fat / 100) if body_fat > 0 else None
            mc1, mc2 = st.columns(2)
            mc1.metric("BMI", f"{bmi:.1f}")
            if lean_mass:
                mc2.metric("Lean Mass (kg)", f"{lean_mass:.1f}")

        st.divider()
        st.markdown("### 🎯 Goals")
        g1, g2 = st.columns(2)
        goal_weight = g1.number_input(
            "Target Weight (kg)", min_value=0.0, step=0.1,
            value=float(profile.get("goal_weight_kg") or 0.0)
        )

        st.markdown("#### Daily Nutrition Goals")
        n1, n2, n3, n4 = st.columns(4)
        goal_cal = n1.number_input(
            "Calories (kcal)", min_value=0, step=50,
            value=int(profile.get("goal_calories") or 2500)
        )
        goal_prot = n2.number_input(
            "Protein (g)", min_value=0, step=1,
            value=int(profile.get("goal_protein_g") or 150)
        )
        goal_carbs = n3.number_input(
            "Carbs (g)", min_value=0, step=1,
            value=int(profile.get("goal_carbs_g") or 300)
        )
        goal_fat = n4.number_input(
            "Fat (g)", min_value=0, step=1,
            value=int(profile.get("goal_fat_g") or 70)
        )

        st.divider()
        st.markdown("### 💊 Default Supplements")
        st.caption("These will be pre-checked in the Nutrition form every day.")

        sup_display_names = [display for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items()]
        sup_json_keys = [json_key for json_key in SUPPLEMENT_MAP.keys()]

        current_defaults = profile.get("default_supplements") or []
        default_indices = [sup_json_keys.index(k) for k in current_defaults if k in sup_json_keys]
        default_display = [sup_display_names[i] for i in default_indices]

        selected_display = st.multiselect(
            "Supplements you take daily by default",
            options=sup_display_names,
            default=default_display
        )

        # Convert back to json_keys for storage
        selected_json_keys = [
            sup_json_keys[sup_display_names.index(d)]
            for d in selected_display
        ]

        st.divider()
        notes = st.text_area(
            "Notes", 
            value=profile.get("notes") or "",
            placeholder="e.g. cutting phase, injured left shoulder..."
        )

        if st.form_submit_button("💾 Save Profile"):
            profile_data = {
                "weight_kg": weight_kg,
                "height_cm": height_cm,
                "body_fat_pct": body_fat,
                "goal_weight_kg": goal_weight,
                "goal_calories": goal_cal,
                "goal_protein_g": goal_prot,
                "goal_carbs_g": goal_carbs,
                "goal_fat_g": goal_fat,
                "default_supplements": selected_json_keys,
                "notes": notes
            }
            if db.save_profile(profile_data):
                st.success("✅ Profile saved.")
                st.rerun()