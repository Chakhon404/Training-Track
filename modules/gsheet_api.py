import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time

# Config dictionary using unique Sheet ID for 100% reliability
SHEET_CONFIG = {
    "sheet_id": "1EEbWz3-C4qOljdUfLy92DNacmEP8MAY2cEKD5XvOmjU",
    "worksheets": {
        "workouts": "Workouts",
        "running": "Running",
        "biohack": "Biohack",
        "weight": "Weight"
    }
}

@st.cache_resource
def get_gspread_client():
    """
    Authenticates and returns a gspread client using Streamlit secrets.
    Cached to avoid re-authenticating on every rerun.
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Failed to authenticate with Google Sheets: {e}")
        return None

def get_worksheet(worksheet_key):
    """
    Gets a specific worksheet from the Google Sheet based on the config key and Sheet ID.
    """
    client = get_gspread_client()
    if not client:
        return None
    
    # Normalize input
    key = worksheet_key.strip().lower()
    
    if key not in SHEET_CONFIG["worksheets"]:
        st.error(f"Worksheet key '{key}' not found in configuration.")
        return None
    
    try:
        # Open by unique Sheet ID instead of name
        sheet = client.open_by_key(SHEET_CONFIG["sheet_id"])
        tab_name = SHEET_CONFIG["worksheets"][key]
        return sheet.worksheet(tab_name)
    except Exception as e:
        st.error(f"Error accessing worksheet '{worksheet_key}': {e}")
        return None

def batch_append(worksheet_key, data_list):
    """
    Appends multiple rows to the specified worksheet efficiently using batch updates.
    Includes UI feedback to prevent double submissions.
    """
    if not data_list:
        st.warning("No data to append.")
        return False

    with st.status("Saving to Cloud...", expanded=True) as status:
        st.write("Establishing connection to database...")
        worksheet = get_worksheet(worksheet_key)
        
        if worksheet is None:
            status.update(label="Connection Failed.", state="error")
            return False
            
        try:
            st.write(f"Appending {len(data_list)} record(s) to cloud storage...")
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            status.update(label="Successfully Saved!", state="complete")
            time.sleep(1) # Brief pause for user feedback
            return True
        except Exception as e:
            st.write(f"API Error: {e}")
            status.update(label="Save Operation Failed.", state="error")
            return False
            
def fetch_all_records(worksheet_key):
    """
    Fetches all records for analytics.
    """
    worksheet = get_worksheet(worksheet_key)
    if worksheet is None:
        return []
    try:
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Error fetching records: {e}")
        return []
