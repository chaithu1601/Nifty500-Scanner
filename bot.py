import yfinance as yf
import pandas as pd
import warnings
import time
import csv
from telebot import TeleBot

warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
TOKEN = "8695254241:AAFCHtioWd8X5mNw17EvL6X0z1pjtjIRtVE"
CHAT_ID = "855009167"
CAPITAL = 500000
RISK_PERCENT = 0.01

bot = TeleBot(TOKEN)

class UltimateAuditorCloudV41:
    def __init__(self):
        self.output_path = 'Final_Institutional_Report.csv'
        self.headers = [
            'Stock Name', 'Total_Score', 'Quality', 'Buy_Price', 'Stop_Loss', 'Target', 
            'Position_Size', 'Risk_Reward', 'TECHNICAL_WHY', 'STRENGTH_WHY', 
            'MOMENTUM_WHY', 'FUNDAMENTALS_WHY', 'MARKET_WHY', 
            'Win_Rate%', 'Last_10_Trades', 'FINAL_VERDICT'
        ]
        with open(self.output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def backtest_logic(self, df):
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

    def start(self):
        print("🚀 GitHub Cloud v41.0 Auditor Started...")
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
            bot.send_message(CHAT_ID, "❌ ERROR: NSE Nifty500 List Download Failed!")
            return

        symbol_col = next((col for col in df_csv.columns if col.strip().lower() == 'symbol'), df_csv.columns[0])
        tickers = [s.strip().upper() + ".NS" for s in df_csv[symbol_col].iloc[:500].dropna().astype(str).tolist()]

        with open(self.output_path, 'a', newline='', buffering=1) as f:
            writer = csv.writer(f)
            for index, t in enumerate(tickers):
                try:
                    df = yf.download(t, period="2y", progress=False, threads=False)
                    if df is not None and len(df) > 60:
                        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                        
                        close = df['Close'].squeeze()
                        last_c = float(close.iloc[-1])
                        e20 = close.ewm(span=20).mean().iloc[-1]
                        rsi = float(self.calculate_rsi(close).iloc[-1])
                        
                        p_ema = 2 if e20 > close.ewm(span=50).mean().iloc[-1] else 0

                        # Pullback Logic
                        pb_val = (abs(last_c - e20)/e20)*100
                        if pb_val <= 1.5: p_pb, pb_status = 2, "Best(+2)"
                        elif 1.5 < pb_val <= 3: p_pb, pb_status = 1, "Acceptable(+1)"
                        else: p_pb, pb_status = -2, "Avoid(-2)"

                        # Volume Logic
                        vol_avg = df['Volume'].tail(5).mean()
                        curr_vol = df['Volume'].iloc[-1]
                        if curr_vol >= 1.5 * vol_avg: p_vol, vol_status = 2, "High Spike(+2)"
                        elif curr_vol < 0.7 * vol_avg: p_vol, vol_status = -2, "Low Vol(-2)"
                        else: p_vol, vol_status = 0, "Normal(0)"

                        # RSI Logic
                        if 40 <= rsi <= 62: p_rsi, rsi_status = 1, "Sweet Spot(+1)"
                        elif 70 <= rsi <= 80: p_rsi, rsi_status = -1, "Overbought(-1)"
                        elif rsi > 80: p_rsi, rsi_status = -2, "Danger(-2)"
                        else: p_rsi, rsi_status = 0, "Neutral(0)"

                        # RS Multi-Timeframe
                        rs_1w = 1 if close.pct_change(5).iloc[-1] > n_close.pct_change(5).iloc[-1] else 0
                        rs_1m = 1 if close.pct_change(21).iloc[-1] > n_close.pct_change(21).iloc[-1] else 0
                        rs_3m = 1 if close.pct_change(63).iloc[-1] > n_close.pct_change(63).iloc[-1] else 0
                        rs_total = rs_1w + rs_1m + rs_3m
                        
                        p_hhl = 1 if last_c > df['High'].iloc[-2] else 0
                        p_mom = 1 if last_c >= (df['High'].max() * 0.90) else 0

                        total_score = p_ema + p_rsi + p_pb + p_vol + p_hhl + mkt_pts + rs_total + p_mom + 1
                        wr, last_10 = self.backtest_logic(df)

                        if total_score >= 11 and wr >= 60:
                            quality_val = "High" if total_score >= 12 else "Watchlist"
                            verdict_val = "Strong Buy" if (total_score >= 12 and wr >= 60) else "Watchlist"

                            roe_val = "Data N/A"
                            try:
                                ticker_obj = yf.Ticker(t)
                                info = ticker_obj.info
                                roe = info.get('returnOnEquity') or info.get('returnOnAssets')
                                if roe: roe_val = f"{roe * 100:.2f}%"
                            except: pass

                            # Save to Cloud Report
                            writer.writerow([
                                t, f"Score: {total_score}/14", quality_val, round(last_c, 2), sl_val, target_val, 
                                qty_val, "01:02", f"EMA:{p_ema} RSI:{rsi_status}", f"Nifty:{mkt_pts}", "Normal", "Data N/A", "Bullish",
                                f"{wr:.0f}%", last_10, verdict_val
                            ])

                            # --- మొత్తం సమాచారాన్ని ఒకే ఎక్సెల్ టేబుల్ బాక్స్ లాగా మార్చే లాజిక్ ---
                            sl_val = round(df['Low'].tail(5).min(), 2)
                            risk = last_c - sl_val
                            target_val = round(last_c + (risk * 2), 2)
                            qty_val = int((CAPITAL * RISK_PERCENT) / risk) if risk > 0 else 0

                            mkt_txt = "BULLISH" if mkt_pts == 1 else "WEAK (ALERT)"
                            pb_txt = f"{pb_val:.1f}% ({pb_status})"
                            rsi_txt = f"{rsi:.1f} ({rsi_status})"

                            full_table_msg = (
                                f"🔬 *INSTITUTIONAL AUDIT: {t}*\n"
                                f"```\n"
                                f"┌────────────────────────────────────────┐\n"
                                f"│        📊 SCORE & FINAL VERDICT        │\n"
                                f"├────────────────┬───────────────────────┤\n"
                                f"│ TOTAL SCORE    │ {total_score:<21}/14 │\n"
                                f"│ QUALITY GRADE  │ {quality_val:<22} │\n"
                                f"│ FINAL VERDICT  │ {verdict_val:<22} │\n"
                                f"├────────────────┴───────────────────────┤\n"
                                f"│          💰 LIVE TRADE SETUP           │\n"
                                f"├────────────────┬───────────────────────┤\n"
                                f"│ BUY PRICE      │ ₹ {last_c:<19.2f} │\n"
                                f"│ STOP LOSS      │ ₹ {sl_val:<19.2f} │\n"
                                f"│ TARGET PRICE   │ ₹ {target_val:<19.2f} │\n"
                                f"│ POSITION QTY   │ {qty_val:<22} │\n"
                                f"│ RISK REWARD    │ 1:2                   │\n"
                                f"├────────────────┴───────────────────────┤\n"
                                f"│         🔍 TECHNICAL INDICATORS        │\n"
                                f"├────────────────┬───────────────────────┤\n"
                                f"│ EMA 20 > 50    │ {('+2) Bullish' if p_ema==2 else '0) Neutral':<22} │\n"
                                f"│ RSI VALUE      │ {rsi_txt:<22} │\n"
                                f"│ PULLBACK DIST  │ {pb_txt:<22} │\n"
                                f"│ VOLUME STATUS  │ {vol_status:<22} │\n"
                                f"│ PRICE ACTION   │ {('HH (+1) Intact' if p_hhl==1 else 'Normal (0)'):<22} │\n"
                                f"├────────────────┴───────────────────────┤\n"
                                f"│         💪 STRENGTH & CONTEXT          │\n"
                                f"├────────────────┬───────────────────────┤\n"
                                f"│ NIFTY STATUS   │ {mkt_txt:<22} │\n"
                                f"│ RS BEAT (500)  │ {str(rs_total)+'/3 (1W,1M,3M)':<22} │\n"
                                f"│ MOMENTUM (52W) │ {('Peak (+1)' if p_mom==1 else 'Normal (0)'):<22} │\n"
                                f"│ ROE %          │ {roe_val:<22} │\n"
                                f"├────────────────┴───────────────────────┤\n"
                                f"│          📉 BACKTEST HISTORY           │\n"
                                f"├────────────────┬───────────────────────┤\n"
                                f"│ 1-YR WIN RATE  │ {str(wr)+'%':<22} │\n"
                                f"│ LAST 10 TRADES │ {last_10:<22} │\n"
                                f"└────────────────┴───────────────────────┘\n"
                                f"
```\n"
                                f"👤 *Verified by: Ashok Reddy*"
                            )
                            try:
                                bot.send_message(CHAT_ID, full_table_msg, parse_mode='Markdown')
                            except: pass

                            time.sleep(1)
                except: continue

        bot.send_message(CHAT_ID, "🏁 *AUTOMATED SCAN COMPLETED!*")

if __name__ == "__main__":
    auditor = UltimateAuditorCloudV41()
    auditor.start()
