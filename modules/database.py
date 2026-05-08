import streamlit as st
from supabase import create_client, Client

class TrainingDB:
    def __init__(self):
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            self.supabase: Client = create_client(url, key)
        except Exception as e:
            st.error(f"Failed to initialize Supabase client: {e}")
            self.supabase = None

    def is_connected(self):
        return self.supabase is not None

    def fetch_plans(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("training_plans").select("*").execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to fetch plans: {e}")
            return []

    def add_plan(self, plan_data):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("training_plans").insert(plan_data).execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to add plan: {e}")
            return None

    def delete_plan(self, plan_id):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("training_plans").delete().eq("id", plan_id).execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to delete plan: {e}")
            return None

    def save_workout(self, workout_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("workouts").insert(workout_data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save workout: {e}")
            return False

    def fetch_workouts(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("workouts").select("*").execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to fetch workouts: {e}")
            return []

    def save_run(self, run_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("running").insert(run_data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save run: {e}")
            return False

    def fetch_runs(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("running").select("*").execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to fetch runs: {e}")
            return []

    def save_nutrition(self, nutrition_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("nutrition").insert(nutrition_data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save nutrition: {e}")
            return False

    def fetch_nutrition(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("nutrition").select("*").execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to fetch nutrition: {e}")
            return []

    def save_weight(self, weight_data):
        if not self.is_connected(): return False
        try:
            self.supabase.table("weight").insert(weight_data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save weight: {e}")
            return False

    def fetch_weight(self):
        if not self.is_connected(): return []
        try:
            response = self.supabase.table("weight").select("*").execute()
            return response.data
        except Exception as e:
            st.error(f"Failed to fetch weight: {e}")
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
        except Exception:
            return []

    def save_draft(self, form_key: str, data: dict):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").upsert(
                {"form_key": form_key, "data": data},
                on_conflict="form_key"
            ).execute()
            return response.data
        except Exception:
            return None

    def load_draft(self, form_key: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").select("data").eq("form_key", form_key).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]["data"]
            return None
        except Exception:
            return None

    def clear_draft(self, form_key: str):
        if not self.is_connected(): return None
        try:
            response = self.supabase.table("drafts").delete().eq("form_key", form_key).execute()
            return response.data
        except Exception:
            return None

@st.cache_resource
def get_db():
    return TrainingDB()
