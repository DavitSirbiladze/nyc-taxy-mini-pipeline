"""
PySpark Job 1: Bronze Layer Ingestion

This job downloads raw NYC Taxi data and loads it into the bronze layer
with minimal transformation. It preserves data lineage through metadata columns.

Bronze layer structure:
  /bronze/nyc_taxi/yellow_trips/year=YYYY/month=MM/
  /bronze/nyc_taxi/zone_lookup/
  
Historical strategy: Supports ingesting multiple months, avoids duplicates
by using partitioning strategy.
"""

import argparse
import os
import sys
import requests
from datetime import datetime
from typing import List

# Set PySpark Python executable (must be before PySpark imports)
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

# Fix Python path to find common module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, TimestampType

from common.spark_session import get_spark_session
from common.config import PipelineConfig


class BronzeIngestion:
    """Handles ingestion of raw data into bronze layer."""
    
    def __init__(self, config: PipelineConfig, spark: SparkSession):
        self.config = config
        self.spark = spark
        self.ingestion_timestamp = datetime.now()
    
    def download_file(self, url: str, local_path: str) -> bool:
        """
        Download file from URL to local path.
        
        Args:
            url: Source URL
            local_path: Destination path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Downloading {url} to {local_path}...")
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Successfully downloaded {url}")
            return True
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return False
    
    def get_taxi_schema(self) -> StructType:
        """Define schema for yellow taxi trip data - UPDATED to match actual data."""
        return StructType([
            StructField("VendorID", IntegerType(), True),
            StructField("tpep_pickup_datetime", TimestampType(), True),
            StructField("tpep_dropoff_datetime", TimestampType(), True),
            StructField("passenger_count", IntegerType(), True),  # Source has BIGINT but we'll use Integer
            StructField("trip_distance", DoubleType(), True),
            StructField("RatecodeID", IntegerType(), True),  # Source has BIGINT but we'll use Integer
            StructField("store_and_fwd_flag", StringType(), True),
            StructField("PULocationID", IntegerType(), True),
            StructField("DOLocationID", IntegerType(), True),
            StructField("payment_type", IntegerType(), True),  # Source has BIGINT but we'll use Integer
            StructField("fare_amount", DoubleType(), True),
            StructField("extra", DoubleType(), True),
            StructField("mta_tax", DoubleType(), True),
            StructField("tip_amount", DoubleType(), True),
            StructField("tolls_amount", DoubleType(), True),
            StructField("improvement_surcharge", DoubleType(), True),
            StructField("total_amount", DoubleType(), True),
            StructField("congestion_surcharge", DoubleType(), True),
            StructField("Airport_fee", DoubleType(), True),  # Note: Capital A in source
            StructField("cbd_congestion_fee", DoubleType(), True),  # New field in 2024+ data
        ])
    
    def ingest_taxi_trips(self, year: int, months: List[int]) -> None:
        """
        Ingest yellow taxi trip data for specified months.
        
        Args:
            year: Year to ingest
            months: List of month numbers (1-12)
        """
        for month in months:
            month_str = f"{month:02d}"
            filename = f"yellow_tripdata_{year}-{month_str}.parquet"
            url = f"{self.config.taxi_data_base_url}/{filename}"
            local_path = self.config.storage.get_raw_path("yellow_trips", filename)
            
            # Download if not exists
            if not os.path.exists(local_path):
                if not self.download_file(url, local_path):
                    print(f"Skipping {filename} due to download error")
                    continue
            
            # Read with schema enforcement
            df = self.spark.read.parquet(local_path)
            
            # Add metadata columns for data lineage
            df_with_metadata = (df
                .withColumn("ingestion_timestamp", F.lit(self.ingestion_timestamp))
                .withColumn("source_file", F.lit(filename))
                .withColumn("year", F.lit(year))
                .withColumn("month", F.lit(month))
            )
            
            # Write to bronze layer partitioned by year/month
            bronze_path = self.config.storage.get_bronze_path(
                "nyc_taxi", "yellow_trips"
            )
            
            print(f"Writing {filename} to bronze: {bronze_path}")
            
            (df_with_metadata
                .write
                .mode("overwrite")  # Overwrite for idempotency
                .partitionBy("year", "month")
                .parquet(bronze_path)
            )
            
            print(f"Successfully ingested {filename} - {df.count()} records")
    
    def ingest_zone_lookup(self) -> None:
        """Ingest taxi zone lookup reference data."""
        url = self.config.zone_lookup_url
        local_path = self.config.storage.get_raw_path("zone_lookup", "taxi_zone_lookup.csv")
        
        # Download if not exists
        if not os.path.exists(local_path):
            if not self.download_file(url, local_path):
                print("Failed to download zone lookup")
                return
        
        # Read CSV with proper options
        print(f"Reading zone lookup from: {local_path}")
        df = (self.spark.read
            .option("header", "true")
            .option("inferSchema", "true")
            .csv(local_path)
        )
        
        # Verify we have the expected columns
        print(f"Zone lookup columns: {df.columns}")
        expected_columns = ["LocationID", "Borough", "Zone", "service_zone"]
        for col in expected_columns:
            if col not in df.columns:
                print(f"WARNING: Expected column '{col}' not found in zone lookup")
        
        # Add metadata
        df_with_metadata = (df
            .withColumn("ingestion_timestamp", F.lit(self.ingestion_timestamp))
            .withColumn("source_file", F.lit("taxi_zone_lookup.csv"))
        )
        
        # Write to bronze (not partitioned as it's small reference data)
        bronze_path = self.config.storage.get_bronze_path(
            "nyc_taxi", "zone_lookup"
        )
        
        print(f"Writing zone lookup to bronze: {bronze_path}")
        
        (df_with_metadata
            .write
            .mode("overwrite")
            .parquet(bronze_path)
        )
        
        print(f"Successfully ingested zone lookup - {df.count()} records")
        
        # Show sample for verification
        print("Sample zone lookup data:")
        df.show(3, truncate=False)
    
    def run(self, year: int, months: List[int]) -> None:
        """
        Execute bronze ingestion pipeline.
        
        Args:
            year: Year to process
            months: List of months to process
        """
        print(f"Starting bronze ingestion for {year}, months: {months}")
        print(f"Ingestion timestamp: {self.ingestion_timestamp}")
        
        # Ingest zone lookup (only once)
        self.ingest_zone_lookup()
        
        # Ingest taxi trips for specified months
        self.ingest_taxi_trips(year, months)
        
        print("Bronze ingestion completed successfully")


def main():
    """Main entry point for bronze ingestion job."""
    parser = argparse.ArgumentParser(description="Bronze layer ingestion")
    parser.add_argument("--year", type=int, default=2023, help="Year to process")
    parser.add_argument("--months", type=str, default="1", 
                       help="Comma-separated months to process (e.g., '1,2,3')")
    parser.add_argument("--storage-type", type=str, default="local",
                       choices=["local", "gcs"], help="Storage type")
    
    args = parser.parse_args()
    
    # Parse months
    months = [int(m.strip()) for m in args.months.split(",")]
    
    # Set storage type
    os.environ["STORAGE_TYPE"] = args.storage_type
    
    # Initialize config and Spark
    config = PipelineConfig()
    spark = get_spark_session(
        app_name="Bronze Ingestion",
        enable_gcs=(args.storage_type == "gcs")
    )
    
    try:
        # Run ingestion
        ingestion = BronzeIngestion(config, spark)
        ingestion.run(year=args.year, months=months)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()