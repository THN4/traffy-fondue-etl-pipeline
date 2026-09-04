import argparse
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from scripts.extract import extract_traffy_data
from scripts.transform import transform_traffy_data
from scripts.db import test_connection, init_db_schema
from scripts.load import load_traffy_data

def run_pipeline(target_month: str = None):
    """
    Execute end-to-end Traffy Fondue ETL pipeline.
    
    Args:
        target_month (str, optional): Target month in 'YYYY-MM' format (e.g., '2026-07').
                                       If omitted, defaults to the previous calendar month.
    """
    if not target_month:
        # Dynamically compute previous calendar month if target_month is unspecified
        prev_month = datetime.now() - relativedelta(months=1)
        target_month = prev_month.strftime("%Y-%m")
        
    file_name = f"bangkok_{target_month}"
    
    print("\n" + "="*60)
    print(f"STARTING ETL PIPELINE FOR: {file_name}")
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    start_time = time.time()
    
    try:
        # Step 1: Healthcheck & Schema Initialization
        test_connection()
        init_db_schema()
        
        # Step 2: Extraction
        raw_df = extract_traffy_data(file_name)
        
        # Step 3: Transformation & Feature Engineering
        clean_df = transform_traffy_data(raw_df)
        
        # Step 4: Loading & Dimensional Upsert
        load_traffy_data(clean_df)
        
        elapsed = time.time() - start_time
        print("="*60)
        print(f"PIPELINE COMPLETED SUCCESSFULLY!")
        print(f"Total Time Elapsed: {elapsed:.2f} seconds")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n" + "!"*60)
        print(f"PIPELINE FAILED with error: {e}")
        print("!"*60 + "\n")
        raise e

# Command Line Interface (CLI) execution block
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traffy Fondue ETL Pipeline Automator")
    parser.add_argument(
        "--month", 
        type=str, 
        help="Target month in YYYY-MM format (e.g., 2026-07). If omitted, defaults to previous month."
    )
    args = parser.parse_args()
    
    run_pipeline(target_month=args.month)