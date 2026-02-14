import os
import random
import tarfile
import shutil
from ai_module import GuruBrain

def hizli_test_tar(model_yolu, tar_klasoru, test_edilecek_adet=100):
    print("🚀 Hızlı Test Motoru (TAR MODU) Başlatılıyor...")
    
    beyin = GuruBrain(model_yolu)
    if beyin.model is None:
        return

    if not os.path.exists(tar_klasoru):
        print(f"❌ HATA: '{tar_klasoru}' klasörü bulunamadı!")
        return

    # Geçici bir test klasörü oluşturuyoruz
    temp_klasor = "temp_test_veri"
    if os.path.exists(temp_klasor):
        shutil.rmtree(temp_klasor)
    os.makedirs(temp_klasor)

    print(f"📦 '{tar_klasoru}' içindeki .tar dosyaları sınıflandırılarak çıkartılıyor...")
    
    tar_dosyalari = [os.path.join(tar_klasoru, f) for f in os.listdir(tar_klasoru) if f.endswith('.tar')]
    
    if not tar_dosyalari:
        print("❌ HATA: Hiç .tar dosyası bulunamadı!")
        shutil.rmtree(temp_klasor)
        return

    # 🔑 KRİTİK DÜZELTME: Her tar dosyasını KENDİ ADINI TAŞIYAN bir alt klasöre çıkarıyoruz
    for tar_yolu in tar_dosyalari:
        # Örn: 'tar_paketleri/HARAMI.tar' -> 'HARAMI'
        gercek_sinif_adi = os.path.basename(tar_yolu).replace('.tar', '') 
        hedef_klasor = os.path.join(temp_klasor, gercek_sinif_adi)
        os.makedirs(hedef_klasor, exist_ok=True)
        
        try:
            with tarfile.open(tar_yolu, "r") as tar:
                tar.extractall(path=hedef_klasor)
        except Exception as e:
            print(f"⚠️ Hata ({tar_yolu}): {e}")

    # Çıkartılan resimleri bul
    tam_resim_yollari = []
    for root, dirs, files in os.walk(temp_klasor):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                tam_resim_yollari.append(os.path.join(root, file))

    if not tam_resim_yollari:
        print("❌ HATA: Çıkartılan tar dosyalarında resim bulunamadı!")
        shutil.rmtree(temp_klasor)
        return

    print(f"📂 Toplam {len(tam_resim_yollari)} grafik başarıyla çıkartıldı. Sınav başlıyor...\n")
    
    rastgele_test_grubu = random.sample(tam_resim_yollari, min(test_edilecek_adet, len(tam_resim_yollari)))
    
    sayac = 0
    dogru_bilinen = 0

    # SINAV DÖNGÜSÜ
    for tam_yol in rastgele_test_grubu:
        dosya_adi = os.path.basename(tam_yol)
        
        # 🔑 DÜZELTME: Gerçek sınıf adını oluşturduğumuz klasör isminden güvenle çekiyoruz
        yol_parcalari = tam_yol.split(os.sep)
        temp_index = yol_parcalari.index(temp_klasor)
        gercek_formasyon = yol_parcalari[temp_index + 1] 
        
        json_yolu = tam_yol.replace('.png', '.json')
        sayisal_girdi = json_yolu if os.path.exists(json_yolu) else [2.0, 50.0, 1.0, 0.0, 0.0, 0.0, 0.0] 
            
        sonuc = beyin.analiz_et(tam_yol, sayisal_girdi)
            
        if sonuc is not None:
            tahmin = sonuc['formasyon']
            
            if gercek_formasyon == tahmin:
                dogru_bilinen += 1
                durum = "✅ DOĞRU"
            else:
                durum = "❌ YANLIŞ"

            print(f"Gerçek: {gercek_formasyon:<15} | Tahmin: {tahmin:<15} | {durum} (Güven: %{sonuc['guven']*100:.1f})")
            sayac += 1

    # KARNE HESAPLAMASI
    if sayac > 0:
        basari_orani = (dogru_bilinen / sayac) * 100
        print("\n" + "=" * 50)
        print("📊 SİSTEM KARNESİ (TAR DOSYALARI)")
        print("=" * 50)
        print(f"📝 Test Edilen: {sayac} Grafik")
        print(f"🎯 Doğru Sayısı: {dogru_bilinen}")
        print(f"🏆 Başarı Oranı: %{basari_orani:.2f}")
        print("=" * 50)

    print("\n🧹 Geçici test dosyaları temizleniyor...")
    shutil.rmtree(temp_klasor)
    print("✨ İşlem tamam!")

if __name__ == "__main__":
    hizli_test_tar(model_yolu="guru_v5_FINAL_B_PLAN.keras", tar_klasoru="tar_paketleri", test_edilecek_adet=100)