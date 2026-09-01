from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.db import test_connection, init_db_schema
from scripts.main import run_pipeline

default_args = {
    "owner": "thanatip",
    "depends_on_past": False, # Dont have to Wait Prev Task 
    "retries": 1, # Retire run if crack
    "retry_delay": timedelta(minutes=5),  # if crack wait 5 min 
}

# 2. Create DAG Workflow
with DAG(
    dag_id="traffy_fondue_monthly_etl",
    default_args=default_args,
    description="Automated monthly ETL pipeline for Traffy Fondue municipal data",
    schedule_interval="@monthly",  # auto every month
    start_date=datetime(2026, 1, 1),
    catchup=False,  # Run only current month 
    tags=["traffy-fondue", "etl", "bangkok"],
):

    # Task 1: Initial Database
    task_init_db = PythonOperator(
        task_id="init_database_schema",
        python_callable=init_db_schema,
    )

    # Task 2: ETL Process
    task_run_etl = PythonOperator(
        task_id="run_traffy_etl_pipeline",
        python_callable=run_pipeline,
    )

    # 3. Define flow: init database -> etl process
    task_init_db >> task_run_etl