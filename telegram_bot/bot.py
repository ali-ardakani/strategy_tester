from concurrent.futures import thread
import io
import os

import pandas as pd
import pyotp
from qrcode import QRCode, constants
from strategy_tester import User
from telegram import Bot
from telegram.ext.callbackcontext import CallbackContext
from telegram.ext.commandhandler import CommandHandler, Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.vendor.ptb_urllib3.urllib3.exceptions import ConnectTimeoutError
from strategy_tester.commands import connect_on
from threading import Thread
import time


class Manager:

    _get_secret_code = False

    def __init__(self,
                 token: str,
                 channel_id: int,
                 user: User,
                 path_db: str,
                 use_context: bool = True,
                 licensed: list = None,
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
        self.user = user(telegram_bot=self, **kwargs)

        # Memory function
        self.memory_function = None

    def start_polling(self):
        self._handler()
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()

    def _check_connect_on(self, function:callable, **kwargs):
        while True:
            try:
                function(**kwargs)
                break
            except ConnectTimeoutError:
                time.sleep(10)

    def send_message_to_channel(self, text: str):
        if self.channel_id is None:
            raise ValueError("Channel ID is not set")

        thread = Thread(
            target=self._check_connect_on,
            kwargs={
                "function": self.bot.send_message,
                "chat_id": self.channel_id,
                "text": text
                })
        thread.start()

    def send_image_to_channel(self, img_bytes: bytes, caption: str):
        if self.channel_id is None:
            raise ValueError("Channel ID is not set")
        thread = Thread(
            target=self._check_connect_on,
            kwargs={
                "function": self.bot.send_photo,
                "chat_id": self.channel_id,
                "photo": img_bytes,
                "caption": caption
                })
        thread.start()

    def _send_message_to_bot(self, update: Update, context: CallbackContext,
                             text: str):
        """Send every message to the bot."""
        update.message.reply_text(text=text)

    def _handler(self):
        """Add command handler."""
        self.updater.dispatcher.add_handler(CommandHandler("help", self._help))
        self.updater.dispatcher.add_handler(
            CommandHandler("authorization", self.authorization))
        self.updater.dispatcher.add_handler(
            CommandHandler("start", self._start))
        self.updater.dispatcher.add_handler(
            CommandHandler("stop_entry_long", self._stop_enter_long))
        self.updater.dispatcher.add_handler(
            CommandHandler("start_entry_long", self._start_entry_long))
        self.updater.dispatcher.add_handler(
            CommandHandler("start_entry_short", self._start_entry_short))
        self.updater.dispatcher.add_handler(
            CommandHandler("stop_entry_short", self._stop_enter_short))
        self.updater.dispatcher.add_handler(
            CommandHandler("stop_not_close_position",
                           self._stop_not_close_position))
        self.updater.dispatcher.add_handler(
            CommandHandler("stop_close_position", self._stop_close_position))
        self.updater.dispatcher.add_handler(
            CommandHandler("stop_close_position_condition",
                           self._stop_close_position_with_close_condition))
        self.updater.dispatcher.add_handler(
            CommandHandler("status", self._status))
        self.updater.dispatcher.add_handler(
            CommandHandler("current_kline", self._current_kline))
        self.updater.dispatcher.add_handler(
            CommandHandler("secondary_asset", self._secondary_asset))
        self.updater.dispatcher.add_handler(
            CommandHandler("open_positions", self._open_positions))
        self.updater.dispatcher.add_handler(
            CommandHandler("close_positions", self._closed_positions))
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self._reply))

    def _help(self, update: Update, context: CallbackContext):
        """Help the user."""
        text = "/start - Start or Restart the user.\n"\
            "/authorization - Authorization the user.\n"\
            "/stop_entry_long - stop user enter long.\n"\
            "/stop_entry_short - stop user enter short.\n"\
            "/start_entry_long - start user enter long.\n"\
            "/start_entry_short - start user enter short.\n"\
            "/stop_not_close_position - Stop the user"\
            " and not close the position.\n"\
            "/stop_close_position - Stop the user and close the position.\n"\
            "/stop_close_position_with_close_condition -"\
            "Stop the user and close the position with close condition.\n"\
            "/status - Get the status of the user.\n"\
            f"/secondary_asset - Get the {self.user.secondary_pair} asset.\n"\
            "/open_positions - Get the open positions of the user.\n"\
            "/close_positions - Get the closed positions of the user.\n"\

        update.message.reply_text(text=text)

    def _start(self,
               update: Update,
               context: CallbackContext,
               permission_code: bool = False):
        """Start the user."""
        self._permission(update, context, self._start)

        if permission_code:
            self.user._exit = True
            self.user._entry = True
            self.user._permission_long = True
            self.user._permission_short = True
            self.user.run()
            msg = "Strategy is started!"\
                "\nStrategy have permission to enter long and short."\
                "If you want to prevent the strategy to enter long and short,"\
                "please use /stop_entry_long and /stop_entry_short."
            self.send_message_to_channel(msg)
            update.message.reply_text(text="User is running.")

    def _stop_enter_long(self,
                         update: Update,
                         context: CallbackContext,
                         permission_code: bool = False):
        """Stop the user enter long."""
        self._permission(update, context, self._stop_enter_long)
        if permission_code:
            self.user._permission_long = False
            update.message.reply_text(text="User is stop enter long.")
            msg = "User stop enter long."\
                " Strategy don't have permission to enter long position."
            self.send_message_to_channel(msg)

    def _stop_enter_short(self,
                          update: Update,
                          context: CallbackContext,
                          permission_code: bool = False):
        """Stop the user enter short."""
        self._permission(update, context, self._stop_enter_short)
        if permission_code:
            self.user._permission_short = False
            update.message.reply_text(text="User is stop enter short.")
            msg = "User stop enter short."\
                " Strategy don't have permission to enter short position."
            self.send_message_to_channel(msg)

    def _start_entry_long(self,
                          update: Update,
                          context: CallbackContext,
                          permission_code: bool = False):
        """Start the user enter long."""
        self._permission(update, context, self._start_entry_long)
        if permission_code:
            self.user._permission_long = True
            update.message.reply_text(text="User is start enter long.")
            msg = "User start enter long."\
                " Strategy have permission to enter long position."
            self.send_message_to_channel(msg)

    def _start_entry_short(self,
                           update: Update,
                           context: CallbackContext,
                           permission_code: bool = False):
        """Start the user enter short."""
        self._permission(update, context, self._start_entry_short)
        if permission_code:
            self.user._permission_short = True
            update.message.reply_text(text="User is start enter short.")
            msg = "User start enter short."\
                "Strategy have permission to enter short position."
            self.send_message_to_channel(msg)

    def _stop_not_close_position(self,
                                 update: Update,
                                 context: CallbackContext,
                                 permission_code: bool = False):
        """Stop the open positions and not close the position."""
        self._permission(update, context, self._stop_not_close_position)

        if permission_code:
            self._stop(update, context)
            open_positions = self.user.open_positions
            if open_positions:
                self.send_message_to_channel(
                    "Strategy is stopped! Opened positions: {}".format(
                        open_positions))
            else:
                self.send_message_to_channel(
                    "Strategy is stopped! No open positions.")
            update.message.reply_text(
                text="Command stop_not_close_position is executed.")

    def _stop_close_position(self,
                             update: Update,
                             context: CallbackContext,
                             permission_code: bool = False):
        """Stop the user and close the position."""
        self._permission(update, context, self._stop_close_position)

        if permission_code:
            self._stop(update, context)
            self.user.start_trade = True
            self.user._exit = True
            open_positions = self.user.open_positions
            self.user.close_positions()
            self.start_trade = False
            if open_positions != []:
                self.send_message_to_channel(
                    "Strategy is stopped! Close positions: {}".format(
                        open_positions))
            else:
                self.send_message_to_channel(
                    "Strategy is stopped! No open positions.")
            update.message.reply_text(
                text="Command stop_close_position is executed.")

    def _stop_close_position_with_close_condition(
            self,
            update: Update,
            context: CallbackContext,
            permission_code: bool = False):
        """Stop the user and close the position."""
        self._permission(update, context,
                         self._stop_close_position_with_close_condition)

        if permission_code:
            self.user._exit = True
            self.user._entry = False
            open_positions = self.user.open_positions
            if open_positions:
                msg = "Strategy is stopped! Open positions: {}\n"\
                        "Opened positions close "\
                        "when the close condition is satisfied."
                self.send_message_to_channel(msg.format(open_positions))
            else:
                self.send_message_to_channel(
                    "Strategy is stopped! No open positions.")
            msg = "Command stop_close_position_with_close_condition"\
                "is executed."
            update.message.reply_text(text=msg)

    def _status(self, update: Update, context: CallbackContext):
        """Check user status."""
        try:
            open_positions = self.user.open_positions
            usdt_asset = self.user.free_secondary
            text = f"User is running.\n"\
                f"Open positions: {open_positions}\n"\
                f"USDT asset: {usdt_asset}\n"\
                f"Permission to entry: {self.user._entry}\n"\
                f"Permission to exit: {self.user._exit}\n"\
                f"Permission to enter long: {self.user._permission_long}\n"\
                f"Permission to enter short: {self.user._permission_short}\n"\
                f"Leverage: {self.user.leverage}\n"\
                f"Margin Type: {self.user.margin_type}"
            update.message.reply_text(text=text)
        except Exception as e:
            text = "User is not running. "\
                "if you want to start the user, please type /start"
            update.message.reply_text(text=text)

    def _secondary_asset(self, update: Update, context: CallbackContext):
        """Get the secondary pair asset."""
        secondary_asset = self.user.free_secondary
        update.message.reply_text(text="User {} asset: {}".format(
            self.user.secondary_pair, secondary_asset))

    def _open_positions(self, update: Update, context: CallbackContext):
        """Get the open positions."""
        open_positions = self.user.open_positions
        if open_positions:
            update.message.reply_text(
                text="Open positions: {}".format(open_positions))
        else:
            update.message.reply_text(text="No open positions.")

    def _closed_positions(self, update: Update, context: CallbackContext):
        """Get the closed positions."""
        closed_positions = self.user._closed_positions
        if closed_positions:
            update.message.reply_text(
                text="Closed positions: {}".format(closed_positions))
        else:
            update.message.reply_text(text="No closed positions.")
            
    def _current_kline(self, update: Update, context: CallbackContext):
        """Get the current kline."""
        kline = self.user.current_kline
        if kline:
            update.message.reply_text(
                text="Current kline: {}".format(kline))
        else:
            update.message.reply_text(text="No current kline.")

    def _reply(self, update: Update, context: CallbackContext):
        """Reply to the message."""
        if self._get_secret_code and \
                update.message.from_user.id in self.licensed.id.values:
            secret_code = update.message.text
            secret_key = self._get_secret_key(update.message.from_user.id)
            if self._verify_code(secret_key, secret_code):
                permission_code = True
                self.memory_function(update, context, permission_code)
                self._get_secret_code = False
                text = "Secret code is correct and"\
                    f" {self.memory_function.__name__} is executed."
                update.message.reply_text(text=text)
                self._reset_attribute()
            else:
                update.message.reply_text(
                    text="Secret code is incorrect. please try again.")

        # if self._permission():
        #     user_input = update.message.text.split("/")
        #     if user_input[0] == "change_leverage":
        #         reply_text = self._change_leverage(user_input)

        #     update.message.reply_text(text=reply_text)

    def _change_leverage(self, user_input: list):
        """Change leverage."""
        if len(user_input) > 1:
            try:
                leverage = int(user_input[1])
            except ValueError:
                return "Leverage must be an integer."
            self.user.futures_change_leverage(symbol=self.user.symbol,
                                              leverage=leverage)
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
            text = "Please scan the QR code to authorize or"\
                f"use /authorize_by_secret_key/{secret_key}"
            update.message.reply_text(text=text)

    def _permission(self, update, context, func):
        """Check the permission."""
        if not self._get_secret_code:
            self.memory_function = func
            if update.message.chat_id in self.licensed.id.values:
                # For get secret code from user(in _reply function)
                self._get_secret_code = True

                # Check secret code of user in the database
                if self._get_secret_key(update.message.chat_id):
                    update.message.reply_text(
                        text="Please enter the secret code.")
                else:
                    text = "You are not authorized. "\
                        "Please contact the administrator."
                    update.message.reply_text(text=text)
            else:
                update.message.reply_text(text="You don't have permission.")

    def _two_factor_auth(self, update: Update, context: CallbackContext):
        """Check user's id and
        send secret code to user's email for two factor authentication."""
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
        df = pd.concat([df, pd.DataFrame([user])], axis=0, ignore_index=True)
        df.to_pickle(self.path_db)

    def _create_qr_code(self, user_id, secret_key):
        """ Create a QR code for the user """
        url = pyotp.totp.TOTP(secret_key).provisioning_uri(name=None,
                                                           issuer_name=None)
        qr = QRCode(version=1,
                    error_correction=constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4)

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
