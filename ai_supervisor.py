# ai_supervisor.py

def denetle(islem_verisi, mevcut_fiyat, atr=0):
    """
    islem_verisi: portfolio_manager'dan gelen acik_islem sözlüğü
    mevcut_fiyat: Coin'in anlık fiyatı
    atr: O anki ATR değeri
    """
    try:
        pos = islem_verisi
        entry = pos["giris_fiyati"]
        side = pos.get("tip", "BUY") # 'BUY' veya 'SELL'
        
        # Risk birimi (Girişte belirlenen SL mesafesi)
        # sl_fiyati_ilk yoksa mevcut sl'den hesapla
        sl_ilk = pos.get("sl_fiyati_ilk", pos["sl"])
        risk_birimi = abs(entry - sl_ilk) 
        kat_edilen_mesafe = abs(mevcut_fiyat - entry)

        # 🛡️ KADEMELİ KİLİT MEKANİZMASI
        yeni_sl = pos["sl"] # Mevcut stopu koru

        # Aşama 1: Fiyat 1 Risk birimi kadar lehimize giderse -> Stopu Maliyete Çek
        if kat_edilen_mesafe >= risk_birimi:
            komisyon_payi = entry * 0.002
            breakeven_p = (entry + komisyon_payi) if side == "BUY" else (entry - komisyon_payi)
            # Stopu sadece daha iyi bir yere gidiyorsa güncelle (Geri çekme!)
            if side == "BUY": yeni_sl = max(yeni_sl, breakeven_p)
            else: yeni_sl = min(yeni_sl, breakeven_p)

        # Aşama 2: Fiyat 1.8 Risk birimi kadar giderse -> Stopu +1 Risk kâr bölgesine çek
        if kat_edilen_mesafe >= (risk_birimi * 1.8):
            kar_kilidi = (entry + (risk_birimi * 0.8)) if side == "BUY" else (entry - (risk_birimi * 0.8))
            if side == "BUY": yeni_sl = max(yeni_sl, kar_kilidi)
            else: yeni_sl = min(yeni_sl, kar_kilidi)

        # KARAR VERME
        # Stop patladı mı?
        stop_patladi = (side == "BUY" and mevcut_fiyat <= yeni_sl) or (side == "SELL" and mevcut_fiyat >= yeni_sl)
        # Kar hedefi vuruldu mu?
        tp_vuruldu = (side == "BUY" and mevcut_fiyat >= pos["tp"]) or (side == "SELL" and mevcut_fiyat <= pos["tp"])

        if tp_vuruldu: 
            return "CLOSE", "DEV KAZANÇ 🎯🎯🎯"
        if stop_patladi: 
            return "CLOSE", "SİSTEMATİK STOP 🛑"
        
        return "KEEP", yeni_sl # Pozisyonu koru, güncellenmiş stopu dön

    except Exception as e:
        print(f"⚠️ Supervisor Hatası: {e}")
        return "KEEP", islem_verisi["sl"]