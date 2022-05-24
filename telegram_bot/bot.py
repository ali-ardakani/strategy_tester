from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram import Bot
from telegram.ext.commandhandler import CommandHandler

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
        if self.channel_id == None:
            raise ValueError("Channel ID is not set")
        self.bot.send_message(chat_id=self.channel_id, text=text)
    
    def bot_is_running(self, update: Update, context: CallbackContext):
        """Send message to the channel when the bot is running."""
        # TODO: add account info
        self._send_message_to_bot(update, context, "Bot is running")

    def _send_message_to_bot(self, update: Update, context: CallbackContext, text: str):
        """Send every message to the bot."""
        update.message.reply_text(text=text)

    def test_send(self):
        self.bot.send_message(chat_id="@aka1378", text="lsdjfslfjlsjl")

    def _handler(self):
        """Add command handler."""
        self.updater.dispatcher.add_handler(CommandHandler("bot_is_running", self.bot_is_running))

    