from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    bot_token: str
    admin_players: int
    admin_worker: int
    admin_goalkeeper: int
    main: int
    spare: int
    # Якорный понедельник — от него считаются двухнедельные периоды (формат YYYY-MM-DD)
    anchor_monday: str | None = None

    model_config = SettingsConfigDict(env_file=".env")



bot_settings = BotSettings() # type: ignore