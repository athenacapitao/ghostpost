from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str = "redis://localhost:6379/1"
    JWT_SECRET: str
    ADMIN_USERNAME: str = "athena"
    ADMIN_PASSWORD_HASH: str
    GMAIL_CREDENTIALS_FILE: str = "credentials.json"
    GMAIL_TOKEN_FILE: str = "token.json"

    # LLM via OpenClaw gateway — routes to ghostpost agent (MiniMax M2.5)
    LLM_GATEWAY_URL: str = "http://127.0.0.1:18789/v1/chat/completions"
    LLM_GATEWAY_TOKEN: str = ""
    LLM_MODEL: str = "openclaw:ghostpost"
    LLM_USER_ID: str = "ghostpost-app"

    # Ghost Research — web search
    SEARCH_API_KEY: str = ""
    SEARCH_API_URL: str = "https://google.serper.dev/search"

    # Ghost Research — paths
    RESEARCH_DIR: str = "research"
    IDENTITIES_DIR: str = "config/identities"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
