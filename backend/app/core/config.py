from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./culinary.db"
    debug: bool = False
    app_username: str = ""
    app_password: str = ""


settings = Settings()

# The application intentionally has one local owner account.
OWNER_ID = 1
