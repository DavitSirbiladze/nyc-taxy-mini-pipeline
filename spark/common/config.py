import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StorageConfig:
    """Configuration for storage paths."""
    
    storage_type: str = os.getenv("STORAGE_TYPE", "local")  # local or gcs
    
    # Local paths
    local_base_path: str = "/data"
    local_bronze_path: str = field(default_factory=lambda: "/data/bronze")
    local_silver_path: str = field(default_factory=lambda: "/data/silver")
    local_gold_path: str = field(default_factory=lambda: "/data/gold")
    local_raw_path: str = field(default_factory=lambda: "/data/raw")
    
    # GCS paths
    gcs_project_id: Optional[str] = field(default_factory=lambda: os.getenv("GCS_PROJECT_ID"))
    gcs_bronze_bucket: Optional[str] = field(default_factory=lambda: os.getenv("GCS_BRONZE_BUCKET"))
    gcs_silver_bucket: Optional[str] = field(default_factory=lambda: os.getenv("GCS_SILVER_BUCKET"))
    gcs_gold_bucket: Optional[str] = field(default_factory=lambda: os.getenv("GCS_GOLD_BUCKET"))
    
    def __post_init__(self):
        """Initialize computed paths."""
        self.local_bronze_path = f"{self.local_base_path}/bronze"
        self.local_silver_path = f"{self.local_base_path}/silver"
        self.local_gold_path = f"{self.local_base_path}/gold"
        self.local_raw_path = f"{self.local_base_path}/raw"
    
    def get_bronze_path(self, *path_parts: str) -> str:
        """Get bronze layer path based on storage type."""
        if self.storage_type == "gcs":
            return f"gs://{self.gcs_bronze_bucket}/{'/'.join(path_parts)}"
        return os.path.join(self.local_bronze_path, *path_parts)
    
    def get_silver_path(self, *path_parts: str) -> str:
        """Get silver layer path based on storage type."""
        if self.storage_type == "gcs":
            return f"gs://{self.gcs_silver_bucket}/{'/'.join(path_parts)}"
        return os.path.join(self.local_silver_path, *path_parts)
    
    def get_gold_path(self, *path_parts: str) -> str:
        """Get gold layer path based on storage type."""
        if self.storage_type == "gcs":
            return f"gs://{self.gcs_gold_bucket}/{'/'.join(path_parts)}"
        return os.path.join(self.local_gold_path, *path_parts)
    
    def get_raw_path(self, *path_parts: str) -> str:
        """Get raw data download path (always local)."""
        return os.path.join(self.local_raw_path, *path_parts)


@dataclass
class DatabaseConfig:
    """Configuration for database connections."""
    
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "nyc_taxi"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "taxi_user"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "taxi_pass"))
    
    @property
    def jdbc_url(self) -> str:
        """Get JDBC connection URL."""
        return f"jdbc:postgresql://{self.host}:{self.port}/{self.database}"
    
    @property
    def connection_properties(self) -> dict:
        """Get JDBC connection properties."""
        return {
            "user": self.user,
            "password": self.password,
            "driver": "org.postgresql.Driver"
        }


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""
    
    app_name: str = "NYC Taxi Pipeline"
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # Data source URLs
    taxi_data_base_url: str = "https://d37ci6vzurychx.cloudfront.net/trip-data"
    zone_lookup_url: str = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    
    # Processing parameters
    default_year: int = 2023
    default_months: list = field(default_factory=lambda: [1])  # January by default