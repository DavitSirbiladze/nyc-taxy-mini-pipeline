# Troubleshooting Guide - NYC Taxi Pipeline

## Quick Diagnostics

### Check All Services Status
```bash
docker-compose ps
```

Expected output: All services should show "Up" status

### View All Logs
```bash
docker-compose logs --tail=100 -f
```

### Check Specific Service
```bash
# Spark logs
docker-compose logs spark-master

# PostgreSQL logs
docker-compose logs postgres

# Airflow logs
docker-compose logs airflow-webserver
```

## Common Issues & Solutions

### 1. Services Won't Start

#### Issue: Port Already in Use
```
Error: Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Solution A**: Find and kill the process using the port
```bash
# Find process using port 8080
lsof -i :8080
# Or on Linux
netstat -tulpn | grep :8080

# Kill the process
kill -9 <PID>
```

**Solution B**: Change ports in docker-compose.yml
```yaml
ports:
  - "8090:8080"  # Use 8090 instead of 8080
```

#### Issue: Docker Daemon Not Running
```
Cannot connect to the Docker daemon
```

**Solution**: Start Docker Desktop
- **Mac**: Open Docker Desktop from Applications
- **Windows**: Open Docker Desktop from Start Menu
- **Linux**: `sudo systemctl start docker`

#### Issue: Insufficient Memory
```
docker-compose up fails with memory error
```

**Solution**: Increase Docker memory allocation
1. Open Docker Desktop
2. Go to Settings → Resources
3. Increase Memory to at least 4GB
4. Click "Apply & Restart"

### 2. PostgreSQL Issues

#### Issue: Database Connection Refused
```
psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
```

**Solution**: Wait for PostgreSQL to be healthy
```bash
# Check health
docker-compose ps postgres

# If unhealthy, check logs
docker-compose logs postgres

# Restart if needed
docker-compose restart postgres
sleep 10
```

#### Issue: Database Not Initialized
```
ERROR: relation "fact_taxi_trips" does not exist
```

**Solution**: Run schema initialization
```bash
docker-compose exec postgres psql -U taxi_user -d nyc_taxi \
  -f /docker-entrypoint-initdb.d/02-schema.sql
```

#### Issue: Out of Disk Space
```
ERROR: could not extend file: No space left on device
```

**Solution**: Free up disk space
```bash
# Remove old Docker volumes
docker volume prune -f

# Clean up data directory
make clean

# Remove unused Docker images
docker image prune -a
```

### 3. Spark Job Failures

#### Issue: Out of Memory Error
```
java.lang.OutOfMemoryError: Java heap space
```

**Solution A**: Increase worker memory
```yaml
# In docker-compose.yml
spark-worker:
  environment:
    SPARK_WORKER_MEMORY: 4g  # Increase from 2g
```

**Solution B**: Process fewer months
```bash
# Instead of all 12 months
make run-pipeline YEAR=2023 MONTHS=1,2,3
```

**Solution C**: Increase shuffle partitions
```python
# In spark job
spark.conf.set("spark.sql.shuffle.partitions", "400")  # Increase from 200
```

#### Issue: Data Download Fails
```
Failed to download: https://d37ci6vzurychx.cloudfront.net/trip-data/...
```

**Solution A**: Check internet connection
```bash
ping d37ci6vzurychx.cloudfront.net
```

**Solution B**: Try different month (some months may be unavailable)
```bash
make run-pipeline YEAR=2023 MONTHS=2  # Try February instead
```

**Solution C**: Manual download
```bash
# Download manually
wget https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet \
  -O data/raw/yellow_trips/yellow_tripdata_2023-01.parquet

# Then run pipeline
make run-pipeline YEAR=2023 MONTHS=1
```

#### Issue: PySpark Import Errors
```
ModuleNotFoundError: No module named 'pyspark'
```

**Solution**: Rebuild Docker images
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Issue: JDBC Driver Not Found
```
java.lang.ClassNotFoundException: org.postgresql.Driver
```

**Solution**: Ensure PostgreSQL JDBC jar is in Spark classpath
```bash
# Check if jar exists
docker-compose exec spark-master ls -la /opt/spark/jars/ | grep postgresql

# If missing, rebuild images
docker-compose build --no-cache
```

### 4. Airflow Issues

#### Issue: Airflow UI Not Loading
```
Connection refused when accessing http://localhost:8081
```

**Solution**: Check Airflow webserver status
```bash
# Check status
docker-compose ps airflow-webserver

# If not running, check logs
docker-compose logs airflow-webserver

# Restart
docker-compose restart airflow-webserver
sleep 20
```

#### Issue: DAG Not Appearing
```
DAG 'nyc_taxi_pipeline' not found
```

**Solution A**: Check DAG syntax
```bash
docker-compose exec airflow-webserver python /opt/airflow/dags/nyc_taxi_pipeline.py
```

**Solution B**: Refresh DAGs in UI
1. Open Airflow UI
2. Click the refresh button
3. Wait 30 seconds for DAG to appear

#### Issue: Task Fails with "Variable not found"
```
Variable spark_master_url not found
```

**Solution**: Set Airflow variables
```bash
docker-compose exec airflow-webserver airflow variables set \
  spark_master_url "spark://spark-master:7077"
```

#### Issue: Database Connection Error in Airflow
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Verify Airflow database connection
```bash
# Check environment variable
docker-compose exec airflow-webserver env | grep SQL_ALCHEMY

# Should show: AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...
```

### 5. Data Quality Issues

#### Issue: Zero Records in Fact Table
```
SELECT COUNT(*) FROM fact_taxi_trips;
-- Returns: 0
```

**Solution**: Check each pipeline stage
```bash
# 1. Check bronze data exists
docker-compose exec spark-master ls -la /data/bronze/nyc_taxi/yellow_trips/

# 2. Check silver data exists
docker-compose exec spark-master ls -la /data/silver/nyc_taxi/facts/

# 3. Check logs for errors
docker-compose logs spark-master | grep ERROR

# 4. Re-run pipeline with verbose logging
docker-compose exec spark-master spark-submit \
  --conf spark.driver.log.level=INFO \
  /opt/spark-app/jobs/bronze_ingestion.py --year 2023 --months 1
```

#### Issue: Duplicate Records
```
SELECT trip_id, COUNT(*) FROM fact_taxi_trips GROUP BY trip_id HAVING COUNT(*) > 1;
```

**Solution**: Re-run with overwrite mode
```bash
# Overwrite will replace existing partition
make run-loader YEAR=2023 MONTHS=1
```

#### Issue: Foreign Key Violations
```
ERROR: insert or update on table "fact_taxi_trips" violates foreign key constraint
```

**Solution**: Ensure dimensions are loaded first
```bash
# Check dimension tables have data
docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
  "SELECT 'dim_datetime' as table_name, COUNT(*) FROM dim_datetime
   UNION ALL SELECT 'dim_location', COUNT(*) FROM dim_location;"

# If empty, re-run transformation and loading
make run-transform YEAR=2023 MONTHS=1
make run-loader YEAR=2023 MONTHS=1
```

### 6. Performance Issues

#### Issue: Queries Taking Too Long
```
Query running for > 30 seconds
```

**Solution A**: Check if indexes exist
```sql
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public';
```

**Solution B**: Analyze tables
```sql
ANALYZE fact_taxi_trips;
ANALYZE dim_datetime;
ANALYZE dim_location;
```

**Solution C**: Refresh materialized view
```bash
docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
  "REFRESH MATERIALIZED VIEW mv_daily_trip_summary;"
```

#### Issue: Pipeline Taking Too Long
```
Bronze ingestion taking > 30 minutes
```

**Solution A**: Check network speed
```bash
# Test download speed
time wget -O /dev/null https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet
```

**Solution B**: Increase parallelism
```yaml
# In docker-compose.yml
spark-worker:
  environment:
    SPARK_WORKER_CORES: 4  # Increase cores
```

**Solution C**: Process fewer months at once
```bash
# Instead of
make run-pipeline YEAR=2023 MONTHS=1,2,3,4,5,6

# Do
make run-pipeline YEAR=2023 MONTHS=1,2,3
# Then
make run-pipeline YEAR=2023 MONTHS=4,5,6
```

### 7. Terraform Issues

#### Issue: Terraform Init Fails
```
Error: Failed to query available provider packages
```

**Solution**: Check internet connection and retry
```bash
cd terraform
rm -rf .terraform
terraform init
```

#### Issue: GCP Authentication Error
```
Error: google: could not find default credentials
```

**Solution**: Set up GCP credentials
```bash
# Option A: Using gcloud CLI
gcloud auth application-default login

# Option B: Using service account key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

#### Issue: Resource Already Exists
```
Error: A resource with the ID "..." already exists
```

**Solution**: Import existing resource
```bash
terraform import google_storage_bucket.bronze_zone existing-bucket-name
```

### 8. Testing Issues

#### Issue: Tests Fail to Run
```
ImportError: No module named 'pytest'
```

**Solution**: Install test dependencies
```bash
cd spark
pip install -r requirements.txt
```

#### Issue: Tests Pass Locally but Fail in CI
```
Tests pass on local machine but fail in GitHub Actions
```

**Solution**: Check CI environment differences
```bash
# Compare Python versions
python --version  # Local
# vs CI workflow python version

# Check for missing dependencies
pip list
```

## Debugging Tips

### Enable Verbose Logging

**For Spark Jobs**:
```bash
docker-compose exec spark-master spark-submit \
  --conf spark.driver.log.level=DEBUG \
  /opt/spark-app/jobs/bronze_ingestion.py --year 2023 --months 1
```

**For PostgreSQL**:
```bash
# Edit postgresql.conf to enable query logging
docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
  "ALTER SYSTEM SET log_statement = 'all';"
docker-compose restart postgres
```

### Inspect Data at Each Stage

**Bronze Layer**:
```bash
docker-compose exec spark-master spark-submit --conf spark.driver.log.level=WARN \
  -c "from pyspark.sql import SparkSession; \
      spark = SparkSession.builder.appName('test').getOrCreate(); \
      df = spark.read.parquet('/data/bronze/nyc_taxi/yellow_trips/'); \
      print(df.count()); \
      df.show(5)"
```

**Silver Layer**:
```bash
docker-compose exec spark-master ls -lh /data/silver/nyc_taxi/facts/fact_taxi_trips/
```

**Gold Layer**:
```bash
docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
  "SELECT * FROM fact_taxi_trips LIMIT 5;"
```

### Check Resource Usage

**Docker Container Stats**:
```bash
docker stats
```

**Disk Usage**:
```bash
du -sh data/*
```

**Database Size**:
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Emergency Recovery

### Complete Reset

If everything is broken and you want to start fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Remove all data
rm -rf data/{bronze,silver,gold}/*
rm -rf logs/*

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d

# Wait for services
sleep 30

# Re-run setup
./setup.sh
```

### Backup Before Recovery

```bash
# Backup database
docker-compose exec postgres pg_dump -U taxi_user nyc_taxi > backup.sql

# Backup data directories
tar -czf data_backup.tar.gz data/

# Restore later if needed
docker-compose exec -T postgres psql -U taxi_user -d nyc_taxi < backup.sql
```

## Getting Help

### Collect Diagnostic Information

Before asking for help, collect these details:

```bash
# System info
uname -a
docker --version
docker-compose --version

# Service status
docker-compose ps

# Recent logs
docker-compose logs --tail=200 > all_logs.txt

# Disk space
df -h

# Memory usage
free -h  # Linux
# Or: vm_stat  # Mac
```

### Where to Get Help

1. **Check Documentation**: README.md, architecture.md
2. **Search Logs**: `docker-compose logs | grep ERROR`
3. **GitHub Issues**: Open an issue with diagnostic info
4. **Stack Overflow**: Tag with `apache-spark`, `airflow`, `postgresql`

## Prevention

### Regular Maintenance

```bash
# Weekly: Clean up unused Docker resources
docker system prune -f

# Monthly: Update Docker images
docker-compose pull
docker-compose build --pull

# Check for updates
docker-compose config --services | xargs -I {} docker-compose pull {}
```

### Monitoring Checklist

- [ ] Check disk space weekly
- [ ] Review logs for errors
- [ ] Verify backup integrity
- [ ] Test recovery procedures
- [ ] Update dependencies regularly

## Known Limitations

1. **Single Worker**: Limited parallelism with one Spark worker
2. **Local Storage**: Not suitable for large-scale production
3. **No HA**: Single point of failure for each service
4. **Memory Constraints**: Docker Desktop memory limits
5. **No Auto-Scaling**: Manual resource management

See README.md "Limitations & Future Improvements" section for more details.