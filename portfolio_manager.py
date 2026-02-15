import json
import os
import threading
import time
from datetime import datetime, timedelta

DOSYA = "cuzdan.json"
dosya_kilidi = threading.RLock()

def cuzdan_yukle():
    """Taze veriyi güvenle okur. Hata anında sistemi korumaya alır."""
    with dosya_kilidi:
        if not os.path.exists(DOSYA):
            return {"bakiye": 10000.0, "aktif_pozisyonlar": [], "islem_gecmisi": []}
        
        for deneme in range(5):
            try:
                with open(DOSYA, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                    if not veri: raise ValueError("JSON boş!")
                    # Eski tekli sistemden kalan 'acik_islem' varsa listeye çevir
                    if "acik_islem" in veri and veri["acik_islem"] is not None:
                        if "aktif_pozisyonlar" not in veri: veri["aktif_pozisyonlar"] = []
                        veri["aktif_pozisyonlar"].append(veri["acik_islem"])
                        veri["acik_islem"] = None
                    if "aktif_pozisyonlar" not in veri: veri["aktif_pozisyonlar"] = []
                    return veri
            except Exception as e:
                time.sleep(0.5)
        
        raise RuntimeError("Cüzdan dosyası okunamadı veya bozuk!")

def cuzdan_kaydet(veri):
    """Atomic Write: Önce geçici dosyaya yazar, sonra asıl dosyayı günceller."""
    temp_dosya = DOSYA + ".tmp"
    with dosya_kilidi:
        try:
            with open(temp_dosya, "w", encoding="utf-8") as f:
                json.dump(veri, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(DOSYA): os.remove(DOSYA)
            os.rename(temp_dosya, DOSYA)
        except Exception as e:
            print(f"⚠️ Kritik Yazma Hatası: {e}")

def bu_coin_acik_mi(coin):
    """Aynı coine iki kere girilmesini engeller."""
    cuzdan = cuzdan_yukle()
    return any(p["coin"] == coin for p in cuzdan.get("aktif_pozisyonlar", []))

def islem_ac(coin, fiyat, miktar, tip, sl, tp, mod, sl_yuzde, tp_yuzde, sl_ilk):
    """Yeni bir pozisyonu listeye ekler (Maksimum 5 işlem)."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        pozisyonlar = cuzdan.get("aktif_pozisyonlar", [])
        
        # EMNİYET KONTROLLERİ
        if len(pozisyonlar) >= 5: return False # 5 işlem sınırı
        if bu_coin_acik_mi(coin): return False # Aynı coin kontrolü
        if cuzdan["bakiye"] < miktar: return False # Bakiye kontrolü
        
        # --- MALİYET VE SLIPPAGE ---
        komisyon_orani = 0.001 
        slippage_orani = 0.002 if mod == "KAMIKAZE" else 0.000 
        
        gerceklesen_fiyat = fiyat * (1 + slippage_orani) if tip == "BUY" else fiyat * (1 - slippage_orani)
        kesilen_komisyon_usd = miktar * komisyon_orani
        gercek_islem_miktari = miktar - kesilen_komisyon_usd

        cuzdan["bakiye"] -= miktar
        
        yeni_islem = {
            "coin": coin, 
            "giris_fiyati": gerceklesen_fiyat,
            "miktar": gercek_islem_miktari,
            "tip": tip,
            "sl": sl, "tp": tp, 
            "sl_fiyati_ilk": sl_ilk, # Supervisor için kritik
            "sl_yuzde": sl_yuzde, "tp_yuzde": tp_yuzde,
            "mod": mod, 
            "zaman": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        cuzdan["aktif_pozisyonlar"].append(yeni_islem)
        print(f"💸 [Multi-Sniper] {coin} Girildi | Komisyon: {kesilen_komisyon_usd:.2f} USDT")
        
        cuzdan_kaydet(cuzdan)
        return True

def islem_kapat(coin, mevcut_fiyat, sebep="OTOMATIK"):
    """Belirli bir coini listeden bulur, kapatır ve nakde döner."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        pozisyonlar = cuzdan.get("aktif_pozisyonlar", [])
        
        hedef_islem = next((p for p in pozisyonlar if p["coin"] == coin), None)
        if not hedef_islem: return None

        # --- ÇIKIŞ HESAPLAMA ---
        slippage_orani = 0.002 if sebep == "WATCHDOG_EXIT" else 0.000
        gerceklesen_cikis = mevcut_fiyat * (1 - slippage_orani) if hedef_islem["tip"] == "BUY" else mevcut_fiyat * (1 + slippage_orani)
        
        kar_orani = ((gerceklesen_cikis - hedef_islem["giris_fiyati"]) / hedef_islem["giris_fiyati"]) * 100
        if hedef_islem["tip"] == "SELL": kar_orani *= -1
        
        brut_kar_zarar = (hedef_islem["miktar"] * kar_orani) / 100
        toplam_donen = hedef_islem["miktar"] + brut_kar_zarar
        cikis_komisyonu = toplam_donen * 0.001
        net_kar = brut_kar_zarar - cikis_komisyonu
        
        cuzdan["bakiye"] += (hedef_islem["miktar"] + net_kar)
        
        sonuc = {
            **hedef_islem, 
            "cikis_fiyati": gerceklesen_cikis, 
            "kar_usd": round(net_kar, 2), 
            "kapanis_zamani": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "kapanis_sebebi": sebep
        }
        
        cuzdan["islem_gecmisi"].append(sonuc)
        cuzdan["aktif_pozisyonlar"] = [p for p in pozisyonlar if p["coin"] != coin]
        
        cuzdan_kaydet(cuzdan)
        return sonuc

def sl_guncelle(coin, yeni_sl):
    """Listedeki bir coinin stop loss değerini günceller."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        for p in cuzdan["aktif_pozisyonlar"]:
            if p["coin"] == coin:
                p["sl"] = yeni_sl
                cuzdan_kaydet(cuzdan)
                return True
    return False

def is_islem_var():
    """Herhangi bir açık işlem olup olmadığını kontrol eder."""
    cuzdan = cuzdan_yukle()
    return len(cuzdan.get("aktif_pozisyonlar", [])) > 0

def kasa_durumu_kontrol(baslangic_bakiyesi, hedef_kar_orani, max_zarar_orani):
    """Toplam varlığı (Nakit + İşlemdekiler) hesaplar ve limiti kontrol eder."""
    cuzdan = cuzdan_yukle()
    nakit = cuzdan.get("bakiye", 0)
    islemdekiler = sum(p["miktar"] for p in cuzdan.get("aktif_pozisyonlar", []))
    toplam_varlik = nakit + islemdekiler
    
    if toplam_varlik >= baslangic_bakiyesi * (1 + hedef_kar_orani / 100):
        return "TARGET_REACHED", toplam_varlik
    if toplam_varlik <= baslangic_bakiyesi * (1 - max_zarar_orani / 100):
        return "MAX_LOSS_REACHED", toplam_varlik
        
    return "OK", toplam_varlik

def istatistikleri_getir():
    """Tüm geçmiş üzerinden genel başarı oranını döner."""
    with dosya_kilidi:
        cuzdan = cuzdan_yukle()
        gecmis = cuzdan.get("islem_gecmisi", [])
        bir_hafta_once = datetime.now() - timedelta(days=7)
        haftalik_kar = sum(i.get("kar_usd", 0.0) for i in gecmis if datetime.strptime(i["kapanis_zamani"], '%Y-%m-%d %H:%M:%S') > bir_hafta_once)
        
        kamikaze = [i for i in gecmis if i.get("mod") == "KAMIKAZE"]
        k_basari = (len([i for i in kamikaze if i.get("kar_usd", 0) > 0]) / len(kamikaze) * 100) if kamikaze else 0
        
        return round(haftalik_kar, 2), len(kamikaze), round(k_basari, 2)


def aktif_islem_sayisi():
    """Kaç tane açık pozisyon olduğunu sayar."""
    cuzdan = cuzdan_yukle()
    return len(cuzdan.get("aktif_pozisyonlar", []))