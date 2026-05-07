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
    mock_secrets.get.return_value = "dummy"
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
    mock_secrets.get.return_value = "dummy"
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
