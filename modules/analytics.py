import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.database import get_db

# --- UTILITIES ---

def safe_numeric(df, columns):
    """Sanitizes dataframe columns: coerces to numeric, fills NaN with 0."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def render_chart_safely(df, x, y, title=None, chart_type='line'):
    """Renders a chart only if valid data exists, switches type based on count."""
    if df.empty or x not in df.columns or y not in df.columns:
        st.info(f"Insufficient data to render {title or y} chart.")
        return

    # Clean data for plotting
    plot_df = df.copy()
    plot_df[x] = pd.to_datetime(plot_df[x], errors='coerce')
    plot_df = plot_df.dropna(subset=[x, y])
    
    if plot_df.empty:
        st.info(f"No valid data points for {title or y}.")
        return

    if title: st.markdown(f"#### {title}")
    
    # Logic: 1 point = scatter, >1 point = requested type
    if len(plot_df) == 1:
        st.scatter_chart(plot_df.set_index(x)[y])
    else:
        if chart_type == 'line':
            st.line_chart(plot_df.set_index(x)[y])
        else:
            st.bar_chart(plot_df.set_index(x)[y])

# --- CORE LOGIC ---

def predict_target_date(df_weights, target=64.0):
    """Predicts target date using linear regression. Minimum 2 valid points."""
    if df_weights.empty: return "Collecting data for predictions..."
    
    df = df_weights.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
    df = df.dropna(subset=['Date', 'Weight']).sort_values('Date')

    if len(df) < 2:
        return "Collecting data for predictions..."

    try:
        first_date = df['Date'].min()
        df['Days'] = (df['Date'] - first_date).dt.days
        x, y = df['Days'].values, df['Weight'].values
        
        m, c = np.polyfit(x, y, 1)
        
        # Trend checks
        if m >= 0 and target < y[-1]: return "Weight is increasing/stable"
        if m <= 0 and target > y[-1]: return "Weight is decreasing/stable"
        if abs(m) < 1e-6: return "No trend detected"

        target_days = (target - c) / m
        predicted_date = first_date + timedelta(days=float(target_days))
        
        if predicted_date < datetime.now(): return "Target reached or date in past"
        return predicted_date.strftime('%Y-%m-%d')
    except Exception as e:
        return f"Err: {str(e)}"

# --- UI RENDERING ---

def render_analytics():
    st.title("📉 Analytics")
    db = get_db()
    c1, c2 = st.columns(2)
    
    with st.spinner("Fetching data..."):
        weight_data = db.fetch_weight()
        df_weight = pd.DataFrame(weight_data)
        if not df_weight.empty:
            df_weight = df_weight.rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
            df_weight = safe_numeric(df_weight, ['Weight'])

    with c1:
        st.subheader("Weight Prediction")
        with st.form("weight_form"):
            today_w = st.number_input("Current Weight", min_value=30.0, step=0.1)
            target_w = st.number_input("Target Weight", value=64.0, step=0.1)
            w_date = st.date_input("Date", datetime.now().date())
            notes = st.text_input("Notes")
            if st.form_submit_button("Log & Predict"):
                if db.save_weight({
                    "log_ts": datetime.combine(w_date, datetime.now().time()).isoformat(),
                    "weight": today_w,
                    "notes": notes
                }):
                    st.success("Weight logged!")
                    st.rerun()
        
        pred = predict_target_date(df_weight, target_w)
        st.metric("Predicted Target Date", pred)

    with c2:
        st.subheader("Weight Trend")
        render_chart_safely(df_weight, 'Date', 'Weight', None)

def render_nutrition_analysis():
    st.subheader("🥦 Nutrition & Energy")
    db = get_db()
    GOALS = {"Calories": 2500, "Protein": 160, "Carbs": 300, "Fat": 70}
    
    nutrition_data = db.fetch_nutrition()
    if not nutrition_data:
        st.info("No logs found.")
        return
        
    df_nut = pd.DataFrame(nutrition_data)
    if df_nut.empty:
        st.info("No logs found.")
        return

    # Map columns
    df_nut = df_nut.rename(columns={
        'log_ts': 'Date',
        'calories': 'Calories (kcal)',
        'protein_g': 'Protein (g)',
        'carbs_g': 'Carbs (g)',
        'fat_g': 'Fat (g)'
    })
    
    df_nut = safe_numeric(df_nut, ['Calories (kcal)', 'Protein (g)', 'Carbs (g)', 'Fat (g)'])
    latest = df_nut.iloc[-1]
    
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, goal) in zip([c1, c2, c3, c4], GOALS.items()):
        key = 'Calories (kcal)' if label == "Calories" else f"{label} (g)"
        val = float(latest.get(key, 0))
        diff = val - goal
        color = "inverse" if label == "Calories" and diff > 0 else "normal"
        col.metric(label, f"{val:.0f}/{goal}", delta=f"{diff:.0f}", delta_color=color)

    st.divider()
    
    # Supplement Status
    st.markdown("### Supplements")
    s1, s2, s3, s4 = st.columns(4)
    supps = [
        ("Creatine", "creatine"),
        ("Protein Powder", "protein_powder"),
        ("Multivitamin", "multivitamin"),
        ("Omega-3", "omega3")
    ]
    for col, (label, key) in zip([s1, s2, s3, s4], supps):
        status = "✅" if latest.get(key) else "❌"
        col.markdown(f"**{label}**: {status}")

    st.divider()
    st.markdown("### Daily Progress (%)")
    pct_data = []
    for label, goal in GOALS.items():
        key = 'Calories (kcal)' if label == "Calories" else f"{label} (g)"
        val = float(latest.get(key, 0))
        pct = min(100, (val / goal * 100)) if goal > 0 else 0
        pct_data.append({"Macro": label, "Percentage": pct})
    
    st.bar_chart(pd.DataFrame(pct_data).set_index("Macro"), horizontal=True)

def render_overview():
    st.title("🏠 Dashboard Overview")
    db = get_db()
    today = datetime.now().date()
    
    with st.spinner("Loading today's activity..."):
        # Section A: Today's Summary
        workouts = db.fetch_workouts()
        weights = db.fetch_weight()
        nutrition = db.fetch_nutrition()
        runs = db.fetch_runs()

        # Filter for today
        today_str = today.strftime("%Y-%m-%d")
        wrk_today = [w for w in workouts if w['log_ts'].startswith(today_str)]
        wgt_today = [w for w in weights if w['log_ts'].startswith(today_str)]
        nut_today = [n for n in nutrition if n['log_ts'].startswith(today_str)]
        run_today = [r for r in runs if r['log_ts'].startswith(today_str)]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏋️ Training", f"{len(wrk_today)} Exercises" if wrk_today else "Rest Day")
        c2.metric("⚖️ Weight", f"{wgt_today[-1]['weight']} kg" if wgt_today else "Not logged")
        c3.metric("🍱 Nutrition", f"{nut_today[-1]['calories']} kcal" if nut_today else "Not logged")
        
        total_dist = sum([r['distance'] for r in run_today])
        c4.metric("🏃 Movement", f"{total_dist:.1f} km" if total_dist > 0 else "Rest Day")

    st.divider()

    # Section B: Progressive Overload Alert
    st.subheader("📈 Progressive Overload Tracking")
    vol_data = db.fetch_weekly_volume()
    if vol_data:
        df_vol = pd.DataFrame(vol_data)
        df_vol['log_ts'] = pd.to_datetime(df_vol['log_ts'])
        df_vol['week'] = df_vol['log_ts'].dt.isocalendar().week
        df_vol['year'] = df_vol['log_ts'].dt.isocalendar().year
        
        weekly_totals = df_vol.groupby(['year', 'week'])['volume'].sum().sort_index(ascending=False)
        
        if len(weekly_totals) >= 2:
            curr_vol = weekly_totals.iloc[0]
            prev_vol = weekly_totals.iloc[1]
            
            if prev_vol > 0:
                diff_pct = ((curr_vol - prev_vol) / prev_vol) * 100
                if curr_vol >= prev_vol:
                    st.success(f"✅ On track — volume up {diff_pct:.1f}% vs last week.")
                else:
                    st.warning(f"⚠️ Weekly volume is down {abs(diff_pct):.1f}% vs last week.")
            else:
                st.info("📊 Comparison not possible (previous week volume was 0).")
        else:
            st.info("📊 Log at least 2 weeks of training to see overload trends.")
    else:
        st.info("📊 Log training sessions to see overload trends.")

    st.divider()
    
    # Section C: Keep existing charts
    l, r = st.columns(2)
    with st.spinner("Generating charts..."):
        # Re-fetch for charts if needed or use previous data
        df_w = pd.DataFrame(weights).rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
        df_w = safe_numeric(df_w, ['Weight'])
        
        df_wrk = pd.DataFrame(workouts).rename(columns={'log_ts': 'Date', 'volume': 'Volume'})
        df_wrk = safe_numeric(df_wrk, ['Volume'])

    with l:
        render_chart_safely(df_wrk, 'Date', 'Volume', "Weekly Training Volume")
    with r:
        render_chart_safely(df_w, 'Date', 'Weight', "Weight Progression")
