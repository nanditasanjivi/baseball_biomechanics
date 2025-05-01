# app.py
import streamlit as st
import pandas as pd
import requests
import io



st.set_page_config(page_title="Baseball Data Viewer", layout="wide")

# Load preprocessed CSV
url = st.secrets["PRIVATE_CSV_URL"]

response = requests.get(url)
df = pd.read_csv(io.StringIO(response.text))

st.title("Baseball Data Dashboard")

# --- Filters ---
name_filter = st.text_input("Filter by Pitcher Name")
tagged_type = st.multiselect("Tagged Pitch Type", options=df['pitchTag_taggedPitchType'].dropna().unique())
auto_type = st.multiselect("Auto Pitch Type", options=df['pitchTag_autoPitchType'].dropna().unique())

filtered = df.copy()
if name_filter:
    filtered = filtered[filtered['pitcher_name'].str.contains(name_filter, case=False, na=False)]
if tagged_type:
    filtered = filtered[filtered['pitchTag_taggedPitchType'].isin(tagged_type)]
if auto_type:
    filtered = filtered[filtered['pitchTag_autoPitchType'].isin(auto_type)]

# --- Show Table ---
st.dataframe(filtered, use_container_width=True)
