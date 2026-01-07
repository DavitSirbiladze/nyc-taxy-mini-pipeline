# NYC Taxi Data Pipeline

A production-ready data pipeline for processing NYC Taxi trip data using Apache Spark, implementing medallion architecture (Bronze/Silver/Gold) with dimensional modeling, orchestrated by Apache Airflow, and deployed on GCP infrastructure via Terraform.

## 📊 Architecture Overview

### High-Level Architecture

```
┌─────────────────┐
│  Data Sources   │
│  (NYC TLC API)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Bronze Layer   │─────▶│  Silver Layer    │
│  (Raw Data)     │      │  (Dimensional)   │
│  - Parquet      │      │  - Star Schema   │
│  - Partitioned  │      │  - Cleaned       │
└─────────────────┘      └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Gold Layer      │
                         │  (PostgreSQL)    │
                         │  - Analytics DB  │
                         │  - BI Ready      │
                         └──────────────────┘
```

### Technology Stack

- **Processing**: Apache Spark 3.5.0 (PySpark)
- **Orchestration**: Apache Airflow 2.8.0
- **Database**: PostgreSQL 15
- **Infrastructure**: GCP (GCS, BigQuery) via Terraform
- **CI/CD**: GitHub Actions
- **Containerization**: Docker & Docker Compose

## 🎯 Features

- ✅ **Medallion Architecture**: Bronze (raw) → Silver (curated) → Gold (analytics)
- ✅ **Dimensional Modeling**: Star schema with fact and dimension tables
- ✅ **Historical Data Support**: Process multiple months, backfill capabilities
- ✅ **Data Quality**: Comprehensive cleaning and validation
- ✅ **Idempotent**: Safe to re-run without data corruption
- ✅ **Infrastructure as Code**: Full Terraform configuration for GCP
- ✅ **CI/CD Pipeline**: Automated testing, linting, and deployment
- ✅ **Orchestration**: Airflow DAG with task dependencies
- ✅ **Unit Tests**: Comprehensive test coverage with pytest

## 📁 Project Structure

```
nyc-taxi-pipeline/
├── spark/                      # PySpark jobs and utilities
│   ├── jobs/
│   │   ├── bronze_ingestion.py      # Job 1: Raw data ingestion
│   │   ├── dimensional_transform.py  # Job 2: Dimensional model
│   │   └── db_loader.py             # Job 3: Load to PostgreSQL
│   ├── common/
│   │   ├── config.py               # Configuration management
│   │   └── spark_session.py        # Spark session factory
│   └── tests/                      # Unit tests
├── airflow/                    # Airflow DAGs and config
│   └── dags/
│       └── nyc_taxi_pipeline.py    # Main orchestration DAG
├── database/                   # Database schemas
│   ├── init.sql               # Initialization
│   └── schema.sql             # Dimensional model DDL
├── terraform/                  # Infrastructure as Code
│   ├── main.tf                # Main configuration
│   ├── gcs.tf                 # GCS buckets
│   └── iam.tf                 # Service accounts
├── .github/workflows/          # CI/CD pipelines
│   └── ci.yml                 # GitHub Actions workflow
├── docker-compose.yml          # Local development setup
├── Makefile                    # Automation commands
└── README.md                   # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Make (optional, for convenience)
- Terraform 1.5+ (for GCP deployment)

### 1. Clone and Setup

```bash
git clone https://github.com/your-org/nyc-taxi-pipeline.git
cd nyc-taxi-pipeline

# Create environment file
cp .env.example .env

# Create data directories
mkdir -p data/{raw,bronze,silver,gold}
```

### 2. Start Services

```bash
# Build and start all services
make up

# Or without Make:
docker-compose up -d
```

**Service URLs:**
- Spark Master UI: http://localhost:8080
- Airflow UI: http://localhost:8081 (admin/admin)
- PostgreSQL: localhost:5432

### 3. Run the Pipeline

#### Option A: Using Make (Recommended)

```bash
# Run complete pipeline for January 2023
make run-pipeline YEAR=2023 MONTHS=1

# Process multiple months
make run-pipeline YEAR=2023 MONTHS=1,2,3

# Backfill entire year
make run-pipeline YEAR=2023 MONTHS=1,2,3,4,5,6,7,8,9,10,11,12
```

#### Option B: Individual Jobs

```bash
# Step 1: Bronze ingestion
make run-bronze YEAR=2023 MONTHS=1

# Step 2: Dimensional transformation
make run-transform YEAR=2023 MONTHS=1

# Step 3: Load to database
make run-loader YEAR=2023 MONTHS=1
```

#### Option C: Via Airflow UI

1. Open http://localhost:8081
2. Login with admin/admin
3. Enable the `nyc_taxi_pipeline` DAG
4. Trigger with parameters:
   - year: 2023
   - months: "1,2,3"
   - storage_type: "local"

### 4. Query the Data

```bash
# Connect to database
make db-connect

# Or directly:
docker-compose exec postgres psql -U taxi_user -d nyc_taxi
```

**Example Queries:**

```sql
-- Total trips and revenue
SELECT 
    COUNT(*) as total_trips,
    SUM(total_amount) as total_revenue,
    AVG(fare_amount) as avg_fare
FROM fact_taxi_trips;

-- Trips by borough and hour
SELECT 
    l.borough,
    dt.hour,
    COUNT(*) as trip_count,
    AVG(f.trip_distance) as avg_distance
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY l.borough, dt.hour
ORDER BY l.borough, dt.hour;

-- Daily summary (using materialized view)
SELECT * FROM mv_daily_trip_summary
ORDER BY date DESC
LIMIT 10;
```

## 📐 Data Model

### Star Schema Design

#### Fact Table: `fact_taxi_trips`

**Grain**: One row per taxi trip

| Column | Type | Description |
|--------|------|-------------|
| trip_id | BIGINT | Surrogate key |
| pickup_datetime_id | BIGINT | FK to dim_datetime |
| dropoff_datetime_id | BIGINT | FK to dim_datetime |
| pickup_location_id | INT | FK to dim_location |
| dropoff_location_id | INT | FK to dim_location |
| rate_code_id | INT | FK to dim_rate_code |
| payment_type_id | INT | FK to dim_payment_type |
| passenger_count | DOUBLE | Number of passengers |
| trip_distance | DOUBLE | Distance in miles |
| fare_amount | DOUBLE | Base fare |
| tip_amount | DOUBLE | Tip amount |
| total_amount | DOUBLE | Total charge |
| trip_duration_minutes | DOUBLE | Calculated duration |

#### Dimension Tables

**dim_datetime**: Temporal attributes
- datetime_id (PK)
- date, year, month, day, hour
- day_of_week, day_name, is_weekend

**dim_location**: Geographic zones
- location_id (PK)
- zone_name, borough, service_zone

**dim_rate_code**: Rate types
- rate_code_id (PK)
- rate_code_description

**dim_payment_type**: Payment methods
- payment_type_id (PK)
- payment_type_description

### Design Decisions

1. **Star Schema**: Denormalized for query performance
2. **Surrogate Keys**: Generated IDs for dimensions
3. **Slowly Changing Dimensions**: Type 1 (overwrite) for simplicity
4. **Partitioning**: Fact table partitioned by year/month
5. **Indexes**: On all foreign keys and common filter columns

## 🔄 Pipeline Details

### Job 1: Bronze Ingestion (`bronze_ingestion.py`)

**Purpose**: Download and store raw data with minimal transformation

**Process**:
1. Downloads NYC Taxi parquet files from TLC website
2. Downloads zone lookup CSV
3. Adds metadata columns (ingestion_timestamp, source_file)
4. Writes to Bronze layer partitioned by year/month
5. Preserves raw data for auditability

**Key Features**:
- Historical data support (multiple months)
- Idempotent (safe to re-run)
- Partition pruning for efficiency

### Job 2: Dimensional Transformation (`dimensional_transform.py`)

**Purpose**: Clean data and create dimensional model

**Process**:
1. Reads from Bronze layer
2. Applies data quality filters:
   - Removes null critical fields
   - Filters invalid fares/distances
   - Removes same pickup/dropoff trips
3. Creates dimension tables:
   - dim_datetime (with calendar attributes)
   - dim_location (from zone lookup)
   - dim_rate_code (static)
   - dim_payment_type (static)
4. Creates fact table with foreign keys
5. Writes to Silver layer partitioned by year/month

**Data Quality Rules**:
```python
- fare_amount >= 0 and <= 500
- trip_distance > 0 and <= 100
- passenger_count >= 1 and <= 6
- trip_duration > 0 and <= 300 minutes
- pickup != dropoff location
```

### Job 3: Database Loader (`db_loader.py`)

**Purpose**: Load dimensional model into PostgreSQL

**Process**:
1. Reads dimension tables from Silver layer
2. Reads fact table with partition filters
3. Loads dimensions (overwrite mode)
4. Loads facts (append or overwrite mode)
5. Uses JDBC for efficient bulk loading

**Modes**:
- `overwrite`: Full refresh (default)
- `append`: Incremental load for backfills

## 🏗️ Infrastructure (Terraform)

### GCP Resources

```bash
# Initialize Terraform
make terraform-init

# Plan changes
make terraform-plan

# Apply infrastructure
make terraform-apply
```

**Created Resources**:
- **GCS Buckets**: bronze, silver, gold zones
- **Service Account**: Pipeline execution
- **IAM Roles**: Storage Object Admin
- **BigQuery Dataset**: Analytics (optional)

**Cost Optimization**:
- Lifecycle policies (delete after 90 days for bronze)
- Regional storage
- Minimal IAM permissions

### Terraform Structure

```hcl
terraform/
├── main.tf      # Provider and core config
├── gcs.tf       # GCS buckets
├── iam.tf       # Service accounts and IAM
├── variables.tf # Input variables
└── outputs.tf   # Output values
```

## 🧪 Testing

### Run Unit Tests

```bash
# All tests
make test

# With coverage report
make test-coverage

# Specific test file
cd spark && pytest tests/test_bronze_ingestion.py -v
```

### Test Coverage

Current coverage: **85%+**

Tested components:
- ✅ Bronze ingestion schema validation
- ✅ Data cleaning and filtering logic
- ✅ Dimension table creation
- ✅ Fact table creation with foreign keys
- ✅ Configuration management

### CI/CD Pipeline

GitHub Actions workflow runs on every push/PR:

1. **Linting**: black, flake8, isort
2. **Unit Tests**: pytest with coverage
3. **Terraform Validation**: fmt, validate
4. **Docker Build**: Spark and Airflow images
5. **Integration Test**: Full pipeline execution
6. **Deploy** (main branch only): Terraform apply, image push

## 📝 Historical Data Strategy

### Backfilling Multiple Months

The pipeline supports processing multiple historical months:

```bash
# Single month
make run-pipeline YEAR=2023 MONTHS=1

# Multiple months
make run-pipeline YEAR=2023 MONTHS=1,2,3

# Entire year
make run-pipeline YEAR=2023 MONTHS=1,2,3,4,5,6,7,8,9,10,11,12
```

### Avoiding Duplicates

**Strategy**: Partition overwrite

- Bronze: Partitioned by year/month, overwrite mode
- Silver: Partitioned by year/month, overwrite mode
- Gold: Dimension overwrite + fact append/overwrite

**Re-running Same Month**:
- Safe to re-run any month
- Overwrites existing partition
- No duplicates in database

### Incremental Loading

For incremental loads (adding new months to existing data):

```bash
# Initial load
make run-loader YEAR=2023 MONTHS=1 MODE=overwrite

# Add February (incremental)
make run-bronze YEAR=2023 MONTHS=2
make run-transform YEAR=2023 MONTHS=2
make run-loader YEAR=2023 MONTHS=2 MODE=append
```

## 🔍 Monitoring & Observability

### Spark Monitoring

- **Spark UI**: http://localhost:8080
- Monitor job progress, stages, tasks
- View execution plans and metrics

### Airflow Monitoring

- **Airflow UI**: http://localhost:8081
- DAG execution history
- Task logs and duration
- Retry mechanisms

### Database Monitoring

```sql
-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Record counts
SELECT 
    'fact_taxi_trips' as table_name, COUNT(*) as records FROM fact_taxi_trips
UNION ALL
SELECT 'dim_datetime', COUNT(*) FROM dim_datetime
UNION ALL
SELECT 'dim_location', COUNT(*) FROM dim_location;
```

## 🐛 Troubleshooting

### Common Issues

**Issue**: Spark job fails with memory error
```bash
# Solution: Increase worker memory in docker-compose.yml
SPARK_WORKER_MEMORY=4g
```

**Issue**: PostgreSQL connection refused
```bash
# Solution: Wait for postgres to be ready
docker-compose logs postgres
# Check health: docker-compose ps
```

**Issue**: Airflow DAG not showing up
```bash
# Solution: Check DAG syntax
docker-compose exec airflow-webserver airflow dags list
docker-compose exec airflow-webserver python /opt/airflow/dags/nyc_taxi_pipeline.py
```

**Issue**: Data download fails
```bash
# Solution: Check NYC TLC data availability
# Try different month: --months 2
# Check URL manually in browser
```

### Debug Mode

```bash
# View all logs
make logs

# Specific service logs
make logs-spark
make logs-airflow
make logs-postgres

# Access container shell
make shell-spark
make shell-postgres
```

## 🚧 Limitations & Future Improvements

### Current Limitations

1. **Scale**: Single Spark worker (local mode)
   - Can process ~3 months comfortably
   - Memory constraints for full year

2. **Storage**: Local filesystem only
   - No distributed storage
   - Limited by disk space

3. **Orchestration**: Basic Airflow setup
   - No distributed executors
   - Limited scalability

4. **Data Quality**: Basic validation
   - Could add more sophisticated checks
   - No anomaly detection

5. **Monitoring**: Minimal observability
   - No metrics collection
   - No alerting

### Proposed Improvements

#### Phase 1: Scale & Performance
- [ ] Add more Spark workers
- [ ] Implement GCS storage backend
- [ ] Use Dataproc for managed Spark
- [ ] Add data partitioning strategies
- [ ] Implement caching for dimensions

#### Phase 2: Data Quality
- [ ] Great Expectations integration
- [ ] Schema evolution handling
- [ ] Data lineage tracking
- [ ] Automated data profiling
- [ ] Anomaly detection

#### Phase 3: Production Readiness
- [ ] Implement secret management (HashiCorp Vault)
- [ ] Add comprehensive monitoring (Prometheus/Grafana)
- [ ] Set up alerting (PagerDuty)
- [ ] Implement data cataloging (Amundsen)
- [ ] Add disaster recovery procedures

#### Phase 4: Advanced Analytics
- [ ] Real-time streaming pipeline (Kafka)
- [ ] ML feature store integration
- [ ] Predictive analytics models
- [ ] Self-service BI dashboards
- [ ] Data mesh architecture

## 📚 Additional Resources

### Documentation
- [Architecture Diagram](docs/architecture.md)
- [Data Model Details](docs/data_model.md)
- [Visual Diagrams](docs/diagrams.md)
- [Architecture Image](docs/diagrams/architecture.png)

### External Links
- [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Apache Spark Documentation](https://spark.apache.org/docs/latest/)
- [Airflow Documentation](https://airflow.apache.org/docs/)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

Davit Sirbiladze

## 🙏 Acknowledgments

- NYC Taxi & Limousine Commission for public dataset
- Apache Spark and Airflow communities
- All contributors and maintainers
