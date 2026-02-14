# dosya: hafiza_yoneticisi.py
import json
import os
import datetime

DOSYA_ADI = "islem_gecmisi.json"

def gecmisi_yukle():
    if not os.path.exists(DOSYA_ADI):
        return []
    try:
        with open(DOSYA_ADI, 'r') as f:
            return json.load(f)
    except:
        return []

def islem_kaydet(formasyon, karar, fiyat=0):
    gecmis = gecmisi_yukle()
    
    yeni_kayit = {
        "tarih": str(datetime.datetime.now()),
        "formasyon": formasyon,
        "karar": karar,
        "fiyat": fiyat
    }
    
    gecmis.append(yeni_kayit)
    
    with open(DOSYA_ADI, 'w') as f:
        json.dump(gecmis, f, indent=4)
    print(f"💾 İşlem hafızaya kaydedildi: {karar} -> {formasyon}")

def son_islem_neydi():
    gecmis = gecmisi_yukle()
    if not gecmis: return "YOK"
    return gecmis[-1]["karar"]