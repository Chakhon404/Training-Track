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
            submit_weight = st.form_submit_button("Log & Predict")
            
            if submit_weight:
                new_row = [datetime.now().strftime('%Y-%m-%d'), today_weight]
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
