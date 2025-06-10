import streamlit as st
import pandas as pd
import requests

# Load secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_play_url = api_secrets["base_url"]  # plays endpoint
session_query_url = api_secrets["session_query_url"]
base_ball_url = base_play_url.replace("/plays", "/balls")  # balls endpoint

# Authenticate
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

# Fetch session metadata and flatten teams properly
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
        data = response.json()
        df = pd.json_normalize(data)
        # Extract nested team names properly
        df["homeTeam.name"] = df["homeTeam"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
        df["awayTeam.name"] = df["awayTeam"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
        return df
    else:
        st.error(f"Session fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch plays data
@st.cache_data(show_spinner=False)
def fetch_play_data(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    url = f"{base_play_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame()
    else:
        st.error(f"Play data fetch error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch balls data
@st.cache_data(show_spinner=False)
def fetch_ball_data(token, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    url = f"{base_ball_url}/{session_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        df = pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame()
        # Filter to only 'Pitch' kind
        if not df.empty:
            df = df[df["kind"] == "Pitch"]
        return df
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

            # Display teams with sessionId for clarity
            adhoc_sessions_df["session_display"] = (
                adhoc_sessions_df["homeTeam.name"].fillna("Unknown Home") + " vs " +
                adhoc_sessions_df["awayTeam.name"].fillna("Unknown Away") +
                " (" + adhoc_sessions_df["sessionId"] + ")"
            )

            session_map = dict(zip(adhoc_sessions_df["session_display"], adhoc_sessions_df["sessionId"]))
            session_choice = st.selectbox("Session", options=list(session_map.keys()))
            chosen_session_id = session_map[session_choice]

            # Fetch plays and balls for selected session
            play_df = fetch_play_data(access_token, chosen_session_id)
            ball_df = fetch_ball_data(access_token, chosen_session_id)

            if not play_df.empty and not ball_df.empty:
                # Prepare pitcher filter with pitcher name and id
                play_df["pitcherID"] = play_df["pitcher.id"]
                play_df["pitcherName"] = play_df["pitcher.name"]
                pitchers = play_df[["pitcherID", "pitcherName"]].drop_duplicates()
                pitchers["display"] = pitchers["pitcherName"] + " (" + pitchers["pitcherID"] + ")"
                pitcher_map = dict(zip(pitchers["display"], pitchers["pitcherID"]))

                st.subheader("Filter by Pitcher")
                selected_pitchers = st.multiselect("Select Pitcher(s)", options=list(pitcher_map.keys()))

                if selected_pitchers:
                    selected_ids = [pitcher_map[name] for name in selected_pitchers]
                    filtered_plays = play_df[play_df["pitcherID"].isin(selected_ids)]
                    filtered_balls = ball_df[ball_df["playId"].isin(filtered_plays["playID"])]

                    # Merge balls first, then plays (as requested)
                    merged_df = pd.merge(
                        filtered_balls,
                        filtered_plays,
                        left_on="playId",
                        right_on="playID",
                        how="inner",
                        suffixes=("_ball", "_play")
                    )

                    # Sort by utcDateTime chronologically
                    merged_df = merged_df.sort_values("utcDateTime")

                    st.subheader("Merged Play and Ball Data")
                    st.dataframe(merged_df)

                    csv_data = merged_df.to_csv(index=False)
                    st.download_button("Download CSV", csv_data, "merged_filtered.csv", "text/csv")
                else:
                    st.info("Select at least one pitcher to filter data.")
            else:
                st.warning("No play or ball data found for this session.")
        else:
            st.warning("No Adhoc sessions found in the selected date range.")
