import streamlit as st
from modules.forms import render_workout_form, render_running_form, render_biohack_form, render_plan_builder, render_weight_form, render_profile_form
from modules.analytics import render_analytics, render_overview, render_nutrition_analysis, render_data_manager, render_export_section, render_wellness
from modules.database import get_db
from datetime import date, datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Training Track",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    """Returns True if the user is authenticated via token or password."""
    if st.session_state.get("password_correct"):
        return True

    # Auto-login via URL token
    token = st.query_params.get("token", "")
    if token and token == st.secrets.get("app_token", ""):
        st.session_state["password_correct"] = True
        return True

    # Fallback: manual password login
    st.title("🔐 Secure Access")
    with st.form("login_form"):
        pwd = st.text_input("Access Key", type="password")
        submitted = st.form_submit_button("Unlock Dashboard")
    if submitted:
        if pwd == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Invalid Key.")
    return False

def _handle_pending_confirmations(db):
    """
    Runs on every rerun before tabs are rendered.
    Handles all post-confirmation saves for all 4 forms.
    """

    # ── WORKOUT ──────────────────────────────────────────
    if st.session_state.get("workout_confirm_overwrite"):
        date_str = str(st.session_state.get("work_date", ""))
        if st.session_state.pop("workout_do_overwrite", False):
            db.delete_workouts_by_date(date_str)
        st.session_state.pop("workout_confirm_overwrite", None)

        plans = db.fetch_plans()
        curr_plan = st.session_state.get("work_plan_name", "")
        selected_plan_obj = next((p for p in plans if p["name"] == curr_plan), None)
        work_date = st.session_state.get("work_date")
        work_time = st.session_state.get("work_time")

        if selected_plan_obj and work_date and work_time:
            log_ts = f"{work_date} {work_time.strftime('%H:%M:%S')}"
            bodyweight_kg = float(st.session_state.get("bodyweight_kg", 0.0))
            final_rows = []
            for i, ex in enumerate(selected_plan_obj["exercises"]):
                ex_t = ex["type"]
                s = int(st.session_state.get(f"work_s_{i}", 0))
                r = int(st.session_state.get(f"work_r_{i}", 0))
                d = int(st.session_state.get(f"work_d_{i}", 0))
                w = float(st.session_state.get(f"work_w_{i}", 0.0)) if ex_t == "Heavy" else 0.0
                rpe = float(st.session_state.get(f"work_rpe_{i}", 7.0))
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
                form_key = f"draft_workout_{st.session_state.get('user_id', 'default')}"
                if db.save_workout(final_rows):
                    st.session_state["_pending_success"] = f"✅ Session saved: {len(final_rows)} exercises logged."
                    db.clear_draft(form_key)
                    st.session_state.pop("work_draft_loaded", None)
            else:
                st.session_state["_pending_warning"] = "No exercises with sets > 0. Nothing saved."

    # ── RUNNING ──────────────────────────────────────────
    if st.session_state.get("run_confirm_overwrite"):
        date_str = str(st.session_state.get("run_date", ""))
        if st.session_state.pop("run_do_overwrite", False):
            db.delete_runs_by_date(date_str)
        st.session_state.pop("run_confirm_overwrite", None)

        run_date = st.session_state.get("run_date")
        run_time = st.session_state.get("run_time")
        _dist = float(st.session_state.get("run_dist", 0.0))
        _dur = str(st.session_state.get("run_dur", "00:00"))
        _hr = int(st.session_state.get("run_hr", 0))
        _hrr = int(st.session_state.get("run_hrr", 0))
        _cat = str(st.session_state.get("run_cat", "Easy"))

        if run_date and run_time:
            log_ts = f"{run_date} {run_time.strftime('%H:%M:%S')}"
            try:
                p = _dur.split(":")
                mins, secs = (int(p[0]), int(p[1])) if len(p) == 2 else (0, 0)
                tot_s = mins * 60 + secs
                pace_s = "0:00"
                if _dist > 0:
                    p_s = tot_s / _dist
                    pace_s = f"{int(p_s // 60)}:{int(p_s % 60):02d}"
                run_data = {
                    "log_ts": log_ts,
                    "distance": _dist,
                    "duration": _dur,
                    "pace": pace_s,
                    "hr": _hr,
                    "hrr": _hrr,
                    "category": _cat
                }
                form_key = f"draft_run_{st.session_state.get('user_id', 'default')}"
                if db.save_run(run_data):
                    st.session_state["_pending_success"] = "✅ Movement session logged."
                    db.clear_draft(form_key)
                    st.session_state.pop("run_draft_loaded", None)
            except Exception:
                st.session_state["_pending_warning"] = "Use MM:SS format for duration."

   # ── NUTRITION ─────────────────────────────────────────
    if st.session_state.get("nut_confirm_overwrite"):
        from modules.forms import SUPPLEMENT_MAP
        date_str = str(st.session_state.get("nut_date", ""))
        if st.session_state.pop("nut_do_overwrite", False):
            db.delete_nutrition_by_date(date_str)
        st.session_state.pop("nut_confirm_overwrite", None)

        nut_date = st.session_state.get("nut_date")
        nut_time = st.session_state.get("nut_time")

        if nut_date and nut_time:
            log_ts = f"{nut_date} {nut_time.strftime('%H:%M:%S')}"
            nut_data = {
                "log_ts": log_ts,
                "food_name": str(st.session_state.get("nut_food_name", "")),
                "calories": int(st.session_state.get("nut_cal", 0)),
                "protein_g": int(st.session_state.get("nut_pg", 0)),
                "carbs_g": int(st.session_state.get("nut_cg", 0)),
                "fat_g": int(st.session_state.get("nut_fg", 0)),
                "meal_score": int(st.session_state.get("nut_meal_score", 5)),
            }
            for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
                nut_data[db_col] = bool(st.session_state.get(sess_key, False))

            form_key = f"draft_nutrition_{st.session_state.get('user_id', 'default')}"
            if db.save_nutrition(nut_data):
                st.session_state["_pending_success"] = "✅ Nutrition data saved."
                db.clear_draft(form_key)
                st.session_state.pop("nut_draft_loaded", None)

    # ── WEIGHT ────────────────────────────────────────────
    if st.session_state.get("weight_confirm_overwrite"):
        date_str = str(st.session_state.get("weight_date", ""))
        if st.session_state.pop("weight_do_overwrite", False):
            db.delete_weight_by_date(date_str)
        st.session_state.pop("weight_confirm_overwrite", None)

        weight_date = st.session_state.get("weight_date")
        weight_time = st.session_state.get("weight_time")

        if weight_date and weight_time:
            log_ts = f"{weight_date} {weight_time.strftime('%H:%M:%S')}"
            weight_data = {
                "log_ts": log_ts,
                "weight": float(st.session_state.get("weight_kg", 0.0)),
                "notes": str(st.session_state.get("weight_notes", ""))
            }
            form_key = f"draft_weight_{st.session_state.get('user_id', 'default')}"
            if db.save_weight(weight_data):
                st.session_state["_pending_success"] = "✅ Weight logged."
                db.clear_draft(form_key)
                st.session_state.pop("weight_draft_loaded", None)

def main():
    """Main application entry point."""
    if not check_password():
        st.stop()

    db = get_db()

    # ── handle confirmations BEFORE tabs render ──
    _handle_pending_confirmations(db)

    # ── show pending success/warning messages ──
    if "_pending_success" in st.session_state:
        st.success(st.session_state.pop("_pending_success"))
    if "_pending_warning" in st.session_state:
        st.warning(st.session_state.pop("_pending_warning"))

    # --- SIDEBAR STATUS ---
    with st.sidebar:
        st.title("⚙️ System Management")
        if db.is_connected():
            st.success("Database Online")
        else:
            st.error("Database Offline")
        
        if st.button("🔄 Refresh Data"):
            for key in [
                "work_draft_loaded", "run_draft_loaded", "nut_draft_loaded", "weight_draft_loaded",
                "workout_show_confirm", "run_show_confirm", "nut_show_confirm", "weight_show_confirm",
                "workout_pending_date", "run_pending_date", "nut_pending_date", "weight_pending_date",
                "_pending_success", "_pending_warning"
            ]:
                st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        if db.is_connected():
            show_plan_builder = st.toggle("🛠️ Open Plan Builder", value=False)
            show_profile = st.toggle("👤 Edit Profile & Goals", value=False)
        else:
            show_plan_builder = False
            show_profile = False

    # --- APP HEADER ---
    st.title("🎯 Training & Health Track")
    st.markdown("---")

    if show_profile:
        render_profile_form()
        st.stop()

    if show_plan_builder:
        render_plan_builder()
        st.stop()

    # --- NAVIGATION ---
    tabs = st.tabs(["🏠 Overview", "🏋️ Training", "🏃 Movement", "📉 Analytics", "🍱 Nutrition", "🔋 Wellness", "🗂️ Data"])

    with tabs[0]:
        render_overview()

    with tabs[1]:
        if db.is_connected():
            render_workout_form()
        else:
            st.warning("Database offline. Cannot load training plans.")

    with tabs[2]:
        render_running_form()

    with tabs[3]:
        render_analytics()

    with tabs[4]:
        render_nutrition_analysis()
        st.divider()
        render_biohack_form()

    with tabs[5]:
        render_wellness()

    with tabs[6]:
        render_data_manager()

if __name__ == "__main__":
    main()
