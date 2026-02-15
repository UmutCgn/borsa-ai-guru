import os
import cv2
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, Model
from tensorflow.keras.callbacks import ModelCheckpoint, ReduceLROnPlateau, EarlyStopping
from sklearn.model_selection import train_test_split

# --- AYARLAR ---
DATASET_YOLU = "v6_dataset"  # Klasör ismin farklıysa burayı düzelt
SINIFLAR = ["BUY", "HOLD", "SELL"] # 0, 1, 2
BATCH_SIZE = 32
EPOCHS = 40

# --- 1. VERİ JENERATÖRÜ (RAM Çökmesini Önler) ---
class GuruDataGenerator(tf.keras.utils.Sequence):
    def __init__(self, resim_yollari, sayisal_veriler, etiketler, batch_size=32):
        self.resim_yollari = resim_yollari
        self.sayisal_veriler = np.array(sayisal_veriler, dtype="float32")
        self.etiketler = np.array(etiketler, dtype="int32")
        self.batch_size = batch_size

    def __len__(self):
        return int(np.ceil(len(self.resim_yollari) / float(self.batch_size)))

    def __getitem__(self, idx):
        low = idx * self.batch_size
        high = min(low + self.batch_size, len(self.resim_yollari))
        
        batch_x_yol = self.resim_yollari[low:high]
        batch_x_say = self.sayisal_veriler[low:high]
        batch_y = self.etiketler[low:high]
        
        X_resim = []
        for yol in batch_x_yol:
            img = cv2.imread(yol)
            img = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (224, 224)) / 255.0
            X_resim.append(img)
            
        return {"gorsel_input": np.array(X_resim, dtype="float32"), 
                "sayisal_input": batch_x_say}, batch_y

# --- 2. VERİ SETİNİ TARAMA ---
def verileri_hazirla():
    print(f"🔍 {DATASET_YOLU} taranıyor...")
    resim_yollari, sayisal_veriler, etiketler = [], [], []
    
    for i, sinif in enumerate(SINIFLAR):
        klasor = os.path.join(DATASET_YOLU, sinif)
        if not os.path.exists(klasor): continue
            
        for dosya in os.listdir(klasor):
            if dosya.endswith(".png"):
                img_yol = os.path.join(klasor, dosya)
                json_yol = img_yol.replace('.png', '.json')
                
                if os.path.exists(json_yol):
                    with open(json_yol, 'r') as f:
                        d = json.load(f)
                        # 7 Lob Parametresi (Normalizasyon dahil)
                        sayisal = [
                            float(d.get('tf_id', 2.0)), 
                            float(d.get('rsi', 50.0)) / 100.0, 
                            float(d.get('atr_yuzde', 1.0)),
                            float(d.get('volume_z_score', 0.0)), 
                            float(d.get('body_size', 0.0)),
                            float(d.get('upper_wick', 0.0)), 
                            float(d.get('lower_wick', 0.0))
                        ]
                    resim_yollari.append(img_yol)
                    sayisal_veriler.append(sayisal)
                    etiketler.append(i)
    return np.array(resim_yollari), np.array(sayisal_veriler), np.array(etiketler)

# --- 3. HİBRİT MODEL MİMARİSİ ---
def modeli_insa_et():
    # GÖRSEL LOB
    gorsel_in = layers.Input(shape=(224, 224, 3), name="gorsel_input")
    base_model = tf.keras.applications.MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='imagenet')
    
    # Fine-tuning: Son 30 katmanı aç
    base_model.trainable = True
    for layer in base_model.layers[:-30]: layer.trainable = False

    x = layers.GlobalAveragePooling2D()(base_model(gorsel_in))
    x = layers.BatchNormalization()(x)
    gorsel_out = layers.Dense(128, activation='relu')(x)

    # SAYISAL LOB
    sayisal_in = layers.Input(shape=(7,), name="sayisal_input")
    y = layers.Dense(64, activation='relu')(sayisal_in)
    sayisal_out = layers.Dense(32, activation='relu')(y)

    # FÜZYON
    birlesik = layers.concatenate([gorsel_out, sayisal_out])
    z = layers.Dense(128, activation='relu')(birlesik)
    z = layers.Dropout(0.4)(z)
    final_cikis = layers.Dense(3, activation='softmax', name="karar_cikisi")(z)

    model = Model(inputs=[gorsel_in, sayisal_in], outputs=final_cikis)
    model.compile(optimizer=tf.keras.optimizers.Adam(0.0005), 
                  loss='sparse_categorical_crossentropy', 
                  metrics=['accuracy'])
    return model

# --- 4. EĞİTİM DÖNGÜSÜ ---
if __name__ == "__main__":
    yollar, sayisallar, etiketler = verileri_hazirla()
    print(f"📊 Toplam Örnek: {len(etiketler)}")
    
    XR_train, XR_test, XS_train, XS_test, Y_train, Y_test = train_test_split(
        yollar, sayisallar, etiketler, test_size=0.2, random_state=42, stratify=etiketler
    )
    
    train_gen = GuruDataGenerator(XR_train, XS_train, Y_train, batch_size=BATCH_SIZE)
    test_gen = GuruDataGenerator(XR_test, XS_test, Y_test, batch_size=BATCH_SIZE)
    
    model = modeli_insa_et()
    
    # Callback Mekanizmaları
    callbacks = [
        ModelCheckpoint('guru_v6_HYBRID.keras', monitor='val_accuracy', save_best_only=True, verbose=1),
        ReduceLROnPlateau(monitor='val_accuracy', factor=0.5, patience=3, min_lr=0.00001, verbose=1),
        EarlyStopping(monitor='val_accuracy', patience=8, restore_best_weights=True, verbose=1)
    ]

    print("\n🚀 LOCAL EĞİTİM BAŞLIYOR...")
    model.fit(train_gen, validation_data=test_gen, epochs=EPOCHS, callbacks=callbacks)
    print("\n🏆 İşlem Tamam! 'guru_v6_HYBRID.keras' hazır.")