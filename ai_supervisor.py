# ai_supervisor.py

class AISupervisor:
    def __init__(self, ana_aralik=2.5): # Aralığı %2.5'e çekerek biraz daha nefes payı verdik
        """
        ana_aralik: Maksimum izin verilen temel zarar yüzdesi.
        """
        self.max_zarar = ana_aralik

    def denetle(self, mevcut_pnl, ai_guven, atr_p_ratio):
        """
        mevcut_pnl: % cinsinden PnL (Örn: -1.2 veya 0.5)
        ai_guven: AI'nın yön için güven skoru (0.0 - 1.0)
        atr_p_ratio: ATR / Fiyat * 100 (Oynaklık çarpanı)
        """
        
        # 1. SENARYO: AI ÇOK EMİN (%75 ÜZERİ) -> "GENİŞ ALAN"
        if ai_guven >= 0.75:
            # Model çok eminse, gürültüden (noise) etkilenmemek için tam stop mesafesi ver.
            aktif_stop = -self.max_zarar
            aksiyon = "GÜÇLÜ (Esnek)"
            
        # 2. SENARYO: AI KARARSIZ (%40 - %75 ARASI) -> "DARALTILMIŞ STOP"
        elif 0.40 <= ai_guven < 0.75:
            # AI biraz şüpheli. Stopu maliyete yaklaştır ama hemen çıkma.
            # En az %1.0 veya max_zararın %40'ı kadar stop bırak.
            aktif_stop = -max(1.0, self.max_zarar * 0.4)
            aksiyon = "İZLEMEDE (Dar SL)"

        # 3. SENARYO: AI GÜVENİ ÇÖKTÜ (%40 ALTI) -> "ACİL ÇIKIŞ"
        else:
            # Eskiden 0.0 idi (yani hemen çıkış), şimdi ufak bir (-0.3%) pay bırakıyoruz 
            # ki ufak toparlanmada en azından komisyon çıksın.
            aktif_stop = -0.3
            aksiyon = "PANİK (Acil Çıkış)"

        # 4. VOLATİLİTEYE GÖRE TRAILING (Kâr Koruma)
        # Sadece %1.2 kâra geçince değil, volatiliteye (ATR) göre stopu sürükle
        if mevcut_pnl > 1.2:
            # Oynaklık ne kadar fazlaysa, trailing stop o kadar uzaktan takip eder (1.5 katı)
            trail_distance = max(0.6, atr_p_ratio * 1.5)
            yeni_stop = mevcut_pnl - trail_distance
            aktif_stop = max(aktif_stop, yeni_stop)
            aksiyon = "TAKİPTE (Trailing)"

        # Karar Verme
        if mevcut_pnl <= aktif_stop:
            return "CLOSE", aktif_stop, aksiyon
        else:
            return "KEEP", aktif_stop, aksiyon