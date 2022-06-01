from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram import Bot
from telegram.ext.commandhandler import CommandHandler, Filters
from strategy_tester.user import User
from telegram.ext.messagehandler import MessageHandler

class Manager:
    def __init__(self, token: str, channel_id: int, use_context: bool = True, user: User = None, **kwargs):
        # Set the config telegram bot
        self.token = token
        self.use_context = use_context
        self.channel_id = channel_id
        self.updater = Updater(token=self.token, use_context=self.use_context)
        self.dispatcher = self.updater.dispatcher
        self.bot = Bot(token=self.token)
        
        # Set the user
        self.user = User(**kwargs)
        
    

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
        self.updater.dispatcher.add_handler(CommandHandler("start", self._start))
        self.updater.dispatcher.add_handler(CommandHandler("bot_is_running", self.bot_is_running))
        self.updater.dispatcher.add_handler(MessageHandler(Filters.text, self._reply))
        
    def _start(self, update: Update, context: CallbackContext):
        """Start the user."""
        self.user.run()
        self.send_message_to_channel("Strategy is started!")
        update.message.reply_text(text="User is running.")
        
    def _reply(self, update: Update, context: CallbackContext):
        """Reply to the message."""
        user_input = update.message.text.split("/")
        if user_input[0] == "change_leverage":
            reply_text = self._change_leverage(user_input)
        
        update.message.reply_text(text=reply_text)
        
    def _change_leverage(self, user_input:list):
        """Change leverage."""
        if len(user_input) > 1:
            try:
                leverage = int(user_input[1])
            except ValueError:
                return "Leverage must be an integer."
            self.user.futures_change_leverage(symbol=self.user.symbol, leverage=leverage)
            return "Leverage changed to {}.".format(leverage)
        else:
            return "Please specify the leverage e.g. change_leverage/10"

    