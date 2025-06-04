import os
import random
from enum import Enum

from google import genai
from google.genai import types
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Tool,
)
from pydantic import BaseModel


class History(BaseModel):
    contents: list[types.Content]


class ReplyType(str, Enum):
    text = "text"
    file = "file"


class Reply(BaseModel):
    type: ReplyType
    body: str


def split_message_text(text, chunk_size=1500):
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


class AI_risajuu:
    def __init__(self, api_key, common_instruction, system_instruction):
        self.main_model_name = os.getenv("MAIN_MODEL_NAME")
        self.sub_model_name = os.getenv("SUB_MODEL_NAME")
        self.client = genai.Client(api_key=api_key)
        self.chat = self.client.aio.chats.create(model=self.main_model_name)
        self.google_search_tool = Tool(google_search=GoogleSearch())
        self.url_context_tool = Tool(url_context=types.UrlContext())
        self.common_instruction = common_instruction
        self.system_instruction = system_instruction
        self.current_system_instruction = system_instruction

    def import_history(self, json_str):
        history = History.model_validate_json(json_str)
        self.chat = self.client.aio.chats.create(model=self.main_model_name, history=history.contents)

    def export_history(self):
        history = History(contents=self.chat.get_history())
        return history.model_dump_json(indent=2)

    async def react(self, input_text, probability):
        if random.random() < probability:
            emoji = self.client.models.generate_content(
                model=self.sub_model_name,
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
                config=GenerateContentConfig(
                    safety_settings=get_safety_settings(),
                ),
            )
            return emoji.text.strip()
        else:
            return None

    async def reply(self, input_text, attachments=[]):
        if input_text.startswith("あ、これはりさじゅう反応しないでね"):
            pass
        elif input_text.endswith("リセット"):
            for file in self.client.files.list():
                self.client.files.delete(name=file.name)
            self.current_system_instruction = self.system_instruction
            self.chat = self.client.aio.chats.create(model=self.main_model_name)
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
                system_instruction=self.common_instruction + self.current_system_instruction,

                tools=[self.google_search_tool, self.url_context_tool],
                safety_settings=get_safety_settings(),
            )

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
