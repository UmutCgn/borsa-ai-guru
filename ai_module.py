# dosya: ai_module.py
import tensorflow as tf
import numpy as np
import cv2
import json

# --- GURU v5: 100 EPOCH EĞİTİMİNDEKİ 55 SINIF LİSTESİ ---
# Not: Eğitimdeki sırayla (label mapping) BİREBİR AYNI olmalıdır.
SINIFLAR = [
    '3BLACKCROWS', '3INSIDE', '3LINESTRIKE', '3OUTSIDE', '3WHITESOLDIERS',
    'ABANDONEDBABY', 'ADVANCEBLOCK', 'BELTHOLD', 'CLOSINGMARUBOZU',
    'COUNTERATTACK', 'DARKCLOUDCOVER', 'DOJI', 'DOJISTAR', 'DOJI_10_0.1',
    'DRAGONFLYDOJI', 'ENGULFING', 'EVENINGDOJISTAR', 'EVENINGSTAR',
    'GAPSIDESIDEWHITE', 'GRAVESTONEDOJI', 'HAMMER', 'HANGINGMAN',
    'HARAMI', 'HARAMICROSS', 'HIGHWAVE', 'HIKKAKE', 'HIKKAKEMOD',
    'HOMINGPIGEON', 'IDENTICAL3CROWS', 'INNECK', 'INSIDE',
    'INVERTEDHAMMER', 'KICKING', 'KICKINGBYLENGTH', 'LONGLEGGEDDOJI',
    'LONGLINE', 'MARUBOZU', 'MATCHINGLOW', 'MORNINGDOJISTAR',
    'MORNINGSTAR', 'ONNECK', 'PIERCING', 'RICKSHAWMAN',
    'RISEFALL3METHODS', 'SEPARATINGLINES', 'SHOOTINGSTAR', 'SHORTLINE',
    'SPINNINGTOP', 'STALLEDPATTERN', 'STICKSANDWICH', 'TAKURI',
    'TASUKIGAP', 'THRUSTING', 'TRISTAR', 'UNIQUE3RIVER', 'XSIDEGAP3METHODS'
]

class GuruBrain:
    def __init__(self, model_path):
        print(f"🧠 GURU AI: Hibrit Beyin Yükleniyor... ({model_path})")
        try:
            # Modeli yükle (functional_2 - 2 Input bekler)
            self.model = tf.keras.models.load_model(model_path)
            print("✅ GURU AI: Görsel (224x224 RGB) + Sayısal (2) loblar senkronize.")
        except Exception as e:
            print(f"❌ KRİTİK HATA: Model yüklenemedi! {e}")
            self.model = None

    def goruntuyu_hazirla(self, resim_yolu):
        """Grafiği MobileNetV2 standardı olan 224x224 RGB formatına dönüştürür."""
        img = cv2.imread(resim_yolu)
        if img is None: return None
        
        # BGR -> RGB Dönüşümü (Kritik!)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224))
        
        # Normalizasyon ve Batch boyutu ekleme (1, 224, 224, 3)
        img_final = img_resized.astype('float32') / 255.0
        return np.expand_dims(img_final, axis=0)

    def sayisal_veriyi_hazirla(self, veri):
        """Sayısal veriyi (1, 7) formatında float32 vektöre çevirir."""
        # Modelin datasetten öğrendiği 7 özellik ve nötr (varsayılan) değerleri:
        # [tf_id, rsi, atr_yuzde, volume_z_score, body_size, upper_wick, lower_wick]
        veri_listesi = [2.0, 50.0, 1.0, 0.0, 0.0, 0.0, 0.0] 
        
        if isinstance(veri, str) and veri.endswith('.json'):
            try:
                import json
                with open(veri, 'r') as f:
                    data = json.load(f)
                    # JSON'dan tam olarak eğitim sırasıyla verileri çekiyoruz
                    veri_listesi = [
                        float(data.get('tf_id', 2.0)),
                        float(data.get('rsi', 50.0)),
                        float(data.get('atr_yuzde', 1.0)),
                        float(data.get('volume_z_score', 0.0)),
                        float(data.get('body_size', 0.0)),
                        float(data.get('upper_wick', 0.0)),
                        float(data.get('lower_wick', 0.0))
                    ]
            except Exception as e: 
                print(f"⚠️ JSON Okuma hatası (Nötr değerler kullanılıyor): {e}")
                
        elif isinstance(veri, (list, np.ndarray)):
            # Eğer dışarıdan liste gelirse, model patlamasın diye ilk 7 elemanı alırız, 
            # eksikse nötr değerlerle tamamlarız.
            for i in range(min(len(veri), 7)):
                veri_listesi[i] = float(veri[i])
        
        # Boyutu modelin beklediği (1, 7) yapıyoruz
        return np.array(veri_listesi, dtype='float32').reshape(1, 7)

    def analiz_et(self, resim_yolu, sayisal_input=None):
        """Hem görseli hem sayısal veriyi modele LİSTE olarak gönderir."""
        if self.model is None: return None

        # 1. Giriş: Görsel Lob (224x224x3)
        gorsel_girdi = self.goruntuyu_hazirla(resim_yolu)
        if gorsel_girdi is None: return None

        # 2. Giriş: Sayısal Lob (1, 2)
        if sayisal_input is None: sayisal_input = [1.0, 0.0]
        sayisal_girdi = self.sayisal_veriyi_hazirla(sayisal_input)

        # 🔥 KRİTİK DÜZELTME: Tahmini LİSTE olarak gönder (Predictor expects a list of 2 tensors)
        try:
            # Model hibrit ise kesinlikle bu çalışır
            tahmin = self.model.predict([gorsel_girdi, sayisal_girdi], verbose=0)
            
            index = np.argmax(tahmin[0])
            guven = np.max(tahmin[0])

            return {
                "formasyon": SINIFLAR[index],
                "guven": float(guven)
            }
        except Exception as e:
            print(f"❌ Tahmin Hatası: {e}")
            return None