# NYC Taxi Pipeline - Visual Diagrams

## System Architecture - High Level

```
┌────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                               │
│                                                                    │
│  https://d37ci6vzurychx.cloudfront.net/trip-data/                │
│  ├── yellow_tripdata_2023-01.parquet                             │
│  ├── yellow_tripdata_2023-02.parquet                             │
│  └── taxi_zone_lookup.csv                                        │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     │ HTTP Download
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER (Raw)                            │
│                   PySpark Job 1: Ingestion                         │
│                                                                    │
│  Storage: GCS gs://bucket/bronze/ or Local /data/bronze/          │
│  ├── nyc_taxi/                                                    │
│  │   ├── yellow_trips/                                           │
│  │   │   └── year=2023/month=01/*.parquet                        │
│  │   └── zone_lookup/*.parquet                                   │
│  │                                                                │
│  Features:                                                         │
│  • Minimal transformation                                         │
│  • Schema enforcement                                             │
│  • Metadata columns (ingestion_timestamp, source_file)           │
│  • Partitioned by year/month                                     │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     │ Read Parquet
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                     SILVER LAYER (Curated)                         │
│              PySpark Job 2: Transformation                         │
│                                                                    │
│  Storage: GCS gs://bucket/silver/ or Local /data/silver/          │
│  ├── nyc_taxi/                                                    │
│  │   ├── dimensions/                                             │
│  │   │   ├── dim_datetime/*.parquet                              │
│  │   │   ├── dim_location/*.parquet                              │
│  │   │   ├── dim_rate_code/*.parquet                             │
│  │   │   └── dim_payment_type/*.parquet                          │
│  │   └── facts/                                                   │
│  │       └── fact_taxi_trips/year=2023/month=01/*.parquet        │
│  │                                                                │
│  Transformations:                                                  │
│  • Data cleaning & quality filters                               │
│  • Join zone lookup                                              │
│  • Create dimensional model (star schema)                        │
│  • Calculate derived measures                                    │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     │ JDBC Bulk Load
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                      GOLD LAYER (Analytics)                        │
│                  PostgreSQL Database                               │
│                                                                    │
│  Database: nyc_taxi                                               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │           DIMENSIONAL MODEL (Star Schema)                 │    │
│  │                                                           │    │
│  │  ┌─────────────────┐      ┌─────────────────┐          │    │
│  │  │  dim_datetime   │      │  dim_location   │          │    │
│  │  │  (198K rows)    │      │  (265 rows)     │          │    │
│  │  └────────┬────────┘      └────────┬────────┘          │    │
│  │           │                         │                    │    │
│  │           │        ┌────────────────┼──────────┐        │    │
│  │           │        │                │          │        │    │
│  │           ▼        ▼                ▼          ▼        │    │
│  │     ┌────────────────────────────────────────────┐      │    │
│  │     │      fact_taxi_trips                       │      │    │
│  │     │      (2.9M rows/month)                     │      │    │
│  │     │                                            │      │    │
│  │     │  • trip_id (PK)                            │      │    │
│  │     │  • pickup_datetime_id (FK)                 │      │    │
│  │     │  • dropoff_datetime_id (FK)                │      │    │
│  │     │  • pickup_location_id (FK)                 │      │    │
│  │     │  • dropoff_location_id (FK)                │      │    │
│  │     │  • rate_code_id (FK)                       │      │    │
│  │     │  • payment_type_id (FK)                    │      │    │
│  │     │  • fare_amount, tip_amount, etc.           │      │    │
│  │     └────────────────────────────────────────────┘      │    │
│  │           ▲        ▲                                     │    │
│  │           │        │                                     │    │
│  │  ┌────────┴────┐   │     ┌─────────────────┐           │    │
│  │  │dim_rate_code│   └─────│dim_payment_type │           │    │
│  │  │(6 rows)     │         │(6 rows)         │           │    │
│  │  └─────────────┘         └─────────────────┘           │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                      CONSUMPTION LAYER                             │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  SQL Queries │  │  BI Tools    │  │  Dashboards  │           │
│  │              │  │  (Tableau,   │  │  (Superset,  │           │
│  │  • psql      │  │   PowerBI)   │  │   Grafana)   │           │
│  │  • pgAdmin   │  │              │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow Sequence

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Extract │ ──▶ │Transform│ ──▶ │  Load   │ ──▶ │ Analyze │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
    │               │               │               │
    │               │               │               │
    ▼               ▼               ▼               ▼
 Download       Clean &         Load to        Run SQL
NYC Data       Create          PostgreSQL      Queries
(Bronze)       Star Schema        (Gold)
               (Silver)
```

## Star Schema Entity-Relationship Diagram

```
                    ╔═════════════════════╗
                    ║   dim_datetime      ║
                    ╠═════════════════════╣
                    ║ •datetime_id (PK)   ║
                    ║  datetime_value     ║
                    ║  date               ║
                    ║  year, month, day   ║
                    ║  hour, minute       ║
                    ║  day_of_week        ║
                    ║  is_weekend         ║
                    ╚══════════╤══════════╝
                               │
                               │ 1:M
                               │
╔═════════════════════╗        │        ╔═════════════════════╗
║   dim_location      ║        │        ║  dim_rate_code      ║
╠═════════════════════╣        │        ╠═════════════════════╣
║ •location_id (PK)   ║        │        ║ •rate_code_id (PK)  ║
║  zone_name          ║        │        ║  rate_code_desc     ║
║  borough            ║        │        ╚══════════╤══════════╝
║  service_zone       ║        │                   │
╚══════════╤══════════╝        │                   │ 1:M
           │                   │                   │
           │ 1:M               │                   │
           │                   ▼                   │
           │          ╔═════════════════════╗      │
           └─────────▶║  fact_taxi_trips    ║◀─────┘
                      ╠═════════════════════╣
             1:M      ║ •trip_id (PK)       ║
           ┌─────────▶║  pickup_datetime_id ║──────┐
           │          ║  dropoff_datetime_id║      │ M:1
           │          ║  pickup_location_id ║      │
           │          ║  dropoff_location_id║      └─────┐
           │          ║  rate_code_id       ║            │
           │          ║  payment_type_id    ║            │
           │          ║  passenger_count    ║            ▼
           │          ║  trip_distance      ║  ╔═════════════════════╗
           │          ║  fare_amount        ║  ║   dim_datetime      ║
           │          ║  tip_amount         ║  ║  (same as above)    ║
           │          ║  total_amount       ║  ╚═════════════════════╝
           │          ╚══════════╤══════════╝
           │                     │
           │                     │ M:1
           │                     ▼
           │          ╔═════════════════════╗
           └──────────║ dim_payment_type    ║
                      ╠═════════════════════╣
                      ║•payment_type_id(PK) ║
                      ║ payment_type_desc   ║
                      ╚═════════════════════╝

Legend:
• = Primary Key
─▶ = Foreign Key Relationship
1:M = One-to-Many
M:1 = Many-to-One
```

## Pipeline Orchestration Flow (Airflow DAG)

```
                    ┌──────────────────────┐
                    │   Start Pipeline     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  bronze_ingestion    │
                    │                      │
                    │  • Download data     │
                    │  • Store in bronze   │
                    │  • Add metadata      │
                    └──────────┬───────────┘
                               │
                               │ Success
                               ▼
                    ┌──────────────────────┐
                    │dimensional_transform │
                    │                      │
                    │  • Read bronze       │
                    │  • Clean data        │
                    │  • Create star schema│
                    │  • Write to silver   │
                    └──────────┬───────────┘
                               │
                               │ Success
                               ▼
                    ┌──────────────────────┐
                    │    database_load     │
                    │                      │
                    │  • Read silver       │
                    │  • Load dimensions   │
                    │  • Load facts        │
                    │  • Create indexes    │
                    └──────────┬───────────┘
                               │
                               │ Success
                               ▼
                    ┌──────────────────────┐
                    │ data_quality_check   │
                    │                      │
                    │  • Verify counts     │
                    │  • Check FK integrity│
                    │  • Validate ranges   │
                    └──────────┬───────────┘
                               │
                               │ Success
                               ▼
                    ┌──────────────────────┐
                    │ refresh_materialized │
                    │       _view          │
                    │                      │
                    │  • Refresh MV        │
                    │  • Update stats      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Pipeline Complete  │
                    └──────────────────────┘

Note: Each task has retry logic (2 retries, 5 min delay)
```

## CI/CD Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Git Push / Pull Request                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GitHub Actions Triggered                      │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ├──────────────┬──────────────┬──────────────┬──────────────┐
      │              │              │              │              │
      ▼              ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Lint    │  │   Test   │  │Terraform │  │  Build   │  │ Integrate│
│          │  │          │  │ Validate │  │  Docker  │  │   Test   │
│ •black   │  │ •pytest  │  │          │  │          │  │          │
│ •flake8  │  │ •coverage│  │ •fmt     │  │ •spark   │  │ •full    │
│ •isort   │  │          │  │ •validate│  │ •airflow │  │  pipeline│
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │
     └─────────────┴─────────────┴─────────────┴─────────────┘
                                  │
                          All checks pass?
                                  │
                    ┌─────────────┴─────────────┐
                    │ No                        │ Yes
                    ▼                           ▼
            ┌──────────────┐          ┌──────────────────┐
            │   Fail PR    │          │  Approve PR      │
            │   Report     │          │  Ready to merge  │
            └──────────────┘          └────────┬─────────┘
                                               │
                                   Merged to main branch
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │  Deploy to GCP   │
                                    │                  │
                                    │ •terraform apply │
                                    │ •push images     │
                                    └──────────────────┘
```

## Infrastructure Architecture (GCP)

```
┌──────────────────────────────────────────────────────────────────┐
│                      Google Cloud Platform                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Cloud Storage (GCS)                      │ │
│  │                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ Bronze Bucket│  │Silver Bucket │  │ Gold Bucket  │   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ •Raw data    │  │ •Curated     │  │ •Aggregated  │   │ │
│  │  │ •90d lifecycle│  │ •Versioned   │  │ •Optimized   │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Cloud Dataproc                          │ │
│  │                (Optional - for scale)                      │ │
│  │                                                            │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │ │
│  │  │   Master   │  │  Worker 1  │  │  Worker N  │         │ │
│  │  │   Node     │  │   Node     │  │   Node     │         │ │
│  │  └────────────┘  └────────────┘  └────────────┘         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   BigQuery                                 │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────┐                │ │
│  │  │  Dataset: nyc_taxi_analytics         │                │ │
│  │  │                                      │                │ │
│  │  │  Tables:                             │                │ │
│  │  │  • fact_taxi_trips                   │                │ │
│  │  │  • dim_datetime                      │                │ │
│  │  │  • dim_location                      │                │ │
│  │  └──────────────────────────────────────┘                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   IAM & Security                           │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────┐                │ │
│  │  │  Service Account:                    │                │ │
│  │  │  nyc-taxi-pipeline-sa                │                │ │
│  │  │                                      │                │ │
│  │  │  Roles:                              │                │ │
│  │  │  • Storage Object Admin              │                │ │
│  │  │  • BigQuery Data Editor              │                │ │
│  │  └──────────────────────────────────────┘                │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Local Development Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Docker Compose Network                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Spark Cluster                            │ │
│  │                                                            │ │
│  │  ┌──────────────────┐          ┌──────────────────┐      │ │
│  │  │  Spark Master    │          │  Spark Worker    │      │ │
│  │  │                  │          │                  │      │ │
│  │  │  Port: 7077      │◀────────▶│  Cores: 2        │      │ │
│  │  │  UI: 8080        │          │  Memory: 2GB     │      │ │
│  │  └──────────────────┘          └──────────────────┘      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   PostgreSQL                               │ │
│  │                                                            │ │
│  │  Database: nyc_taxi                                       │ │
│  │  Port: 5432                                               │ │
│  │  User: taxi_user                                          │ │
│  │                                                            │ │
│  │  Volumes: postgres-data                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Apache Airflow                           │ │
│  │                                                            │ │
│  │  ┌──────────────────┐          ┌──────────────────┐      │ │
│  │  │  Webserver       │          │  Scheduler       │      │ │
│  │  │                  │          │                  │      │ │
│  │  │  Port: 8081      │          │  DAGs: /dags     │      │ │
│  │  │  UI: admin/admin │          │                  │      │ │
│  │  └──────────────────┘          └──────────────────┘      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Volumes (Shared)                         │ │
│  │                                                            │ │
│  │  • ./data → /data (Bronze, Silver, Gold)                  │ │
│  │  • ./spark → /opt/spark-app (Jobs & Code)                 │ │
│  │  • ./airflow/dags → /opt/airflow/dags                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                         ▲
                         │
                  Access from Host
                         │
                ┌────────┴────────┐
                │  localhost:8080 │ → Spark UI
                │  localhost:8081 │ → Airflow UI
                │  localhost:5432 │ → PostgreSQL
                └─────────────────┘
```

## Data Partitioning Strategy

```
Bronze Layer Structure:
/data/bronze/nyc_taxi/
├── yellow_trips/
│   ├── year=2023/
│   │   ├── month=01/
│   │   │   └── part-00000-*.parquet
│   │   ├── month=02/
│   │   │   └── part-00000-*.parquet
│   │   └── month=03/
│   │       └── part-00000-*.parquet
│   └── year=2024/
│       └── month=01/
│           └── part-00000-*.parquet
└── zone_lookup/
    └── part-00000-*.parquet

Silver Layer Structure:
/data/silver/nyc_taxi/
├── dimensions/
│   ├── dim_datetime/
│   │   └── part-00000-*.parquet
│   ├── dim_location/
│   │   └── part-00000-*.parquet
│   ├── dim_rate_code/
│   │   └── part-00000-*.parquet
│   └── dim_payment_type/
│       └── part-00000-*.parquet
└── facts/
    └── fact_taxi_trips/
        ├── year=2023/
        │   ├── month=01/
        │   │   └── part-00000-*.parquet
        │   ├── month=02/
        │   │   └── part-00000-*.parquet
        │   └── month=03/
        │       └── part-00000-*.parquet
        └── year=2024/
            └── month=01/
                └── part-00000-*.parquet

Benefits:
✓ Partition pruning in queries
✓ Easy historical backfills
✓ Efficient data management
✓ Isolated month re-processing
```

## Scaling Strategy

```
Current: Single Worker
┌──────────┐
│  Master  │
└────┬─────┘
     │
     ▼
┌──────────┐
│ Worker 1 │
└──────────┘

Scale: Multiple Workers (Horizontal)
┌──────────┐
│  Master  │
└────┬─────┘
     │
     ├─────────┬─────────┬─────────┐
     ▼         ▼         ▼         ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│ Worker 1 ││ Worker 2 ││ Worker 3 ││ Worker N │
└──────────┘└──────────┘└──────────┘└──────────┘

Cloud Scale: Dataproc (Auto-scaling)
┌──────────────────────────────────────┐
│       Dataproc Cluster               │
│                                      │
│  ┌──────────┐                        │
│  │  Master  │                        │
│  └────┬─────┘                        │
│       │                              │
│  Auto-scaling Worker Pool:           │
│  Min: 2, Max: 10                     │
│  ┌──────────┐ ┌──────────┐          │
│  │ Worker 1 │ │ Worker 2 │ ... [N]  │
│  └──────────┘ └──────────┘          │
└──────────────────────────────────────┘
```