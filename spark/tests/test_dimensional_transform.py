"""
Unit tests for dimensional transformation job.
"""

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, DoubleType, TimestampType, StringType
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jobs.dimensional_transform import DimensionalTransform
from common.config import PipelineConfig


@pytest.fixture(scope="session")
def spark():
    """Create a Spark session for testing."""
    spark = SparkSession.builder \
        .appName("TestDimensionalTransform") \
        .master("local[2]") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("ERROR")
    yield spark
    spark.stop()


@pytest.fixture
def config():
    """Create test configuration."""
    os.environ["STORAGE_TYPE"] = "local"
    return PipelineConfig()


@pytest.fixture
def dimensional_transform(config, spark):
    """Create DimensionalTransform instance."""
    return DimensionalTransform(config, spark)


@pytest.fixture
def sample_trips_df(spark):
    """Create sample trips DataFrame for testing with all required columns."""
    data = [
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),
        (2, datetime(2023, 1, 1, 11, 0), datetime(2023, 1, 1, 11, 45), 3, 5.2, 1, 'N', 150, 250, 2, 22.0, 1.0, 0.5, 0.0, 0.0, 0.3, 23.8, 0.0, 0.0, 0.0, 2023, 1),
    ]
    
    schema = StructType([
        StructField("VendorID", IntegerType()),
        StructField("tpep_pickup_datetime", TimestampType()),
        StructField("tpep_dropoff_datetime", TimestampType()),
        StructField("passenger_count", IntegerType()),
        StructField("trip_distance", DoubleType()),
        StructField("RatecodeID", IntegerType()),
        StructField("store_and_fwd_flag", StringType()),
        StructField("PULocationID", IntegerType()),
        StructField("DOLocationID", IntegerType()),
        StructField("payment_type", IntegerType()),
        StructField("fare_amount", DoubleType()),
        StructField("extra", DoubleType()),
        StructField("mta_tax", DoubleType()),
        StructField("tip_amount", DoubleType()),
        StructField("tolls_amount", DoubleType()),
        StructField("improvement_surcharge", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("congestion_surcharge", DoubleType()),
        StructField("Airport_fee", DoubleType()),  # Capital A to match source
        StructField("cbd_congestion_fee", DoubleType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
    ])
    
    return spark.createDataFrame(data, schema)


@pytest.fixture
def sample_zones_df(spark):
    """Create sample zone lookup DataFrame with actual CSV column names."""
    data = [
        (100, "Manhattan", "Central Park", "Yellow Zone"),
        (200, "Brooklyn", "Williamsburg", "Boro Zone"),
        (150, "Queens", "JFK Airport", "Airports"),
        (250, "Bronx", "Yankee Stadium", "Boro Zone"),
    ]
    
    schema = StructType([
        StructField("LocationID", IntegerType()),
        StructField("Borough", StringType()),
        StructField("Zone", StringType()),
        StructField("service_zone", StringType()),
    ])
    
    return spark.createDataFrame(data, schema)


def test_clean_trips_removes_invalid_records(dimensional_transform, sample_trips_df, spark):
    """Test that data cleaning filters out invalid records."""
    # Add invalid records
    invalid_data = [
        # Negative fare
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, -15.0, 0.5, 0.5, 3.0, 0.0, 0.3, -11.0, 0.0, 0.0, 0.0, 2023, 1),
        # Zero distance
        (2, datetime(2023, 1, 1, 11, 0), datetime(2023, 1, 1, 11, 45), 3, 0.0, 1, 'N', 150, 250, 2, 22.0, 1.0, 0.5, 0.0, 0.0, 0.3, 23.8, 0.0, 0.0, 0.0, 2023, 1),
        # Same pickup/dropoff
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 100, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),
    ]
    
    invalid_df = spark.createDataFrame(invalid_data, sample_trips_df.schema)
    combined_df = sample_trips_df.union(invalid_df)
    
    initial_count = combined_df.count()
    cleaned_df = dimensional_transform.clean_trips(combined_df)
    final_count = cleaned_df.count()
    
    # Should filter out 3 invalid records
    assert final_count < initial_count
    assert final_count == 2  # Only valid records remain
    
    # Verify all cleaned records have positive fares
    fares = cleaned_df.select("fare_amount").collect()
    for row in fares:
        assert row.fare_amount > 0


def test_clean_trips_adds_duration(dimensional_transform, sample_trips_df):
    """Test that trip duration is calculated during cleaning."""
    cleaned_df = dimensional_transform.clean_trips(sample_trips_df)
    
    # Check that trip_duration_minutes column was added
    assert "trip_duration_minutes" in cleaned_df.columns
    
    # Verify durations are positive
    durations = cleaned_df.select("trip_duration_minutes").collect()
    for row in durations:
        assert row.trip_duration_minutes > 0


def test_clean_trips_filters_extreme_values(dimensional_transform, sample_trips_df, spark):
    """Test that extreme values are filtered out."""
    extreme_data = [
        # Extremely high fare (>$500)
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 600.0, 0.5, 0.5, 3.0, 0.0, 0.3, 604.3, 0.0, 0.0, 0.0, 2023, 1),
        # Extremely long trip (>100 miles)
        (2, datetime(2023, 1, 1, 11, 0), datetime(2023, 1, 1, 11, 45), 3, 150.0, 1, 'N', 150, 250, 2, 22.0, 1.0, 0.5, 0.0, 0.0, 0.3, 23.8, 0.0, 0.0, 0.0, 2023, 1),
        # Too many passengers (>6)
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 8, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),
    ]
    
    extreme_df = spark.createDataFrame(extreme_data, sample_trips_df.schema)
    combined_df = sample_trips_df.union(extreme_df)
    
    cleaned_df = dimensional_transform.clean_trips(combined_df)
    
    # All extreme records should be filtered
    assert cleaned_df.count() == 2
    
    # Verify fare amounts are within limits
    max_fare = cleaned_df.agg({"fare_amount": "max"}).collect()[0][0]
    assert max_fare <= 500


def test_clean_trips_filters_null_values(dimensional_transform, spark):
    """Test that null critical values are filtered out."""
    null_data = [
        # Null pickup time
        (1, None, datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),
        # Null dropoff time
        (2, datetime(2023, 1, 1, 11, 0), None, 3, 5.2, 1, 'N', 150, 250, 2, 22.0, 1.0, 0.5, 0.0, 0.0, 0.3, 23.8, 0.0, 0.0, 0.0, 2023, 1),
        # Null location IDs
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', None, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),
    ]
    
    schema = StructType([
        StructField("VendorID", IntegerType()),
        StructField("tpep_pickup_datetime", TimestampType()),
        StructField("tpep_dropoff_datetime", TimestampType()),
        StructField("passenger_count", IntegerType()),
        StructField("trip_distance", DoubleType()),
        StructField("RatecodeID", IntegerType()),
        StructField("store_and_fwd_flag", StringType()),
        StructField("PULocationID", IntegerType()),
        StructField("DOLocationID", IntegerType()),
        StructField("payment_type", IntegerType()),
        StructField("fare_amount", DoubleType()),
        StructField("extra", DoubleType()),
        StructField("mta_tax", DoubleType()),
        StructField("tip_amount", DoubleType()),
        StructField("tolls_amount", DoubleType()),
        StructField("improvement_surcharge", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("congestion_surcharge", DoubleType()),
        StructField("Airport_fee", DoubleType()),
        StructField("cbd_congestion_fee", DoubleType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
    ])
    
    null_df = spark.createDataFrame(null_data, schema)
    cleaned_df = dimensional_transform.clean_trips(null_df)
    
    # All records with null critical fields should be filtered
    assert cleaned_df.count() == 0


def test_create_dim_datetime(dimensional_transform, sample_trips_df):
    """Test datetime dimension creation."""
    dim_datetime = dimensional_transform.create_dim_datetime(sample_trips_df)
    
    # Should have records for both pickup and dropoff times
    assert dim_datetime.count() >= 2
    
    # Check required columns exist
    required_cols = ['datetime_id', 'datetime_value', 'date', 'year', 'month', 
                     'day', 'hour', 'minute', 'day_of_week', 'day_name', 
                     'month_name', 'quarter', 'is_weekend']
    for col in required_cols:
        assert col in dim_datetime.columns
    
    # Verify datetime attributes are correct
    row = dim_datetime.filter(dim_datetime.hour == 10).first()
    assert row.year == 2023
    assert row.month == 1
    assert row.day == 1
    assert row.day_of_week is not None


def test_create_dim_datetime_weekend_flag(dimensional_transform, spark):
    """Test that weekend flag is correctly set."""
    # Create data with weekend dates
    data = [
        (1, datetime(2023, 1, 7, 10, 0), datetime(2023, 1, 7, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),  # Saturday
        (2, datetime(2023, 1, 8, 11, 0), datetime(2023, 1, 8, 11, 45), 3, 5.2, 1, 'N', 150, 250, 2, 22.0, 1.0, 0.5, 0.0, 0.0, 0.3, 23.8, 0.0, 0.0, 0.0, 2023, 1),  # Sunday
        (1, datetime(2023, 1, 9, 10, 0), datetime(2023, 1, 9, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0, 2023, 1),  # Monday
    ]
    
    schema = StructType([
        StructField("VendorID", IntegerType()),
        StructField("tpep_pickup_datetime", TimestampType()),
        StructField("tpep_dropoff_datetime", TimestampType()),
        StructField("passenger_count", IntegerType()),
        StructField("trip_distance", DoubleType()),
        StructField("RatecodeID", IntegerType()),
        StructField("store_and_fwd_flag", StringType()),
        StructField("PULocationID", IntegerType()),
        StructField("DOLocationID", IntegerType()),
        StructField("payment_type", IntegerType()),
        StructField("fare_amount", DoubleType()),
        StructField("extra", DoubleType()),
        StructField("mta_tax", DoubleType()),
        StructField("tip_amount", DoubleType()),
        StructField("tolls_amount", DoubleType()),
        StructField("improvement_surcharge", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("congestion_surcharge", DoubleType()),
        StructField("Airport_fee", DoubleType()),
        StructField("cbd_congestion_fee", DoubleType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
    ])
    
    df = spark.createDataFrame(data, schema)
    dim_datetime = dimensional_transform.create_dim_datetime(df)
    
    # Check weekend flags
    weekend_count = dim_datetime.filter(dim_datetime.is_weekend == True).count()
    weekday_count = dim_datetime.filter(dim_datetime.is_weekend == False).count()
    
    assert weekend_count > 0
    assert weekday_count > 0


def test_create_dim_location(dimensional_transform, sample_zones_df):
    """Test location dimension creation with actual CSV column names."""
    dim_location = dimensional_transform.create_dim_location(sample_zones_df)
    
    assert dim_location.count() == 4
    
    # Check required columns after transformation
    required_cols = ['location_id', 'zone_name', 'borough', 'service_zone']
    for col in required_cols:
        assert col in dim_location.columns
    
    # Verify data integrity
    manhattan_zone = dim_location.filter(dim_location.borough == "Manhattan").first()
    assert manhattan_zone.location_id == 100
    assert manhattan_zone.zone_name == "Central Park"
    assert manhattan_zone.service_zone == "Yellow Zone"


def test_create_dim_location_handles_duplicates(dimensional_transform, spark):
    """Test that location dimension removes duplicates."""
    duplicate_data = [
        (100, "Manhattan", "Central Park", "Yellow Zone"),
        (100, "Manhattan", "Central Park", "Yellow Zone"),  # Duplicate
        (200, "Brooklyn", "Williamsburg", "Boro Zone"),
    ]
    
    schema = StructType([
        StructField("LocationID", IntegerType()),
        StructField("Borough", StringType()),
        StructField("Zone", StringType()),
        StructField("service_zone", StringType()),
    ])
    
    zones_df = spark.createDataFrame(duplicate_data, schema)
    dim_location = dimensional_transform.create_dim_location(zones_df)
    
    # Should have 2 unique locations, not 3
    assert dim_location.count() == 2


def test_create_dim_rate_code(dimensional_transform):
    """Test rate code dimension creation."""
    dim_rate_code = dimensional_transform.create_dim_rate_code()
    
    # Should have 6 rate codes
    assert dim_rate_code.count() == 6
    
    # Check columns
    assert "rate_code_id" in dim_rate_code.columns
    assert "rate_code_description" in dim_rate_code.columns
    
    # Verify specific rate codes exist
    rate_codes = {row.rate_code_id: row.rate_code_description 
                  for row in dim_rate_code.collect()}
    
    assert 1 in rate_codes
    assert "Standard" in rate_codes[1]
    assert 2 in rate_codes
    assert "JFK" in rate_codes[2]
    assert 3 in rate_codes
    assert "Newark" in rate_codes[3]


def test_create_dim_payment_type(dimensional_transform):
    """Test payment type dimension creation."""
    dim_payment_type = dimensional_transform.create_dim_payment_type()
    
    # Should have 6 payment types
    assert dim_payment_type.count() == 6
    
    # Check columns
    assert "payment_type_id" in dim_payment_type.columns
    assert "payment_type_description" in dim_payment_type.columns
    
    # Verify specific payment types exist
    payment_types = {row.payment_type_id: row.payment_type_description 
                     for row in dim_payment_type.collect()}
    
    assert 1 in payment_types
    assert "Credit" in payment_types[1]
    assert 2 in payment_types
    assert "Cash" in payment_types[2]


def test_create_fact_trips(dimensional_transform, sample_trips_df):
    """Test fact table creation."""
    # Clean trips first (this adds trip_duration_minutes)
    cleaned_trips = dimensional_transform.clean_trips(sample_trips_df)
    
    # Create required dimension
    dim_datetime = dimensional_transform.create_dim_datetime(cleaned_trips)
    
    # Create fact table
    fact_trips = dimensional_transform.create_fact_trips(cleaned_trips, dim_datetime)
    
    # Should have same number of records as input
    assert fact_trips.count() == sample_trips_df.count()
    
    # Check key columns exist
    key_cols = ['trip_id', 'pickup_datetime_id', 'dropoff_datetime_id',
                'pickup_location_id', 'dropoff_location_id', 'rate_code_id',
                'payment_type_id', 'fare_amount', 'total_amount']
    for col in key_cols:
        assert col in fact_trips.columns
    
    # Verify foreign keys are not null
    null_pickup_count = fact_trips.filter(fact_trips.pickup_datetime_id.isNull()).count()
    null_dropoff_count = fact_trips.filter(fact_trips.dropoff_datetime_id.isNull()).count()
    
    assert null_pickup_count == 0
    assert null_dropoff_count == 0


def test_create_fact_trips_handles_airport_fee(dimensional_transform, sample_trips_df):
    """Test that Airport_fee is normalized to airport_fee."""
    cleaned_trips = dimensional_transform.clean_trips(sample_trips_df)
    dim_datetime = dimensional_transform.create_dim_datetime(cleaned_trips)
    fact_trips = dimensional_transform.create_fact_trips(cleaned_trips, dim_datetime)
    
    # Check that airport_fee column exists (lowercase)
    assert "airport_fee" in fact_trips.columns
    
    # Verify it's not null (should default to 0.0)
    null_count = fact_trips.filter(fact_trips.airport_fee.isNull()).count()
    assert null_count == 0


def test_create_fact_trips_handles_cbd_fee(dimensional_transform, spark):
    """Test that cbd_congestion_fee is properly handled."""
    # Create data without cbd_congestion_fee
    data = [
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2, 3.5, 1, 'N', 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 2.5, 0.0, None, 2023, 1),
    ]
    
    schema = StructType([
        StructField("VendorID", IntegerType()),
        StructField("tpep_pickup_datetime", TimestampType()),
        StructField("tpep_dropoff_datetime", TimestampType()),
        StructField("passenger_count", IntegerType()),
        StructField("trip_distance", DoubleType()),
        StructField("RatecodeID", IntegerType()),
        StructField("store_and_fwd_flag", StringType()),
        StructField("PULocationID", IntegerType()),
        StructField("DOLocationID", IntegerType()),
        StructField("payment_type", IntegerType()),
        StructField("fare_amount", DoubleType()),
        StructField("extra", DoubleType()),
        StructField("mta_tax", DoubleType()),
        StructField("tip_amount", DoubleType()),
        StructField("tolls_amount", DoubleType()),
        StructField("improvement_surcharge", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("congestion_surcharge", DoubleType()),
        StructField("Airport_fee", DoubleType()),
        StructField("cbd_congestion_fee", DoubleType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
    ])
    
    df = spark.createDataFrame(data, schema)
    cleaned_df = dimensional_transform.clean_trips(df)
    dim_datetime = dimensional_transform.create_dim_datetime(cleaned_df)
    fact_trips = dimensional_transform.create_fact_trips(cleaned_df, dim_datetime)
    
    # Should coalesce to congestion_surcharge when cbd_congestion_fee is null
    row = fact_trips.first()
    assert row.cbd_congestion_fee is not None


def test_create_fact_trips_partitioning_columns(dimensional_transform, sample_trips_df):
    """Test that fact table includes year and month for partitioning."""
    cleaned_trips = dimensional_transform.clean_trips(sample_trips_df)
    dim_datetime = dimensional_transform.create_dim_datetime(cleaned_trips)
    fact_trips = dimensional_transform.create_fact_trips(cleaned_trips, dim_datetime)
    
    # Check partitioning columns exist
    assert "year" in fact_trips.columns
    assert "month" in fact_trips.columns
    
    # Verify values
    row = fact_trips.first()
    assert row.year == 2023
    assert row.month == 1


def test_transform_timestamp_initialization(dimensional_transform):
    """Test that transform timestamp is set during initialization."""
    assert dimensional_transform.transform_timestamp is not None
    assert isinstance(dimensional_transform.transform_timestamp, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])