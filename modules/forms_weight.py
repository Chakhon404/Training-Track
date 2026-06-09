import streamlit as st
import time
import pytz
from datetime import datetime
from modules.database import get_db, fetch_profile_cached, fetch_weight_cached
from modules.constants import SUPPLEMENT_MAP

def get_timestamp(log_date, log_time):
    return f"{log_date} {log_time.strftime('%H:%M:%S')}"

@st.fragment
def render_weight_form():
    db = get_db()
    st.markdown('<div style="font-family:Syne;font-size:20px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:16px;">Weight Log</div>', unsafe_allow_html=True)
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

        data = {
            "date": str(st.session_state.weight_date),
            "time": st.session_state.weight_time.strftime("%H:%M:%S"),
            "weight_kg": st.session_state.weight_kg,
            "weight_bf": st.session_state.weight_bf,
            "weight_notes": st.session_state.weight_notes
        }
        db.save_draft(form_key, data)
        st.session_state["_last_weight_draft_save"] = now

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="weight_date", on_change=save_weight_draft)
    with col_t:
        l_time = st.time_input("Time", key="weight_time", on_change=save_weight_draft)

    weight_val = st.number_input("Weight (kg)", min_value=0.0, step=0.1, key="weight_kg", on_change=save_weight_draft)
    weight_bf_val = st.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, key="weight_bf", on_change=save_weight_draft)
    notes = st.text_input("Notes (optional)", key="weight_notes", on_change=save_weight_draft)

    submitted = st.button("Log Weight")

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
                st.success("Weight logged.")
                db.clear_draft(form_key)
                st.session_state.pop("weight_draft_loaded", None)
                st.rerun()

    # Step 2: show confirmation UI OUTSIDE if submitted
    if st.session_state.get("weight_show_confirm"):
        date_str = st.session_state.get("weight_pending_date", "")
        st.markdown(f"""
        <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);
        border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:DM Sans;">
        Duplicate entries found on {date_str}.</div>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        if col1.button("Save Anyway", key="weight_save_anyway"):
            st.session_state.weight_confirm_overwrite = True
            st.session_state.pop("weight_show_confirm", None)
            st.rerun()
            
        st.markdown("""<style>div:has(> button[key="weight_overwrite"]) > button { background:#C8F135 !important; color:#0D0D0F !important; }</style>""", unsafe_allow_html=True)
        if col2.button("Overwrite", key="weight_overwrite"):
            st.session_state.weight_confirm_overwrite = True
            st.session_state.weight_do_overwrite = True
            st.session_state.pop("weight_show_confirm", None)
            st.rerun()
            
        st.markdown("""<style>div:has(> button[key="weight_cancel"]) > button { color:#F13568 !important; border-color:rgba(241,53,104,0.3) !important; }</style>""", unsafe_allow_html=True)
        if col3.button("Cancel", key="weight_cancel"):
            st.session_state.pop("weight_show_confirm", None)
            st.session_state.pop("weight_pending_date", None)
            st.rerun()

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
            session_state["_pending_success"] = "Weight logged."
            db.clear_draft(form_key)
            session_state.pop("weight_draft_loaded", None)

def render_profile_form():
    db = get_db()
    st.markdown('<div style="font-family:Syne;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">User Profile & Goals</div>', unsafe_allow_html=True)
    st.caption("Your physical stats and nutrition goals. Used across all tabs.")

    profile = fetch_profile_cached(db) or {}

    with st.form("profile_form"):
        st.markdown('<div style="font-family:DM Sans;font-size:10px;color:#444440;letter-spacing:0.2em;text-transform:uppercase;margin:16px 0 10px;">Physical Stats</div>', unsafe_allow_html=True)
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
            
            mc1.markdown(f"""
            <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px;">
              <div style="font-family:DM Sans;font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">BMI</div>
              <div style="font-family:Syne;font-size:22px;font-weight:700;color:#F0EFE8;">{bmi:.1f}</div>
            </div>""", unsafe_allow_html=True)
            
            if lean_mass:
                mc2.markdown(f"""
                <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px;">
                  <div style="font-family:DM Sans;font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">Lean Mass</div>
                  <div style="font-family:Syne;font-size:22px;font-weight:700;color:#F0EFE8;">{lean_mass:.1f} kg</div>
                </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown('<div style="font-family:DM Sans;font-size:10px;color:#444440;letter-spacing:0.2em;text-transform:uppercase;margin:16px 0 10px;">Goals</div>', unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        goal_weight = g1.number_input(
            "Target Weight (kg)", min_value=0.0, step=0.1,
            value=float(profile.get("goal_weight_kg") or 0.0)
        )

        st.markdown('<div style="font-family:DM Sans;font-size:10px;color:#444440;letter-spacing:0.2em;text-transform:uppercase;margin:12px 0 8px;">Daily Nutrition Goals</div>', unsafe_allow_html=True)
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
        st.markdown('<div style="font-family:DM Sans;font-size:10px;color:#444440;letter-spacing:0.2em;text-transform:uppercase;margin:16px 0 10px;">Default Supplements</div>', unsafe_allow_html=True)
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

        if st.form_submit_button("Save Profile"):
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
                st.success("Profile saved.")
                st.rerun()