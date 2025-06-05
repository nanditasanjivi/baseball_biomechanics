import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_url = api_secrets["base_url"]
session_query_url = api_secrets["session_query_url"]

# Authentication
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

# Fetch sessions
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

# Fetch session metadata
@st.cache_data
def fetch_session_metadata(token, session_id):
    url = f"{base_url}/game/session/{session_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Session metadata error: {response.status_code} - {response.text}")
        return {}

# Fetch plays
@st.cache_data
def fetch_play_data(token, session_id):
    url = f"{base_url}/game/plays/{session_id}"
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Play data error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch ball data
@st.cache_data
def fetch_ball_data(token, session_id):
    url = f"{base_url}/game/balls/{session_id}"
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Ball data error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# UI
st.title("TrackMan Game Data Explorer")

# Date inputs
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-01"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-31"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        if not sessions_df.empty:
            st.subheader("Select Game Session")
            session_display_col = "sessionName" if "sessionName" in sessions_df.columns else "sessionId"
            session_id_col = "sessionId"
            session_map = dict(zip(sessions_df[session_display_col], sessions_df[session_id_col]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            session_id = session_map[session_choice]

            # Show session metadata
            metadata = fetch_session_metadata(token, session_id)
            st.markdown("### Session Metadata")
            st.json(metadata)

            # Fetch and merge data
            play_df = fetch_play_data(token, session_id)
            ball_df = fetch_ball_data(token, session_id)

            if not play_df.empty and not ball_df.empty and "playId" in ball_df.columns:
                merged_df = pd.merge(play_df, ball_df, on="playId", how="left")
                st.subheader("Merged Play and Ball Data")
                st.dataframe(merged_df)

                st.subheader("Filter")
                col_to_filter = st.selectbox("Filter by Column", merged_df.columns)
                if pd.api.types.is_numeric_dtype(merged_df[col_to_filter]):
                    min_val, max_val = float(merged_df[col_to_filter].min()), float(merged_df[col_to_filter].max())
                    selected = st.slider("Select Range", min_val, max_val, (min_val, max_val))
                    filtered_df = merged_df[merged_df[col_to_filter].between(selected[0], selected[1])]
                else:
                    options = st.multiselect("Choose Values", merged_df[col_to_filter].dropna().unique())
                    filtered_df = merged_df[merged_df[col_to_filter].isin(options)] if options else merged_df

                st.subheader("Filtered Results")
                st.dataframe(filtered_df)
                st.download_button("Download CSV", filtered_df.to_csv(index=False), "filtered.csv", "text/csv")
            else:
                st.warning("Play or Ball data is empty or not mergeable.")
        else:
            st.warning("No sessions found.")
