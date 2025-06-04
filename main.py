import os

from dotenv import load_dotenv

from ai_risajuu import AI_risajuu
from discord_client import Risajuu_discord_client
from keep_alive import keep_alive


def main():
    load_dotenv()

    with open("default_prompt.md", "r", encoding="utf-8") as f:
        system_prompt = f.read()
    with open("common_prompt.md", "r", encoding="utf-8") as f:
        common_prompt = f.read()

    google_api_key = os.environ["GOOGLE_API_KEY"]
    risajuu = AI_risajuu(google_api_key, common_prompt, system_prompt)

    # Webサーバの立ち上げ
    keep_alive()

    discord_token = os.getenv("DISCORD_TOKEN")
    client = Risajuu_discord_client(risajuu)

    client.run(discord_token)


if __name__ == "__main__":
    main()
