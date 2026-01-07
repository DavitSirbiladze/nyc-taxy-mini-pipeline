from pyspark.sql import SparkSession


def get_spark_session(app_name: str = "NYC Taxi Pipeline", 
                      master: str = None,
                      enable_gcs: bool = False) -> SparkSession:
    """
    Create and configure Spark session with appropriate settings.
    
    Args:
        app_name: Name of the Spark application
        master: Spark master URL (if None, uses local[*])
        enable_gcs: Whether to enable GCS connector
    
    Returns:
        Configured SparkSession
    """
    builder = SparkSession.builder.appName(app_name)
    
    # Set master if not already set
    if master:
        builder = builder.master(master)
    
    # Configure for GCS if needed
    if enable_gcs:
        builder = builder.config(
            "spark.jars",
            "https://storage.googleapis.com/hadoop-lib/gcs/gcs-connector-hadoop3-latest.jar"
        )
    
    # Add PostgreSQL JDBC driver
    builder = builder.config(
        "spark.jars",
        "/opt/spark/jars/postgresql-42.7.8.jar"
    )
    
    # Performance tuning
    builder = (builder
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.sql.files.maxPartitionBytes", "134217728")  # 128MB
        .config("spark.sql.parquet.compression.codec", "snappy")
    )
    
    spark = builder.getOrCreate()
    
    # Set log level
    spark.sparkContext.setLogLevel("WARN")
    
    return spark