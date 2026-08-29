import os
import sqlite3
import pandas as pd

DB_PATH = "regional_sales.db"
DATA_DIR = "Data_CSV"

TABLES_MAP = {
    '2017_budgets': os.path.join(DATA_DIR, '2017_Budgets.csv'),
    'customers': os.path.join(DATA_DIR, 'Customers.csv'),
    'products': os.path.join(DATA_DIR, 'Products.csv'),
    'regions': os.path.join(DATA_DIR, 'Regions.csv'),
    'sales_order': os.path.join(DATA_DIR, 'sales_order.csv'),
    'state_regions': os.path.join(DATA_DIR, 'State_Regions.csv')
}

def init_db(db_path=DB_PATH, force=False):
    if os.path.exists(db_path) and not force:
        print(f"Database '{db_path}' already exists.")
        return
    
    print(f"Creating database '{db_path}' from CSV files...")
    conn = sqlite3.connect(db_path)
    
    for table_name, csv_path in TABLES_MAP.items():
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"  Loaded '{table_name}' ({len(df)} rows)")
        else:
            print(f"  Warning: {csv_path} not found.")
            
    conn.close()
    print("Database initialization complete.\n")

if __name__ == "__main__":
    init_db(force=True)
