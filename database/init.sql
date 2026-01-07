-- Database initialization script
-- Creates necessary extensions and configurations

-- Create extensions
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create separate database for Airflow (if not exists)
CREATE DATABASE airflow;
GRANT ALL PRIVILEGES ON DATABASE airflow TO taxi_user;

-- Performance tuning for analytical queries
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';