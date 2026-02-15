# dosya: veri_ayiklayici.py
import tarfile
import os

def tar_paketlerini_ac(kaynak_klasor="tar_paketleri", hedef_klasor="ayiklanmis_veri"):
    if not os.path.exists(hedef_klasor):
        os.makedirs(hedef_klasor)
        print(f"📂 Hedef klasör oluşturuldu: {hedef_klasor}")

    # Kaynak klasördeki tüm .tar dosyalarını bul
    dosyalar = [f for f in os.listdir(kaynak_klasor) if f.endswith('.tar')]
    
    print(f"📦 Toplam {len(dosyalar)} paket bulundu. Ayıklama başlıyor...")

    for dosya in dosyalar:
        tam_yol = os.path.join(kaynak_klasor, dosya)
        try:
            with tarfile.open(tam_yol, 'r') as tar:
                tar.extractall(path=hedef_klasor)
                print(f"✅ Çıkarıldı: {dosya}")
        except Exception as e:
            print(f"❌ HATA ({dosya}): {e}")

    print("\n🎉 Tüm paketler başarıyla ayıklandı!")

# Klasör isimlerin farklıysa burayı değiştir
# Colab'da isen "/content/drive/MyDrive/..." yollarını kullanabilirsin.
if __name__ == "__main__":
    # Eğer tar dosyaların 'tar_paketleri' klasöründeyse:
    tar_paketlerini_ac()