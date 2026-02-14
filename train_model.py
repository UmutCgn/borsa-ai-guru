import tensorflow as tf
from tensorflow.keras import layers, models

# ÖNEMLİ: MobileNet renkli resim bekler, dataseti RGB (color) yükleyelim
train_ds = tf.keras.utils.image_dataset_from_directory(
    "dataset",
    validation_split=0.2,
    subset="training",
    seed=123,
    image_size=(224, 224), # MobileNet standardı
    batch_size=32
)

val_ds = tf.keras.utils.image_dataset_from_directory(
    "dataset",
    validation_split=0.2,
    subset="validation",
    seed=123,
    image_size=(224, 224),
    batch_size=32
)

# 1. Hazır Modeli Yükle (Google'ın beyni)
base_model = tf.keras.applications.MobileNetV2(
    input_shape=(224, 224, 3), 
    include_top=False, 
    weights='imagenet'
)
base_model.trainable = False # Hazır bilgileri bozma

# 2. Üzerine Kendi "Borsa Uzmanı" Katmanını Ekle
model = models.Sequential([
    base_model,
    layers.GlobalAveragePooling2D(),
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.2),
    layers.Dense(len(train_ds.class_names), activation='softmax')
])

model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

# 3. Eğit
model.fit(train_ds, validation_data=val_ds, epochs=20)
model.save('borsa_uzmani_guru_v4.keras')