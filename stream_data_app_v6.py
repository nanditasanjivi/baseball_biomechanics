import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
plays_base_url = api_secrets["base_url"]  # This is for plays
session_query_url = api_secrets["session_query_url"]

# Construct ball data base URL from plays_base_url
balls_base_url = plays_base_url.replace("/plays", "/balls")

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

# Fetch plays
@st.cache_data
def fetch_plays(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{plays_base_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Plays fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls
@st.cache_data
def fetch_balls(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{balls_base_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Balls fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# UI
st.title("TrackMan Game Data Viewer")

# Step 1: Select Date Range
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-01"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        adhoc_sessions_df = sessions_df[sessions_df["sessionType"] == "Adhoc"]
        if not adhoc_sessions_df.empty:
            st.subheader("Select Session")
            session_display_col = "sessionName" if "sessionName" in adhoc_sessions_df.columns else "sessionId"
            session_map = dict(zip(adhoc_sessions_df[session_display_col], adhoc_sessions_df["sessionId"]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            session_id = session_map[session_choice]

            # Step 2: Fetch Data
            plays_df = fetch_plays(token, session_id)
            balls_df = fetch_balls(token, session_id)

            if not plays_df.empty:
                st.subheader("Filter by Player ID")

                # Combine unique pitcher and batter IDs
                all_ids = pd.Series(plays_df["pitcher.id"].dropna().tolist() + plays_df["batter.id"].dropna().tolist()).unique()
                selected_player_id = st.selectbox("Select Player ID", all_ids)

                # Filter plays
                filtered_plays = plays_df[
                    (plays_df["pitcher.id"] == selected_player_id) |
                    (plays_df["batter.id"] == selected_player_id)
                ]

                # Filter balls based on matching playId
                filtered_balls = balls_df[balls_df["playId"].isin(filtered_plays["playID"])]

                st.subheader("Filtered Plays")
                st.dataframe(filtered_plays)

                st.subheader("Filtered Balls")
                st.dataframe(filtered_balls)

                # Download
                st.download_button("Download Plays CSV", filtered_plays.to_csv(index=False), "filtered_plays.csv", "text/csv")
                st.download_button("Download Balls CSV", filtered_balls.to_csv(index=False), "filtered_balls.csv", "text/csv")
            else:
                st.warning("No play data found for this session.")
        else:
            st.warning("No Adhoc sessions found.")
