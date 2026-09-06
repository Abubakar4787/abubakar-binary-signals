import os
import requests
import pandas as pd

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]

CHAT_ID = 7353190184


def get_signal():
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": "EUR/USD",
        "interval": "1min",
        "outputsize": 100,
        "apikey": API_KEY
    }

    response = requests.get(url, params=params, timeout=20)
    data = response.json()

    if "values" not in data:
        return None

    df = pd.DataFrame(data["values"])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    latest = df.iloc[-1]

    up = 0
    down = 0

    # EMA trend
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

    return latest, up, down, signal


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "✅ Bot yana aiki lafiya!\n"
        "📊 Market analysis yana shirye."
    )


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = get_signal()

    if result is None:
        await update.message.reply_text(
            "❌ An kasa samun market data yanzu."
        )
        return

    latest, up, down, signal_text = result

    message = (
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "📊 Pair: EUR/USD\n"
        f"💰 Price: {latest['close']}\n"
        f"📈 RSI: {latest['RSI']:.2f}\n"
        f"🟢 UP Score: {up}/3\n"
        f"🔴 DOWN Score: {down}/3\n\n"
        f"🎯 SIGNAL: {signal_text}\n"
        "⏱️ Timeframe: 1 Minute\n\n"
        "⚠️ DEMO/TEST — ba garanti ba."
    )

    await update.message.reply_text(message)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", signal))

app.run_polling()
