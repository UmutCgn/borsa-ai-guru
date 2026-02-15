# dosya: decision_engine.py
import os
from ai_module import GuruBrain # Ana beyni içeri alıyoruz

# --- AYARLAR ---
MODEL_YOLU = 'guru_v5_FINAL_B_PLAN.keras'

# Global Beyin Objeksiyonu
BEYIN = None

def modeli_baslat():
    """ai_module üzerindeki GuruBrain'i bir kez RAM'e yükler."""
    global BEYIN
    if BEYIN is None:
        print("🧠 [KARAR MOTORU] GuruBrain üzerinden başlatılıyor...")
        BEYIN = GuruBrain(MODEL_YOLU)
        if BEYIN.model is None:
            return False
    return True

def yatirim_karari_ver(formasyon_adi):
    """
    AI modülünden gelen kesin (exact) formasyon isimlerine göre yön tayin eder.
    Alt çizgi silme veya kelime içinde kelime arama (substring) hataları giderilmiştir.
    """
    # ai_module.py içindeki 55 sınıfın sadece yönü KESİN olanları listeledik.
    bullish_formasyonlar = {
        '3WHITESOLDIERS', 'DRAGONFLYDOJI', 'HAMMER', 'INVERTEDHAMMER', 
        'MORNINGDOJISTAR', 'MORNINGSTAR', 'PIERCING', 'HOMINGPIGEON', 
        'MATCHINGLOW', 'TAKURI', 'UNIQUE3RIVER'
    }
    
    bearish_formasyonlar = {
        '3BLACKCROWS', 'DARKCLOUDCOVER', 'EVENINGDOJISTAR', 'EVENINGSTAR', 
        'GRAVESTONEDOJI', 'HANGINGMAN', 'IDENTICAL3CROWS', 'SHOOTINGSTAR', 
        'ADVANCEBLOCK'
    }

    # Kümelerde (set) arama yapmak 'any()' döngüsünden çok daha hızlıdır (O(1) hızında).
    if formasyon_adi in bullish_formasyonlar:
        return "BUY 🟢 (Boğa Baskısı)"
    
    elif formasyon_adi in bearish_formasyonlar:
        return "SELL 🔴 (Ayı Baskısı)"
    
    else:
        # Geri kalanlar (ENGULFING, HARAMI, DOJI, DOJI_10_0.1 vb.)
        # Yönü mevcut trende bağlı olanlar veya tamamen nötr olan formasyonlar.
        return f"HOLD 🟡 (Nötr/Kararsız: {formasyon_adi})"

def sistemi_test_et_donuslu(resim_yolu, sayisal_vektor=None):
    """Hem görseli hem de tahta/hacim verisini GuruBrain'e gönderip nihai kararı verir."""
    if not modeli_baslat():
        return "Model Bulunamadı", 0, "ERROR"
    
    # 1. AI'dan tahmin al (Görsel + Sayısal beraber gider)
    sonuc = BEYIN.analiz_et(resim_yolu, sayisal_vektor)
    
    if sonuc is None:
        return "Okuma/Tahmin Hatası", 0, "ERROR"
        
    tespit_edilen = sonuc["formasyon"]
    guven_orani = sonuc["guven"] * 100
    
    # 2. Temel Görsel/AI Sinyali
    sinyal = yatirim_karari_ver(tespit_edilen)
    nihai_sinyal = sinyal
    
    # 3. MANTIKSAL FÜZYON (Veto Sistemi - Güvenlik Katmanı)
    if sayisal_vektor:
        dengesizlik = sayisal_vektor[0]
        hacim_deltasi = sayisal_vektor[1]
        
        if "BUY" in sinyal:
            if dengesizlik < 0.8:
                print(f"🛑 [FÜZYON] AI BUY dedi ama Tahta Zayıf ({dengesizlik:.2f}). VETO!")
                nihai_sinyal = "HOLD 🟡 (VETO EDİLDİ - Tahta Zayıf)"
                guven_orani = 0.0
            elif hacim_deltasi < -5000:
                print(f"🛑 [FÜZYON] AI BUY dedi ama Hacim Negatif ({hacim_deltasi:.0f}). VETO!")
                nihai_sinyal = "HOLD 🟡 (VETO EDİLDİ - Para Çıkışı)"
                guven_orani = 0.0
                
        elif "SELL" in sinyal:
            if dengesizlik > 1.2:
                print(f"🛑 [FÜZYON] AI SELL dedi ama Tahta Güçlü ({dengesizlik:.2f}). VETO!")
                nihai_sinyal = "HOLD 🟡 (VETO EDİLDİ - Tahta Güçlü)"
                guven_orani = 0.0
            elif hacim_deltasi > 5000:
                print(f"🛑 [FÜZYON] AI SELL dedi ama Hacim Pozitif ({hacim_deltasi:.0f}). VETO!")
                nihai_sinyal = "HOLD 🟡 (VETO EDİLDİ - Para Girişi)"
                guven_orani = 0.0

    return tespit_edilen, guven_orani, nihai_sinyal