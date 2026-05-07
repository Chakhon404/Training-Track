# Supabase Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Training-Track application from Google Sheets to Supabase for permanent, reliable cloud storage, tracking workouts, running, nutrition, training plans, and weight.

**Architecture:** We will replace `gsheet_api.py` with `database.py` containing a `TrainingDB` class powered by `supabase-py`. The UI modules (`app.py`, `forms.py`, `analytics.py`) will be refactored to use `TrainingDB` while maintaining their existing logic. Data transformations (like Pandas conversion for charts) will happen client-side after fetching from Supabase. We will add a basic pytest suite to verify the database client.

**Tech Stack:** Python, Streamlit, Supabase (`supabase-py`), Pandas, Pytest.

---

### Task 1: Add Dependencies and Supabase SQL Schema setup

**Files:**
- Modify: `requirements.txt`
- Create: `supabase_schema.sql` (For user reference)

- [ ] **Step 1: Update requirements.txt**

```text
streamlit
pandas
numpy
supabase
pytest
pytest-mock
```

- [ ] **Step 2: Create Supabase Schema file (for the user to run in Supabase SQL Editor)**
Create `supabase_schema.sql` with the following content:

```sql
CREATE TABLE training_plans (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT UNIQUE NOT NULL,
  exercises JSONB NOT NULL
);

CREATE TABLE workouts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  plan_name TEXT NOT NULL,
  exercise TEXT NOT NULL,
  weight FLOAT NOT NULL,
  sets INTEGER NOT NULL,
  reps INTEGER NOT NULL,
  rpe FLOAT NOT NULL,
  volume FLOAT NOT NULL
);

CREATE TABLE running (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  distance FLOAT NOT NULL,
  duration TEXT NOT NULL,
  pace TEXT NOT NULL,
  hr INTEGER NOT NULL,
  hrr INTEGER NOT NULL,
  category TEXT NOT NULL
);

CREATE TABLE nutrition (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  calories INTEGER NOT NULL,
  protein_g INTEGER NOT NULL,
  carbs_g INTEGER NOT NULL,
  fat_g INTEGER NOT NULL,
  creatine BOOLEAN NOT NULL,
  protein_powder BOOLEAN NOT NULL,
  multivitamin BOOLEAN NOT NULL,
  omega3 BOOLEAN NOT NULL
);

CREATE TABLE weight (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  weight FLOAT NOT NULL,
  notes TEXT
);
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt supabase_schema.sql
git commit -m "chore: add supabase dependencies and sql schema"
```

---

### Task 2: Create Supabase Client (`database.py`)

**Files:**
- Create: `modules/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_database.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_fetch_plans(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.get.return_value = "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    # Mocking the Supabase query chain: table().select().execute()
    mock_execute = MagicMock()
    mock_execute.data = [{"name": "Plan A", "exercises": []}]
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_execute
    
    db = TrainingDB()
    plans = db.fetch_plans()
    assert len(plans) == 1
    assert plans[0]["name"] == "Plan A"
    mock_supabase.table.assert_called_with("training_plans")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_database.py -v`
Expected: FAIL with ModuleNotFoundError or similar since `modules.database` doesn't exist.

- [ ] **Step 3: Write minimal implementation**
Create `modules/database.py`:

```python
import streamlit as st
from supabase import create_client, Client
import logging

class TrainingDB:
    def __init__(self):
        url = st.secrets.get("SUPABASE_URL", "dummy_url")
        key = st.secrets.get("SUPABASE_KEY", "dummy_key")
        try:
            self.client: Client = create_client(url, key)
        except Exception as e:
            logging.error(f"Failed to initialize Supabase client: {e}")
            self.client = None

    def is_connected(self):
        return self.client is not None

    def fetch_plans(self):
        if not self.is_connected(): return []
        res = self.client.table("training_plans").select("*").execute()
        return res.data

    def add_plan(self, name: str, exercises: list):
        if not self.is_connected(): return False
        try:
            self.client.table("training_plans").insert({"name": name, "exercises": exercises}).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save plan: {e}")
            return False

    def delete_plan(self, name: str):
        if not self.is_connected(): return False
        try:
            self.client.table("training_plans").delete().eq("name", name).execute()
            return True
        except Exception as e:
            st.error(f"Failed to delete plan: {e}")
            return False

    def save_workout(self, rows: list):
        if not self.is_connected(): return False
        try:
            self.client.table("workouts").insert(rows).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save workout: {e}")
            return False
            
    def fetch_workouts(self):
        if not self.is_connected(): return []
        res = self.client.table("workouts").select("*").execute()
        return res.data

    def save_run(self, data: dict):
        if not self.is_connected(): return False
        try:
            self.client.table("running").insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save run: {e}")
            return False

    def save_nutrition(self, data: dict):
        if not self.is_connected(): return False
        try:
            self.client.table("nutrition").insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save nutrition: {e}")
            return False
            
    def fetch_nutrition(self):
        if not self.is_connected(): return []
        res = self.client.table("nutrition").select("*").execute()
        return res.data

    def save_weight(self, data: dict):
        if not self.is_connected(): return False
        try:
            self.client.table("weight").insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save weight: {e}")
            return False
            
    def fetch_weight(self):
        if not self.is_connected(): return []
        res = self.client.table("weight").select("*").execute()
        return res.data

def get_db():
    return TrainingDB()
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/test_database.py modules/database.py
git commit -m "feat: add supabase TrainingDB client"
```

---

### Task 3: Refactor UI Forms (`modules/forms.py`)

**Files:**
- Modify: `modules/forms.py`

- [ ] **Step 1: Replace gsheet imports and update plan builder**
In `modules/forms.py`, replace `from modules.gsheet_api import batch_append, fetch_all_records, update_worksheet` with:
```python
from modules.database import get_db
```

Update `render_plan_builder()`:
```python
def render_plan_builder():
    db = get_db()
    st.header("🛠️ Training Plan Builder")
    st.info("Define recurring training templates.")
    
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
                    valid_ex = [{"name": ex["name"].strip(), "type": ex["type"]} for ex in ex_data if ex["name"].strip()]
                    if valid_ex:
                        if db.add_plan(plan_name.strip(), valid_ex):
                            st.success(f"Plan '{plan_name}' saved!")
                            st.rerun()
                    else:
                        st.warning("Add at least one exercise label.")

    st.subheader("📋 Active Plans")
    raw_plans = db.fetch_plans()
    if raw_plans:
        for p in raw_plans:
            p_name = p['name']
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"### {p_name}")
                if c2.button("🗑️ Delete", key=f"del_{p_name}"):
                    if db.delete_plan(p_name):
                        st.rerun()
                
                ex_list = ", ".join([f"{ex['name']} ({ex['type']})" for ex in p.get('exercises', [])])
                st.caption(ex_list)
    else:
        st.info("No plans found. Build your first one above!")
```

- [ ] **Step 2: Update render_workout_form()**
```python
def render_workout_form():
    db = get_db()
    st.subheader("🏋️ Training Logger")
    
    raw_plans = db.fetch_plans()
    if not raw_plans:
        st.warning("No plans found. Use the 'Plan Builder' in the System sidebar to get started.")
        return
        
    plan_names = [p['name'] for p in raw_plans]
    selected_plan_name = st.selectbox("Select Training Plan", plan_names)
    
    selected_plan = next((p for p in raw_plans if p['name'] == selected_plan_name), None)
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="tr_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="tr_time")
    
    log_ts = get_timestamp(l_date, l_time)
    # Supabase timestamp format expects YYYY-MM-DD HH:MM:SS, let's append :00
    db_ts = f"{log_ts}:00"

    with st.form(key=f"workout_form_{selected_plan_name}"):
        session_results = []
        for i, ex in enumerate(selected_plan.get('exercises', [])):
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
                        "log_ts": db_ts,
                        "plan_name": selected_plan_name,
                        "exercise": item["name"],
                        "weight": float(item["w"]),
                        "sets": int(item["s"]),
                        "reps": int(item["r"]),
                        "rpe": float(item["rpe"]),
                        "volume": float(volume)
                    })
            
            if final_rows and db.save_workout(final_rows):
                st.success(f"Session saved: {len(final_rows)} exercises logged.")
```

- [ ] **Step 3: Update render_running_form()**
```python
def render_running_form():
    db = get_db()
    st.subheader("🏃 Movement Tracker")
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="run_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="run_time")
    
    log_ts = get_timestamp(l_date, l_time)
    db_ts = f"{log_ts}:00"

    with st.form(key="run_form_v2"):
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
                
                data = {
                    "log_ts": db_ts,
                    "distance": float(dist),
                    "duration": dur,
                    "pace": pace_s,
                    "hr": int(hr),
                    "hrr": int(hrr),
                    "category": cat
                }
                
                if db.save_run(data):
                    st.success("Movement session logged.")
            except:
                st.error("Use MM:SS format for duration.")
```

- [ ] **Step 4: Update render_biohack_form()**
```python
def render_biohack_form():
    db = get_db()
    st.subheader("🍱 Nutrition Log")
    
    col_d, col_t = st.columns(2)
    with col_d:
        l_date = st.date_input("Date", datetime.now().date(), key="nut_date")
    with col_t:
        l_time = st.time_input("Time", datetime.now().time(), key="nut_time")
    
    log_ts = get_timestamp(l_date, l_time)
    db_ts = f"{log_ts}:00"

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
            data = {
                "log_ts": db_ts,
                "creatine": crea,
                "protein_powder": prot,
                "multivitamin": vit,
                "omega3": omg,
                "calories": int(cal),
                "protein_g": int(p_g),
                "carbs_g": int(c_g),
                "fat_g": int(f_g)
            }
            if db.save_nutrition(data):
                st.success("Nutrition data saved.")
```

- [ ] **Step 5: Commit**
```bash
git add modules/forms.py
git commit -m "refactor: update forms to use Supabase database client"
```

---

### Task 4: Refactor Analytics (`modules/analytics.py`)

**Files:**
- Modify: `modules/analytics.py`

- [ ] **Step 1: Replace gsheet imports**
In `modules/analytics.py`, replace:
```python
from modules.gsheet_api import fetch_all_records, batch_append
```
With:
```python
from modules.database import get_db
```

- [ ] **Step 2: Update render_analytics()**
```python
def render_analytics():
    db = get_db()
    st.title("📉 Analytics")
    c1, c2 = st.columns(2)
    
    with st.spinner("Syncing..."):
        weights_data = db.fetch_weight()
        df_weight = safe_numeric(pd.DataFrame(weights_data), ['weight'])

    with c1:
        st.subheader("Weight Prediction")
        with st.form("weight_form"):
            today_w = st.number_input("Current Weight", min_value=30.0, step=0.1)
            target_w = st.number_input("Target Weight", value=64.0, step=0.1)
            w_date = st.date_input("Date", datetime.now().date())
            w_ts = f"{w_date} 00:00:00"
            if st.form_submit_button("Log & Predict"):
                if db.save_weight({"log_ts": w_ts, "weight": float(today_w), "notes": "Manual Entry"}):
                    st.rerun()
        
        # We need to map 'log_ts' to 'Date' and 'weight' to 'Weight' for predict_target_date 
        if not df_weight.empty:
            df_weight = df_weight.rename(columns={"log_ts": "Date", "weight": "Weight"})
        pred = predict_target_date(df_weight, target_w)
        st.metric("Predicted Target Date", pred)

    with c2:
        st.subheader("Weight Trend")
        if not df_weight.empty:
            render_chart_safely(df_weight, 'Date', 'Weight', None)
        else:
            st.info("Insufficient data to render chart.")
```

- [ ] **Step 3: Update render_nutrition_analysis()**
```python
def render_nutrition_analysis():
    db = get_db()
    st.subheader("🥦 Nutrition & Energy")
    GOALS = {"Calories": 2500, "Protein": 160, "Carbs": 300, "Fat": 70}
    
    bio_data = db.fetch_nutrition()
    if not bio_data:
        st.info("No logs found.")
        return
        
    df_bio = safe_numeric(pd.DataFrame(bio_data), ['calories', 'protein_g', 'carbs_g', 'fat_g'])
    if df_bio.empty:
        st.info("No logs found.")
        return
        
    latest = df_bio.iloc[-1]
    
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, goal) in zip([c1, c2, c3, c4], GOALS.items()):
        key = 'calories' if label == "Calories" else f"{label.lower()}_g"
        val = float(latest.get(key, 0))
        diff = val - goal
        color = "inverse" if label == "Calories" and diff > 0 else "normal"
        col.metric(label, f"{val:.0f}/{goal}", delta=f"{diff:.0f}", delta_color=color)

    st.divider()
    st.markdown("### Daily Progress (%)")
    pct_data = []
    for label, goal in GOALS.items():
        key = 'calories' if label == "Calories" else f"{label.lower()}_g"
        val = float(latest.get(key, 0))
        pct = min(100, (val / goal * 100)) if goal > 0 else 0
        pct_data.append({"Macro": label, "Percentage": pct})
    
    st.bar_chart(pd.DataFrame(pct_data).set_index("Macro"), horizontal=True)
```

- [ ] **Step 4: Update render_overview()**
```python
def render_overview():
    db = get_db()
    st.title("🏠 Dashboard Overview")
    
    with st.spinner("Loading metrics..."):
        df_w = safe_numeric(pd.DataFrame(db.fetch_weight()), ['weight'])
        df_b = safe_numeric(pd.DataFrame(db.fetch_nutrition()), ['calories', 'protein_g', 'carbs_g', 'fat_g'])
        df_wrk = safe_numeric(pd.DataFrame(db.fetch_workouts()), ['volume'])

    k1, k2 = st.columns(2)
    k1.metric("Latest Weight", f"{df_w['weight'].iloc[-1]:.1f} kg" if not df_w.empty and 'weight' in df_w.columns else "N/A")
    
    if not df_b.empty and 'calories' in df_b.columns:
        cal = df_b['calories'].iloc[-1]
        k2.metric("Energy Balance", f"{cal:.0f} kcal", delta=f"{cal-2500:.0f} vs Goal", delta_color="inverse")
    else:
        k2.metric("Energy Balance", "N/A")

    # --- MACRO ROW ---
    if not df_b.empty and 'protein_g' in df_b.columns and 'carbs_g' in df_b.columns and 'fat_g' in df_b.columns:
        latest_bio = df_b.iloc[-1]
        m1, m2, m3 = st.columns(3)
        
        with m1:
            prot = float(latest_bio.get("protein_g", 0))
            target_p = 160
            st.metric("Protein", f"{prot:.1f} / {target_p}g", delta=f"{prot - target_p:.1f}g")
            
        with m2:
            carb = float(latest_bio.get("carbs_g", 0))
            target_c = 300
            st.metric("Carbohydrates", f"{carb:.1f} / {target_c}g", delta=f"{carb - target_c:.1f}g")
            
        with m3:
            fat = float(latest_bio.get("fat_g", 0))
            target_f = 70
            st.metric("Fats", f"{fat:.1f} / {target_f}g", delta=f"{fat - target_f:.1f}g")

    st.divider()
    l, r = st.columns(2)
    
    with l:
        if not df_wrk.empty:
            df_wrk_renamed = df_wrk.rename(columns={"log_ts": "Date", "volume": "Volume"})
            render_chart_safely(df_wrk_renamed, 'Date', 'Volume', "Weekly Training Volume")
        else:
            st.info("Insufficient data for Training Volume chart.")

    with r:
        if not df_w.empty:
            df_w_renamed = df_w.rename(columns={"log_ts": "Date", "weight": "Weight"})
            render_chart_safely(df_w_renamed, 'Date', 'Weight', "Weight Progression")
        else:
            st.info("Insufficient data for Weight chart.")
```

- [ ] **Step 5: Commit**
```bash
git add modules/analytics.py
git commit -m "refactor: update analytics to process Supabase data format"
```

---

### Task 5: App Entrypoint & Cleanup (`app.py` & `gsheet_api.py`)

**Files:**
- Modify: `app.py`
- Delete: `modules/gsheet_api.py`

- [ ] **Step 1: Replace gsheet imports in app.py**
In `app.py`, replace:
```python
from modules.gsheet_api import get_gspread_client
```
With:
```python
from modules.database import get_db
```

- [ ] **Step 2: Update main() in app.py**
Find `client = get_gspread_client()` and replace with `db = get_db()`.
Update the connection checks:
Replace `if client:` with `if db.is_connected():`.

```python
def main():
    """Main application entry point."""
    if not check_password():
        st.stop()

    db = get_db()

    # --- SIDEBAR STATUS ---
    with st.sidebar:
        st.title("⚙️ System Management")
        if db.is_connected():
            st.success("Database Online")
        else:
            st.error("Database Offline")
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
            
        st.divider()
        if db.is_connected():
            show_plan_builder = st.toggle("🛠️ Open Plan Builder", value=False)
        else:
            show_plan_builder = False

    # --- APP HEADER ---
    st.title("🎯 Training & Health Track")
    st.markdown("---")

    if show_plan_builder:
        render_plan_builder()
        st.stop()

    # --- NAVIGATION ---
    tabs = st.tabs(["🏠 Overview", "🏋️ Training", "🏃 Movement", "📉 Analytics", "🍱 Nutrition"])

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
```

- [ ] **Step 3: Delete gsheet_api.py**
Run:
```bash
rm modules/gsheet_api.py
```

- [ ] **Step 4: Commit cleanup**
```bash
git add app.py
git rm modules/gsheet_api.py
git commit -m "refactor: integrate Supabase client in app and remove Google Sheets API"
```
