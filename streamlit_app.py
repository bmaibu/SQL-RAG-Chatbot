import os
import re
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from db_setup import init_db

# Load environment variables from .env file
load_dotenv()

st.set_page_config(
    page_title="Text-to-SQL Chatbot & Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.set_option("client.toolbarMode", "viewer")

# Initialize database
init_db()
DB_PATH = "regional_sales.db"

# Styling
st.markdown("""
<style>
    /* Streamlit toolbar/menu customization for Streamlit 1.59.2. */
    [data-testid="stAppDeployButton"],
    [data-testid="stMainMenuItem-theme-Light"],
    [data-testid="stMainMenuItem-print"],
    [data-testid="stMainMenuItem-recordScreencast"],
    [data-testid="stMainMenuDivider"],
    [data-testid="stMainMenuList"] + * {
        display: none !important;
    }

    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #64748b;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .card {
        border-radius: 12px;
        padding: 1.2rem;
        background-color: #1e293b;
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    .sql-box {
        background-color: #0f172a;
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        border-radius: 6px;
        font-family: monospace;
    }
    .footer {
        margin-top: 2rem;
        padding: 1rem 0;
        border-top: 1px solid #334155;
        color: #64748b;
        font-size: 0.85rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">⚡ Text-to-SQL Chatbot & Database Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Query regional sales data in plain English or standard SQL using Gemini AI & SQLite</div>', unsafe_allow_html=True)

# Default API key from environment
env_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

# Sidebar
api_key = env_api_key
model_choice = "gemini-3.6-flash"

# Database connection
conn = sqlite3.connect(DB_PATH)

def get_tables():
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]

def get_table_schema(table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info(`{table_name}`);")
    cols = cursor.fetchall()
    return pd.DataFrame(cols, columns=["cid", "name", "type", "notnull", "dflt_value", "pk"])

tables = get_tables()

# Sidebar Database Explorer
st.sidebar.subheader("📊 Database Schema")
selected_table = st.sidebar.selectbox("Inspect Table", tables)
if selected_table:
    st.sidebar.write(f"**Schema for `{selected_table}`:**")
    st.sidebar.dataframe(get_table_schema(selected_table)[["name", "type"]], use_container_width=True)

# Main tabs
tab1, tab2, tab3 = st.tabs(["💬 Chatbot (Natural Language)", "💻 Custom SQL Runner", "📁 Data Preview"])

def get_schema_summary():
    cursor = conn.cursor()
    summary = ""
    for t in tables:
        cursor.execute(f"PRAGMA table_info(`{t}`);")
        cols = cursor.fetchall()
        col_str = ", ".join([f"`{c[1]}` {c[2]}" for c in cols])
        summary += f"Table `{t}` ({col_str})\n"
    return summary

with tab1:
    st.subheader("Ask a question in Plain English")
    
    preset_questions = [
        "Select a sample question...",
        "What are the top 5 products by total 2017 budget?",
        "How many total sales orders are there in the database?",
        "List total order count and total line sales by channel",
        "What is the total 'Line Total' for Geiss Company?",
        "Show top 10 regions ordered by population descending"
    ]
    
    selected_preset = st.selectbox("Sample Questions:", preset_questions)
    user_query = st.text_input("Or type your own question:", value="" if selected_preset == preset_questions[0] else selected_preset)
    
    if st.button("🚀 Generate SQL & Query Data", type="primary"):
        if not user_query:
            st.warning("Please enter a question or select a sample question.")
        else:
            key_to_use = api_key or env_api_key
            
            schema_info = get_schema_summary()
            prompt = f"""Based on the SQLite database schema below, write a clean SQL query to answer the user's question.

Database Schema:
{schema_info}

Rules:
- Return ONLY the SQL query inside a ```sql ... ``` code block.
- Use exact column names from schema.

Question: {user_query}
SQL Query:"""

            sql_result = None
            err_msg = None
            
            if key_to_use:
                try:
                    client = genai.Client(api_key=key_to_use)
                    res = client.models.generate_content(
                        model=model_choice,
                        contents=prompt
                    )
                    raw_text = res.text if hasattr(res, 'text') else str(res)
                    match = re.search(r"```sql\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
                    sql_result = match.group(1).strip() if match else raw_text.strip()
                except Exception as e:
                    err_msg = f"LLM Call Failed: {e}"
            else:
                err_msg = "Gemini API Key missing. Please input your API Key in the sidebar or update .env file."

            if err_msg:
                st.error(err_msg)
            elif sql_result:
                st.markdown("### 📝 Generated SQL Query")
                st.code(sql_result, language="sql")
                
                st.markdown("### 📊 Execution Results")
                try:
                    df_res = pd.read_sql_query(sql_result, conn)
                    st.dataframe(df_res, use_container_width=True)
                    st.success(f"Query returned {len(df_res)} rows.")
                    
                    # Numeric columns chart preview
                    num_cols = df_res.select_dtypes(include=["number"]).columns
                    cat_cols = df_res.select_dtypes(include=["object", "string"]).columns
                    if len(num_cols) > 0 and len(cat_cols) > 0 and len(df_res) <= 50:
                        st.markdown("### 📈 Visual Chart")
                        st.bar_chart(df_res.set_index(cat_cols[0])[num_cols[0]])
                except Exception as e:
                    st.error(f"SQL Execution Error: {e}")

with tab2:
    st.subheader("Execute Raw SQL Query")
    default_sql = "SELECT p.`Product Name`, b.`2017 Budgets` FROM `products` p JOIN `2017_budgets` b ON p.`Product Name` = b.`Product Name` ORDER BY b.`2017 Budgets` DESC LIMIT 10;"
    custom_sql = st.text_area("SQL Statement:", value=default_sql, height=120)
    
    if st.button("Run SQL"):
        try:
            df_custom = pd.read_sql_query(custom_sql, conn)
            st.dataframe(df_custom, use_container_width=True)
            st.success(f"Successfully executed query. Returned {len(df_custom)} rows.")
        except Exception as e:
            st.error(f"Error executing query: {e}")

with tab3:
    st.subheader("Data Tables Preview")
    preview_table = st.selectbox("Select table to preview:", tables)
    if preview_table:
        limit = st.slider("Row limit:", 5, 100, 15)
        df_preview = pd.read_sql_query(f"SELECT * FROM `{preview_table}` LIMIT {limit};", conn)
        st.dataframe(df_preview, use_container_width=True)

conn.close()

st.markdown(
    '<div class="footer">© 2026 B Maibu · All rights reserved · Crafted with 💚 by Maibu</div>',
    unsafe_allow_html=True,
)
