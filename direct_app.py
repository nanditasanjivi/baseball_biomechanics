# app.py
import requests
import streamlit as st
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StringType, StructType, StructField

# Initialize SparkSession
spark = SparkSession.builder \
    .appName("Trackman Data Stream") \
    .master("local[*]") \
    .getOrCreate()

# Streamlit UI
st.title("Trackman Baseball Data Viewer")

# Authenticate and Get Access Token
@st.cache_data(show_spinner=False)
def get_access_token():
    auth_url = "https://login.trackmanbaseball.com/connect/token"
    auth_data = {
    "client_id": "PRIVATE_CLIENT_ID",
    "client_secret": "PRIVATE_CLIENT_SECRET",
    "grant_type": "client_credentials"
    }
    auth_response = requests.post(auth_url, data=auth_data)
    if auth_response.status_code == 200:
        return auth_response.json().get("access_token")
    else:
        st.error(f"Authentication Failed: {auth_response.status_code}")
        return None

access_token = get_access_token()


# Get Video Metadata
@st.cache_data(show_spinner=False)
def get_video_metadata(token):
    video_metadata_url = "METADATA_URL"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    response = requests.get(video_metadata_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Data Fetch Failed: {response.status_code}")
        return []

# Fetch data
if access_token:
    raw_data = get_video_metadata(access_token)
    
    if isinstance(raw_data, list) and len(raw_data) > 0:
        # Create Spark DataFrame
        df = spark.createDataFrame(raw_data)

        # Show full schema
        if st.checkbox("Show Data Schema"):
            st.text(df.printSchema())

        # Convert to Pandas for Streamlit display (since Streamlit does not natively render Spark DataFrames)
        st.dataframe(df.toPandas())

        # Filter options
        columns = df.columns
        selected_column = st.selectbox("Select Column to Filter:", columns)
        if selected_column:
            unique_values = [row[selected_column] for row in df.select(selected_column).distinct().collect()]
            filter_value = st.selectbox(f"Filter {selected_column}:", unique_values)
            if filter_value:
                filtered_df = df.filter(col(selected_column) == filter_value)
                st.dataframe(filtered_df.toPandas())

    else:
        st.warning("No data available for the session.")

