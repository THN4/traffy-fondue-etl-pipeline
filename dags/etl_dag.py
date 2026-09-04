from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.db import init_db_schema
from scripts.main import run_pipeline

# Default configuration arguments for DAG tasks
default_args = {
    "owner": "thanatip",
    "depends_on_past": False,            # Execute current run independently of previous run status
    "retries": 1,                        # Automatically retry once if task execution fails
    "retry_delay": timedelta(minutes=5), # Wait 5 minutes before retrying a failed task
}

# Define monthly automated ETL workflow
with DAG(
    dag_id="traffy_fondue_monthly_etl",
    default_args=default_args,
    description="Automated monthly ETL pipeline for Traffy Fondue municipal issue data",
    schedule_interval="@monthly",        # Trigger automatically on the 1st of every month
    start_date=datetime(2026, 1, 1),
    catchup=False,                       # Skip historical execution catchups prior to activation
    tags=["traffy-fondue", "etl", "bangkok"],
):

    # Task 1: Verify database connection and initialize Star Schema tables
    task_init_db = PythonOperator(
        task_id="init_database_schema",
        python_callable=init_db_schema,
    )

    # Task 2: Execute end-to-end Extract -> Transform -> Load pipeline
    task_run_etl = PythonOperator(
        task_id="run_traffy_etl_pipeline",
        python_callable=run_pipeline,
    )

    # Task Dependency: Initialize database schema prior to executing the ETL pipeline
    task_init_db >> task_run_etl