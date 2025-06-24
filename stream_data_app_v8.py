import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns

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
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(auth_url, data=auth_data, headers=headers)
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

# Fetch plays
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
        return pd.json_normalize(data, sep="_")
    else:
        st.error(f"Play data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls
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
        return pd.json_normalize(data, sep="_")
    else:
        st.error(f"Ball data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Streamlit UI
st.title("TrackMan Game Data Explorer")

# Step 1: Date Range
date_from = st.date_input("Start Date", pd.to_datetime("2025-01-03"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    access_token = get_access_token()
    if access_token:
        sessions_df = fetch_sessions(access_token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        if not sessions_df.empty:
            # Filter Adhoc sessions only
            sessions_df = sessions_df[sessions_df["sessionType"] == "Adhoc"]

            # Keep only sessions where CSD_TRI is home or away
            sessions_df = sessions_df[
                sessions_df.apply(
                    lambda row: row.get('homeTeam', {}).get('shortName') == 'CSD_TRI' or 
                                row.get('awayTeam', {}).get('shortName') == 'CSD_TRI',
                    axis=1
                )
            ]

            # Display format: Home vs Away (sessionId)
            sessions_df["sessionDisplay"] = sessions_df.apply(
                lambda row: f"{row.get('homeTeam', {}).get('name', 'Unknown')} vs {row.get('awayTeam', {}).get('name', 'Unknown')} ({row['sessionId'][:8]})",
                axis=1
            )

            session_display = st.selectbox("Select Session", sessions_df["sessionDisplay"])
            chosen_session_id = session_display.split('(')[-1].split(')')[0]

            play_df = fetch_play_data(access_token, chosen_session_id)
            ball_df = fetch_ball_data(access_token, chosen_session_id)

            if not play_df.empty and not ball_df.empty:
                ball_df = ball_df[ball_df['kind'] == 'Pitch']

                # Merge ball and play data using playId
                merged_df = pd.merge(ball_df, play_df, how="left", left_on="playId", right_on="playID")
                merged_df = merged_df.dropna(subset=["pitcher_id"])
                merged_df["utcDateTime"] = pd.to_datetime(merged_df["utcDateTime"])
                merged_df = merged_df.sort_values("utcDateTime")

                # Format for pitcher dropdown
                merged_df['pitcher_display'] = merged_df['pitcher_name'] + " (" + merged_df['pitcher_id'].astype(str) + ")"
                pitcher_display = st.selectbox("Select Pitcher", merged_df['pitcher_display'].dropna().unique())
                selected_pitcher_id = pitcher_display.split('(')[-1].replace(')', '').strip()

                # Filter by pitcher ID
                filtered_df = merged_df[merged_df['pitcher_id'] == selected_pitcher_id]

                st.subheader("Filtered Balls and Plays Data")
                st.dataframe(filtered_df)

                st.download_button("Download CSV", filtered_df.to_csv(index=False), "filtered.csv", "text/csv")

                # Plotting
                if not filtered_df.empty:
                    st.subheader("Pitch Charts Over Time")

                    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
                    plt.subplots_adjust(hspace=0.5, wspace=0.4)

                    sns.lineplot(x='utcDateTime', y='pitch_release_relSpeed', data=filtered_df, ax=axs[0, 0])
                    axs[0, 0].set_title("Pitch Velocity (Release Speed)")
                    axs[0, 0].tick_params(axis='x', rotation=45)

                    sns.lineplot(x='utcDateTime', y='pitch_release_spinRate', data=filtered_df, ax=axs[0, 1])
                    axs[0, 1].set_title("Spin Rate")
                    axs[0, 1].tick_params(axis='x', rotation=45)

                    if 'hit_launchSpeed' in filtered_df.columns:
                        sns.lineplot(x='utcDateTime', y='hit_launchSpeed', data=filtered_df, ax=axs[1, 0])
                        axs[1, 0].set_title("Exit Velocity")
                        axs[1, 0].tick_params(axis='x', rotation=45)
                    else:
                        axs[1, 0].set_visible(False)

                    if 'hit_launchAngle' in filtered_df.columns:
                        sns.lineplot(x='utcDateTime', y='hit_launchAngle', data=filtered_df, ax=axs[1, 1])
                        axs[1, 1].set_title("Launch Angle")
                        axs[1, 1].tick_params(axis='x', rotation=45)
                    else:
                        axs[1, 1].set_visible(False)

                    st.pyplot(fig)

            else:
                st.warning("No play or ball data found for this session.")
        else:
            st.warning("No Adhoc sessions found for the selected date range.")
