from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Async URL used by the running app (asyncpg driver)
    database_url: str = "postgresql+asyncpg://shop_user:shop_pass@localhost:5432/shopping"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
