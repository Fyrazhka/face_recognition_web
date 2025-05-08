import uuid
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Request, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.database import add_task, add_task_image, update_task_by_user_key, get_task, update_task, get_task_images
import shutil
import os
import json

from starlette.responses import RedirectResponse

from logic.face_recognition_logic import FaceRecognitionLogic

app = FastAPI()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

@app.post("/recognize/")
async def recognize_face(
        background_tasks: BackgroundTasks,
        video: UploadFile = File(...),
        images: List[UploadFile] = File(...),
        image_names: str = Form(None)  # Принимаем строку JSON с именами
):
    # Создаем временную директорию, если она не существует
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)

    task_id = str(uuid.uuid4())
    logger.info(f"Создана новая задача распознавания: {task_id}")

    # Сохраняем видеофайл
    video_path = os.path.join(temp_dir, f"{task_id}_{video.filename}")
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)
    logger.info(f"Видео сохранено по пути: {video_path}")

    # Парсим имена из JSON строки
    names_dict = {}
    if image_names:
        try:
            names_dict = json.loads(image_names)
            logger.info(f"Получены имена для изображений: {names_dict}")
        except json.JSONDecodeError:
            logger.error(f"Ошибка при парсинге JSON имен: {image_names}")

    # Создаем запись о задаче в базе данных
    add_task(user_key=task_id)

    # Сохраняем все загруженные изображения и добавляем их в базу данных
    image_paths = []
    for i, image in enumerate(images):
        image_path = os.path.join(temp_dir, f"{task_id}_{i}_{image.filename}")
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

        # Получаем имя для текущего изображения из словаря по индексу
        name = names_dict.get(str(i), None)
        if not name or name.strip() == "":
            name = f"Лицо {i+1}"

        # Добавляем информацию об изображении в базу данных
        add_task_image(task_id, image_path, name)
        image_paths.append({"path": image_path, "name": name})

        logger.info(f"Изображение сохранено: {image_path}, имя: {name}")

    # Запускаем задачу распознавания в фоновом режиме
    background_tasks.add_task(process_video_task, task_id, image_paths, video_path)

    # Перенаправляем на главную с task_id в параметрах URL
    query_string = urlencode({"task_id": task_id})
    return RedirectResponse(url=f"/?{query_string}", status_code=303)


def process_video_task(task_id, image_paths, video_path):
    try:
        logger.info(f"Начало обработки задачи {task_id}")
        os.makedirs("results", exist_ok=True)

        # Инициализируем класс распознавания
        recognizer = FaceRecognitionLogic()

        # Добавляем все целевые изображения
        for i, image_info in enumerate(image_paths):
            image_id = f"image_{i}"
            image_path = image_info["path"]
            name = image_info["name"] if image_info["name"] else f"Лицо {i+1}"

            try:
                recognizer.add_target_image(image_path, image_id, name)
                logger.info(f"Добавлено изображение {image_id} с именем '{name}'")
            except Exception as e:
                logger.error(f"Ошибка при добавлении изображения {image_path}: {e}")

        # Если нет добавленных изображений, завершаем с ошибкой
        if not recognizer.target_embeddings:
            logger.error(f"Не удалось добавить ни одного изображения для задачи {task_id}")
            update_task_by_user_key(user_key=task_id, status="error")
            return

        # Запускаем распознавание
        logger.info(f"Распознавание видео для задачи {task_id}")
        log_output = recognizer.recognize_in_video(video_path)

        # Сохраняем результат
        result_path = os.path.join("results", f"{task_id}.txt")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(log_output)

        logger.info(f"Обработка видео завершена для задачи {task_id}, обновляем статус на 'done'")
        update_task_by_user_key(user_key=task_id, status="done", result_path=result_path)
        logger.info(f"Статус задачи {task_id} обновлен на 'done'")
    except Exception as e:
        logger.error(f"Ошибка обработки {task_id}: {e}")
        update_task_by_user_key(user_key=task_id, status="error")
        logger.error(f"Статус задачи {task_id} обновлен на 'error'")
    finally:
        try:
            # Очищаем временные файлы
            for image_info in image_paths:
                image_path = image_info["path"]
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.info(f"Удален временный файл изображения: {image_path}")

            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"Удален временный файл видео: {video_path}")
        except Exception as e:
            logger.error(f"Ошибка при удалении временных файлов: {e}")


@app.get("/status/{task_id}")
async def check_status(task_id: str):
    # Используем задержку в ответе, чтобы видеть, что запрос действительно отправляется
    import time
    time.sleep(0.2)  # Задержка 200 мс для наглядности

    # task_id используется как user_key
    task = get_task(task_id)
    if not task:
        return JSONResponse({"error": "Задача не найдена"})

    task_id, status, result_path = task
    return JSONResponse({"status": status})


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    task = get_task(task_id)
    if not task or task[1] != "done" or not task[2]:
        return JSONResponse({"error": "Результат недоступен"})

    return FileResponse(task[2], media_type="text/plain", filename="результат_распознавания.txt")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, task_id: str = None):
    task_status = None
    if task_id:
        task = get_task(task_id)
        if task:
            task_status = task[1]  # Статус из базы данных
    return templates.TemplateResponse("index.html", {"request": request, "task_id": task_id, "task_status": task_status})
