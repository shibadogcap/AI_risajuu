from pydantic import BaseModel

# Event：Risajuuがloopで受け取る
# Action：Risajuuがmessage_routerに送る


# メッセージ情報
class MessageInfo(BaseModel):
    message: object
    is_dm: bool
    is_target: bool


class DiscordMessage(BaseModel):
    info: MessageInfo


# 外部イベントを実装したら種類が増える予定
type Event = DiscordMessage


class TextReply(BaseModel):
    message: str


class FileReply(BaseModel):
    file_name: str


# 返答メッセージの種類
type Reply = TextReply | FileReply


class PostMessage(BaseModel):
    channel: object
    content: Reply


class Reaction(BaseModel):
    origin_message: object
    emoji: str


type Action = PostMessage | Reaction
