import streamlit as st
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

class TrainingDB:
    def __init__(self):
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            self.supabase: Client = create_client(url, key)
        except Exception as e:
            logger.error(f"[TrainingDB.__init__] {e}", exc_info=True)
            st.error("Failed to initialize Supabase client. Check your configuration.")
            self.supabase = None

    def is_connected(self):
        return self.supabase is not None

    def fetch_plans(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("training_plans").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_plans] {e}", exc_info=True)
            st.error("Failed to fetch plans. Check your connection.")
            return []

    def add_plan(self, plan_data):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("training_plans").insert(plan_data).execute()
            fetch_plans_cached.clear()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.add_plan] {e}", exc_info=True)
            st.error("Failed to add plan. Check your connection.")
            return None

    def delete_plan(self, plan_id):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("training_plans").delete().eq("id", plan_id).execute()
            fetch_plans_cached.clear()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.delete_plan] {e}", exc_info=True)
            st.error("Failed to delete plan.")
            return None

    def update_plan(self, plan_id: str, plan_data: dict):
        """Update an existing training plan by id."""
        if not self.is_connected(): return False
        try:
            self.supabase.table("training_plans")\
                .update(plan_data)\
                .eq("id", plan_id)\
                .execute()
            fetch_plans_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.update_plan] {e}", exc_info=True)
            st.error("Failed to update plan.")
            return False

    def save_workout(self, workout_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("workouts").insert(workout_data).execute()
            fetch_workouts_cached.clear()
            fetch_last_session_cached.clear()
            fetch_today_summary_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_workout] {e}", exc_info=True)
            st.error("Failed to save workout. Check your connection.")
            return False

    def fetch_workouts(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("workouts").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_workouts] {e}", exc_info=True)
            return []

    def save_run(self, run_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("running").insert(run_data).execute()
            fetch_runs_cached.clear()
            fetch_today_summary_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_run] {e}", exc_info=True)
            st.error("Failed to save run.")
            return False

    def fetch_runs(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("running").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_runs] {e}", exc_info=True)
            return []

    def save_nutrition(self, nutrition_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("nutrition").insert(nutrition_data).execute()
            fetch_nutrition_cached.clear()
            fetch_today_summary_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_nutrition] {e}", exc_info=True)
            st.error("Failed to save nutrition.")
            return False

    def fetch_nutrition(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("nutrition").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_nutrition] {e}", exc_info=True)
            return []

    def save_weight(self, weight_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("weight").insert(weight_data).execute()
            fetch_weight_cached.clear()
            fetch_today_summary_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_weight] {e}", exc_info=True)
            st.error("Failed to save weight.")
            return False

    def fetch_weight(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("weight").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_weight] {e}", exc_info=True)
            return []

    def fetch_weekly_volume(self):
        """DEPRECATED: Use fetch_workouts() and filter in-memory instead."""
        if not self.is_connected(): return []
        try:
            response = (
                self.supabase.table("workouts")
                .select("log_ts, volume")
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_weekly_volume] {e}", exc_info=True)
            return []

    def fetch_exercise_history(self, exercise_name: str, limit: int = 3):
        if not self.is_connected(): return []
        try:
            response = (
                self.supabase.table("workouts")
                .select("log_ts, weight, sets, reps, rpe")
                .eq("exercise", exercise_name)
                .order("log_ts", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_exercise_history] {e}", exc_info=True)
            return []

    def fetch_workouts_by_date(self, date: str):
        """Fetch workouts for a specific date (YYYY-MM-DD)."""
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("workouts").select("*")\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_workouts_by_date] {e}", exc_info=True)
            return []

    def fetch_runs_by_date(self, date: str):
        """Fetch runs for a specific date (YYYY-MM-DD)."""
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("running").select("*")\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_runs_by_date] {e}", exc_info=True)
            return []

    def fetch_nutrition_by_date(self, date: str):
        """Fetch nutrition entries for a specific date (YYYY-MM-DD)."""
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("nutrition").select("*")\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_nutrition_by_date] {e}", exc_info=True)
            return []

    def fetch_weight_by_date(self, date: str):
        """Fetch weight entries for a specific date (YYYY-MM-DD)."""
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("weight").select("*")\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_weight_by_date] {e}", exc_info=True)
            return []

    def save_draft(self, form_key: str, data: dict):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").upsert(
                {"form_key": form_key, "data": data},
                on_conflict="form_key"
            ).execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.save_draft] {e}", exc_info=True)
            return None

    def load_draft(self, form_key: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").select("data").eq("form_key", form_key).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]["data"]
            return None
        except Exception as e:
            logger.error(f"[TrainingDB.load_draft] {e}", exc_info=True)
            return None

    def clear_draft(self, form_key: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").delete().eq("form_key", form_key).execute()
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.clear_draft] {e}", exc_info=True)
            return None

    # --- DUPLICATE DETECTION ---

    def check_duplicate_workout(self, date: str) -> int:
        """Returns count of exercises logged on given date (YYYY-MM-DD)"""
        if not self.is_connected(): return 0
        try:
            response = (
                self.supabase.table("workouts")
                .select("id", count="exact")
                .gte("log_ts", f"{date}T00:00:00")
                .lte("log_ts", f"{date}T23:59:59")
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"[TrainingDB.check_duplicate_workout] {e}", exc_info=True)
            return 0

    def check_duplicate_run(self, date: str) -> int:
        """Returns count of runs logged on given date"""
        if not self.is_connected(): return 0
        try:
            response = (
                self.supabase.table("running")
                .select("id", count="exact")
                .gte("log_ts", f"{date}T00:00:00")
                .lte("log_ts", f"{date}T23:59:59")
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"[TrainingDB.check_duplicate_run] {e}", exc_info=True)
            return 0

    def check_duplicate_nutrition(self, date: str) -> int:
        """Returns count of nutrition entries logged on given date"""
        if not self.is_connected(): return 0
        try:
            response = (
                self.supabase.table("nutrition")
                .select("id", count="exact")
                .gte("log_ts", f"{date}T00:00:00")
                .lte("log_ts", f"{date}T23:59:59")
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"[TrainingDB.check_duplicate_nutrition] {e}", exc_info=True)
            return 0

    def check_duplicate_weight(self, date: str) -> int:
        """Returns count of weight entries logged on given date"""
        if not self.is_connected(): return 0
        try:
            response = (
                self.supabase.table("weight")
                .select("id", count="exact")
                .gte("log_ts", f"{date}T00:00:00")
                .lte("log_ts", f"{date}T23:59:59")
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"[TrainingDB.check_duplicate_weight] {e}", exc_info=True)
            return 0

    # --- DELETE BY DATE (OVERWRITE) ---

    def delete_workouts_by_date(self, date: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("workouts").delete()\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            fetch_workouts_cached.clear()
            fetch_last_session_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_workouts_by_date] {e}", exc_info=True)
            st.error("Failed to delete workouts by date.")
            return None

    def delete_runs_by_date(self, date: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("running").delete()\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            fetch_runs_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_runs_by_date] {e}", exc_info=True)
            st.error("Failed to delete runs.")
            return None

    def delete_nutrition_by_date(self, date: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("nutrition").delete()\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            fetch_nutrition_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_nutrition_by_date] {e}", exc_info=True)
            st.error("Failed to delete nutrition entries.")
            return None

    def delete_weight_by_date(self, date: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("weight").delete()\
                .gte("log_ts", f"{date}T00:00:00")\
                .lte("log_ts", f"{date}T23:59:59")\
                .execute()
            fetch_weight_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_weight_by_date] {e}", exc_info=True)
            st.error("Failed to delete weight entry.")
            return None

    # --- DELETE BY ID ---

    def delete_workout_by_id(self, entry_id: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("workouts").delete().eq("id", entry_id).execute()
            fetch_workouts_cached.clear()
            fetch_last_session_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_workout_by_id] {e}", exc_info=True)
            st.error("Failed to delete workout entry.")
            return None

    def delete_run_by_id(self, entry_id: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("running").delete().eq("id", entry_id).execute()
            fetch_runs_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_run_by_id] {e}", exc_info=True)
            st.error("Failed to delete run entry.")
            return None

    def delete_nutrition_by_id(self, entry_id: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("nutrition").delete().eq("id", entry_id).execute()
            fetch_nutrition_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_nutrition_by_id] {e}", exc_info=True)
            st.error("Failed to delete nutrition entry.")
            return None

    def delete_weight_by_id(self, entry_id: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("weight").delete().eq("id", entry_id).execute()
            fetch_weight_cached.clear()
            fetch_today_summary_cached.clear()
            return response
        except Exception as e:
            logger.error(f"[TrainingDB.delete_weight_by_id] {e}", exc_info=True)
            st.error("Failed to delete weight entry.")
            return None

    # --- SESSION HISTORY ---

    def fetch_last_session_by_plan(self, plan_name: str) -> dict:
        """
        Returns the most recent workout session rows for a given plan_name.
        Returns a dict keyed by exercise name:
        {
          "Overhead Slam": [
            {"set_number": 1, "weight": 7.0, "reps": 8, "duration_sec": 0},
            ...
          ],
          ...
        }
        Fetches the latest log_ts date for that plan, then all rows on that date.
        """
        if not self.is_connected(): return {}
        try:
            # 1. Find the most recent date for this plan
            response = self.supabase.table("workouts")\
                .select("log_ts")\
                .eq("plan_name", plan_name)\
                .order("log_ts", desc=True)\
                .limit(1)\
                .execute()
            
            if not response.data:
                return {}
            
            latest_ts = response.data[0]["log_ts"]
            latest_date = latest_ts.split(" ")[0] if " " in latest_ts else latest_ts.split("T")[0]

            # 2. Fetch all rows for that plan on that date
            response = self.supabase.table("workouts")\
                .select("*")\
                .eq("plan_name", plan_name)\
                .gte("log_ts", f"{latest_date} 00:00:00")\
                .lte("log_ts", f"{latest_date} 23:59:59")\
                .execute()
            
            if not response.data:
                return {}
            
            # 3. Group by exercise and preserve order (sorted by log_ts)
            sorted_data = sorted(response.data, key=lambda x: (x.get("log_ts"), x.get("set_number", 0)))
            
            grouped = {}
            for row in sorted_data:
                ex = row["exercise"]
                if ex not in grouped:
                    grouped[ex] = []
                grouped[ex].append({
                    "set_number": row.get("set_number", len(grouped[ex]) + 1),
                    "weight": row.get("weight", 0.0),
                    "reps": row.get("reps", 0),
                    "duration_sec": row.get("duration_sec", 0),
                    "date": latest_date
                })
            return grouped
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_last_session_by_plan] {e}", exc_info=True)
            return {}

    # --- WELLNESS ---

    def fetch_wellness(self, days: int = 30):
        """Fetch last N days of wellness data ordered by date desc."""
        if not self.is_connected(): return []
        try:
            response = (
                self.supabase.table("wellness")
                .select("*")
                .order("log_date", desc=True)
                .limit(days)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_wellness] {e}", exc_info=True)
            return []

    def fetch_wellness_by_date(self, log_date: str):
        """Fetch single wellness entry by date (YYYY-MM-DD)."""
        if not self.is_connected(): return None
        try:
            response = (
                self.supabase.table("wellness")
                .select("*")
                .eq("log_date", log_date)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_wellness_by_date] {e}", exc_info=True)
            return None

    def fetch_profile(self) -> dict | None:
        """Returns the single user profile row, or None if not set up yet."""
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("user_profile").select("*").limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"[TrainingDB.fetch_profile] {e}", exc_info=True)
            return None

    def save_profile(self, profile_data: dict) -> bool:
        """Upserts the user profile. If a row exists, update it. Otherwise insert."""
        if not self.is_connected(): return False
        try:
            existing = self.fetch_profile()
            if existing:
                self.supabase.table("user_profile")\
                    .update(profile_data)\
                    .eq("id", existing["id"])\
                    .execute()
            else:
                self.supabase.table("user_profile").insert(profile_data).execute()
            fetch_profile_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_profile] {e}", exc_info=True)
            st.error("Failed to save profile.")
            return False

    def save_wellness(self, payload: dict) -> bool:
        """Upsert wellness data into the wellness table."""
        if not self.is_connected(): return False
        try:
            self.supabase.table("wellness").upsert(payload, on_conflict="log_date").execute()
            fetch_wellness_cached.clear()
            return True
        except Exception as e:
            logger.error(f"[TrainingDB.save_wellness] {e}", exc_info=True)
            st.error("Failed to save wellness data.")
            return False

@st.cache_resource
def get_db():
    return TrainingDB()

@st.cache_data(ttl=300)
def fetch_profile_cached(_db):
    """Cached wrapper for fetch_profile(). TTL=300s (5 min).
    Underscore prefix on _db prevents Streamlit from trying to hash the DB object."""
    return _db.fetch_profile()

@st.cache_data(ttl=60)
def fetch_workouts_cached(_db):
    """Cached wrapper for fetch_workouts(). TTL=60s."""
    return _db.fetch_workouts()

@st.cache_data(ttl=60)
def fetch_runs_cached(_db):
    """Cached wrapper for fetch_runs(). TTL=60s."""
    return _db.fetch_runs()

@st.cache_data(ttl=60)
def fetch_nutrition_cached(_db):
    """Cached wrapper for fetch_nutrition(). TTL=60s."""
    return _db.fetch_nutrition()

@st.cache_data(ttl=60)
def fetch_weight_cached(_db):
    """Cached wrapper for fetch_weight(). TTL=60s."""
    return _db.fetch_weight()

@st.cache_data(ttl=60)
def fetch_wellness_cached(_db, days=30):
    """Cached wrapper for fetch_wellness(). TTL=60s."""
    return _db.fetch_wellness(days=days)

@st.cache_data(ttl=300)
def fetch_plans_cached(_db):
    """Cached wrapper for fetch_plans(). TTL=300s (plans change rarely)."""
    return _db.fetch_plans()

@st.cache_data(ttl=120)
def fetch_last_session_cached(_db, plan_name: str) -> dict:
    return _db.fetch_last_session_by_plan(plan_name)

@st.cache_data(ttl=120)
def fetch_today_summary_cached(_db, target_date_str):
    """
    Fetch a consolidated summary for a specific date string (YYYY-MM-DD).
    Target date must be a string for stable caching.
    """
    return {
        "work": _db.fetch_workouts_by_date(target_date_str),
        "run": _db.fetch_runs_by_date(target_date_str),
        "nut": _db.fetch_nutrition_by_date(target_date_str),
        "weight": _db.fetch_weight_by_date(target_date_str)
    }
