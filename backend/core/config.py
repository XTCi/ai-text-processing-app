from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "./data/app.db"
    task_timeout_seconds: int = 60


settings = Settings()
