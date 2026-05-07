import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time
import pandas as pd

# --- EXACT CONFIGURATION ---
SHEET_CONFIG = {
    "sheet_id": "1EEbWz3-C4qOljdUfLy92DNacmEP8MAY2cEKD5XvOmjU",
    "worksheets": {
        "workouts": "Workouts",
        "running": "Running",
        "biohack": "Biohack",
        "weight": "Weight",
        "training_plans": "Training_Plans"
    }
}

@st.cache_resource
def get_gspread_client():
    """Authenticates and returns a gspread client using Streamlit secrets."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Missing 'gcp_service_account' in secrets.")
            return None
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Cloud Authentication Failed: {e}")
        return None

def get_worksheet(worksheet_key):
    """Gets worksheet by key. Auto-creates 'Training_Plans' if missing."""
    client = get_gspread_client()
    if not client: return None
    
    key = worksheet_key.strip().lower()
    if key not in SHEET_CONFIG["worksheets"]:
        st.error(f"Config Key '{key}' not found.")
        return None
        
    tab_name = SHEET_CONFIG["worksheets"][key]
    try:
        sheet = client.open_by_key(SHEET_CONFIG["sheet_id"])
        return sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        if key == "training_plans":
            try:
                sheet = client.open_by_key(SHEET_CONFIG["sheet_id"])
                new_ws = sheet.add_worksheet(title=tab_name, rows=1000, cols=10)
                # Initialize with headers
                new_ws.append_row(["Plan Name", "Exercise", "Type"])
                return new_ws
            except Exception as e2:
                st.error(f"Failed to create Tab [{tab_name}]: {e2}")
                return None
        st.error(f"Tab [{tab_name}] not found.")
        return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def batch_append(worksheet_key, data_list):
    """Appends multiple rows to the specified worksheet."""
    if not data_list: return False
    with st.status(f"Saving to {worksheet_key}...", expanded=False) as status:
        worksheet = get_worksheet(worksheet_key)
        if worksheet is None: return False
        try:
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            status.update(label="Saved Successfully!", state="complete")
            return True
        except Exception as e:
            status.update(label=f"Write Error: {e}", state="error")
            return False

def update_worksheet(worksheet_key, data_matrix):
    """Overwrites the entire worksheet (used for plan deletion/management)."""
    with st.status(f"Updating {worksheet_key}...", expanded=False) as status:
        worksheet = get_worksheet(worksheet_key)
        if worksheet is None: return False
        try:
            worksheet.clear()
            if data_matrix:
                worksheet.update('A1', data_matrix, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            status.update(label="Update Successful!", state="complete")
            return True
        except Exception as e:
            status.update(label=f"Update Error: {e}", state="error")
            return False

@st.cache_data(ttl=600)
def fetch_all_records(worksheet_key):
    """Fetches all records with header cleaning."""
    worksheet = get_worksheet(worksheet_key)
    if worksheet is None: return []
    try:
        data = worksheet.get_all_values()
        if not data: return []
        headers = [str(h).strip() for h in data[0]]
        clean_headers = []
        for i, h in enumerate(headers):
            h_clean = h if h else f"Unnamed_{i}"
            if h_clean in clean_headers: h_clean = f"{h_clean}_{i}"
            clean_headers.append(h_clean)
        
        records = []
        for row in data[1:]:
            record = {}
            for i, val in enumerate(row):
                if i < len(clean_headers): record[clean_headers[i]] = val
            records.append(record)
        return records
    except Exception as e:
        st.error(f"Retrieval Error: {e}")
        return []
