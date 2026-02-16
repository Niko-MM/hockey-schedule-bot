from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    bot_token : str
    admin_players:int
    admin_worker: int
    admin_goalkeeper: int
    main: int
    spare: int

    

    model_config = SettingsConfigDict(env_file='.env')



bot_settings = BotSettings() # type: ignore