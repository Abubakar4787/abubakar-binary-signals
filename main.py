import os
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

# =========================
# REAL MARKET PAIRS
# =========================

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

# =========================
# OTC PAIRS
# NOTE:
# Twelve Data ba OTC data ba ne.
# Wadannan suna matsayin menu kawai.
# =========================

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

# User selections
user_pair = {}
user_expiry = {}


# =========================
# MARKET DATA
# =========================

def get_analysis(pair, expiry):

    # OTC ba za mu yi amfani da Twelve Data mu kira shi OTC ba
    if "OTC" in pair:
        return {
            "status": "otc_unavailable"
        }

    # Analysis interval
    if expiry == 5:
        interval = "5min"
    else:
        interval = "1min"

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": pair,
        "interval": interval,
        "outputsize": 100,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        data = response.json()

        # API error
        if "code" in data and data.get("code") != 200:
            return {
                "status": "error",
                "message": data.get(
                    "message",
                    "Unknown API error"
                )
            }

        if "values" not in data:
            return {
                "status": "closed"
            }

        df = pd.DataFrame(data["values"])

        if df.empty:
            return {
                "status": "closed"
            }

        # Convert numbers
        for column in ["open", "high", "low", "close"]:
            df[column] = pd.to_numeric(df[column])

        df = df.sort_values(
            "datetime"
        ).reset_index(drop=True)

        if len(df) < 60:
            return {
                "status": "error",
                "message": "Ba a samu isasshen market data ba."
            }

        # =========================
        # EMA TREND
        # =========================

        df["EMA20"] = df["close"].ewm(
            span=20,
            adjust=False
        ).mean()

        df["EMA50"] = df["close"].ewm(
            span=50,
            adjust=False
        ).mean()

        # =========================
        # RSI 14
        # =========================

        delta = df["close"].diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            0.000001
        )

        df["RSI"] = 100 - (
            100 / (1 + rs)
        )

        # =========================
        # SUPPORT / RESISTANCE
        # =========================

        recent = df.tail(20)

        support = float(
            recent["low"].min()
        )

        resistance = float(
            recent["high"].max()
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

        open_price = float(last["open"])
        close_price = float(last["close"])

        # Candle direction
        candle_up = close_price > open_price
        candle_down = close_price < open_price

        # Previous candle comparison
        momentum_up = close_price > float(
            previous["close"]
        )

        momentum_down = close_price < float(
            previous["close"]
        )

        # =========================
        # SUPPORT / RESISTANCE ZONE
        # =========================

        distance_support = abs(
            price - support
        ) / price

        distance_resistance = abs(
            resistance - price
        ) / price

        near_support = distance_support <= 0.0015
        near_resistance = distance_resistance <= 0.0015

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
        if rsi >= 50:
            up_votes += 1
        elif rsi < 50:
            down_votes += 1

        # 3. Candle
        if candle_up:
            up_votes += 1
        elif candle_down:
            down_votes += 1

        # 4. Momentum
        if momentum_up:
            up_votes += 1
        elif momentum_down:
            down_votes += 1

        # 5. Support / Resistance
        if near_support and candle_up:
            up_votes += 1

        if near_resistance and candle_down:
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
        # TREND LABEL
        # =========================

        if ema20 > ema50:
            trend = "BULLISH 📈"

        elif ema20 < ema50:
            trend = "BEARISH 📉"

        else:
            trend = "SIDEWAYS ➡️"

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "💱 REAL MARKET",
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
        "🤖 ABUBAKAR BINARY SIGNALS\n\n"
        "Zaɓi market ɗin da kake so:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# SIGNAL COMMAND
# =========================

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "💱 REAL MARKET",
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
        "📊 SIGNAL MENU\n\n"
        "Zaɓi market:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # =========================
    # REAL MARKET
    # =========================

    if data == "real_market":

        buttons = []

        for i in range(0, len(REAL_PAIRS), 2):

            row = []

            row.append(
                InlineKeyboardButton(
                    REAL_PAIRS[i],
                    callback_data=f"pair:{REAL_PAIRS[i]}"
                )
            )

            if i + 1 < len(REAL_PAIRS):
                row.append(
                    InlineKeyboardButton(
                        REAL_PAIRS[i + 1],
                        callback_data=f"pair:{REAL_PAIRS[i + 1]}"
                    )
                )

            buttons.append(row)

        await query.edit_message_text(
            "💱 REAL MARKET\n\n"
            "Zaɓi pair:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        return

    # =========================
    # OTC MARKET
    # =========================

    if data == "otc_market":

        buttons = []

        for i in range(0, len(OTC_PAIRS), 2):

            row = []

            row.append(
                InlineKeyboardButton(
                    OTC_PAIRS[i],
                    callback_data=f"otc:{OTC_PAIRS[i]}"
                )
            )

            if i + 1 < len(OTC_PAIRS):
                row.append(
                    InlineKeyboardButton(
                        OTC_PAIRS[i + 1],
                        callback_data=f"otc:{OTC_PAIRS[i + 1]}"
                    )
                )

            buttons.append(row)

        await query.edit_message_text(
            "🟣 OTC MARKET\n\n"
            "Zaɓi OTC pair:\n\n"
            "⚠️ OTC analysis bai kunna ba tukuna saboda "
            "Twelve Data ba ya samar da ainihin Quotex/Pocket Option OTC data.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        return

    # =========================
    # OTC PAIR
    # =========================

    if data.startswith("otc:"):

        pair = data.replace("otc:", "", 1)

        await query.edit_message_text(
            f"🟣 {pair}\n\n"
            "⚠️ OTC DATA SOURCE BA A HAƊA BA.\n\n"
            "Ba zan yi amfani da Real Market data in kira shi OTC ba.\n"
            "Da zarar an haɗa ainihin OTC data source, za mu kunna analysis."
        )

        return

    # =========================
    # PAIR SELECTED
    # =========================

    if data.startswith("pair:"):

        pair = data.replace("pair:", "", 1)

        user_pair[query.from_user.id] = pair

        keyboard = [
            [
                InlineKeyboardButton(
                    "1 MINUTE",
                    callback_data="expiry:1"
                ),
                InlineKeyboardButton(
                    "2 MINUTES",
                    callback_data="expiry:2"
                ),
            ],
            [
                InlineKeyboardButton(
                    "3 MINUTES",
                    callback_data="expiry:3"
                ),
                InlineKeyboardButton(
                    "5 MINUTES",
                    callback_data="expiry:5"
                ),
            ],
        ]

        await query.edit_message_text(
            f"💱 PAIR: {pair}\n\n"
            "⏱️ Zaɓi trade expiry:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # =========================
    # EXPIRY SELECTED
    # =========================

    if data.startswith("expiry:"):

        expiry = int(data.replace("expiry:", "", 1))

        user_id = query.from_user.id

        pair = user_pair.get(user_id)

        if not pair:

            await query.edit_message_text(
                "⚠️ Ba a zaɓi pair ba.\n"
                "Ka sake amfani da /signal."
            )

            return

        user_expiry[user_id] = expiry

        # Current Nigeria time
        now = datetime.now(
            ZoneInfo("Africa/Lagos")
        )

        entry_time = now.strftime("%H:%M:%S")

        await query.edit_message_text(
            f"🔎 ANA YIN ANALYSIS...\n\n"
            f"💱 Pair: {pair}\n"
            f"⏱️ Expiry: {expiry} minute\n"
            f"🕐 Entry Time: {entry_time} 🇳🇬"
        )

        result = get_analysis(pair, expiry)

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
            f"⬆️ UP CONFIRMATION: {result['up_votes']}/3\n"
            f"⬇️ DOWN CONFIRMATION: {result['down_votes']}/3\n\n"
            f"🎯 SIGNAL: {signal}\n\n"
            "⚠️ Wannan analysis ne kawai, ba garantin win ba.\n"
            "Yi amfani da DEMO kafin real money."
        )

        await query.edit_message_text(message)


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
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("signal", signal_command)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("🤖 ABUBAKAR BINARY SIGNALS BOT IS RUNNING...")

    app.run_polling()


if __name__ == "__main__":
    main()
