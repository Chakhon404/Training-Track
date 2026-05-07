import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.gsheet_api import fetch_all_records, batch_append

def predict_target_date(df_weights, target=64.0):
    """
    Predicts the date when the target weight will be reached using linear regression.
    Requires at least 3 data points.
    """
    if df_weights.empty or len(df_weights) < 3:
        return "Insufficient data (min 3 points required)"

    try:
        # Convert Date to numeric (days since first entry)
        df = df_weights.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        first_date = df['Date'].min()
        df['Days'] = (df['Date'] - first_date).dt.days
        
        # Linear regression: y = mx + c
        # y = Weight, x = Days
        x = df['Days'].values
        y = df['Weight'].values
        
        m, c = np.polyfit(x, y, 1)
        
        # If weight is increasing or stable and target is below current
        if m >= 0 and target < y[-1]:
            return "Trend is not moving towards target weight"
        if m <= 0 and target > y[-1]:
            return "Trend is not moving towards target weight"
        
        # Solve for x: target = mx + c => x = (target - c) / m
        target_days = (target - c) / m
        
        # Predict date
        predicted_date = first_date + timedelta(days=float(target_days))
        
        if predicted_date < datetime.now():
            return "Predicted date is in the past (already reached?)"
            
        return predicted_date.strftime('%Y-%m-%d')
        
    except Exception as e:
        return f"Prediction Error: {str(e)}"

def calculate_cns_readiness(df_runs, df_bio):
    """
    Calculates CNS Readiness score based on recent HR Recovery and PPPD trends.
    """
    try:
        score = 85 # Base score
        
        if not df_runs.empty:
            df_runs['Date'] = pd.to_datetime(df_runs['Date'])
            recent_runs = df_runs[df_runs['Date'] > (datetime.now() - timedelta(days=7))]
            if not recent_runs.empty:
                avg_hrr = recent_runs['HR Recovery'].mean()
                # HRR > 30 is good, < 20 is poor
                if avg_hrr > 35: score += 5
                elif avg_hrr < 25: score -= 10

        if not df_bio.empty:
            df_bio['Date'] = pd.to_datetime(df_bio['Date'])
            recent_bio = df_bio[df_bio['Date'] > (datetime.now() - timedelta(days=3))]
            if not recent_bio.empty:
                avg_pppd = recent_bio['PPPD'].mean()
                # PPPD > 8 is good, < 5 is poor
                if avg_pppd > 8: score += 5
                elif avg_pppd < 6: score -= 10

        # Clamp score
        score = max(0, min(100, score))
        
        if score >= 90: status = "Optimal"
        elif score >= 75: status = "Good"
        elif score >= 60: status = "Fair"
        else: status = "Fatigued"
        
        return f"{status} ({score}/100)"
    except Exception as e:
        return f"Status: Data Error ({str(e)})"

def render_analytics():
    """
    UI structure for the Analytics module.
    """
    st.title("📊 Training Analytics")
    
    col1, col2 = st.columns(2)
    
    # Fetch Data
    with st.spinner("Fetching latest data..."):
        weight_data = fetch_all_records("weight")
        run_data = fetch_all_records("running")
        bio_data = fetch_all_records("biohack")
        
        df_weight = pd.DataFrame(weight_data)
        df_runs = pd.DataFrame(run_data)
        df_bio = pd.DataFrame(bio_data)

    with col1:
        st.subheader("Weight Prediction")
        
        # Weight entry form
        with st.form("weight_entry"):
            today_weight = st.number_input("Today's Weight (kg)", min_value=30.0, max_value=200.0, step=0.1)
            target_weight = st.number_input("Target Weight (kg)", value=64.0, step=0.1)
            
            # Date and Time for weight logging
            c_d, c_t = st.columns(2)
            with c_d:
                w_date = st.date_input("Date", datetime.now().date())
            with c_t:
                w_time = st.time_input("Time", datetime.now().time())
            
            # Context selector (Day/Night analysis)
            w_context = st.selectbox("Context / Time of Day", ["Morning (Fasted)", "Day (Post-Meal)", "Night"])
            
            submit_weight = st.form_submit_button("Log & Predict")
            
            if submit_weight:
                w_datetime = f"{w_date} {w_time.strftime('%H:%M')}"
                new_row = [w_datetime, today_weight, w_context]
                success = batch_append("weight", [new_row])
                if success:
                    st.success("Weight logged!")
                    # Update df_weight for immediate prediction update
                    df_weight = pd.DataFrame(fetch_all_records("weight"))

        prediction = predict_target_date(df_weight, target=target_weight)
        st.metric("Target Date Prediction", prediction)

    with col2:
        st.subheader("CNS Readiness")
        status = calculate_cns_readiness(df_runs, df_bio)
        
        st.info("CNS readiness is calculated from your recent HR Recovery and PPPD (Post-Performance Physiological Drive) scores.")
        st.metric("CNS Status", status)
        
        # Trend Chart (Optional but good for UX)
        if not df_weight.empty:
            st.line_chart(df_weight.set_index('Date')['Weight'])

def render_nutrition_analysis():
    """
    Goal-based Macronutrient Tracking.
    """
    st.subheader("🥦 Macronutrient Distribution & Energy Balance")
    
    # Adjustable Goals (could be moved to st.sidebar or st.secrets later)
    GOALS = {
        "Calories": 2500,
        "Protein": 160,
        "Carbs": 300,
        "Fat": 70
    }
    
    with st.spinner("Fetching latest nutrition logs..."):
        bio_data = fetch_all_records("biohack")
        if not bio_data:
            st.info("No nutrition data found. Start logging in the Health tab.")
            return
        
        # Latest entry
        latest = bio_data[-1]
        
    # Mapping keys (ensure these match the order/names in GSheet if using get_all_records)
    # The order was: [Date, Creatine, Protein_P, MultiV, Omega3, PPPD, Shoulder, Calories, Protein_g, Carb_g, Fat_g, Weight_kg]
    # If get_all_records() returns a list of dicts, keys are headers.
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    
    def get_metric_delta(val, goal, label):
        diff = val - goal
        if label == "Calories":
            return diff, "inverse" # Red if over for calories
        return diff, "normal"

    with c1:
        cal = latest.get("Calories (kcal)", 0)
        diff, color = get_metric_delta(cal, GOALS["Calories"], "Calories")
        st.metric("Calories", f"{cal} / {GOALS['Calories']}", delta=f"{diff} kcal", delta_color=color)
        
    with c2:
        prot = latest.get("Protein (g)", 0)
        diff, _ = get_metric_delta(prot, GOALS["Protein"], "Protein")
        st.metric("Protein", f"{prot} / {GOALS['Protein']}g", delta=f"{diff}g")

    with c3:
        carb = latest.get("Carbs (g)", 0)
        diff, _ = get_metric_delta(carb, GOALS["Carbs"], "Carbs")
        st.metric("Carbohydrates", f"{carb} / {GOALS['Carbs']}g", delta=f"{diff}g")
        
    with c4:
        fat = latest.get("Fat (g)", 0)
        diff, _ = get_metric_delta(fat, GOALS["Fat"], "Fat")
        st.metric("Fats", f"{fat} / {GOALS['Fat']}g", delta=f"{diff}g")

    st.divider()
    
    # Progress Chart
    st.markdown("### Progress vs Daily Target")
    chart_data = pd.DataFrame({
        'Macro': ['Calories', 'Protein', 'Carbs', 'Fat'],
        'Percentage': [
            min(100, (cal / GOALS["Calories"]) * 100),
            min(100, (prot / GOALS["Protein"]) * 100),
            min(100, (carb / GOALS["Carbs"]) * 100),
            min(100, (fat / GOALS["Fat"]) * 100)
        ]
    })
    st.bar_chart(chart_data.set_index('Macro'), horizontal=True)

def render_overview():
    """
    Consolidated Goal-based Overview Dashboard.
    """
    st.title("🏠 Overview Dashboard")
    
    with st.spinner("Aggregating system-wide data..."):
        weight_data = fetch_all_records("weight")
        workouts_data = fetch_all_records("workouts")
        run_data = fetch_all_records("running")
        bio_data = fetch_all_records("biohack")
        
        df_weight = pd.DataFrame(weight_data)
        df_workouts = pd.DataFrame(workouts_data)
        df_runs = pd.DataFrame(run_data)
        df_bio = pd.DataFrame(bio_data)

    # --- KPI ROW ---
    st.markdown("### Key Performance Indicators")
    k1, k2, k3 = st.columns(3)
    
    with k1:
        latest_w = df_weight['Weight'].iloc[-1] if not df_weight.empty else "N/A"
        st.metric("Latest Weight", f"{latest_w} kg")
    
    with k2:
        from modules.analytics import calculate_cns_readiness
        status = calculate_cns_readiness(df_runs, df_bio)
        st.metric("CNS Readiness", status)
        
    with k3:
        if not df_bio.empty:
            cal_val = df_bio['Calories (kcal)'].iloc[-1]
            target = 2500
            diff = cal_val - target
            st.metric("Energy Balance", f"{cal_val} kcal", delta=f"{diff} vs Target", delta_color="inverse")
        else:
            st.metric("Energy Balance", "N/A")

    # --- MACRO ROW (Mirroring Nutrients tab) ---
    if not df_bio.empty:
        latest_bio = df_bio.iloc[-1]
        m1, m2, m3 = st.columns(3)
        
        with m1:
            prot = latest_bio.get("Protein (g)", 0)
            target_p = 160
            st.metric("Protein", f"{prot} / {target_p}g", delta=f"{prot - target_p}g")
            
        with m2:
            carb = latest_bio.get("Carbs (g)", 0)
            target_c = 300
            st.metric("Carbohydrates", f"{carb} / {target_c}g", delta=f"{carb - target_c}g")
            
        with m3:
            fat = latest_bio.get("Fat (g)", 0)
            target_f = 70
            st.metric("Fats", f"{fat} / {target_f}g", delta=f"{fat - target_f}g")

    st.divider()

    # --- HEALTH ALERTS & VOLUME ---
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.markdown("### ⚠️ Health & Stability Alerts")
        if not df_bio.empty:
            recent_7 = df_bio.tail(7)
            avg_shoulder = recent_7['Stability Score (Shoulder)'].mean()
            avg_pppd = recent_7['Equilibrium Score (PPPD)'].mean()
            
            # Shoulder Alert
            if avg_shoulder < 4:
                st.error(f"Shoulder Stability Low: {avg_shoulder:.1f}/10")
            elif avg_shoulder < 7:
                st.warning(f"Shoulder Stability Moderate: {avg_shoulder:.1f}/10")
            else:
                st.success(f"Shoulder Stability Optimal: {avg_shoulder:.1f}/10")
                
            # PPPD Alert
            if avg_pppd > 7:
                st.error(f"PPPD Symptoms High: {avg_pppd:.1f}/10")
            elif avg_pppd > 4:
                st.warning(f"PPPD Symptoms Moderate: {avg_pppd:.1f}/10")
            else:
                st.success(f"PPPD Symptoms Low: {avg_pppd:.1f}/10")
        else:
            st.info("Insufficient health data for alerts.")

    with col_right:
        st.markdown("### 📊 Weekly Training Volume")
        if not df_workouts.empty:
            # Aggregate volume over last 7 days
            df_workouts['Date'] = pd.to_datetime(df_workouts['Date'])
            last_7_days = datetime.now() - timedelta(days=7)
            recent_workouts = df_workouts[df_workouts['Date'] >= last_7_days]
            
            if not recent_workouts.empty:
                # Group by Date and sum Volume
                daily_vol = recent_workouts.groupby(recent_workouts['Date'].dt.date)['Volume'].sum()
                st.line_chart(daily_vol)
            else:
                st.info("No workouts logged in the last 7 days.")
        else:
            st.info("Log your training sessions to track volume.")

    st.divider()
    
    # Weight Trend Chart
    st.markdown("### Weight Progression")
    if not df_weight.empty:
        st.line_chart(df_weight.set_index('Date')['Weight'])
    else:
        st.info("Log your weight to see progress.")

