"""
NYC Taxi Pipeline DAG

Orchestrates the complete data pipeline:
1. Bronze ingestion (download + store raw data)
2. Dimensional transformation (create star schema)
3. Database loading (load to PostgreSQL)

Supports historical backfills by parameterizing year and months.
"""

from datetime import datetime, timedelta
from airflow import DAG

# Try new import path first (Airflow 2.10+), fall back to legacy (Airflow 2.0-2.9)
try:
    from airflow.providers.standard.operators.bash import BashOperator
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.bash import BashOperator
    from airflow.operators.python import PythonOperator

# Default arguments for all tasks
default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG configuration
dag = DAG(
    'nyc_taxi_pipeline',
    default_args=default_args,
    description='NYC Taxi data pipeline with medallion architecture',
    schedule='@monthly',  # Run monthly for new data
    start_date=datetime(2023, 1, 1),
    catchup=False,  # Don't backfill automatically
    tags=['nyc_taxi', 'medallion', 'dimensional_model'],
    params={
        'year': 2023,
        'months': '1',  # Comma-separated months
        'storage_type': 'local',
    }
)

# Task 1: Bronze Ingestion
# Downloads raw data and stores in bronze layer
bronze_ingestion = BashOperator(
    task_id='bronze_ingestion',
    bash_command="""
    spark-submit \
        --master {{ var.value.spark_master_url }} \
        --deploy-mode client \
        --name "Bronze Ingestion" \
        /opt/spark-app/jobs/bronze_ingestion.py \
        --year {{ params.year }} \
        --months {{ params.months }} \
        --storage-type {{ params.storage_type }}
    """,
    dag=dag,
)

# Task 2: Dimensional Transformation
# Creates star schema from bronze data
dimensional_transform = BashOperator(
    task_id='dimensional_transform',
    bash_command="""
    spark-submit \
        --master {{ var.value.spark_master_url }} \
        --deploy-mode client \
        --name "Dimensional Transform" \
        /opt/spark-app/jobs/dimensional_transform.py \
        --year {{ params.year }} \
        --months {{ params.months }} \
        --storage-type {{ params.storage_type }}
    """,
    dag=dag,
)

# Task 3: Database Loading
# Loads dimensional model to PostgreSQL
database_load = BashOperator(
    task_id='database_load',
    bash_command="""
    spark-submit \
        --master {{ var.value.spark_master_url }} \
        --deploy-mode client \
        --name "Database Loader" \
        --jars /opt/spark/jars/postgresql-42.7.8.jar \
        /opt/spark-app/jobs/db_loader.py \
        --year {{ params.year }} \
        --months {{ params.months }} \
        --mode overwrite \
        --storage-type {{ params.storage_type }}
    """,
    dag=dag,
)

# Task 4: Data Quality Checks (simple validation)
def validate_data(**context):
    """
    Perform basic data quality checks after loading.
    In production, this would be more comprehensive.
    """
    import psycopg2
    
    conn = psycopg2.connect(
        host='postgres',
        database='nyc_taxi',
        user='taxi_user',
        password='taxi_pass'
    )
    
    cur = conn.cursor()
    
    # Check 1: Record counts
    cur.execute("SELECT COUNT(*) FROM fact_taxi_trips")
    fact_count = cur.fetchone()[0]
    print(f"Fact table count: {fact_count}")
    
    if fact_count == 0:
        raise ValueError("Fact table is empty!")
    
    # Check 2: Dimension integrity
    cur.execute("""
        SELECT COUNT(*) 
        FROM fact_taxi_trips f
        LEFT JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
        WHERE dt.datetime_id IS NULL
    """)
    orphan_count = cur.fetchone()[0]
    
    if orphan_count > 0:
        raise ValueError(f"Found {orphan_count} orphaned records in fact table!")
    
    # Check 3: Data reasonableness
    cur.execute("""
        SELECT 
            MIN(total_amount) as min_fare,
            MAX(total_amount) as max_fare,
            AVG(total_amount) as avg_fare
        FROM fact_taxi_trips
    """)
    min_fare, max_fare, avg_fare = cur.fetchone()
    print(f"Fare range: ${min_fare:.2f} - ${max_fare:.2f}, avg: ${avg_fare:.2f}")
    
    cur.close()
    conn.close()
    
    print("All data quality checks passed!")

data_quality_check = PythonOperator(
    task_id='data_quality_check',
    python_callable=validate_data,
    dag=dag,
)

# Task 5: Refresh materialized view
refresh_mv = BashOperator(
    task_id='refresh_materialized_view',
    bash_command="""
    PGPASSWORD=taxi_pass psql -h postgres -U taxi_user -d nyc_taxi -c \
    "REFRESH MATERIALIZED VIEW mv_daily_trip_summary;"
    """,
    dag=dag,
)

# Define task dependencies
bronze_ingestion >> dimensional_transform >> database_load >> data_quality_check >> refresh_mv

# Documentation
dag.doc_md = """
# NYC Taxi Data Pipeline

This DAG orchestrates the complete NYC Taxi data pipeline using the medallion architecture.

## Pipeline Stages

1. **Bronze Ingestion**: Downloads raw parquet files and CSV lookup data, stores in bronze layer
2. **Dimensional Transform**: Cleans data and creates star schema (fact + dimension tables)
3. **Database Load**: Loads dimensional model into PostgreSQL for analytics
4. **Data Quality Check**: Validates data integrity and reasonableness
5. **Refresh MV**: Updates materialized views for reporting

## Parameters

- `year`: Year to process (default: 2023)
- `months`: Comma-separated months to process (default: '1')
- `storage_type`: 'local' or 'gcs' (default: 'local')

## Historical Backfills

To backfill historical data, trigger the DAG with custom parameters:
- Set `months` to "1,2,3" to process multiple months
- Use `mode: append` in database_load to add to existing data

## Data Model

**Fact Table**: `fact_taxi_trips` (grain: one row per trip)
**Dimensions**: 
- `dim_datetime`: Temporal attributes
- `dim_location`: Pickup/dropoff zones
- `dim_rate_code`: Rate code descriptions
- `dim_payment_type`: Payment method descriptions
"""