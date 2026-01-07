# NYC Taxi Pipeline - Quick Start Guide

## 🎯 What This Pipeline Does

Processes NYC Taxi trip data through a production-ready data pipeline:
- **Downloads** raw data from NYC TLC (Taxi & Limousine Commission)
- **Cleans** and validates the data with quality checks
- **Transforms** into a star schema dimensional model
- **Loads** into PostgreSQL for analytics and BI tools

## ⚡ 5-Minute Quick Start

### Prerequisites Check

```bash
# Check Docker is installed
docker --version
# Should show: Docker version 20.x or higher

# Check Docker Compose is installed
docker-compose --version
# Should show: Docker Compose version 2.x or higher
```

### Step 1: Setup (2 minutes)

```bash
# Clone the repository
git clone <your-repo-url>
cd nyc-taxi-pipeline

# Create environment file
cp .env.example .env

# Create data directories
mkdir -p data/{raw,bronze,silver,gold}
```

### Step 2: Start Services (1 minute)

```bash
# Build and start all services
docker-compose up -d

# Wait for services to be ready (about 30 seconds)
sleep 30

# Verify all services are running
docker-compose ps
```

You should see:
- ✅ spark-master (running)
- ✅ spark-worker (running)
- ✅ postgres-taxi (running, healthy)
- ✅ airflow-webserver (running)
- ✅ airflow-scheduler (running)

### Step 3: Run Pipeline (2 minutes)

```bash
# Run complete pipeline for January 2023
make run-pipeline YEAR=2023 MONTHS=1
```

This will:
1. Download NYC Taxi data (~1GB)
2. Process and clean the data
3. Create dimensional model
4. Load into PostgreSQL

**Expected output:**
```
Running bronze ingestion...
✓ Downloaded yellow_tripdata_2023-01.parquet
✓ Ingested 3,066,766 records to bronze

Running dimensional transformation...
✓ Created dim_datetime with 198,450 records
✓ Created dim_location with 265 records
✓ Created fact_taxi_trips with 2,964,624 records

Running database load...
✓ Loaded dimensions to PostgreSQL
✓ Loaded facts to PostgreSQL

Pipeline execution finished!
```

### Step 4: Query Data (30 seconds)

```bash
# Connect to database
docker-compose exec postgres psql -U taxi_user -d nyc_taxi

# Run your first query
SELECT COUNT(*) as total_trips, 
       AVG(fare_amount) as avg_fare,
       SUM(total_amount) as total_revenue
FROM fact_taxi_trips;
```

**Example result:**
```
 total_trips | avg_fare  | total_revenue
-------------+-----------+---------------
   2,964,624 |     14.32 |  51,245,892.43
```

## 📊 Explore Your Data

### Using SQL

```sql
-- Top 10 pickup locations
SELECT l.zone_name, l.borough, COUNT(*) as trips
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
GROUP BY l.zone_name, l.borough
ORDER BY trips DESC
LIMIT 10;

-- Average tip by payment type
SELECT pt.payment_type_description,
       AVG(f.tip_amount) as avg_tip,
       COUNT(*) as trip_count
FROM fact_taxi_trips f
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
GROUP BY pt.payment_type_description;

-- Hourly trip patterns
SELECT dt.hour,
       COUNT(*) as trips,
       AVG(f.trip_distance) as avg_distance
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.hour
ORDER BY dt.hour;
```

### Using Web UIs

**Spark UI** (Monitor jobs):
- URL: http://localhost:8080
- View job progress, execution plans, and metrics

**Airflow UI** (Orchestration):
- URL: http://localhost:8081
- Login: admin / admin
- View DAG execution history and logs

## 🔄 Processing More Data

### Single Month
```bash
make run-pipeline YEAR=2023 MONTHS=2
```

### Multiple Months
```bash
make run-pipeline YEAR=2023 MONTHS=1,2,3
```

### Backfill Entire Year
```bash
make run-pipeline YEAR=2023 MONTHS=1,2,3,4,5,6,7,8,9,10,11,12
```

**Note**: Full year processing takes ~2-3 hours and requires ~60GB disk space.

## 🎨 Using Airflow (Alternative Method)

1. **Open Airflow UI**: http://localhost:8081
2. **Login**: admin / admin
3. **Find DAG**: `nyc_taxi_pipeline`
4. **Enable DAG**: Toggle the switch to ON
5. **Trigger**: Click "Trigger DAG" button
6. **Configure Parameters**:
   ```json
   {
     "year": 2023,
     "months": "1,2,3",
     "storage_type": "local"
   }
   ```
7. **Monitor**: Watch tasks complete in the Graph View

## 🛠️ Common Tasks

### Check Data Counts
```bash
make db-query-facts
```

### View Daily Summary
```bash
make db-query-summary
```

### Connect to Database
```bash
make db-connect
# Then run any SQL queries
```

### View Logs
```bash
# All services
make logs

# Just Spark
make logs-spark

# Just Airflow
make logs-airflow
```

### Stop Services
```bash
# Stop but keep data
make down

# Stop and remove all data
make down-clean
```

## 🧪 Verify Installation

Run the test suite to ensure everything is working:

```bash
# Run all tests
make test

# Expected output:
# ===== 12 passed in 45.23s =====
```

## 📈 Sample Analytical Queries

### Business Questions & Queries

**Q: What's the busiest hour of the day?**
```sql
SELECT dt.hour, COUNT(*) as trips
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.hour
ORDER BY trips DESC;
```

**Q: Which borough generates most revenue?**
```sql
SELECT l.borough, 
       COUNT(*) as trips,
       SUM(f.total_amount) as revenue
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
WHERE l.borough IS NOT NULL
GROUP BY l.borough
ORDER BY revenue DESC;
```

**Q: Weekend vs Weekday patterns?**
```sql
SELECT dt.is_weekend,
       COUNT(*) as trips,
       AVG(f.trip_distance) as avg_distance,
       AVG(f.total_amount) as avg_fare
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.is_weekend;
```

**Q: Airport trips analysis?**
```sql
SELECT COUNT(*) as airport_trips,
       AVG(f.fare_amount) as avg_fare,
       AVG(f.trip_distance) as avg_distance
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
WHERE l.service_zone = 'Airports';
```

## 🐛 Troubleshooting

### Services Won't Start
```bash
# Check if ports are already in use
lsof -i :8080  # Spark
lsof -i :8081  # Airflow
lsof -i :5432  # PostgreSQL

# Kill conflicting processes or change ports in docker-compose.yml
```

### Out of Disk Space
```bash
# Clean up old data
make clean

# Remove Docker volumes
docker volume prune
```

### Pipeline Fails During Download
```bash
# Check internet connection
ping d37ci6vzurychx.cloudfront.net

# Try different month (some months might be unavailable)
make run-pipeline YEAR=2023 MONTHS=2
```

### PostgreSQL Connection Issues
```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# If unhealthy, restart
docker-compose restart postgres
sleep 10
```

### Memory Issues
```bash
# Increase Docker Desktop memory allocation
# Docker Desktop → Settings → Resources → Memory → 8GB

# Or reduce Spark worker memory in docker-compose.yml
# SPARK_WORKER_MEMORY: 1g
```

## 📚 Next Steps

### Learn More
1. **Read Full Documentation**: See [README.md](README.md)
2. **Architecture Details**: See [docs/architecture.md](docs/architecture.md)
3. **Data Model**: See [docs/data_model.md](docs/data_model.md)

### Advanced Usage
1. **Deploy to GCP**: Follow Terraform guide
2. **Add Custom Transformations**: Modify `dimensional_transform.py`
3. **Create BI Dashboards**: Connect Tableau/PowerBI to PostgreSQL
4. **Add Data Quality Checks**: Extend `data_quality_check` task

### Integration Examples

**Connect with BI Tools:**
```
Host: localhost
Port: 5432
Database: nyc_taxi
User: taxi_user
Password: taxi_pass
```

**Export Data:**
```bash
# Export to CSV
docker-compose exec postgres psql -U taxi_user -d nyc_taxi \
  -c "COPY (SELECT * FROM mv_daily_trip_summary) TO STDOUT CSV HEADER" \
  > daily_summary.csv
```

**Python Integration:**
```python
import pandas as pd
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="nyc_taxi",
    user="taxi_user",
    password="taxi_pass"
)

df = pd.read_sql("SELECT * FROM fact_taxi_trips LIMIT 1000", conn)
print(df.head())
```

## 🎓 Understanding the Pipeline

### Data Flow
```
NYC TLC API → Bronze (Raw) → Silver (Dimensional Model) → Gold (PostgreSQL)
```

### What Gets Created

**In Storage** (`/data/`):
- `bronze/nyc_taxi/yellow_trips/` - Raw parquet files
- `silver/nyc_taxi/dimensions/` - Dimension tables
- `silver/nyc_taxi/facts/` - Fact table

**In PostgreSQL**:
- `fact_taxi_trips` - Main fact table (2.9M rows for Jan 2023)
- `dim_datetime` - Time dimension (198K rows)
- `dim_location` - Location dimension (265 rows)
- `dim_rate_code` - Rate codes (6 rows)
- `dim_payment_type` - Payment types (6 rows)

### Processing Time
- Bronze ingestion: ~5-10 minutes (depends on download speed)
- Transformation: ~3-5 minutes
- Database load: ~2-3 minutes
- **Total: ~15 minutes per month**

## 🚀 Tips for Success

1. **Start Small**: Process 1-2 months first
2. **Monitor Resources**: Watch CPU/memory usage
3. **Check Logs**: Use `make logs` if something fails
4. **Test Queries**: Verify data before processing more months
5. **Backup Data**: Copy `/data/` folder before major changes

## 💡 Did You Know?

- The pipeline is **idempotent** - you can safely re-run any month
- All data is stored in **partitioned** format for efficient queries
- The dimensional model supports **time-travel** queries with datetime dimension
- You can **scale horizontally** by adding more Spark workers

## 🤝 Getting Help

1. **Check logs**: `make logs`
2. **Review documentation**: [README.md](README.md)
3. **Common issues**: See Troubleshooting section above
4. **Open an issue**: On GitHub repository

## ✅ Success Checklist

- [ ] All Docker containers running
- [ ] Pipeline completed without errors
- [ ] Data visible in PostgreSQL
- [ ] Sample queries return results
- [ ] Airflow UI accessible
- [ ] Spark UI shows completed jobs

**Congratulations! Your NYC Taxi Pipeline is ready for analytics!** 🎉