import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import cv2
import tensorflow as tf
from tensorflow.keras.models import load_model
import mplfinance as mpf
import io
import matplotlib.pyplot as plt
from tqdm import tqdm
import datetime

# --- 0. AI MODEL COMPATIBILITY (SpatialAttention) ---
@tf.keras.utils.register_keras_serializable()
class SpatialAttention(tf.keras.layers.Layer):
    def __init__(self, kernel_size=7, **kwargs):
        super(SpatialAttention, self).__init__(**kwargs); self.kernel_size = kernel_size
        self.conv = tf.keras.layers.Conv2D(1, kernel_size, padding='same', activation='sigmoid')
    def call(self, inputs):
        avg_out = tf.reduce_mean(inputs, axis=-1, keepdims=True)
        max_out = tf.reduce_max(inputs, axis=-1, keepdims=True)
        return inputs * self.conv(tf.concat([avg_out, max_out], axis=-1))

# --- 1. GURU V23 ENGINE (Detaylı Log ve Raporlama Sistemi) ---
class GuruV23Engine:
    def __init__(self, capital=1000):
        self.initial_capital = capital
        self.total_balance = capital
        self.cash = capital
        self.positions = {}
        self.trades = [] 
        self.symbol_stats = {} # Her coin için karne verisi
        self.commission = 0.0006

    def open_trade(self, symbol, price, side, atr, conf):
        if symbol in self.positions: return
        
        margin_used = self.total_balance * 0.05
        lot = (margin_used * 10) / price # 10x kaldıraç
        
        entry_p = price * (1.0007 if side == "LONG" else 0.9993)
        fee = lot * entry_p * self.commission
        self.cash -= (margin_used + fee)
        
        # 👑 ASİMETRİK RİSK (1'e 3 Oranı)
        risk_mesafesi = atr * 1.5   
        hedef_mesafesi = risk_mesafesi * 3.0 
        
        if side == "LONG":
            sl = entry_p - risk_mesafesi
            tp = entry_p + hedef_mesafesi
        else:
            sl = entry_p + risk_mesafesi
            tp = entry_p - hedef_mesafesi

        self.positions[symbol] = {
            'lot': lot, 'entry': entry_p, 'margin': margin_used, 'side': side,
            'sl': sl, 'tp': tp, 'risk_mesafesi': risk_mesafesi,
            'candles_held': 0, 'breakeven': False, 'kilit_kar': False
        }
        
        # LOGLAR GERİ GELDİ
        tqdm.write(f"\n🚀 [GİRİŞ] {symbol} {side} | Güven: %{conf*100:.1f} | Risk Mesafesi: {risk_mesafesi:.4f} | Kâr Hedefi: {hedef_mesafesi:.4f}")

    def manage_positions(self, symbol, price, atr):
        if symbol not in self.positions: return
        pos = self.positions[symbol]
        pos['candles_held'] += 1
        
        tp_hit = (pos['side']=="LONG" and price >= pos['tp']) or (pos['side']=="SHORT" and price <= pos['tp'])
        sl_hit = (pos['side']=="LONG" and price <= pos['sl']) or (pos['side']=="SHORT" and price >= pos['sl'])

        if tp_hit:
            self.close_trade(symbol, price, "DEV KAZANÇ 🎯🎯🎯")
        elif sl_hit:
            reason = "KÜÇÜK ZARAR 🛑"
            if pos['kilit_kar']: reason = "GARANTİ KÂR 💰"
            elif pos['breakeven']: reason = "SIFIR ZARAR 🛡️"
            self.close_trade(symbol, price, reason)
        elif pos['candles_held'] >= 18:
            self.close_trade(symbol, price, "ZAMAN AŞIMI ⏳")
        else:
            kat_edilen = (price - pos['entry']) if pos['side'] == "LONG" else (pos['entry'] - price)
            if kat_edilen >= pos['risk_mesafesi'] and not pos['breakeven']:
                komisyon_kurtarma = pos['entry'] * 0.002
                pos['sl'] = pos['entry'] + (komisyon_kurtarma if pos['side']=="LONG" else -komisyon_kurtarma)
                pos['breakeven'] = True
            if kat_edilen >= (pos['risk_mesafesi'] * 1.8) and not pos['kilit_kar']:
                pos['sl'] = pos['entry'] + (pos['risk_mesafesi'] if pos['side']=="LONG" else -pos['risk_mesafesi'])
                pos['kilit_kar'] = True

    def close_trade(self, symbol, price, reason):
        pos = self.positions[symbol]
        exit_p = price * (0.9993 if pos['side']=="LONG" else 1.0007)
        pnl = pos['lot'] * (exit_p - pos['entry']) if pos['side']=="LONG" else pos['lot'] * (pos['entry'] - exit_p)
        net_pnl = pnl - (pos['lot'] * exit_p * self.commission)
        
        self.cash += pos['margin'] + net_pnl
        self.total_balance = self.cash + sum(p['margin'] for s,p in self.positions.items() if s != symbol)
        
        # KARNE KAYDI
        if symbol not in self.symbol_stats:
            self.symbol_stats[symbol] = {"pnls": [], "wins": 0, "total": 0}
        self.symbol_stats[symbol]["pnls"].append(net_pnl)
        self.symbol_stats[symbol]["total"] += 1
        if net_pnl > 0: self.symbol_stats[symbol]["wins"] += 1
        self.trades.append(net_pnl)

        pnl_icon = "🟢" if net_pnl > 0 else "🔴"
        if "SIFIR ZARAR" in reason: pnl_icon = "⚪"
        tqdm.write(f"{pnl_icon} [KAPAT] {symbol} ({reason}) | PnL: ${net_pnl:.2f} | Bakiye: ${self.total_balance:.2f}\n")
        
        del self.positions[symbol]

# --- 2. INTERACTIVE SIMULATOR (Tüm Mantık Korundu) ---
class UnstoppableScanner:
    def __init__(self):
        print("\n" + "🧠"*3 + " GURU V23 PRO SIMULATOR BAŞLATILIYOR " + "🧠"*3)
        self.model = load_model("guru_v6_ELITE_80plus.keras", custom_objects={'SpatialAttention': SpatialAttention})
        self.engine = GuruV23Engine()
        self.config = {}
        self.symbols = []

    def get_user_setup(self):
        """Kullanıcıdan girişleri güvenli şekilde alır."""
        print("\n--- TEST AYARLARI ---")
        coins = input("🔍 Test edilecek coinler (Örn: BTC/USDT, ETH/USDT, OM/USDT): ")
        self.symbols = [s.strip().upper() for s in coins.split(',')]
        
        # Interval Kontrolü (Invalid Interval hatasını önler)
        tf = input("⏰ Zaman Dilimi (5m, 15m, 1h, 4h): ").strip().lower()
        if tf.isdigit(): tf += 'm' # Sadece sayı girilirse 'm' ekle
        self.config['tf'] = tf
        
        self.config['limit'] = int(input("📊 Kaç mumluk geçmiş taransın? (Örn: 1000): "))
        print(f"\n🚀 Binance verileri çekiliyor... Lütfen bekleyin.\n")

    def fetch_data(self, symbol):
        try:
            ex = ccxt.binance()
            ohlcv = ex.fetch_ohlcv(symbol, self.config['tf'], limit=self.config['limit'])
            df = pd.DataFrame(ohlcv, columns=['Date','Open','High','Low','Close','Volume'])
            df['Date'] = pd.to_datetime(df['Date'], unit='ms'); df.set_index('Date', inplace=True)
            
            df['EMA20'] = ta.ema(df['Close'], length=20)
            df['EMA50'] = ta.ema(df['Close'], length=50)
            bbands = ta.bbands(df['Close'], length=20, std=2)
            df['BB_LOWER'], df['BB_UPPER'] = bbands.iloc[:, 0], bbands.iloc[:, 2]
            df['RSI'], df['ATR'] = ta.rsi(df['Close'], length=14), ta.atr(df['High'], df['Low'], df['Close'], length=14)
            df['ADX'] = ta.adx(df['High'], df['Low'], df['Close'])['ADX_14']
            return df.dropna()
        except Exception as e:
            tqdm.write(f"⚠️ {symbol} için veri hatası: {e}")
            return None

    def run(self):
        self.get_user_setup()
        datasets = {}
        for s in self.symbols:
            d = self.fetch_data(s)
            if d is not None: datasets[s] = d
        
        if not datasets:
            print("❌ Hiçbir coin için veri alınamadı. Program kapatılıyor."); return

        # En kısa veriye göre döngüyü hizala
        common_len = min(len(datasets[s]) for s in datasets)

        for i in tqdm(range(50, common_len - 2), desc="Piyasa İşleniyor"):
            for s in datasets:
                df = datasets[s]
                curr = df.iloc[i] 
                price = curr['Close']
                
                if s in self.engine.positions:
                    self.engine.manage_positions(s, price, curr['ATR'])
                    continue

                # GÖRSEL ANALİZ
                df_slice = df.iloc[i-15 : i+2] 
                buf = io.BytesIO()
                ekstra = [
                    mpf.make_addplot(df_slice['EMA20'], color='blue', width=1.5),
                    mpf.make_addplot(df_slice['EMA50'], color='orange', width=1.5),
                    mpf.make_addplot(df_slice['BB_LOWER'], color='gray', alpha=0.5),
                    mpf.make_addplot(df_slice['BB_UPPER'], color='gray', alpha=0.5)
                ]
                mpf.plot(df_slice, type='candle', style='charles', axisoff=True, tight_layout=True, addplot=ekstra, savefig=dict(fname=buf, dpi=85, format='png', bbox_inches='tight'))
                img = cv2.resize(cv2.cvtColor(cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), 1), cv2.COLOR_BGR2RGB), (224, 224)) / 255.0
                plt.close('all')

                # SAYISAL ANALİZ (Modelin alıştığı kör format)
                num = np.array([[curr['RSI']/100.0, 0.5, 0.5, 0.0, 0.5, 0.0, 0.5]], dtype=np.float32)

                # YAPAY ZEKA TAHMİNİ
                preds = self.model({'gorsel_input': np.expand_dims(img, 0), 'sayisal_input': num}, training=False).numpy()[0]
                
                # SNIPER GİRİŞ KURALLARI
                if curr['ADX'] > 20 and preds[1] < 0.40:
                    if preds[0] > 0.75 and price > curr['EMA50']: 
                        self.engine.open_trade(s, price, "LONG", curr['ATR'], preds[0])
                    elif preds[2] > 0.75 and price < curr['EMA50']: 
                        self.engine.open_trade(s, price, "SHORT", curr['ATR'], preds[2])

        self.final_report()

    def final_report(self):
        """Test sonu coin bazlı karne."""
        print("\n" + "="*70)
        print(f"📊 GURU V23 DETAYLI PERFORMANS RAPORU")
        print("="*70)
        print(f"{'COIN':<12} | {'İŞLEM':<6} | {'WINRATE':<10} | {'TOPLAM PnL':<15}")
        print("-" * 70)
        
        for s, stat in self.engine.symbol_stats.items():
            wr = (stat['wins'] / stat['total'] * 100) if stat['total'] > 0 else 0
            tpnl = sum(stat['pnls'])
            icon = "📈" if tpnl > 0 else "📉"
            print(f"{s:<12} | {stat['total']:<6} | %{wr:<8.2f} | {icon} ${tpnl:.2f}")

        print("-" * 70)
        total_tr = len(self.engine.trades)
        final_wr = (len([t for t in self.engine.trades if t > 0]) / total_tr * 100) if total_tr > 0 else 0
        print(f"GENEL BAŞARI (WR) : %{final_wr:.2f}")
        print(f"BAŞLANGIÇ BAKİYE   : ${self.engine.initial_capital:.2f}")
        print(f"FİNAL EQUITY       : ${self.engine.total_balance:.2f}")
        
        net = self.engine.total_balance - self.engine.initial_capital
        res_icon = "🔥" if net > 0 else "❄️"
        print(f"NET KÂR/ZARAR      : {res_icon} ${net:.2f}")
        print("="*70 + "\n")

if __name__ == "__main__":
    UnstoppableScanner().run()