import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
plays_url = api_secrets["plays_url"]
balls_url = api_secrets["balls_url"]
session_query_url = api_secrets["session_query_url"]

# --- API Authentication ---
@st.cache_data
def get_access_token():
    auth_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    response = requests.post(auth_url, data=auth_data)
    return response.json().get("access_token") if response.status_code == 200 else None

# --- Fetch Sessions ---
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

# --- Fetch Plays ---
@st.cache_data
def fetch_plays(token, session_id):
    url = f"{plays_url}/{session_id}"
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    response = requests.get(url, headers=headers)
    return pd.json_normalize(response.json()) if response.status_code == 200 else pd.DataFrame()

# --- Fetch Balls ---
@st.cache_data
def fetch_balls(token, session_id):
    url = f"{balls_url}/{session_id}"
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    response = requests.get(url, headers=headers)
    return pd.json_normalize(response.json()) if response.status_code == 200 else pd.DataFrame()

# --- Streamlit UI ---
st.title("⚾ TrackMan Play & Ball Data Explorer")

date_from = st.date_input("Start Date", pd.to_datetime("2025-01-03"))
date_to = st.date_input("End Date", pd.to_datetime("2025-01-30"))

if date_from and date_to:
    token = get_access_token()
    if token:
        sessions_df = fetch_sessions(token, f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z")
        if not sessions_df.empty:
            st.subheader("Select a Game Session")
            session_display_col = "sessionName" if "sessionName" in sessions_df.columns else sessions_df.columns[0]
            session_id_col = "sessionId" if "sessionId" in sessions_df.columns else sessions_df.columns[0]
            session_map = dict(zip(sessions_df[session_display_col], sessions_df[session_id_col]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            selected_session_id = session_map[session_choice]

            st.success(f"Selected Session ID: {selected_session_id}")

            # Fetch and merge plays + balls
            plays_df = fetch_plays(token, selected_session_id)
            balls_df = fetch_balls(token, selected_session_id)

            if not plays_df.empty and not balls_df.empty:
                merged_df = pd.merge(plays_df, balls_df, on="playId", suffixes=("_play", "_ball"))

                st.subheader("📊 Merged Play & Ball Data")
                st.dataframe(merged_df)

                # Filtering
                st.subheader("🔍 Filter Merged Data")
                filter_col = st.selectbox("Filter by Column", merged_df.columns)
                if pd.api.types.is_numeric_dtype(merged_df[filter_col]):
                    min_val, max_val = float(merged_df[filter_col].min()), float(merged_df[filter_col].max())
                    selected = st.slider("Select Range", min_val, max_val, (min_val, max_val))
                    filtered = merged_df[merged_df[filter_col].between(*selected)]
                else:
                    options = st.multiselect("Select values", merged_df[filter_col].dropna().unique())
                    filtered = merged_df[merged_df[filter_col].isin(options)] if options else merged_df

                st.subheader("📄 Filtered Merged Results")
                st.dataframe(filtered)

                st.download_button("📥 Download CSV", filtered.to_csv(index=False), "merged_data.csv", "text/csv")
            else:
                st.warning("No play or ball data found for this session.")

