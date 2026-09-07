import os
import asyncio
import requests
import pandas as pd

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]

CHAT_ID = 7353190184

last_sent_candle = None


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
        print("Market data error:", data)
        return None

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(df["datetime"])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    # A jera candles daga tsoho zuwa sabo
    df = df.sort_values("datetime").reset_index(drop=True)

    # EMA
    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    # RSI
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

    # EMA confirmation
    if latest["EMA20"] > latest["EMA50"]:
        up += 1
    elif latest["EMA20"] < latest["EMA50"]:
        down += 1

    # RSI confirmation
    if 50 < latest["RSI"] < 70:
        up += 1
    elif 30 < latest["RSI"] < 50:
        down += 1

    # Candle confirmation
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
        "📊 Automatic market analysis yana aiki."
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


async def automatic_analysis(app):

    global last_sent_candle

    print("🤖 AUTOMATIC ANALYSIS YA FARA")

    while True:

        try:

            result = get_signal()

            if result is not None:

                latest, up, down, signal_text = result

                candle_time = str(latest["datetime"])

                print(
                    f"EUR/USD | "
                    f"Price: {latest['close']} | "
                    f"UP: {up}/3 | "
                    f"DOWN: {down}/3 | "
                    f"{signal_text}"
                )

                # A aika signal idan 3/3 kawai
                if signal_text != "⚪ NO SIGNAL":

                    # Kada a sake aika signal na candle daya
                    if candle_time != last_sent_candle:

                        message = (
                            "🤖 ABUBAKAR BINARY SIGNALS\n\n"
                            "🚨 NEW SIGNAL\n\n"
                            "📊 Pair: EUR/USD\n"
                            f"💰 Price: {latest['close']}\n"
                            f"📈 RSI: {latest['RSI']:.2f}\n\n"
                            f"🎯 SIGNAL: {signal_text}\n"
                            "⏱️ Timeframe: 1 Minute\n\n"
                            "⚠️ DEMO/TEST — ba garanti ba."
                        )

                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=message
                        )

                        last_sent_candle = candle_time

                        print("📩 SIGNAL AN AIKA TELEGRAM ✅")

            else:
                print("❌ Babu market data.")

        except Exception as e:
            print("❌ ERROR:", e)

        # Jira sabon candle
        await asyncio.sleep(60)


async def post_init(app):
    asyncio.create_task(
        automatic_analysis(app)
    )


app = (
    Application.builder()
    .token(TOKEN)
    .post_init(post_init)
    .build()
)

app.add_handler(
    CommandHandler("start", start)
)

app.add_handler(
    CommandHandler("signal", signal)
)

app.run_polling()
