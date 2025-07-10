import asyncio
import random
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from .llm_chat import LLMChat, LLMConfig
from .types import DiscordMessage, Event, FileReply, MessageInfo, PostMessage, Reaction, TextReply


class RisajuuConfig(BaseModel):
    llm_config: LLMConfig
    reaction_probability: float


class Risajuu:
    def __init__(self, tg: asyncio.TaskGroup, config: RisajuuConfig):
        self.tg = tg
        self.config = config
        self.llm_chat = LLMChat(config.llm_config)
        self.event_queue = asyncio.Queue()
        self.action_queue = asyncio.Queue()

    async def boot(self):
        # りさじゅうがイベントを待機するループ
        while True:
            event: Event = await self.event_queue.get()

            # Discordからのメッセージイベント
            if isinstance(event, DiscordMessage):
                info: MessageInfo = event.info
                self.tg.create_task(self.add_reaction(info))
                # ターゲットのメッセージのときだけ返答する
                if info.is_target:
                    self.tg.create_task(self.reply_to_message(info))
                continue

    async def add_reaction(self, info: MessageInfo):
        # 指定した確率でリアクションを付ける
        if random.random() < self.config.reaction_probability:
            reaction = await self.llm_chat.react(info.message.content)
            event = Reaction(
                origin_message=info.message,
                emoji=reaction,
            )
            await self.action_queue.put(event)

    async def reply_to_message(self, info: MessageInfo):
        # メッセージへの返答を生成してアクションキューに登録する
        message = info.message
        input = message.content
        chat = self.llm_chat

        if input.startswith("あ、これはりさじゅう反応しないでね"):
            return

        if input.startswith("カスタム\n"):
            custom_instruction = input.replace("カスタム\n", "")
            chat.set_custom_instruction(custom_instruction)
            text = "カスタム履歴を追加して新たなチャットで開始したじゅう！いつものりさじゅうに戻ってほしくなったら、「リセット」って言うじゅう！"
            reply = TextReply(message=text)
            action = PostMessage(channel=message.channel, content=reply)
            await self.action_queue.put(action)
            return

        if input.startswith("インポート"):
            if len(message.attachments) == 1 and message.attachments[0].filename.endswith(".json"):
                json_data = await message.attachments[0].read()
                json_str = json_data.decode("utf-8").replace("\n", "")
                chat.import_history(json_str)
                text = "履歴をインポートしたじゅう！"
            else:
                text = "インポートするには、1つのJSONファイルを添付してほしいじゅう！"
            reply = TextReply(message=text)
            action = PostMessage(channel=message.channel, content=reply)
            await self.action_queue.put(action)
            return

        if input.endswith("エクスポート"):
            text = "履歴をエクスポートするじゅう！"
            reply = TextReply(message=text)
            action = PostMessage(channel=message.channel, content=reply)
            await self.action_queue.put(action)

            json_str = chat.export_history()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"risajuu_history_{timestamp}_"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".json", prefix=prefix, mode="w", encoding="utf-8"
            ) as file:
                file.write(json_str)
                file.flush()
                # ファイルをDiscordに送信する
                reply = FileReply(file_name=file.name)
                action = PostMessage(channel=message.channel, content=reply)
                await self.action_queue.put(action)
            return

        if input.endswith("リセット"):
            chat.reset()
            text = "履歴をリセットしたじゅう！"
            reply = TextReply(message=text)
            action = PostMessage(channel=message.channel, content=reply)
            await self.action_queue.put(action)
            return

        timestamp = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()
        obj = {"timestamp": timestamp, "author": message.author.display_name, "body": input}

        async for text in chat.reply(obj, message.attachments):
            if not isinstance(text, str):
                text = f"Geminiライブラリのエラーじゅう：{text}"
            reply = TextReply(message=text)
            action = PostMessage(channel=message.channel, content=reply)
            await self.action_queue.put(action)
