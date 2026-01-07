-- NYC Taxi Dimensional Model Schema - UPDATED FOR ACTUAL DATA
-- Star schema optimized for analytical queries

-- Drop tables if they exist (for idempotency)
DROP TABLE IF EXISTS fact_taxi_trips CASCADE;

DROP TABLE IF EXISTS dim_datetime CASCADE;

DROP TABLE IF EXISTS dim_location CASCADE;

DROP TABLE IF EXISTS dim_rate_code CASCADE;

DROP TABLE IF EXISTS dim_payment_type CASCADE;

-- Dimension: DateTime
-- Contains all unique timestamps with calendar attributes
CREATE TABLE dim_datetime (
    datetime_id BIGINT PRIMARY KEY,
    datetime_value TIMESTAMP NOT NULL,
    date DATE NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE INDEX idx_dim_datetime_date ON dim_datetime (date);

CREATE INDEX idx_dim_datetime_year_month ON dim_datetime (year, month);

CREATE INDEX idx_dim_datetime_hour ON dim_datetime (hour);

CREATE INDEX idx_dim_datetime_is_weekend ON dim_datetime (is_weekend);

-- Dimension: Location
-- Taxi zones with borough and service zone information
CREATE TABLE dim_location (
    location_id INTEGER PRIMARY KEY,
    zone_name VARCHAR(100) NOT NULL,
    borough VARCHAR(50),
    service_zone VARCHAR(50)
);

CREATE INDEX idx_dim_location_borough ON dim_location (borough);

CREATE INDEX idx_dim_location_service_zone ON dim_location (service_zone);

-- Dimension: Rate Code
-- Rate code descriptions
CREATE TABLE dim_rate_code (
    rate_code_id BIGINT PRIMARY KEY,
    rate_code_description VARCHAR(100) NOT NULL
);

-- Dimension: Payment Type
-- Payment method descriptions
CREATE TABLE dim_payment_type (
    payment_type_id BIGINT PRIMARY KEY,
    payment_type_description VARCHAR(50) NOT NULL
);

-- Fact Table: Taxi Trips
-- One row per trip with measures and foreign keys to dimensions
CREATE TABLE fact_taxi_trips ( trip_id BIGINT PRIMARY KEY,

-- Foreign keys to dimensions
pickup_datetime_id BIGINT REFERENCES dim_datetime (datetime_id),
dropoff_datetime_id BIGINT REFERENCES dim_datetime (datetime_id),
pickup_location_id INTEGER REFERENCES dim_location (location_id),
dropoff_location_id INTEGER REFERENCES dim_location (location_id),
rate_code_id BIGINT REFERENCES dim_rate_code (rate_code_id),
payment_type_id BIGINT REFERENCES dim_payment_type (payment_type_id),

-- Degenerate dimensions (low cardinality attributes)
vendor_id INTEGER, store_and_fwd_flag VARCHAR(1),

-- Measures (facts) - UPDATED to match actual data types
passenger_count BIGINT, -- Changed from DOUBLE to BIGINT
trip_distance DOUBLE PRECISION,
fare_amount DOUBLE PRECISION,
extra DOUBLE PRECISION,
mta_tax DOUBLE PRECISION,
tip_amount DOUBLE PRECISION,
tolls_amount DOUBLE PRECISION,
improvement_surcharge DOUBLE PRECISION,
total_amount DOUBLE PRECISION,
congestion_surcharge DOUBLE PRECISION,
airport_fee DOUBLE PRECISION,
cbd_congestion_fee DOUBLE PRECISION, -- NEW field added
trip_duration_minutes DOUBLE PRECISION,

-- Partition columns for data management
year INTEGER NOT NULL, month INTEGER NOT NULL );

-- Indexes on fact table for common query patterns
CREATE INDEX idx_fact_pickup_datetime ON fact_taxi_trips (pickup_datetime_id);

CREATE INDEX idx_fact_dropoff_datetime ON fact_taxi_trips (dropoff_datetime_id);

CREATE INDEX idx_fact_pickup_location ON fact_taxi_trips (pickup_location_id);

CREATE INDEX idx_fact_dropoff_location ON fact_taxi_trips (dropoff_location_id);

CREATE INDEX idx_fact_year_month ON fact_taxi_trips (year, month);

CREATE INDEX idx_fact_payment_type ON fact_taxi_trips (payment_type_id);

CREATE INDEX idx_fact_rate_code ON fact_taxi_trips (rate_code_id);

-- Create materialized view for common aggregations
CREATE MATERIALIZED VIEW mv_daily_trip_summary AS
SELECT
    dt.date,
    dt.day_name,
    dt.is_weekend,
    loc.borough AS pickup_borough,
    COUNT(*) AS trip_count,
    SUM(f.passenger_count) AS total_passengers,
    AVG(f.trip_distance) AS avg_trip_distance,
    AVG(f.trip_duration_minutes) AS avg_trip_duration,
    SUM(f.fare_amount) AS total_fare,
    AVG(f.fare_amount) AS avg_fare,
    SUM(f.tip_amount) AS total_tips,
    AVG(f.tip_amount) AS avg_tip,
    SUM(f.total_amount) AS total_revenue
FROM
    fact_taxi_trips f
    JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
    JOIN dim_location loc ON f.pickup_location_id = loc.location_id
GROUP BY
    dt.date,
    dt.day_name,
    dt.is_weekend,
    loc.borough;

CREATE INDEX idx_mv_daily_summary_date ON mv_daily_trip_summary (date);

CREATE INDEX idx_mv_daily_summary_borough ON mv_daily_trip_summary (pickup_borough);

-- Sample analytical queries (documented for users)
COMMENT ON
TABLE fact_taxi_trips IS 'Fact table containing one row per taxi trip with measures and foreign keys to dimensions';

COMMENT ON
TABLE dim_datetime IS 'Dimension table with calendar attributes for temporal analysis';

COMMENT ON
TABLE dim_location IS 'Dimension table with taxi zone information including borough and service zone';

COMMENT ON
TABLE dim_rate_code IS 'Dimension table with rate code descriptions';

COMMENT ON
TABLE dim_payment_type IS 'Dimension table with payment method descriptions';

COMMENT ON COLUMN fact_taxi_trips.passenger_count IS 'Number of passengers (BIGINT to match source data)';

COMMENT ON COLUMN fact_taxi_trips.rate_code_id IS 'Rate code ID (BIGINT to match source data)';

COMMENT ON COLUMN fact_taxi_trips.payment_type_id IS 'Payment type ID (BIGINT to match source data)';

COMMENT ON COLUMN fact_taxi_trips.cbd_congestion_fee IS 'CBD congestion fee (new field in 2024+ data)';

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO taxi_user;

GRANT ALL ON ALL TABLES IN SCHEMA public TO taxi_user;