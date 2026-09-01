# --- Imports & Path Setup ---
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from scripts.db import engine

# --- Page Configuration ---
st.set_page_config(
    page_title="Traffy Fondue Analytics Dashboard",
    layout="wide"
)

st.title("Traffy Fondue Analytics Dashboard")
st.markdown("ระบบสรุปภาพรวมและวิเคราะห์ข้อมูลเรื่องร้องเรียนเมือง กรุงเทพมหานคร")

# --- Cached Data Loading Functions ---
@st.cache_data
def load_summary_data():
    """ดึงข้อมูล Fact และ Location เพื่อทำ Visualization สรุปภาพรวม"""
    query = """
        SELECT 
            f.ticket_id,
            f.state,
            COALESCE(l.district, 'ไม่ระบุเขต') AS district
        FROM fact_tickets f
        LEFT JOIN dim_location l ON f.location_id = l.location_id
    """
    return pd.read_sql(query, engine)

@st.cache_data
def load_table_data(table_name: str):
    """ดึงข้อมูลตารางที่เลือกแบบจำกัดจำนวนเพื่อความเร็ว"""
    limit_clause = " LIMIT 1000" if table_name == "fact_tickets" else ""
    query = f"SELECT * FROM {table_name}{limit_clause}"
    return pd.read_sql(query, engine)

# โหลดข้อมูลสรุปภาพรวม
summary_df = load_summary_data()

# ==========================================
# SECTION 1: VISUALIZATION SUMMARY (ภาพรวมข้อมูล)
# ==========================================
st.header("สรุปภาพรวมเรื่องร้องเรียน")

# --- 1.1 KPI Metric Cards ---
total_cases = len(summary_df)
finished_cases = len(summary_df[summary_df["state"] == "เสร็จสิ้น"])
inprogress_cases = len(summary_df[summary_df["state"] == "กำลังดำเนินการ"])
pending_cases = len(summary_df[summary_df["state"] == "รอรับเรื่อง"])
other_cases = total_cases - (finished_cases + inprogress_cases + pending_cases)

col1, col2, col3, col4 = st.columns(4)
col1.metric("เคสทั้งหมด", f"{total_cases:,}")
col2.metric("เสร็จสิ้น", f"{finished_cases:,}")
col3.metric("กำลังดำเนินการ", f"{inprogress_cases:,}")
col4.metric("รอรับเรื่อง / อื่นๆ", f"{pending_cases + other_cases:,}")

st.markdown("<br>", unsafe_allow_html=True)

# --- 1.2 Charts Layout (2 Columns) ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("1. สัดส่วนและจำนวนเคสตามสถานะ (State)")
    state_counts = (
        summary_df["state"]
        .value_counts()
        .reset_index()
        .rename(columns={"index": "state", "count": "จำนวนเคส", "state": "สถานะ"})
    )
    
    fig_state = px.pie(
        state_counts,
        names="สถานะ",
        values="จำนวนเคส",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_state.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_state, use_container_width=True)

with chart_col2:
    st.subheader("2. จำนวนเคสสูงสุด 10 อันดับแรกแยกตามเขต (District)")
    top_districts = (
        summary_df["district"]
        .value_counts()
        .head(10)
        .reset_index()
        .rename(columns={"district": "เขต", "count": "จำนวนเคส"})
    )
    
    fig_district = px.bar(
        top_districts,
        x="จำนวนเคส",
        y="เขต",
        orientation="h",
        color="จำนวนเคส",
        color_continuous_scale="Blues",
        text="จำนวนเคส"
    )
    fig_district.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_district, use_container_width=True)

# ==========================================
# SECTION 2: RAW DATA EXPLORER (สำรวจตารางข้อมูล)
# ==========================================
st.divider()
st.header("สำรวจข้อมูลในฐานข้อมูล (Data Explorer)")

table_options = {
    "Fact: เรื่องร้องเรียน (fact_tickets)": "fact_tickets",
    "Dim: ประเภทปัญหา (dim_problem_type)": "dim_problem_type",
    "Dim: สถานที่/เขต/แขวง (dim_location)": "dim_location",
    "Dim: หน่วยงาน (dim_organizations)": "dim_organizations",
    "Bridge: หน่วยงานในเคส (ticket_organizations)": "ticket_organizations"
}

selected_label = st.selectbox(
    "เลือกตารางข้อมูลที่ต้องการดู:",
    options=list(table_options.keys())
)

target_table = table_options[selected_label]
table_df = load_table_data(target_table)

st.write(f"แสดงข้อมูลจากตาราง **`{target_table}`** (จำนวน {len(table_df):,} แถว):")
st.dataframe(table_df, use_container_width=True)
