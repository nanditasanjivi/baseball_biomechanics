import streamlit as st
import pandas as pd
import requests

# Load API credentials from Streamlit secrets
api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]
base_url = api_secrets["base_url"]

# Function to authenticate and get access token
@st.cache_data
def get_access_token():
    auth_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    response = requests.post(auth_url, data=auth_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        st.error(f"Authentication failed: {response.status_code}")
        return None

# Function to fetch data from TrackMan API
@st.cache_data
def fetch_data(token, session_id):
    url = f"{base_url}/{session_id}"  # Construct URL using base_url from secrets
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            df = pd.json_normalize(data)
            return df
        else:
            st.warning("Unexpected response format.")
            return pd.DataFrame()
    else:
        st.error(f"Failed to fetch data: {response.status_code}")
        return pd.DataFrame()

# --- Streamlit App UI ---
st.title("🏟️ TrackMan Game Play Viewer")

# Input session ID
session_id = st.text_input("Enter TrackMan Game Session ID", value="abc")

if session_id:
    access_token = get_access_token()

    if access_token:
        df = fetch_data(access_token, session_id)

        if not df.empty:
            st.subheader("📊 Raw Data")
            st.dataframe(df)

            st.subheader("🔍 Filter Data")

            # Column selector
            filter_col = st.selectbox("Choose a column to filter", df.columns)

            if pd.api.types.is_numeric_dtype(df[filter_col]):
                min_val = float(df[filter_col].min())
                max_val = float(df[filter_col].max())
                selected_range = st.slider("Select numeric range", min_val, max_val, (min_val, max_val))
                filtered_df = df[df[filter_col].between(selected_range[0], selected_range[1])]

            elif pd.api.types.is_datetime64_any_dtype(df[filter_col]):
                df[filter_col] = pd.to_datetime(df[filter_col])
                dates = st.date_input("Select date range", [])
                if len(dates) == 2:
                    filtered_df = df[df[filter_col].between(dates[0], dates[1])]
                else:
                    filtered_df = df

            else:
                options = st.multiselect("Select values", df[filter_col].dropna().unique())
                filtered_df = df[df[filter_col].isin(options)] if options else df

            st.subheader("📄 Filtered Data")
            st.dataframe(filtered_df)

            # Download option
            st.download_button("📥 Download Filtered CSV", filtered_df.to_csv(index=False), "filtered_data.csv", "text/csv")

        else:
            st.warning("No data returned. Check the session ID.")
