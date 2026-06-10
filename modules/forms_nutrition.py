import streamlit as st
import json
import time
import pytz
from datetime import datetime
from modules.database import get_db, fetch_profile_cached, fetch_nutrition_cached, fetch_today_summary_cached
from modules.constants import SUPPLEMENT_MAP

def get_timestamp(log_date, log_time):
    return f"{log_date} {log_time.strftime('%H:%M:%S')}"

@st.fragment
def render_biohack_form():
    db = get_db()
    st.markdown('<div style="font-family:Syne;font-size:20px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:16px;">Nutrition Log</div>', unsafe_allow_html=True)
    form_key = f"draft_nutrition_{st.session_state.get('user_id', 'default')}"

    # Determine if today already has a saved nutrition entry
    _bkk = pytz.timezone("Asia/Bangkok")
    today_str = str(datetime.now(_bkk).date())
    today_entries = db.fetch_nutrition_by_date(today_str)
    sups_locked = len(today_entries) > 0

    # ── JSON Quick Fill ──────────────────────────────────
    with st.expander("Quick Fill", expanded=False):
        st.markdown('<div style="font-size:11px;color:#35C8F1;margin-bottom:8px;">Paste JSON from Gemini Gem to auto-fill</div>', unsafe_allow_html=True)
        
        json_input = st.text_area(
            "Paste JSON here",
            height=200,
            placeholder='{\n  "log_date": "2026-05-11",\n  "log_time": "12:30",\n  "supplements": {\n    "creatine": true,\n    "protein_powder": false,\n    "multi_vitamin": true,\n    "omega_3": true\n  },\n  "energy_macros": {\n    "calories": 2100,\n    "protein_g": 145,\n    "carbs_g": 210,\n    "fat_g": 65\n  },\n  "meal_score": 8\n}',
            key="nut_json_input"
        )

        if st.button("Fill Form from JSON", key="nut_json_fill"):
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

                    st.success("Form filled from JSON.")

                except json.JSONDecodeError:
                    st.error("Invalid JSON format. Please check and try again.")
                except Exception as e:
                    st.error(f"Error parsing JSON: {e}")
            else:
                st.warning("Please paste a JSON first.")

    if "nut_draft_loaded" not in st.session_state:
        draft = db.load_draft(form_key) or {}
        _bkk = pytz.timezone("Asia/Bangkok")
        _now = datetime.now(_bkk).replace(microsecond=0)
        
        # Load date/time from draft if present, else default to now
        if "date" in draft and isinstance(draft["date"], str):
            try:
                st.session_state.nut_date = datetime.strptime(draft["date"], "%Y-%m-%d").date()
            except ValueError:
                st.session_state.nut_date = _now.date()
        else:
            st.session_state.nut_date = _now.date()

        if "time" in draft and isinstance(draft["time"], str):
            try:
                st.session_state.nut_time = datetime.strptime(draft["time"], "%H:%M:%S").time()
            except ValueError:
                st.session_state.nut_time = _now.time().replace(tzinfo=None)
        else:
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
        _now = datetime.now(_bkk).replace(microsecond=0)
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
        st.session_state["_last_nut_draft_save"] = now

    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", key="nut_date", on_change=save_nut_draft)
    with col_t:
        l_time = st.time_input("Time", key="nut_time", on_change=save_nut_draft)

    food_name = st.text_input(
        "Food Name / Description",
        key="nut_food_name",
        placeholder="e.g. โอ๊ตเต็มใบ 30g + โยเกิร์ต 1 ถ้วย",
        on_change=save_nut_draft
    )

    st.markdown('<div style="font-family:Syne;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Supplements</div>', unsafe_allow_html=True)

    # Load profile supplements
    profile = fetch_profile_cached(db) or {}
    default_sups = profile.get("default_supplements") or []

    # Filter to only show supplements in profile
    sup_keys = [k for k in SUPPLEMENT_MAP.keys() if k in default_sups]

    if not sup_keys:
        st.info("No supplements configured. Go to System -> Edit Profile & Goals to add your supplements.")
    else:
        if sups_locked:
            st.caption("Supplements already logged today - adjust if needed.")

        st.markdown('<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px;">', unsafe_allow_html=True)
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
                    on_change=save_nut_draft
                )
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown('<div style="font-family:DM Sans;font-size:10px;color:#444440;letter-spacing:0.2em;text-transform:uppercase;margin:12px 0 8px;">Energy & Macros</div>', unsafe_allow_html=True)
    n1, n2, n3, n4 = st.columns(4)
    cal = n1.number_input("Calories", min_value=0, step=50, key="nut_cal", on_change=save_nut_draft)
    p_g = n2.number_input("Protein (g)", min_value=0, step=1, key="nut_pg", on_change=save_nut_draft)
    c_g = n3.number_input("Carbs (g)", min_value=0, step=1, key="nut_cg", on_change=save_nut_draft)
    f_g = n4.number_input("Fat (g)", min_value=0, step=1, key="nut_fg", on_change=save_nut_draft)

    st.divider()
    st.markdown('<div style="font-size:11px;color:#888880;margin-top:8px;font-family:DM Sans;letter-spacing:0.04em;text-transform:uppercase;">Meal Score</div>', unsafe_allow_html=True)
    meal_score = st.slider(
        "Rate today's nutrition (1 = terrible, 10 = perfect)",
        min_value=1, max_value=10,
        step=1,
        key="nut_meal_score",
        on_change=save_nut_draft,
        label_visibility="collapsed"
    )

    submitted = st.button("Save Nutrition")

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
            st.success("Nutrition data saved.")
            db.clear_draft(form_key)
            st.session_state.pop("nut_draft_loaded", None)
            st.rerun()

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
            session_state["_pending_success"] = "Nutrition data saved."
            db.clear_draft(form_key)
            session_state.pop("nut_draft_loaded", None)