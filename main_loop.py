import traceback
from asyncio import CancelledError, Queue, TaskGroup
from enum import Enum

from pydantic import BaseModel

# LLMConfigは再公開のためだけにインポート
from lib.discord_client import DiscordClient, DiscordConfig, MessageInfo
from lib.risajuu import LLMConfig, Risajuu, RisajuuConfig
from lib.types import Action, DiscordMessage, PostMessage, Reaction


# 基本設定
class AppConfig(BaseModel):
    discord_config: DiscordConfig
    risajuu_config: RisajuuConfig


# りさじゅうインスタンス辞書のキーのための現在の場所の種類
class InstanceType(str, Enum):
    SERVER = "server"
    DM = "dm"


# りさじゅうインスタンス辞書のキー
class InstanceID(BaseModel):
    type: InstanceType
    id: int

    class Config:
        frozen = True


class MainLoop:
    def __init__(self, config: AppConfig):
        self.config = config
        self.message_queue = Queue()
        # りさじゅうインスタンス
        # いつか再起動時に復旧できるようになるかも
        self.risajuu_instances = {}
        # Discordクライアントの初期化
        self.client = DiscordClient(self.config.discord_config, self.message_queue)

    async def start(self):
        # メインループ
        try:
            async with TaskGroup() as tg:
                tg.create_task(self.client.start(self.config.discord_config.token))
                tg.create_task(self.discord_loop(tg))
                # りさじゅうインスタンスを起動時に復旧するなら下をアンコメントする
                # for risajuu_id in self.risajuu.instances.keys():
                #     tg.create_task(self.wait_risajuu(risajuu_id))
        except CancelledError:
            pass
        except BaseException as err:
            traceback.print_exc()
            print(f"Error: {err}")

    async def discord_loop(self, tg: TaskGroup):
        # Discordからのメッセージを待機するループ
        while True:
            info: MessageInfo = await self.message_queue.get()

            # DMならチャンネルid、そうでなければサーバーidを使用する
            instance_type = InstanceType.DM if info.is_dm else InstanceType.SERVER
            place_id = info.message.channel.id if info.is_dm else info.message.guild.id
            risajuu_id = InstanceID(type=instance_type, id=place_id)

            # サーバー・DMごとのりさじゅうインスタンスを指定
            if risajuu_id in self.risajuu_instances:
                risajuu = self.risajuu_instances[risajuu_id]
            else:
                # メッセージが送られてきた場所にりさじゅうのインスタンスがまだ無いときは作成する
                risajuu = Risajuu(tg, self.config.risajuu_config)
                self.risajuu_instances[risajuu_id] = risajuu
                # 並行処理用のタスクグループに登録
                tg.create_task(self.wait_risajuu(risajuu))
                tg.create_task(risajuu.boot())

            # メッセージがターゲットチャンネルに送られたとき入力中表示を出す
            if info.is_target:
                await info.message.channel.typing()

            # りさじゅうインスタンスにメッセージイベントを送信
            event = DiscordMessage(info=info)
            await risajuu.event_queue.put(event)

    async def wait_risajuu(self, risajuu: Risajuu):
        # りさじゅうの行動を待機するループ
        while True:
            action: Action = await risajuu.action_queue.get()

            if isinstance(action, PostMessage):
                # メッセージを送信する
                await self.client.send_message(action.channel, action.content)
                continue

            if isinstance(action, Reaction):
                # リアクションを付ける
                await self.client.add_reaction(action.origin_message, action.emoji)
                continue
