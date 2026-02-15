import os
import cv2
import json
import random
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model

# --- 0. KRİTİK KATMAN: SpatialAttention ---
@tf.keras.utils.register_keras_serializable()
class SpatialAttention(tf.keras.layers.Layer):
    def __init__(self, kernel_size=7, **kwargs):
        super(SpatialAttention, self).__init__(**kwargs)
        self.kernel_size = kernel_size
        self.conv = tf.keras.layers.Conv2D(1, kernel_size, padding='same', activation='sigmoid')
    def call(self, inputs):
        avg_out = tf.reduce_mean(inputs, axis=-1, keepdims=True)
        max_out = tf.reduce_max(inputs, axis=-1, keepdims=True)
        concat = tf.concat([avg_out, max_out], axis=-1)
        return inputs * self.conv(concat)

# --- 1. AI SUPERVISOR: Dinamik Risk Yönetimi Sınıfı ---
class AISupervisor:
    def __init__(self, ana_aralik=2.0):
        self.max_zarar = ana_aralik
        self.iz_suren_stop = 0.5

    def analiz_et(self, ai_guven):
        # AI Güvenine göre koruma kalkanı seviyeleri
        if ai_guven >= 0.85:
            return f"🛡️ GÜÇLÜ KORUMA: %{self.max_zarar} Esneme Payı Verildi."
        elif 0.65 <= ai_guven < 0.85:
            return f"⚠️ STANDART: %{self.max_zarar/2} Sıkı Stop Aktif."
        else:
            return "❌ RİSKLİ: Güven Düşük, İşlem Reddedildi!"

# --- 2. AYARLAR ---
MODEL_ISMI = "guru_v6_ELITE_80plus.keras" 
DATASET_KLASORU = "v6_dataset" 
TEST_ADEDI = 250 
HOLD_THRESHOLD = 0.70 # %70 altı HOLD ise BUY/SELL'e bak

def testi_baslat():
    print(f"🕵️ GURU V6 Ultimate + AI Supervisor Testi Başlıyor...")
    supervisor = AISupervisor(ana_aralik=2.0)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, MODEL_ISMI)
    dataset_path = os.path.join(current_dir, DATASET_KLASORU)

    try:
        model = load_model(model_path, custom_objects={'SpatialAttention': SpatialAttention})
        print("✅ Model ve Denetleyici RAM'e alındı.")
    except Exception as e:
        print(f"❌ Yükleme hatası: {e}"); return

    # Veri Toplama
    test_verileri = []
    for kat in ["buy", "hold", "sell"]:
        yol = os.path.join(dataset_path, kat)
        if not os.path.exists(yol): continue
        for d in os.listdir(yol):
            if d.endswith('.png'):
                test_verileri.append({"resim": os.path.join(yol, d), "json": os.path.join(yol, d.replace('.png', '.json')), "etiket": kat.upper()})

    secilenler = random.sample(test_verileri, min(TEST_ADEDI, len(test_verileri)))

    # --- 3. TEST DÖNGÜSÜ ---
    print("\n" + "ID".ljust(5) + "DURUM".ljust(8) + "SİNYAL".ljust(10) + "GÜVEN".ljust(10) + "SUPERVISOR KARARI")
    print("-" * 85)

    for i, veri in enumerate(secilenler, 1):
        # A. Görsel & Sayısal Hazırlık (Normalizasyon Dahil)
        img = cv2.resize(cv2.cvtColor(cv2.imread(veri["resim"]), cv2.COLOR_BGR2RGB), (224, 224)) / 255.0
        with open(veri["json"], 'r') as f:
            js = json.load(f)
            sayisal = np.array([[js.get('rsi', 50)/100, js.get('stoch_k', 50)/100, js.get('stoch_d', 50)/100, 
                                 min(js.get('atr', 0)/5, 1), (js.get('cci', 0)+200)/400, 
                                 js.get('adx', 0)/100, (js.get('macd', 0)+5)/10]], dtype=np.float32)

        # B. Tahmin & Eşik Kontrolü
        tahmin = model.predict({'gorsel_input': np.expand_dims(img, 0), 'sayisal_input': sayisal}, verbose=0)[0]
        
        if tahmin[1] < HOLD_THRESHOLD:
            sinif_id = 0 if tahmin[0] > tahmin[2] else 2
        else:
            sinif_id = 1
            
        tahmin_ad = ["BUY", "HOLD", "SELL"][sinif_id]
        guven = tahmin[sinif_id]
        
        # C. SUPERVISOR DENETİMİ
        denetim_notu = supervisor.analiz_et(guven) if tahmin_ad != "HOLD" else "---"
        
        durum = "✅" if tahmin_ad == veri["etiket"] else "❌"
        print(f"{i:03d}  {durum.ljust(5)}  {tahmin_ad.ljust(8)}  %{guven*100:0.1f}  {denetim_notu}")

    print("-" * 85)

if __name__ == "__main__":
    testi_baslat()