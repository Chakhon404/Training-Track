import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import json
from datetime import datetime, timedelta
import pytz
from modules.database import (
    get_db, fetch_profile_cached, fetch_workouts_cached,
    fetch_nutrition_cached, fetch_weight_cached, fetch_wellness_cached,
    fetch_today_summary_cached, fetch_runs_cached
)
from modules.constants import SUPPLEMENT_MAP
from modules.forms import render_today_training_summary

# --- UTILITIES ---

def apply_dark_theme(fig, primary_color='#C8F135'):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#141417',
        font=dict(family='Inter', color='#888880', size=11),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.05)',
            linecolor='rgba(255,255,255,0.07)',
            tickfont=dict(color='#888880'),
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.05)',
            linecolor='rgba(255,255,255,0.07)',
            tickfont=dict(color='#888880'),
        ),
        margin=dict(l=0, r=0, t=28, b=0),
        legend=dict(
            bgcolor='rgba(0,0,0,0)',
            font=dict(color='#888880'),
        ),
    )
    fig.update_traces(marker_color=primary_color)
    return fig

def safe_numeric(df, columns):
    """Sanitizes dataframe columns: coerces to numeric, fills NaN with 0."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def render_chart_safely(df, x, y, title=None, chart_type='line', primary_color='#C8F135', key=None):
    """Renders a chart only if valid data exists, switches type based on count."""
    if df.empty or x not in df.columns or y not in df.columns:
        st.info(f"Insufficient data to render {title or y} chart.")
        return

    # Clean data for plotting
    plot_df = df.copy()
    plot_df[x] = pd.to_datetime(plot_df[x], format='ISO8601', errors='coerce')
    plot_df = plot_df.dropna(subset=[x, y])
    
    if plot_df.empty:
        st.info(f"No valid data points for {title or y}.")
        return

    if title:
        st.markdown(f'<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:8px;">{title}</div>', unsafe_allow_html=True)
    
    # Logic: 1 point = scatter, >1 point = requested type
    if chart_type == 'line':
        fig = px.line(plot_df, x=x, y=y)
    else:
        fig = px.bar(plot_df, x=x, y=y)
    
    apply_dark_theme(fig, primary_color)
    st.plotly_chart(fig, use_container_width=True, key=key or f"chart_{x}_{y}")

# --- CORE LOGIC ---

def predict_target_date(df_weights, target=64.0):
    """Predicts target date using linear regression. Minimum 2 valid points."""
    if df_weights.empty: return "Collecting data for predictions..."
    
    df = df_weights.copy()
    df['Date'] = pd.to_datetime(df['Date'], format='ISO8601', errors='coerce')
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
    df = df.dropna(subset=['Date', 'Weight']).sort_values('Date')

    if len(df) < 2:
        return "Collecting data for predictions..."

    try:
        first_date = df['Date'].min()
        df['Days'] = (df['Date'] - first_date).dt.days
        x, y = df['Days'].values, df['Weight'].values
        
        # Check for sufficient variance and unique points
        if len(np.unique(x)) <= 1 or np.var(x) == 0:
            return "Collecting data for predictions..."

        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('error', category=np.RankWarning)
            warnings.filterwarnings('error', category=RuntimeWarning)
            try:
                m, c = np.polyfit(x, y, 1)
            except (np.RankWarning, RuntimeWarning):
                return "Collecting data for predictions..."
        
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
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">Weight</div>', unsafe_allow_html=True)
    db = get_db()
    profile = fetch_profile_cached(db) or {}
    GOAL_WEIGHT = profile.get("goal_weight_kg") or 64.0

    with st.spinner("Fetching data..."):
        weight_data = fetch_weight_cached(db)
        df_weight = pd.DataFrame(weight_data)
        if not df_weight.empty:
            df_weight = df_weight.rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
            df_weight = safe_numeric(df_weight, ['Weight'])
            df_weight['body_fat_pct'] = pd.to_numeric(df_weight['body_fat_pct'], errors='coerce')
            df_weight['Date'] = pd.to_datetime(df_weight['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
            df_weight = df_weight.sort_values('Date')

    # 1. Metrics Row
    if not df_weight.empty:
        m1, m2 = st.columns(2)
        latest = df_weight.iloc[-1]
        prev = df_weight.iloc[-2] if len(df_weight) > 1 else latest
        
        w_delta = float(latest['Weight']) - float(prev['Weight'])
        m1.metric("Latest Weight", f"{latest['Weight']:.1f} kg", delta=f"{w_delta:+.1f} kg", delta_color="inverse")
        
        bf_val = latest.get('body_fat_pct', 0)
        bf_prev = prev.get('body_fat_pct', 0)
        bf_delta = float(bf_val) - float(bf_prev)
        m2.metric("Body Fat", f"{bf_val:.1f}%", delta=f"{bf_delta:+.1f}%", delta_color="inverse")
        
        st.divider()

    # 2. Unified Logging Form
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:20px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Weight & Body Fat Log</div>', unsafe_allow_html=True)
    with st.form("weight_form_unified"):
        c1, c2, c3 = st.columns(3)
        today_w = c1.number_input("Weight (kg)", min_value=30.0, step=0.1)
        today_bf = c2.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, value=float(profile.get('body_fat_pct') or 0.0))
        _bkk = pytz.timezone("Asia/Bangkok")
        w_date = c3.date_input("Date", datetime.now(_bkk).date())
        notes = st.text_input("Notes (optional)")
        if st.form_submit_button("Save Stats", use_container_width=True):
            if db.check_duplicate_weight(str(w_date)) > 0:
                st.markdown("""
                <div style="background:rgba(239,159,39,0.08);border:0.5px solid rgba(239,159,39,0.3);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#EF9F27;font-family:Inter, sans-serif;">
                Duplicate entry already exists for """ + str(w_date) + """. Please use the Data Manager to overwrite.</div>""", unsafe_allow_html=True)
            else:
                _bkk = pytz.timezone("Asia/Bangkok")
                if db.save_weight({
                    "log_ts": datetime.combine(w_date, datetime.now(_bkk).replace(microsecond=0).time().replace(tzinfo=None)).isoformat(),
                    "weight": today_w,
                    "body_fat_pct": today_bf,
                    "notes": notes
                }):
                    st.success("Stats logged!")
                    st.rerun()

    st.divider()
    
    # 3. Trend Charts
    chart_l, chart_r = st.columns(2)
    
    with chart_l:
        render_chart_safely(df_weight, 'Date', 'Weight', "Weight Trend", primary_color='#C8F135', key="weight_trend_tab")

    with chart_r:
        if not df_weight.empty and df_weight['body_fat_pct'].notna().any():
            plot_bf_df = df_weight.dropna(subset=['body_fat_pct']).sort_values('Date')
            fig_bf = px.line(
                plot_bf_df,
                x='Date', y='body_fat_pct',
                labels={'Date': 'Date', 'body_fat_pct': 'Body Fat (%)'}
            )
            fig_bf.update_traces(mode='lines+markers')
            apply_dark_theme(fig_bf, '#F13568')
            st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:8px;">Body Fat % Trend</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_bf, use_container_width=True, key="bodyfat_trend_tab")
        else:
            st.info("Log body fat to see the trend chart.")

def render_nutrition_analysis():
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:22px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:12px;">Nutrition & Energy</div>', unsafe_allow_html=True)
    db = get_db()
    profile = fetch_profile_cached(db) or {}
    GOAL_CALORIES = profile.get("goal_calories") or 2500
    GOAL_PROTEIN = profile.get("goal_protein_g") or 150
    GOAL_CARBS = profile.get("goal_carbs_g") or 300
    GOAL_FAT = profile.get("goal_fat_g") or 70

    GOALS = {
        "Calories": GOAL_CALORIES,
        "Protein": GOAL_PROTEIN,
        "Carbs": GOAL_CARBS,
        "Fat": GOAL_FAT
    }
    
    nutrition_data = fetch_nutrition_cached(db)
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
    
    # Date processing with TZ strip
    df_nut['Date_dt'] = pd.to_datetime(df_nut['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
    df_nut = safe_numeric(df_nut, ['Calories (kcal)', 'Protein (g)', 'Carbs (g)', 'Fat (g)'])
    _bkk = pytz.timezone("Asia/Bangkok")
    today_str = datetime.now(_bkk).date()
    df_nut['Date_date'] = df_nut['Date_dt'].dt.date
    df_today = df_nut[df_nut['Date_date'] == today_str]

    if df_today.empty:
        st.info("Nutrition information for today is not yet available.")
        return
    # Sum all entries for today (multiple meals)
    cal_val  = df_today['Calories (kcal)'].sum()
    prot_val = df_today['Protein (g)'].sum()
    carb_val = df_today['Carbs (g)'].sum()
    fat_val  = df_today['Fat (g)'].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, goal) in zip([c1, c2, c3, c4], GOALS.items()):
        if label == "Calories": val = cal_val
        elif label == "Protein": val = prot_val
        elif label == "Carbs": val = carb_val
        else: val = fat_val
        
        diff = val - goal
        color = "inverse" if label == "Calories" and diff > 0 else "normal"
        col.metric(label, f"{val:.0f}/{goal}", delta=f"{diff:.0f}", delta_color=color)

    st.divider()
    
    # Dynamic Supplement Status based on Profile Defaults
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Supplements</div>', unsafe_allow_html=True)
    default_sups = profile.get("default_supplements") or []
    if not default_sups:
        st.info("No supplements configured in profile. Go to System -> Edit Profile & Goals to add them.")
    else:
        pills_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">'
        for sup_key in default_sups:
            if sup_key in SUPPLEMENT_MAP:
                display, _, db_col = SUPPLEMENT_MAP[sup_key]
                taken = bool(df_today[db_col].any()) if db_col in df_today.columns else False
                if taken:
                    pills_html += f'<div style="background:rgba(200,241,53,0.08);border:0.5px solid rgba(200,241,53,0.2);color:#C8F135;padding:4px 12px;border-radius:20px;font-size:11px;font-family:Inter, sans-serif;font-weight:500;">{display}</div>'
                else:
                    pills_html += f'<div style="background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.07);color:#444440;padding:4px 12px;border-radius:20px;font-size:11px;font-family:Inter, sans-serif;font-weight:500;">{display}</div>'
        pills_html += '</div>'
        st.markdown(pills_html, unsafe_allow_html=True)

    st.divider()
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Daily Progress (%)</div>', unsafe_allow_html=True)
    
    progress_html = ""
    macro_colors = {"Calories": "#C8F135", "Protein": "#F13568", "Carbs": "#35C8F1", "Fat": "#EF9F27"}
    for label, goal in GOALS.items():
        if label == "Calories": val = cal_val
        elif label == "Protein": val = prot_val
        elif label == "Carbs": val = carb_val
        else: val = fat_val
        
        pct = min(100, (val / goal * 100)) if goal > 0 else 0
        color = macro_colors.get(label, "#C8F135")
        
        progress_html += f"""
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:11px;color:#888880;font-family:Inter, sans-serif;">{label}</span>
            <span style="font-size:11px;color:#F0EFE8;font-weight:500;">{val:.0f} / {goal}</span>
          </div>
          <div style="height:4px;background:#1F1F26;border-radius:2px;">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:2px;transition:width 0.3s;"></div>
          </div>
        </div>
        """
    st.markdown(progress_html, unsafe_allow_html=True)

    # Section: Meal Score Trend
    if 'meal_score' in df_nut.columns and df_nut['meal_score'].notna().any():
        st.divider()
        st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Meal Score Trend</div>', unsafe_allow_html=True)
        # Ensure we drop NaNs for the chart and sort by Date
        plot_ms_df = df_nut.dropna(subset=['meal_score']).copy()
        plot_ms_df['Date_plot'] = pd.to_datetime(plot_ms_df['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
        plot_ms_df = plot_ms_df.sort_values('Date_plot')
        fig_ms = px.line(
            plot_ms_df,
            x='Date_plot', y='meal_score',
            labels={'Date_plot': 'Date', 'meal_score': 'Meal Score'}
        )
        fig_ms.update_yaxes(range=[0, 10.5]) # Score is 1-10, give some breathing room
        fig_ms.add_hline(y=7, line_dash="dash", line_color="gray", annotation_text="Good")
        apply_dark_theme(fig_ms, '#EF9F27')
        st.plotly_chart(fig_ms, use_container_width=True, key="meal_score_trend")

    st.divider()
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Supplement Compliance (last 30 days)</div>', unsafe_allow_html=True)

    # Total unique logging days
    total_days = df_nut['Date_date'].nunique()

    sup_data = []
    for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items():
        if json_key not in default_sups:
            continue
        if db_col in df_nut.columns:
            # Group by date first, then check if taken in any meal that day
            days_taken = int(df_nut.groupby('Date_date')[db_col].any().sum())
            pct = (days_taken / total_days * 100) if total_days > 0 else 0
            sup_data.append({"Supplement": display, "Compliance (%)": round(pct, 1)})

    if sup_data:
        df_comp = pd.DataFrame(sup_data).sort_values("Compliance (%)", ascending=True)

        fig_comp = px.bar(
            df_comp,
            x="Compliance (%)", y="Supplement",
            orientation="h",
            color="Compliance (%)",
            color_continuous_scale=["#F13568", "#EF9F27", "#C8F135"],
            range_color=[0, 100],
            labels={"Compliance (%)": "Days taken (%)"}
        )
        fig_comp.update_layout(showlegend=False, coloraxis_showscale=False)
        apply_dark_theme(fig_comp)
        st.plotly_chart(fig_comp, use_container_width=True, key="supplement_compliance")
    else:
        st.info("No supplement data yet.")

def render_overview():
    db = get_db()
    _bkk = pytz.timezone("Asia/Bangkok")
    today = datetime.now(_bkk).date()
    profile = fetch_profile_cached(db) or {}
    GOAL_CALORIES = profile.get("goal_calories") or 2500
    GOAL_PROTEIN = profile.get("goal_protein_g") or 150
    GOAL_WEIGHT = profile.get("goal_weight_kg") or None
    
    with st.spinner("Loading Today's Summary..."):
        summary = fetch_today_summary_cached(db, str(today))
        
        work_today = pd.DataFrame(summary["work"])
        run_today = pd.DataFrame(summary["run"])
        nut_today = pd.DataFrame(summary["nut"])
        weight_today = pd.DataFrame(summary["weight"])


    # Section A — Header
    st.markdown(f"""
    <div style="font-family:Inter, sans-serif;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin:0 0 4px;">Daily Overview</div>
    <div style="font-size:12px;color:#888880;font-family:Inter, sans-serif;font-weight:300;margin-bottom:20px;">{today.strftime('%A, %d %B %Y')}</div>
    """, unsafe_allow_html=True)

    if profile:
        goal_w = profile.get('goal_weight_kg')
        curr_w = profile.get('weight_kg')
        to_goal_html = ""
        if goal_w and curr_w:
            diff = round(curr_w - goal_w, 1)
            to_goal_html = f"Metric: To Goal | Value: {abs(diff)} kg | Delta: {-diff:+.1f} kg"
        
        profile_grid = f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
            <div><div style="font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">Weight</div><div style="font-family:Inter, sans-serif;font-size:20px;font-weight:700;color:#F0EFE8;">{profile.get('weight_kg', 'N/A')} kg</div></div>
            <div><div style="font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">Height</div><div style="font-family:Inter, sans-serif;font-size:20px;font-weight:700;color:#F0EFE8;">{profile.get('height_cm', 'N/A')} cm</div></div>
            <div><div style="font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">Body Fat</div><div style="font-family:Inter, sans-serif;font-size:20px;font-weight:700;color:#F0EFE8;">{profile.get('body_fat_pct', 'N/A')}%</div></div>
            <div><div style="font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">To Goal</div><div style="font-family:Inter, sans-serif;font-size:20px;font-weight:700;color:#F0EFE8;">{f"{abs(curr_w - goal_w):.2f}" if goal_w and curr_w else 'N/A'} kg</div></div>
        </div>
        """
        
        st.markdown(f"""
        <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px 20px;margin-bottom:12px;">
            <div style="font-family:Inter, sans-serif;font-size:12px;font-weight:700;color:#444440;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:12px;">Profile</div>
            {profile_grid}
        </div>""", unsafe_allow_html=True)

    # Section B — Activity Status Row
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if not work_today.empty:
            st.markdown('<div style="border-top:1.5px solid #C8F135;border-radius:2px;margin-bottom:-10px;position:relative;z-index:1;"></div>', unsafe_allow_html=True)
            count = work_today['exercise'].nunique()
            vol = work_today['volume'].sum()
            st.metric("Training", f"{count} exercises", delta=f"{vol:,.0f} kg volume")
        else:
            st.metric("Training", "Rest day")

    with c2:
        if not run_today.empty:
            st.markdown('<div style="border-top:1.5px solid #C8F135;border-radius:2px;margin-bottom:-10px;position:relative;z-index:1;"></div>', unsafe_allow_html=True)
            dist = run_today['distance'].sum()
            cat = run_today.iloc[-1]['category']
            st.metric("Movement", f"{dist:.1f} km", delta=cat)
        else:
            st.metric("Movement", "Rest day")

    with c3:
        if not nut_today.empty:
            st.markdown('<div style="border-top:1.5px solid #C8F135;border-radius:2px;margin-bottom:-10px;position:relative;z-index:1;"></div>', unsafe_allow_html=True)
            cal = int(nut_today['calories'].sum())
            st.metric("Calories", f"{cal} kcal", delta=f"{cal - GOAL_CALORIES} vs Goal")
        else:
            st.metric("Calories", "Not logged")

    st.divider()

    # Section C — Nutrition Detail Card (pure HTML)
    if not nut_today.empty:
        prot_total = int(nut_today['protein_g'].sum())
        carb_total = int(nut_today['carbs_g'].sum())
        fat_total  = int(nut_today['fat_g'].sum())

        GOAL_CARBS = profile.get("goal_carbs_g") or 300
        GOAL_FAT   = profile.get("goal_fat_g") or 70

        def _delta_html(val, goal, unit="g"):
            diff = val - goal
            color = "#C8F135" if diff >= 0 else "#F13568"
            sign  = "+" if diff >= 0 else ""
            return f'<span style="font-size:11px;color:{color};">{sign}{diff}{unit}</span>'

        default_sups = profile.get("default_supplements") or []
        pills_html = ""
        if default_sups:
            pills_html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:14px;padding-top:14px;border-top:0.5px solid rgba(255,255,255,0.07);">'
            for sup_key in default_sups:
                if sup_key in SUPPLEMENT_MAP:
                    display, _, db_col = SUPPLEMENT_MAP[sup_key]
                    taken = bool(nut_today[db_col].any()) if db_col in nut_today.columns else False
                    if taken:
                        pills_html += f'<div style="background:rgba(200,241,53,0.08);border:0.5px solid rgba(200,241,53,0.2);color:#C8F135;padding:4px 12px;border-radius:20px;font-size:11px;font-family:Inter, sans-serif;font-weight:500;">{display}</div>'
                    else:
                        pills_html += f'<div style="background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.07);color:#444440;padding:4px 12px;border-radius:20px;font-size:11px;font-family:Inter, sans-serif;font-weight:500;">{display}</div>'
            pills_html += '</div>'

        st.markdown(f"""
        <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);
        border-radius:12px;padding:16px 20px;margin-bottom:12px;">
            <div style="font-family:Inter, sans-serif;font-size:12px;font-weight:700;color:#444440;
            letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px;">Today's Nutrition</div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
                <div style="background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.06);
                border-radius:8px;padding:12px 14px;">
                    <div style="font-size:10px;color:#888880;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:6px;font-family:Inter, sans-serif;">Protein</div>
                    <div style="font-family:Inter, sans-serif;font-size:22px;font-weight:800;
                    color:#F0EFE8;letter-spacing:-0.03em;">{prot_total}<span style="font-size:13px;
                    color:#888880;font-weight:400;">g</span></div>
                    <div style="margin-top:4px;">{_delta_html(prot_total, GOAL_PROTEIN)}</div>
                </div>
                <div style="background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.06);
                border-radius:8px;padding:12px 14px;">
                    <div style="font-size:10px;color:#888880;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:6px;font-family:Inter, sans-serif;">Carbs</div>
                    <div style="font-family:Inter, sans-serif;font-size:22px;font-weight:800;
                    color:#F0EFE8;letter-spacing:-0.03em;">{carb_total}<span style="font-size:13px;
                    color:#888880;font-weight:400;">g</span></div>
                    <div style="margin-top:4px;">{_delta_html(carb_total, GOAL_CARBS)}</div>
                </div>
                <div style="background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.06);
                border-radius:8px;padding:12px 14px;">
                    <div style="font-size:10px;color:#888880;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:6px;font-family:Inter, sans-serif;">Fat</div>
                    <div style="font-family:Inter, sans-serif;font-size:22px;font-weight:800;
                    color:#F0EFE8;letter-spacing:-0.03em;">{fat_total}<span style="font-size:13px;
                    color:#888880;font-weight:400;">g</span></div>
                    <div style="margin-top:4px;">{_delta_html(fat_total, GOAL_FAT)}</div>
                </div>
            </div>
            {pills_html}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No nutrition logged today.")

    # Section D — Training Detail Card
    render_today_training_summary()

    # Section E — Movement Detail Card (pure HTML)
    if not run_today.empty:
        last_run = run_today.iloc[-1]
        dist = last_run['distance']
        dur   = last_run['duration']
        pace = last_run['pace']
        hr   = last_run['hr']
        cat   = last_run.get('category', '')

        cell_style = "background:#1A1A1F;border:0.5px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 14px;"
        label_style = "font-size:10px;color:#888880;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;font-family:Inter, sans-serif;"
        value_style = "font-family:Inter, sans-serif;font-size:20px;font-weight:800;color:#F0EFE8;letter-spacing:-0.03em;"

        # สร้างป้ายแคปซูลสำหรับ Zone (ซ่อนอัตโนมัติถ้าไม่มีข้อมูล category)
        zone_badge_html = f'<div style="background:rgba(200,241,53,0.08);border:0.5px solid rgba(200,241,53,0.2);color:#C8F135;padding:3px 12px;border-radius:20px;font-size:11px;font-family:Inter, sans-serif;font-weight:500; letter-spacing: 0.02em;">{cat}</div>' if cat else ''

        st.markdown(f"""
        <div style="background:#141417;border:0.5px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px 20px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
                <div style="font-family:Inter, sans-serif;font-size:12px;font-weight:700;color:#444440;letter-spacing:0.12em;text-transform:uppercase;">Today's Movement</div>
                {zone_badge_html}
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
                <div style="{cell_style}"><div style="{label_style}">Distance</div><div style="{value_style}">{dist} km</div></div>
                <div style="{cell_style}"><div style="{label_style}">Duration</div><div style="{value_style}">{dur}</div></div>
                <div style="{cell_style}"><div style="{label_style}">Pace</div><div style="{value_style}">{pace} /km</div></div>
                <div style="{cell_style}"><div style="{label_style}">Avg HR</div><div style="{value_style}">{hr} bpm</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Section F — Progressive Overload Alert
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:18px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Progressive Overload Tracking</div>', unsafe_allow_html=True)
    all_workouts_data = fetch_workouts_cached(db)
    if all_workouts_data:
        df_vol = pd.DataFrame(all_workouts_data)
        df_vol['log_ts'] = pd.to_datetime(df_vol['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
        
        # ใช้ลอจิก Rolling 7 วันเพื่อแก้ปัญหาจำนวนวันไม่เท่ากัน
        _bkk = pytz.timezone("Asia/Bangkok")
        today = datetime.now(_bkk).date()
        
        # ช่วงที่ 1: 7 วันล่าสุด (นับรวมวันนี้ย้อนไปทั้งหมด 7 วัน)
        start_current = today - timedelta(days=6)
        df_current_7 = df_vol[(df_vol['log_ts'].dt.date >= start_current) & (df_vol['log_ts'].dt.date <= today)]
        curr_vol = df_current_7['volume'].sum()
        
        # ช่วงที่ 2: 7 วันก่อนหน้า (ถัดย้อนหลังไปอีก 7 วัน)
        start_prev = today - timedelta(days=13)
        end_prev = today - timedelta(days=7)
        df_prev_7 = df_vol[(df_vol['log_ts'].dt.date >= start_prev) & (df_vol['log_ts'].dt.date <= end_prev)]
        prev_vol = df_prev_7['volume'].sum()
        
        if prev_vol > 0:
            diff_pct = ((curr_vol - prev_vol) / prev_vol) * 100
            if curr_vol >= prev_vol:
                st.markdown(f"""
                <div style="padding:10px 16px;background:rgba(200,241,53,0.06);border:0.5px solid rgba(200,241,53,0.2);border-radius:8px;display:flex;align-items:center;gap:10px;margin:8px 0;">
                  <div style="width:8px;height:8px;border-radius:50%;background:#C8F135;flex-shrink:0;"></div>
                  <span style="font-size:13px;color:#F0EFE8;font-family:Inter, sans-serif;">Volume up <strong style="color:#C8F135;">{diff_pct:.1f}%</strong> vs previous 7 days</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="padding:10px 16px;background:rgba(241,53,104,0.06);border:0.5px solid rgba(241,53,104,0.2);border-radius:8px;display:flex;align-items:center;gap:10px;margin:8px 0;">
                  <div style="width:8px;height:8px;border-radius:50%;background:#F13568;flex-shrink:0;"></div>
                  <span style="font-size:13px;color:#F0EFE8;font-family:Inter, sans-serif;">Volume down <strong style="color:#F13568;">{abs(diff_pct):.1f}%</strong> vs previous 7 days</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Comparison not possible (previous week volume was 0).")
    else:
        st.info("Log training sessions to see overload trends.")
    
   # Section G — Trend Charts
    with st.spinner("Generating volume chart..."):
        all_workouts = fetch_workouts_cached(db)
        df_wrk_all = pd.DataFrame(all_workouts)

        if not df_wrk_all.empty:
            df_wrk_plot = df_wrk_all.rename(columns={'log_ts': 'Date', 'volume': 'Volume'})
            df_wrk_plot = safe_numeric(df_wrk_plot, ['Volume'])
            
            # 1. แปลงคอลัมน์ Date ให้เหลือแค่วันที่ (ลบข้อมูลเวลาออกชั่วคราวเพื่อใช้จัดกลุ่ม)
            df_wrk_plot['Date'] = pd.to_datetime(df_wrk_plot['Date'], format='ISO8601', errors='coerce').dt.date
            
            # 2. Groupby ตามวันที่ แล้วทำการ Sum รวม Volume ของทุกท่าในวันเดียวกัน
            df_wrk_plot = df_wrk_plot.groupby('Date', as_index=False)['Volume'].sum()
            
            # 3. เรียงลำดับจากอดีตไปปัจจุบันเพื่อความถูกต้องในการลากเส้นกราฟ
            df_wrk_plot = df_wrk_plot.sort_values('Date')
        else:
            df_wrk_plot = pd.DataFrame()

    # แสดงผลกราฟแบบเต็มความกว้าง (ลบ st.columns ออกเพื่อให้กราฟขยายเต็มตา ดูง่ายขึ้น)
    render_chart_safely(
        df_wrk_plot, 
        'Date', 
        'Volume', 
        "Weekly Training Volume", 
        primary_color='#C8F135', 
        key="volume_trend_overview"
    )

    st.divider()
    render_export_section()

@st.fragment
def render_data_manager():
    db = get_db()
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:26px;font-weight:800;color:#F0EFE8;letter-spacing:-0.04em;margin-bottom:4px;">Data Manager</div>', unsafe_allow_html=True)
    st.caption("Review and delete individual entries across all logs.")

    # Workout Entries
    with st.expander("Workout Entries", expanded=False):
        df = pd.DataFrame(fetch_workouts_cached(db))
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
            display_cols = ['log_ts', 'exercise', 'weight', 'reps', 'rpe', 'volume']
            df_display = df[[c for c in display_cols if c in df.columns]].copy()

            event = st.dataframe(
                df_display.sort_values('log_ts', ascending=False).reset_index(drop=True),
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="select_workout"
            )

            selected_rows = event.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                df_full_sorted = df.sort_values('log_ts', ascending=False).reset_index(drop=True)
                selected_entry = df_full_sorted.iloc[selected_idx]
                
                st.markdown(f"""
                <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:Inter, sans-serif;">
                Delete **{selected_entry['exercise']}** logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?</div>""", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 6])
                st.markdown('<style>[key="confirm_del_workout"] button {background:#F13568 !important;color:#fff !important;border:none !important;}</style>', unsafe_allow_html=True)
                if col1.button("Confirm Delete", key="confirm_del_workout"):
                    db.delete_workout_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_workout"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 2. Movement Entries
    with st.expander("Movement Entries", expanded=False):
        df = pd.DataFrame(fetch_runs_cached(db))
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
            df_display = df[['log_ts', 'category', 'distance', 'duration', 'pace', 'hr']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="select_run"
            )

            selected_rows = event.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                df_full_sorted = df.sort_values('log_ts', ascending=False).reset_index(drop=True)
                selected_entry = df_full_sorted.iloc[selected_idx]
                
                st.markdown(f"""
                <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:Inter, sans-serif;">
                Delete **{selected_entry['category']} {selected_entry['distance']}km** logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?</div>""", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 6])
                st.markdown('<style>[key="confirm_del_run"] button {background:#F13568 !important;color:#fff !important;border:none !important;}</style>', unsafe_allow_html=True)
                if col1.button("Confirm Delete", key="confirm_del_run"):
                    db.delete_run_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_run"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 3. Nutrition Entries
    with st.expander("Nutrition Entries", expanded=False):
        df = pd.DataFrame(fetch_nutrition_cached(db))
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
            display_cols = ['log_ts', 'food_name', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'meal_score']
            available = [c for c in display_cols if c in df.columns]
            df_display = df[available].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="select_nutrition"
            )

            selected_rows = event.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                df_full_sorted = df.sort_values('log_ts', ascending=False).reset_index(drop=True)
                selected_entry = df_full_sorted.iloc[selected_idx]
                
                st.markdown(f"""
                <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:Inter, sans-serif;">
                Delete entry of **{selected_entry['calories']} kcal** logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?</div>""", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 6])
                st.markdown('<style>[key="confirm_del_nutrition"] button {background:#F13568 !important;color:#fff !important;border:none !important;}</style>', unsafe_allow_html=True)
                if col1.button("Confirm Delete", key="confirm_del_nutrition"):
                    db.delete_nutrition_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_nutrition"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 4. Weight Entries
    with st.expander("Weight Entries", expanded=False):
        df = pd.DataFrame(fetch_weight_cached(db))
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
            df_display = df[['log_ts', 'weight', 'notes']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="select_weight"
            )

            selected_rows = event.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                df_full_sorted = df.sort_values('log_ts', ascending=False).reset_index(drop=True)
                selected_entry = df_full_sorted.iloc[selected_idx]
                
                st.markdown(f"""
                <div style="background:rgba(241,53,104,0.08);border:0.5px solid rgba(241,53,104,0.2);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px;color:#F13568;font-family:Inter, sans-serif;">
                Delete weight entry of **{selected_entry['weight']} kg** logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?</div>""", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 6])
                st.markdown('<style>[key="confirm_del_weight"] button {background:#F13568 !important;color:#fff !important;border:none !important;}</style>', unsafe_allow_html=True)
                if col1.button("Confirm Delete", key="confirm_del_weight"):
                    db.delete_weight_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_weight"):
                    st.rerun()
        else:
            st.info("No entries found.")

def render_export_section():
    db = get_db()
    st.markdown('<div style="font-family:Inter, sans-serif;font-size:22px;font-weight:700;color:#F0EFE8;margin-bottom:12px;">Export Data</div>', unsafe_allow_html=True)

    # ปรับเป็น 4 คอลัมน์เพื่อเพิ่มพื้นที่ให้ปุ่ม Movement
    col1, col2, col3, col4 = st.columns(4)

    # 1. Workouts
    workouts = fetch_workouts_cached(db)
    if workouts:
        df = pd.DataFrame(workouts).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col1.download_button(
            "Workouts CSV",
            data=csv,
            file_name=f"workouts_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # 2. Nutrition
    nutrition = fetch_nutrition_cached(db)
    if nutrition:
        df = pd.DataFrame(nutrition).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col2.download_button(
            "Nutrition CSV",
            data=csv,
            file_name=f"nutrition_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # 3. Weight
    weight = fetch_weight_cached(db)
    if weight:
        df = pd.DataFrame(weight).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col3.download_button(
            "Weight CSV",
            data=csv,
            file_name=f"weight_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # 4. Movement / Runs (ส่วนที่เพิ่มเข้ามาใหม่)
    runs = fetch_runs_cached(db)
    if runs:
        df = pd.DataFrame(runs).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col4.download_button(
            "Movement CSV",
            data=csv,
            file_name=f"movement_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )