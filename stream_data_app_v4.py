import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_play_url = api_secrets["base_url"]  # /game/plays
ball_url_base = api_secrets["balls_url_base"]  # new entry: /game/balls
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
    return response.json()["access_token"] if response.status_code == 200 else None

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
    return pd.DataFrame(response.json()) if response.status_code == 200 else pd.DataFrame()

# Fetch plays
@st.cache_data
def fetch_play_data(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_play_url}/{session_id}"
    r = requests.get(url, headers=headers)
    return pd.json_normalize(r.json()) if r.status_code == 200 else pd.DataFrame()

# Fetch balls
@st.cache_data
def fetch_ball_data(token, session_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{ball_url_base}/{session_id}"
    r = requests.get(url, headers=headers)
    return pd.json_normalize(r.json()) if r.status_code == 200 else pd.DataFrame()

# Streamlit UI
st.title("TrackMan Play + Ball Data Explorer")

date_from = st.date_input("Start Date", pd.to_datetime("2025-01-03"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        adhoc_sessions = sessions_df[sessions_df["sessionType"] == "Adhoc"]

        if not adhoc_sessions.empty:
            st.subheader("Select Game Session")
            session_map = dict(zip(adhoc_sessions["sessionName"], adhoc_sessions["sessionId"]))
            session_name = st.selectbox("Session", options=list(session_map.keys()))
            session_id = session_map[session_name]

            play_df = fetch_play_data(token, session_id)
            ball_df = fetch_ball_data(token, session_id)

            if not play_df.empty and not ball_df.empty:
                merged_df = pd.merge(play_df, ball_df, on="playId", suffixes=("_play", "_ball"), how="inner")

                st.subheader("Merged Play + Ball Data")
                st.dataframe(merged_df)

                # Filter UI
                filter_col = st.selectbox("Filter by column", merged_df.columns)

                if pd.api.types.is_numeric_dtype(merged_df[filter_col]):
                    min_val = float(merged_df[filter_col].min())
                    max_val = float(merged_df[filter_col].max())
                    selected_range = st.slider("Select range", min_val, max_val, (min_val, max_val))
                    filtered = merged_df[merged_df[filter_col].between(*selected_range)]
                else:
                    choices = st.multiselect("Select values", merged_df[filter_col].dropna().unique())
                    filtered = merged_df[merged_df[filter_col].isin(choices)] if choices else merged_df

                st.subheader("Filtered Data")
                st.dataframe(filtered)

                st.download_button("Download CSV", filtered.to_csv(index=False), "merged_data.csv", "text/csv")

            else:
                st.warning("Missing play or ball data for selected session.")
        else:
            st.warning("No Adhoc sessions in selected range.")
    else:
        st.error("Authentication failed.")
