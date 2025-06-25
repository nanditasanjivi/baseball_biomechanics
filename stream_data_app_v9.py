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
@st.cache_data(show_spinner=False)
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

# Fetch plays
@st.cache_data(show_spinner=False)
def fetch_play_data(token, session_id: str):
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
@st.cache_data(show_spinner=False)
def fetch_ball_data(token, session_id: str):
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
            sessions_df = sessions_df[sessions_df["sessionType"] == "Adhoc"]
            sessions_df = sessions_df[
                sessions_df.apply(
                    lambda row: row.get('homeTeam', {}).get('shortName') == 'CSD_TRI' or 
                                row.get('awayTeam', {}).get('shortName') == 'CSD_TRI',
                    axis=1
                )
            ]

            sessions_df["sessionDisplay"] = sessions_df.apply(
                lambda row: f"{row.get('homeTeam', {}).get('name', 'Unknown')} vs {row.get('awayTeam', {}).get('name', 'Unknown')} ({row['sessionId']})",
                axis=1
            )

            session_display_multi = st.multiselect("Select Sessions", sessions_df["sessionDisplay"])

            all_merged_dfs = []

            for session_display in session_display_multi:
                session_id = session_display.split('(')[-1].split(')')[0]
                play_df = fetch_play_data(access_token, session_id)
                ball_df = fetch_ball_data(access_token, session_id)

                if not play_df.empty and not ball_df.empty:
                    ball_df = ball_df[ball_df['kind'] == 'Pitch']
                    merged_df = pd.merge(ball_df, play_df, how="left", left_on="playId", right_on="playID")
                    merged_df = merged_df.dropna(subset=["pitcher_id"])
                    merged_df["utcDateTime"] = pd.to_datetime(merged_df["utcDateTime"])
                    merged_df["sessionId"] = session_id
                    all_merged_dfs.append(merged_df)

            if all_merged_dfs:
                merged_df_all = pd.concat(all_merged_dfs).sort_values("utcDateTime")

                # Create continuous timeline
                t0 = merged_df_all["utcDateTime"].min()
                merged_df_all["relativeTime"] = (merged_df_all["utcDateTime"] - t0).dt.total_seconds()

                merged_df_all['pitcher_display'] = merged_df_all['pitcher_name'] + " (" + merged_df_all['pitcher_id'].astype(str) + ")"
                pitcher_display = st.selectbox("Select Pitcher", merged_df_all['pitcher_display'].dropna().unique())
                selected_pitcher_id = pitcher_display.split('(')[-1].replace(')', '').strip()

                filtered_df = merged_df_all[merged_df_all['pitcher_id'] == selected_pitcher_id]

                st.subheader("Filtered Balls and Plays Data")
                st.dataframe(filtered_df)

                st.download_button("Download CSV", filtered_df.to_csv(index=False), "filtered.csv", "text/csv")

                if not filtered_df.empty:
                    st.subheader("Pitch Charts Over Continuous Time")

                    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
                    plt.subplots_adjust(hspace=0.5, wspace=0.4)

                    sns.lineplot(x='relativeTime', y='pitch_release_relSpeed', data=filtered_df, ax=axs[0, 0])
                    axs[0, 0].set_title("Pitch Velocity (Release Speed)")
                    axs[0, 0].set_xlabel("Time (s)")

                    sns.lineplot(x='relativeTime', y='pitch_release_spinRate', data=filtered_df, ax=axs[0, 1])
                    axs[0, 1].set_title("Spin Rate")
                    axs[0, 1].set_xlabel("Time (s)")

                    if 'hit_launchSpeed' in filtered_df.columns:
                        sns.lineplot(x='relativeTime', y='hit_launchSpeed', data=filtered_df, ax=axs[1, 0])
                        axs[1, 0].set_title("Exit Velocity")
                        axs[1, 0].set_xlabel("Time (s)")
                    else:
                        axs[1, 0].set_visible(False)

                    if 'hit_launchAngle' in filtered_df.columns:
                        sns.lineplot(x='relativeTime', y='hit_launchAngle', data=filtered_df, ax=axs[1, 1])
                        axs[1, 1].set_title("Launch Angle")
                        axs[1, 1].set_xlabel("Time (s)")
                    else:
                        axs[1, 1].set_visible(False)

                    st.pyplot(fig)
            else:
                st.warning("No valid play or ball data found in selected sessions.")
        else:
            st.warning("No Adhoc sessions found for the selected date range.")
