import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_url = api_secrets["base_url"]
session_query_url = api_secrets["session_query_url"]  # Add to secrets.toml

# Authenticate
@st.cache_data
def get_access_token():
    auth_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    response = requests.post(auth_url, data=auth_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        st.error(f"Auth error: {response.status_code} - {response.text}")
        return None

# Fetch session metadata
@st.cache_data
def fetch_sessions(token, date_from, date_to):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "text/plain",
        "Content-Type": "application/json-patch+json"
    }
    payload = {
        "sessionType": "All",
        "utcDateFrom": date_from,
        "utcDateTo": date_to
    }
    response = requests.post(session_query_url, headers=headers, json=payload)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    else:
        st.error(f"Session fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch play-by-play data for a session
@st.cache_data
def fetch_play_data(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    url = f"{base_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame()
    else:
        st.error(f"Play data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Streamlit UI
st.title("TrackMan Game Data Explorer")

# Step 1: Select Date Range
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-03"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    access_token = get_access_token()
    if access_token:
        sessions_df = fetch_sessions(access_token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        adhoc_sessions_df = sessions_df[sessions_df["sessionType"] == "Adhoc"]
        if not adhoc_sessions_df.empty:
            st.subheader("🎯 Select an Adhoc Game Session")

            session_id_col = "sessionId" if "sessionId" in adhoc_sessions_df.columns else adhoc_sessions_df.columns[0]
            session_display_col = "sessionName" if "sessionName" in adhoc_sessions_df.columns else session_id_col

            session_map = dict(zip(adhoc_sessions_df[session_display_col], adhoc_sessions_df[session_id_col]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            chosen_session_id = session_map[session_choice]

            # Step 2: Fetch play-by-play data
            play_df = fetch_play_data(access_token, chosen_session_id)

            if not play_df.empty:
                st.subheader("Play-by-Play Data")
                st.dataframe(play_df)

                st.subheader("Filter")
                col_to_filter = st.selectbox("Filter by Column", play_df.columns)

                if pd.api.types.is_numeric_dtype(play_df[col_to_filter]):
                    min_val, max_val = float(play_df[col_to_filter].min()), float(play_df[col_to_filter].max())
                    selected = st.slider("Select Range", min_val, max_val, (min_val, max_val))
                    filtered_df = play_df[play_df[col_to_filter].between(selected[0], selected[1])]
                else:
                    options = st.multiselect("Choose Values", play_df[col_to_filter].dropna().unique())
                    filtered_df = play_df[play_df[col_to_filter].isin(options)] if options else play_df

                st.subheader("Filtered Results")
                st.dataframe(filtered_df)

                st.download_button("Download CSV", filtered_df.to_csv(index=False), "filtered.csv", "text/csv")

            else:
                st.warning("No play-by-play data found for this session.")
        else:
            st.warning("No sessions found in the selected date range.")
