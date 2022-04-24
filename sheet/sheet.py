import gspread
from datetime import datetime as dt
from pandas._libs.tslibs.timestamps import Timestamp
from strategy_tester.encoder import NpEncoder
import json
import math

class Sheet:
    def __init__(self, strategy_name, service_account, email, scopes=gspread.auth.DEFAULT_SCOPES, worksheet_name=None):
        """Authenticate using a service account.
        
        Description
        -----------
        ``scopes`` parameter default to read/write scope available in 
        ``gspread.auth.DEFAULT_SCOPES``. It's read/write for Sheets
        and Drive API::

            DEFAULT_SCOPES =[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

        You can also use ``gspread.auth.READONLY_SCOPES`` for read only access.
        Obviously any method of ``gspread`` that updates a spreadsheet
        **will not work** in this case.

        :param str filename: The path to the service account json file.
        :param list scopes: The scopes used to obtain authorization.

        :rtype: :class:`gspread.Client`
        """
        self.service_account = service_account
        self.email = email
        self.client = gspread.service_account(filename=service_account, scopes=scopes)
        self.sheet = self._sheet(strategy_name)
        self.share_sheet(email)
        self.worksheet = self.add_worksheet(worksheet_name)
        self._init_columns_names()
        
        
    def _sheet(self, strategy_name:str) -> gspread.Spreadsheet:
        """Open the sheet if it's exists else create a new one.
        
        :param str strategy_name: The name of the strategy.
        :rtype: :class:`gspread.Spreadsheet`
        """
        try:
            sheet = self.client.open(strategy_name)
        except gspread.exceptions.SpreadsheetNotFound:
            sheet = self.client.create(strategy_name)
        
        return sheet
    
    def share_sheet(self, email:str) -> None:
        """Share a sheet with a user.

        :param str email: The email of the user to share the sheet with.

        :rtype: :None
        """
        self.sheet.share(email, perm_type="user", role="writer", notify=False)
    
    def add_worksheet(self, title:Timestamp=None) -> gspread.Worksheet:
        """Add a new worksheet to the sheet.

        :param str title: The title of the new worksheet.

        :rtype: :gsread.Worksheet
        """
        if not title:
            title = dt.now().strftime("%Y/%m/%d_%H-%M-%S")
        else:
            if isinstance(title, str):
                time_ = dt.now().strftime("%H-%M-%S")
                title = title+"_"+time_
            else:
                title = title.strftime("%Y/%m/%d_%H-%M-%S")
        try:
            worksheet = self.sheet.add_worksheet(title, 1, 1)
        except gspread.exceptions.APIError:
            worksheet = self.sheet.worksheet(title)
            worksheet.clear()
        return worksheet
    
    def _update_worksheet(self) -> None:
        """Update the worksheet.

        :rtype: :None
        """
        self.worksheet = self.sheet.worksheet(self.worksheet.title)
    
    def _init_columns_names(self) -> list:
        """Get the columns names from the sheet.
        
        :rtype: :list
        """
        names_of_columns = ['parameters', 'initial_capital', 'net_profit', 'net_profit_percent', 'gross_profit', 'gross_profit_percent', 'gross_loss', 'gross_loss_percent', 'max_draw_down', 'buy_and_hold_return', 'buy_and_hold_return_percent', 'profit_factor', 'max_contract_held', 'total_closed_trades', 'total_open_trades', 'number_wining_trades', 'number_losing_trades', 'percent_profitable', 'avg_trade', 'avg_trade_percent', 'avg_wining_trade', 'avg_wining_trade_percent', 'avg_losing_trade', 'avg_losing_trade_percent', 'largest_wining_trade', 'largest_wining_trade_percent', 'largest_lossing_trade', 'largest_lossing_trade_percent', 'ratio_avg_win_divide_avg_lose', 'avg_bars_in_trade', 'avg_bars_in_wining_trade', 'avg_bars_in_losing_trade']
        self.worksheet.append_row(names_of_columns)
        self._update_worksheet()
        self.columns = names_of_columns
        
    def add_columns_names(self, columns:list) -> None:#TODO: append columns names to the sheet this function is not working
        """Add the columns with their names.
        
        :param list columns: The list of columns names.
        :rtype: :None
        """
        # columns = [column.strftime("%Y/%m/%d_%H-%M-%S") for column in columns if isinstance(column, Timestamp)]
        # The list was used due to lack of order in the set(```set(columns+set(self.columns))```).
        # new_columns = self.columns + [column for column in columns if column not in self.columns]
        for column in columns:
            if isinstance(column, Timestamp):
                    column = column.strftime("%Y/%m/%d")
            if column not in self.columns:
                self.columns.append(column)
                
        list_cells = []
        for index, column in enumerate(self.columns):
            list_cells.append(gspread.Cell(1, index+1, column))
        self.worksheet.update_cells(list_cells)
        self._update_worksheet()
        # self.worksheet.add_cols(len(columns))
        # for index, name in enumerate(columns):
        #     thread = Thread(target=self.worksheet.update_cell, args=(1, index+1, name))
        #     thread.start()
        #     # self.worksheet.update_cell(1, index+2, name)
        # else:
        #     thread.join()
            
    def add_row(self, rows:list[list]) -> None:
        """Add one or more rows to the sheet.

        :param list rows: The list of the row(s) to add to the sheet.

        :rtype: :None
        """
        rows = self._serialize(rows)
        self.worksheet.append_rows(rows, value_input_option='USER_ENTERED')
        self._update_worksheet()
        
    @staticmethod
    def _serialize(objs:list) -> list:
        """Serialize the objects to a list of lists."""
        for index, row in enumerate(objs):
            row = ["nan" if not isinstance(x, str) and math.isnan(x) else x for x in list(row)]
            row = json.dumps(list(row), cls=NpEncoder)
            row = json.loads(row)
            objs[index] = row
        return objs
        