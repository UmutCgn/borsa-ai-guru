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

# --- 1. GURU V23 ENGINE (Hardened & Unstoppable) ---
class GuruV23Engine:
    def __init__(self, capital=1000):
        self.total_balance = capital
        self.cash = capital
        self.positions = {}
        self.trades = []
        self.symbol_pnl = {}
        self.commission = 0.0006
        self.slippage = 0.0007

    def open_trade(self, symbol, price, side, atr, conf):
        if symbol in self.positions: return
        
        # Sabit %5 Risk (Portföy Koruması)
        margin_used = self.total_balance * 0.05
        lot = (margin_used * 10) / price # 10x kaldıraç
        
        entry_p = price * (1.0007 if side == "LONG" else 0.9993)
        fee = lot * entry_p * self.commission
        
        self.cash -= (margin_used + fee)
        self.positions[symbol] = {
            'lot': lot, 'entry': entry_p, 'margin': margin_used, 'side': side,
            'sl': entry_p * (0.975 if side=="LONG" else 1.025), # %2.5 Hard Stop
            'candles_held': 0, 'tp1_hit': False
        }
        
        tqdm.write(f"\n🚀 [GİRİŞ] {symbol} {side} | Güven: %{conf*100:.1f} | Fiyat: {entry_p:.4f} | Margin: ${margin_used:.2f}")

    def manage_positions(self, symbol, price, atr):
        if symbol not in self.positions: return
        pos = self.positions[symbol]
        pos['candles_held'] += 1
        
        pnl_pct = ((price - pos['entry']) / pos['entry'] * 100) if pos['side'] == "LONG" else ((pos['entry'] - price) / pos['entry'] * 100)
        atr_ratio = (atr / price) * 100

        # 1. HARD STOP CHECK (Gözünün Yaşına Bakmaz)
        stop_hit = (pos['side']=="LONG" and price <= pos['sl']) or (pos['side']=="SHORT" and price >= pos['sl'])
        if stop_hit:
            self.close_trade(symbol, price, "HARD STOP LOSS")
            return

        # 2. AI TRAILING EXIT (Sadece %1.2 kardan sonra ve 3 mum geçince)
        if pos['candles_held'] > 3 and pnl_pct > 1.2:
            trail_dist = max(0.8, atr_ratio * 1.5)
            aktif_stop = pnl_pct - trail_dist
            if pnl_pct <= aktif_stop:
                self.close_trade(symbol, price, "AI TRAILING STOP")

    def close_trade(self, symbol, price, reason):
        pos = self.positions[symbol]
        exit_p = price * (0.9993 if pos['side']=="LONG" else 1.0007)
        pnl = pos['lot'] * (exit_p - pos['entry']) if pos['side']=="LONG" else pos['lot'] * (pos['entry'] - exit_p)
        fee = pos['lot'] * exit_p * self.commission
        net_pnl = pnl - fee
        
        self.cash += pos['margin'] + net_pnl
        self.total_balance = self.cash + sum(p['margin'] for s,p in self.positions.items() if s != symbol)
        self.symbol_pnl[symbol] = self.symbol_pnl.get(symbol, 0) + net_pnl
        self.trades.append(net_pnl)
        
        tqdm.write(f"✅ [KAPAT] {symbol} ({reason}) | PnL: ${net_pnl:.2f} | Bakiye: ${self.total_balance:.2f}\n")
        del self.positions[symbol]

# --- 2. MULTI-COIN SCANNER (Radar & Analysis) ---
class UnstoppableScanner:
    def __init__(self):
        self.model = load_model("guru_v6_ELITE_80plus.keras", custom_objects={'SpatialAttention': SpatialAttention})
        self.engine = GuruV23Engine()
        self.symbols = []

    def auto_select_coins(self):
        print("🔍 Binance taranıyor, en aktif 5 coin seçiliyor...")
        ex = ccxt.binance(); tickers = ex.fetch_tickers()
        sorted_coins = sorted(tickers.items(), key=lambda x: x[1]['quoteVolume'], reverse=True)
        potential = [s for s, t in sorted_coins if '/USDT' in s and 'UP' not in s and 'DOWN' not in s][:15]
        final = []
        for s in potential:
            try:
                ohlcv = ex.fetch_ohlcv(s, '5m', limit=50)
                df = pd.DataFrame(ohlcv, columns=['D','O','H','L','C','V'])
                if (ta.atr(df['H'],df['L'],df['C']).iloc[-1] / df['C'].iloc[-1]) * 100 > 0.18:
                    final.append(s)
                if len(final) >= 5: break
            except: continue
        return final

    def fetch_data(self, symbol):
        ex = ccxt.binance(); ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=1000)
        df = pd.DataFrame(ohlcv, columns=['Date','Open','High','Low','Close','Volume'])
        df['Date'] = pd.to_datetime(df['Date'], unit='ms'); df.set_index('Date', inplace=True)
        df['RSI']=ta.rsi(df['Close']); df['ATR']=ta.atr(df['High'],df['Low'],df['Close'])
        df['EMA200']=ta.ema(df['Close'], 200)
        st=ta.stoch(df['High'],df['Low'],df['Close']); df['SK']=st.iloc[:,0]; df['SD']=st.iloc[:,1]
        df['CCI']=ta.cci(df['High'],df['Low'],df['Close']); df['ADX']=ta.adx(df['High'],df['Low'],df['Close'])['ADX_14']
        df['MACD']=ta.macd(df['Close']).iloc[:,0]
        return df.fillna(0.5)

    def run(self):
        self.symbols = self.auto_select_coins()
        datasets = {s: self.fetch_data(s) for s in self.symbols}
        print(f"🚀 V23 UNSTOPPABLE AKTİF | Portföy: {self.symbols}")

        for i in tqdm(range(500, 1000), desc="Piyasa İşleniyor"):
            for s in self.symbols:
                df = datasets[s]; curr = df.iloc[i]; price = curr['Close']
                
                # 1. POZİSYON YÖNETİMİ
                if s in self.engine.positions:
                    self.engine.manage_positions(s, price, curr['ATR'])
                    continue

                # 2. ANALİZ (Resim & Sayısal)
                df_slice = df.iloc[i-31:i-1]
                buf = io.BytesIO(); mpf.plot(df_slice, type='candle', style='charles', savefig=buf); buf.seek(0)
                img = cv2.resize(cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), 1), (224, 224)) / 255.0
                plt.close('all')

                num = np.array([[curr['RSI']/100, curr['SK']/100, curr['SD']/100, min(curr['ATR']/5, 1), 
                                 (curr['CCI']+200)/400, curr['ADX']/100, (curr['MACD']+5)/10]], dtype=np.float32)

                preds = self.model({'gorsel_input': np.expand_dims(img, 0), 'sayisal_input': num}, training=False).numpy()[0]
                
                # --- V23 KESKİN GİRİŞ KURALLARI ---
                if preds[1] < 0.65: # Hold düşük olacak
                    if preds[0] > 0.55 and price > curr['EMA200']: # Güçlü LONG + Trend Onayı
                        self.engine.open_trade(s, price, "LONG", curr['ATR'], preds[0])
                    elif preds[2] > 0.55 and price < curr['EMA200']: # Güçlü SHORT + Trend Onayı
                        self.engine.open_trade(s, price, "SHORT", curr['ATR'], preds[2])

        self.final_report()

    def final_report(self):
        print("\n" + "="*50 + "\n🏁 GURU V23 FINAL REPORT\n" + "="*50)
        winrate = (len([t for t in self.engine.trades if t > 0]) / len(self.engine.trades) * 100) if self.engine.trades else 0
        print(f"Toplam İşlem: {len(self.engine.trades)} | Winrate: %{winrate:.2f}")
        print(f"FİNAL EQUITY: ${self.engine.total_balance:.2f}")
        print("="*50)

if __name__ == "__main__":
    UnstoppableScanner().run()