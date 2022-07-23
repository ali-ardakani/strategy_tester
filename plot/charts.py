import pandas as pd
import numpy as np
# from strategy_tester import Strategy
from dash import Dash, dcc, html, Input, Output, dash_table
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import uuid
import io
# import makeresponse as mr
from flask import make_response


class Plot:

    def __init__(self, strategy, indicators: list = []):
        self.strategy = strategy
        self.trades = self.strategy.list_of_trades()
        self.indicators = indicators
        monthly_backtest = self.strategy.periodic_calc("1M")
        self.monthly_backtest = pd.DataFrame(monthly_backtest.values(),
                            index=monthly_backtest.keys())
        self.monthly_backtest.reset_index(inplace=True)
        self.monthly_backtest.rename(columns={"index": "Last trade of that month"},
                    inplace=True)
        self.data = self._validate_data(strategy.data)
        self._dash = Dash(self.__class__.__name__,
                          external_stylesheets=[dbc.themes.BOOTSTRAP])
        self._dash.layout = self._create_layout()
        self._dash.callback(
            Output("graph", "figure"),
            Output("date-slider", "value"),
            Output("tbl", "active_cell"),
            Output("trades-monthly", "children"),
            Input("tbl", "active_cell"),
            Input("date-slider", "value"),
            Input("trades-type", "value"),
            Input("trades-profitability", "value"),
            Input("logarithmic", "value"),
        )(self._set_chart)
        self._dash.callback(Output("tabs-content", "children"),
                            Input("tabs", "value"))(self._trades)
        self._dash.callback(Output("export-xlsx-download", "data"),
                            Input("export-xlsx", "n_clicks"))(self._export_excel)
        self._first_called = True
        self.previous_range = None
        self._dash.run_server(debug=True, host="0.0.0.0", port=8050)

    @staticmethod
    def _validate_data(data):
        if not isinstance(data, pd.DataFrame):
            raise TypeError("candles must be a pandas.DataFrame")

        required_columns = ['date', 'open', 'high', 'low', 'close']
        data.columns = data.columns.str.lower()
        wrong_columns = [
            column for column in required_columns
            if column not in data.columns.to_list()
        ]
        # Filter just the required columns
        data = data[required_columns]
        if wrong_columns:
            raise ValueError(
                "The data must have the columns: {}".format(wrong_columns))

        # Check type of the date and close_time
        if np.issubdtype(data["date"], np.datetime64):
            data["date"] = data["date"].astype(np.int64) / 10**6

        # Set the index to the datetime
        data.index = pd.to_datetime(data["date"], unit="ms")

        return data

    def _create_layout(self):
        """
        Create the layout of the Dash app
        
        Note:
            This method is called only if the Plot is created with dash=True
        """
        _min = int(self.data.date.min())
        _max = int(self.data.date.max())
        _last_month = _max - pd.Timedelta(days=30).total_seconds() * 1000
        _step = int((_max - _min) / 5)
        marks = {}
        for label in range(_min, _max, _step):
            marks[label] = str(
                pd.to_datetime(label, unit="ms")\
                    .round("1s").strftime("%Y-%m-%d"))
        layout = html.Div([
            html.H4('candlestick chart'),
            dcc.Checklist(
                id="logarithmic",
                options=[
                    {'label': 'Logarithmic', 'value': 'log'},
                ],
                value=[],
                labelStyle={'display': 'inline-block'}
            ),
            dcc.Graph(id="graph", style={"height": "calc(100vh - 200px)"}),
            dcc.RangeSlider(
                id='date-slider',
                min=_min,
                max=_max,
                value=[_last_month, _max],
                marks=marks,
            ),
            html.H6("Type of trades"),
            dcc.Dropdown(id="trades-type",
                         options=[
                             {
                                 "label": "All",
                                 "value": "all"
                             },
                             {
                                 "label": "Long",
                                 "value": "long"
                             },
                             {
                                 "label": "Short",
                                 "value": "short"
                             },
                         ],
                         value="all",
                         style={"width": "30%"}),
            html.H6("Profitability"),
            dcc.Dropdown(
                id="trades-profitability",
                options=[
                    {
                        "label": "All",
                        "value": "all"
                    },
                    {
                        "label": "Winning",
                        "value": "winning"
                    },
                    {
                        "label": "Losing",
                        "value": "losing"
                    },
                ],
                value="all",
                style={"width": "30%"},
            ),
            html.Br(),
            html.Button("Export to xlsx", id="export-xlsx"),
            html.Br(),
            dcc.Download(id="export-xlsx-download"),
            # Tab for list of trades and backtest results
            dcc.Tabs(id="tabs",
                     value="trades",
                     children=[
                         dcc.Tab(label="Trades", value="trades"),
                         dcc.Tab(label="Backtest result", value="backtest"),
                         dcc.Tab(label="Monthly backtest result",
                                 value="monthly"),
                     ]),
            html.Div(id="tabs-content",
                        ),
            html.Br(),
            html.Div(id="trades-monthly")
                 
        ])
        return layout

    def _set_chart(self, active_cell, range_date, trades_type,
                   trades_profitability, logarithmic):
        trade_monthly_html = None
        # Prepare the data
        if self._first_called:
            data = self.data.loc[self.data.index.max() -
                                 pd.Timedelta(days=30):]
            self._first_called = False
        elif active_cell and active_cell["column_id"] in self.trades.columns:
            trade = self.trades.iloc[active_cell["row"]]
            _step = self.data.index[1] - self.data.index[0]
            trade.exit_date = self.data.index[-1] if trade.isnull().exit_date else \
                trade.exit_date
            data = self.data[
                (self.data.index >= (trade.entry_date - 10 * _step))
                & (self.data.index <= (trade.exit_date + 10 * _step))]
        elif active_cell:
            date = self.monthly_backtest.iloc[active_cell["row"]]["Last trade of that month"]
            _step = self.data.index[1] - self.data.index[0]
            data = self.data[
                self.data.index.strftime("%Y-%m") == date.strftime("%Y-%m")]
            trade_monthly_html = dash_table.DataTable(
                id="trade",
                columns=[{"name": i, "id": i} for i in self.trades.columns],
                data=self.trades[self.trades.entry_date.isin(data.index)].to_dict("records"),
                style_cell={
                    "textAlign": "left",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "fontWeight": "normal"
                },
                style_header={
                    "fontWeight": "bold",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                },
                style_data_conditional=[{
                    "if": {
                        "row_index": "odd"
                    },
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                }],
                style_table={
                    "maxHeight": "300px",
                    "overflowY": "scroll"
                },
            )
        else:
            # Slice the data according to the slider value in date column
            data = self.data.loc[pd.Timestamp(range_date[0], unit="ms"):pd.
                                 Timestamp(range_date[1], unit="ms")]

        trades = pd.DataFrame(self.strategy.closed_positions +
                              self.strategy.open_positions)
        # Filter the trades according the data in the slider
        trades = trades[trades.entry_date.isin(data.date)]
        if not trades.empty:
            if trades_type != "all":
                trades = trades[trades["type"] == trades_type]
            if trades_profitability != "all":
                if trades_profitability == "winning":
                    trades = trades[trades["profit"] > 0]
                elif trades_profitability == "losing":
                    trades = trades[trades["profit"] < 0]
            if "log" in logarithmic:
                trades["entry_price"] = np.log10(trades["entry_price"])
                trades["exit_price"] = np.log10(trades["exit_price"])
            trades.entry_date = pd.to_datetime(trades.entry_date, unit="ms")
            trades.exit_date = pd.to_datetime(trades.exit_date, unit="ms")
            longs = trades[trades["type"] == "long"]
            shorts = trades[trades["type"] == "short"]

        if "log" in logarithmic:
            data[["open", "high", "low", "close"]] = np.log10( data[["open", "high", "low", "close"]])

        # Chart
        chart = go.Candlestick(x=data.index,
                               open=data.open,
                               high=data.high,
                               low=data.low,
                               close=data.close,
                               name="candlestick")

        layout = go.Layout(title="Candlestick Chart",
                           xaxis=dict(title="Time"),
                           yaxis=dict(
                               title="Price",
                               fixedrange=False,
                           ))

        charts = [chart]
        if not trades.empty:
            if not longs.empty:
                green_arrow = go.Scatter(
                    x=longs.entry_date,
                    y=longs.entry_price,
                    text=(longs.entry_signal.astype(str) + "  "),
                    textfont=dict(color="green"),
                    textposition="middle left",
                    mode="markers+text",
                    hoverinfo="text",
                    hovertext=(
                        "Entry date: " + longs.entry_date.astype(str) +
                        "<br>Entry price: " + longs.entry_price.astype(str) +
                        "<br>Entry signal: " + longs.entry_signal.astype(str) +
                        "<br>Exit date: " + longs.exit_date.astype(str) +
                        "<br>Exit price: " + longs.exit_price.astype(str) +
                        "<br>Comment: " + longs.comment.astype(str)),
                    marker=dict(symbol="arrow-bar-right",
                                color="green",
                                size=10),
                    name="Long Entry")
                charts.append(green_arrow)

            if not longs.exit_date.empty:
                gray_arrow_long = go.Scatter(
                    x=longs.exit_date,
                    y=longs.exit_price,
                    text=longs.entry_signal.astype(str),
                    textfont=dict(color="#1e572d"),
                    textposition="top center",
                    mode="markers+text",
                    hoverinfo="text",
                    hovertext=(
                        "Entry date: " + longs.entry_date.astype(str) +
                        "<br>Entry price: " + longs.entry_price.astype(str) +
                        "<br>Entry signal: " + longs.entry_signal.astype(str) +
                        "<br>Exit date: " + longs.exit_date.astype(str) +
                        "<br>Exit price: " + longs.exit_price.astype(str) +
                        "<br>Comment: " + longs.comment.astype(str)),
                    marker=dict(symbol="arrow-bar-left",
                                color="#1e572d",
                                size=10),
                    name="Long Exit")
                charts.append(gray_arrow_long)
            if not shorts.empty:
                red_arrow = go.Scatter(
                    x=shorts.entry_date,
                    y=shorts.entry_price,
                    text=(shorts.entry_signal.astype(str) + "  "),
                    textfont=dict(color="red"),
                    textposition="middle left",
                    mode="markers+text",
                    hoverinfo="text",
                    hovertext=(
                        "Entry date: " + shorts.entry_date.astype(str) +
                        "<br>Entry price: " + shorts.entry_price.astype(str) +
                        "<br>Entry signal: " +
                        shorts.entry_signal.astype(str) + "<br>Exit date: " +
                        shorts.exit_date.astype(str) + "<br>Exit price: " +
                        shorts.exit_price.astype(str) + "<br>Comment: " +
                        shorts.comment.astype(str)),
                    marker=dict(symbol="arrow-bar-right", color="red",
                                size=10),
                    name="Short Entry")
                charts.append(red_arrow)

            if not shorts.exit_date.empty:
                gray_arrow_short = go.Scatter(
                    x=shorts.exit_date,
                    y=shorts.exit_price,
                    text=shorts.entry_signal.astype(str),
                    textfont=dict(color="#7d0404"),
                    textposition="bottom center",
                    mode="markers+text",
                    hoverinfo="text",
                    hovertext=(
                        "Entry date: " + shorts.entry_date.astype(str) +
                        "<br>Entry price: " + shorts.entry_price.astype(str) +
                        "<br>Entry signal: " +
                        shorts.entry_signal.astype(str) + "<br>Exit date: " +
                        shorts.exit_date.astype(str) + "<br>Exit price: " +
                        shorts.exit_price.astype(str) + "<br>Comment: " +
                        shorts.comment.astype(str)),
                    marker=dict(symbol="arrow-bar-left",
                                color="#7d0404",
                                size=10),
                    name="Short Exit")
                charts.append(gray_arrow_short)

        for indicator in self.indicators:
            name = indicator["name"] if "name" in indicator else indicator[
                "value"].name
            # Check index is not datetime
            if not isinstance(indicator["value"].index, pd.DatetimeIndex):
                #     data.index = pd.to_datetime(indicator["value"].index, unit=)
                indicator["value"].index = pd.to_datetime(
                    indicator["value"].index, unit='ms')

            indicator_value = indicator["value"][indicator["value"].index.isin(
                data.index)]
            
            if "log" in logarithmic:
                indicator_value = np.log10(indicator_value)

            charts.append(
                go.Scatter(x=indicator_value.index,
                           y=indicator_value,
                           hoverinfo="text",
                           hovertext=("Value: " + indicator_value.astype(str)),
                           name=name,
                           marker=dict(color=indicator["color"])))
        fig = go.Figure(data=charts, layout=layout)

        # disable range slider
        fig.update_layout(
            xaxis=dict(rangeslider=dict(visible=False), type="date"))

        self.previous_range = range_date
        return fig, (data.date.iloc[0], data.date.iloc[-1]), None, trade_monthly_html

    def _trades(self, value):
        if value == "trades":
            trades = self.trades
            return dash_table.DataTable(
                id="tbl",
                columns=[{
                    "name": i,
                    "id": i
                } for i in trades.columns],
                data=trades.to_dict("records"),
                page_action='none',
                style_cell={
                    "textAlign": "left",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "fontWeight": "normal"
                },
                style_header={
                    "fontWeight": "bold",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                },
                style_data_conditional=[{
                    "if": {
                        "row_index": "odd"
                    },
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                }],
                style_table={
                    "overflowY": "scroll"
                },
            )
        elif value == "backtest":
            result = self.strategy.result()
            result = pd.DataFrame({"#": result.index, " ": result.values})
            # Table result series
            return dash_table.DataTable(
                id="tbl",
                columns=[{
                    "name": i,
                    "id": i
                } for i in result.columns],
                data=result.to_dict("records"),
                style_cell={
                    "textAlign": "left",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "fontWeight": "normal"
                },
                style_header={
                    "fontWeight": "bold",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                },
                style_data_conditional=[{
                    "if": {
                        "row_index": "odd"
                    },
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                }],
                style_table={
                    "overflowY": "scroll"
                },
            )
        elif value == "monthly":

            return dash_table.DataTable(
                id="tbl",
                columns=[{
                    "name": i,
                    "id": i
                } for i in self.monthly_backtest.columns],
                data=self.monthly_backtest.to_dict("records"),
                style_cell={
                    "textAlign": "left",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "fontWeight": "normal"
                },
                style_header={
                    "fontWeight": "bold",
                    "fontSize": "20px",
                    "fontFamily": "Arial",
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                },
                style_data_conditional=[{
                    "if": {
                        "row_index": "odd"
                    },
                    "backgroundColor": "#f1f6ff",
                    "color": "#135788"
                }],
                style_table={
                    "overflowY": "scroll"
                },
            )

    def _export_excel(self, n_clicks):
        """
        Export backtest, trades, monthly trades to seprate sheet
        """
        if n_clicks:
            # Create a Pandas Excel writer using XlsxWriter as the engine and save as buffer
            # Random name for the file and download
            buffer = io.BytesIO()
            writer = pd.ExcelWriter(buffer, engine='xlsxwriter')
            # Write backtest
            self.strategy.result().to_excel(writer, sheet_name='Backtest')
            # Write trades
            self.trades.to_excel(writer, sheet_name='Trades')
            # Write monthly trades
            self.monthly_backtest.to_excel(writer, sheet_name='Monthly trades')
            # Close the Pandas Excel writer and save the Excel sheet as buffer
            writer.save()
            # Get the value of the buffer
            excel_buffer = buffer.getvalue()
            # Reset the buffer to start
            buffer.seek(0)
            return dcc.send_bytes(src=excel_buffer, filename='backtest.xlsx')
            
