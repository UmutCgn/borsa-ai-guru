import os
import tarfile

def multi_modal_sharding():
    dataset_yolu = "dataset"
    cikti_yolu = "tar_paketleri"
    
    if not os.path.exists(cikti_yolu): os.makedirs(cikti_yolu)
    
    # 70+ Formasyon klasörünü tek tek gez
    formasyonlar = os.listdir(dataset_yolu)
    
    for f in formasyonlar:
        f_yolu = os.path.join(dataset_yolu, f)
        if not os.path.isdir(f_yolu): continue
        
        print(f"📦 {f} formasyonu paketleniyor...")
        tar_adi = os.path.join(cikti_yolu, f"{f}.tar")
        
        with tarfile.open(tar_adi, "w") as tar:
            # Klasördeki tüm dosyaları listele
            dosyalar = os.listdir(f_yolu)
            
            # Sadece PNG'leri bul, sonra JSON ikizlerini kontrol et
            png_dosyalari = [d for d in dosyalar if d.endswith('.png')]
            
            for png in png_dosyalari:
                base_name = os.path.splitext(png)[0]
                json_dosyasi = f"{base_name}.json"
                
                png_tam_yol = os.path.join(f_yolu, png)
                json_tam_yol = os.path.join(f_yolu, json_dosyasi)
                
                # KRİTİK KONTROL: Eğer ikizi yoksa pakete ekleme!
                if os.path.exists(json_tam_yol):
                    # PNG'yi ekle
                    tar.add(png_tam_yol, arcname=png)
                    # JSON'u ekle
                    tar.add(json_tam_yol, arcname=json_dosyasi)
                else:
                    print(f"⚠️ HATA: {png} dosyasının JSON ikizi bulunamadı! Atlanıyor.")

    print("\n✅ Tüm \"ikizler\" güvenle tar paketlerine yerleştirildi. Kayma riski sıfır!")

if __name__ == "__main__":
    multi_modal_sharding()