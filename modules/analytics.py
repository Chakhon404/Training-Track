import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import json
from datetime import datetime, timedelta
from modules.database import get_db, fetch_profile_cached, fetch_workouts_cached
from modules.constants import SUPPLEMENT_MAP

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
    plot_df[x] = pd.to_datetime(plot_df[x], format='ISO8601', errors='coerce')
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
    st.title("⚖️ Weight")
    db = get_db()
    profile = fetch_profile_cached(db) or {}
    GOAL_WEIGHT = profile.get("goal_weight_kg") or 64.0

    with st.spinner("Fetching data..."):
        weight_data = db.fetch_weight()
        df_weight = pd.DataFrame(weight_data)
        if not df_weight.empty:
            df_weight = df_weight.rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
            df_weight = safe_numeric(df_weight, ['Weight'])
            df_weight['body_fat_pct'] = pd.to_numeric(df_weight['body_fat_pct'], errors='coerce')
            df_weight['Date'] = pd.to_datetime(df_weight['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
            df_weight = df_weight.sort_values('Date')

    # 1. Metrics Row
    if not df_weight.empty:
        m1, m2, m3 = st.columns(3)
        latest = df_weight.iloc[-1]
        prev = df_weight.iloc[-2] if len(df_weight) > 1 else latest
        
        w_delta = float(latest['Weight']) - float(prev['Weight'])
        m1.metric("Latest Weight", f"{latest['Weight']:.1f} kg", delta=f"{w_delta:+.1f} kg", delta_color="inverse")
        
        bf_val = latest.get('body_fat_pct', 0)
        bf_prev = prev.get('body_fat_pct', 0)
        bf_delta = float(bf_val) - float(bf_prev)
        m2.metric("Body Fat", f"{bf_val:.1f}%", delta=f"{bf_delta:+.1f}%", delta_color="inverse")
        
        # Target Date Prediction
        pred = predict_target_date(df_weight, GOAL_WEIGHT)
        m3.metric("Predicted Target Date", pred)
        st.divider()

    # 2. Unified Logging Form
    st.subheader("Weight & Body Fat Log")
    with st.form("weight_form_unified"):
        c1, c2, c3 = st.columns(3)
        today_w = c1.number_input("Weight (kg)", min_value=30.0, step=0.1)
        today_bf = c2.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, value=float(profile.get('body_fat_pct') or 0.0))
        w_date = c3.date_input("Date", datetime.now().date())
        notes = st.text_input("Notes (optional)")
        if st.form_submit_button("💾 Save Stats", use_container_width=True):
            if db.check_duplicate_weight(str(w_date)) > 0:
                st.warning(f"⚠️ Duplicate entry already exists for {w_date}. Please use the Weight Log tab to overwrite.")
            else:
                if db.save_weight({
                    "log_ts": datetime.combine(w_date, datetime.now().time()).isoformat(),
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
        st.subheader("📈 Weight Trend")
        render_chart_safely(df_weight, 'Date', 'Weight', None)

    with chart_r:
        if not df_weight.empty and df_weight['body_fat_pct'].notna().any():
            st.subheader("📉 Body Fat % Trend")
            plot_bf_df = df_weight.dropna(subset=['body_fat_pct']).sort_values('Date')
            fig_bf = px.line(
                plot_bf_df,
                x='Date', y='body_fat_pct',
                labels={'Date': 'Date', 'body_fat_pct': 'Body Fat (%)'},
                color_discrete_sequence=['#F5A623']
            )
            fig_bf.update_traces(mode='lines+markers')
            st.plotly_chart(fig_bf, width='stretch')
        else:
            st.info("Log body fat to see the trend chart.")

def render_nutrition_analysis():
    st.subheader("🥦 Nutrition & Energy")
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
    
    # Date processing with TZ strip
    df_nut['Date_dt'] = pd.to_datetime(df_nut['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
    df_nut = safe_numeric(df_nut, ['Calories (kcal)', 'Protein (g)', 'Carbs (g)', 'Fat (g)'])
    today_str = datetime.now().date()
    df_nut['Date_date'] = df_nut['Date_dt'].dt.date
    df_today = df_nut[df_nut['Date_date'] == today_str]

    if df_today.empty:
        st.info("🍱 Nutrition information for today is not yet available.")
        return
    latest = df_nut.iloc[-1]
    
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, goal) in zip([c1, c2, c3, c4], GOALS.items()):
        key = 'Calories (kcal)' if label == "Calories" else f"{label} (g)"
        val = float(latest.get(key, 0))
        diff = val - goal
        color = "inverse" if label == "Calories" and diff > 0 else "normal"
        col.metric(label, f"{val:.0f}/{goal}", delta=f"{diff:.0f}", delta_color=color)

    st.divider()
    
    # Dynamic Supplement Status based on Profile Defaults
    st.markdown("### Supplements")
    default_sups = profile.get("default_supplements") or []
    if not default_sups:
        st.info("💡 No supplements configured in profile. Go to ⚙️ System → 👤 Edit Profile & Goals to add them.")
    else:
        cols_per_row = 4
        for i in range(0, len(default_sups), cols_per_row):
            row_keys = default_sups[i:i + cols_per_row]
            cols = st.columns(len(row_keys))
            for col, sup_key in zip(cols, row_keys):
                if sup_key in SUPPLEMENT_MAP:
                    display, _, db_col = SUPPLEMENT_MAP[sup_key]
                    status = "✅" if latest.get(db_col) else "❌"
                    col.markdown(f"**{display}**: {status}")

    st.divider()
    st.markdown("### Daily Progress (%)")
    pct_data = []
    for label, goal in GOALS.items():
        key = 'Calories (kcal)' if label == "Calories" else f"{label} (g)"
        val = float(latest.get(key, 0))
        pct = min(100, (val / goal * 100)) if goal > 0 else 0
        pct_data.append({"Macro": label, "Percentage": pct})
    
    st.bar_chart(pd.DataFrame(pct_data).set_index("Macro"), horizontal=True)

    # Section: Meal Score Trend
    if 'meal_score' in df_nut.columns and df_nut['meal_score'].notna().any():
        st.divider()
        st.subheader("⭐ Meal Score Trend")
        # Ensure we drop NaNs for the chart and sort by Date
        plot_ms_df = df_nut.dropna(subset=['meal_score']).copy()
        plot_ms_df['Date_plot'] = pd.to_datetime(plot_ms_df['Date'], format='ISO8601', utc=True).dt.tz_convert(None)
        plot_ms_df = plot_ms_df.sort_values('Date_plot')
        fig_ms = px.line(
            plot_ms_df,
            x='Date_plot', y='meal_score',
            labels={'Date_plot': 'Date', 'meal_score': 'Meal Score'},
            color_discrete_sequence=['#F5A623']
        )
        fig_ms.update_yaxes(range=[0, 10.5]) # Score is 1-10, give some breathing room
        fig_ms.add_hline(y=7, line_dash="dash", line_color="gray", annotation_text="Good")
        st.plotly_chart(fig_ms, width='stretch')

    st.divider()
    st.subheader("💊 Supplement Compliance (last 30 days)")

    sup_db_cols = [db_col for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items()]
    sup_display_names = {db_col: display for json_key, (display, sess_key, db_col) in SUPPLEMENT_MAP.items()}

    available_cols = [c for c in sup_db_cols if c in df_nut.columns]
    if available_cols:
        compliance = {}
        for col in available_cols:
            # fillna(False) because missing in DB means not taken
            pct = df_nut[col].fillna(False).astype(bool).mean() * 100
            compliance[sup_display_names.get(col, col)] = round(pct, 1)

        df_comp = pd.DataFrame(
            list(compliance.items()),
            columns=["Supplement", "Compliance (%)"]
        ).sort_values("Compliance (%)", ascending=True)

        fig_comp = px.bar(
            df_comp,
            x="Compliance (%)", y="Supplement",
            orientation="h",
            color="Compliance (%)",
            color_continuous_scale=["#D85A30", "#F5A623", "#5DCAA5"],
            range_color=[0, 100],
            labels={"Compliance (%)": "Days taken (%)"}
        )
        fig_comp.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_comp, width='stretch')
    else:
        st.info("No supplement data yet.")

def render_overview():
    db = get_db()
    today = datetime.now().date()
    profile = fetch_profile_cached(db) or {}
    GOAL_CALORIES = profile.get("goal_calories") or 2500
    GOAL_PROTEIN = profile.get("goal_protein_g") or 150
    GOAL_WEIGHT = profile.get("goal_weight_kg") or None
    
    with st.spinner("Loading Today's Summary..."):
        work_today_raw = db.fetch_workouts_by_date(str(today))
        run_today_raw = db.fetch_runs_by_date(str(today))
        nut_today_raw = db.fetch_nutrition_by_date(str(today))
        weight_today_raw = db.fetch_weight_by_date(str(today))

        df_work = pd.DataFrame(work_today_raw)
        df_run = pd.DataFrame(run_today_raw)
        df_nut = pd.DataFrame(nut_today_raw)
        df_weight = pd.DataFrame(weight_today_raw)

        # Re-map legacy variable names to the new DataFrames for compatibility
        work_today = df_work
        run_today = df_run
        nut_today = df_nut
        weight_today = df_weight

    # Fetch latest wellness for Readiness
    wellness = db.fetch_wellness(days=1)
    tr_score = None
    if wellness:
        tr_score = wellness[0].get("training_readiness")

    # Section A — Header
    st.header("🏠 Daily Overview")
    st.caption(f"Today: {today.strftime('%A, %d %B %Y')}")

    if profile:
        with st.container(border=True):
            st.markdown("### 👤 Profile Summary")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("Weight", f"{profile.get('weight_kg', 'N/A')} kg")
            pc2.metric("Height", f"{profile.get('height_cm', 'N/A')} cm")
            pc3.metric("Body Fat", f"{profile.get('body_fat_pct', 'N/A')}%")
            
            goal_w = profile.get('goal_weight_kg')
            curr_w = profile.get('weight_kg')
            if goal_w and curr_w:
                diff = round(curr_w - goal_w, 1)
                pc4.metric("To Goal", f"{abs(diff)} kg", delta=f"{-diff:+.1f} kg")
            else:
                pc4.metric("To Goal", "N/A")
                
            if profile.get("supplements"):
                st.caption("💊 " + " · ".join(profile["supplements"]))

    # Section B — Activity Status Row
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        if not work_today.empty:
            count = work_today['exercise'].nunique()
            vol = work_today['volume'].sum()
            st.metric("🏋️ Training", f"{count} exercises", delta=f"{vol:,.0f} kg volume")
        else:
            st.metric("🏋️ Training", "Rest day")

    with c2:
        if not run_today.empty:
            dist = run_today['distance'].sum()
            cat = run_today.iloc[-1]['category']
            st.metric("🏃 Movement", f"{dist:.1f} km", delta=cat)
        else:
            st.metric("🏃 Movement", "Rest day")

    with c3:
        st.metric(
            "💪 Readiness",
            f"{tr_score}/100" if tr_score else "N/A",
            help="Garmin Training Readiness score"
        )

    with c4:
        if not weight_today.empty:
            w = weight_today.iloc[-1]['weight']
            st.metric("⚖️ Weight", f"{w} kg")
        else:
            st.metric("⚖️ Weight", "Not logged")

    with c5:
        if not nut_today.empty:
            cal = int(nut_today.iloc[-1]['calories'])
            st.metric("🍱 Calories", f"{cal} kcal", delta=f"{cal - GOAL_CALORIES} vs Goal")
        else:
            st.metric("🍱 Calories", "Not logged")

    st.divider()

    # Section C — Nutrition Detail Card
    if not nut_today.empty:
        with st.container(border=True):
            st.markdown("### 🍱 Today's Nutrition")
            latest_nut = nut_today.iloc[-1]
            
            m1, m2, m3 = st.columns(3)
            with m1:
                p = int(latest_nut.get('protein_g', 0))
                st.metric("Protein", f"{p}g", delta=f"{p - GOAL_PROTEIN}g vs Goal")
            with m2:
                st.metric("Carbs", f"{int(latest_nut.get('carbs_g', 0))}g")
            with m3:
                st.metric("Fat", f"{int(latest_nut.get('fat_g', 0))}g")
            st.divider()
            
            # Dynamic Supplement Status based on Profile Defaults
            st.markdown("#### 💊 Supplements")
            default_sups = profile.get("default_supplements") or []
            if not default_sups:
                st.caption("No supplements configured in profile.")
            else:
                cols_per_row = 4
                for i in range(0, len(default_sups), cols_per_row):
                    row_keys = default_sups[i:i + cols_per_row]
                    cols = st.columns(len(row_keys))
                    for col, sup_key in zip(cols, row_keys):
                        if sup_key in SUPPLEMENT_MAP:
                            display, _, db_col = SUPPLEMENT_MAP[sup_key]
                            status = "✅" if latest_nut.get(db_col) else "❌"
                            col.markdown(f"**{display}**: {status}")
    else:
        st.info("🍱 No nutrition logged today.")

    # Section D — Training Detail Card
    if not work_today.empty:
        with st.container(border=True):
            st.markdown("### 🏋️ Today's Training")
            st.dataframe(
                work_today[['exercise', 'weight', 'sets', 'reps', 'volume', 'rpe']], 
                hide_index=True,
                width='stretch'
            )
    else:
        st.info("🏋️ No training logged today.")

    # Section E — Movement Detail Card
    if not run_today.empty:
        with st.container(border=True):
            st.markdown("### 🏃 Today's Movement")
            # Show latest run details
            last_run = run_today.iloc[-1]
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Distance", f"{last_run['distance']} km")
            r2.metric("Duration", f"{last_run['duration']}")
            r3.metric("Pace", f"{last_run['pace']} /km")
            r4.metric("Avg HR", f"{last_run['hr']} bpm")
    else:
        st.info("🏃 No movement logged today.")

    st.divider()

    # Section F — Progressive Overload Alert
    st.subheader("📈 Progressive Overload Tracking")
    vol_data = db.fetch_weekly_volume()
    if vol_data:
        df_vol = pd.DataFrame(vol_data)
        df_vol['log_ts'] = pd.to_datetime(df_vol['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
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
    
    # Section G — Trend Charts
    l, r = st.columns(2)
    with st.spinner("Generating charts..."):
        all_workouts = fetch_workouts_cached(db)
        all_weights  = db.fetch_weight()
        df_wrk_all = pd.DataFrame(all_workouts)
        df_w_all   = pd.DataFrame(all_weights)

        df_w_plot = df_w_all.rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
        df_w_plot = safe_numeric(df_w_plot, ['Weight'])
        
        df_wrk_plot = df_wrk_all.rename(columns={'log_ts': 'Date', 'volume': 'Volume'})
        df_wrk_plot = safe_numeric(df_wrk_plot, ['Volume'])

    with l:
        render_chart_safely(df_wrk_plot, 'Date', 'Volume', "Weekly Training Volume")
    with r:
        render_chart_safely(df_w_plot, 'Date', 'Weight', "Weight Progression")

    st.divider()
    render_export_section()

def render_data_manager():
    db = get_db()
    st.header("🗂️ Data Manager")
    st.caption("Review and delete individual entries across all logs.")

    # Workout Entries
    with st.expander("🏋️ Workout Entries", expanded=False):
        df = pd.DataFrame(db.fetch_workouts())
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
            display_cols = ['log_ts', 'exercise', 'set_number', 'weight', 'reps', 'rpe', 'volume']
            df_display = df[[c for c in display_cols if c in df.columns]].copy()
            st.dataframe(df_display.sort_values('log_ts', ascending=False), hide_index=True, width='stretch')


            event = st.dataframe(
                df_display,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="select_workout"
            )

            selected_rows = event.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                # Re-sort full df to match display order if needed, but display is already sorted and reset
                # So we sort full df the same way to ensure iloc matches
                df_full_sorted = df.sort_values('log_ts', ascending=False).reset_index(drop=True)
                selected_entry = df_full_sorted.iloc[selected_idx]
                
                st.warning(
                    f"Delete **{selected_entry['exercise']}** "
                    f"logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?"
                )
                col1, col2 = st.columns([1, 6])
                if col1.button("🗑️ Confirm Delete", key="confirm_del_workout", type="primary"):
                    db.delete_workout_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_workout"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 2. Movement Entries
    with st.expander("🏃 Movement Entries", expanded=False):
        df = pd.DataFrame(db.fetch_runs())
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
                
                st.warning(
                    f"Delete **{selected_entry['category']} {selected_entry['distance']}km** "
                    f"logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?"
                )
                col1, col2 = st.columns([1, 6])
                if col1.button("🗑️ Confirm Delete", key="confirm_del_run", type="primary"):
                    db.delete_run_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_run"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 3. Nutrition Entries
    with st.expander("🍱 Nutrition Entries", expanded=False):
        df = pd.DataFrame(db.fetch_nutrition())
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
                
                st.warning(
                    f"Delete entry of **{selected_entry['calories']} kcal** "
                    f"logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?"
                )
                col1, col2 = st.columns([1, 6])
                if col1.button("🗑️ Confirm Delete", key="confirm_del_nutrition", type="primary"):
                    db.delete_nutrition_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_nutrition"):
                    st.rerun()
        else:
            st.info("No entries found.")

    # 4. Weight Entries
    with st.expander("⚖️ Weight Entries", expanded=False):
        df = pd.DataFrame(db.fetch_weight())
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
                
                st.warning(
                    f"Delete weight entry of **{selected_entry['weight']} kg** "
                    f"logged on {selected_entry['log_ts'].strftime('%Y-%m-%d %H:%M')}?"
                )
                col1, col2 = st.columns([1, 6])
                if col1.button("🗑️ Confirm Delete", key="confirm_del_weight", type="primary"):
                    db.delete_weight_by_id(str(selected_entry['id']))
                    st.success("Entry deleted.")
                    st.rerun()
                if col2.button("Cancel", key="cancel_del_weight"):
                    st.rerun()
        else:
            st.info("No entries found.")

def render_export_section():
    db = get_db()
    st.subheader("📥 Export Data")

    col1, col2, col3 = st.columns(3)

    # Workouts
    workouts = db.fetch_workouts()
    if workouts:
        df = pd.DataFrame(workouts).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col1.download_button(
            "⬇️ Workouts CSV",
            data=csv,
            file_name=f"workouts_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width='stretch'
        )

    # Nutrition
    nutrition = db.fetch_nutrition()
    if nutrition:
        df = pd.DataFrame(nutrition).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col2.download_button(
            "⬇️ Nutrition CSV",
            data=csv,
            file_name=f"nutrition_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width='stretch'
        )

    # Weight
    weight = db.fetch_weight()
    if weight:
        df = pd.DataFrame(weight).drop(columns=["id"], errors="ignore")
        csv = df.to_csv(index=False).encode("utf-8")
        col3.download_button(
            "⬇️ Weight CSV",
            data=csv,
            file_name=f"weight_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width='stretch'
        )

def render_wellness():
    db = get_db()
    st.header("🔋 Wellness & Recovery")
    
    # --- MANUAL ENTRY FORM ---
    with st.expander("📝 Log Daily Wellness", expanded=True):
        with st.form("wellness_manual_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            log_date = col1.date_input("Log Date", value=datetime.now().date())
            resting_hr = col2.number_input("Resting Heart Rate (bpm)", min_value=30, max_value=150, value=55, step=1)

            st.markdown("---")
            st.markdown("### 😴 Sleep Session")
            t1, t2 = st.columns(2)
            sleep_start_time = t1.time_input("Sleep Start Time", value=datetime.strptime("22:00", "%H:%M").time())
            sleep_end_time = t2.time_input("Sleep End Time", value=datetime.strptime("06:00", "%H:%M").time())
            
            sleep_score = st.select_slider("Sleep Quality Score", options=list(range(101)), value=80)

            st.markdown("---")
            st.markdown("### 📊 Daily Readiness Metrics")
            m1, m2, m3 = st.columns(3)
            with m1:
                stress_avg = st.select_slider("Avg Stress", options=list(range(101)), value=25)
            with m2:
                training_readiness = st.select_slider("Training Readiness", options=list(range(101)), value=80)
            with m3:
                body_battery_start = st.select_slider("Body Battery (Start)", options=list(range(101)), value=90)

            body_battery_end = st.select_slider("Body Battery (End of Day)", options=list(range(101)), value=50)

            if st.form_submit_button("💾 Save Wellness Data"):
                try:
                    # Logic for Cross-Midnight Calculation
                    # We assume sleep_start is on (log_date - 1 day) if it's late night, 
                    # but for simplicity, we treat log_date as the 'waking up' date.
                    # Start is usually night before, End is morning of log_date.
                    
                    start_dt = datetime.combine(log_date - timedelta(days=1), sleep_start_time)
                    end_dt = datetime.combine(log_date, sleep_end_time)
                    
                    # If end_dt is still before or equal to start_dt, adjust (e.g., sleeping after midnight)
                    if end_dt <= start_dt:
                        # Case: user slept at 1 AM and woke up at 8 AM on the same log_date
                        start_dt = datetime.combine(log_date, sleep_start_time)
                        if end_dt <= start_dt:
                             # This should technically not happen if they sleep and wake on same day 
                             # unless it's a very short nap or error.
                             pass

                    duration_min = int((end_dt - start_dt).total_seconds() / 60)

                    # Validation
                    if duration_min <= 0:
                        st.error("❌ Invalid sleep duration. Please check your start and end times.")
                    else:
                        payload = {
                            "log_date": str(log_date),
                            "sleep_start": start_dt.isoformat(),
                            "sleep_end": end_dt.isoformat(),
                            "sleep_duration_min": duration_min,
                            "sleep_score": int(sleep_score),
                            "resting_hr": int(resting_hr),
                            "stress_avg": int(stress_avg),
                            "body_battery_start": int(body_battery_start),
                            "body_battery_end": int(body_battery_end),
                            "training_readiness": int(training_readiness)
                        }
                        
                        if db.save_wellness(payload):
                            st.success(f"✅ Wellness data for {log_date} saved successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Database Error: Could not save wellness entry.")
                            
                except Exception as e:
                    st.error(f"⚠️ Error processing data: {str(e)}")

    st.divider()

    wellness = db.fetch_wellness(days=30)
    if not wellness:
        st.info("No wellness data yet. Start by logging your data above.")
        return

    df = pd.DataFrame(wellness)
    df['log_date'] = pd.to_datetime(df['log_date'], format='ISO8601')
    df = df.sort_values('log_date')

    # Section A — Today's snapshot
    latest = df.iloc[-1]
    st.subheader("📊 Latest Snapshot")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sleep Score", f"{int(latest['sleep_score']) if pd.notna(latest['sleep_score']) else 'N/A'}")
    c2.metric("Resting HR", f"{int(latest['resting_hr']) if pd.notna(latest['resting_hr']) else 'N/A'} bpm")
    c3.metric("Avg Stress", f"{int(latest['stress_avg']) if pd.notna(latest['stress_avg']) else 'N/A'}")
    c4.metric("Body Battery",
        f"{int(latest['body_battery_start']) if pd.notna(latest['body_battery_start']) else 'N/A'}"
    )
    c5.metric(
        "Training Readiness",
        f"{int(latest['training_readiness']) if pd.notna(latest.get('training_readiness')) else 'N/A'}"
    )

    # --- AI COACH & JSON IMPORT ---
    st.divider()
    st.subheader("🤖 AI Coach & Data Import")
    
    c_coach, c_import = st.columns(2)
    
    with c_coach:
        st.markdown("#### 🔔 Manual Reminder")
        if st.button("🔔 Test AI Coach (Send to LINE)"):
            import subprocess
            try:
                # Use st.secrets to populate environment for the sub-process
                env = os.environ.copy()
                for key, val in st.secrets.items():
                    env[key] = str(val)
                
                result = subprocess.run(["python", "daily_reminder.py"], env=env, capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("✅ AI Coach reminder triggered! Check LINE.")
                    st.info(f"Coach output: {result.stdout}")
                else:
                    st.error(f"❌ Failed: {result.stderr}")
            except Exception as e:
                st.error(f"⚠️ Error: {str(e)}")

    with c_import:
        st.markdown("#### 📥 JSON Quick Import")
        with st.expander("Paste Daily Summary JSON"):
            json_text = st.text_area("Paste Gemini JSON here", height=150, key="wellness_json_import")
            if st.button("💾 Import Nutrition Data", key="btn_import_nut"):
                if json_text.strip():
                    try:
                        data = json.loads(json_text)
                        log_date = data.get("log_date", datetime.now().strftime("%Y-%m-%d"))
                        
                        # Prepare payload for upsert
                        nut_payload = {
                            "log_ts": f"{log_date} {data.get('log_time', '12:00:00')}",
                            "calories": int(data.get("energy_macros", {}).get("calories", 0)),
                            "protein_g": int(data.get("energy_macros", {}).get("protein_g", 0)),
                            "carbs_g": int(data.get("energy_macros", {}).get("carbs_g", 0)),
                            "fat_g": int(data.get("energy_macros", {}).get("fat_g", 0)),
                            "meal_score": data.get("meal_score"),
                            "food_name": data.get("food_name", "Gemini Daily Summary")
                        }
                        
                        # Map supplements from JSON to DB columns
                        sups = data.get("supplements", {})
                        for k, v in sups.items():
                            # Use SUPPLEMENT_MAP to map JSON keys to DB columns
                            if k in SUPPLEMENT_MAP:
                                db_key = SUPPLEMENT_MAP[k][2]
                            else:
                                db_key = k
                            nut_payload[db_key] = bool(v)
                            
                        # Perform Update/Insert manually without log_date column
                        nut_payload.pop("log_date", None)

                        # Check if entry already exists for this date (by log_ts date prefix)
                        existing = db.supabase.table("nutrition")\
                            .select("id")\
                            .gte("log_ts", f"{log_date}T00:00:00")\
                            .lte("log_ts", f"{log_date}T23:59:59")\
                            .execute()

                        if existing.data:
                            # Update existing entry
                            entry_id = existing.data[0]["id"]
                            res = db.supabase.table("nutrition")\
                                .update(nut_payload)\
                                .eq("id", entry_id)\
                                .execute()
                        else:
                            # Insert new entry
                            res = db.supabase.table("nutrition")\
                                .insert(nut_payload)\
                                .execute()

                        if res.data:
                            st.success(f"✅ Data imported/updated for {log_date}")
                            st.rerun()
                        else:
                            st.error("❌ Import failed. Check Supabase logs.")
                            
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

    st.divider()
    # Section B — Sleep duration bar
    if 'sleep_duration_min' in df.columns:
        st.subheader("😴 Sleep Duration (last 30 days)")
        df['sleep_hours'] = df['sleep_duration_min'] / 60
        fig_sleep = px.bar(
            df, x='log_date', y='sleep_hours',
            labels={'log_date': 'Date', 'sleep_hours': 'Hours'},
            color_discrete_sequence=['#5DCAA5']
        )
        fig_sleep.add_hline(y=8, line_dash="dash", line_color="gray", annotation_text="8hr goal")
        fig_sleep.update_layout(showlegend=False)
        st.plotly_chart(fig_sleep, width='stretch')

    # Section C — RHR trend
    st.subheader("❤️ Resting Heart Rate Trend")
    fig_rhr = px.line(
        df.dropna(subset=['resting_hr']),
        x='log_date', y='resting_hr',
        labels={'log_date': 'Date', 'resting_hr': 'RHR (bpm)'},
        color_discrete_sequence=['#D85A30']
    )
    st.plotly_chart(fig_rhr, width='stretch')

    # Section D — Body Battery
    st.subheader("🔋 Body Battery")
    fig_bb = px.line(
        df.dropna(subset=['body_battery_end']),
        x='log_date', y='body_battery_end',
        labels={'log_date': 'Date', 'body_battery_end': 'Body Battery (end of day)'},
        color_discrete_sequence=['#378ADD']
    )
    st.plotly_chart(fig_bb, width='stretch')

    # Training Readiness
    st.subheader("💪 Training Readiness Trend")
    if 'training_readiness' in df.columns and df['training_readiness'].notna().any():
        fig_tr = px.line(
            df.dropna(subset=['training_readiness']),
            x='log_date', y='training_readiness',
            labels={'log_date': 'Date', 'training_readiness': 'Training Readiness'},
            color_discrete_sequence=['#7F77DD']
        )
        fig_tr.add_hline(y=75, line_dash="dash", line_color="gray", annotation_text="High readiness")
        fig_tr.add_hline(y=40, line_dash="dash", line_color="orange", annotation_text="Low readiness")
        st.plotly_chart(fig_tr, width='stretch')
    else:
        st.info("No training readiness data yet.")

    # Section E — Correlation: Sleep Score vs Training Volume
    st.subheader("🔗 Sleep vs Next-Day Training Volume")
    workouts = fetch_workouts_cached(db)
    if workouts:

        df_work = pd.DataFrame(workouts)
        df_work['log_ts'] = pd.to_datetime(df_work['log_ts'], format='ISO8601', utc=True).dt.tz_convert(None)
        df_work['log_date'] = df_work['log_ts'].dt.date
        df_vol = df_work.groupby('log_date')['volume'].sum().reset_index()
        df_vol['log_date'] = pd.to_datetime(df_vol['log_date'], format='ISO8601')
        df_vol['next_date'] = df_vol['log_date']
        df['log_date_only'] = df['log_date'].dt.date
        df_vol['log_date_only'] = df_vol['log_date'].dt.date

        df_corr = df[['log_date_only', 'sleep_score']].merge(
            df_vol[['log_date_only', 'volume']],
            left_on='log_date_only', right_on='log_date_only',
            how='inner'
        )
        if not df_corr.empty and len(df_corr) >= 3:
            fig_corr = px.scatter(
                df_corr, x='sleep_score', y='volume',
                trendline='ols',
                labels={'sleep_score': 'Sleep Score', 'volume': 'Training Volume (kg)'},
                color_discrete_sequence=['#7F77DD']
            )
            st.plotly_chart(fig_corr, width='stretch')
        else:
            st.info("Need at least 3 data points to show correlation.")
