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
        "accept": "application/json",
        "Content-Type": "application/json"
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
        st.error(f"Session metadata error: {response.status_code} - {response.text}")
        return pd.DataFrame()

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

# Date range selector
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-01"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        adhoc_sessions = sessions_df[sessions_df["sessionType"] == "Adhoc"]

        if not adhoc_sessions.empty:
            session_display_col = "sessionName" if "sessionName" in adhoc_sessions.columns else "sessionId"
            session_map = dict(zip(adhoc_sessions[session_display_col], adhoc_sessions["sessionId"]))
            session_choice = st.selectbox("Select Adhoc Session", options=list(session_map.keys()))
            selected_session_id = session_map[session_choice]

            play_df = fetch_play_data(token, selected_session_id)
            ball_df = fetch_ball_data(token, selected_session_id)

            if not play_df.empty:
                st.subheader("Play-by-Play Data")
                st.dataframe(play_df)

                if "batter.name" in play_df.columns:
                    player_names = play_df["batter.name"].dropna().unique()
                    selected_player = st.selectbox("Select Player", player_names)

                    if not ball_df.empty:
                        merged_df = pd.merge(play_df, ball_df, on="playId", how="inner")
                        filtered_df = merged_df[merged_df["batter.name"] == selected_player]

                        st.subheader("Ball Data for Selected Player")
                        st.dataframe(filtered_df)
                        st.download_button("Download Player Ball Data", filtered_df.to_csv(index=False), "player_ball_data.csv", "text/csv")
                    else:
                        st.warning("No ball data found for the selected session.")
                else:
                    st.warning("No batter name data to filter on.")
            else:
                st.warning("No play-by-play data found for this session.")
        else:
            st.warning("No 'Adhoc' sessions found in the selected date range.")
