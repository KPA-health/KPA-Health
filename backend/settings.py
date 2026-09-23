import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_path: str = "hospital_validated.db"
    catalog_version: str = "v1"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["*"]
    timezone: str = "America/Bogota"
    
    # Query Executor Settings
    query_deadline_s: float = 30.0
    query_sql_limit_s: float = 2.0
    query_max_groups: int = 200
    query_max_length: int = 2000
    
    # Generation Settings
    max_concurrent_generations: int = 1
    max_queue_size: int = 4
    
    # Logging
    log_level: str = "INFO"
    
    # Profile config
    profiles_config_path: str = "config/models.yaml"

    class Config:
        env_prefix = "HIS_"

settings = Settings()
