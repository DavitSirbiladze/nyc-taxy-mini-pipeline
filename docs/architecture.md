# NYC Taxi Pipeline - Architecture Documentation

## System Architecture

### Overview

The NYC Taxi Pipeline implements a modern data lakehouse architecture using the medallion pattern (Bronze → Silver → Gold) with dimensional modeling for analytics.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                   │
│  ┌──────────────────────┐       ┌──────────────────────┐               │
│  │ NYC TLC Trip Data    │       │ Taxi Zone Lookup     │               │
│  │ (Parquet Files)      │       │ (CSV)                │               │
│  └──────────┬───────────┘       └──────────┬───────────┘               │
└─────────────┼──────────────────────────────┼───────────────────────────┘
              │                              │
              │    PySpark Job 1: Bronze Ingestion
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        BRONZE LAYER (Raw Zone)                           │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  GCS/Local Storage: /bronze/nyc_taxi/                          │    │
│  │  ├── yellow_trips/year=2023/month=01/*.parquet                 │    │
│  │  │   - Minimal transformation                                  │    │
│  │  │   - Schema enforcement                                      │    │
│  │  │   - Metadata columns added                                  │    │
│  │  └── zone_lookup/*.parquet                                     │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │    PySpark Job 2: Dimensional Transform
                              │    - Data cleaning
                              │    - Quality filters
                              │    - Star schema creation
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SILVER LAYER (Curated Zone)                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  GCS/Local Storage: /silver/nyc_taxi/                          │    │
│  │  ├── dimensions/                                               │    │
│  │  │   ├── dim_datetime/*.parquet                                │    │
│  │  │   ├── dim_location/*.parquet                                │    │
│  │  │   ├── dim_rate_code/*.parquet                               │    │
│  │  │   └── dim_payment_type/*.parquet                            │    │
│  │  └── facts/                                                     │    │
│  │      └── fact_taxi_trips/year=2023/month=01/*.parquet          │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │    PySpark Job 3: Database Loader
                              │    - JDBC bulk load
                              │    - Index creation
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       GOLD LAYER (Analytics DB)                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL Database: nyc_taxi                                  │    │
│  │  ┌──────────────────────────────────────────────────────┐      │    │
│  │  │             DIMENSIONAL MODEL (Star Schema)          │      │    │
│  │  │                                                       │      │    │
│  │  │  ┌─────────────────┐                                │      │    │
│  │  │  │ dim_datetime    │◄──┐                            │      │    │
│  │  │  └─────────────────┘   │                            │      │    │
│  │  │  ┌─────────────────┐   │   ┌─────────────────┐     │      │    │
│  │  │  │ dim_location    │◄──┼───│ fact_taxi_trips │     │      │    │
│  │  │  └─────────────────┘   │   │  (Grain: Trip)  │     │      │    │
│  │  │  ┌─────────────────┐   │   └─────────────────┘     │      │    │
│  │  │  │ dim_rate_code   │◄──┤                            │      │    │
│  │  │  └─────────────────┘   │                            │      │    │
│  │  │  ┌─────────────────┐   │                            │      │    │
│  │  │  │ dim_payment_type│◄──┘                            │      │    │
│  │  │  └─────────────────┘                                │      │    │
│  │  └──────────────────────────────────────────────────────┘      │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │   BI Tools / Users    │
                    │  - SQL Queries        │
                    │  - Dashboards         │
                    │  - Reports            │
                    └──────────────────────┘
```

## Component Details

### 1. Data Ingestion Layer

**Technology**: PySpark on Apache Spark
**Input**: HTTP downloads from NYC TLC
**Output**: Parquet files in Bronze layer

**Components**:
- `bronze_ingestion.py`: Downloads and stores raw data
- HTTP client for file downloads
- Partition management (year/month)

**Key Features**:
- Idempotent operations
- Metadata tracking
- Schema enforcement
- Error handling and retries

### 2. Transformation Layer

**Technology**: PySpark with Spark SQL
**Input**: Bronze layer parquet files
**Output**: Dimensional model in Silver layer

**Components**:
- `dimensional_transform.py`: Core transformation logic
- Data quality filters
- Dimension builders
- Fact table generator

**Transformations**:
```python
Raw Trip Data
    ↓ [Clean & Filter]
    ├─→ dim_datetime (calendar attributes)
    ├─→ dim_location (zone enrichment)
    ├─→ dim_rate_code (static lookup)
    ├─→ dim_payment_type (static lookup)
    └─→ fact_taxi_trips (with FKs)
```

### 3. Loading Layer

**Technology**: JDBC with PySpark
**Input**: Silver layer dimensional model
**Output**: PostgreSQL tables

**Components**:
- `db_loader.py`: Bulk loading logic
- JDBC driver management
- Index creation
- Materialized view refresh

### 4. Orchestration Layer

**Technology**: Apache Airflow
**Purpose**: Pipeline scheduling and monitoring

**DAG Structure**:
```python
bronze_ingestion
    ↓
dimensional_transform
    ↓
database_load
    ↓
data_quality_check
    ↓
refresh_materialized_view
```

**Features**:
- Task dependency management
- Retry mechanisms
- Parameter passing
- Execution history

### 5. Infrastructure Layer

**Technology**: Terraform on GCP
**Resources**: GCS, IAM, BigQuery

**Components**:
```
GCS Buckets
├── bronze-bucket (raw data, 90-day lifecycle)
├── silver-bucket (curated data)
└── gold-bucket (aggregated data)

Service Accounts
└── pipeline-sa (Storage Object Admin)

BigQuery
└── nyc_taxi_analytics (optional)
```

## Data Flow

### Detailed Flow Sequence

1. **Ingestion Phase**
   ```
   NYC TLC API
   └─→ HTTP Download
       └─→ Local Cache (/data/raw)
           └─→ Spark Read
               └─→ Add Metadata
                   └─→ Write Bronze (Partitioned)
   ```

2. **Transformation Phase**
   ```
   Bronze Layer
   └─→ Spark Read (with partition filters)
       └─→ Data Quality Filters
           ├─→ Create dim_datetime
           ├─→ Create dim_location
           ├─→ Create dim_rate_code
           ├─→ Create dim_payment_type
           └─→ Create fact_taxi_trips (join dimensions)
               └─→ Write Silver (Partitioned)
   ```

3. **Loading Phase**
   ```
   Silver Layer
   └─→ Spark Read
       └─→ JDBC Write
           └─→ PostgreSQL Tables
               └─→ Create Indexes
                   └─→ Refresh Materialized Views
   ```

## Scalability Considerations

### Current Scale

| Metric | Value |
|--------|-------|
| Monthly Data Size | ~5GB parquet |
| Processing Time | ~15 min/month |
| Spark Workers | 1 (local mode) |
| Max Recommended Months | 3-6 |

### Scaling Strategies

#### Vertical Scaling
```yaml
# Increase worker resources
spark-worker:
  environment:
    SPARK_WORKER_CORES: 4
    SPARK_WORKER_MEMORY: 8g
```

#### Horizontal Scaling
```yaml
# Add more workers
spark-worker-2:
  << : *spark-worker-template
spark-worker-3:
  << : *spark-worker-template
```

#### Cloud Scaling (GCP)
```bash
# Use Dataproc instead of local Spark
gcloud dataproc clusters create nyc-taxi-cluster \
  --region=us-central1 \
  --num-workers=5 \
  --worker-machine-type=n1-standard-4
```

## Performance Optimization

### 1. Partitioning Strategy

**Bronze Layer**:
- Partition by year/month
- Enables partition pruning
- Reduces data scanned

**Silver Layer**:
- Fact table: Partitioned by year/month
- Dimensions: No partitioning (small size)

### 2. File Formats

- **Parquet**: Columnar format, compressed
- **Snappy Compression**: Balance of speed/size
- **Predicate Pushdown**: Filter at file level

### 3. Spark Tuning

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "200")
spark.conf.set("spark.sql.files.maxPartitionBytes", "134217728")  # 128MB
```

### 4. Database Optimization

```sql
-- Indexes on foreign keys
CREATE INDEX idx_fact_pickup_datetime ON fact_taxi_trips(pickup_datetime_id);
CREATE INDEX idx_fact_pickup_location ON fact_taxi_trips(pickup_location_id);

-- Materialized views for common queries
CREATE MATERIALIZED VIEW mv_daily_trip_summary AS ...;
```

## Security Architecture

### Authentication & Authorization

```
User Request
    ↓
┌─────────────────┐
│  IAM Policy     │ ← GCP IAM roles
└────────┬────────┘
         ↓
┌─────────────────┐
│ Service Account │ ← Minimal permissions
│  pipeline-sa    │   (Storage Object Admin)
└────────┬────────┘
         ↓
┌─────────────────┐
│  GCS Buckets    │ ← Uniform bucket-level access
└─────────────────┘
```

### Data Security

- **At Rest**: GCS encryption by default
- **In Transit**: HTTPS for downloads, TLS for database
- **Access Control**: IAM roles, service account keys
- **Secrets Management**: Environment variables (upgrade to Vault in production)

### Best Practices

1. **Principle of Least Privilege**: Minimal IAM permissions
2. **Rotation**: Regular service account key rotation
3. **Audit Logging**: Enable Cloud Audit Logs
4. **VPC**: Deploy in private VPC (production)
5. **Encryption**: Customer-managed encryption keys (CMEK) for sensitive data

## Monitoring & Observability

### Logging Architecture

```
Application Logs
    ├─→ Spark Driver Logs → Spark UI
    ├─→ Airflow Task Logs → Airflow UI
    ├─→ PostgreSQL Logs → Docker logs
    └─→ (Future) → Cloud Logging
```

### Metrics Collection

**Current**:
- Spark UI: Job metrics, stage timings
- Airflow UI: DAG run duration, task success rate
- PostgreSQL: Query performance, table sizes

**Future**:
- Prometheus for metrics collection
- Grafana for visualization
- Custom metrics for data quality

## Disaster Recovery

### Backup Strategy

**Bronze Layer**:
- Source of truth: NYC TLC API (re-downloadable)
- GCS versioning enabled
- 90-day retention policy

**Silver Layer**:
- Reproducible from Bronze
- GCS versioning enabled
- No explicit backup needed

**Gold Layer** (PostgreSQL):
- Daily backups via pg_dump
- Point-in-time recovery
- Backup retention: 30 days

### Recovery Procedures

1. **Data Corruption**: Re-run pipeline from Bronze
2. **Infrastructure Failure**: Terraform re-apply
3. **Database Failure**: Restore from backup + replay recent data

## Cost Optimization

### Current Costs (Local)

- **Infrastructure**: $0 (local Docker)
- **Storage**: Local disk space only
- **Compute**: Local machine resources

### Projected GCP Costs

| Component | Monthly Cost (Estimated) |
|-----------|--------------------------|
| GCS Storage (100GB) | $2.60 |
| Dataproc (5 workers, 10 hrs/month) | $15-30 |
| BigQuery (1TB analyzed) | $5 |
| Cloud Logging | $1-5 |
| **Total** | **$25-45/month** |

### Cost Optimization Strategies

1. **Lifecycle Policies**: Auto-delete old Bronze data
2. **Spot Instances**: Use preemptible VMs for Dataproc
3. **Data Compression**: Snappy compression reduces storage
4. **Query Optimization**: Partition pruning reduces BigQuery costs
5. **Resource Scheduling**: Run during off-peak hours

## Future Architecture Enhancements

### Phase 1: Cloud Native
- Migrate to fully managed GCP services
- Use Dataproc for Spark
- Use Cloud Composer for Airflow
- Use BigQuery for analytics

### Phase 2: Real-Time
- Add Kafka for streaming ingestion
- Implement Lambda architecture
- Real-time dashboards

### Phase 3: ML Integration
- Feature store for ML pipelines
- Model training and serving
- Prediction serving layer

### Phase 4: Data Mesh
- Domain-oriented data ownership
- Self-serve data infrastructure
- Federated governance