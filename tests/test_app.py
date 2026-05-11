import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import streamlit as st
from app import _handle_pending_confirmations

@patch('app.st')
def test_handle_pending_confirmations_fallback_bodyweight(mock_st):
    # Setup mock db
    mock_db = MagicMock()
    mock_db.fetch_plans.return_value = [{"name": "Test Plan", "exercises": [{"name": "Pushup", "type": "Bodyweight"}]}]
    mock_db.fetch_profile.return_value = {"weight_kg": 80.0}

    # Setup mock session state
    mock_st.session_state = MagicMock()
    session_state_data = {
        "workout_confirm_overwrite": True,
        "workout_do_overwrite": False,
        "work_plan_name": "Test Plan",
        "work_date": "2026-05-11",
        "work_time": datetime.strptime("10:00:00", "%H:%M:%S"),
        # bodyweight_kg is missing
        "work_s_0": 3,
        "work_r_0": 10,
        "work_d_0": 0,
        "work_w_0": 0.0,
        "work_rpe_0": 7.0,
    }

    def mock_pop(key, default=None):
        return session_state_data.pop(key, default)
    mock_st.session_state.pop.side_effect = mock_pop

    def mock_get(key, default=None):
        return session_state_data.get(key, default)
    mock_st.session_state.get.side_effect = mock_get

    # Run function
    _handle_pending_confirmations(mock_db)

    # Verify db.fetch_profile was called since bodyweight_kg was missing
    mock_db.fetch_profile.assert_called_once()
    
    # Verify the volume calculation used 80.0 kg (3 * 10 * 80.0 = 2400.0)
    # The payload is passed to db.save_workout(final_rows)
    mock_db.save_workout.assert_called_once()
    saved_rows = mock_db.save_workout.call_args[0][0]
    assert len(saved_rows) == 1
    assert saved_rows[0]["volume"] == 2400.0
