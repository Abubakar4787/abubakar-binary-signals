import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

REAL_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "EUR/JPY",
    "GBP/JPY",
]

OTC_PAIRS = [
    "EUR/USD OTC",
    "GBP/USD OTC",
    "USD/JPY OTC",
    "USD/CHF OTC",
    "AUD/USD OTC",
    "USD/CAD OTC",
    "EUR/JPY OTC",
    "GBP/JPY OTC",
]


# =========================
# MARKET STATUS
# =========================

def market_is_open():
    """
    Simple forex market-hours check.
    Uses Nigeria/Lagos time.
    """

    now = datetime.now(ZoneInfo("Africa/Lagos"))

    # Saturday and Sunday
    if now.weekday() >= 5:
        return False

    # Friday after 10pm Nigeria time
    if now.weekday() == 4 and now.hour >= 22:
        return False

    # Monday before 12am
    if now.weekday() == 0 and now.hour < 0:
        return False

    return True


# =========================
# MARKET ANALYSIS
# =========================

def get_analysis(pair, expiry):

    try:

        if not market_is_open():
            return {
                "status": "closed",
                "message": "Forex market a rufe yanzu."
            }

        # Remove OTC label
        if " OTC" in pair:
            return {
                "status": "error",
                "message": (
                    "OTC data source bai haɗu da bot ba tukuna. "
                    "Ba za mu yi amfani da real forex data mu kira shi OTC ba."
                )
            }

        # =========================
        # INTERVAL
        # =========================

        if expiry == 5:
            interval = "5min"
        else:
            interval = "1min"

        # =========================
        # TWELVE DATA
        # =========================

        url = "https://api.twelvedata.com/time_series"

        params = {
            "symbol": pair,
            "interval": interval,
            "outputsize": 100,
            "apikey": TWELVE_DATA_API_KEY,
        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = response.json()

        if "values" not in data:

            return {
                "status": "error",
                "message": str(
                    data.get(
                        "message",
                        "An samu matsala wajen samun market data."
                    )
                )
            }

        # =========================
        # DATAFRAME
        # =========================

        df = pd.DataFrame(data["values"])

        numeric_columns = [
            "open",
            "high",
            "low",
            "close"
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df = df.dropna()

        if len(df) < 50:
            return {
                "status": "error",
                "message": "Market data bai isa ba domin analysis."
            }

        df = df.sort_values("datetime")

        # =========================
        # EMA
        # =========================

        df["EMA20"] = (
            df["close"]
            .ewm(span=20, adjust=False)
            .mean()
        )

        df["EMA50"] = (
            df["close"]
            .ewm(span=50, adjust=False)
            .mean()
        )

        # =========================
        # RSI
        # =========================

        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        average_gain = gain.rolling(14).mean()
        average_loss = loss.rolling(14).mean()

        rs = average_gain / average_loss.replace(0, 0.000001)

        df["RSI"] = 100 - (
            100 / (1 + rs)
        )

        # =========================
        # LAST CANDLES
        # =========================

        last = df.iloc[-1]
        previous = df.iloc[-2]

        price = float(last["close"])
        ema20 = float(last["EMA20"])
        ema50 = float(last["EMA50"])
        rsi = float(last["RSI"])

        # =========================
        # SUPPORT / RESISTANCE
        # =========================

        recent = df.tail(20)

        support = float(recent["low"].min())
        resistance = float(recent["high"].max())

        # =========================
        # CONFIRMATIONS
        # =========================

        up_votes = 0
        down_votes = 0

        # 1. EMA trend
        if ema20 > ema50:
            up_votes += 1
        elif ema20 < ema50:
            down_votes += 1

        # 2. RSI
        if rsi > 50 and rsi < 70:
            up_votes += 1
        elif rsi < 50 and rsi > 30:
            down_votes += 1

        # 3. Candle direction
        if float(last["close"]) > float(last["open"]):
            up_votes += 1
        elif float(last["close"]) < float(last["open"]):
            down_votes += 1

        # 4. Momentum
        if float(last["close"]) > float(previous["close"]):
            up_votes += 1
        elif float(last["close"]) < float(previous["close"]):
            down_votes += 1

        # 5. Support / Resistance
        support_distance = abs(price - support) / price
        resistance_distance = abs(resistance - price) / price

        if support_distance <= 0.0015:
            up_votes += 1

        elif resistance_distance <= 0.0015:
            down_votes += 1

        # =========================
        # SIGNAL
        # =========================

        if up_votes >= 4 and up_votes > down_votes:
            signal = "UP ⬆️"

        elif down_votes >= 4 and down_votes > up_votes:
            signal = "DOWN ⬇️"

        else:
            signal = "NO SIGNAL ⚠️"

        # =========================
        # TREND
        # =========================

        if ema20 > ema50:
            trend = "BULLISH 🟢"

        elif ema20 < ema50:
            trend = "BEARISH 🔴"

        else:
            trend = "SIDEWAYS ⚪"

        # =========================
        # RESULT
        # =========================

        return {
            "status": "open",
            "pair": pair,
            "price": price,
            "ema20": ema20,
            "ema50": ema50,
            "rsi": rsi,
            "support": support,
            "resistance": resistance,
            "up_votes": up_votes,
            "down_votes": down_votes,
            "signal": signal,
            "trend": trend,
            "interval": interval,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "Bot ya haɗu lafiya! ✅\n\n"
        "Rubuta /signal domin samun market analysis."
    )


# =========================
# SIGNAL MENU
# =========================

async def signal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [
            InlineKeyboardButton(
                "🌍 REAL MARKET",
                callback_data="real_market"
            )
        ],
        [
            InlineKeyboardButton(
                "🟣 OTC MARKET",
                callback_data="otc_market"
            )
        ],
    ]

    await update.message.reply_text(
        "📊 ABUBAKAR BINARY SIGNALS\n\n"
        "Zaɓi market:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# PAIR BUTTONS
# =========================

def pair_keyboard(pairs, prefix):

    keyboard = []

    for i in range(0, len(pairs), 2):

        row = []

        for pair in pairs[i:i + 2]:

            row.append(
                InlineKeyboardButton(
                    pair,
                    callback_data=f"{prefix}|{pair}"
                )
            )

        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


# =========================
# EXPIRY BUTTONS
# =========================

def expiry_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "1 MINUTE",
                callback_data="expiry|1"
            ),
            InlineKeyboardButton(
                "2 MINUTES",
                callback_data="expiry|2"
            ),
        ],
        [
            InlineKeyboardButton(
                "3 MINUTES",
                callback_data="expiry|3"
            ),
            InlineKeyboardButton(
                "5 MINUTES",
                callback_data="expiry|5"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    # =========================
    # REAL MARKET
    # =========================

    if data == "real_market":

        await query.edit_message_text(
            "🌍 REAL MARKET\n\n"
            "Zaɓi currency pair:",
            reply_markup=pair_keyboard(
                REAL_PAIRS,
                "realpair"
            )
        )

        return

    # =========================
    # OTC MARKET
    # =========================

    if data == "otc_market":

        await query.edit_message_text(
            "🟣 OTC MARKET\n\n"
            "Zaɓi OTC pair:",
            reply_markup=pair_keyboard(
                OTC_PAIRS,
                "otcpair"
            )
        )

        return

    # =========================
    # REAL PAIR
    # =========================

    if data.startswith("realpair|"):

        pair = data.split("|", 1)[1]

        context.user_data["pair"] = pair
        context.user_data["market_type"] = "real"

        await query.edit_message_text(
            f"💱 PAIR: {pair}\n\n"
            "Zaɓi expiry:",
            reply_markup=expiry_keyboard()
        )

        return

    # =========================
    # OTC PAIR
    # =========================

    if data.startswith("otcpair|"):

        pair = data.split("|", 1)[1]

        context.user_data["pair"] = pair
        context.user_data["market_type"] = "otc"

        await query.edit_message_text(
            f"🟣 OTC PAIR: {pair}\n\n"
            "Zaɓi expiry:",
            reply_markup=expiry_keyboard()
        )

        return

    # =========================
    # EXPIRY
    # =========================

    if data.startswith("expiry|"):

        expiry = int(
            data.split("|", 1)[1]
        )

        pair = context.user_data.get("pair")

        if not pair:

            await query.edit_message_text(
                "❌ Ba a zaɓi pair ba.\n\n"
                "Rubuta /signal ka sake farawa."
            )

            return

        # =========================
        # ANALYSIS
        # =========================

        result = get_analysis(
            pair,
            expiry
        )

        # =========================
        # MARKET CLOSED
        # =========================

        if result["status"] == "closed":

            await query.edit_message_text(
                f"🔴 MARKET A RUFE\n\n"
                f"💱 Pair: {pair}\n\n"
                "Jira market ya buɗe kafin yin analysis.\n"
                "⚠️ Ba a bada signal idan market ya rufe."
            )

            return

        # =========================
        # API ERROR
        # =========================

        if result["status"] == "error":

            await query.edit_message_text(
                "❌ AN SAMU MATSALA\n\n"
                f"{result['message']}\n\n"
                "Ka sake gwadawa daga baya."
            )

            return

        # =========================
        # SIGNAL
        # =========================

        signal = result["signal"]

        entry_time = datetime.now(
            ZoneInfo("Africa/Lagos")
        ).strftime("%H:%M:%S")

        message = (
            "🤖 ABUBAKAR BINARY SIGNALS\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"💱 PAIR: {pair}\n"
            f"🕐 ENTRY: {entry_time} 🇳🇬\n"
            f"⏱️ EXPIRY: {expiry} MINUTE\n"
            f"📊 ANALYSIS: {result['interval']}\n\n"
            f"💰 PRICE: {result['price']:.5f}\n"
            f"📈 EMA20: {result['ema20']:.5f}\n"
            f"📉 EMA50: {result['ema50']:.5f}\n"
            f"📊 RSI: {result['rsi']:.2f}\n\n"
            f"⬆️ UP CONFIRMATION: {result['up_votes']}/5\n"
            f"⬇️ DOWN CONFIRMATION: {result['down_votes']}/5\n"
            f"📈 TREND: {result['trend']}\n"
            f"🟢 SUPPORT: {result['support']:.5f}\n"
            f"🔴 RESISTANCE: {result['resistance']:.5f}\n\n"
            f"🎯 SIGNAL: {signal}\n\n"
            "⚠️ Wannan analysis ne kawai, ba garantin win ba.\n"
            "Yi amfani da DEMO kafin real money."
        )

        await query.edit_message_text(
            message
        )


# =========================
# MAIN
# =========================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "signal",
            signal_command
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    print(
        "🤖 ABUBAKAR BINARY SIGNALS BOT IS RUNNING..."
    )

    app.run_polling()


# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
async def monitor_prices():
    asset = "EURUSD_otc"
    await client.start_realtime_price(asset, 60)  # Fara bin diddigin
    while True:
        prices = await client.get_realtime_price(asset)
        if prices:
            last_price = prices[-1]
            print(f"Lokaci: {last_price['time']} | Farashi: {last_price['price']}")
        await asyncio.sleep(1)  # Jira sakan ɗaya kafin ka sake dubawa
