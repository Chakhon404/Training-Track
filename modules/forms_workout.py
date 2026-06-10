import streamlit as st
import pandas as pd
import time
import pytz
from datetime import datetime
from modules.database import get_db, fetch_profile_cached, fetch_workouts_cached, fetch_plans_cached, fetch_last_session_cached, fetch_today_summary_cached, fetch_weight_cached

# 1. ปรับให้รองรับ String HH:MM ทันที
def get_timestamp(log_date, log_time_str):
    return f"{log_date} {log_time_str}:00"

def _build_workout_rows(plan_obj, session_state, log_ts, plan_name, bodyweight_kg):
    """
    Builds list of workout row dicts from session_state.
    Used by both direct save and process_pending_workout.
    Returns list of dicts ready for db.save_workout().
    """
    final_rows = []
    for i, ex in enumerate(plan_obj["exercises"]):
        ex_name = ex["name"]
        ex_type = ex["type"]
        nsets = int(session_state.get(f"work_nsets_{i}", 3))
        rpe = float(session_state.get(f"work_rpe_{i}", 7.0))
        for s in range(nsets):
            w = float(session_state.get(f"work_w_{i}_{s}", 0.0)) if ex_type != "Bodyweight" else 0.0
            r = int(session_state.get(f"work_r_{i}_{s}", 0)) if ex_type != "Timed" else 0
            d = int(session_state.get(f"work_d_{i}_{s}", 0)) if ex_type == "Timed" else 0
            if ex_type == "Bodyweight":
                volume = bodyweight_kg * r
            elif ex_type == "Timed":
                volume = bodyweight_kg * (d / 60)
            else:
                volume = w * r
            if r > 0 or d > 0:
                final_rows.append({
                    "log_ts": log_ts,
                    "plan_name": plan_name,
                    "exercise": ex_name,
                    "weight": w,
                    "sets": nsets,
                    "reps": r,
                    "rpe": rpe,
                    "volume": volume,
                    "duration_sec": d,
                    "set_number": s + 1
                })
    return final_rows

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
    
    # รองรับการรับค่า String เวลาโดยตรง
    time_str = f"{log_time}:00" if isinstance(log_time, str) and len(log_time) == 5 else str(log_time)
    
    return {
        "date":      str(log_date),
        "time":      time_str,
        "plan_name": plan_name,
        "exercises": ex_data,
        "_is_last_session": True
    }

@st.fragment
def render_plan_builder():
    db = get_db()
    st.markdown('<div style="font-family:Syne;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">Training Plan Builder</div>', unsafe_allow_html=True)
    st.info("Define recurring training templates. Plans are stored in Supabase.")
    
    # Detect edit mode
    is_edit_mode = "plan_editing_id" in st.session_state

    if is_edit_mode:
        st.info(f"Editing plan: **{st.session_state['plan_editing_name']}**")

    # Initialize session state for dynamic builder
    if "plan_builder_exercises" not in st.session_state:
        st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]

    # 1. Dynamic Plan Form
    with st.expander("Create New Plan" if not is_edit_mode else "Edit Plan", expanded=True):
        # We don't use st.form because we need dynamic row additions/deletions
        exercises = st.session_state["plan_builder_exercises"]
        
        for i in range(len(exercises)):
            c1, c2, c3 = st.columns([3, 1, 0.5])
            exercises[i]["name"] = c1.text_input(f"Exercise {i+1}", value=exercises[i]["name"], key=f"pb_name_{i}")
            exercises[i]["type"] = c2.selectbox("Type", ["Heavy", "Bodyweight", "Timed"], index=["Heavy", "Bodyweight", "Timed"].index(exercises[i]["type"]), key=f"pb_type_{i}")
            if c3.button("X", key=f"pb_del_{i}"):
                st.session_state["plan_builder_exercises"].pop(i)
                st.rerun()
        
        if st.button("Add Exercise"):
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
            save_label  = "Update Plan"
            save_key    = "pb_update"
        else:
            save_label  = "Save Plan"
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
            if col_cancel.button("Cancel", key="pb_cancel"):
                st.session_state["plan_builder_exercises"] = [{"name": "", "type": "Heavy"}]
                st.session_state.pop("plan_builder_name", None)
                st.session_state.pop("plan_editing_id",   None)
                st.session_state.pop("plan_editing_name", None)
                st.rerun()

    # 2. Existing Plans Management
    st.markdown('<div style="font-family:Syne;font-size:20px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Active Plans</div>', unsafe_allow_html=True)
    plans = fetch_plans_cached(db)
    if plans:
        for p in plans:
            ex_list = ", ".join([f"{ex['name']} ({ex['type']})" for ex in p['exercises']])
            st.markdown(f"""
            <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);
            border-radius:10px;padding:14px 16px;margin-bottom:6px;">
              <div style="font-family:Syne;font-size:15px;font-weight:700;
              color:#F0EFE8;">{p['name']}</div>
              <div style="font-size:11px;color:#888880;margin-top:4px;
              font-family:DM Sans;">{ex_list}</div>
            </div>""", unsafe_allow_html=True)
            
            c2, c3 = st.columns([1, 1])
            if c2.button("Edit", key=f"edit_{p['id']}"):
                # Load this plan into editor session state
                st.session_state["plan_editing_id"]       = p["id"]
                st.session_state["plan_editing_name"]     = p["name"]
                st.session_state["plan_builder_exercises"] = [
                    {"name": ex["name"], "type": ex["type"]}
                    for ex in p["exercises"]
                ]
                st.session_state.pop("plan_builder_name", None)
                st.rerun()
            if c3.button("Delete", key=f"del_{p['id']}"):
                if db.delete_plan(p['id']):
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("No plans found. Build your first one above!")

@st.fragment
def render_workout_form():
    db = get_db()
    st.markdown('<div style="font-family:Syne;font-size:20px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:16px;">Training Logger</div>', unsafe_allow_html=True)

    plans = fetch_plans_cached(db)
    if not plans:
        st.warning("No plans found. Use the 'Plan Builder' in the System sidebar to get started.")
        return

    plan_names = [p['name'] for p in plans]
    form_key = f"draft_workout_{st.session_state.get('user_id', 'default')}"

    # --- Plan Change Handling ---
    def on_plan_change():
        keys_to_clear = [
            k for k in st.session_state.keys()
            if k.startswith((
                "work_nsets_", "work_w_", "work_r_", "work_d_",
                "work_done_", "work_last_", "work_last_w_",
                "work_last_r_", "work_last_d_", "work_rpe_"
            ))
        ]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        db.clear_draft(form_key)

    if "work_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk).replace(microsecond=0)
        st.session_state.work_date = _now.date()
        st.session_state.work_time = _now.strftime("%H:%M") # String HH:MM
        
        saved_plan = draft.get("plan_name")
        st.session_state.work_plan_name = saved_plan if saved_plan in plan_names else plan_names[0]
        
        dyn_fields = draft.get("exercises", {})
        for k, v in dyn_fields.items():
            if v is not None:
                if "date" in k and isinstance(v, str):
                    try:
                        st.session_state[k] = datetime.strptime(v, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                elif "time" in k and isinstance(v, str):
                    st.session_state[k] = v[:5] # ตัดเอาแค่ String HH:MM
                elif "_w_" in k or "_rpe_" in k:
                    st.session_state[k] = float(v)
                elif "_r_" in k or "_d_" in k or "_nsets_" in k:
                    st.session_state[k] = int(v)
                else:
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
        _now = datetime.now(_bkk).replace(microsecond=0)
        if "work_date" not in st.session_state:
            st.session_state.work_date = _now.date()
        if "work_time" not in st.session_state:
            st.session_state.work_time = _now.strftime("%H:%M")
    if "work_plan_name" not in st.session_state:
        st.session_state.work_plan_name = plan_names[0]

    def save_workout_draft():
        if "work_plan_name" not in st.session_state:
            return
        now = time.time()
        last_save = st.session_state.get("_last_workout_draft_save", 0)
        if now - last_save < 3:
            return

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
        st.session_state["_last_workout_draft_save"] = now

    # ฟังก์ชัน Callback สำหรับปุ่ม Quick Set
    def set_work_time_to_now():
        _now = datetime.now(pytz.timezone("Asia/Bangkok"))
        st.session_state.work_date = _now.date()
        st.session_state.work_time = _now.strftime("%H:%M")
        save_workout_draft()

    # --- Row 1: จัดกลุ่ม Date, Time รูปแบบ Text, และปุ่ม Quick Set ---
    r1_c1, r1_c2, r1_c3 = st.columns([4, 4, 2])
    with r1_c1:
        l_date = st.date_input("Date", key="work_date", on_change=save_workout_draft)
    with r1_c2:
        l_time = st.text_input("Time (HH:MM)", key="work_time", on_change=save_workout_draft)
    with r1_c3:
        st.markdown('<div style="font-size:14px; color:#F0EFE8; margin-bottom:8px; font-family:DM Sans;">Quick Set Time</div>', unsafe_allow_html=True)
        st.button("Now", key="work_now_btn", use_container_width=True, on_click=set_work_time_to_now)

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
                # FORCE STRICT TYPING to prevent Streamlit React Error #185
                prev_w = float(hset.get("weight", 0.0))
                prev_r = int(hset.get("reps", 0))
                prev_d = int(hset.get("duration_sec", 0))
                
                # Store history for PR check
                st.session_state[f"work_last_w_{i}_{s}"] = prev_w
                st.session_state[f"work_last_r_{i}_{s}"] = prev_r
                st.session_state[f"work_last_d_{i}_{s}"] = prev_d
                
                # Populate inputs if not set
                if f"work_w_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_w_{i}_{s}"] = prev_w
                if f"work_r_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_r_{i}_{s}"] = prev_r
                if f"work_d_{i}_{s}" not in st.session_state:
                    st.session_state[f"work_d_{i}_{s}"] = prev_d
        
        # Ensure nsets has a default
        if f"work_nsets_{i}" not in st.session_state:
            st.session_state[f"work_nsets_{i}"] = 3

    # Fetch latest weight for volume calculation
    weight_data = fetch_weight_cached(db)
    if weight_data:
        df_w = pd.DataFrame(weight_data)
        df_w['log_ts'] = pd.to_datetime(df_w['log_ts'], format='ISO8601')
        bodyweight_kg = float(df_w.sort_values('log_ts').iloc[-1]['weight'])
    else:
        profile = fetch_profile_cached(db) or {}
        bodyweight_kg = float(profile.get('weight_kg') or 0.0)
    
    st.session_state["bodyweight_kg"] = bodyweight_kg

    for i, ex in enumerate(selected_plan['exercises']):
        ex_n = ex['name']
        ex_t = ex['type']

        type_badge_style = ""
        if ex_t == "Heavy":
            type_badge_style = "background:rgba(241,53,104,0.1);color:#F13568;border:0.5px solid rgba(241,53,104,0.2)"
        elif ex_t == "Bodyweight":
            type_badge_style = "background:rgba(53,200,241,0.1);color:#35C8F1;border:0.5px solid rgba(53,200,241,0.2)"
        elif ex_t == "Timed":
            type_badge_style = "background:rgba(239,159,39,0.1);color:#EF9F27;border:0.5px solid rgba(239,159,39,0.2)"

        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
        padding:12px 0 6px;border-top:0.5px solid rgba(255,255,255,0.07);">
          <span style="font-family:Syne;font-size:15px;font-weight:700;
          color:#F0EFE8;letter-spacing:-0.02em;">{ex_n}</span>
          <span style="font-size:10px;padding:3px 8px;border-radius:4px;
          font-weight:600;letter-spacing:0.06em;text-transform:uppercase;
          {type_badge_style}">{ex_t}</span>
        </div>""", unsafe_allow_html=True)
        
        # Last Session Summary Caption
        if ex_n in last_session:
            h_sets = last_session[ex_n]
            h_date = h_sets[0]["date"]
            h_details = []
            for h in h_sets:
                if ex_t == "Timed": h_details.append(f"{h['duration_sec']}s")
                elif ex_t == "Bodyweight": h_details.append(f"{h['reps']}r")
                else: h_details.append(f"{h['weight']}kg x {h['reps']}")
            st.markdown(f'<div style="font-size:11px;color:#444440;margin-bottom:8px;padding-left:4px;font-family:DM Sans;">Last {h_date}: {" | ".join(h_details)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size:11px;color:#444440;margin-bottom:8px;padding-left:4px;font-family:DM Sans;">No history for this exercise.</div>', unsafe_allow_html=True)

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
            arrow = "Up" if delta_pct >= 0 else "Down"
            color = "#C8F135" if delta_pct >= 0 else "#F13568"
            st.markdown(f"""
            <div style="font-size:11px;color:#888880;margin:4px 0 10px;
            font-family:DM Sans;">Volume <strong style="color:#F0EFE8;
            font-family:Syne;">{curr_vol:.0f} kg</strong>
            <span style="color:{color};">{arrow} {abs(delta_pct):.1f}%</span>
            vs last session</div>""", unsafe_allow_html=True)

        # Per-Set UI
        nsets = st.session_state[f"work_nsets_{i}"]
        
        for s in range(nsets):
            # If expanding sets beyond history, initialize missing keys with STRICT types
            if f"work_w_{i}_{s}" not in st.session_state:
                st.session_state[f"work_w_{i}_{s}"] = 0.0 # STRICT FLOAT for step=0.5
            if f"work_r_{i}_{s}" not in st.session_state:
                st.session_state[f"work_r_{i}_{s}"] = 0   # STRICT INT for step=1
            if f"work_d_{i}_{s}" not in st.session_state:
                st.session_state[f"work_d_{i}_{s}"] = 0   # STRICT INT for step=1

            # Checkbox state for "Done"
            is_done = st.session_state.get(f"work_done_{i}_{s}", False)
            # Set label with inline done indicator — no dynamic CSS injection
            set_label = f'<span style="font-size:13px;font-weight:700;color:{"#C8F135" if is_done else "#888880"};">{"✓" if is_done else s+1}</span>'

            row_container = st.container()
            with row_container:
                if ex_t == "Heavy":
                    cols = st.columns([0.3, 1, 1, 0.4, 0.4, 0.3])
                    cols[0].markdown(set_label, unsafe_allow_html=True)
                    w = cols[1].number_input("W", label_visibility="collapsed", min_value=0.0, step=0.5, key=f"work_w_{i}_{s}", on_change=save_workout_draft)
                    r = cols[2].number_input("R", label_visibility="collapsed", min_value=0, step=1, key=f"work_r_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_w = st.session_state.get(f"work_last_w_{i}_{s}", 0.0)
                    last_r = st.session_state.get(f"work_last_r_{i}_{s}", 0)
                    if (w > last_w or r > last_r) and (last_w > 0 or last_r > 0):
                        cols[3].markdown('<span style="font-size:10px;background:rgba(200,241,53,0.12);color:#C8F135;padding:2px 6px;border-radius:4px;font-weight:700;font-family:DM Sans;">PR</span>', unsafe_allow_html=True)
                    
                    cols[4].checkbox("Done", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[5].button("X", key=f"rm_set_{i}_{s}"):
                            # shift values down
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_w_{i}_{ss}"] = st.session_state.get(f"work_w_{i}_{ss+1}", 0.0)
                                st.session_state[f"work_r_{i}_{ss}"] = st.session_state.get(f"work_r_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()

                elif ex_t == "Timed":
                    cols = st.columns([0.3, 2, 0.4, 0.4, 0.3])
                    cols[0].markdown(set_label, unsafe_allow_html=True)
                    d = cols[1].number_input("D", label_visibility="collapsed", min_value=0, step=5, key=f"work_d_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_d = st.session_state.get(f"work_last_d_{i}_{s}", 0)
                    if d > last_d and last_d > 0:
                        cols[2].markdown('<span style="font-size:10px;background:rgba(200,241,53,0.12);color:#C8F135;padding:2px 6px;border-radius:4px;font-weight:700;font-family:DM Sans;">PR</span>', unsafe_allow_html=True)

                    cols[3].checkbox("Done", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[4].button("X", key=f"rm_set_{i}_{s}"):
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_d_{i}_{ss}"] = st.session_state.get(f"work_d_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()
                else: # Bodyweight
                    cols = st.columns([0.3, 2, 0.4, 0.4, 0.3])
                    cols[0].markdown(set_label, unsafe_allow_html=True)
                    r = cols[1].number_input("R", label_visibility="collapsed", min_value=0, step=1, key=f"work_r_{i}_{s}", on_change=save_workout_draft)
                    
                    # PR Check
                    last_r = st.session_state.get(f"work_last_r_{i}_{s}", 0)
                    if r > last_r and last_r > 0:
                        cols[2].markdown('<span style="font-size:10px;background:rgba(200,241,53,0.12);color:#C8F135;padding:2px 6px;border-radius:4px;font-weight:700;font-family:DM Sans;">PR</span>', unsafe_allow_html=True)

                    cols[3].checkbox("Done", label_visibility="collapsed", key=f"work_done_{i}_{s}")
                    if nsets > 1:
                        if cols[4].button("X", key=f"rm_set_{i}_{s}"):
                            for ss in range(s, nsets - 1):
                                st.session_state[f"work_r_{i}_{ss}"] = st.session_state.get(f"work_r_{i}_{ss+1}", 0)
                                st.session_state[f"work_done_{i}_{ss}"] = st.session_state.get(f"work_done_{i}_{ss+1}", False)
                            st.session_state[f"work_nsets_{i}"] -= 1
                            st.rerun()
            
        if st.button(f"Add Set", key=f"add_set_{i}"):
            st.session_state[f"work_nsets_{i}"] += 1
            st.rerun()

        # --- Restore RPE (as Number Input for better Mobile UX) ---
        if f"work_rpe_{i}" not in st.session_state:
            st.session_state[f"work_rpe_{i}"] = 7.0

        st.number_input(
            "RPE (Rate of Perceived Exertion)", 
            min_value=1.0, 
            max_value=10.0, 
            value=float(st.session_state.get(f"work_rpe_{i}", 7.0)),
            step=0.5, 
            key=f"work_rpe_{i}", 
            on_change=save_workout_draft
        )
        st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    st.markdown("""<style>
    div:has(> button[key="save_workout_btn"]) > button {
      background: #C8F135 !important; color: #0D0D0F !important;
      font-family: Syne !important; font-weight: 800 !important;
      border: none !important; width: 100%;
    }
    </style>""", unsafe_allow_html=True)
    submitted = st.button("Save Training Session", key="save_workout_btn")

    # Step 1: on submit, check duplicate and set show_confirm flag
    if submitted:
        date_str = str(l_date)
        
        # ตรวจสอบรูปแบบเวลาก่อนเซฟ
        if len(l_time) != 5 or ":" not in l_time:
            st.error("Please enter time in HH:MM format (e.g., 08:30)")
            return
            
        dup_count = db.check_duplicate_workout(date_str)
        if dup_count > 0:
            st.session_state.workout_show_confirm = True
            st.session_state.workout_pending_date = date_str
        else:
            # No duplicate — save directly
            log_ts = get_timestamp(l_date, l_time)
            final_rows = _build_workout_rows(selected_plan, st.session_state, log_ts, selected_plan_name, bodyweight_kg)

            if final_rows:
                if db.save_workout(final_rows):
                    st.success(f"Session saved: {len(final_rows)} rows logged.")
                    db.clear_draft(form_key)
                    # Save last session snapshot (separate from normal draft)
                    last_key = f"last_workout_{st.session_state.get('user_id', 'default')}"
                    db.save_draft(last_key, _build_workout_snapshot(
                        selected_plan_name, selected_plan, l_date, l_time, st.session_state
                    ))
                    # Cleanup session state
                    cleanup_prefixes = (
                        "work_nsets_", "work_w_", "work_r_", "work_d_",
                        "work_done_", "work_last_", "work_last_w_",
                        "work_last_r_", "work_last_d_", "work_rpe_"
                    )
                    for k in list(st.session_state.keys()):
                        if k.startswith(cleanup_prefixes):
                            st.session_state.pop(k, None)
                    st.session_state.pop("work_draft_loaded", None)
                    st.rerun()
            else:
                st.warning("No entries with reps/duration > 0. Nothing saved.")

    # Step 2: show confirmation UI OUTSIDE if submitted — persists across reruns
    if st.session_state.get("workout_show_confirm"):
        date_str = st.session_state.get("workout_pending_date", "")
        st.markdown(f"""
        <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);
        border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:DM Sans;">
        Duplicate entries found on {date_str}.</div>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        if col1.button("Save Anyway", key="workout_save_anyway"):
            st.session_state.workout_confirm_overwrite = True
            st.session_state.pop("workout_show_confirm", None)
            st.rerun()
        
        st.markdown("""<style>div:has(> button[key="workout_overwrite"]) > button { background:#C8F135 !important; color:#0D0D0F !important; }</style>""", unsafe_allow_html=True)
        if col2.button("Overwrite", key="workout_overwrite"):
            st.session_state.workout_confirm_overwrite = True
            st.session_state.workout_do_overwrite = True
            st.session_state.pop("workout_show_confirm", None)
            st.rerun()
            
        st.markdown("""<style>div:has(> button[key="workout_cancel"]) > button { color:#F13568 !important; border-color:rgba(241,53,104,0.3) !important; }</style>""", unsafe_allow_html=True)
        if col3.button("Cancel", key="workout_cancel"):
            st.session_state.pop("workout_show_confirm", None)
            st.session_state.pop("workout_pending_date", None)
            st.rerun()

def process_pending_workout(db, session_state):
    """Constructs and saves workout data from session state."""
    plans = db.fetch_plans()
    curr_plan = session_state.get("work_plan_name", "")
    selected_plan_obj = next((p for p in plans if p["name"] == curr_plan), None)
    work_date = session_state.get("work_date")
    work_time = session_state.get("work_time")

    if selected_plan_obj and work_date and work_time:
        # ใช้เป็น String ทันที ถอด strftime ออกเพื่อกัน Error
        log_ts = f"{work_date} {work_time}:00"
        
        bw = session_state.get("bodyweight_kg")
        if not bw or float(bw) == 0.0:
            profile = fetch_profile_cached(db)
            bodyweight_kg = float(profile.get("weight_kg", 0.0)) if profile else 0.0
        else:
            bodyweight_kg = float(bw)

        final_rows = _build_workout_rows(selected_plan_obj, session_state, log_ts, curr_plan, bodyweight_kg)

        if final_rows:
            form_key = f"draft_workout_{session_state.get('user_id', 'default')}"
            if db.save_workout(final_rows):
                session_state["_pending_success"] = f"Session saved: {len(final_rows)} rows logged."
                db.clear_draft(form_key)
                # Save last session snapshot
                last_key = f"last_workout_{session_state.get('user_id', 'default')}"
                db.save_draft(last_key, _build_workout_snapshot(
                    curr_plan, selected_plan_obj, work_date, work_time, session_state
                ))
                # Cleanup session state
                cleanup_prefixes = (
                    "work_nsets_", "work_w_", "work_r_", "work_d_",
                    "work_done_", "work_last_", "work_last_w_",
                    "work_last_r_", "work_last_d_", "work_rpe_"
                )
                for k in list(session_state.keys()):
                    if k.startswith(cleanup_prefixes):
                        session_state.pop(k, None)
            session_state.pop("work_draft_loaded", None)
        else:
            session_state["_pending_warning"] = "No entries with reps/duration > 0. Nothing saved."

def render_today_training_summary():
    db = get_db()
    _bkk = pytz.timezone("Asia/Bangkok")
    today_str = str(datetime.now(_bkk).date())
    
    summary = fetch_today_summary_cached(db, today_str)
    rows = summary["work"]

    if not rows:
        st.markdown('<div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px 20px;margin-bottom:12px;"><div style="font-family:Syne;font-size:12px;font-weight:700;color:#444440;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:12px;">Today Training</div><div style="font-size:13px;color:#444440;font-family:DM Sans;">No training logged today.</div></div>', unsafe_allow_html=True)
        return

    df = pd.DataFrame(rows)
    df['rpe']    = pd.to_numeric(df['rpe'],    errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    total_volume = df['volume'].sum()
    avg_rpe      = df['rpe'].mean()

    # Build exercise breakdown rows as pure HTML
    sets_col = df.groupby("exercise")["exercise"].count().rename("Sets")
    breakdown = df.groupby("exercise").agg(
        Volume=("volume", "sum"),
        RPE=("rpe", "mean"),
    ).join(sets_col).reset_index()

    rows_html = ""
    for _, row in breakdown.iterrows():
        rows_html += f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;padding:8px 0;border-top:0.5px solid rgba(255,255,255,0.05);align-items:center;"><div style="font-size:13px;color:#F0EFE8;font-family:DM Sans;">{row["exercise"]}</div><div style="font-size:12px;color:#888880;font-family:DM Sans;text-align:right;">{int(row["Sets"])} sets</div><div style="font-size:12px;color:#C8F135;font-family:DM Sans;text-align:right;">{row["Volume"]:,.0f} kg</div><div style="font-size:12px;color:#888880;font-family:DM Sans;text-align:right;">RPE {row["RPE"]:.1f}</div></div>'

    st.markdown(f'<div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px 20px;margin-bottom:12px;"><div style="font-family:Syne;font-size:12px;font-weight:700;color:#444440;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px;">Today Training</div><div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px;padding-bottom:14px;border-bottom:0.5px solid rgba(255,255,255,0.07);"><div><div style="font-size:10px;color:#888880;font-family:DM Sans;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">Total Volume</div><div style="font-family:Syne;font-size:28px;font-weight:800;color:#C8F135;letter-spacing:-0.04em;line-height:1;">{total_volume:,.0f}<span style="font-size:13px;color:#888880;font-weight:400;">kg</span></div></div><div style="text-align:right;"><div style="font-size:10px;color:#888880;font-family:DM Sans;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">Avg RPE</div><div style="font-family:Syne;font-size:22px;font-weight:700;color:#F0EFE8;">{avg_rpe:.1f}</div></div></div><div style="font-size:10px;color:#555552;font-family:DM Sans;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;"><div>Exercise</div><div style="text-align:right;">Sets</div><div style="text-align:right;">Volume</div><div style="text-align:right;">RPE</div></div>{rows_html}</div>', unsafe_allow_html=True)

def render_exercise_history_card():
    import pandas as pd
    import streamlit as st
    
    db = get_db()
    
    st.markdown('<div style="font-family:Syne;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">Exercise History</div>', unsafe_allow_html=True)
    
    # 1. Fetch active workout templates/plans from database
    active_plans = db.fetch_plans()
        
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
        unique_exercises = sorted(df_all['exercise'].unique().tolist())
        active_plans = [{"name": "Global Active Routines", "exercises": [{"name": ex, "type": "Heavy"} for ex in unique_exercises]}]

    # Plan Selection UI
    plan_names = [p.get('name', 'Unnamed Plan') for p in active_plans]
    selected_plan_name = st.selectbox("Select Active Plan to View History", options=plan_names)
    
    # Filter to selected plan
    selected_plan = next((p for p in active_plans if p.get('name') == selected_plan_name), None)
    
    if not selected_plan:
        st.error("Selected plan not found.")
        return

    st.markdown(f'<div style="font-family:Syne;font-size:20px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Training Plan: {selected_plan_name}</div>', unsafe_allow_html=True)
    
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
        
        # Sort chronologically descending to target newest workouts first
        df_ex = df_ex.sort_values(by=['date', 'log_ts'], ascending=[False, True])
        
        # Isolate only the single most recent distinct session date
        recent_dates = df_ex['date'].unique()[:1]
        
        for target_date in recent_dates:
            date_str = target_date.strftime('%d %b %Y')
            df_session = df_ex[df_ex['date'] == target_date]
            
            sets_html = ""
            for idx, row in enumerate(df_session.itertuples(), start=1):
                detail = ""
                if str(ex_type).lower() == 'timed':
                    sec_val = int(getattr(row, 'duration_sec', 0))
                    detail = f"{sec_val}s"
                elif str(ex_type).lower() == 'bodyweight':
                    rep_val = int(getattr(row, 'reps', 0))
                    weight_val = float(getattr(row, 'weight', 0))
                    if weight_val > 0:
                        detail = f"+{weight_val:.1f} kg x {rep_val}"
                    else:
                        detail = f"{rep_val} reps"
                else: # Default/Heavy Weight Training
                    weight_val = float(getattr(row, 'weight', 0))
                    rep_val = int(getattr(row, 'reps', 0))
                    detail = f"{weight_val:.1f} kg x {rep_val}"
                
                sets_html += f'<div style="font-size:12px;color:#F0EFE8;padding:3px 0;">Set {idx}: {detail}</div>'

            type_badge_style = ""
            if ex_type == "Heavy":
                type_badge_style = "background:rgba(241,53,104,0.1);color:#F13568;border:0.5px solid rgba(241,53,104,0.2)"
            elif ex_type == "Bodyweight":
                type_badge_style = "background:rgba(53,200,241,0.1);color:#35C8F1;border:0.5px solid rgba(53,200,241,0.2)"
            elif ex_type == "Timed":
                type_badge_style = "background:rgba(239,159,39,0.1);color:#EF9F27;border:0.5px solid rgba(239,159,39,0.2)"

            st.markdown(f"""
            <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);
            border-radius:10px;padding:12px 14px;margin-bottom:6px;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <span style="font-family:Syne;font-size:14px;font-weight:700;color:#F0EFE8;">{ex_name}</span>
                <span style="font-size:10px;padding:3px 8px;border-radius:4px;{type_badge_style}">{ex_type}</span>
              </div>
              <div style="font-size:11px;color:#888880;margin-bottom:6px;">Latest: {date_str}</div>
              {sets_html}
            </div>""", unsafe_allow_html=True)
        
    if has_history_output:
        st.divider()