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
    headers = {
        "Authorization": f"Bearer {token}"
    }
    url = f"{base_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    else:
        st.error(f"Plays fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls
@st.cache_data

def fetch_balls(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    url = f"https://dataapi.trackmanbaseball.com/api/v1/data/game/balls/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data)
    else:
        st.error(f"Balls fetch error: {response.status_code} - {response.text}")
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
        if not sessions_df.empty:
            # Add team names to session display
            sessions_df["sessionDisplay"] = sessions_df.apply(
                lambda row: f"{row.get('homeTeam', {}).get('name', 'Unknown')} vs {row.get('awayTeam', {}).get('name', 'Unknown')} ({row['sessionId'][:8]})",
                axis=1
            )
            session_choice = st.selectbox("Select Session", sessions_df["sessionDisplay"])
            session_id = sessions_df[sessions_df["sessionDisplay"] == session_choice]["sessionId"].values[0]

            play_df = fetch_plays(access_token, session_id)
            ball_df = fetch_balls(access_token, session_id)

            if not play_df.empty and not ball_df.empty:
                # Filter balls for kind == Pitch
                ball_df = ball_df[ball_df["kind"] == "Pitch"]

                # Merge data (plays left, balls right) on playID
                merged_df = pd.merge(play_df, ball_df, left_on="playID", right_on="playId", how="left")

                # Sort by utcDateTime
                merged_df["utcDateTime"] = pd.to_datetime(merged_df["utcDateTime"])
                merged_df = merged_df.sort_values(by="utcDateTime")

                # Add pitcher display name
                merged_df["pitcherDisplay"] = merged_df.apply(
                    lambda row: f"{row.get('pitcher.name', 'Unknown')} ({row.get('pitcher.id', 'NA')})", axis=1
                )
                pitcher_options = merged_df["pitcherDisplay"].dropna().unique()
                selected_pitchers = st.multiselect("Select Pitcher", options=pitcher_options)

                if selected_pitchers:
                    filtered_df = merged_df[merged_df["pitcherDisplay"].isin(selected_pitchers)]

                    st.subheader("Filtered Plays and Balls Data")
                    st.dataframe(filtered_df)

                    # Plotting
                    st.subheader("Pitch Metrics Line Plots")
                    numeric_cols = [
                        ("pitch.release.relSpeed", "Release Speed (mph)"),
                        ("pitch.release.spinRate", "Spin Rate (rpm)"),
                        ("pitch.release.extension", "Extension (ft)"),
                        ("pitch.movement.horzBreak", "Horizontal Break (in)"),
                        ("pitch.movement.vertBreak", "Vertical Break (in)"),
                        ("pitch.effectiveVelo", "Effective Velocity (mph)")
                    ]

                    for col, label in numeric_cols:
                        if col in filtered_df.columns:
                            fig, ax = plt.subplots()
                            sns.lineplot(
                                data=filtered_df,
                                x="utcDateTime",
                                y=col,
                                hue="pitcherDisplay",
                                marker="o",
                                ax=ax
                            )
                            ax.set_title(label)
                            ax.set_xlabel("Time")
                            ax.set_ylabel(label)
                            ax.legend(loc="best")
                            st.pyplot(fig)

                    st.download_button("Download CSV", filtered_df.to_csv(index=False), "filtered_pitch_data.csv", "text/csv")

                else:
                    st.warning("Please select at least one pitcher to view filtered data and plots.")
            else:
                st.warning("No play or ball data found for selected session.")
        else:
            st.warning("No sessions found in the selected date range.")
