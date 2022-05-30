from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram import Bot
from telegram.ext.commandhandler import CommandHandler, Filters
from strategy_tester import User
from telegram.ext.messagehandler import MessageHandler

class Manager:
    def __init__(self, token: str, channel_id: int, use_context: bool = True, licensed_ids: list = None, **kwargs):
        # Set the config telegram bot
        self.token = token
        self.use_context = use_context
        self.channel_id = channel_id
        self.licensed_ids = licensed_ids
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
    
    def _status(self, update: Update, context: CallbackContext):
        """Check user status."""
        try:
            open_positions = self.user.open_positions
            usdt_asset = self.user.free_usdt
            if open_positions:
                update.message.reply_text(text="User is running.\nUSDT: {}\nOpen Positions: {}".format(usdt_asset, open_positions))
            else:
                update.message.reply_text(text="User is running.\nUSDT: {}\nNo open positions.".format(usdt_asset))
        except:
            update.message.reply_text(text="User is not running. if you want to start the user, please type /start")

    def _send_message_to_bot(self, update: Update, context: CallbackContext, text: str):
        """Send every message to the bot."""
        update.message.reply_text(text=text)

    def test_send(self):
        self.bot.send_message(chat_id="@aka1378", text="lsdjfslfjlsjl")

    def _handler(self):
        """Add command handler."""
        self.updater.dispatcher.add_handler(CommandHandler("start", self._start))
        self.updater.dispatcher.add_handler(CommandHandler("stop_not_close_position", self._stop_not_close_position))
        self.updater.dispatcher.add_handler(CommandHandler("stop_close_position", self._stop_close_position))
        self.updater.dispatcher.add_handler(CommandHandler("stop_close_position_with_close_condition", self._stop_close_position_with_close_condition))
        self.updater.dispatcher.add_handler(CommandHandler("status", self._status))
        self.updater.dispatcher.add_handler(CommandHandler("usdt_asset", self._usdt_asset))
        self.updater.dispatcher.add_handler(CommandHandler("open_positions", self._open_positions))
        self.updater.dispatcher.add_handler(CommandHandler("close_positions", self._closed_positions))
        self.updater.dispatcher.add_handler(MessageHandler(Filters.text, self._reply))
        
    def _start(self, update: Update, context: CallbackContext):
        """Start the user."""
        if self._permission():
            self.user._exit = True
            self.user._entry = True
            self.user.run()
            self.send_message_to_channel("Strategy is started!")
            update.message.reply_text(text="User is running.")
    
    def _stop_not_close_position(self, update: Update, context: CallbackContext):
        """Stop the open positions and not close the position."""
        if self._permission():
            self._stop()
            open_positions = self.user.open_positions
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Opened positions: {}".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
            update.message.reply_text(text="Command stop_not_close_position is executed.")
    
    def _stop_close_position(self, update: Update, context: CallbackContext):
        """Stop the user and close the position."""
        if self._permission():
            self._stop()
            open_positions = self.user.open_positions
            self.user.close_positions()
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Close positions: {}".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
            update.message.reply_text(text="Command stop_close_position is executed.")
        
    def _stop_close_position_with_close_condition(self, update: Update, context: CallbackContext):
        """Stop the user and close the position."""
        if self._permission():
            self.user._exit = True
            self.user._entry = False
            open_positions = self.user.open_positions
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Open positions: {}\nOpened positions close when the close condition is satisfied.".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
                
            update.message.reply_text(text="Command stop_close_position_with_close_condition is executed.")
        
    def _usdt_asset(self, update: Update, context: CallbackContext):
        """Get the USDT asset."""
        if self._permission():
            usdt_asset = self.user.free_usdt
            update.message.reply_text(text="User USDT asset: {}".format(usdt_asset))
        
    def _open_positions(self, update: Update, context: CallbackContext):
        """Get the open positions."""
        if self._permission():
            open_positions = self.user.open_positions
            if open_positions:
                update.message.reply_text(text="Open positions: {}".format(open_positions))
            else:
                update.message.reply_text(text="No open positions.")
            
    def _closed_positions(self, update: Update, context: CallbackContext):
        """Get the closed positions."""
        if self._permission():
            closed_positions = self.user.closed_positions
            if closed_positions:
                update.message.reply_text(text="Closed positions: {}".format(closed_positions))
            else:
                update.message.reply_text(text="No closed positions.")

    def _reply(self, update: Update, context: CallbackContext):
        """Reply to the message."""
        if self._permission():
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
        
    def _stop(self, update: Update, context: CallbackContext):
        """Stop the user."""       
        self.user._exit = False
        self.user._entry = False
        
    def _permission(self, update: Update, context: CallbackContext):
        """Check the permission."""
        if update.message.chat_id in self.licensed_ids:
            return True
        else:
            update.message.reply_text(text="You don't have permission.")
            return False
        
    

    