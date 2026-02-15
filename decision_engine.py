import numpy as np
import cv2
import tensorflow as tf
from tensorflow.keras.models import load_model

# --- AI MODEL COMPATIBILITY (SpatialAttention) ---
@tf.keras.utils.register_keras_serializable()
class SpatialAttention(tf.keras.layers.Layer):
    def __init__(self, kernel_size=7, **kwargs):
        super(SpatialAttention, self).__init__(**kwargs); self.kernel_size = kernel_size
        self.conv = tf.keras.layers.Conv2D(1, kernel_size, padding='same', activation='sigmoid')
    def call(self, inputs):
        avg_out = tf.reduce_mean(inputs, axis=-1, keepdims=True)
        max_out = tf.reduce_max(inputs, axis=-1, keepdims=True)
        return inputs * self.conv(tf.concat([avg_out, max_out], axis=-1))

MODEL_YOLU = 'guru_v6_ELITE_80plus.keras'
BEYIN = None

def modeli_baslat():
    global BEYIN
    if BEYIN is None:
        print("🧠 [KARAR MOTORU] Guru V6 ELITE Yükleniyor...")
        BEYIN = load_model(MODEL_YOLU, custom_objects={'SpatialAttention': SpatialAttention})
    return True

def sistemi_test_et_donuslu(resim_yolu, sayisal_vektor):
    """Hem görseli hem de sayısal veriyi Guru V6'ya (Simülasyon formatında) gönderir."""
    if not modeli_baslat(): return "ERROR", 0, "HOLD"
    
    try:
        # 1. Görüntüyü RGB olarak oku
        img_bgr = cv2.imread(resim_yolu)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img_rgb, (224, 224)) / 255.0
        
        # 🚨 2. LIVE_SIM İLE %100 UYUMLU KÖR FORMAT 🚨
        rsi_raw = sayisal_vektor[1] # Gerçek RSI'ı al
        # Tıpkı live_sim.py'deki gibi RSI/100 ve diğerlerini sabit 0.5/0.0 yapıyoruz
        num = np.array([[rsi_raw/100.0, 0.5, 0.5, 0.0, 0.5, 0.0, 0.5]], dtype=np.float32)
        
        # 3. TAHMİN
        preds = BEYIN({'gorsel_input': np.expand_dims(img, 0), 'sayisal_input': num}, training=False).numpy()[0]
        
        buy_prob, hold_prob, sell_prob = preds[0], preds[1], preds[2]
        
        # V6 Elite Sinyal Üretimi
        if buy_prob > 0.60 and buy_prob > sell_prob:
            return "V6 BOĞA", buy_prob * 100, "BUY 🟢"
        elif sell_prob > 0.60 and sell_prob > buy_prob:
            return "V6 AYI", sell_prob * 100, "SELL 🔴"
        else:
            return "V6 NÖTR", hold_prob * 100, "HOLD 🟡"
            
    except Exception as e:
        print(f"⚠️ Karar Motoru Hatası: {e}")
        return "HATA", 0, "HOLD"