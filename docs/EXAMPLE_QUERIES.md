# NYC Taxi Pipeline - Example SQL Queries

This document provides a comprehensive collection of SQL queries for analyzing NYC Taxi data using the dimensional model.

## Table of Contents

- [Basic Queries](#basic-queries)
- [Temporal Analysis](#temporal-analysis)
- [Geographic Analysis](#geographic-analysis)
- [Revenue Analysis](#revenue-analysis)
- [Customer Behavior](#customer-behavior)
- [Performance Analysis](#performance-analysis)
- [Advanced Analytics](#advanced-analytics)

## Basic Queries

### Total Trip Count and Revenue

```sql
-- Overall statistics
SELECT 
    COUNT(*) AS total_trips,
    COUNT(DISTINCT DATE(dt.datetime_value)) AS days_of_data,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue,
    ROUND(AVG(passenger_count)::numeric, 1) AS avg_passengers
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id;
```

### Trip Distribution by Month

```sql
SELECT 
    dt.year,
    dt.month_name,
    COUNT(*) AS trip_count,
    ROUND(SUM(total_amount)::numeric, 2) AS revenue,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.year, dt.month, dt.month_name
ORDER BY dt.year, dt.month;
```

### Sample Trip Details

```sql
-- View sample trips with all dimensional attributes
SELECT 
    f.trip_id,
    pdt.datetime_value AS pickup_time,
    ddt.datetime_value AS dropoff_time,
    f.trip_duration_minutes,
    pl.zone_name AS pickup_zone,
    pl.borough AS pickup_borough,
    dl.zone_name AS dropoff_zone,
    dl.borough AS dropoff_borough,
    f.trip_distance,
    f.passenger_count,
    pt.payment_type_description,
    f.fare_amount,
    f.tip_amount,
    f.total_amount
FROM fact_taxi_trips f
JOIN dim_datetime pdt ON f.pickup_datetime_id = pdt.datetime_id
JOIN dim_datetime ddt ON f.dropoff_datetime_id = ddt.datetime_id
JOIN dim_location pl ON f.pickup_location_id = pl.location_id
JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
LIMIT 10;
```

## Temporal Analysis

### Trips by Hour of Day

```sql
-- Hourly trip patterns
SELECT 
    dt.hour,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(total_amount)::numeric, 2) AS avg_fare,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.hour
ORDER BY dt.hour;
```

### Weekday vs Weekend Comparison

```sql
-- Compare weekday and weekend patterns
SELECT 
    CASE 
        WHEN dt.is_weekend THEN 'Weekend'
        ELSE 'Weekday'
    END AS period,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(total_amount)::numeric, 2) AS avg_fare,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue,
    ROUND(AVG(tip_amount)::numeric, 2) AS avg_tip
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.is_weekend
ORDER BY period;
```

### Daily Trip Trends

```sql
-- Daily trip volume with 7-day moving average
SELECT 
    dt.date,
    dt.day_name,
    COUNT(*) AS trips_today,
    ROUND(AVG(COUNT(*)) OVER (
        ORDER BY dt.date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 0) AS trips_7day_avg,
    ROUND(SUM(total_amount)::numeric, 2) AS revenue_today
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.date, dt.day_name
ORDER BY dt.date;
```

### Rush Hour Analysis

```sql
-- Define rush hours: Morning (7-9 AM), Evening (5-7 PM)
SELECT 
    CASE 
        WHEN dt.hour BETWEEN 7 AND 9 THEN 'Morning Rush (7-9 AM)'
        WHEN dt.hour BETWEEN 17 AND 19 THEN 'Evening Rush (5-7 PM)'
        ELSE 'Off-Peak'
    END AS time_period,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY 
    CASE 
        WHEN dt.hour BETWEEN 7 AND 9 THEN 'Morning Rush (7-9 AM)'
        WHEN dt.hour BETWEEN 17 AND 19 THEN 'Evening Rush (5-7 PM)'
        ELSE 'Off-Peak'
    END
ORDER BY trip_count DESC;
```

## Geographic Analysis

### Top Pickup Locations

```sql
-- Most popular pickup zones
SELECT 
    l.zone_name,
    l.borough,
    l.service_zone,
    COUNT(*) AS pickup_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_trip_distance,
    ROUND(AVG(total_amount)::numeric, 2) AS avg_fare
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
GROUP BY l.zone_name, l.borough, l.service_zone
ORDER BY pickup_count DESC
LIMIT 20;
```

### Popular Routes

```sql
-- Most common pickup-dropoff route combinations
SELECT 
    pl.borough AS pickup_borough,
    pl.zone_name AS pickup_zone,
    dl.borough AS dropoff_borough,
    dl.zone_name AS dropoff_zone,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(total_amount)::numeric, 2) AS avg_fare
FROM fact_taxi_trips f
JOIN dim_location pl ON f.pickup_location_id = pl.location_id
JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
GROUP BY pl.borough, pl.zone_name, dl.borough, dl.zone_name
ORDER BY trip_count DESC
LIMIT 20;
```

### Borough-to-Borough Matrix

```sql
-- Trip counts between boroughs
SELECT 
    pl.borough AS from_borough,
    dl.borough AS to_borough,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue
FROM fact_taxi_trips f
JOIN dim_location pl ON f.pickup_location_id = pl.location_id
JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
WHERE pl.borough IS NOT NULL AND dl.borough IS NOT NULL
GROUP BY pl.borough, dl.borough
ORDER BY pl.borough, dl.borough;
```

### Airport Traffic Analysis

```sql
-- Trips to/from airports
SELECT 
    CASE 
        WHEN pl.service_zone = 'Airports' THEN 'From Airport'
        WHEN dl.service_zone = 'Airports' THEN 'To Airport'
        ELSE 'Non-Airport'
    END AS trip_type,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare,
    ROUND(AVG(tip_amount)::numeric, 2) AS avg_tip
FROM fact_taxi_trips f
JOIN dim_location pl ON f.pickup_location_id = pl.location_id
JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
GROUP BY 
    CASE 
        WHEN pl.service_zone = 'Airports' THEN 'From Airport'
        WHEN dl.service_zone = 'Airports' THEN 'To Airport'
        ELSE 'Non-Airport'
    END
ORDER BY trip_count DESC;
```

## Revenue Analysis

### Revenue by Payment Type

```sql
-- Breakdown of revenue by payment method
SELECT 
    pt.payment_type_description,
    COUNT(*) AS trip_count,
    ROUND(SUM(fare_amount)::numeric, 2) AS total_fare,
    ROUND(SUM(tip_amount)::numeric, 2) AS total_tips,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue,
    ROUND(AVG(tip_amount)::numeric, 2) AS avg_tip,
    ROUND((SUM(tip_amount) / NULLIF(SUM(fare_amount), 0) * 100)::numeric, 1) AS tip_percentage
FROM fact_taxi_trips f
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
GROUP BY pt.payment_type_description
ORDER BY total_revenue DESC;
```

### Tip Analysis

```sql
-- Tip patterns by various factors
SELECT 
    CASE 
        WHEN trip_distance < 1 THEN 'Short (< 1 mile)'
        WHEN trip_distance < 5 THEN 'Medium (1-5 miles)'
        WHEN trip_distance < 10 THEN 'Long (5-10 miles)'
        ELSE 'Very Long (> 10 miles)'
    END AS distance_category,
    pt.payment_type_description,
    COUNT(*) AS trip_count,
    ROUND(AVG(tip_amount)::numeric, 2) AS avg_tip,
    ROUND((AVG(tip_amount) / NULLIF(AVG(fare_amount), 0) * 100)::numeric, 1) AS avg_tip_pct
FROM fact_taxi_trips f
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
WHERE pt.payment_type_id = 1  -- Credit card only (tips recorded)
GROUP BY 
    CASE 
        WHEN trip_distance < 1 THEN 'Short (< 1 mile)'
        WHEN trip_distance < 5 THEN 'Medium (1-5 miles)'
        WHEN trip_distance < 10 THEN 'Long (5-10 miles)'
        ELSE 'Very Long (> 10 miles)'
    END,
    pt.payment_type_description
ORDER BY distance_category;
```

### Fare Distribution

```sql
-- Fare amount distribution in buckets
SELECT 
    CASE 
        WHEN fare_amount < 10 THEN '$0-10'
        WHEN fare_amount < 20 THEN '$10-20'
        WHEN fare_amount < 30 THEN '$20-30'
        WHEN fare_amount < 50 THEN '$30-50'
        ELSE '$50+'
    END AS fare_range,
    COUNT(*) AS trip_count,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER())::numeric, 2) AS percentage
FROM fact_taxi_trips
GROUP BY 
    CASE 
        WHEN fare_amount < 10 THEN '$0-10'
        WHEN fare_amount < 20 THEN '$10-20'
        WHEN fare_amount < 30 THEN '$20-30'
        WHEN fare_amount < 50 THEN '$30-50'
        ELSE '$50+'
    END
ORDER BY MIN(fare_amount);
```

## Customer Behavior

### Passenger Count Distribution

```sql
-- Distribution of passengers per trip
SELECT 
    passenger_count,
    COUNT(*) AS trip_count,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER())::numeric, 2) AS percentage,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(total_amount)::numeric, 2) AS avg_fare
FROM fact_taxi_trips
WHERE passenger_count > 0  -- Valid passenger counts
GROUP BY passenger_count
ORDER BY passenger_count;
```

### Trip Duration Analysis

```sql
-- Trip duration distribution
SELECT 
    CASE 
        WHEN trip_duration_minutes < 5 THEN '< 5 min'
        WHEN trip_duration_minutes < 15 THEN '5-15 min'
        WHEN trip_duration_minutes < 30 THEN '15-30 min'
        WHEN trip_duration_minutes < 60 THEN '30-60 min'
        ELSE '> 60 min'
    END AS duration_bucket,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare,
    ROUND(AVG(trip_distance / NULLIF(trip_duration_minutes, 0) * 60)::numeric, 1) AS avg_speed_mph
FROM fact_taxi_trips
GROUP BY 
    CASE 
        WHEN trip_duration_minutes < 5 THEN '< 5 min'
        WHEN trip_duration_minutes < 15 THEN '5-15 min'
        WHEN trip_duration_minutes < 30 THEN '15-30 min'
        WHEN trip_duration_minutes < 60 THEN '30-60 min'
        ELSE '> 60 min'
    END
ORDER BY MIN(trip_duration_minutes);
```

### Rate Code Usage

```sql
-- Analysis of different rate codes
SELECT 
    rc.rate_code_description,
    COUNT(*) AS trip_count,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER())::numeric, 2) AS percentage,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare,
    ROUND(SUM(total_amount)::numeric, 2) AS total_revenue
FROM fact_taxi_trips f
JOIN dim_rate_code rc ON f.rate_code_id = rc.rate_code_id
GROUP BY rc.rate_code_description
ORDER BY trip_count DESC;
```

## Performance Analysis

### Average Speed by Time of Day

```sql
-- Calculate average speed (mph) by hour
SELECT 
    dt.hour,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(trip_distance / NULLIF(trip_duration_minutes, 0) * 60)::numeric, 1) AS avg_speed_mph
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
WHERE trip_duration_minutes > 0
GROUP BY dt.hour
ORDER BY dt.hour;
```

### Efficiency Metrics by Borough

```sql
-- Efficiency metrics by pickup borough
SELECT 
    l.borough,
    COUNT(*) AS trip_count,
    ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(fare_amount)::numeric, 2) AS avg_fare,
    ROUND(AVG(fare_amount / NULLIF(trip_distance, 0))::numeric, 2) AS fare_per_mile,
    ROUND(AVG(fare_amount / NULLIF(trip_duration_minutes, 0) * 60)::numeric, 2) AS fare_per_hour
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
WHERE l.borough IS NOT NULL
GROUP BY l.borough
ORDER BY trip_count DESC;
```

## Advanced Analytics

### Cohort Analysis by Week

```sql
-- Weekly cohort analysis
WITH weekly_stats AS (
    SELECT 
        DATE_TRUNC('week', dt.date) AS week_start,
        COUNT(*) AS trip_count,
        ROUND(AVG(trip_distance)::numeric, 2) AS avg_distance,
        ROUND(SUM(total_amount)::numeric, 2) AS revenue,
        ROUND(AVG(total_amount)::numeric, 2) AS avg_fare
    FROM fact_taxi_trips f
    JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
    GROUP BY DATE_TRUNC('week', dt.date)
)
SELECT 
    week_start,
    trip_count,
    avg_distance,
    revenue,
    avg_fare,
    trip_count - LAG(trip_count) OVER (ORDER BY week_start) AS trip_count_change,
    ROUND(((trip_count::numeric / NULLIF(LAG(trip_count) OVER (ORDER BY week_start), 0) - 1) * 100)::numeric, 2) AS pct_change
FROM weekly_stats
ORDER BY week_start;
```

### Percentile Analysis

```sql
-- Fare distribution percentiles
SELECT 
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS p25_fare,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS median_fare,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS p75_fare,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS p90_fare,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS p95_fare,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY fare_amount)::numeric, 2) AS p99_fare
FROM fact_taxi_trips;
```

### Correlation Analysis

```sql
-- Correlation between distance and various factors
SELECT 
    ROUND(CORR(trip_distance, fare_amount)::numeric, 3) AS dist_fare_corr,
    ROUND(CORR(trip_distance, trip_duration_minutes)::numeric, 3) AS dist_duration_corr,
    ROUND(CORR(trip_distance, tip_amount)::numeric, 3) AS dist_tip_corr,
    ROUND(CORR(fare_amount, tip_amount)::numeric, 3) AS fare_tip_corr
FROM fact_taxi_trips
WHERE payment_type_id = 1;  -- Credit card only for tip correlation
```

### Time Series Decomposition

```sql
-- Daily trip counts with trend
WITH daily_trips AS (
    SELECT 
        dt.date,
        COUNT(*) AS trip_count,
        ROW_NUMBER() OVER (ORDER BY dt.date) AS day_num
    FROM fact_taxi_trips f
    JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
    GROUP BY dt.date
)
SELECT 
    date,
    trip_count,
    ROUND(AVG(trip_count) OVER (
        ORDER BY date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 0) AS moving_avg_7d,
    ROUND(AVG(trip_count) OVER (
        ORDER BY date 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ), 0) AS moving_avg_30d
FROM daily_trips
ORDER BY date;
```

## Using Materialized View

```sql
-- Query the pre-aggregated daily summary
SELECT 
    date,
    day_name,
    pickup_borough,
    trip_count,
    ROUND(avg_trip_distance::numeric, 2) AS avg_distance,
    ROUND(avg_fare::numeric, 2) AS avg_fare,
    ROUND(total_revenue::numeric, 2) AS total_revenue
FROM mv_daily_trip_summary
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC, total_revenue DESC;
```

## Performance Tips

### Using Indexes Effectively

```sql
-- Example of query that uses indexes efficiently
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
WHERE dt.year = 2023 
  AND dt.month = 1
  AND f.pickup_location_id = 161;

-- Index scan on (year, month) and pickup_location_id
```

### Partition Pruning

```sql
-- Query with partition pruning (much faster)
SELECT COUNT(*), AVG(fare_amount)
FROM fact_taxi_trips
WHERE year = 2023 AND month = 1;  -- Uses partition pruning

-- vs. without partition pruning (slower)
SELECT COUNT(*), AVG(fare_amount)
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
WHERE dt.date = '2023-01-01';  -- Scans all partitions
```

## Export Results

### Export to CSV

```sql
-- Run from psql command line
\copy (SELECT * FROM fact_taxi_trips WHERE year = 2023 AND month = 1 LIMIT 10000) TO '/tmp/trips_jan_2023.csv' CSV HEADER;
```

### Create Summary Report

```sql
-- Comprehensive monthly report
SELECT 
    dt.year,
    dt.month_name,
    COUNT(*) AS total_trips,
    COUNT(DISTINCT f.pickup_location_id) AS unique_pickup_zones,
    ROUND(AVG(f.trip_distance)::numeric, 2) AS avg_distance,
    ROUND(AVG(f.trip_duration_minutes)::numeric, 1) AS avg_duration,
    ROUND(AVG(f.fare_amount)::numeric, 2) AS avg_fare,
    ROUND(SUM(f.total_amount)::numeric, 2) AS total_revenue,
    ROUND(AVG(CASE WHEN pt.payment_type_id = 1 THEN f.tip_amount END)::numeric, 2) AS avg_tip_credit_card
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
GROUP BY dt.year, dt.month, dt.month_name
ORDER BY dt.year, dt.month;
```

---

## Tips for Writing Efficient Queries

1. **Always use partition columns** (year, month) in WHERE clauses
2. **Join on indexed columns** (foreign keys)
3. **Use EXPLAIN ANALYZE** to check query plans
4. **Aggregate before joining** when possible
5. **Use materialized views** for frequently accessed aggregations
6. **Limit result sets** when exploring data
7. **Use appropriate data types** in calculations

## Additional Resources

- PostgreSQL Performance Tips: https://www.postgresql.org/docs/current/performance-tips.html
- Dimensional Modeling Best Practices: See docs/data_model.md
- Query Optimization Guide: See docs/architecture.md