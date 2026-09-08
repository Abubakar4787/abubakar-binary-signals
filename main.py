import os
import requests
import pandas as pd

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

TOKEN = os.environ["BOT_TOKEN"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]

PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "EUR/JPY",
    "GBP/JPY"
]


def get_analysis(pair):
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": pair,
        "interval": "5min",
        "outputsize": 100,
        "apikey": API_KEY
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = response.json()

        if "values" not in data:
            print(f"{pair} ERROR:", data)
            return None, "closed"

        df = pd.DataFrame(data["values"])

        if df.empty:
            return None, "closed"

        df["datetime"] = pd.to_datetime(df["datetime"])

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col])

        df = df.sort_values("datetime").reset_index(drop=True)

        # EMA
        df["EMA20"] = df["close"].ewm(
            span=20,
            adjust=False
        ).mean()

        df["EMA50"] = df["close"].ewm(
            span=50,
            adjust=False
        ).mean()

        # RSI
        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss

        df["RSI"] = 100 - (
            100 / (1 + rs)
        )

        latest = df.iloc[-1]

        up = 0
        down = 0

        # Trend
        if latest["EMA20"] > latest["EMA50"]:
            up += 1
        elif latest["EMA20"] < latest["EMA50"]:
            down += 1

        # RSI
       
