import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="EE4 Dashboard", layout="wide")
st.title("EE4 Dashboard - Volume + Efficiency (PPT Logic)")

# -----------------------------
# Helpers
# -----------------------------
def to_dt(df: pd.DataFrame, col: str) -> None:
    """Parse a dataframe column into datetime (in-place)."""
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

def require_cols(df: pd.DataFrame, cols: list[str], block_name: str) -> bool:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.warning(f"[{block_name}] Missing columns: {missing}. This section will be skipped.")
        return False
    return True

def make_bar(df_counts: pd.DataFrame, x: str, y: str, title: str):
    fig = px.bar(df_counts, x=x, y=y, text=y, title=title)
    fig.update_traces(textposition="outside")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig

def on_time_completion_rate(completed_not_overdue: int, overdue_completed: int, overdue_not_completed: int) -> float:
    """
    PPT formula:
    On-time completion rate = Completed not overdue /
        (Completed not overdue + Overdue has been completed + Overdue not completed)
    """
    denom = completed_not_overdue + overdue_completed + overdue_not_completed
    if denom == 0:
        return np.nan
    return completed_not_overdue / denom

def compute_due_date(start_dt: pd.Series, target_days: int) -> pd.Series:
    """Due date = start date + target days (calendar days)."""
    return start_dt + pd.to_timedelta(target_days, unit="D")

def classify_sla(close_dt: pd.Series, due_dt: pd.Series) -> pd.Series:
    """
    Returns one of:
      - completed_not_overdue
      - overdue_completed
      - overdue_not_completed
      - unknown
    """
    out = pd.Series(["unknown"] * len(close_dt), index=close_dt.index)

    # completed cases
    mask_completed = close_dt.notna() & due_dt.notna()
    out.loc[mask_completed & (close_dt <= due_dt)] = "completed_not_overdue"
    out.loc[mask_completed & (close_dt > due_dt)] = "overdue_completed"

    # not completed but due date passed
    mask_open_overdue = close_dt.isna() & due_dt.notna() & (pd.Timestamp.now() > due_dt)
    out.loc[mask_open_overdue] = "overdue_not_completed"

    return out

# -----------------------------
# Upload data
# -----------------------------
uploaded = st.file_uploader("Upload EE cases data (CSV/XLSX)", type=["csv", "xlsx"])
if uploaded is None:
    st.info("Upload a case export file to continue.")
    st.stop()

if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded)

st.subheader("Data preview")
st.dataframe(df.head(30), use_container_width=True)

# -----------------------------
# Column mapping (user selects)
# -----------------------------
st.sidebar.header("Column mapping (set once)")

# A flexible approach: user chooses columns from dropdowns (safer than guessing)
all_cols = ["(none)"] + list(df.columns)

case_date_col = st.sidebar.selectbox("Case date for volume charts", all_cols, index=0)
case_type_col = st.sidebar.selectbox("Case type (Incident/Problem)", all_cols, index=0)
close_date_col = st.sidebar.selectbox("Close date / Closing time", all_cols, index=0)
exception_col = st.sidebar.selectbox("Exception approved? (optional)", all_cols, index=0)

st.sidebar.markdown("---")
st.sidebar.caption("Incident node date columns (optional; only needed for KPI):")
incident_occur_col = st.sidebar.selectbox("Incident Occurrence date", all_cols, index=0)
incident_assign_col = st.sidebar.selectbox("Incident Assignment date", all_cols, index=0)
incident_review_col = st.sidebar.selectbox("Incident Review date", all_cols, index=0)

st.sidebar.markdown("---")
st.sidebar.caption("Problem node date columns (optional; only needed for KPI):")
problem_create_col = st.sidebar.selectbox("Problem Create date", all_cols, index=0)
problem_rca_review_col = st.sidebar.selectbox("RCA/Measures Review date", all_cols, index=0)

# Convert selected "(none)" to None
def none_to_none(x): return None if x == "(none)" else x
case_date_col = none_to_none(case_date_col)
case_type_col = none_to_none(case_type_col)
close_date_col = none_to_none(close_date_col)
exception_col = none_to_none(exception_col)
incident_occur_col = none_to_none(incident_occur_col)
incident_assign_col = none_to_none(incident_assign_col)
incident_review_col = none_to_none(incident_review_col)
problem_create_col = none_to_none(problem_create_col)
problem_rca_review_col = none_to_none(problem_rca_review_col)

# Parse datetimes
for c in [case_date_col, close_date_col,
          incident_occur_col, incident_assign_col, incident_review_col,
          problem_create_col, problem_rca_review_col]:
    if c:
        to_dt(df, c)

# Optional filter: date range based on case_date_col
if not case_date_col:
    st.error("Please map 'Case date for volume charts' in the sidebar.")
    st.stop()

df = df.dropna(subset=[case_date_col]).copy()

with st.sidebar:
    st.markdown("---")
    st.header("Filters")
    min_d = df[case_date_col].min().date()
    max_d = df[case_date_col].max().date()
    start_date, end_date = st.date_input(
        "Date range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d
    )

df = df[(df[case_date_col].dt.date >= start_date) & (df[case_date_col].dt.date <= end_date)].copy()

if case_type_col:
    types = sorted([x for x in df[case_type_col].dropna().unique().tolist()])
    selected_types = st.sidebar.multiselect("Case type filter", options=types, default=types)
    df = df[df[case_type_col].isin(selected_types)].copy()

# -----------------------------
# 1) Volume charts (Year/Month/Week)
# -----------------------------
st.header("A) Case Volume (Bar Charts)")

# LOGIC formulas:
# year_count(Y)  = number of rows where year(case_date)=Y
# month_count(M) = number of rows where year_month(case_date)=M
# week_count(W)  = number of rows where iso_year_week(case_date)=W
df["year"] = df[case_date_col].dt.year
df["year_month"] = df[case_date_col].dt.to_period("M").astype(str)
iso = df[case_date_col].dt.isocalendar()
df["iso_year_week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

year_counts = df.groupby("year", as_index=False).size().rename(columns={"size": "case_count"}).sort_values("year")
month_counts = df.groupby("year_month", as_index=False).size().rename(columns={"size": "case_count"}).sort_values("year_month")
week_counts = df.groupby("iso_year_week", as_index=False).size().rename(columns={"size": "case_count"}).sort_values("iso_year_week")

c1, c2, c3 = st.columns(3)
with c1:
    st.plotly_chart(make_bar(year_counts, "year", "case_count", "Year-wise number of cases"), use_container_width=True)
with c2:
    fig = make_bar(month_counts, "year_month", "case_count", "Month-wise number of cases")
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
with c3:
    fig = make_bar(week_counts, "iso_year_week", "case_count", "Week-wise number of cases (ISO week)")
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 2) Efficiency KPI (PPT logic)
# -----------------------------
st.header("B) Efficiency KPI (PPT Formula Logic)")

st.markdown(
    """
From the PPT:

**On-time completion rate**  
`OnTimeRate = CompletedNotOverdue / (CompletedNotOverdue + OverdueCompleted + OverdueNotCompleted)`

This section computes OnTimeRate by building SLA **due dates** from target days and comparing close date vs due date.
"""
)

# We'll compute an example KPI rate based on a selected "node"
node = st.selectbox(
    "Select KPI node to compute On-time completion rate (based on available columns)",
    [
        "Incident: Submit (occurrence -> submission)",
        "Incident: Assignment (occurrence -> assignment)",
        "Incident: Review (assignment -> review)",
        "Incident: Closing (review -> close)",
        "Problem: Create problem (incident containment -> problem create)",
        "Problem: RCA & Preparation measures (create -> rca review)",
        "Problem: Closing (create -> close)"
    ]
)

# Targets from PPT (you can adjust if your org uses different split days):
# Incident split targets shown:
# Submit <=1 day; Assignment <=2; Review (containment+review in PPT) <=2 for review step; Closing <=25; Effect confirmation <=5
# Problem split targets shown:
# Create problem <=10; Review RCA & measures <=10; Closing time - create time <=30 (also shows <=100 for RCA & preparation measures in one column)
targets = {
    "Incident: Submit (occurrence -> submission)": 1,
    "Incident: Assignment (occurrence -> assignment)": 2,
    "Incident: Review (assignment -> review)": 2,
    "Incident: Closing (review -> close)": 25,
    "Problem: Create problem (incident containment -> problem create)": 10,
    "Problem: RCA & Preparation measures (create -> rca review)": 10,
    "Problem: Closing (create -> close)": 30,
}

target_days = targets[node]
st.caption(f"Target days used for this node (from PPT split targets): {target_days} day(s)")

# Determine start/end columns based on node
start_col = None
end_col = None

if node == "Incident: Submit (occurrence -> submission)":
    # We don't have explicit submission date column mapped; fallback to case_date_col as "submission" if needed.
    # For accurate KPI: map a submission date in your export and use that instead.
    start_col = incident_occur_col
    end_col = case_date_col  # fallback (often create/submit date)
elif node == "Incident: Assignment (occurrence -> assignment)":
    start_col = incident_occur_col
    end_col = incident_assign_col
elif node == "Incident: Review (assignment -> review)":
    start_col = incident_assign_col
    end_col = incident_review_col
elif node == "Incident: Closing (review -> close)":
    start_col = incident_review_col
    end_col = close_date_col
elif node == "Problem: Create problem (incident containment -> problem create)":
    # PPT references "Create time – Incident Containment-Action time"
    # If you don't have containment-action time, you must map it; using occurrence as fallback is NOT ideal.
    start_col = incident_occur_col
    end_col = problem_create_col
elif node == "Problem: RCA & Preparation measures (create -> rca review)":
    start_col = problem_create_col
    end_col = problem_rca_review_col
elif node == "Problem: Closing (create -> close)":
    start_col = problem_create_col
    end_col = close_date_col

# Validate needed columns
needed = [c for c in [start_col, end_col] if c]
if len(needed) < 2 or (start_col not in df.columns) or (end_col not in df.columns):
    st.warning(
        "Not enough mapped columns to compute this KPI node. "
        "Map the required start/end date columns in the sidebar."
    )
else:
    work = df.copy()

    # Optional: exclude exceptions if exception_col is provided and user chooses
    if exception_col and exception_col in work.columns:
        exclude_exceptions = st.checkbox("Exclude approved exceptions from KPI", value=True)
        if exclude_exceptions:
            # common representations: True/False, Y/N, 1/0
            ex = work[exception_col].astype(str).str.lower()
            work = work[~ex.isin(["1", "true", "yes", "y"])].copy()

    # Build due date from start date + target days
    work["kpi_start"] = work[start_col]
    work["kpi_end"] = work[end_col]  # acts like "close" for that node
    work = work.dropna(subset=["kpi_start"]).copy()

    work["due_date"] = compute_due_date(work["kpi_start"], target_days)
    # classify completion as per PPT buckets
    work["sla_bucket"] = classify_sla(work["kpi_end"], work["due_date"])

    completed_not_overdue = int((work["sla_bucket"] == "completed_not_overdue").sum())
    overdue_completed = int((work["sla_bucket"] == "overdue_completed").sum())
    overdue_not_completed = int((work["sla_bucket"] == "overdue_not_completed").sum())

    rate = on_time_completion_rate(completed_not_overdue, overdue_completed, overdue_not_completed)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Completed not overdue", completed_not_overdue)
    k2.metric("Overdue completed", overdue_completed)
    k3.metric("Overdue not completed", overdue_not_completed)
    k4.metric("On-time completion rate", "-" if np.isnan(rate) else f"{rate:.2%}")

    # Visual breakdown
    bucket_counts = (
        work.groupby("sla_bucket", as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values("count", ascending=False)
    )
    fig = px.bar(bucket_counts, x="sla_bucket", y="count", text="count",
                 title="SLA bucket distribution (for selected node)")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Show KPI calculation sample rows"):
        show_cols = [case_date_col]
        if case_type_col: show_cols.append(case_type_col)
        show_cols += [start_col, end_col, "due_date", "sla_bucket"]
        show_cols = [c for c in show_cols if c in work.columns]
        st.dataframe(work[show_cols].head(50), use_container_width=True)
