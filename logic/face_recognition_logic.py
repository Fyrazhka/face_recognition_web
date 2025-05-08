import cv2
import numpy as np
from deepface.DeepFace import build_model
from deepface.detectors import FaceDetector
from datetime import datetime


class FaceRecognitionLogic:
    def __init__(self):
        self.threshold = 0.6
        self.frame_counter = 0
        self.target_embeddings = {}  # Словарь для хранения эмбеддингов лиц {image_id: embedding}
        self.target_names = {}       # Словарь для хранения имен лиц {image_id: name}
        self.model = build_model("Facenet")
        self.detector_backend = "retinaface"
        self.detector_func = FaceDetector.build_model(self.detector_backend)

    def add_target_image(self, image_path, image_id, name=None):
        """
        Добавляет изображение лица для распознавания

        Args:
            image_path (str): Путь к изображению
            image_id (str): Уникальный идентификатор изображения
            name (str, optional): Имя или метка для изображения
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Не удалось прочитать изображение: {image_path}")

        faces = FaceDetector.detect_faces(self.detector_func, self.detector_backend, img, align=True)
        if not faces:
            raise ValueError(f"Лицо не найдено в изображении: {image_path}")

        face_img = faces[0][0][0] if isinstance(faces[0][0], tuple) else faces[0][0]
        face_img = cv2.resize(face_img, (160, 160)).astype("float32") / 255
        face_img = np.expand_dims(face_img, axis=0)
        embedding = self.model.predict(face_img)[0]

        self.target_embeddings[image_id] = embedding
        self.target_names[image_id] = name if name else f"Лицо {image_id}"

        return True

    def clear_targets(self):
        """Очищает все целевые изображения"""
        self.target_embeddings = {}
        self.target_names = {}

    def recognize_in_video(self, video_path) -> str:
        """
        Распознает лица в видео и возвращает лог распознавания

        Args:
            video_path (str): Путь к видеофайлу

        Returns:
            str: Лог распознавания
        """
        if not self.target_embeddings:
            return "Ошибка: не добавлено ни одного эталонного лица"

        cap = cv2.VideoCapture(video_path)
        log_lines = []

        # Добавляем заголовок с информацией о задаче
        log_lines.append(f"Отчет о распознавании лиц от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_lines.append(f"Количество искомых лиц: {len(self.target_embeddings)}")
        log_lines.append("-" * 50)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            self.frame_counter += 1
            if self.frame_counter % 5 != 0:  # Обрабатываем каждый 5-й кадр для оптимизации
                continue

            try:
                # Получаем текущую позицию в секундах
                timestamp = round(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000, 2)

                faces = FaceDetector.detect_faces(self.detector_func, self.detector_backend, frame, align=True)
                for face, area in faces:
                    face = face[0] if isinstance(face, tuple) else face
                    resized = cv2.resize(face, (160, 160)).astype("float32") / 255
                    resized = np.expand_dims(resized, axis=0)
                    embedding = self.model.predict(resized)[0]

                    # Сравниваем со всеми целевыми лицами
                    best_match_id = None
                    best_confidence = 0

                    for image_id, target_embedding in self.target_embeddings.items():
                        distance = self.cosine_distance(target_embedding, embedding)
                        confidence = 100 - distance * 100

                        # Если уверенность выше порога и лучше предыдущих совпадений
                        if confidence > self.threshold * 100 and confidence > best_confidence:
                            best_match_id = image_id
                            best_confidence = confidence

                    # Если найдено совпадение, записываем в лог
                    if best_match_id:
                        name = self.target_names[best_match_id]
                        log_line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} - В момент {timestamp} сек: обнаружено лицо '{name}' с уверенностью {round(best_confidence, 2)}%"
                        print(log_line)
                        log_lines.append(log_line)
            except Exception as e:
                error_msg = f"Ошибка обработки кадра {self.frame_counter}: {str(e)}"
                print(error_msg)
                log_lines.append(error_msg)

        cap.release()

        # Добавляем итоговую информацию
        log_lines.append("-" * 50)
        log_lines.append(f"Обработка завершена. Всего обработано {self.frame_counter} кадров.")

        return "\n".join(log_lines)

    def cosine_distance(self, emb1, emb2):
        """Рассчитывает косинусное расстояние между двумя векторами признаков"""
        dot = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        return 1 - dot / (norm1 * norm2)
