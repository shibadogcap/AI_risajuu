import os
from enum import Enum

from google import genai
from google.genai import types
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Tool,
)
from pydantic import BaseModel


# AIりさじゅうの基本設定
class RisajuuConfig(BaseModel):
    google_api_key: str
    main_model_name: str
    sub_model_name: str
    common_instruction: str
    system_instruction: str


# 履歴インポート・エクスポート用の構造体
class History(BaseModel):
    contents: list[types.Content]


# 返答メッセージの種類
class ReplyType(str, Enum):
    text = "text"
    file = "file"


# 返答メッセージの種類と内容
class Reply(BaseModel):
    type: ReplyType
    body: str


# 履歴の保持と回答の生成を担当するクラス
# Discordのサーバー・DMごとにインスタンス化される
class AI_risajuu:
    def __init__(self, config):
        self.config = config
        self.client = genai.Client(api_key=config.google_api_key)
        self.chat = self.client.aio.chats.create(model=config.main_model_name)
        self.google_search_tool = Tool(google_search=GoogleSearch())
        self.url_context_tool = Tool(url_context=types.UrlContext())
        self.current_system_instruction = config.system_instruction

    def import_history(self, json_str):
        # 履歴の読み込み
        history = History.model_validate_json(json_str)
        self.chat = self.client.aio.chats.create(model=self.config.main_model_name, history=history.contents)

    def export_history(self):
        # 履歴の書き出し
        history = History(contents=self.chat.get_history())
        return history.model_dump_json(indent=2)

    def set_custom_instruction(self, custom_instruction):
        # プロンプトのカスタム
        self.current_system_instruction = custom_instruction

    async def react(self, input_text):
        # リアクションをサブのモデルで生成
        emoji = await self.client.aio.models.generate_content(
            model=self.config.sub_model_name,
            contents=[
                """
                    # 指示
                    「"""
                + input_text
                + """」というメッセージへのリアクションとして適切な絵文字を一つだけ選んでください。
                # 注意
                出力には**絵文字一文字のみ**を取ってください。余計なテキストや説明は**絶対に**含めず、**絵文字一文字のみ**を出力してください。
                """
            ],
            config=GenerateContentConfig(safety_settings=get_safety_settings()),
        )
        return emoji.text.strip()

    async def reply(self, input_text, attachments=[]):
        # テキストと添付ファイルに対する返答を生成する

        if input_text.startswith("あ、これはりさじゅう反応しないでね"):
            pass
        elif input_text.endswith("リセット"):
            for file in self.client.files.list():
                self.client.files.delete(name=file.name)
            self.current_system_instruction = self.config.system_instruction
            self.chat = self.client.aio.chats.create(model=self.config.main_model_name)
            yield Reply(type=ReplyType.text, body="履歴をリセットしたじゅう！")
        else:
            text = types.Part.from_text(text=input_text)
            files = []
            for attachment in attachments:
                await attachment.save(attachment.filename)
                files.append(
                    self.client.files.upload(
                        file="./" + attachment.filename,
                    )
                )
                os.remove(attachment.filename)

            parts = [text]
            parts.extend(files)
            config = GenerateContentConfig(
                system_instruction=self.config.common_instruction + self.current_system_instruction,
                tools=[self.google_search_tool, self.url_context_tool],
                safety_settings=get_safety_settings(),
            )

            # 返答をストリーミングで生成する
            # そのままだと区切りが中途半端なため、改行区切りでyieldする
            buffer = ""
            async for chunk in await self.chat.send_message_stream(message=parts, config=config):
                if chunk.text:
                    buffer += chunk.text
                    pop = buffer.rsplit(sep="\n", maxsplit=1)
                    if len(pop) == 2:
                        yield Reply(type=ReplyType.text, body=pop[0])
                        buffer = pop[1]
                else:
                    if buffer != "":
                        yield Reply(type=ReplyType.text, body=buffer)
                        buffer = ""

            if buffer != "":
                yield Reply(type=ReplyType.text, body=buffer)


def get_safety_settings():
    # 安全フィルタ設定：ブロックなし
    safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
    ]
    return safety_settings
