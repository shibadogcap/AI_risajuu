import asyncio
import os

import discord
from discord import Message
from pydantic import BaseModel

from .types import FileReply, MessageInfo, Reply, TextReply


# Discord用の設定項目
class DiscordConfig(BaseModel):
    token: str
    targets: list[tuple[str, str]]


# Discordのイベントを監視するメインのクラス
class DiscordClient(discord.Client):
    def __init__(self, config: DiscordConfig, message_queue: asyncio.Queue):
        # メッセージイベントを受信するための設定
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.config = config
        self.message_queue = message_queue

    async def on_ready(self):
        # Discordクライアントの準備が完了した
        print(f"We have logged in as {self.user}")

    async def on_message(self, message: Message):
        # メッセージが飛んできたら内部メッセージキューに追加
        # 送信者がボットなら無視
        if message.author.bot:
            return

        # DM判定
        is_dm = message.channel.type == discord.ChannelType.private
        # ターゲット判定
        is_target = (
            is_dm
            or (message.guild.name, message.channel.name) in self.config.targets
            or self.user.mentioned_in(message)
        )

        # ターゲットかだれでも見れるチャンネルならメッセージキューに追加
        if is_target or message.channel.permissions_for(message.channel.guild.default_role).view_channel:
            info = MessageInfo(message=message, is_dm=is_dm, is_target=is_target)
            await self.message_queue.put(info)

    async def send_message(self, destination, reply: Reply):
        # 種別を判定してメッセージを送信

        if isinstance(reply, TextReply):
            # Discordは一度に2,000文字まで送信できる
            # 余裕をもって1,500文字に制限
            for chunk in split_message_text(reply.message):
                await destination.send(chunk)
            return

        if isinstance(reply, FileReply):
            await destination.send(file=discord.File(reply.file_name, filename=os.path.basename(reply.file_name)))
            os.remove(reply.file_name)
            return

    async def add_reaction(self, origin_message: Message, reaction: str):
        # リアクションを付ける
        if reaction is not None:
            try:
                await origin_message.add_reaction(reaction)
            except TypeError:
                print(f"reaction error: <{reaction}>")


def split_message_text(text, chunk_size=1500):
    # 文字列をchunk_size文字ごとのリストにする
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
