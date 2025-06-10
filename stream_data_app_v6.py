import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_plays_url = api_secrets["base_url"]
session_query_url = api_secrets["session_query_url"]

# Derive balls URL from plays URL
base_balls_url = base_plays_url.replace("/plays", "/balls")

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

# Fetch plays data
@st.cache_data
def fetch_plays(token, session_id):
    url = f"{base_plays_url}/{session_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Play data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls data
@st.cache_data
def fetch_balls(token, session_id):
    url = f"{base_balls_url}/{session_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.json_normalize(response.json())
    else:
        st.error(f"Balls data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Streamlit UI
st.title("TrackMan Session Explorer (Plays + Balls by Pitcher)")

# Step 1: Date range
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-03"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        if not sessions_df.empty:
            st.subheader("Select Game Session")
            session_map = {
                row["sessionName"] if "sessionName" in row else row["sessionId"]: row["sessionId"]
                for _, row in sessions_df.iterrows()
            }
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            chosen_session_id = session_map[session_choice]

            # Step 2: Fetch plays and balls data
            plays_df = fetch_plays(token, chosen_session_id)
            balls_df = fetch_balls(token, chosen_session_id)

            if not plays_df.empty and not balls_df.empty:
                st.subheader("Filter by Pitcher")

                # Pitcher ID selection
                pitcher_ids = plays_df["pitcher.id"].dropna().unique()
                selected_pitcher = st.selectbox("Select Pitcher ID", pitcher_ids)

                # Filter
                filtered_plays = plays_df[plays_df["pitcher.id"] == selected_pitcher]
                filtered_balls = balls_df[balls_df["playId"].isin(filtered_plays["playID"])]

                # Show results
                st.markdown("### Filtered Plays")
                st.dataframe(filtered_plays)

                st.download_button("Download Filtered Plays CSV", filtered_plays.to_csv(index=False), "filtered_plays.csv", "text/csv")

                st.markdown("### Filtered Balls")
                st.dataframe(filtered_balls)

                st.download_button("Download Filtered Balls CSV", filtered_balls.to_csv(index=False), "filtered_balls.csv", "text/csv")

                # Merge balls + plays on play ID
                combined_df = pd.merge(
                    filtered_balls,
                    filtered_plays,
                    left_on="playId",
                    right_on="playID",
                    suffixes=("_ball", "_play")
                )

                st.markdown("### Merged Balls + Plays Table")
                st.dataframe(combined_df)

                st.download_button("Download Merged CSV", combined_df.to_csv(index=False), "merged_balls_plays.csv", "text/csv")

            else:
                st.warning("No plays or balls data found for selected session.")
        else:
            st.warning("No sessions found in selected date range.")
