import streamlit as st
from supabase import create_client, Client

class TrainingDB:
    def __init__(self):
        url: str = st.secrets["SUPABASE_URL"]
        key: str = st.secrets["SUPABASE_KEY"]
        self.supabase: Client = create_client(url, key)

    def is_connected(self):
        return self.supabase is not None

    def fetch_plans(self):
        response = self.supabase.table("training_plans").select("*").execute()
        return response.data

    def add_plan(self, plan_data):
        response = self.supabase.table("training_plans").insert(plan_data).execute()
        return response.data

    def delete_plan(self, plan_id):
        response = self.supabase.table("training_plans").delete().eq("id", plan_id).execute()
        return response.data

    def save_workout(self, workout_data):
        response = self.supabase.table("workouts").insert(workout_data).execute()
        return response.data

    def fetch_workouts(self):
        response = self.supabase.table("workouts").select("*").execute()
        return response.data

    def save_run(self, run_data):
        response = self.supabase.table("runs").insert(run_data).execute()
        return response.data

    def save_nutrition(self, nutrition_data):
        response = self.supabase.table("nutrition").insert(nutrition_data).execute()
        return response.data

    def fetch_nutrition(self):
        response = self.supabase.table("nutrition").select("*").execute()
        return response.data

    def save_weight(self, weight_data):
        response = self.supabase.table("weight").insert(weight_data).execute()
        return response.data

    def fetch_weight(self):
        response = self.supabase.table("weight").select("*").execute()
        return response.data
