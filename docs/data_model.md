# NYC Taxi Pipeline - Data Model Documentation

## Dimensional Model Overview

This pipeline implements a **star schema** dimensional model optimized for analytical queries on NYC Taxi trip data.

## Schema Diagram

```
                    ┌─────────────────────┐
                    │   dim_datetime      │
                    ├─────────────────────┤
                    │ datetime_id (PK)    │
                    │ datetime_value      │
                    │ date                │
                    │ year                │
                    │ month               │
                    │ day                 │
                    │ hour                │
                    │ minute              │
                    │ day_of_week         │
                    │ day_name            │
                    │ month_name          │
                    │ quarter             │
                    │ is_weekend          │
                    └──────────┬──────────┘
                               │
                               │ (1:M)
                               │
┌─────────────────────┐        │        ┌─────────────────────┐
│   dim_location      │        │        │  dim_rate_code      │
├─────────────────────┤        │        ├─────────────────────┤
│ location_id (PK)    │        │        │ rate_code_id (PK)   │
│ zone_name           │        │        │ rate_code_desc      │
│ borough             │        │        └──────────┬──────────┘
│ service_zone        │        │                   │
└──────────┬──────────┘        │                   │ (1:M)
           │                   │                   │
           │ (1:M)             │                   │
           │                   ▼                   │
           │          ┌─────────────────────┐      │
           └─────────▶│  fact_taxi_trips    │◀─────┘
                      ├─────────────────────┤
                      │ trip_id (PK)        │
                      │ pickup_datetime_id  │─────┐
                      │ dropoff_datetime_id │     │ (M:1)
                      │ pickup_location_id  │     │
                      │ dropoff_location_id │     └────────┐
                      │ rate_code_id        │              │
                      │ payment_type_id     │              ▼
                      │ vendor_id           │    ┌─────────────────────┐
                      │ store_and_fwd_flag  │    │   dim_datetime      │
                      │ passenger_count     │    │  (same as above)    │
                      │ trip_distance       │    └─────────────────────┘
                      │ fare_amount         │
                      │ extra               │
                      │ mta_tax             │
                      │ tip_amount          │
                      │ tolls_amount        │
                      │ improvement_surcharge│
                      │ total_amount        │
                      │ congestion_surcharge│
                      │ airport_fee         │
                      │ trip_duration_min   │
                      │ year                │
                      │ month               │
                      └──────────┬──────────┘
                                 │
                                 │ (M:1)
                                 ▼
                      ┌─────────────────────┐
                      │ dim_payment_type    │
                      ├─────────────────────┤
                      │ payment_type_id(PK) │
                      │ payment_type_desc   │
                      └─────────────────────┘
```

## Table Definitions

### Fact Table: fact_taxi_trips

**Purpose**: Core transactional table storing one row per taxi trip

**Grain**: One row per completed taxi trip

**Size**: ~3M rows per month (~36M rows per year)

**Partitioning**: Partitioned by year and month for query performance

| Column Name | Data Type | Description | Null? | Notes |
|-------------|-----------|-------------|-------|-------|
| trip_id | BIGINT | Surrogate key | NOT NULL | Generated via monotonically_increasing_id() |
| pickup_datetime_id | BIGINT | Foreign key to dim_datetime | NOT NULL | Links to pickup timestamp |
| dropoff_datetime_id | BIGINT | Foreign key to dim_datetime | NOT NULL | Links to dropoff timestamp |
| pickup_location_id | INTEGER | Foreign key to dim_location | NOT NULL | Pickup taxi zone |
| dropoff_location_id | INTEGER | Foreign key to dim_location | NOT NULL | Dropoff taxi zone |
| rate_code_id | INTEGER | Foreign key to dim_rate_code | NULL | Rate type used |
| payment_type_id | INTEGER | Foreign key to dim_payment_type | NULL | Payment method |
| vendor_id | INTEGER | Degenerate dimension | NULL | Taxi vendor (1=Creative Mobile, 2=VeriFone) |
| store_and_fwd_flag | VARCHAR(1) | Degenerate dimension | NULL | Y=stored before sending, N=not stored |
| passenger_count | DOUBLE | Measure | NULL | Number of passengers |
| trip_distance | DOUBLE | Measure | NULL | Trip distance in miles |
| fare_amount | DOUBLE | Measure | NULL | Base time-and-distance fare |
| extra | DOUBLE | Measure | NULL | Miscellaneous extras and surcharges |
| mta_tax | DOUBLE | Measure | NULL | MTA tax (automatically triggered) |
| tip_amount | DOUBLE | Measure | NULL | Tip amount (credit card only) |
| tolls_amount | DOUBLE | Measure | NULL | Total tolls paid |
| improvement_surcharge | DOUBLE | Measure | NULL | Improvement surcharge |
| total_amount | DOUBLE | Measure | NULL | Total amount charged to passengers |
| congestion_surcharge | DOUBLE | Measure | NULL | Congestion surcharge |
| airport_fee | DOUBLE | Measure | NULL | Airport fee ($1.25 for trips to/from airports) |
| trip_duration_minutes | DOUBLE | Calculated measure | NULL | Derived: (dropoff_time - pickup_time) / 60 |
| year | INTEGER | Partition column | NOT NULL | For partition pruning |
| month | INTEGER | Partition column | NOT NULL | For partition pruning |

**Indexes**:
- Primary key on trip_id
- Index on pickup_datetime_id
- Index on dropoff_datetime_id
- Index on pickup_location_id
- Index on dropoff_location_id
- Index on payment_type_id
- Index on rate_code_id
- Composite index on (year, month)

### Dimension Table: dim_datetime

**Purpose**: Provides calendar attributes for temporal analysis

**Type**: Conformed dimension (shared across multiple fact tables if extended)

**SCD Type**: Type 1 (no history tracking needed for time)

**Size**: ~200K unique datetime values per month

| Column Name | Data Type | Description | Example |
|-------------|-----------|-------------|---------|
| datetime_id | BIGINT | Surrogate key | 20230115143000 |
| datetime_value | TIMESTAMP | Actual timestamp | 2023-01-15 14:30:00 |
| date | DATE | Date portion | 2023-01-15 |
| year | INTEGER | Year | 2023 |
| month | INTEGER | Month (1-12) | 1 |
| day | INTEGER | Day of month (1-31) | 15 |
| hour | INTEGER | Hour (0-23) | 14 |
| minute | INTEGER | Minute (0-59) | 30 |
| day_of_week | INTEGER | Day of week (1=Sun, 7=Sat) | 1 |
| day_name | VARCHAR(20) | Day name | Sunday |
| month_name | VARCHAR(20) | Month name | January |
| quarter | INTEGER | Quarter (1-4) | 1 |
| is_weekend | BOOLEAN | Weekend flag | TRUE |

**Indexes**:
- Primary key on datetime_id
- Index on date
- Index on (year, month)
- Index on hour
- Index on is_weekend

**Key Decisions**:
- datetime_id is generated as YYYYMMDDHHmmss for readability
- Denormalized calendar attributes for query performance
- Includes both pickup and dropoff datetimes (union of both)

### Dimension Table: dim_location

**Purpose**: Geographic information about pickup and dropoff zones

**Type**: Conformed dimension

**SCD Type**: Type 1 (overwrite changes - zones rarely change)

**Size**: 265 taxi zones

| Column Name | Data Type | Description | Example |
|-------------|-----------|-------------|---------|
| location_id | INTEGER | Natural key from source | 100 |
| zone_name | VARCHAR(100) | Zone name | Times Sq/Theatre District |
| borough | VARCHAR(50) | NYC borough | Manhattan |
| service_zone | VARCHAR(50) | Service zone type | Yellow Zone |

**Indexes**:
- Primary key on location_id
- Index on borough
- Index on service_zone

**Key Decisions**:
- Uses natural key (LocationID) from source data
- Denormalized (no separate borough dimension)
- Small size allows full table scans without performance impact

### Dimension Table: dim_rate_code

**Purpose**: Describes the rate code used for the trip

**Type**: Static reference dimension

**SCD Type**: Type 1

**Size**: 6 rate codes (static)

| rate_code_id | rate_code_description |
|--------------|----------------------|
| 1 | Standard rate |
| 2 | JFK |
| 3 | Newark |
| 4 | Nassau or Westchester |
| 5 | Negotiated fare |
| 6 | Group ride |

**Key Decisions**:
- Small, static dimension (loaded from hardcoded values)
- No indexes needed beyond primary key (tiny table)

### Dimension Table: dim_payment_type

**Purpose**: Describes the payment method used

**Type**: Static reference dimension

**SCD Type**: Type 1

**Size**: 6 payment types (static)

| payment_type_id | payment_type_description |
|-----------------|-------------------------|
| 1 | Credit card |
| 2 | Cash |
| 3 | No charge |
| 4 | Dispute |
| 5 | Unknown |
| 6 | Voided trip |

**Key Decisions**:
- Small, static dimension (loaded from hardcoded values)
- Important for tip analysis (tips only recorded for credit cards)

## Modeling Decisions

### Why Star Schema?

1. **Query Performance**: Denormalized structure = fewer joins
2. **Simplicity**: Easy to understand for analysts and BI tools
3. **Flexibility**: Easy to add new dimensions without breaking existing queries
4. **Scalability**: Proven pattern for large fact tables

### Why These Dimensions?

**dim_datetime**: 
- Enables temporal analysis (hourly patterns, weekday vs weekend, seasonal trends)
- Calendar attributes pre-calculated for performance
- Supports both pickup and dropoff analysis

**dim_location**:
- Geographic analysis (borough performance, popular routes)
- Integrated with official NYC taxi zone data
- Supports pickup and dropoff analysis

**dim_rate_code & dim_payment_type**:
- Small reference tables
- Provide business context for trip pricing and payment
- Enable filtering and grouping by these attributes

### Degenerate Dimensions

**vendor_id** and **store_and_fwd_flag** are kept in the fact table (degenerate dimensions) because:
- Low cardinality (vendor_id has only 2 values)
- Rarely used for analysis
- Creating separate dimensions would add unnecessary complexity

### Grain Selection

**Fact Table Grain**: One row per completed trip

This grain was chosen because:
- Matches the natural grain of source data
- Supports all common analyses (trip counts, revenue, averages)
- Enables drill-down to individual trip details if needed

Alternative grains considered but rejected:
- **Aggregated (daily/hourly)**: Would lose analytical flexibility
- **Split pickup/dropoff**: Would double row count unnecessarily

### Partitioning Strategy

**Fact Table**: Partitioned by year and month

Benefits:
- **Query Performance**: Partition pruning for date-filtered queries
- **Data Management**: Easy to drop old partitions
- **Maintenance**: Vacuum/analyze can target specific partitions
- **Backfills**: Safe to overwrite specific month without affecting others

**Dimensions**: Not partitioned (small size, frequently joined)

### Slowly Changing Dimensions (SCD)

**Current Implementation**: Type 1 (overwrite)

For this dataset, Type 1 is appropriate because:
- Dimensions rarely change (especially zones)
- Historical accuracy less critical than simplicity
- No business requirement to track dimension changes

**Future Consideration**: Could implement Type 2 for dim_location if:
- Zone boundaries change and historical accuracy matters
- Need to analyze trips with correct historical zone definitions

## Data Quality Rules

### Fact Table Filters

During transformation, records are filtered out if they violate:

1. **Null Checks**: Critical fields cannot be null
   - pickup_datetime, dropoff_datetime
   - pickup_location_id, dropoff_location_id

2. **Temporal Logic**: 
   - dropoff_datetime > pickup_datetime
   - trip_duration > 0 and <= 300 minutes (5 hours max)

3. **Fare Validation**:
   - fare_amount >= 0 and <= $500
   - total_amount reasonableness

4. **Distance Validation**:
   - trip_distance > 0 and <= 100 miles

5. **Passenger Validation**:
   - passenger_count >= 1 and <= 6

6. **Location Validation**:
   - pickup_location_id != dropoff_location_id (no same-location trips)

### Data Quality Impact

Based on January 2023 data:
- **Raw Records**: 3,066,766
- **Filtered Out**: ~102,142 (3.3%)
- **Clean Records**: 2,964,624 (96.7%)

Common reasons for filtering:
- Null critical fields (1.5%)
- Invalid fares/distances (1.2%)
- Same pickup/dropoff (0.4%)
- Other violations (0.2%)

## Query Patterns & Optimization

### Typical Analytical Queries

**1. Temporal Analysis**
```sql
-- Busiest hours
SELECT dt.hour, COUNT(*) as trips
FROM fact_taxi_trips f
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.hour;
```
- Optimized by: Index on pickup_datetime_id, index on hour

**2. Geographic Analysis**
```sql
-- Revenue by borough
SELECT l.borough, SUM(f.total_amount) as revenue
FROM fact_taxi_trips f
JOIN dim_location l ON f.pickup_location_id = l.location_id
GROUP BY l.borough;
```
- Optimized by: Index on pickup_location_id, index on borough

**3. Payment Analysis**
```sql
-- Average tip by payment type
SELECT pt.payment_type_description, AVG(f.tip_amount)
FROM fact_taxi_trips f
JOIN dim_payment_type pt ON f.payment_type_id = pt.payment_type_id
GROUP BY pt.payment_type_description;
```
- Optimized by: Index on payment_type_id

**4. Route Analysis**
```sql
-- Popular routes
SELECT 
    pl.zone_name as pickup,
    dl.zone_name as dropoff,
    COUNT(*) as trips
FROM fact_taxi_trips f
JOIN dim_location pl ON f.pickup_location_id = pl.location_id
JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
GROUP BY pl.zone_name, dl.zone_name
ORDER BY trips DESC
LIMIT 10;
```
- Optimized by: Indexes on pickup_location_id and dropoff_location_id

### Materialized View

**mv_daily_trip_summary**: Pre-aggregated daily statistics

Purpose: Accelerate common dashboard queries

Refresh strategy: After each data load

## Extensibility

### Adding New Dimensions

To add a new dimension (e.g., dim_weather):

1. Create dimension table in Silver layer
2. Add foreign key column to fact table
3. Update dimensional_transform.py to create dimension
4. Update db_loader.py to load new dimension
5. Add indexes and update documentation

### Adding New Measures

To add calculated measures (e.g., average_speed):

1. Add calculation in dimensional_transform.py
2. Add column to fact table schema
3. Update documentation

Example:
```python
.withColumn("avg_speed_mph", 
    F.col("trip_distance") / (F.col("trip_duration_minutes") / 60))
```

## Data Model Evolution

### Version History

**v1.0 (Current)**:
- Initial star schema implementation
- 5 tables (1 fact, 4 dimensions)
- Year/month partitioning

**Future Versions**:
- v1.1: Add dim_weather (if weather data available)
- v1.2: Implement Type 2 SCD for dim_location
- v2.0: Add aggregate fact tables for performance
- v3.0: Add real-time streaming fact table

### Migration Strategy

When schema changes are needed:

1. Version control all schema changes
2. Use Alembic or Liquibase for migrations
3. Maintain backward compatibility where possible
4. Test migrations on dev environment first
5. Document breaking changes clearly

## Storage Estimates

### Per Month (January 2023 as baseline)

| Table | Rows | Size (PostgreSQL) | Size (Parquet) |
|-------|------|-------------------|----------------|
| fact_taxi_trips | 2.9M | ~750 MB | ~400 MB |
| dim_datetime | 200K | ~50 MB | ~20 MB |
| dim_location | 265 | <1 MB | <1 MB |
| dim_rate_code | 6 | <1 MB | <1 MB |
| dim_payment_type | 6 | <1 MB | <1 MB |
| **Total** | ~3.1M | **~800 MB** | **~420 MB** |

### Per Year Projection

- **Fact Records**: ~35M rows
- **PostgreSQL Size**: ~9.5 GB
- **Parquet Size**: ~5 GB
- **With Indexes**: ~12 GB total

## Performance Benchmarks

Based on January 2023 data (2.9M trips):

| Operation | Time | Notes |
|-----------|------|-------|
| Full table scan | ~5 sec | Sequential scan of fact table |
| Filtered query (1 day) | ~0.5 sec | With partition pruning |
| Join to 2 dimensions | ~1.5 sec | Using indexes |
| Aggregation (grouping) | ~2-3 sec | Depends on cardinality |
| Materialized view refresh | ~8 sec | Daily summary calculation |

Hardware: Local Docker (2 CPU cores, 4GB RAM)

Cloud performance would be significantly faster with proper sizing.