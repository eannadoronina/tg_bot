# Виртуальное окружение

Создать виртуальное окружение (если есть папка venv, то уже не нужно, оно уже создано)

```sh
python3 -m venv venv
```

Активировать окружение (если в терминале нет подписи venc, иначе, ненужно, оно уже активировано)

```sh
source venv/bin/activate
```

Установить необходимые библиотеки можно как обычно командой

```sh
pip install
```

Сохранить список библиотек проекта в файл `requirements.txt` можно командой

```sh
pip freeze > requirements.txt
```

Их всегда можно установить из этого файла командой

```sh
pip install -r requirements.txt
```

# Сборка и запуск

## Dev

```sh
python main.py
```

## Prod

Принудительная пересборка образа и запуск контейнера

```sh
pip freeze > requirements.txt && docker compose up -d --build --force-recreate --no-deps
```

Остановка

```sh
docker compose down
```

Просмотр запущенных контейнеров

```sh
docker ps
```
