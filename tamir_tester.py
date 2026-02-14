import os
import random
import tarfile
import cv2
import numpy as np
import tensorflow as tf
import json

def akilli_teshis_testi(model_yolu, tar_klasoru, kalici_klasor="hazir_dataset", test_edilecek_adet=100):
    print("🚀 AKILLI TEŞHİS MOTORU BAŞLATILIYOR...")
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    
    # --- 1. AKILLI ÇIKARMA SİSTEMİ (SADECE 1 KERE ÇALIŞIR) ---
    if not os.path.exists(kalici_klasor) or len(os.listdir(kalici_klasor)) == 0:
        print(f"📦 İlk çalışma tespit edildi! Dosyalar '{kalici_klasor}' klasörüne KALICI olarak çıkarılıyor (Bir daha beklemeyeceksin)...")
        os.makedirs(kalici_klasor, exist_ok=True)
        
        tar_dosyalari = [os.path.join(tar_klasoru, f) for f in os.listdir(tar_klasoru) if f.endswith('.tar')]
        for tar_yolu in tar_dosyalari:
            gercek_sinif_adi = os.path.basename(tar_yolu).replace('.tar', '')
            hedef = os.path.join(kalici_klasor, gercek_sinif_adi)
            os.makedirs(hedef, exist_ok=True)
            with tarfile.open(tar_yolu, "r") as tar: 
                tar.extractall(path=hedef)
        print("✅ Çıkarma işlemi bitti! Artık testler saniyeler sürecek.\n")
    else:
        print(f"⚡ Klasör zaten hazır ('{kalici_klasor}'). Tar işlemi atlandı, I/O hızı maksimumda!\n")

    # --- 2. TEŞHİS İÇİN HAZIRLIK ---
    model = tf.keras.models.load_model(model_yolu)
    keras_siniflari = sorted([d for d in os.listdir(kalici_klasor) if os.path.isdir(os.path.join(kalici_klasor, d))])
    
    tam_resim_yollari = []
    for root, dirs, files in os.walk(kalici_klasor):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                tam_resim_yollari.append(os.path.join(root, file))

    rastgele_test = random.sample(tam_resim_yollari, min(test_edilecek_adet, len(tam_resim_yollari)))

    dogru_orijinal = 0
    dogru_bolunmus = 0
    sayac = 0

    print("⏳ Yapay Zeka Sınava Sokuluyor (Test A ve Test B)...")

    # --- 3. İKİLİ SINAV (ÇİFT TEST) ---
    for tam_yol in rastgele_test:
        gercek_formasyon = os.path.basename(os.path.dirname(tam_yol))

        # JSON Yükle
        json_yolu = tam_yol.replace('.png', '.json')
        sayisal = [2.0, 50.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        if os.path.exists(json_yolu):
            with open(json_yolu, 'r') as f:
                d = json.load(f)
                sayisal = [float(d.get('tf_id',2)), float(d.get('rsi',50)), float(d.get('atr_yuzde',1)),
                           float(d.get('volume_z_score',0)), float(d.get('body_size',0)),
                           float(d.get('upper_wick',0)), float(d.get('lower_wick',0))]
        sayisal_arr = np.array(sayisal, dtype='float32').reshape(1, 7)

        # Görseli Yükle
        img = cv2.imread(tam_yol)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224)).astype('float32')

        # TEST A: Orijinal Ham Pikseller (0-255)
        img_arr_raw = np.expand_dims(img_resized, axis=0)
        tahmin_raw = model.predict([img_arr_raw, sayisal_arr], verbose=0)
        if keras_siniflari[np.argmax(tahmin_raw[0])] == gercek_formasyon: 
            dogru_orijinal += 1

        # TEST B: Modele 255'e bölünmüş şekilde (0-1) gidiyorsa
        img_arr_scaled = np.expand_dims(img_resized / 255.0, axis=0)
        tahmin_scaled = model.predict([img_arr_scaled, sayisal_arr], verbose=0)
        if keras_siniflari[np.argmax(tahmin_scaled[0])] == gercek_formasyon: 
            dogru_bolunmus += 1

        sayac += 1

    print("\n" + "=" * 60)
    print("🎯 TEŞHİS SONUÇLARI (Model Nerede Daha İyi Çalışıyor?)")
    print("=" * 60)
    print(f"Test A (Ham Resim 0-255 ile Başarı)    : %{(dogru_orijinal/sayac)*100:.2f}")
    print(f"Test B (/ 255.0 Bölünmüş ile Başarı)   : %{(dogru_bolunmus/sayac)*100:.2f}")
    print("=" * 60)
    print("💡 Not: Hangi test daha yüksek sonuç verdiyse, ai_module.py içindeki kodumuzu ona göre güncelleyeceğiz.")

if __name__ == "__main__":
    akilli_teshis_testi(model_yolu="guru_v5_FINAL_B_PLAN.keras", tar_klasoru="tar_paketleri", test_edilecek_adet=10000)