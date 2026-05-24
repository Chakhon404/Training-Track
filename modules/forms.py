import streamlit as st
import pandas as pd
import json
import time
import pytz
from datetime import datetime
from modules.database import get_db, fetch_profile_cached, fetch_workouts_cached, fetch_plans_cached, fetch_last_session_cached
from modules.constants import SUPPLEMENT_MAP

def get_timestamp(log_date, log_time):
    return f"{log_date} {log_time.strftime('%H:%M:%S')}"

def render_plan_builder():
    db = get_db()
    st.header("🛠️ Training Plan Builder")
    st.info("Define recurring training templates. Plans are stored in Supabase.")
    
    # Detect edit mode
    is_edit_mode = "plan_editing_id" in st.session_state

    if is_edit_mode:
        st.info(f"✏️ Editing plan: **{st.session_state['plan_editing_name']}**")

    # Initialize session state for dynamic builder
    if "plan_builder_exercises" not in st.session_state:
        st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]

    # 1. Dynamic Plan Form
    with st.expander("➕ Create New Plan" if not is_edit_mode else "✏️ Edit Plan", expanded=True):
        # We don't use st.form because we need dynamic row additions/deletions
        exercises = st.session_state["plan_builder_exercises"]
        
        for i in range(len(exercises)):
            c1, c2, c3 = st.columns([3, 1, 0.5])
            exercises[i]["name"] = c1.text_input(f"Exercise {i+1}", value=exercises[i]["name"], key=f"pb_name_{i}")
            exercises[i]["type"] = c2.selectbox("Type", ["Heavy", "Bodyweight", "Timed"], index=["Heavy", "Bodyweight", "Timed"].index(exercises[i]["type"]), key=f"pb_type_{i}")
            if c3.button("🗑️", key=f"pb_del_{i}"):
                st.session_state["plan_builder_exercises"].pop(i)
                st.rerun()
        
        if st.button("➕ Add Exercise"):
            st.session_state["plan_builder_exercises"].append({"name": "", "type": "Heavy"})
            st.rerun()

        st.divider()

        # Plan name input — pre-fill with editing name if in edit mode
        if is_edit_mode and "plan_builder_name" not in st.session_state:
            st.session_state["plan_builder_name"] = st.session_state["plan_editing_name"]

        plan_name = st.text_input("Plan Name", key="plan_builder_name", placeholder="e.g., Upper Body A")
        
        # Cancel Edit button — only shown in edit mode
        col_save, col_cancel = st.columns([3, 1])

        if is_edit_mode:
            save_label  = "💾 Update Plan"
            save_key    = "pb_update"
        else:
            save_label  = "💾 Save Plan"
            save_key    = "pb_save"

        if col_save.button(save_label, key=save_key, type="primary"):
            # Filter and validate
            valid_exercises = [{"name": ex["name"].strip(), "type": ex["type"]} for ex in exercises if ex["name"].strip()]
            plan_name_val = plan_name.strip()

            if not plan_name_val:
                st.error("Please provide a plan name.")
            elif not valid_exercises:
                st.error("Add at least one exercise.")
            elif is_edit_mode:
                plan_id = st.session_state["plan_editing_id"]
                if db.update_plan(plan_id, {"name": plan_name_val, "exercises": valid_exercises}):
                    st.success(f"Plan '{plan_name_val}' updated!")
                    st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]
                    st.session_state.pop("plan_builder_name",    None)
                    st.session_state.pop("plan_editing_id",      None)
                    st.session_state.pop("plan_editing_name",    None)
                    st.cache_data.clear()
                    st.rerun()
            else:
                if db.add_plan({"name": plan_name_val, "exercises": valid_exercises}):
                    st.success(f"Plan '{plan_name_val}' saved!")
                    st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]
                    st.session_state.pop("plan_builder_name", None)
                    st.rerun()

        if is_edit_mode:
            if col_cancel.button("❌ Cancel", key="pb_cancel"):
                st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]
                st.session_state.pop("plan_builder_name", None)
                st.session_state.pop("plan_editing_id",   None)
                st.session_state.pop("plan_editing_name", None)
                st.rerun()

    # 2. Existing Plans Management
    st.subheader("📋 Active Plans")
    plans = fetch_plans_cached(db)
    if plans:
        for p in plans:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.markdown(f"### {p['name']}")
                if c2.button("✏️ Edit", key=f"edit_{p['id']}"):
                    # Load this plan into editor session state
                    st.session_state["plan_editing_id"]       = p["id"]
                    st.session_state["plan_editing_name"]     = p["name"]
                    st.session_state["plan_builder_exercises"] = [
                        {"name": ex["name"], "type": ex["type"]}
                        for ex in p["exercises"]
                    ]
                    st.session_state.pop("plan_builder_name", None)
                    st.rerun()
                if c3.button("🗑️ Delete", key=f"del_{p['id']}"):
                    if db.delete_plan(p['id']):
                        st.cache_data.clear()
                        st.rerun()
                ex_list = ", ".join([f"{ex['name']} ({ex['type']})" for ex in p['exercises']])
                st.caption(ex_list)
    else:
        st.info("No plans found. Build your first one above!")

def _build_workout_snapshot(plan_name, plan_obj, log_date, log_time, state):
    """Build a draft-compatible snapshot of the current workout session.
    Used to persist the last successfully saved session separately from
    the normal auto-save draft."""
    ex_data = {}
    if plan_obj:
        exercises = plan_obj.get("exercises", [])
        for i, ex in enumerate(exercises):
            nsets = int(state.get(f"work_nsets_{i}", 3))
            ex_data[f"work_nsets_{i}"] = nsets
            ex_data[f"work_rpe_{i}"]   = state.get(f"work_rpe_{i}", 7.0)
            for s in range(nsets):
                ex_data[f"work_w_{i}_{s}"] = state.get(f"work_w_{i}_{s}", 0.0)
                ex_data[f"work_r_{i}_{s}"] = state.get(f"work_r_{i}_{s}", 0)
                ex_data[f"work_d_{i}_{s}"] = state.get(f"work_d_{i}_{s}", 0)
    return {
        "date":      str(log_date),
        "time":      log_time.strftime("%H:%M:%S") if hasattr(log_time, "strftime") else str(log_time),
        "plan_name": plan_name,
        "exercises": ex_data,
        "_is_last_session": True
    }

def render_workout_form():
    db = get_db()
    st.subheader("🏋️ Training Logger")

    plans = fetch_plans_cached(db)
    if not plans:
        st.warning("No plans found. Use the 'Plan Builder' in the System sidebar to get started.")
        return

    plan_names = [p['name'] for p in plans]
    form_key = f"draft_workout_{st.session_state.get('user_id', 'default')}"

    # --- Plan Change Handling ---
    def on_plan_change():
        curr_plan = st.session_state.get("work_plan_name")
        # Clear all dynamic keys when plan changes
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("work_nsets_", "work_w_", "work_r_", "work_d_", "work_done_", "work_last_", "work_rpe_"))]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        # Also clear the draft in DB for the old plan to avoid confusion
        db.clear_draft(form_key)

    if "work_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        st.session_state.work_date = _now.date()
        st.session_state.work_time = _now.time().replace(tzinfo=None)
        
        saved_plan = draft.get("plan_name")
        st.session_state.work_plan_name = saved_plan if saved_plan in plan_names else plan_names[0]
        
        dyn_fields = draft.get("exercises", {})
        for k, v in dyn_fields.items():
            st.session_state[k] = v

        if not draft:
            _last = db.fetch_last_session_by_plan(
                st.session_state.get("work_plan_name", plan_names[0])
            )
            _selected = next(
                (p for p in plans if p["name"] == st.session_state.get("work_plan_name", plan_names[0])),
                None
            )
            if _last and _selected:
                for _i, _ex in enumerate(_selected["exercises"]):
                    _sets = _last.get(_ex["name"], [])
                    if _sets:
                        st.session_state[f"work_nsets_{_i}"] = len(_sets)
                        for _s, _row in enumerate(_sets):
                            st.session_state[f"work_w_{_i}_{_s}"]      = _row.get("weight", 0.0)
                            st.session_state[f"work_r_{_i}_{_s}"]      = _row.get("reps", 0)
                            st.session_state[f"work_d_{_i}_{_s}"]      = _row.get("duration_sec", 0)
                            st.session_state[f"work_last_w_{_i}_{_s}"] = _row.get("weight", 0.0)
                            st.session_state[f"work_last_r_{_i}_{_s}"] = _row.get("reps", 0)
            
        st.session_state.work_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "work_date" not in st.session_state or "work_time" not in st.session_state:
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        if "work_date" not in st.session_state:
            st.session_state.work_date = _now.date()
        if "work_time" not in st.session_state:
            st.session_state.work_time = _now.time().replace(tzinfo=None)
    if "work_plan_name" not in st.session_state:
        st.session_state.work_plan_name = plan_names[0]

    def save_workout_draft():
        if "work_plan_name" not in st.session_state:
            return
        now = time.time()
        if now - st.session_state.get("_last_workout_draft_save", 0) < 3:
            return
        st.session_state["_last_workout_draft_save"] = now

        curr_plan = st.session_state.get("work_plan_name")
        if not curr_plan:
            return
        selected_plan = next((p for p in plans if p['name'] == curr_plan), None)
        
        ex_data = {}
        if selected_plan:
            for i, ex in enumerate(selected_plan['exercises']):
                nsets = st.session_state.get(f"work_nsets_{i}", 3)
                ex_data[f"work_nsets_{i}"] = nsets
                ex_data[f"work_rpe_{i}"] = st.session_state.get(f"work_rpe_{i}", 7.0)
                for s in range(nsets):
                    ex_data[f"work_done_{i}_{s}"] = st.session_state.get(f"work_done_{i}_{s}", False)
                    if ex['type'] != "Bodyweight":
                        ex_data[f"work_w_{i}_{s}"] = st.session_state.get(f"work_w_{i}_{s}", 0.0)
                    if ex['type'] == "Timed":
                        ex_data[f"work_d_{i}_{s}"] = st.session_state.get(f"work_d_{i}_{s}", 0)
                    else:
                        ex_data[f"work_r_{i}_{s}"] = st.session_state.get(f"work_r_{i}_{s}", 0)

        data = {
            "plan_name": curr_plan,
            "exercises": ex_data
        }
        db.save_draft(form_key, data)

    selected_plan_name = st.selectbox("Select Training Plan", plan_names, key="work_plan_name", on_change=on_plan_change)
    selected_plan = next(p for p in plans if p['name'] == selected_plan_name)

    # --- Auto-populate from Last Session ---
    last_session = fetch_last_session_cached(db, selected_plan_name)
    
    # Initialize defaults if not already in session state
    for i, ex in enumerate(selected_plan['exercises']):
        ex_name = ex['name']
        if ex_name in last_session:
            history_sets = last_session[ex_name]
            # Populate nsets if not set
            if f"work_nsets_{i}" not in st.session_state:
                st.session_state[f"work_nsets_{i}"] = len(history_sets)
            
            for s, hset in enumerate(history_sets):
                # Store history for PR check
                st.session_state[f"work_last_w_{i}_{s}"] = hset["weight"]
                st.session_state[f"work_last_r_{i}_{s}"] = hset["reps"]
                st.session_state[f"work_last_d_{i}_{s}"] = hset["duration_sec"]
                
                # Populate inputs if not set
                if f"work_w_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_w_{i}_{s}"] = hset["weight"]
                if f"work_r_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_r_{i}_{s}"] = hset["reps"]
                if f"work_d_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_d_{i}_{s}"] = hset["duration_sec"]
        
        # Ensure nsets has a default
        if f"work_nsets_{i}" not in st.session_state:
            st.session_state[f"work_nsets_{i}"] = 3

    # Fetch latest weight for volume calculation
    latest_weight_entry = db.fetch_weight()
    if latest_weight_entry:
        import pandas as pd
        df_w = pd.DataFrame(latest_weight_entry)
        df_w['log_ts'] = pd.to_datetime(df_w['log_ts'], format='ISO8601')
        bodyweight_kg = float(df_w.sort_values('log_ts').iloc[-1]['weight'])
    else:
        profile = fetch_profile_cached(db) or {}
        bodyweight_kg = float(profile.get('weight_kg') or 0.0)
    
    st.session_state["bodyweight_kg"] = bodyweight_kg

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="work_date", on_change=save_workout_draft)
    with col_t:
        l_time = st.time_input("Time", key="work_time", on_change=save_workout_draft)

    for i, ex in enumerate(selected_plan['exercises']):
        ex_n = ex['name']
        ex_t = ex['type']

        st.markdown(f"#### {ex_n} ({ex_t})")
        
        # Last Session Summary Caption
        if ex_n in last_session:
            h_sets = last_session[ex_n]
            h_date = h_sets[0]["date"]
            h_details = []
            for h in h_sets:
                if ex_t == "Timed": h_details.append(f"{h['duration_sec']}s")
                elif ex_t == "Bodyweight": h_details.append(f"{h['reps']}r")
                else: h_details.append(f"{h['weight']}kg × {h['reps']}")
            st.caption(f"📅 Last {h_date}: {len(h_sets)} sets • {' | '.join(h_details)}")
        else:
            st.caption("No history for this exercise in this plan.")

        # --- Volume Delta Calculation ---
        # Current session volume
        curr_vol = 0.0
        nsets_i = st.session_state.get(f"work_nsets_{i}", 0)
        for s in range(nsets_i):
            w = float(st.session_state.get(f"work_w_{i}_{s}", 0.0))
            r = int(st.session_state.get(f"work_r_{i}_{s}", 0))
            d = int(st.session_state.get(f"work_d_{i}_{s}", 0))
            if ex_t == "Heavy":
                curr_vol += w * r
            elif ex_t == "Bodyweight":
                curr_vol += bodyweight_kg * r
            elif ex_t == "Timed":
                curr_vol += bodyweight_kg * (d / 60)

        # Last session volume
        last_sets = last_session.get(ex_n, [])
        last_vol = 0.0
        for row in last_sets:
            w = float(row.get("weight", 0.0))
            r = int(row.get("reps", 0))
            d = int(row.get("duration_sec", 0))
            if ex_t == "Heavy":
                last_vol += w * r
            elif ex_t == "Bodyweight":
                last_vol += bodyweight_kg * r
            elif ex_t == "Timed":
                last_vol += bodyweight_kg * (d / 60)

        # Display delta
        if last_vol > 0:
            delta_pct = ((curr_vol - last_vol) / last_vol) * 100
            arrow = "▲" if delta_pct >= 0 else "▼"
            color = "green" if delta_pct >= 0 else "orange"
            st.markdown(
                f"📊 Volume: **{curr_vol:.0f} kg** "
                f"<span style='color:{color}'>{arrow} {abs(delta_pct):.1f}%</span> vs last session",
                unsafe_allow_html=True
            )

        # Per-Set UI
        nsets = st.session_state[f"work_nsets_{i}"]
        
        # Header Row
        if ex_t == "Heavy":
            h_cols = st.columns([0.4, 1, 1, 0.5, 0.5, 0.5])
            h_cols[0].caption("Set")
            h_cols[1].caption("Weight")
            h_cols[2].caption("Reps")
            h_cols[3].caption("PR")
            h_cols[4].caption("Done")
            h_cols[5].caption("")
        elif ex_t == "Timed":
            h_cols = st.columns([0.4, 2, 0.5, 0.5, 0.5])
            h_cols[0].caption("Set")
            h_cols[1].caption("Duration (s)")
            h_cols[2].caption("PR")
            h_cols[3].caption("Done")
            h_cols[4].caption("")
        else: # Bodyweight
            h_cols = st.columns([0.4, 2, 0.5, 0.5, 0.5])
            h_cols[0].caption("Set")
            h_cols[1].caption("Reps")
            h_cols[2].caption("PR")
            h_cols[3].caption("Done")
            h_cols[4].caption("")

        for s in range(nsets):
            # Checkbox state for "Done"
            is_done = st.session_state.get(f"work_done_{i}_{s}", False)
            
            # Use a container to potentially highlight the row
            row_container = st.container()
            with row_container:
                if ex_t == "Heavy":
                    cols = st.columns([0.4, 1, 1, 0.5, 0.5, 0.5])
                    cols[0].markdown(f"**{s+1}**")
                    w = cols[1].number_input("W", label_visibility="collapsed", min_value=0.0, step=0.5, key=f"work_w_{i}_{s}", on_change=save_workout_draft)
                    r = cols[2].number_input("R", label_visibility="collapsed", min_value=0, step=1, key=f"work_r_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_w = st.session_state.get(f"work_last_w_{i}_{s}", 0.0)
                    last_r = st.session_state.get(f"work_last_r_{i}_{s}", 0)
                    if (w > last_w or r > last_r) and (last_w > 0 or last_r > 0):
                        cols[3].markdown("🏆", help="Personal Record!")
                    
                    cols[4].checkbox("✅", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[5].button("✕", key=f"rm_set_{i}_{s}"):
                            # shift values down
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_w_{i}_{ss}"] = st.session_state.get(f"work_w_{i}_{ss+1}", 0.0)
                                st.session_state[f"work_r_{i}_{ss}"] = st.session_state.get(f"work_r_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()

                elif ex_t == "Timed":
                    cols = st.columns([0.4, 2, 0.5, 0.5, 0.5])
                    cols[0].markdown(f"**{s+1}**")
                    d = cols[1].number_input("D", label_visibility="collapsed", min_value=0, step=5, key=f"work_d_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_d = st.session_state.get(f"work_last_d_{i}_{s}", 0)
                    if d > last_d and last_d > 0:
                        cols[2].markdown("🏆", help="Personal Record!")

                    cols[3].checkbox("✅", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[4].button("✕", key=f"rm_set_{i}_{s}"):
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_d_{i}_{ss}"] = st.session_state.get(f"work_d_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()
                else: # Bodyweight
                    cols = st.columns([0.4, 2, 0.5, 0.5, 0.5])
                    cols[0].markdown(f"**{s+1}**")
                    r = cols[1].number_input("R", label_visibility="collapsed", min_value=0, step=1, key=f"work_r_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_r = st.session_state.get(f"work_last_r_{i}_{s}", 0)
                    if r > last_r and last_r > 0:
                        cols[2].markdown("🏆", help="Personal Record!")

                    cols[3].checkbox("✅", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[4].button("✕", key=f"rm_set_{i}_{s}"):
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_r_{i}_{ss}"] = st.session_state.get(f"work_r_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()
            
            # Apply visual highlight if done
            if is_done:
                st.markdown(
                    f"""<style>div[data-testid="stVerticalBlock"] > div:nth-child({(s*2)+3}) {{ border-left: 5px solid green; padding-left: 10px; }}</style>""", 
                    unsafe_allow_html=True
                )

        if st.button(f"➕ Add Set", key=f"add_set_{i}"):
            st.session_state[f"work_nsets_{i}"] += 1
            st.rerun()

        rpe_key = f"work_rpe_{i}"
        if rpe_key not in st.session_state:
            st.session_state[rpe_key] = 7.0
        rpe = st.slider("Intensity (RPE)", 1.0, 10.0, step=0.5, key=rpe_key, on_change=save_workout_draft)
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
            for i, ex in enumerate(selected_plan['exercises']):
                ex_name = ex['name']
                ex_type = ex['type']
                nsets = st.session_state.get(f"work_nsets_{i}", 3)
                rpe = st.session_state.get(f"work_rpe_{i}", 7.0)
                
                for s in range(nsets):
                    w = st.session_state.get(f"work_w_{i}_{s}", 0.0) if ex_type != "Bodyweight" else 0.0
                    r = st.session_state.get(f"work_r_{i}_{s}", 0) if ex_type != "Timed" else 0
                    d = st.session_state.get(f"work_d_{i}_{s}", 0) if ex_type == "Timed" else 0
                    
                    if ex_type == "Bodyweight":
                        volume = bodyweight_kg * r
                    elif ex_type == "Timed":
                        volume = bodyweight_kg * (d / 60)
                    else:
                        volume = w * r
                        
                    if r > 0 or d > 0:
                        final_rows.append({
                            "log_ts": log_ts,
                            "plan_name": selected_plan_name,
                            "exercise": ex_name,
                            "weight": w,
                            "sets": nsets,
                            "reps": r,
                            "rpe": rpe,
                            "volume": volume,
                            "duration_sec": d,
                            "set_number": s + 1
                        })

            if final_rows:
                if db.save_workout(final_rows):
                    st.success(f"✅ Session saved: {len(final_rows)} rows logged.")
                    db.clear_draft(form_key)
                    # Save last session snapshot (separate from normal draft)
                    last_key = f"last_workout_{st.session_state.get('user_id', 'default')}"
                    db.save_draft(last_key, _build_workout_snapshot(
                        selected_plan_name, selected_plan, l_date, l_time, st.session_state
                    ))
                    # Clear session state for next fresh load
                    keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("work_nsets_", "work_w_", "work_r_", "work_d_", "work_done_", "work_last_", "work_rpe_"))]
                    for k in keys_to_clear:
                        st.session_state.pop(k, None)
                    st.session_state.pop("work_draft_loaded", None)
                    st.rerun()
            else:
                st.warning("No entries with reps/duration > 0. Nothing saved.")

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
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        st.session_state.run_date = _now.date()
        st.session_state.run_time = _now.time().replace(tzinfo=None)
        st.session_state.run_cat = draft.get("cat", "Easy")
        st.session_state.run_dist = draft.get("dist", 0.0)
        st.session_state.run_dur = draft.get("dur", "00:00")
        st.session_state.run_hr = draft.get("hr", 0)
        st.session_state.run_hrr = draft.get("hrr", 0)
        st.session_state.run_draft_loaded = True

    def save_run_draft():
        if "run_cat" not in st.session_state:
            return
        now = time.time()
        if now - st.session_state.get("_last_run_draft_save", 0) < 3:
            return
        st.session_state["_last_run_draft_save"] = now

        data = {
            "cat": st.session_state.run_cat,
            "dist": st.session_state.run_dist,
            "dur": st.session_state.run_dur,
            "hr": st.session_state.run_hr,
            "hrr": st.session_state.run_hrr
        }
        db.save_draft(form_key, data)

    # --- Standardized Widget Initialization ---
    if "run_date" not in st.session_state or "run_time" not in st.session_state:
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        if "run_date" not in st.session_state:
            st.session_state.run_date = _now.date()
        if "run_time" not in st.session_state:
            st.session_state.run_time = _now.time().replace(tzinfo=None)
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

    cat = st.selectbox("Activity Category", [ "Zone-2","Easy", "Tempo", "Interval", "Long", "Walk"], key="run_cat", on_change=save_run_draft)

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

    # Determine if today already has a saved nutrition entry
    _bkk = pytz.timezone("Asia/Bangkok")
    today_str = str(datetime.now(_bkk).date())
    today_entries = db.fetch_nutrition_by_date(today_str)
    sups_locked = len(today_entries) > 0

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
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        st.session_state.nut_date = _now.date()
        st.session_state.nut_time = _now.time().replace(tzinfo=None)
        
        # food_name
        st.session_state.nut_food_name = draft.get("food_name", "")
        
        # Try to pre-fill supplements from today's entries first
        if draft:
            # Draft exists — load supplements from draft as before
            for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                draft_val = draft.get(db_col)
                if draft_val is not None:
                    st.session_state[sess_key] = bool(draft_val)
                else:
                    st.session_state[sess_key] = False

        elif today_entries:
            # No draft but has entries today — pre-fill from latest entry
            latest_today = today_entries[-1]
            for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                st.session_state[sess_key] = bool(latest_today.get(db_col, False))

        else:
            # No draft, no entries today — fall back to profile defaults
            profile = fetch_profile_cached(db) or {}
            default_sups = profile.get("default_supplements") or []
            for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                st.session_state[sess_key] = json_key in default_sups
        
        st.session_state.nut_cal = draft.get("cal", 0)
        st.session_state.nut_pg = draft.get("p_g", 0)
        st.session_state.nut_cg = draft.get("c_g", 0)
        st.session_state.nut_fg = draft.get("f_g", 0)
        st.session_state.nut_meal_score = draft.get("meal_score", 5)
        st.session_state.nut_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "nut_date" not in st.session_state or "nut_time" not in st.session_state:
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        if "nut_date" not in st.session_state:
            st.session_state.nut_date = _now.date()
        if "nut_time" not in st.session_state:
            st.session_state.nut_time = _now.time().replace(tzinfo=None)
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
        if "nut_cal" not in st.session_state:
            return
        now = time.time()
        if now - st.session_state.get("_last_nut_draft_save", 0) < 3:
            return
        st.session_state["_last_nut_draft_save"] = now

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
    profile = fetch_profile_cached(db) or {}
    default_sups = profile.get("default_supplements") or []

    # Filter to only show supplements in profile
    sup_keys = [k for k in SUPPLEMENT_MAP.keys() if k in default_sups]

    if not sup_keys:
        st.info("💡 No supplements configured. Go to ⚙️ System → 👤 Edit Profile & Goals to add your supplements.")
    else:
        if sups_locked:
            st.caption("✅ Supplements already logged for today — cannot be changed.")

        cols_per_row = 4
        for row_start in range(0, len(sup_keys), cols_per_row):
            row_keys = sup_keys[row_start:row_start + cols_per_row]
            cols = st.columns(len(row_keys))
            for col, json_key in zip(cols, row_keys):
                display, sess_key, db_col = SUPPLEMENT_MAP[json_key]
                if sess_key not in st.session_state:
                    st.session_state[sess_key] = json_key in default_sups
                col.checkbox(
                    display,
                    key=sess_key,
                    on_change=save_nut_draft if not sups_locked else None,
                    disabled=sups_locked
                )

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

    if submitted:
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
            st.rerun()

def render_weight_form():
    db = get_db()
    st.subheader("⚖️ Weight Log")
    form_key = f"draft_weight_{st.session_state.get('user_id', 'default')}"

    if "weight_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        st.session_state.weight_date = _now.date()
        st.session_state.weight_time = _now.time().replace(tzinfo=None)
        st.session_state.weight_kg = draft.get("weight_kg", 0.0)
        st.session_state.weight_bf = draft.get("weight_bf", 0.0)
        st.session_state.weight_notes = draft.get("weight_notes", "")
        st.session_state.weight_draft_loaded = True

    # --- Standardized Widget Initialization ---
    if "weight_date" not in st.session_state or "weight_time" not in st.session_state:
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk)
        if "weight_date" not in st.session_state:
            st.session_state.weight_date = _now.date()
        if "weight_time" not in st.session_state:
            st.session_state.weight_time = _now.time().replace(tzinfo=None)
    if "weight_kg" not in st.session_state:
        st.session_state.weight_kg = 0.0
    if "weight_notes" not in st.session_state:
        st.session_state.weight_notes = ""

    def save_weight_draft():
        if "weight_kg" not in st.session_state:
            return
        now = time.time()
        if now - st.session_state.get("_last_weight_draft_save", 0) < 3:
            return
        st.session_state["_last_weight_draft_save"] = now

        data = {
            "date": str(st.session_state.weight_date),
            "time": st.session_state.weight_time.strftime("%H:%M:%S"),
            "weight_kg": st.session_state.weight_kg,
            "weight_bf": st.session_state.weight_bf,
            "weight_notes": st.session_state.weight_notes
        }
        db.save_draft(form_key, data)

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="weight_date", on_change=save_weight_draft)
    with col_t:
        l_time = st.time_input("Time", key="weight_time", on_change=save_weight_draft)

    weight_val = st.number_input("Weight (kg)", min_value=0.0, step=0.1, key="weight_kg", on_change=save_weight_draft)
    weight_bf_val = st.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, key="weight_bf", on_change=save_weight_draft)
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
                "body_fat_pct": float(weight_bf_val),
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
            profile = fetch_profile_cached(db)
            bodyweight_kg = float(profile.get("weight_kg", 0.0)) if profile else 0.0
        else:
            bodyweight_kg = float(bw)

        final_rows = []
        for i, ex in enumerate(selected_plan_obj["exercises"]):
            ex_t = ex["type"]
            ex_name = ex["name"]
            nsets = int(session_state.get(f"work_nsets_{i}", 3))
            rpe = float(session_state.get(f"work_rpe_{i}", 7.0))
            
            for s in range(nsets):
                w = float(session_state.get(f"work_w_{i}_{s}", 0.0)) if ex_t != "Bodyweight" else 0.0
                r = int(session_state.get(f"work_r_{i}_{s}", 0)) if ex_t != "Timed" else 0
                d = int(session_state.get(f"work_d_{i}_{s}", 0)) if ex_t == "Timed" else 0
                
                if ex_t == "Bodyweight":
                    volume = bodyweight_kg * r
                elif ex_t == "Timed":
                    volume = bodyweight_kg * (d / 60)
                else:
                    volume = w * r
                    
                if r > 0 or d > 0:
                    final_rows.append({
                        "log_ts": log_ts,
                        "plan_name": curr_plan,
                        "exercise": ex_name,
                        "weight": w,
                        "sets": nsets,
                        "reps": r,
                        "rpe": rpe,
                        "volume": volume,
                        "duration_sec": d
                    })

        if final_rows:
            form_key = f"draft_workout_{session_state.get('user_id', 'default')}"
            if db.save_workout(final_rows):
                session_state["_pending_success"] = f"✅ Session saved: {len(final_rows)} rows logged."
                db.clear_draft(form_key)
                # Save last session snapshot
                last_key = f"last_workout_{session_state.get('user_id', 'default')}"
                db.save_draft(last_key, _build_workout_snapshot(
                    curr_plan, selected_plan_obj, work_date, work_time, session_state
                ))
                session_state.pop("work_draft_loaded", None)
        else:
            session_state["_pending_warning"] = "No entries with reps/duration > 0. Nothing saved."

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
            "body_fat_pct": float(session_state.get("weight_bf", 0.0)),
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

    profile = fetch_profile_cached(db) or {}

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

def render_today_training_summary():
    db = get_db()
    _bkk = pytz.timezone("Asia/Bangkok")
    today_str = str(datetime.now(_bkk).date())
    rows = db.fetch_workouts_by_date(today_str)
    with st.container(border=True):
        st.markdown("### 🏋️ Today Training")

        if not rows:
            st.info("🏋️ no training logged today.")
            return

        df = pd.DataFrame(rows)
        df['rpe']          = pd.to_numeric(df['rpe'],          errors='coerce')
        df['volume']       = pd.to_numeric(df['volume'],       errors='coerce')

        # ── Top Metrics ──────────────────────────────────────
        total_volume = df['volume'].sum()
        avg_rpe      = df['rpe'].mean()

        c1, c2 = st.columns(2)
        c1.metric("🏋️ Total Volume", f"{total_volume:,.0f} kg")
        c2.metric("🔥 Avg RPE",      f"{avg_rpe:.1f} / 10")

        st.divider()

        # ── Exercise Breakdown Table ──────────────────────────
        # นับ Sets โดยนับ rows ที่มีชื่อ exercise ซ้ำกัน
        # เพราะแต่ละ set = 1 row ใน DB ไม่ขึ้นกับ set_number column
        with st.expander(" 🗂️ Exercise Breakdown"):
            sets_col = df.groupby("exercise")["exercise"].count().rename("Sets")

            summary = df.groupby("exercise").agg(
                Volume=("volume", "sum"),
                RPE=("rpe", "mean"),
            ).join(sets_col).reset_index()

            summary = summary[["exercise", "Sets", "Volume", "RPE"]]
            summary["Volume"] = summary["Volume"].map(lambda x: f"{x:,.1f} kg")
            summary["RPE"]    = summary["RPE"].map(lambda x: f"{x:.1f}")
            st.dataframe(summary, hide_index=True, use_container_width=True)

        # ── Per-Set Detail Expanders ──────────────────────────
        with st.expander(" 🔍 Per-Set Detail"):
            for exercise, group in df.groupby("exercise"):
                with st.expander(f"📌 {exercise}", expanded=False):
                    detail_cols = [c for c in
                        ['weight', 'reps', 'duration_sec', 'rpe', 'volume']
                        if c in group.columns]
                    st.dataframe(
                        group[detail_cols].reset_index(drop=True),
                        hide_index=False,
                        use_container_width=True
                    )

def render_exercise_history_card():
    import pandas as pd
    import streamlit as st
    
    db = get_db()
    
    st.header("📊 Open Exercise History")
    
    # 1. Fetch active workout templates/plans from database
    if hasattr(db, 'fetch_plans'):
        active_plans = db.fetch_plans()
    elif hasattr(db, 'get_plans'):
        active_plans = db.get_plans()
    elif hasattr(db, 'get_workout_plans'):
        active_plans = db.get_workout_plans()
    else:
        active_plans = db.fetch_workouts() 
        
    # 2. Fetch historical workout logs
    all_workouts = db.fetch_workouts()
    if not all_workouts:
        st.info("No workout history data found yet.")
        return

    # Convert logs to DataFrame and normalize timestamps to dates
    df_all = pd.DataFrame(all_workouts)
    try:
        df_all['log_ts'] = pd.to_datetime(df_all['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
        df_all['date'] = df_all['log_ts'].dt.date
    except Exception:
        if 'date' not in df_all.columns and 'log_ts' in df_all.columns:
            df_all['date'] = pd.to_datetime(df_all['log_ts']).dt.date

    # Ensure metric columns are fully numeric to avoid format crashes
    for col in ['weight', 'reps', 'duration_sec', 'volume']:
        if col in df_all.columns:
            df_all[col] = pd.to_numeric(df_all[col], errors='coerce').fillna(0)
        else:
            df_all[col] = 0

    # If active_plans failed to fetch or is just a raw logs dump, group dynamically
    if not active_plans or not isinstance(active_plans, list):
        st.warning("Could not map active template structures. Displaying global exercise groups instead.")
        unique_exercises = sorted(df_all['exercise'].unique().tolist())
        active_plans = [{"name": "Global Active Routines", "exercises": [{"name": ex, "type": "Heavy"} for ex in unique_exercises]}]

    # --- Plan Selection UI ---
    plan_names = [p.get('name', 'Unnamed Plan') for p in active_plans]
    selected_plan_name = st.selectbox("Select Active Plan to View History", options=plan_names)
    
    # Filter to selected plan
    selected_plan = next((p for p in active_plans if p.get('name') == selected_plan_name), None)
    
    if not selected_plan:
        st.error("Selected plan not found.")
        return

    st.markdown(f"### 🏋️ {selected_plan_name} (Most Recent History)")
    
    plan_exercises = selected_plan.get('exercises', [])
    if not plan_exercises:
        st.info("No exercises found in this plan.")
        return

    # 3. Rendering Loop for Selected Plan
    has_history_output = False
    
    for ex_obj in plan_exercises:
        if isinstance(ex_obj, dict):
            ex_name = ex_obj.get('name', '')
            ex_type = ex_obj.get('type', 'Heavy')
        else:
            ex_name = str(ex_obj)
            ex_type = 'Heavy'
            
        if not ex_name:
            continue
            
        # Filter history logs down to this specific exercise name
        df_ex = df_all[df_all['exercise'].str.lower() == ex_name.lower()].copy()
        if df_ex.empty:
            continue
            
        has_history_output = True
        st.markdown(f"**{ex_name}** *(Type: {ex_type})*")
        
        # Sort chronologically descending to target newest workouts first
        df_ex = df_ex.sort_values(by=['date', 'log_ts'], ascending=[False, True])
        
        # Strict Date Throttling: Isolate only the single most recent distinct session date
        recent_dates = df_ex['date'].unique()[:1]
        
        for target_date in recent_dates:
            date_str = target_date.strftime('%d %b %Y')
            st.markdown(f"📅 {date_str} *(Latest Session)*")
            
            df_session = df_ex[df_ex['date'] == target_date]
            
            for idx, row in enumerate(df_session.itertuples(), start=1):
                if str(ex_type).lower() == 'timed':
                    sec_val = int(getattr(row, 'duration_sec', 0))
                    st.markdown(f"*   ยก {idx}: {sec_val}วิ")
                elif str(ex_type).lower() == 'bodyweight':
                    rep_val = int(getattr(row, 'reps', 0))
                    weight_val = float(getattr(row, 'weight', 0))
                    if weight_val > 0:
                        st.markdown(f"*   round {idx}: +{weight_val:.1f} kg x {rep_val} rep")
                    else:
                        st.markdown(f"*   round {idx}: {rep_val} rep")
                else: # Default/Heavy Weight Training
                    weight_val = float(getattr(row, 'weight', 0))
                    rep_val = int(getattr(row, 'reps', 0))
                    st.markdown(f"*   round {idx}: {weight_val:.1f} kg x {rep_val} rep")
        st.write("") # Micro-spacing between exercises
        
    if has_history_output:
        st.divider()