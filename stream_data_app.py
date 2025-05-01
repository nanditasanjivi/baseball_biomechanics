import streamlit as st
import pandas as pd
import requests
import json


api_secrets = st.secrets["trackman_api"]
auth_url = api_secrets["auth_url"]
client_id = api_secrets["client_id"]
client_secret = api_secrets["client_secret"]

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


# Function to fetch and normalize JSON data
@st.cache_data
def fetch_data(token):
    url = "https://dataapi.trackmanbaseball.com/api/v1/data/game/plays/abc"
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
            st.warning("Unexpected data format received.")
            return pd.DataFrame()
    else:
        st.error(f"Failed to fetch data: {response.status_code}")
        return pd.DataFrame()

# Main Streamlit App
st.title("TrackMan Game Play Data Viewer")

token = get_access_token()
if token:
    df = fetch_data(token)
    if not df.empty:
        st.subheader("Raw Data")
        st.dataframe(df)

        st.subheader("Filter Options")

        # Dynamic filtering for each column
        filter_col = st.selectbox("Choose a column to filter", df.columns)

        # Determine filter type based on dtype
        if pd.api.types.is_numeric_dtype(df[filter_col]):
            min_val = float(df[filter_col].min())
            max_val = float(df[filter_col].max())
            filter_range = st.slider("Filter range", min_val, max_val, (min_val, max_val))
            filtered_df = df[df[filter_col].between(filter_range[0], filter_range[1])]
        elif pd.api.types.is_datetime64_any_dtype(df[filter_col]):
            date_range = st.date_input("Date range", [])
            if len(date_range) == 2:
                filtered_df = df[df[filter_col].between(date_range[0], date_range[1])]
            else:
                filtered_df = df
        else:
            options = st.multiselect("Select values", df[filter_col].dropna().unique())
            filtered_df = df[df[filter_col].isin(options)] if options else df

        st.subheader("Filtered Data")
        st.dataframe(filtered_df)

        # Option to download filtered data
        st.download_button("Download Filtered Data as CSV", filtered_df.to_csv(index=False), "filtered_data.csv", "text/csv")
