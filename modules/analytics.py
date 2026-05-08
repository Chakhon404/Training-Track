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
    db = get_db()
    today = datetime.now().date()
    
    with st.spinner("Loading Today's Summary..."):
        workouts = db.fetch_workouts()
        weight_logs = db.fetch_weight()
        nutrition_logs = db.fetch_nutrition()
        runs = db.fetch_runs()

        df_work = pd.DataFrame(workouts)
        df_weight = pd.DataFrame(weight_logs)
        df_nut = pd.DataFrame(nutrition_logs)
        df_run = pd.DataFrame(runs)

        # Parse timestamps with format='ISO8601'
        for df in [df_work, df_weight, df_nut, df_run]:
            if not df.empty and 'log_ts' in df.columns:
                df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601')
                df['date'] = df['log_ts'].dt.date

        # Filter today
        work_today = df_work[df_work['date'] == today] if not df_work.empty else pd.DataFrame()
        weight_today = df_weight[df_weight['date'] == today] if not df_weight.empty else pd.DataFrame()
        nut_today = df_nut[df_nut['date'] == today] if not df_nut.empty else pd.DataFrame()
        run_today = df_run[df_run['date'] == today] if not df_run.empty else pd.DataFrame()

    # Section A — Header
    st.header("🏠 Daily Overview")
    st.caption(f"Today: {today.strftime('%A, %d %B %Y')}")

    # Section B — Activity Status Row
    c1, c2, c3, c4 = st.columns(4)
    
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
        if not weight_today.empty:
            w = weight_today.iloc[-1]['weight']
            st.metric("⚖️ Weight", f"{w} kg")
        else:
            st.metric("⚖️ Weight", "Not logged")

    with c4:
        if not nut_today.empty:
            cal = int(nut_today.iloc[-1]['calories'])
            goal_cal = 2500 # TODO: move to user_profiles table
            st.metric("🍱 Calories", f"{cal} kcal", delta=f"{cal - goal_cal} vs Goal")
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
                p = latest_nut.get('protein_g', 0)
                p_goal = 150 # TODO: move to user_profiles table
                st.metric("Protein", f"{p}g", delta=f"{p - p_goal}g vs Goal")
            with m2:
                st.metric("Carbs", f"{latest_nut.get('carbs_g', 0)}g")
            with m3:
                st.metric("Fat", f"{latest_nut.get('fat_g', 0)}g")
            
            st.divider()
            s1, s2, s3, s4 = st.columns(4)
            supps = [
                ("Creatine", "creatine"),
                ("Protein Powder", "protein_powder"),
                ("Multi-Vitamin", "multivitamin"),
                ("Omega-3", "omega3")
            ]
            for col, (label, key) in zip([s1, s2, s3, s4], supps):
                status = "✅" if latest_nut.get(key) else "❌"
                col.markdown(f"**{label}**: {status}")
    else:
        st.info("🍱 No nutrition logged today.")

    # Section D — Training Detail Card
    if not work_today.empty:
        with st.container(border=True):
            st.markdown("### 🏋️ Today's Training")
            st.dataframe(
                work_today[['exercise', 'weight', 'sets', 'reps', 'volume', 'rpe']], 
                hide_index=True,
                use_container_width=True
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
        df_vol['log_ts'] = pd.to_datetime(df_vol['log_ts'], format='ISO8601')
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
        df_w_plot = df_weight.rename(columns={'log_ts': 'Date', 'weight': 'Weight'})
        df_w_plot = safe_numeric(df_w_plot, ['Weight'])
        
        df_wrk_plot = df_work.rename(columns={'log_ts': 'Date', 'volume': 'Volume'})
        df_wrk_plot = safe_numeric(df_wrk_plot, ['Volume'])

    with l:
        render_chart_safely(df_wrk_plot, 'Date', 'Volume', "Weekly Training Volume")
    with r:
        render_chart_safely(df_w_plot, 'Date', 'Weight', "Weight Progression")

def render_data_manager():
    db = get_db()
    st.header("🗂️ Data Manager")
    st.caption("Review and delete individual entries across all logs.")

    # 1. Workout Entries
    with st.expander("🏋️ Workout Entries", expanded=False):
        df = pd.DataFrame(db.fetch_workouts())
        if not df.empty:
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601')
            df_display = df[['log_ts', 'exercise', 'weight', 'sets', 'reps', 'rpe', 'volume']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                use_container_width=True,
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
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601')
            df_display = df[['log_ts', 'category', 'distance', 'duration', 'pace', 'hr']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                use_container_width=True,
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
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601')
            df_display = df[['log_ts', 'calories', 'protein_g', 'carbs_g', 'fat_g']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                use_container_width=True,
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
            df['log_ts'] = pd.to_datetime(df['log_ts'], format='ISO8601')
            df_display = df[['log_ts', 'weight', 'notes']].copy()
            df_display = df_display.sort_values('log_ts', ascending=False).reset_index(drop=True)

            event = st.dataframe(
                df_display,
                use_container_width=True,
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
