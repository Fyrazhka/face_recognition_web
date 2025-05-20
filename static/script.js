document.addEventListener('DOMContentLoaded', function() {
    // Инициализация формы загрузки изображений
    initImageUpload();

    // Добавляем обработчик события для формы проверки статуса
    document.getElementById('status_form').addEventListener('submit', checkStatus);

    // Проверяем, есть ли оригинальный ключ задачи
    const originalTaskIdElement = document.getElementById('original_task_id');
    if (originalTaskIdElement) {
        const originalTaskId = originalTaskIdElement.textContent;

        // Если есть оригинальный ключ, добавляем его в поле ввода
        if (originalTaskId) {
            document.getElementById('task_id_input').value = originalTaskId;

            // Проверяем статус для этого ключа
            checkStatusAgain();
        }
    }
});

function initImageUpload() {
    const imagesInput = document.getElementById('images-input');
    const imagesContainer = document.getElementById('images-container');
    const namesContainer = document.getElementById('names-container');

    // Добавляем обработчик события изменения выбранных файлов
    imagesInput.addEventListener('change', function(event) {
        // Очищаем контейнеры
        imagesContainer.innerHTML = '';
        namesContainer.innerHTML = '';

        if (this.files.length > 0) {
            const imagesList = document.createElement('div');
            imagesList.className = 'images-list';
            imagesContainer.appendChild(imagesList);

            // Добавляем заголовок для списка имен
            const namesHeader = document.createElement('div');
            namesHeader.className = 'names-header';
            namesHeader.textContent = 'Укажите имена/метки для загруженных изображений (необязательно):';
            namesContainer.appendChild(namesHeader);

            // Создаем скрытое поле для передачи имен в формате JSON
            const namesInput = document.createElement('input');
            namesInput.type = 'hidden';
            namesInput.name = 'image_names';
            namesInput.id = 'image-names-input';
            namesContainer.appendChild(namesInput);

            // Добавляем контейнер для имен
            const namesList = document.createElement('div');
            namesList.className = 'names-list';
            namesContainer.appendChild(namesList);

            // Обрабатываем каждый выбранный файл
            Array.from(this.files).forEach((file, index) => {
                // Создаем элемент для превью изображения
                const imageItem = document.createElement('div');
                imageItem.className = 'image-item';

                const imagePreview = document.createElement('div');
                imagePreview.className = 'image-preview';

                // Создаем превью изображения
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                img.onload = function() {
                    URL.revokeObjectURL(this.src); // Освобождаем память
                };
                imagePreview.appendChild(img);

                const imageLabel = document.createElement('div');
                imageLabel.className = 'image-label';
                imageLabel.textContent = `Изображение ${index + 1}: ${file.name}`;

                imageItem.appendChild(imagePreview);
                imageItem.appendChild(imageLabel);
                imagesList.appendChild(imageItem);

                // Создаем поле для ввода имени
                const nameItem = document.createElement('div');
                nameItem.className = 'name-item';

                const nameLabel = document.createElement('label');
                nameLabel.textContent = `Имя для изображения ${index + 1}:`;
                nameLabel.htmlFor = `name-input-${index}`;

                const nameInput = document.createElement('input');
                nameInput.type = 'text';
                nameInput.id = `name-input-${index}`;
                nameInput.placeholder = `Например: Иван, Мария и т.д.`;
                nameInput.dataset.index = index;
                nameInput.addEventListener('input', updateNamesField);

                nameItem.appendChild(nameLabel);
                nameItem.appendChild(nameInput);
                namesList.appendChild(nameItem);
            });
        }
    });
}

function updateNamesField() {
    // Создаем объект для хранения имен по индексам
    const namesObj = {};

    // Собираем все имена из полей ввода с их индексами
    const nameInputs = document.querySelectorAll('[id^=name-input-]');
    nameInputs.forEach(input => {
        const index = input.dataset.index;
        const value = input.value.trim();
        if (value) {
            namesObj[index] = value;
        }
    });

    // Обновляем скрытое поле с именами в формате JSON
    const namesInput = document.getElementById('image-names-input');
    namesInput.value = JSON.stringify(namesObj);
}

// Глобальная переменная для отслеживания статуса задачи
let taskStatusIsInProgress = false;
// Идентификатор таймера для возможности его отмены
let statusCheckTimer = null;

async function checkStatus(event) {
    if (event) {
        event.preventDefault();
    }

    const taskId = document.getElementById('task_id_input').value;
    if (!taskId) {
        alert('Пожалуйста, введите ключ задачи');
        return;
    }

    const statusElement = document.getElementById('status_result');
    statusElement.innerHTML = '<p class="progress-text">Проверка статуса...</p>';

    try {
        // Добавляем timestamp для предотвращения кеширования
        const timestamp = new Date().getTime();
        const response = await fetch(`/status/${taskId}?_=${timestamp}`);

        if (!response.ok) {
            throw new Error(`HTTP ошибка! Статус: ${response.status}`);
        }

        const data = await response.json();

        // Очищаем предыдущий таймер, если он был установлен
        if (statusCheckTimer) {
            clearTimeout(statusCheckTimer);
            statusCheckTimer = null;
        }

        if (data.error) {
            taskStatusIsInProgress = false;
            statusElement.innerHTML = `<p class="error-text">Ошибка: ${data.error}</p>`;
        } else if (data.status === "done") {
            taskStatusIsInProgress = false;
            statusElement.innerHTML = `<p class="success-text">Статус задачи: <strong>Завершена</strong></p>
                                      <a href="/download/${taskId}" class="download-btn">Скачать результат</a>`;
        } else if (data.status === "error") {
            taskStatusIsInProgress = false;
            statusElement.innerHTML = `<p class="error-text">Статус задачи: <strong>Ошибка</strong></p>
                                      <p class="error-details">Произошла ошибка при обработке задачи. Попробуйте загрузить другие файлы.</p>`;
        } else if (data.status === "in_progress") {
            taskStatusIsInProgress = true;
            statusElement.innerHTML = `<p class="progress-text">Статус задачи: <strong>В процессе</strong></p>
                                      <p>Обработка может занять несколько минут в зависимости от размера видео.</p>
                                      <button onclick="checkStatusAgain()" class="refresh-btn">Проверить снова</button>`;

            // Запускаем автоматическую проверку статуса через 60 секунд только если задача еще в процессе
            statusCheckTimer = setTimeout(checkStatusAgain, 60000);
        } else {
            taskStatusIsInProgress = false;
            statusElement.innerHTML = `<p>Статус задачи: <strong>${data.status}</strong></p>`;
        }
    } catch (error) {
        console.error('Ошибка при проверке статуса:', error);
        statusElement.innerHTML = '<p class="error-text">Ошибка при проверке статуса</p>';
        taskStatusIsInProgress = false;
    }
}

function checkStatusAgain() {
    // Проверяем статус только если задача еще в процессе обработки
    // или если функция вызвана напрямую (например, по нажатию кнопки)
    checkStatus();
}

// Добавляем обработчик для новой формы распознавания
document.addEventListener('DOMContentLoaded', function() {
    // Сброс статуса при отправке новой формы распознавания
    const recognizeForm = document.getElementById('recognize_form');
    if (recognizeForm) {
        recognizeForm.addEventListener('submit', function() {
            // Сбрасываем статус отслеживания задачи при начале новой
            taskStatusIsInProgress = false;
            // Очищаем таймер, если он был установлен
            if (statusCheckTimer) {
                clearTimeout(statusCheckTimer);
                statusCheckTimer = null;
            }
        });
    }
});