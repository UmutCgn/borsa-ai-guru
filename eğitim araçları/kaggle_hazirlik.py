import shutil
import os

def kaggle_icin_paketle(kaynak_klasor="v6_dataset", cikti_adi="guru_v6_dataset"):
    print(f"📦 '{kaynak_klasor}' klasörü Kaggle için sıkıştırılıyor (Bu işlem birkaç dakika sürebilir)...")
    
    if not os.path.exists(kaynak_klasor):
        print("❌ HATA: Veri seti klasörü bulunamadı!")
        return

    # shutil.make_archive ile klasörü zip formatına çeviriyoruz
    shutil.make_archive(cikti_adi, 'zip', kaynak_klasor)
    
    zip_boyutu_mb = os.path.getsize(f"{cikti_adi}.zip") / (1024 * 1024)
    print("="*50)
    print(f"✅ İŞLEM TAMAM! Dosya Adı: {cikti_adi}.zip")
    print(f"📊 Toplam Boyut: {zip_boyutu_mb:.2f} MB")
    print("🚀 Şimdi bu .zip dosyasını Kaggle'a 'Dataset' olarak yükleyebilirsin.")
    print("="*50)

if __name__ == "__main__":
    kaggle_icin_paketle()