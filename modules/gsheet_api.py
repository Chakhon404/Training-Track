import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time

# Config dictionary to avoid hardcoding errors
SHEET_CONFIG = {
    "sheet_name": "The Tank Log DB", # Change this to your actual Google Sheet name
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
    Gets a specific worksheet from the Google Sheet based on the config key.
    """
    client = get_gspread_client()
    if not client: return None
    
    try:
        sheet = client.open(SHEET_CONFIG["sheet_name"])
        return sheet.worksheet(SHEET_CONFIG["worksheets"][worksheet_key])
    except Exception as e:
        st.error(f"Error accessing worksheet '{worksheet_key}': {e}")
        return None

def batch_append(worksheet_key, data_list):
    """
    Appends multiple rows to the specified worksheet efficiently.
    Includes UI feedback to prevent double submissions.
    """
    if not data_list:
        st.warning("No data to append.")
        return False

    with st.status("Saving to Cloud...", expanded=True) as status:
        st.write(f"Connecting to {SHEET_CONFIG['worksheets'][worksheet_key]} worksheet...")
        worksheet = get_worksheet(worksheet_key)
        
        if worksheet is None:
            status.update(label="Failed to connect to worksheet.", state="error")
            return False
            
        try:
            st.write(f"Appending {len(data_list)} rows...")
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            status.update(label="Successfully saved to Cloud!", state="complete")
            time.sleep(1) # Brief pause for user to see success message
            return True
        except Exception as e:
            st.write(f"API Error: {e}")
            status.update(label="Failed to save data.", state="error")
            return False
            
def fetch_all_records(worksheet_key):
    """Fetches all records for analytics."""
    worksheet = get_worksheet(worksheet_key)
    if worksheet is None:
        return []
    try:
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Error fetching records: {e}")
        return []
