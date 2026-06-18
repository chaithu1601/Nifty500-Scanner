import yfinance as yf
import pandas as pd
import warnings
import time
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telebot import TeleBot

warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
TOKEN = "8695254241:AAFCHtioWd8X5mNw17EvL6X0z1pjtjIRtVE"
CHAT_ID = "855009167"
GOOGLE_SHEET_NAME = "Trading Journal" 

bot = TeleBot(TOKEN)

class UltimateAuditorCloudV43:
    def __init__(self):
        self.output_path = 'Final_Institutional_Report.csv'
        
        # 🟢 మీ 16 పాయింట్ల పక్కా గూగుల్ షీట్ హెడర్స్ (A నుండి P)
        self.headers = [
            'Date of Entry', 'Stock Name', 'Buy_Price', 'Stop_Loss', 'Target', 
            'Live Price', '% Change (Buy vs Live)', 'Status', 'Target %', 'SL %', 
            'Hit Date and time', '12. TECHNICALS', '13. STRENGTH ANALYSIS', 
            '14. MOMENTUM & FUNDAMENTALS', '15. MARKET CONDITION', '16. BACKTEST HISTORY'
        ]

        with open(self.output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
            
        self.sheet = None
        self.init_google_sheets()

    def init_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            self.sheet = client.open(GOOGLE_SHEET_NAME).sheet1
            print("✅ Google Sheets Connection Successful!")
            
            # షీట్ రీసెట్/ఖాళీగా ఉంటే హెడర్స్ రాయడం
            try:
                current_rows = self.sheet.get_all_values()
                if not current_rows or len(current_rows) == 0:
                    self.sheet.append_row(self.headers, value_input_option='USER_ENTERED')
            except: pass
        except Exception as e:
            print(f"⚠️ Google Sheets Connection Failed: {e}")

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
        print("🚀 Cloud Scan Started...")
        bot.send_message(CHAT_ID, "🚀 *Cloud Scan Started (20-Point Linear Alignment System Active)...*", parse_mode='Markdown')
        
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
                        
                        # 1. EMA Trend
                        p_ema = 2 if e20 > close.ewm(span=50).mean().iloc[-1] else 0

                        # 2. Pullback Logic
                        pb_val = (abs(last_c - e20)/e20)*100
                        if pb_val <= 1.5: p_pb, pb_status = 2, "Best(+2)"
                        elif 1.5 < pb_val <= 3: p_pb, pb_status = 1, "Acceptable(+1)"
                        else: p_pb, pb_status = -2, "Avoid(-2 Penalty)"

                        # 3. RSI Dynamic Scoring
                        if 40 <= rsi <= 62: p_rsi, rsi_status = 1, "Sweet Spot(+1)"
                        elif 62 < rsi < 70: p_rsi, rsi_status = 0, "Neutral(0)"
                        elif 70 <= rsi <= 80: p_rsi, rsi_status = -1, "Overbought(-1 Penalty)"
                        elif rsi > 80: p_rsi, rsi_status = -2, "Danger(-2 Penalty)"
                        else: p_rsi, rsi_status = -1, "Bearish Bear(-1 Penalty)"

                        # 4. Liquidity & Volume Analytics
                        vol_avg = float(df['Volume'].tail(5).mean())
                        curr_vol = float(df['Volume'].iloc[-1])
                        
                        if vol_avg >= 500000: p_liq = 1
                        else: p_liq = -2

                        if curr_vol >= 1.5 * vol_avg: p_vol, vol_status = 2, "High Spike(+2)"
                        elif curr_vol < 0.7 * vol_avg: p_vol, vol_status = -2, "Low Vol(-2 Penalty)"
                        else: p_vol, vol_status = 0, "Normal(0)"

                        # 5. Relative Strength & Momentum
                        rs_1w = 1 if close.pct_change(5).iloc[-1] > n_close.pct_change(5).iloc[-1] else 0
                        rs_1m = 1 if close.pct_change(21).iloc[-1] > n_close.pct_change(21).iloc[-1] else 0
                        rs_3m = 1 if close.pct_change(63).iloc[-1] > n_close.pct_change(63).iloc[-1] else 0
                        rs_total = rs_1w + rs_1m + rs_3m
                        
                        p_hhl = 1 if last_c > df['High'].iloc[-2] else 0
                        p_mom = 1 if last_c >= (df['High'].max() * 0.90) else 0

                        # 🔒 5 GOLDEN FUNDAMENTAL RULES
                        p_fund = 0
                        roe_txt, roce_txt, debt_txt, sales_txt, profit_txt = "N/A", "N/A", "N/A", "N/A", "N/A"
                        
                        try:
                            ticker_obj = yf.Ticker(t)
                            info = ticker_obj.info
                            roe = info.get('returnOnEquity')
                            if roe:
                                roe_p = roe * 100
                                roe_txt = f"{roe_p:.1f}%"
                                if roe_p > 15: p_fund += 1
                                
                            roce = info.get('returnOnCapital') or info.get('operatingMargins')
                            if roce:
                                roce_p = roce * 100
                                roce_txt = f"{roce_p:.1f}%"
                                if roce_p > 15: p_fund += 1
                                
                            debt = info.get('debtToEquity')
                            if debt is not None:
                                d_e = debt / 100
                                debt_txt = f"{d_e:.2f}"
                                if d_e < 1.0: p_fund += 1
                                elif d_e > 2.0: p_fund -= 1
                                
                            sales_g = info.get('revenueGrowth')
                            if sales_g:
                                rev_p = sales_g * 100
                                sales_txt = f"{rev_p:.1f}%"
                                if rev_p > 10: p_fund += 1
                                
                            profit_g = info.get('earningsGrowth')
                            if profit_g:
                                e_p = profit_g * 100
                                profit_txt = f"{e_p:.1f}%"
                                if e_p > 10: p_fund += 1
                        except: pass

                        total_score = p_ema + p_rsi + p_pb + p_vol + p_liq + p_hhl + mkt_pts + rs_total + p_mom + p_fund + 1
                        wr, last_10 = self.backtest_logic(df)

                        # స్ట్రిక్ట్ ఫిల్టర్
                        if total_score >= 13 and wr >= 60:
                            quality_val = "Super Institutional" if total_score >= 15 else "Watchlist Grade"
                            verdict_val = "Strong Buy" if (total_score >= 15 and wr >= 60) else "Watchlist"

                            sl_val = round(df['Low'].tail(5).min(), 2)
                            risk = last_c - sl_val
                            target_val = round(last_c + (risk * 2), 2)
                            
                            target_pct = round(((target_val - last_c) / last_c) * 100, 2)
                            sl_pct = round(((last_c - sl_val) / last_c) * 100, 2)

                            final_buy_price = round(last_c, 2)
                            final_sl_price = round(sl_val, 2)
                            final_target_price = round(target_val, 2)
                            current_date = time.strftime("%d.%m.%y")

                            # 💡 షీట్ అలైన్‌మెంట్ కోసం ఒకే సెల్‌లో డేటాను స్పేసెస్‌తో రీప్లేస్ చేసాం (\n తీసేసాం)
                            tech_sheet = f"EMA:20>50 | RSI:{rsi:.1f}({rsi_status}) | Pullback:{pb_val:.1f}%({pb_status}) | Price Act:HH"
                            strength_sheet = f"RS Beat:{rs_total}/3 | 52W High:{'Peak' if p_mom==1 else 'Normal'}"
                            mom_sheet = f"VolAvg:{vol_avg:,.0f} | Spike:{vol_status} | ROE:{roe_txt} | ROCE:{roce_txt} | Debt:{debt_txt} | Sales:{sales_txt} | Profit:{profit_txt}"
                            mkt_sheet = f"Nifty:{'BULLISH' if mkt_pts==1 else 'WEAK'} | Strategy:{'Full Size' if mkt_pts==1 else 'Avoid'} | Score:{total_score}/20"
                            backtest_sheet = f"WR:{wr:.0f}% | {last_10}"

                            # Local CSV రిపోర్ట్
                            writer.writerow([
                                current_date, t, final_buy_price, final_sl_price, final_target_price, "", "", "", target_pct, sl_pct, "", 
                                tech_sheet, strength_sheet, mom_sheet, mkt_sheet, backtest_sheet
                            ])

                            # 📊 గూగుల్ షీట్ లైవ్ ఆటోమేషన్ (పక్కా లీనియర్ రో ఆర్డర్)
                            if self.sheet is not None:
                                try:
                                    # హెడర్స్ ఫోర్స్ అప్‌డేట్
                                    current_values = self.sheet.get_all_values()
                                    if not current_values or len(current_values) == 0:
                                        self.sheet.append_row(self.headers, value_input_option='USER_ENTERED')
                                        time.sleep(1)
                                        current_values = self.sheet.get_all_values()

                                    next_row_idx = len(current_values) + 1
                                    ticker_clean = t.replace('.NS', '').strip()
                                    google_ticker = f"NSE:{ticker_clean}"
                                    
                                    live_price_formula = f'=IFERROR(GOOGLEFINANCE("{google_ticker}"), {final_buy_price})'
                                    change_formula = f'=IFERROR(((F{next_row_idx}-C{next_row_idx})/C{next_row_idx})*100, 0)'
                                    status_formula = f'=IF(F{next_row_idx}>=E{next_row_idx}, "TARGET HIT", IF(F{next_row_idx}<=D{next_row_idx}, "SL HIT", "HOLD"))'

                                    row_data = [
                                        current_date,                # A
                                        t,                           # B
                                        final_buy_price,             # C
                                        final_sl_price,              # D
                                        final_target_price,          # E
                                        live_price_formula,          # F
                                        change_formula,              # G
                                        status_formula,              # H
                                        f"{target_pct}%",            # I
                                        f"{sl_pct}%",                # J
                                        "",                          # K
                                        tech_sheet,                  # L
                                        strength_sheet,              # M
                                        mom_sheet,                   # N
                                        mkt_sheet,                   # O
                                        backtest_sheet               # P
                                    ]
                                    
                                    # నేరుగా రో చివరన పక్కాగా అపెండ్ చేయడం
                                    self.sheet.append_row(row_data, value_input_option='USER_ENTERED')
                                    time.sleep(1)
                                except Exception as sheet_err:
                                    print(f"Sheet Append Error: {sheet_err}")

                            # 📱 టెలిగ్రామ్ అలర్ట్ (టెలిగ్రామ్‌లో మాత్రం బుల్లెట్ పాయింట్స్ నీట్‌గా కనిపిస్తాయి)
                            alert_msg = (
                                f"🚀 *20-POINT SWING AUDIT: {t}*\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏆 *TOTAL SCORE: {total_score}/20 | {quality_val}*\n"
                                f"🎯 *FINAL VERDICT: {verdict_val}*\n\n"
                                f"💰 *TRADE SETUP*\n"
                                f"• BUY: ₹{final_buy_price:.2f}\n"
                                f"• SL: ₹{final_sl_price:.2f} | TGT: ₹{final_target_price:.2f}\n"
                                f"• TGT %: {target_pct}% | SL %: {sl_pct}%\n\n"
                                f"📊 *1. TECHNICALS*\n• {tech_sheet.replace(' | ', ' Change• ')}\n\n"
                                f"💪 *2. RELATIVE STRENGTH*\n• {strength_sheet.replace(' | ', '\n• ')}\n\n"
                                f"🔒 *3. LIQUIDITY & FUNDAMENTALS*\n• {mom_sheet.replace(' | ', '\n• ')}\n\n"
                                f"🌍 *4. MARKET CONDITION*\n• {mkt_sheet.replace(' | ', '\n• ')}\n\n"
                                f"📉 *BACKTEST HISTORY*\n• {backtest_sheet}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"👤 *Verified by: Ashok Reddy*"
                            )
                            try: bot.send_message(CHAT_ID, alert_msg, parse_mode='Markdown')
                            except: pass

                except: continue

        bot.send_message(CHAT_ID, "🏁 *ULTIMATE 20-POINT SCAN COMPLETED!*")

if __name__ == "__main__":
    auditor = UltimateAuditorCloudV43()
    auditor.start()
