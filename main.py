import asyncio
import os

from dotenv import load_dotenv

from keep_alive import keep_alive
from main_loop import AppConfig, DiscordConfig, LLMConfig, MainLoop, RisajuuConfig


def main():
    # Webサーバの立ち上げ
    keep_alive()

    # .envファイルの内容を環境変数として取り込む
    load_dotenv()

    # システムプロンプトの読み込み
    # 「カスタム」してもcommon_promptは残る
    with open("default_prompt.md", "r", encoding="utf-8") as f:
        system_prompt = f.read()
    with open("common_prompt.md", "r", encoding="utf-8") as f:
        common_prompt = f.read()

    targets = []
    for target in os.getenv("TARGET_CHANNEL_NAME").split(","):
        t = target.split("/")
        targets.append((t[0], t[1]))

    # 全体設定
    config = AppConfig(
        discord_config=DiscordConfig(
            token=os.getenv("DISCORD_TOKEN"),
            targets=targets,
        ),
        risajuu_config=RisajuuConfig(
            llm_config=LLMConfig(
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                main_model_name=os.getenv("MAIN_MODEL_NAME"),
                sub_model_name=os.getenv("SUB_MODEL_NAME"),
                system_instruction=system_prompt,
                common_instruction=common_prompt,
            ),
            reaction_probability=float(os.getenv("REACTION_PROBABILITY")),
        ),
    )

    main_loop = MainLoop(config)
    asyncio.run(main_loop.start())

    print("\n=== exit ===")


if __name__ == "__main__":
    main()
