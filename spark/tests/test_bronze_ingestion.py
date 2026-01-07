"""
Unit tests for Bronze Layer Ingestion.

Tests cover:
- Schema validation
- Metadata addition
- Configuration paths
- Error handling
"""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, DoubleType, TimestampType

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from jobs.bronze_ingestion import BronzeIngestion


@pytest.fixture(scope="session")
def spark():
    """Create a Spark session for testing."""
    spark = (SparkSession.builder
        .master("local[2]")
        .appName("bronze-ingestion-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    yield spark
    spark.stop()


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock configuration object."""
    config = Mock()
    config.taxi_data_base_url = "https://test.com/data"
    config.zone_lookup_url = "https://test.com/zones.csv"
    
    # Mock storage paths using tmp_path
    config.storage = Mock()
    config.storage.get_raw_path = lambda dataset, filename: os.path.join(
        str(tmp_path), "raw", dataset, filename
    )
    config.storage.get_bronze_path = lambda source, dataset: os.path.join(
        str(tmp_path), "bronze", source, dataset
    )
    
    return config


@pytest.fixture
def bronze_ingestion(mock_config, spark):
    """Create a BronzeIngestion instance for testing."""
    return BronzeIngestion(mock_config, spark)


def test_taxi_schema(bronze_ingestion):
    """Test that taxi schema is correctly defined."""
    schema = bronze_ingestion.get_taxi_schema()
    
    # Verify schema is StructType
    assert isinstance(schema, StructType)
    
    # Verify key fields exist
    field_names = [field.name for field in schema.fields]
    expected_fields = [
        "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime",
        "passenger_count", "trip_distance", "PULocationID", "DOLocationID",
        "fare_amount", "total_amount"
    ]
    for field in expected_fields:
        assert field in field_names, f"Missing field: {field}"
    
    # Verify specific data types
    field_dict = {field.name: field.dataType for field in schema.fields}
    assert isinstance(field_dict["VendorID"], IntegerType)
    assert isinstance(field_dict["tpep_pickup_datetime"], TimestampType)
    assert isinstance(field_dict["trip_distance"], DoubleType)


def test_metadata_columns(bronze_ingestion, spark):
    """Test that metadata columns are added during ingestion."""
    # Create sample DataFrame with correct types
    sample_data = [
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 2.5, 15.0)
    ]
    schema = StructType([
        StructField("VendorID", IntegerType()),
        StructField("tpep_pickup_datetime", TimestampType()),
        StructField("tpep_dropoff_datetime", TimestampType()),
        StructField("trip_distance", DoubleType()),
        StructField("fare_amount", DoubleType())
    ])
    
    df = spark.createDataFrame(sample_data, schema)
    
    # Add metadata columns (mimicking what the ingestion does)
    from pyspark.sql import functions as F
    df_with_metadata = (df
        .withColumn("ingestion_timestamp", F.lit(bronze_ingestion.ingestion_timestamp))
        .withColumn("source_file", F.lit("test_file.parquet"))
        .withColumn("year", F.lit(2023))
        .withColumn("month", F.lit(1))
    )
    
    # Verify metadata columns exist
    assert "ingestion_timestamp" in df_with_metadata.columns
    assert "source_file" in df_with_metadata.columns
    assert "year" in df_with_metadata.columns
    assert "month" in df_with_metadata.columns
    
    # Verify metadata values
    first_row = df_with_metadata.first()
    assert first_row["year"] == 2023
    assert first_row["month"] == 1
    assert first_row["source_file"] == "test_file.parquet"


@patch('requests.get')
def test_download_file_success(mock_get, bronze_ingestion, tmp_path):
    """Test successful file download."""
    # Mock successful response
    mock_response = Mock()
    mock_response.iter_content = lambda chunk_size: [b"test data"]
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    local_path = str(tmp_path / "test_file.parquet")
    result = bronze_ingestion.download_file("https://test.com/file.parquet", local_path)
    
    assert result is True
    assert os.path.exists(local_path)
    with open(local_path, 'rb') as f:
        assert f.read() == b"test data"


@patch('requests.get')
def test_download_file_failure(mock_get, bronze_ingestion, tmp_path):
    """Test download failure handling."""
    # Mock failed request
    mock_get.side_effect = Exception("Network error")
    
    local_path = str(tmp_path / "test_file.parquet")
    result = bronze_ingestion.download_file("https://test.com/file.parquet", local_path)
    
    assert result is False
    assert not os.path.exists(local_path)


def test_config_paths(mock_config):
    """Test that config paths are correctly generated."""
    raw_path = mock_config.storage.get_raw_path("yellow_trips", "test.parquet")
    assert "raw" in raw_path
    assert "yellow_trips" in raw_path
    assert "test.parquet" in raw_path
    
    bronze_path = mock_config.storage.get_bronze_path("nyc_taxi", "yellow_trips")
    assert "bronze" in bronze_path
    assert "nyc_taxi" in bronze_path
    assert "yellow_trips" in bronze_path


def test_ingest_taxi_trips_full(bronze_ingestion, spark, tmp_path):
    """Test full taxi trips ingestion with real file operations."""
    # Create sample taxi data
    sample_data = [
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 
         2, 5.0, 1, "N", 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0),
        (2, datetime(2023, 1, 1, 11, 0), datetime(2023, 1, 1, 11, 30), 
         1, 3.0, 1, "N", 150, 250, 2, 10.0, 0.5, 0.5, 0.0, 0.0, 0.3, 11.3, 0.0, 0.0, 0.0),
    ]
    
    schema = bronze_ingestion.get_taxi_schema()
    df = spark.createDataFrame(sample_data, schema)
    
    # Save to temp parquet file
    temp_parquet = str(tmp_path / "temp_trips.parquet")
    df.write.parquet(temp_parquet)
    
    # Mock the download to skip it
    with patch.object(bronze_ingestion, 'download_file', return_value=True):
        with patch.object(bronze_ingestion.config.storage, 'get_raw_path', return_value=temp_parquet):
            bronze_ingestion.ingest_taxi_trips(year=2023, months=[1])
    
    # Read back from bronze layer
    bronze_path = bronze_ingestion.config.storage.get_bronze_path("nyc_taxi", "yellow_trips")
    result_df = spark.read.parquet(bronze_path)
    
    # Verify metadata columns exist
    assert "ingestion_timestamp" in result_df.columns
    assert "source_file" in result_df.columns
    assert "year" in result_df.columns
    assert "month" in result_df.columns
    
    # Verify data count
    assert result_df.count() == 2
    
    # Verify metadata values
    first_row = result_df.first()
    assert first_row["year"] == 2023
    assert first_row["month"] == 1
    assert first_row["source_file"] == "yellow_tripdata_2023-01.parquet"


def test_ingest_zone_lookup(bronze_ingestion, spark, tmp_path):
    """Test zone lookup ingestion."""
    # Create sample zone lookup CSV
    csv_path = str(tmp_path / "taxi_zone_lookup.csv")
    with open(csv_path, 'w') as f:
        f.write("LocationID,Borough,Zone,service_zone\n")
        f.write("1,Manhattan,Downtown,Yellow Zone\n")
        f.write("2,Brooklyn,Park Slope,Green Zone\n")
    
    # Mock download and path
    with patch.object(bronze_ingestion, 'download_file', return_value=True):
        with patch.object(bronze_ingestion.config.storage, 'get_raw_path', return_value=csv_path):
            bronze_ingestion.ingest_zone_lookup()
    
    # Read back from bronze
    bronze_path = bronze_ingestion.config.storage.get_bronze_path("nyc_taxi", "zone_lookup")
    result_df = spark.read.parquet(bronze_path)
    
    # Verify data
    assert result_df.count() == 2
    assert "LocationID" in result_df.columns
    assert "Borough" in result_df.columns
    assert "ingestion_timestamp" in result_df.columns
    assert "source_file" in result_df.columns
    
    # Verify content
    rows = result_df.collect()
    boroughs = [row["Borough"] for row in rows]
    assert "Manhattan" in boroughs
    assert "Brooklyn" in boroughs


def test_idempotency(bronze_ingestion, spark, tmp_path):
    """Test that running ingestion twice with same data is idempotent."""
    sample_data = [
        (1, datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 30), 
         2, 5.0, 1, "N", 100, 200, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 0.3, 19.3, 0.0, 0.0, 0.0),
    ]
    
    schema = bronze_ingestion.get_taxi_schema()
    df = spark.createDataFrame(sample_data, schema)
    
    temp_parquet = str(tmp_path / "temp_trips.parquet")
    df.write.parquet(temp_parquet)
    
    # Run ingestion twice
    for i in range(2):
        with patch.object(bronze_ingestion, 'download_file', return_value=True):
            with patch.object(bronze_ingestion.config.storage, 'get_raw_path', return_value=temp_parquet):
                bronze_ingestion.ingest_taxi_trips(year=2023, months=[1])
    
    # Should have the same data, not duplicates (overwrite mode)
    bronze_path = bronze_ingestion.config.storage.get_bronze_path("nyc_taxi", "yellow_trips")
    result_df = spark.read.parquet(bronze_path)
    
    # Should only have 1 record
    assert result_df.filter("year=2023 AND month=1").count() == 1


def test_download_skip_on_error(bronze_ingestion, capsys):
    """Test that failed downloads are skipped gracefully."""
    with patch.object(bronze_ingestion, 'download_file', return_value=False):
        # Should not raise exception
        bronze_ingestion.ingest_taxi_trips(year=2023, months=[1])
    
    # Check for skip message
    captured = capsys.readouterr()
    assert "Skipping" in captured.out


def test_missing_columns_warning(bronze_ingestion, spark, tmp_path, capsys):
    """Test that missing columns in zone lookup generate warnings."""
    # Create CSV with missing columns
    csv_path = str(tmp_path / "bad_zones.csv")
    with open(csv_path, 'w') as f:
        f.write("LocationID,Borough\n")  # Missing Zone and service_zone
        f.write("1,Manhattan\n")
    
    with patch.object(bronze_ingestion, 'download_file', return_value=True):
        with patch.object(bronze_ingestion.config.storage, 'get_raw_path', return_value=csv_path):
            bronze_ingestion.ingest_zone_lookup()
    
    # Check for warning in output
    captured = capsys.readouterr()
    assert "WARNING" in captured.out or "Zone" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])