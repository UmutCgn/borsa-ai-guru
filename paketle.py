import shutil
import os

def veriyi_hazirla(kaynak="v6_dataset", cikti="guru_v6_final"):
    if not os.path.exists(kaynak):
        print(f"❌ HATA: {kaynak} klasörü bulunamadı!")
        return
    
    print(f"📦 {kaynak} paketleniyor... (Lütfen bekleyin)")
    shutil.make_archive(cikti, 'zip', kaynak)
    print(f"✅ BİTTİ! '{cikti}.zip' dosyasını Kaggle'a 'Dataset' olarak yükleyebilirsin.")

if __name__ == "__main__":
    veriyi_hazirla()