"""
Database Loader Job - SIMPLIFIED

Loads dimensional model from silver layer into PostgreSQL database
for analytical queries and BI tool integration.
"""

import argparse
import os
import sys
from typing import List

# Fix console encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set PySpark Python executable (must be before PySpark imports)
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

# Fix Python path to find common module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from pyspark.sql import DataFrame, SparkSession

from common.spark_session import get_spark_session
from common.config import PipelineConfig


class DatabaseLoader:
    """Loads dimensional model into PostgreSQL."""
    
    def __init__(self, config: PipelineConfig, spark: SparkSession):
        self.config = config
        self.spark = spark
    
    def execute_sql(self, sql: str, description: str = None) -> None:
        """Execute SQL statement directly on PostgreSQL."""
        import psycopg2
        
        try:
            conn = psycopg2.connect(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.user,
                password=self.config.database.password
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            if description:
                print(f"  {description}")
            
            cursor.execute(sql)
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  [WARN] SQL execution issue: {e}")
    
    def truncate_table(self, table_name: str) -> None:
        """Truncate table instead of dropping it (preserves structure and constraints)."""
        print(f"  Truncating {table_name}...")
        self.execute_sql(
            f"TRUNCATE TABLE {table_name} CASCADE",
            f"Cleared {table_name}"
        )
    
    def read_dimension(self, name: str) -> DataFrame:
        """Read dimension table from silver layer."""
        silver_path = self.config.storage.get_silver_path(
            "nyc_taxi", "dimensions", name
        )
        
        print(f"Reading {name} from: {silver_path}")
        df = self.spark.read.parquet(silver_path)
        count = df.count()
        print(f"  -> Loaded {count} records")
        return df
    
    def read_fact(self, year: int, months: List[int]) -> DataFrame:
        """Read fact table from silver layer."""
        silver_path = self.config.storage.get_silver_path(
            "nyc_taxi", "facts", "fact_taxi_trips"
        )
        
        print(f"\nReading fact_taxi_trips from: {silver_path}")
        
        # Build partition filters
        month_filters = " OR ".join([f"month = {m}" for m in months])
        filter_expr = f"year = {year} AND ({month_filters})"
        print(f"Filter: {filter_expr}")
        
        df = (self.spark.read
            .parquet(silver_path)
            .filter(filter_expr)
        )
        
        count = df.count()
        print(f"  -> Loaded {count} records")
        
        if count == 0:
            print(f"\nWARNING: No records found!")
            print(f"Checking what's actually in the silver layer...")
            
            # Show what's available
            df_all = self.spark.read.parquet(silver_path)
            print(f"Total records in silver: {df_all.count()}")
            print("Available year/month combinations:")
            df_all.groupBy("year", "month").count().orderBy("year", "month").show()
            
            raise ValueError(f"No records found for year={year}, months={months}")
        
        return df
    
    def load_to_postgres(self, df: DataFrame, table_name: str, mode: str = "overwrite") -> None:
        """
        Load DataFrame to PostgreSQL table.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            mode: Write mode (overwrite, append)
        """
        count = df.count()
        print(f"\nLoading {count} records to {table_name} (mode={mode})...")
        
        if count == 0:
            print(f"  [!] Skipping - no records to load")
            return
        
        # Show sample
        print(f"Sample data from {table_name}:")
        df.show(3, truncate=False)
        
        try:
            # If overwrite mode, truncate the table first (preserves structure)
            if mode == "overwrite":
                self.truncate_table(table_name)
            
            # JDBC properties
            jdbc_props = {
                "user": self.config.database.user,
                "password": self.config.database.password,
                "driver": "org.postgresql.Driver",
                "batchsize": "10000",
                "isolationLevel": "READ_UNCOMMITTED"
            }
            
            # Write to PostgreSQL using append mode (since we already truncated)
            df.write.jdbc(
                url=self.config.database.jdbc_url,
                table=table_name,
                mode="append",  # Always append since we truncate manually
                properties=jdbc_props
            )
            
            print(f"  [OK] Successfully loaded {table_name}")
            
        except Exception as e:
            print(f"  [ERROR] Loading {table_name}: {str(e)}")
            
            # Print more debug info
            print(f"\nDebug Info:")
            print(f"  JDBC URL: {self.config.database.jdbc_url}")
            print(f"  Table: {table_name}")
            print(f"  Mode: {mode}")
            print(f"  Schema:")
            df.printSchema()
            
            raise
    
    def run(self, year: int, months: List[int], mode: str = "overwrite") -> None:
        """
        Execute database loading pipeline.
        
        Args:
            year: Year to process
            months: List of months to process
            mode: Write mode for fact table (overwrite for full refresh, append for incremental)
        """
        print(f"\n{'='*70}")
        print(f"DATABASE LOADER")
        print(f"{'='*70}")
        print(f"Target: {self.config.database.jdbc_url}")
        print(f"Year: {year}")
        print(f"Months: {months}")
        print(f"Fact table mode: {mode}")
        print(f"{'='*70}\n")
        
        # Step 1: Load dimensions (always overwrite to keep them fresh)
        print("STEP 1: Loading Dimensions")
        print("-" * 70)
        
        try:
            dim_datetime = self.read_dimension("dim_datetime")
            self.load_to_postgres(dim_datetime, "dim_datetime", "overwrite")
        except Exception as e:
            print(f"Failed to load dim_datetime: {e}")
        
        try:
            dim_location = self.read_dimension("dim_location")
            self.load_to_postgres(dim_location, "dim_location", "overwrite")
        except Exception as e:
            print(f"Failed to load dim_location: {e}")
        
        try:
            dim_rate_code = self.read_dimension("dim_rate_code")
            self.load_to_postgres(dim_rate_code, "dim_rate_code", "overwrite")
        except Exception as e:
            print(f"Failed to load dim_rate_code: {e}")
        
        try:
            dim_payment_type = self.read_dimension("dim_payment_type")
            self.load_to_postgres(dim_payment_type, "dim_payment_type", "overwrite")
        except Exception as e:
            print(f"Failed to load dim_payment_type: {e}")
        
        # Step 2: Load fact table
        print("\nSTEP 2: Loading Fact Table")
        print("-" * 70)
        
        try:
            fact_trips = self.read_fact(year, months)
            self.load_to_postgres(fact_trips, "fact_taxi_trips", mode)
        except Exception as e:
            print(f"\n[X] CRITICAL ERROR loading fact table: {str(e)}")
            print("\nTroubleshooting:")
            print("1. Check if silver layer has data:")
            print(f"   Dir: {self.config.storage.get_silver_path('nyc_taxi', 'facts', 'fact_taxi_trips')}")
            print("2. Verify dimensional_transform.py completed successfully")
            print("3. Check year/month values match what was transformed")
            raise
        
        print(f"\n{'='*70}")
        print("[OK] DATABASE LOAD COMPLETED SUCCESSFULLY")
        print(f"{'='*70}\n")


def main():
    """Main entry point for database loader job."""
    parser = argparse.ArgumentParser(description="Load dimensional model to database")
    parser.add_argument("--year", type=int, default=2023, help="Year to process")
    parser.add_argument("--months", type=str, default="1",
                       help="Comma-separated months to process")
    parser.add_argument("--mode", type=str, default="overwrite",
                       choices=["overwrite", "append"],
                       help="Write mode for fact table")
    parser.add_argument("--storage-type", type=str, default="local",
                       choices=["local", "gcs"], help="Storage type")
    
    args = parser.parse_args()
    
    # Parse months
    months = [int(m.strip()) for m in args.months.split(",")]
    
    # Set storage type
    os.environ["STORAGE_TYPE"] = args.storage_type
    
    # Initialize config and Spark
    config = PipelineConfig()
    
    # Print config for debugging
    print(f"\nConfiguration:")
    print(f"  Storage type: {config.storage.storage_type}")
    print(f"  Silver path: {config.storage.get_silver_path('nyc_taxi')}")
    print(f"  Database: {config.database.jdbc_url}")
    print(f"  DB Host: {config.database.host}")
    print(f"  DB Port: {config.database.port}")
    print(f"  DB Name: {config.database.database}")
    print(f"  DB User: {config.database.user}\n")
    
    spark = get_spark_session(
        app_name="Database Loader",
        enable_gcs=(args.storage_type == "gcs")
    )
    
    try:
        # Run loader
        loader = DatabaseLoader(config, spark)
        loader.run(year=args.year, months=months, mode=args.mode)
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"PIPELINE FAILED")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nStack trace:")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()