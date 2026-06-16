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
