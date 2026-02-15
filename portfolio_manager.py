import json
import os
import threading
import time
from datetime import datetime, timedelta

DOSYA = "cuzdan.json"
# 🛡️ RLock: Aynı thread'in (Main/Telegram) kilidi birden fazla kez almasına izin verir.
dosya_kilidi = threading.RLock()

def cuzdan_yukle():
    """Her zaman taze veriyi diskten güvenle okur. Okuyamazsa sistemi korumaya alır."""
    with dosya_kilidi:
        if not os.path.exists(DOSYA):
            # Dosya gerçekten hiç yoksa (ilk kurulum) varsayılanı döndür
            return {"bakiye": 10000.0, "acik_islem": None, "islem_gecmisi": []}
        
        # Okuma için 5 deneme (Dosya o an meşgulse bekleme yapar)
        for deneme in range(5):
            try:
                with open(DOSYA, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                    # Dosya boş kalmışsa (crash anında vs.) exception'a düşmesi için kontrol
                    if not veri: raise ValueError("JSON dosyası boş!") 
                    return veri
            except Exception as e:
                print(f"⚠️ Cüzdan okuma denemesi {deneme+1}/5 başarısız: {e}")
                time.sleep(0.5) # Bekleme süresini biraz artırdık
        
        # 5 denemede de okuyamazsa ASLA 10000 varsayılanı DÖNME! Sistemi kilitle.
        print("❌ KRİTİK HATA: Cüzdan dosyası okunamıyor! Veri kaybını önlemek için varsayılan bakiye DÖNDÜRÜLMEYECEK.")
        raise RuntimeError("Cüzdan dosyası okunamadı veya bozuk. Lütfen cuzdan.json dosyasını kontrol edin.")
def cuzdan_kaydet(veri):
    """Atomic Write: Önce geçici dosyaya yazar, sonra asıl dosyayı günceller."""
    temp_dosya = DOSYA + ".tmp"
    with dosya_kilidi:
        try:
            with open(temp_dosya, "w", encoding="utf-8") as f:
                json.dump(veri, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            # Windows uyumluluğu için önce eskisini silip sonra ismini değiştiriyoruz
            if os.path.exists(DOSYA):
                os.remove(DOSYA)
            os.rename(temp_dosya, DOSYA)
        except Exception as e:
            print(f"⚠️ Kritik Yazma Hatası: {e}")
            if os.path.exists(temp_dosya): os.remove(temp_dosya)

def islem_ac(coin, fiyat, miktar, tip, sl, tp, mod, sl_yuzde, tp_yuzde):
    """
    İşlemi açar, komisyonu keser ve Slippage (Fiyat Kayması) uygular.
    """
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        if cuzdan["acik_islem"] or cuzdan["bakiye"] < miktar: return False
        
        # --- 🛡️ MALİYET VE SLIPPAGE YÖNETİMİ ---
        # Binance standart komisyonu: İşlem başına %0.1
        komisyon_orani = 0.001 
        
        # Eğer mod Kamikaze ise agresif girer (Piyasa Emri) ve %0.2 fiyat kayması (Slippage) yaşar
        # Eğer Normal mod ise Limit emir bekler ve kayma yaşamaz (Sıfır Slippage)
        slippage_orani = 0.002 if mod == "KAMIKAZE" else 0.000 
        
        # Gerçekleşen fiyata Slippage yansıtılır (Daha kötü fiyattan almış oluruz)
        gerceklesen_fiyat = fiyat * (1 + slippage_orani) if tip == "BUY" else fiyat * (1 - slippage_orani)
        
        # Komisyon peşin olarak bütçeden düşülür
        kesilen_komisyon_usd = miktar * komisyon_orani
        gercek_islem_miktari = miktar - kesilen_komisyon_usd

        # Bütçe cüzdandan düşülür
        cuzdan["bakiye"] -= miktar
        
        cuzdan["acik_islem"] = {
            "coin": coin, 
            "giris_fiyati": gerceklesen_fiyat, # Slippage yemiş kötü fiyat
            "miktar": gercek_islem_miktari,    # Komisyonu kesilmiş net miktar
            "tip": tip,
            "sl": sl, "tp": tp, 
            "sl_yuzde": sl_yuzde, "tp_yuzde": tp_yuzde,
            "mod": mod, 
            "zaman": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"💸 [Maliyet] Komisyon: {kesilen_komisyon_usd:.2f} USDT | Slippage: %{(slippage_orani*100):.2f}")
        
        cuzdan_kaydet(cuzdan)
        return True

def islem_kapat(mevcut_fiyat, sebep="OTOMATIK"):
    """İşlemi nakde çevirir, çıkış komisyonunu keser ve cüzdanı günceller."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        if not cuzdan.get("acik_islem"): return None
        islem = cuzdan["acik_islem"]
        
        # Çıkışta da Slippage yaşanabilir (Özellikle Stop-Loss patlarsa)
        slippage_orani = 0.002 if sebep == "WATCHDOG_EXIT" else 0.000
        gerceklesen_cikis = mevcut_fiyat * (1 - slippage_orani) if islem["tip"] == "BUY" else mevcut_fiyat * (1 + slippage_orani)
        
        # Kâr oranını hesapla
        kar_orani = ((gerceklesen_cikis - islem["giris_fiyati"]) / islem["giris_fiyati"]) * 100
        if islem["tip"] == "SELL": kar_orani *= -1
        
        # Brüt Kâr/Zarar
        brut_kar_zarar = (islem["miktar"] * kar_orani) / 100
        
        # --- ÇIKIŞ KOMİSYONU ---
        toplam_donen_para = islem["miktar"] + brut_kar_zarar
        cikis_komisyonu = toplam_donen_para * 0.001
        net_kar = brut_kar_zarar - cikis_komisyonu
        
        # Cüzdanı güncelle
        cuzdan["bakiye"] += (islem["miktar"] + net_kar)
        
        sonuc = {
            **islem, 
            "cikis_fiyati": gerceklesen_cikis, 
            "kar_usd": round(net_kar, 2), 
            "kapanis_zamani": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "kapanis_sebebi": sebep
        }
        
        cuzdan["islem_gecmisi"].append(sonuc)
        cuzdan["acik_islem"] = None
        cuzdan_kaydet(cuzdan)
        return sonuc

def istatistikleri_getir():
    """Son 7 günlük kar/zarar özetini döner."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        gecmis = cuzdan.get("islem_gecmisi", [])
        bir_hafta_once = datetime.now() - timedelta(days=7)
        haftalik_kar = 0.0
        for i in gecmis:
            z = i.get("kapanis_zamani")
            if z and datetime.strptime(z, '%Y-%m-%d %H:%M:%S') > bir_hafta_once:
                haftalik_kar += i.get("kar_usd", 0.0)
        kamikaze = [i for i in gecmis if i.get("mod") == "KAMIKAZE"]
        k_adet = len(kamikaze)
        k_basari = (len([i for i in kamikaze if i.get("kar_usd", 0) > 0]) / k_adet * 100) if k_adet > 0 else 0
        return round(haftalik_kar, 2), k_adet, round(k_basari, 2)

def bakiye_senkronize_et():
    # Geliştirme sürecinde sanal bakiye ile devam
    print("ℹ️ Cüzdan kontrol edildi. Sanal mod aktif.")