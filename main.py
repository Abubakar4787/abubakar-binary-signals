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
        if 50 < latest["RSI"] < 70:
            up += 1
        elif 30 < latest["RSI"] < 50:
            down += 1

        # Candle
        if latest["close"] > latest["open"]:
            up += 1
        elif latest["close"] < latest["open"]:
            down += 1

        if up == 3:
            signal = "🟢 UP ⬆️"
        elif down == 3:
            signal = "🔴 DOWN ⬇️"
        else:
            signal = "⚪ NO SIGNAL"

        return {
            "pair": pair,
            "price": latest["close"],
            "rsi": latest["RSI"],
            "signal": signal,
            "candle_time": latest["datetime"]
        }, "open"

    except Exception as e:
        print(f"{pair} ERROR:", e)
        return None, "error"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = []

    row = []

    for pair in PAIRS:
        row.append(
            InlineKeyboardButton(
                pair,
                callback_data=f"pair:{pair}"
            )
        )

        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(
            "🔄 Refresh Pairs",
            callback_data="refresh"
        )
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "🔎 Zabi currency pair ɗin da kake son analysis:\n\n"
        "⏱️ Timeframe: 5 Minutes\n"
        "📊 Bot zai yi analysis na pair ɗin da ka zaɓa kawai.",
        reply_markup=reply_markup
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "refresh":

        await query.edit_message_text(
            "🤖 ABUBAKAR BINARY SIGNALS\n\n"
            "🔎 Zabi pair:"
        )

        keyboard = []
        row = []

        for pair in PAIRS:

            row.append(
                InlineKeyboardButton(
                    pair,
                    callback_data=f"pair:{pair}"
                )
            )

            if len(row) == 2:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton(
                "🔄 Refresh Pairs",
                callback_data="refresh"
            )
        ])

        await query.message.reply_text(
            "🔎 ZABI PAIR:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if query.data.startswith("pair:"):

        pair = query.data.split(":", 1)[1]

        await query.edit_message_text(
            f"⏳ Ana yin analysis na {pair}...\n\n"
            "⏱️ Timeframe: 5 Minutes"
        )

        result, status = get_analysis(pair)

        if status == "closed":

            await query.message.reply_text(
                "🔴 MARKET A RUFE\n\n"
                f"📊 Pair: {pair}\n\n"
                "Ba zan yi analysis ba yanzu.\n"
                "⏳ Jira market ya buɗe sannan ka sake zaɓar pair."
            )

            return

        if status == "error" or result is None:

            await query.message.reply_text(
                "❌ An samu matsala wajen samun market data.\n\n"
                f"📊 Pair: {pair}\n"
                "Ka sake gwadawa daga baya."
            )

            return

        await query.message.reply_text(
            "🤖 ABUBAKAR BINARY SIGNALS\n\n"
            f"📊 Pair: {result['pair']}\n"
            f"💰 Price: {result['price']}\n"
            f"📈 RSI: {result['rsi']:.2f}\n\n"
            f"🎯 MARKET: {result['signal']}\n"
            "⏱️ TIMEFRAME: 5 Minutes\n\n"
            "⚠️ DEMO/TEST — ba garanti ba."
        )


app = (
    Application.builder()
    .token(TOKEN)
    .build()
)

app.add_handler(
    CommandHandler("start", start)
)

app.add_handler(
    CommandHandler("signal", start)
)

app.add_handler(
    CallbackQueryHandler(button_handler)
)

print("🤖 ABUBAKAR BINARY SIGNALS BOT YA FARA")

app.run_polling()
