import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import timedelta
import os
import io

from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(layout="wide")

# SAFE KALEIDO CHECK
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except:
    KALEIDO_AVAILABLE = False

# =========================
# LOGO
# =========================
logo_path = os.path.join(os.path.dirname(__file__), "Envision.png")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)

# =========================
# TITLE
# =========================
st.title("Temperature Analytics Report")

# =========================
# UPLOAD THE TEMPERATURE SCADA FILE
# =========================
st.sidebar.subheader("Upload SCADA File")
uploaded_file = st.sidebar.file_uploader(
    "Upload SCADA CSV",
    type=["csv"]
)

if uploaded_file is None:
    st.warning("Please upload SCADA file")
    st.stop()

site = st.sidebar.selectbox(
    "Select Site",
    list(SITE_CAPACITY.keys())
)

mode = st.sidebar.radio(
    "Select View",
    ["Temperature graph", "", "Show All Turbines"]
)

# =========================
# LOAD SCADA
# =========================
@st.cache_data(show_spinner=True)
def load_scada(file):

    chunksize = 200000

    chunks = pd.read_csv(
        file,
        chunksize=chunksize,
        low_memory=False,
        engine="c"
    )

    df = pd.concat(chunks, ignore_index=True)

    df.columns = df.columns.str.strip()

    wind_col = [
        c for c in df.columns
        if "wind" in c.lower()
    ][0]

    power_col = [
        c for c in df.columns
        if "power" in c.lower()
        or "active" in c.lower()
    ][0]

    time_col = [
        c for c in df.columns
        if "time" in c.lower()
    ][0]

    pitch_col = [
        c for c in df.columns 
        if "pitch" in c.lower()
    ][0]

    df[time_col] = pd.to_datetime(
        df[time_col],
        errors="coerce"
    )

    df[wind_col] = pd.to_numeric(
        df[wind_col],
        errors="coerce"
    )

    df[power_col] = pd.to_numeric(
        df[power_col],
        errors="coerce"
    )

    df[pitch_col] = pd.to_numeric(
        df[pitch_col],
        errors = "coerce"
    )

    df = df.dropna(
        subset=[
            wind_col,
            power_col,
            time_col,
            pitch_col
        ]
    )

    df["Name"] = df["Name"].astype(str).str.strip()

    return df, wind_col, power_col, time_col, pitch_col

with st.spinner("Loading SCADA file..."):
    df, wind_col, power_col, time_col, pitch_col = load_scada(uploaded_file)
