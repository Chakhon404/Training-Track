import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_fetch_plans(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    # Use __getitem__ to mock st.secrets["KEY"]
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    # Mocking the Supabase query chain: table().select().execute()
    mock_execute = MagicMock()
    mock_execute.data = [{"name": "Plan A", "exercises": []}]
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_execute
    
    db = TrainingDB()
    plans = db.fetch_plans()
    assert len(plans) == 1
    assert plans[0]["name"] == "Plan A"
    mock_supabase.table.assert_called_with("training_plans")

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_add_plan(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    mock_execute = MagicMock()
    mock_execute.data = [{"id": 1, "name": "New Plan"}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_execute
    
    db = TrainingDB()
    plan_data = {"name": "New Plan"}
    result = db.add_plan(plan_data)
    
    assert result[0]["name"] == "New Plan"
    mock_supabase.table.assert_called_with("training_plans")
    mock_supabase.table.return_value.insert.assert_called_with(plan_data)

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_save_workout(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    db = TrainingDB()
    workout_data = [{"exercise": "Squat", "sets": 3}]
    result = db.save_workout(workout_data)
    
    assert result is True
    mock_supabase.table.assert_called_with("workouts")
    mock_supabase.table.return_value.insert.assert_called_with(workout_data)

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_save_nutrition(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    db = TrainingDB()
    nutrition_data = {"calories": 2500}
    result = db.save_nutrition(nutrition_data)
    
    assert result is True
    mock_supabase.table.assert_called_with("nutrition")
    mock_supabase.table.return_value.insert.assert_called_with(nutrition_data)

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_error_handling(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    # Force an exception during execute()
    mock_supabase.table.return_value.select.return_value.execute.side_effect = Exception("Supabase Error")
    
    db = TrainingDB()
    with patch('streamlit.error') as mock_error:
        plans = db.fetch_plans()
        assert plans == []
        mock_error.assert_called()

@patch('modules.database.create_client')
@patch('streamlit.secrets')
def test_fetch_profile(mock_secrets, mock_create_client):
    from modules.database import TrainingDB
    mock_secrets.__getitem__.side_effect = lambda key: "dummy"
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase
    
    mock_execute = MagicMock()
    mock_execute.data = [{"id": 1, "name": "User"}]
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_execute
    
    db = TrainingDB()
    profile = db.fetch_profile()
    
    assert profile == {"id": 1, "name": "User"}
    mock_supabase.table.assert_called_with("user_profile")
