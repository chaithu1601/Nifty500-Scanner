import yfinance as yf
import pandas as pd
import warnings
import time
from telebot import TeleBot

warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
TOKEN = "8695254241:AAFCHtioWd8X5mNw17EvL6X0z1pjtjIRtVE"
CHAT_ID = "855009167"
CAPITAL = 500000
RISK_PERCENT = 0.01

bot = TeleBot(TOKEN)

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def backtest_logic(df):
    wins, losses, history = 0, 0, []
    try:
        total_lookback = min(len(df)-5, 250) 
        for i in range(len(df)-5, len(df) - total_lookback, -5):
            sub = df.iloc[:i]
            c = sub['Close'].iloc[-1]
            e20 = sub['Close'].ewm(span=20).mean().iloc[-1]
            if c > e20:
                future = df.iloc[i:i+10]
                sl = sub['Low'].tail(5).min()
                tgt = c + (c - sl) * 2
                if any(future['High'] >= tgt):
                    wins += 1
                    if len(history) < 10: history.append("W") 
                elif any(future['Low'] <= sl):
                    losses += 1
                    if len(history) < 10: history.append("L")
        total_trades = wins + losses
        wr_yearly = round((wins/total_trades)*100, 0) if total_trades > 0 else 0
        return wr_yearly, "-".join(history[::-1])
    except: 
        return 0, "N/A"

def start_scan():
    print("🚀 GitHub Cloud Auditor Started...")
    bot.send_message(CHAT_ID, "🚀 *Full Cloud Scan Started (500 Stocks)...*", parse_mode='Markdown')
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        n_close = nifty['Close'].squeeze()
        n_e20 = n_close.ewm(span=20).mean().iloc[-1]
        n_e50 = n_close.ewm(span=50).mean().iloc[-1]
        mkt_pts = 1 if n_e20 > n_e50 else 0
    except: mkt_pts = 1

    try:
        nse_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df_csv = pd.read_csv(nse_url)
    except:
        bot.send_message(CHAT_ID, "❌ NSE Data Link Error.")
        return

    symbol_col = next((col for col in df_csv.columns if col.strip().lower() == 'symbol'), df_csv.columns[0])
    tickers = [s.strip().upper() + ".NS" for s in df_csv[symbol_col].iloc[:500].dropna().astype(str).tolist()]

    for index, t in enumerate(tickers):
        try:
            df = yf.download(t, period="2y", progress=False, threads=False)
            if df is not None and len(df) > 60:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                close = df['Close'].squeeze()
                last_c = float(close.iloc[-1])
                e20 = close.ewm(span=20).mean().iloc[-1]
                rsi = float(calculate_rsi(close).iloc[-1])
                
                p_ema = 2 if e20 > close.ewm(span=50).mean().iloc[-1] else 0
                pb_val = (abs(last_c - e20)/e20)*100
                p_pb = 2 if pb_val <= 1.5 else 1 if pb_val <= 3 else -2
                
                vol_avg = df['Volume'].tail(5).mean()
                curr_vol = df['Volume'].iloc[-1]
                p_vol = 2 if curr_vol >= 1.5 * vol_avg else -2 if curr_vol < 0.7 * vol_avg else 0

                p_rsi = 1 if 40 <= rsi <= 62 else 0
                rs_total = (1 if close.pct_change(5).iloc[-1] > n_close.pct_change(5).iloc[-1] else 0) + \
                           (1 if close.pct_change(21).iloc[-1] > n_close.pct_change(21).iloc[-1] else 0) + \
                           (1 if close.pct_change(63).iloc[-1] > n_close.pct_change(63).iloc[-1] else 0)
                
                p_hhl = 1 if last_c > df['High'].iloc[-2] else 0
                p_mom = 1 if last_c >= (df['High'].max() * 0.90) else 0

                total_score = p_ema + p_rsi + p_pb + p_vol + p_hhl + mkt_pts + rs_total + p_mom + 1
                wr, last_10 = backtest_logic(df)

                # HIGH SUCCESS FILTERS (Elite and Safe Buy)
                is_elite = (total_score >= 12 and wr >= 60 and mkt_pts == 1 and pb_val <= 1.5)
                is_safe = (total_score >= 10 and wr >= 50)

                if is_elite or is_safe:
                    quality_val = "Elite Grade" if is_elite else "High Quality"
                    verdict_val = "💎 ELITE BUY" if is_elite else "✅ SAFE BUY"
                    emoji = "💎" if is_elite else "✅"

                    sl_val = round(df['Low'].tail(5).min(), 2)
                    risk = last_c - sl_val
                    target_val = round(last_c + (risk * 2), 2)
                    qty_val = int((CAPITAL * RISK_PERCENT) / risk) if risk > 0 else 0

                    alert_msg = (
                        f"{emoji} *{verdict_val}*\n"
                        f"🚀 *STOCK: {t}*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏆 SCORE: {total_score}/14 | {quality_val}\n\n"
                        f"💰 BUY: ₹{last_c:.2f}\n"
                        f"🛡️ SL: ₹{sl_val:.2f} | 🎯 TGT: ₹{target_val:.2f}\n"
                        f"📦 QTY: {qty_val} Shares (1% Risk)\n\n"
                        f"📈 WR (1-Year): {wr:.0f}%\n"
                        f"📊 Last 10 Trades: {last_10}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 *Verified by: Ashok Reddy*"
                    )
                    try: bot.send_message(CHAT_ID, alert_msg, parse_mode='Markdown')
                    except: pass
                    time.sleep(1)
        except: continue

    bot.send_message(CHAT_ID, "🏁 *AUTOMATED SCAN COMPLETED!*")

if __name__ == "__main__":
    start_scan()
