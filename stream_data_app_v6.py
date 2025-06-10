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

# Fetch play data
@st.cache_data
def fetch_play_data(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    url = f"https://dataapi.trackmanbaseball.com/api/v1/data/game/plays/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data)
    else:
        st.error(f"Play data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch ball data (pitch only)
@st.cache_data
def fetch_ball_data(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    url = f"https://dataapi.trackmanbaseball.com/api/v1/data/game/balls/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        pitch_balls = [b for b in data if b.get("kind") == "Pitch"]
        return pd.json_normalize(pitch_balls)
    else:
        st.error(f"Ball data fetch error: {response.status_code} - {response.text}")
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
            st.subheader("Select Game Session")
            session_id_col = "sessionId"
            session_display_col = "sessionName" if "sessionName" in adhoc_sessions_df.columns else session_id_col
            session_map = dict(zip(adhoc_sessions_df[session_display_col], adhoc_sessions_df[session_id_col]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            chosen_session_id = session_map[session_choice]

            play_df = fetch_play_data(access_token, chosen_session_id)
            ball_df = fetch_ball_data(access_token, chosen_session_id)

            if not play_df.empty:
                st.subheader("Play-by-Play Data")
                st.dataframe(play_df)

                if "pitcher.id" in play_df.columns or "batter.id" in play_df.columns:
                    st.subheader("Filter by PlayerID")
                    play_df["playerID"] = play_df["pitcher.id"].fillna('') + '_' + play_df["batter.id"].fillna('')
                    player_ids = play_df["playerID"].unique()
                    selected_ids = st.multiselect("Select PlayerID (pitcherID_batterID format)", player_ids)

                    filtered_plays = play_df[play_df["playerID"].isin(selected_ids)]
                    st.subheader("Filtered Plays")
                    st.dataframe(filtered_plays)

                    if not ball_df.empty:
                        merged_balls = pd.merge(
                            ball_df,
                            filtered_plays[["playID", "playerID"]],
                            left_on="playId",
                            right_on="playID",
                            how="inner"
                        )

                        st.subheader("Filtered Pitch Balls")
                        st.dataframe(merged_balls)

                        combined = pd.concat([
                            filtered_plays.assign(dataType="Play"),
                            merged_balls.assign(dataType="PitchBall")
                        ], sort=False)

                        st.download_button("Download Combined CSV", combined.to_csv(index=False), "filtered_combined.csv", "text/csv")
                    else:
                        st.warning("No pitch ball data available.")
                else:
                    st.warning("Expected pitcher.id or batter.id column not found in play data.")
            else:
                st.warning("No play data found for selected session.")
        else:
            st.warning("No Adhoc sessions found in the selected date range.")
