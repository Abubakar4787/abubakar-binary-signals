import os
import asyncio
import requests
import pandas as pd

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]

CHAT_ID = 7353190184

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

last_results = {}


def get_market_data(pair):
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": pair,
        "interval": "5min",
        "outputsize": 100,
        "apikey": API_KEY
    }

    response = requests.get(url, params=params, timeout=20)
    data = response.json()

    if "values" not in data:
        print(f"{pair} ERROR:", data)
        return None

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(df["datetime"])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

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
        "up": up,
        "down": down,
        "signal": signal,
        "candle_time": str(latest["datetime"])
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "✅ Bot yana aiki lafiya!\n"
        "🔎 Ana binciken currency pairs da yawa.\n"
        "⏱️ Timeframe: 5 Minutes\n\n"
        "⚠️ DEMO/TEST — ba garanti ba."
    )


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not last_results:
        await update.message.reply_text(
            "⏳ Har yanzu ana tattara market data. "
            "Sake gwadawa bayan ɗan lokaci."
        )
        return

    strong_signals = [
        r for r in last_results.values()
        if r["signal"] != "⚪ NO SIGNAL"
    ]

    if not strong_signals:
        await update.message.reply_text(
            "⚪ BABU STRONG SIGNAL YANZU\n\n"
            "⏱️ Timeframe: 5 Minutes\n"
            "Ka jira sabon market analysis."
        )
        return

    message = "🤖 ABUBAKAR BINARY SIGNALS\n\n"
    message += "🚨 STRONG SIGNALS\n\n"

    for r in strong_signals:
        message += (
            f"📊 Pair: {r['pair']}\n"
            f"💰 Price: {r['price']}\n"
            f"📈 RSI: {r['rsi']:.2f}\n"
            f"🎯 SIGNAL: {r['signal']}\n"
            "⏱️ Expiry/Timeframe: 5 Minutes\n"
            "━━━━━━━━━━━━━━\n"
        )

    message += "\n⚠️ DEMO/TEST — ba garanti ba."

    await update.message.reply_text(message)


async def automatic_analysis(app):
    global last_results

    print("🤖 AUTOMATIC 5-MINUTE ANALYSIS YA FARA")

    while True:

        for pair in PAIRS:

            try:
                result = get_market_data(pair)

                if result is not None:

                    last_results[pair] = result

                    print(
                        f"{pair} | "
                        f"Price: {result['price']} | "
                        f"UP: {result['up']}/3 | "
                        f"DOWN: {result['down']}/3 | "
                        f"{result['signal']}"
                    )

                    if result["signal"] != "⚪ NO SIGNAL":

                        message = (
                            "🤖 ABUBAKAR BINARY SIGNALS\n\n"
                            "🚨 NEW 5-MINUTE SIGNAL\n\n"
                            f"📊 Pair: {result['pair']}\n"
                            f"💰 Price: {result['price']}\n"
                            f"📈 RSI: {result['rsi']:.2f}\n"
                            f"🟢 UP Score: {result['up']}/3\n"
                            f"🔴 DOWN Score: {result['down']}/3\n\n"
                            f"🎯 SIGNAL: {result['signal']}\n"
                            "⏱️ Timeframe: 5 Minutes\n\n"
                            "⚠️ DEMO/TEST —  garanti ."
                        )

                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=message
                        )

                        print(
                            f"📩 {pair} SIGNAL AN AIKA TELEGRAM ✅"
                        )

            except Exception as e:
                print(f"❌ {pair} ERROR:", e)

        # Jira sabon analysis bayan minti 5
        await asyncio.sleep(300)


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
