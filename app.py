# app.py
import streamlit as st
import pandas as pd
import requests
import io

url = st.secrets["PRIVATE_CSV_URL"]

response = requests.get(url)
st.text(response.status_code)   # Should be 200
st.text(response.headers["Content-Type"])  # Should be 'text/csv' or 'application/octet-stream'
st.text(response.text[:500])  # Show the first 500 characters of the response



st.set_page_config(page_title="Baseball Data Viewer", layout="wide")

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
