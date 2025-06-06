import asyncio
import datetime
import os
import random
import tempfile
from enum import Enum

import discord
from pydantic import BaseModel

from ai_risajuu import AI_risajuu, ReplyType


# りさじゅうインスタンス辞書のキーのための現在の場所の種類
class InstanceType(str, Enum):
    server = "server"
    dm = "dm"


# りさじゅうインスタンス辞書のキー
class InstanceID(BaseModel):
    type: InstanceType
    id: int

    class Config:
        frozen = True


def split_message_text(text, chunk_size=1500):
    # 文字列をchunk_size文字ごとのリストにする
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


# Discordのイベントを監視するメインのクラス
class Risajuu_discord_client(discord.Client):
    def __init__(self, risajuu_config):
        # メッセージイベントのみ受信する設定
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.risajuu_config = risajuu_config
        self.risajuu_instance = {}
        self.targets = []
        for target in os.getenv("TARGET_CHANNEL_NAME").split(","):
            t = target.split("/")
            self.targets.append((t[0], t[1]))

    async def on_ready(self):
        # Discordクライアントの準備が完了した
        print(f"We have logged in as {self.user}")

    async def on_message(self, message):
        # メッセージが飛んできたとき呼ばれる関数

        # 送信者がボットなら無視
        if message.author.bot:
            return

        is_DM = message.channel.type == discord.ChannelType.private

        if is_DM:
            risajuu_id = InstanceID(type=InstanceType.dm, id=message.channel.id)
        else:
            risajuu_id = InstanceID(type=InstanceType.server, id=message.guild.id)

        # サーバー・DMごとのりさじゅうインスタンスを指定
        if risajuu_id in self.risajuu_instance:
            risajuu = self.risajuu_instance[risajuu_id]
        else:
            # メッセージが送られてきた場所にりさじゅうのインスタンスがまだ無いときは作成する
            risajuu = AI_risajuu(self.risajuu_config)
            self.risajuu_instance[risajuu_id] = risajuu

        # if message.content == "file_list":
        #     text = ""
        #     for file in risajuu.client.files.list():
        #         meta = risajuu.client.files.get(name=file.name)
        #         text += f"・{file.name}: {meta}\n"
        #     for t in split_message_text(text, chunk_size=2000):
        #         await message.channel.send(t)
        #     return

        # リアクション付与と返信は並行して実行
        async with asyncio.TaskGroup() as tasks:
            if is_DM or message.channel.permissions_for(message.channel.guild.default_role).view_channel:
                tasks.create_task(self.add_reaction(risajuu, message))

            if is_DM or (message.guild.name, message.channel.name) in self.targets or self.user.mentioned_in(message):
                tasks.create_task(self.reply_to_message(risajuu, message))

    async def add_reaction(self, risajuu, message):
        # 指定した確率でリアクションを付ける
        p = float(os.getenv("REACTION_PROBABILITY"))
        if random.random() < p:
            reaction = await risajuu.react(message.content)
            if reaction is not None:
                try:
                    await message.add_reaction(reaction)
                except TypeError:
                    pass

    async def reply_to_message(self, risajuu, message):
        # メッセージに返答する

        input_text = message.content

        if input_text.startswith("カスタム\n"):
            custom_instruction = input_text.replace("カスタム\n", "")
            risajuu.set_custom_instruction(custom_instruction)
            text = "カスタム履歴を追加して新たなチャットで開始したじゅう！いつものりさじゅうに戻ってほしくなったら、「リセット」って言うじゅう！"
            await message.channel.send(text)
            return

        if input_text.startswith("インポート"):
            if len(message.attachments) == 1 and message.attachments[0].filename.endswith(".json"):
                json_data = await message.attachments[0].read()
                json_str = json_data.decode("utf-8").replace("\n", "")
                risajuu.import_history(json_str)
                text = "履歴をインポートしたじゅう！"
            else:
                text = "インポートするには、1つのJSONファイルを添付してほしいじゅう！"
            await message.channel.send(text)
            return

        if input_text.endswith("エクスポート"):
            text = "履歴をエクスポートするじゅう！"
            await message.channel.send(text)
            json_str = risajuu.export_history()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"risajuu_history_{timestamp}_"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".json", prefix=prefix, mode="w", encoding="utf-8"
            ) as file:
                file.write(json_str)
                file.flush()
                await message.channel.send(file=discord.File(file.name, filename=os.path.basename(file.name)))
            return

        # 生成された回答を順次送信する
        # 入力中表示のために１回分先に生成する
        gen = risajuu.reply(message.content, message.attachments)
        try:
            buffer = await gen.__anext__()
        except StopAsyncIteration:
            pass
        else:
            await message.channel.typing()
            async for reply in gen:
                await self.send_message(message.channel, buffer)
                await message.channel.typing()
                buffer = reply
            await self.send_message(message.channel, buffer)

    async def send_message(self, channel, reply):
        body = reply.body
        match reply.type:
            case ReplyType.text:
                # Discordは一度に2,000文字まで送信できる
                # 余裕をもって1,500文字に制限
                for chunk in split_message_text(body):
                    await channel.send(chunk)
            case ReplyType.file:
                await channel.send(file=discord.File(body, filename=os.path.basename(body)))
                os.remove(body)
