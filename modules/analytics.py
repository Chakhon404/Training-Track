import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.gsheet_api import fetch_all_records, batch_append

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
    if df_weights.empty: return "No data found"
    
    df = df_weights.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
    df = df.dropna(subset=['Date', 'Weight']).sort_values('Date')

    if len(df) < 2:
        return "Need more data points (min 2)"

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
    c1, c2 = st.columns(2)
    
    with st.spinner("Syncing..."):
        df_weight = safe_numeric(pd.DataFrame(fetch_all_records("weight")), ['Weight'])

    with c1:
        st.subheader("Weight Prediction")
        with st.form("weight_form"):
            today_w = st.number_input("Current Weight", min_value=30.0, step=0.1)
            target_w = st.number_input("Target Weight", value=64.0, step=0.1)
            w_date = st.date_input("Date", datetime.now().date())
            if st.form_submit_button("Log & Predict"):
                if batch_append("weight", [[str(w_date), today_w, "Manual Entry"]]):
                    st.rerun()
        
        pred = predict_target_date(df_weight, target_w)
        st.metric("Predicted Target Date", pred)

    with c2:
        st.subheader("Weight Trend")
        render_chart_safely(df_weight, 'Date', 'Weight', None)

def render_nutrition_analysis():
    st.subheader("🥦 Nutrition & Energy")
    GOALS = {"Calories": 2500, "Protein": 160, "Carbs": 300, "Fat": 70}
    
    bio_data = fetch_all_records("biohack")
    if not bio_data:
        st.info("No logs found.")
        return
        
    df_bio = safe_numeric(pd.DataFrame(bio_data), ['Calories (kcal)', 'Protein (g)', 'Carbs (g)', 'Fat (g)'])
    if df_bio.empty:
        st.info("No logs found.")
        return
        
    latest = df_bio.iloc[-1]
    
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, goal) in zip([c1, c2, c3, c4], GOALS.items()):
        key = 'Calories (kcal)' if label == "Calories" else f"{label} (g)"
        val = float(latest.get(key, 0))
        diff = val - goal
        color = "inverse" if label == "Calories" and diff > 0 else "normal"
        col.metric(label, f"{val:.0f}/{goal}", delta=f"{diff:.0f}", delta_color=color)

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
    
    with st.spinner("Loading metrics..."):
        df_w = safe_numeric(pd.DataFrame(fetch_all_records("weight")), ['Weight'])
        df_b = safe_numeric(pd.DataFrame(fetch_all_records("biohack")), ['Calories (kcal)', 'Protein (g)', 'Carbs (g)', 'Fat (g)'])
        df_wrk = safe_numeric(pd.DataFrame(fetch_all_records("workouts")), ['Volume'])

    k1, k2 = st.columns(2)
    k1.metric("Latest Weight", f"{df_w['Weight'].iloc[-1]:.1f} kg" if not df_w.empty and 'Weight' in df_w.columns else "N/A")
    
    if not df_b.empty and 'Calories (kcal)' in df_b.columns:
        cal = df_b['Calories (kcal)'].iloc[-1]
        k2.metric("Energy Balance", f"{cal:.0f} kcal", delta=f"{cal-2500:.0f} vs Goal", delta_color="inverse")
    else:
        k2.metric("Energy Balance", "N/A")

    # --- MACRO ROW ---
    if not df_b.empty and 'Protein (g)' in df_b.columns and 'Carbs (g)' in df_b.columns and 'Fat (g)' in df_b.columns:
        latest_bio = df_b.iloc[-1]
        m1, m2, m3 = st.columns(3)
        
        with m1:
            prot = float(latest_bio.get("Protein (g)", 0))
            target_p = 160
            st.metric("Protein", f"{prot:.1f} / {target_p}g", delta=f"{prot - target_p:.1f}g")
            
        with m2:
            carb = float(latest_bio.get("Carbs (g)", 0))
            target_c = 300
            st.metric("Carbohydrates", f"{carb:.1f} / {target_c}g", delta=f"{carb - target_c:.1f}g")
            
        with m3:
            fat = float(latest_bio.get("Fat (g)", 0))
            target_f = 70
            st.metric("Fats", f"{fat:.1f} / {target_f}g", delta=f"{fat - target_f:.1f}g")

    st.divider()
    l, r = st.columns(2)
    
    with l:
        render_chart_safely(df_wrk, 'Date', 'Volume', "Weekly Training Volume")

    with r:
        render_chart_safely(df_w, 'Date', 'Weight', "Weight Progression")
