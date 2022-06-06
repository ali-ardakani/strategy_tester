from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram import Bot
from telegram.ext.commandhandler import CommandHandler, Filters
from strategy_tester import User
from telegram.ext.messagehandler import MessageHandler
import pandas as pd
import pyotp
from qrcode import QRCode, constants
import io
import os
import pickle

class Manager:
    _get_secret_code = False
    def __init__(self, 
                 token: str, 
                 channel_id: int,
                 user: User,
                 path_db: str,
                 use_context: bool=True, 
                 licensed: list=None,  
                 **kwargs):
        # Set the config telegram bot
        self.token = token
        self.use_context = use_context
        self.channel_id = channel_id
        self.licensed = self._validate_licensed(licensed)
        # Initialize the database
        self.path_db = self._validate_database(path_db)
        self.updater = Updater(token=self.token, use_context=self.use_context)
        self.dispatcher = self.updater.dispatcher
        self.bot = Bot(token=self.token)
        
        # Set the user
        self.user = user(**kwargs)
        
        # Memory function
        self.memory_function = None
        

    def start_polling(self):
        self._handler()
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()

    def send_message_to_channel(self, text: str):
        if self.channel_id == None:
            raise ValueError("Channel ID is not set")
        self.bot.send_message(chat_id=self.channel_id, text=text)

    def _send_message_to_bot(self, update: Update, context: CallbackContext, text: str):
        """Send every message to the bot."""
        update.message.reply_text(text=text)

    def test_send(self):
        self.bot.send_message(chat_id="@aka1378", text="lsdjfslfjlsjl")

    def _handler(self):
        """Add command handler."""
        self.updater.dispatcher.add_handler(CommandHandler("help", self._help))
        self.updater.dispatcher.add_handler(CommandHandler("authorization", self.authorization))
        self.updater.dispatcher.add_handler(CommandHandler("start", self._start))
        self.updater.dispatcher.add_handler(CommandHandler("stop_not_close_position", self._stop_not_close_position))
        self.updater.dispatcher.add_handler(CommandHandler("stop_close_position", self._stop_close_position))
        self.updater.dispatcher.add_handler(CommandHandler("stop_close_position_condition", self._stop_close_position_with_close_condition))
        self.updater.dispatcher.add_handler(CommandHandler("status", self._status))
        self.updater.dispatcher.add_handler(CommandHandler("usdt_asset", self._usdt_asset))
        self.updater.dispatcher.add_handler(CommandHandler("open_positions", self._open_positions))
        self.updater.dispatcher.add_handler(CommandHandler("close_positions", self._closed_positions))
        self.updater.dispatcher.add_handler(MessageHandler(Filters.text, self._reply))
        
    def _help(self, update: Update, context: CallbackContext):
        """Help the user."""
        update.message.reply_text(text="""
        /start - Start the user.\n/authorization - Authorization the user.\n/stop_not_close_position - Stop the user and not close the position.\n/stop_close_position - Stop the user and close the position.\n/stop_close_position_with_close_condition - Stop the user and close the position with close condition.\n/status - Get the status of the user.\n/usdt_asset - Get the USDT asset.\n/open_positions - Get the open positions of the user.\n/close_positions - Get the closed positions of the user.\n
        """)
        
    def _start(self, update: Update, context: CallbackContext, permission_code: bool=False):
        """Start the user."""
        self._permission(update, context, self._start)
            
        if permission_code:
            self.user._exit = True
            self.user._entry = True
            self.user.run()
            self.send_message_to_channel("Strategy is started!")
            update.message.reply_text(text="User is running.")
        
        self._check_permission(update, context)
    
    def _stop_not_close_position(self, update: Update, context: CallbackContext,permission_code: bool=False):
        """Stop the open positions and not close the position."""
        self._permission(update, context, self._stop_not_close_position)
            
        if permission_code:
            self._stop(update, context)
            open_positions = self.user.open_positions
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Opened positions: {}".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
            update.message.reply_text(text="Command stop_not_close_position is executed.")
            
        self._check_permission(update, context)
    
    def _stop_close_position(self, update: Update, context: CallbackContext, permission_code: bool=False):
        """Stop the user and close the position."""
        self._permission(update, context, self._stop_close_position)
            
        if permission_code:
            self._stop(update, context)
            open_positions = self.user.open_positions
            self.user.close_positions()
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Close positions: {}".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
            update.message.reply_text(text="Command stop_close_position is executed.")
            
        self._check_permission(update, context)
        
    def _stop_close_position_with_close_condition(self, update: Update, context: CallbackContext, permission_code: bool=False):
        """Stop the user and close the position."""
        self._permission(update, context, self._stop_close_position_with_close_condition)
            
        if permission_code:
            self.user._exit = True
            self.user._entry = False
            open_positions = self.user.open_positions
            if open_positions:
                self.send_message_to_channel("Strategy is stopped! Open positions: {}\nOpened positions close when the close condition is satisfied.".format(open_positions))
            else:
                self.send_message_to_channel("Strategy is stopped! No open positions.")
                
            update.message.reply_text(text="Command stop_close_position_with_close_condition is executed.")
            
        self._check_permission(update, context)
        
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
            
    def _usdt_asset(self, update: Update, context: CallbackContext):
        """Get the USDT asset."""
        usdt_asset = self.user.free_usdt
        update.message.reply_text(text="User USDT asset: {}".format(usdt_asset))
        
    def _open_positions(self, update: Update, context: CallbackContext):
        """Get the open positions."""
        open_positions = self.user.open_positions
        if open_positions:
            update.message.reply_text(text="Open positions: {}".format(open_positions))
        else:
            update.message.reply_text(text="No open positions.")
            
    def _closed_positions(self, update: Update, context: CallbackContext):
        """Get the closed positions."""
        closed_positions = self.user._closed_positions
        if closed_positions:
            update.message.reply_text(text="Closed positions: {}".format(closed_positions))
        else:
            update.message.reply_text(text="No closed positions.")

    def _reply(self, update: Update, context: CallbackContext):
        """Reply to the message."""
        if self._get_secret_code and update.message.from_user.id in self.licensed.id.values:
            secret_code = update.message.text
            secret_key = self._get_secret_key(update.message.from_user.id)
            if self._verify_code(secret_key, secret_code):
                self._get_secret_code = False
                permission_code = True
                self.memory_function(update, context, permission_code)
                update.message.reply_text(text=f"Secret code is correct and {self.memory_function.__name__} is executed.")
                self._reset_attribute()
            else:
                update.message.reply_text(text="Secret code is incorrect. please try again.")
                
        # if self._permission():
        #     user_input = update.message.text.split("/")
        #     if user_input[0] == "change_leverage":
        #         reply_text = self._change_leverage(user_input)
            
        #     update.message.reply_text(text=reply_text)
        
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
        
    def authorization(self, update: Update, context: CallbackContext):
        """Authorization."""
        user_id = update.message.from_user.id
        if self._get_secret_key(user_id):
            update.message.reply_text(text="You are authorized.")
        else:
            secret_key = self._generate_secret_key()
            qr_code = self._create_qr_code(user_id, secret_key)
            self._store_to_database(user_id, secret_key)
            update.message.reply_photo(photo=qr_code)
            update.message.reply_text(text="Please scan the QR code to authorize or use /authorize_by_secret_key/{}".format(secret_key))
        
    def _permission(self, update, context, func):
        """Check the permission."""
        if not self._get_secret_code:
            self.memory_function = func
            if update.message.chat_id in self.licensed.id.values:
                self._get_secret_code = True # For get secret code from user(in _reply function)
                
                # Check secret code of user in the database
                if self._get_secret_key(update.message.chat_id):
                    update.message.reply_text(text="Please enter the secret code.")
                    
                else:
                    update.message.reply_text(text="You are not authorized. Please contact the administrator.")
            else:
                update.message.reply_text(text="You don't have permission.")
        else:
            update.message.reply_text(text="Please Enter the password.")
        
    def _two_factor_auth(self, update: Update, context: CallbackContext):
        """Check user's id and send secret code to user's email for two factor authentication."""
        if self._permission():
            pass
        
    def _reset_attribute(self):
        self._get_secret_code = False
        self.memory_function = None
        
    @staticmethod
    def _validate_licensed(licensed):
        """Validate the licensed ids and email."""
        licensed = pd.DataFrame(licensed)
        licensed_columns = licensed.columns
        requirement_columns = ["id", "email"]
        
        # Check columns of licensed in requirements
        if set(requirement_columns) <= set(licensed_columns):
            return licensed
        else:
            raise ValueError("The licensed file must have columns: id, email.")
        
    def _validate_database(self, path):
        """Validate the database"""
        if os.path.isfile(path):
            return path
        else:
            df = pd.DataFrame(columns=["username", "secret_key"])
            df.to_pickle(path)
            return path
        
    @staticmethod
    def _generate_secret_key():
        """Generate the secret key."""
        return pyotp.random_base32(64)

    def _get_secret_key(self, user_id: int):
        """Get the secret key from database."""
        df = pd.read_pickle(self.path_db)
        if user_id in df.username.values:
            return df.loc[df.username == user_id, "secret_key"].values[0]
        else:
            return None
    
    def _store_to_database(self, user_id, secret_key):
        """ Store the secret key to the database """
        df = pd.read_pickle(self.path_db)
        user = {"username": user_id, "secret_key": secret_key}
        df = pd.concat([df, pd.DataFrame(user)], axis=1, ignore_index=True)
        df.to_pickle(self.path_db)
        
    def _create_qr_code(self, user_id, secret_key):
        """ Create a QR code for the user """
        url = pyotp.totp.TOTP(secret_key).provisioning_uri(name=None, issuer_name=None)
        qr = QRCode(version=1, error_correction=constants.ERROR_CORRECT_L, box_size=10, border=4)
        
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        
        # Send image of qr code to bot
        img_byte = io.BytesIO()
        img.save(img_byte, format="PNG")
        img_byte.seek(0)
        return img_byte
    
    def _verify_code(self, secret_key, code):
        """ Verify the code """
        return pyotp.totp.TOTP(secret_key).verify(code)
    
    def _check_permission(self, update, context):
        """Check the permission of the user."""
        if self._get_secret_code:
            update.message.reply_text(text="Please enter the password.")