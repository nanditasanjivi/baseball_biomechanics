import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_url_plays = api_secrets["base_url"]          # plays endpoint
session_query_url = api_secrets["session_query_url"]  # sessions endpoint
base_url_balls = "https://dataapi.trackmanbaseball.com/api/v1/data/game/balls"  # balls endpoint (fixed)

# Authenticate and get access token
@st.cache_data(show_spinner=False)
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
@st.cache_data(show_spinner=False)
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

# Fetch plays data for a session
@st.cache_data(show_spinner=False)
def fetch_plays(token, session_id):
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    url = f"{base_url_plays}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame()
    else:
        st.error(f"Plays fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls data for a session
@st.cache_data(show_spinner=False)
def fetch_balls(token, session_id):
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    url = f"{base_url_balls}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame()
    else:
        st.error(f"Balls fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# --- Streamlit app UI ---

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

            session_id_col = "sessionId" if "sessionId" in adhoc_sessions_df.columns else adhoc_sessions_df.columns[0]
            session_display_col = "sessionName" if "sessionName" in adhoc_sessions_df.columns else session_id_col

            session_map = dict(zip(adhoc_sessions_df[session_display_col], adhoc_sessions_df[session_id_col]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            chosen_session_id = session_map[session_choice]

            # Step 2: Fetch plays and balls data
            plays_df = fetch_plays(access_token, chosen_session_id)
            balls_df = fetch_balls(access_token, chosen_session_id)

            if plays_df.empty:
                st.warning("No plays data found for this session.")
            if balls_df.empty:
                st.warning("No balls data found for this session.")

            if not plays_df.empty and not balls_df.empty:
                st.subheader("Filter by Pitcher ID")

                # Get unique pitcher IDs from plays data
                pitcher_ids = plays_df["pitcher.id"].dropna().unique()
                selected_pitcher_ids = st.multiselect("Select Pitcher ID(s)", options=pitcher_ids)

                if selected_pitcher_ids:
                    # Filter plays by pitcher id
                    filtered_plays = plays_df[plays_df["pitcher.id"].isin(selected_pitcher_ids)]

                    # Filter balls by kind='Pitch' and playId in filtered plays
                    filtered_balls = balls_df[
                        (balls_df["kind"] == "Pitch") & 
                        (balls_df["playId"].isin(filtered_plays["playID"]))
                    ]

                    if filtered_plays.empty or filtered_balls.empty:
                        st.warning("No data found for selected pitcher(s) with kind 'Pitch'.")
                    else:
                        # Merge with plays as left table and balls as right table
                        combined_df = pd.merge(
                            filtered_plays,
                            filtered_balls,
                            left_on="playID",
                            right_on="playId",
                            suffixes=("_play", "_ball")
                        )

                        st.subheader("Combined Balls and Plays Data (Filtered by Pitcher ID)")
                        st.dataframe(combined_df)

                        csv = combined_df.to_csv(index=False)
                        st.download_button("Download Combined Data as CSV", csv, "trackman_combined_data.csv", "text/csv")

                else:
                    st.info("Select at least one pitcher ID to filter data.")

        else:
            st.warning("No 'Adhoc' sessions found in the selected date range.")
