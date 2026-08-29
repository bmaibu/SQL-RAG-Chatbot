import os
import re
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from google import genai
from db_setup import init_db

# Load environment variables from .env file
load_dotenv()

DB_PATH = "regional_sales.db"

def get_db_schema(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    schema_str = ""
    for table in tables:
        cursor.execute(f"PRAGMA table_info(`{table}`);")
        columns = cursor.fetchall()
        col_desc = ", ".join([f"`{col[1]}` {col[2]}" for col in columns])
        
        cursor.execute(f"SELECT * FROM `{table}` LIMIT 1;")
        sample = cursor.fetchone()
        
        schema_str += f"Table `{table}` ({col_desc})\n"
        if sample:
            schema_str += f"  Sample row: {sample}\n"
        schema_str += "\n"
        
    conn.close()
    return schema_str

def execute_sql(sql_query, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return df, None
    except Exception as e:
        conn.close()
        return None, str(e)

def generate_sql_prompt(question, schema):
    return f"""Based on the SQLite database schema below, write a clean SQL query to answer the user's question.
    
Database Schema:
{schema}

Rules:
- Return ONLY the SQL query inside a ```sql ... ``` code block.
- Do not modify or write to database tables (SELECT queries only).
- Use exact column names as shown in the schema.

Question: {question}
SQL Query:"""

def generate_sql_llm(question, api_key=None, model_name="gemini-3.6-flash"):
    schema = get_db_schema()
    prompt = generate_sql_prompt(question, schema)
    
    key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if key:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            raw_text = response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            return None, f"LLM Error: {e}"
    else:
        return None, "No API Key provided. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env file."
        
    match = re.search(r"```sql\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        query = match.group(1).strip()
    else:
        query = raw_text.strip()
        
    return query, None

def run_cli():
    print("=" * 60)
    print("      Text-to-SQL Chatbot & Database Query Engine")
    print("=" * 60)
    init_db()
    
    schema = get_db_schema()
    print("Loaded Database Schema:")
    print(schema)
    
    while True:
        print("-" * 60)
        user_input = input("Enter natural language question or raw SQL (or 'exit' to quit): ").strip()
        if not user_input or user_input.lower() in ['exit', 'quit', 'q']:
            print("Exiting Text-to-SQL Chatbot.")
            break
            
        q_upper = user_input.strip().upper()
        if q_upper.startswith(("SELECT", "PRAGMA", "WITH")) or (q_upper.startswith("SHOW ") and ("TABLES" in q_upper or "COLUMNS" in q_upper)):
            sql_query = user_input
        else:
            print("Generating SQL query from question using Gemini AI...")
            sql_query, err = generate_sql_llm(user_input)
            if err:
                print(f"[{err}]")
                sql_query = input("Fallback: Enter raw SQL manually to run against database: ").strip()
                if not sql_query:
                    continue
            else:
                print(f"\nGenerated SQL:\n{sql_query}\n")
                
        df, err = execute_sql(sql_query)
        if err:
            print(f"Execution Error: {err}")
        else:
            print("Results:")
            print(df.to_string(index=False) if not df.empty else "No rows returned.")

if __name__ == "__main__":
    run_cli()
