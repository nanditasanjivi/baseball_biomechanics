import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil import parser

st.title("TrackMan Game Data Viewer")

# Load secrets
client_id = st.secrets["trackman_api"]["client_id"]
client_secret = st.secrets["trackman_api"]["client_secret"]
auth_url = st.secrets["trackman_api"]["auth_url"]
base_url = st.secrets["trackman_api"]["base_url"]
session_query_url = st.secrets["trackman_api"]["session_query_url"]

# Get access token
def get_access_token():
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    response = requests.post(auth_url, data=data)
    return response.json().get("access_token")

# Query sessions
def get_sessions(token, start_date, end_date):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "text/plain",
        "Content-Type": "application/json-patch+json"
    }
    body = {
        "sessionType": "All",
        "utcDateFrom": start_date,
        "utcDateTo": end_date
    }
    res = requests.post(session_query_url, headers=headers, json=body)
    return res.json()

# Get plays for a session
def get_plays(session_id, token):
    url = f"https://dataapi.trackmanbaseball.com/api/v1/data/game/plays/{session_id}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    return res.json()

# Get balls for a session
def get_balls(session_id, token):
    url = f"https://dataapi.trackmanbaseball.com/api/v1/data/game/balls/{session_id}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    return res.json()

# Inputs
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")

if start_date and end_date:
    token = get_access_token()
    sessions = get_sessions(token, f"{start_date}T00:00:00Z", f"{end_date}T23:59:59Z")

    session_options = {
        f"{s['homeTeam'].get('name', 'Unknown')} vs {s['awayTeam'].get('name', 'Unknown')} ({s['sessionId']})": s['sessionId']
        for s in sessions
    }

    selected_session_label = st.selectbox("Select a session", list(session_options.keys()))
    selected_session_id = session_options[selected_session_label]

    plays = get_plays(selected_session_id, token)
    balls = get_balls(selected_session_id, token)

    plays_df = pd.json_normalize(plays)
    balls_df = pd.json_normalize(balls)
    balls_df = balls_df[balls_df['kind'] == 'Pitch']

    # Merge with playID
    merged_df = pd.merge(plays_df, balls_df, how='right', left_on='playID', right_on='playId')

    # Show pitcher options
    merged_df['pitcher_display'] = merged_df['pitcher.name'] + ' (' + merged_df['pitcher.id'].astype(str) + ')'
    pitcher_options = merged_df[['pitcher_display', 'pitcher.id']].drop_duplicates().dropna()
    selected_pitcher_display = st.selectbox("Select a pitcher", pitcher_options['pitcher_display'])
    selected_pitcher_id = pitcher_options[pitcher_options['pitcher_display'] == selected_pitcher_display]['pitcher.id'].values[0]

    # Filter by pitcherID
    filtered_df = merged_df[merged_df['pitcher.id'] == selected_pitcher_id].sort_values(by='utcDateTime')

    st.subheader("Filtered Play & Ball Data")
    st.dataframe(filtered_df)

    # Plotting
    if not filtered_df.empty:
        st.subheader("Pitch Metrics Over Time")

        filtered_df['utcDateTime'] = pd.to_datetime(filtered_df['utcDateTime'])

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(filtered_df['utcDateTime'], filtered_df['pitch.release.relSpeed'], marker='o', label='Release Speed (mph)')
        ax.plot(filtered_df['utcDateTime'], filtered_df['pitch.release.spinRate'], marker='x', label='Spin Rate (rpm)')
        ax.set_title('Pitch Metrics Over Time')
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)

        st.subheader("Additional Pitch Metrics")
        col1, col2 = st.columns(2)

        with col1:
            fig1, ax1 = plt.subplots()
            ax1.plot(filtered_df['utcDateTime'], filtered_df['pitch.release.extension'], marker='s', color='green')
            ax1.set_title('Extension Over Time')
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Extension (ft)')
            ax1.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(fig1)

        with col2:
            fig2, ax2 = plt.subplots()
            ax2.plot(filtered_df['utcDateTime'], filtered_df['pitch.movement.vertBreak'], marker='^', color='purple', label='Vertical Break')
            ax2.plot(filtered_df['utcDateTime'], filtered_df['pitch.movement.horzBreak'], marker='v', color='orange', label='Horizontal Break')
            ax2.set_title('Pitch Break Over Time')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Break (inches)')
            ax2.legend()
            ax2.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(fig2)
