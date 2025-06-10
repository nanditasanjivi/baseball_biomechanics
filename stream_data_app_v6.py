import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
plays_base_url = api_secrets["base_url"]
session_query_url = api_secrets["session_query_url"]

# Derive balls URL from plays URL
balls_base_url = plays_base_url.replace("/plays", "/balls")

@st.cache_data
def get_access_token():
    response = requests.post(auth_url, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    st.error("Failed to authenticate.")
    return None

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
    res = requests.post(session_query_url, headers=headers, json=payload)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    st.error("Failed to fetch sessions.")
    return pd.DataFrame()

@st.cache_data
def fetch_plays(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{plays_base_url}/{session_id}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return pd.json_normalize(res.json())
    st.error("Failed to fetch plays.")
    return pd.DataFrame()

@st.cache_data
def fetch_balls(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{balls_base_url}/{session_id}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return pd.json_normalize(res.json())
    st.error("Failed to fetch balls.")
    return pd.DataFrame()

# UI
st.title("TrackMan Game Data: Pitcher View")

date_from = st.date_input("Start Date")
date_to = st.date_input("End Date")

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(
            token,
            f"{date_from}T00:00:00Z",
            f"{date_to}T23:59:59Z"
        )

        if not sessions_df.empty:
            st.subheader("Select Session")
            session_map = dict(zip(sessions_df["sessionId"], sessions_df["sessionId"]))
            selected_session = st.selectbox("Session", list(session_map.values()))

            plays_df = fetch_plays(token, selected_session)
            balls_df = fetch_balls(token, selected_session)

            if not plays_df.empty:
                st.subheader("Filter by Pitcher ID")
                unique_pitchers = plays_df["pitcher.id"].dropna().unique()
                selected_pitcher = st.selectbox("Pitcher ID", unique_pitchers)

                filtered_plays = plays_df[plays_df["pitcher.id"] == selected_pitcher]
                filtered_balls = balls_df[balls_df["playId"].isin(filtered_plays["playID"])]

                st.markdown("### Filtered Plays")
                st.dataframe(filtered_plays)

                st.markdown("### Filtered Balls")
                st.dataframe(filtered_balls)

                st.download_button("Download Plays CSV", filtered_plays.to_csv(index=False), "plays.csv", "text/csv")
                st.download_button("Download Balls CSV", filtered_balls.to_csv(index=False), "balls.csv", "text/csv")
            else:
                st.warning("No plays found for this session.")
        else:
            st.warning("No sessions found in this date range.")
