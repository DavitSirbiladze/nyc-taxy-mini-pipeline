"""
PySpark Job 2: Dimensional Model Transformation

Reads bronze layer data, applies transformations, and creates a dimensional model
(star schema) in the silver/gold layer.

Dimensional Model Design:
- Fact Table: fact_taxi_trips (grain: one row per trip)
- Dimensions: dim_datetime, dim_location, dim_rate_code, dim_payment_type

This enables efficient analytical queries while maintaining normalized dimensions.
"""

import argparse
import os
import sys
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
from pyspark.sql.window import Window

from common.spark_session import get_spark_session
from common.config import PipelineConfig


class DimensionalTransform:
    """Transforms bronze data into dimensional model."""
    
    def __init__(self, config: PipelineConfig, spark: SparkSession):
        self.config = config
        self.spark = spark
        self.transform_timestamp = datetime.now()
    
    def read_bronze_trips(self, year: int, months: List[int]) -> DataFrame:
        """
        Read taxi trips from bronze layer.
        
        Args:
            year: Year to read
            months: List of months to read
            
        Returns:
            DataFrame with bronze trip data
        """
        bronze_path = self.config.storage.get_bronze_path(
            "nyc_taxi", "yellow_trips"
        )
        
        # Build partition filters
        month_filters = " OR ".join([f"month = {m}" for m in months])
        filter_expr = f"year = {year} AND ({month_filters})"
        
        print(f"Reading bronze trips from: {bronze_path}")
        print(f"Filter: {filter_expr}")
        
        df = (self.spark.read
            .parquet(bronze_path)
            .filter(filter_expr)
        )
        
        print(f"Loaded {df.count()} trip records from bronze")
        return df
    
    def read_bronze_zones(self) -> DataFrame:
        """Read zone lookup from bronze layer."""
        bronze_path = self.config.storage.get_bronze_path(
            "nyc_taxi", "zone_lookup"
        )
        
        print(f"Reading zone lookup from: {bronze_path}")
        return self.spark.read.parquet(bronze_path)
    
    def clean_trips(self, df: DataFrame) -> DataFrame:
        """
        Clean and filter trip data.
        
        Business rules:
        - Remove records with null pickup/dropoff times
        - Filter invalid fares (negative or extremely high)
        - Filter invalid trip distances
        - Filter invalid passenger counts
        - Remove trips with same pickup/dropoff location
        """
        print("Applying data quality filters...")

        initial_count = df.count()

        cleaned_df = (
            df
            .filter(F.col("tpep_pickup_datetime").isNotNull())
            .filter(F.col("tpep_dropoff_datetime").isNotNull())
            .filter(F.col("PULocationID").isNotNull())
            .filter(F.col("DOLocationID").isNotNull())
            .filter(F.col("tpep_dropoff_datetime") > F.col("tpep_pickup_datetime"))
            .filter(F.col("fare_amount") >= 0)
            .filter(F.col("fare_amount") <= 500)
            .filter(F.col("trip_distance") > 0)
            .filter(F.col("trip_distance") <= 100)
            .filter(F.col("passenger_count") >= 1)
            .filter(F.col("passenger_count") <= 6)
            .filter(F.col("PULocationID") != F.col("DOLocationID"))
            .withColumn(
                "trip_duration_minutes",
                F.expr(
                    "timestampdiff(MINUTE, tpep_pickup_datetime, tpep_dropoff_datetime)"
                )
            )
            .filter(F.col("trip_duration_minutes") > 0)
            .filter(F.col("trip_duration_minutes") <= 300)
        )

        final_count = cleaned_df.count()
        filtered_count = initial_count - final_count
        print(f"Filtered {filtered_count} records ({filtered_count / initial_count * 100:.2f}%)")
        print(f"Clean records: {final_count}")

        return cleaned_df
    
    def create_dim_datetime(self, df: DataFrame) -> DataFrame:
        """
        Create datetime dimension from trip timestamps.
        
        Includes calendar attributes for analytical queries.
        """
        print("Creating dim_datetime...")
        
        # Extract all unique datetime values from pickup times
        datetime_df = (df
            .select(F.col("tpep_pickup_datetime").alias("datetime_value"))
            .union(
                df.select(F.col("tpep_dropoff_datetime").alias("datetime_value"))
            )
            .distinct()
        )
        
        # Add calendar attributes
        dim_datetime = (datetime_df
            .withColumn("datetime_id", 
                F.concat(
                    F.date_format("datetime_value", "yyyyMMdd"),
                    F.date_format("datetime_value", "HHmmss")
                ).cast("long"))
            .withColumn("date", F.to_date("datetime_value"))
            .withColumn("year", F.year("datetime_value"))
            .withColumn("month", F.month("datetime_value"))
            .withColumn("day", F.dayofmonth("datetime_value"))
            .withColumn("hour", F.hour("datetime_value"))
            .withColumn("minute", F.minute("datetime_value"))
            .withColumn("day_of_week", F.dayofweek("datetime_value"))
            .withColumn("day_name", F.date_format("datetime_value", "EEEE"))
            .withColumn("month_name", F.date_format("datetime_value", "MMMM"))
            .withColumn("quarter", F.quarter("datetime_value"))
            .withColumn("is_weekend", 
                F.when(F.dayofweek("datetime_value").isin([1, 7]), True).otherwise(False))
            .select(
                "datetime_id", "datetime_value", "date", "year", "month", "day",
                "hour", "minute", "day_of_week", "day_name", "month_name",
                "quarter", "is_weekend"
            )
        )
        
        print(f"Created dim_datetime with {dim_datetime.count()} records")
        return dim_datetime
    
    def create_dim_location(self, zones_df: DataFrame) -> DataFrame:
        """
        Create location dimension from zone lookup.
        
        One record per zone with borough and service zone info.
        Handles the actual CSV column names: LocationID, Borough, Zone, service_zone
        """
        print("Creating dim_location...")
        
        # Check what columns we have in the dataframe
        print(f"Zone lookup columns: {zones_df.columns}")
        
        dim_location = (zones_df
            .withColumnRenamed("LocationID", "location_id")
            .withColumnRenamed("Borough", "borough")
            .withColumnRenamed("Zone", "zone_name")
            # service_zone is already lowercase in the CSV
            .select("location_id", "zone_name", "borough", "service_zone")
            .dropDuplicates()  # Remove any duplicates
        )
        
        print(f"Created dim_location with {dim_location.count()} records")
        return dim_location
    
    def create_dim_rate_code(self) -> DataFrame:
        """Create rate code dimension with descriptions."""
        print("Creating dim_rate_code...")
        
        rate_codes = [
            (1, "Standard rate"),
            (2, "JFK"),
            (3, "Newark"),
            (4, "Nassau or Westchester"),
            (5, "Negotiated fare"),
            (6, "Group ride")
        ]
        
        dim_rate_code = self.spark.createDataFrame(
            rate_codes, 
            ["rate_code_id", "rate_code_description"]
        )
        
        print(f"Created dim_rate_code with {dim_rate_code.count()} records")
        return dim_rate_code
    
    def create_dim_payment_type(self) -> DataFrame:
        """Create payment type dimension with descriptions."""
        print("Creating dim_payment_type...")
        
        payment_types = [
            (1, "Credit card"),
            (2, "Cash"),
            (3, "No charge"),
            (4, "Dispute"),
            (5, "Unknown"),
            (6, "Voided trip")
        ]
        
        dim_payment_type = self.spark.createDataFrame(
            payment_types,
            ["payment_type_id", "payment_type_description"]
        )
        
        print(f"Created dim_payment_type with {dim_payment_type.count()} records")
        return dim_payment_type
    
    def create_fact_trips(self, trips_df: DataFrame, dim_datetime: DataFrame) -> DataFrame:
        """
        Create fact table with foreign keys to dimensions.
        
        Grain: One row per trip
        """
        print("Creating fact_taxi_trips...")
        
        # Create lookup for datetime IDs
        datetime_lookup = dim_datetime.select("datetime_value", "datetime_id")
        
        # Join to get pickup/dropoff datetime IDs
        fact_df = (trips_df
            .join(
                datetime_lookup.alias("pickup_dt"),
                trips_df.tpep_pickup_datetime == F.col("pickup_dt.datetime_value"),
                "left"
            )
            .join(
                datetime_lookup.alias("dropoff_dt"),
                trips_df.tpep_dropoff_datetime == F.col("dropoff_dt.datetime_value"),
                "left"
            )
            .select(
                # Generate surrogate key
                F.monotonically_increasing_id().alias("trip_id"),
                
                # Foreign keys
                F.col("pickup_dt.datetime_id").alias("pickup_datetime_id"),
                F.col("dropoff_dt.datetime_id").alias("dropoff_datetime_id"),
                F.col("PULocationID").alias("pickup_location_id"),
                F.col("DOLocationID").alias("dropoff_location_id"),
                F.col("RatecodeID").cast("int").alias("rate_code_id"),
                F.col("payment_type").alias("payment_type_id"),
                
                # Degenerate dimensions
                F.col("VendorID").alias("vendor_id"),
                F.col("store_and_fwd_flag"),
                
                # Measures
                F.col("passenger_count"),
                F.col("trip_distance"),
                F.col("fare_amount"),
                F.col("extra"),
                F.col("mta_tax"),
                F.col("tip_amount"),
                F.col("tolls_amount"),
                F.col("improvement_surcharge"),
                F.col("total_amount"),
                F.col("congestion_surcharge"),
                # Normalize Airport_fee to airport_fee
                F.when(F.col("Airport_fee").isNotNull(), F.col("Airport_fee"))
                 .otherwise(F.lit(0.0)).alias("airport_fee"),
                F.coalesce(F.col("cbd_congestion_fee"), F.col("congestion_surcharge"), F.lit(0.0)).alias("cbd_congestion_fee"),
                F.col("trip_duration_minutes"),
                
                # Metadata
                F.col("year"),
                F.col("month")
            )
        )
        
        print(f"Created fact_taxi_trips with {fact_df.count()} records")
        return fact_df
    
    def write_dimension(self, df: DataFrame, name: str) -> None:
        """Write dimension table to silver layer."""
        silver_path = self.config.storage.get_silver_path(
            "nyc_taxi", "dimensions", name
        )
        
        print(f"Writing {name} to: {silver_path}")
        
        (df
            .write
            .mode("overwrite")
            .parquet(silver_path)
        )
    
    def write_fact(self, df: DataFrame) -> None:
        """Write fact table to silver layer, partitioned by year/month."""
        silver_path = self.config.storage.get_silver_path(
            "nyc_taxi", "facts", "fact_taxi_trips"
        )
        
        print(f"Writing fact_taxi_trips to: {silver_path}")
        
        (df
            .write
            .mode("overwrite")
            .partitionBy("year", "month")
            .parquet(silver_path)
        )
    
    def run(self, year: int, months: List[int]) -> None:
        """
        Execute dimensional transformation pipeline.
        
        Args:
            year: Year to process
            months: List of months to process
        """
        print(f"Starting dimensional transformation for {year}, months: {months}")
        print(f"Transform timestamp: {self.transform_timestamp}")
        
        # Read bronze data
        trips_df = self.read_bronze_trips(year, months)
        zones_df = self.read_bronze_zones()
        
        # Clean trip data
        clean_trips_df = self.clean_trips(trips_df)
        if "cbd_congestion_fee" not in clean_trips_df.columns:
            clean_trips_df = clean_trips_df.withColumn(
            "cbd_congestion_fee",
            F.lit(0.0)
        )
    
        # Create dimensions
        dim_datetime = self.create_dim_datetime(clean_trips_df)
        dim_location = self.create_dim_location(zones_df)
        dim_rate_code = self.create_dim_rate_code()
        dim_payment_type = self.create_dim_payment_type()
        
        # Create fact table
        fact_trips = self.create_fact_trips(clean_trips_df, dim_datetime)
        
        # Write to silver layer
        self.write_dimension(dim_datetime, "dim_datetime")
        self.write_dimension(dim_location, "dim_location")
        self.write_dimension(dim_rate_code, "dim_rate_code")
        self.write_dimension(dim_payment_type, "dim_payment_type")
        self.write_fact(fact_trips)
        
        print("Dimensional transformation completed successfully")


def main():
    """Main entry point for dimensional transform job."""
    parser = argparse.ArgumentParser(description="Dimensional model transformation")
    parser.add_argument("--year", type=int, default=2023, help="Year to process")
    parser.add_argument("--months", type=str, default="1",
                       help="Comma-separated months to process")
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
        app_name="Dimensional Transform",
        enable_gcs=(args.storage_type == "gcs")
    )
    
    try:
        # Run transformation
        transform = DimensionalTransform(config, spark)
        transform.run(year=args.year, months=months)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()