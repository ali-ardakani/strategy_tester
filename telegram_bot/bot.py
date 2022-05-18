from telegram.ext.updater import Updater
from telegram import Bot

class Manager:
    def __init__(self, token: str, channel_id: int, use_context: bool = True):
        self.token = token
        self.use_context = use_context
        self.channel_id = channel_id
        self.updater = Updater(token=self.token, use_context=self.use_context)
        self.dispatcher = self.updater.dispatcher
        self.bot = Bot(token=self.token)

    def add_handler(self, handler):
        self.dispatcher.add_handler(handler)

    def start_polling(self):
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()

    def send_message_to_channel(self, text: str):
        if self.channel_id is not None:
            self.bot.send_message(chat_id=self.channel_id, text=text)

    