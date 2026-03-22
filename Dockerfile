FROM python:3.11-alpine

WORKDIR /app

# Устанавливаем переменные окружения для Python
# PYTHONDONTWRITEBYTECODE - не создает .pyc файлы
# PYTHONUNBUFFERED - вывод логов сразу в консоль (без буферизации)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Копируем весь код проекта
COPY . .
    
# Устанавливаем зависимости Python
# --no-cache-dir - не сохранять кэш pip
# --default-timeout - увеличиваем таймаут для медленных соединений
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Команда запуска бота
CMD ["python", "main.py"]