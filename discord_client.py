import datetime
import os
import tempfile

import discord

from ai_risajuu import ReplyType


class Risajuu_discord_client(discord.Client):
    def __init__(self, risajuu):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.risajuu = risajuu

    async def on_ready(self):
        print(f"We have logged in as {self.user}")

    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.permissions_for(message.channel.guild.default_role).view_channel:
            try:
                p = float(os.getenv("REACTION_PROBABILITY"))
                await message.add_reaction(await self.risajuu.react(message.content, p))
            except TypeError:
                pass

        if message.channel.name in os.getenv("TARGET_CHANNEL_NAME").split(",") or self.user.mentioned_in(message):
            await self.reply_to_message(message)

    async def reply_to_message(self, message):
        input_text = message.content

        if input_text.startswith("カスタム\n"):
            custom_instruction = input_text.replace("カスタム\n", "")
            self.risajuu.current_system_instruction = custom_instruction
            text = "カスタム履歴を追加して新たなチャットで開始したじゅう！いつものりさじゅうに戻ってほしくなったら、「リセット」って言うじゅう！"
            await message.channel.send(text)
            return

        if input_text.startswith("インポート"):
            if len(message.attachments) == 1 and message.attachments[0].filename.endswith(".json"):
                json_data = await message.attachments[0].read()
                json_str = json_data.decode("utf-8").replace("\n", "")
                self.risajuu.import_history(json_str)
                text = "履歴をインポートしたじゅう！"
            else:
                text = "インポートするには、1つのJSONファイルを添付してほしいじゅう！"
            await message.channel.send(text)
            return

        if input_text.endswith("エクスポート"):
            json_str = self.risajuu.export_history()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"risajuu_history_{timestamp}_"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".json", prefix=prefix, mode="w", encoding="utf-8"
            ) as file:
                file.write(json_str)
                file.flush()
                await message.channel.send(file=discord.File(file.name, filename=os.path.basename(file.name)))
            text = "履歴をエクスポートするじゅう！"
            await message.channel.send(text)
            return

        async for reply in self.risajuu.reply(message.content, message.attachments):
            async with message.channel.typing():
                body = reply.body
                match reply.type:
                    case ReplyType.text:
                        await message.channel.send(body)
                    case ReplyType.file:
                        await message.channel.send(file=discord.File(body, filename=os.path.basename(body)))
                        os.remove(body)
