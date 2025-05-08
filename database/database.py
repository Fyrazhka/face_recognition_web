from uuid import uuid4
from datetime import datetime
import sqlite3
import json


# Путь к базе данных
DB_PATH = "database/recognition.db"

import logging
# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("server.log", encoding="utf-8"),
        logging.StreamHandler()  # Также выводим в консоль
    ]
)
logger = logging.getLogger(__name__)

def init_db():
    """Создание таблиц, если не существуют."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица для задач распознавания
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recognition_tasks (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        result_path TEXT,
        user_key TEXT NOT NULL
    )
    ''')

    # Таблица для хранения информации о загруженных изображениях
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS task_images (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        image_path TEXT NOT NULL,
        name TEXT,
        FOREIGN KEY (task_id) REFERENCES recognition_tasks (id)
    )
    ''')

    conn.commit()
    conn.close()

def add_task(user_key: str):
    """Добавление новой задачи в базу."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    task_id = str(uuid4())
    created_at = datetime.now()

    logger.info(f"Добавляем задачу: task_id={task_id}, user_key={user_key}, created_at={created_at}")

    cursor.execute('''
        INSERT INTO recognition_tasks (id, status, created_at, user_key)
        VALUES (?, ?, ?, ?)
    ''', (task_id, 'in_progress', created_at, user_key))

    conn.commit()
    conn.close()

    logger.info(f"Задача добавлена с ID: {task_id}")

    return task_id

def add_task_image(task_id: str, image_path: str, name: str = None):
    """Добавляет информацию о загруженном изображении для задачи."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = str(uuid4())

    logger.info(f"Добавляем изображение к задаче: task_id={task_id}, image_path={image_path}, name={name}")

    cursor.execute('''
        INSERT INTO task_images (id, task_id, image_path, name)
        VALUES (?, ?, ?, ?)
    ''', (image_id, task_id, image_path, name))

    conn.commit()
    conn.close()

    logger.info(f"Добавлено изображение с ID: {image_id} к задаче {task_id}")

    return image_id

def get_task_images(task_id: str):
    """Получает список изображений, связанных с задачей."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        logger.info(f"Запрос изображений для задачи: {task_id}")
        cursor.execute('SELECT id, image_path, name FROM task_images WHERE task_id = ?', (task_id,))
        rows = cursor.fetchall()

        images = []
        for row in rows:
            images.append({
                "id": row[0],
                "image_path": row[1],
                "name": row[2]
            })

        logger.info(f"Найдено {len(images)} изображений для задачи {task_id}")
        return images
    except Exception as e:
        logger.error(f"Ошибка при запросе изображений для задачи {task_id}: {e}")
        return []
    finally:
        conn.close()

def update_task_by_user_key(user_key: str, status: str, result_path: str = None):
    """Обновление статуса задачи по ключу пользователя."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Получим ID задачи по user_key
        cursor.execute('SELECT id FROM recognition_tasks WHERE user_key = ?', (user_key,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"Задача с ключом {user_key} не найдена при обновлении статуса")
            conn.close()
            return False

        task_id = row[0]
        logger.info(f"Обновление статуса задачи: user_key={user_key}, task_id={task_id}, новый статус={status}")

        cursor.execute('''
            UPDATE recognition_tasks
            SET status = ?, result_path = ?
            WHERE user_key = ?
        ''', (status, result_path, user_key))

        conn.commit()

        # Проверим, что обновление прошло успешно
        cursor.execute('SELECT status FROM recognition_tasks WHERE user_key = ?', (user_key,))
        updated_row = cursor.fetchone()
        logger.info(f"После обновления статус задачи с ключом {user_key}: {updated_row[0] if updated_row else 'не найдено'}")

        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса задачи с ключом {user_key}: {e}")
        return False
    finally:
        conn.close()

def update_task(task_id: str, status: str, result_path: str = None):
    """Обновление статуса задачи по ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверим существование задачи
        cursor.execute('SELECT user_key FROM recognition_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"Задача с ID {task_id} не найдена при обновлении статуса")
            conn.close()
            return False

        user_key = row[0]
        logger.info(f"Обновление статуса задачи: task_id={task_id}, user_key={user_key}, новый статус={status}")

        cursor.execute('''
            UPDATE recognition_tasks
            SET status = ?, result_path = ?
            WHERE id = ?
        ''', (status, result_path, task_id))

        conn.commit()

        # Проверим, что обновление прошло успешно
        cursor.execute('SELECT status FROM recognition_tasks WHERE id = ?', (task_id,))
        updated_row = cursor.fetchone()
        logger.info(f"После обновления статус задачи {task_id}: {updated_row[0] if updated_row else 'не найдено'}")

        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса задачи {task_id}: {e}")
        return False
    finally:
        conn.close()

def get_task(user_key: str):
    """Получение информации о задаче по ключу пользователя."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        logger.info(f"Запрос информации о задаче по ключу: {user_key}")
        cursor.execute('SELECT id, status, result_path FROM recognition_tasks WHERE user_key = ?', (user_key,))
        row = cursor.fetchone()

        if row:
            logger.info(f"Найдена задача: id={row[0]}, status={row[1]}")
        else:
            logger.info(f"Задача с ключом {user_key} не найдена")

        return row
    except Exception as e:
        logger.error(f"Ошибка при запросе задачи по ключу {user_key}: {e}")
        return None
    finally:
        conn.close()

init_db()  # Создаем таблицу при запуске