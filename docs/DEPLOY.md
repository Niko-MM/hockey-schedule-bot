# Деплой бота: GitHub → сервер → БД

Пошаговая инструкция: залить код без БД на GitHub, развернуть на сервере, подтянуть существующую БД.

---

## Этап 1. Залить на GitHub (без БД)

БД уже исключена в `.gitignore` (`*.db`, `*.db-shm`, `*.db-wal`), в репозиторий не попадёт.

**На своём компьютере (в каталоге проекта):**

1. Проверить, что БД не попадёт в коммит:
   ```bash
   git status
   ```
   В списке не должно быть `rhl_zapad.db`, `rhl_zapad.db-shm`, `rhl_zapad.db-wal`.

2. Если репозиторий ещё не инициализирован:
   ```bash
   git init
   git add .
   git commit -m "Initial: hockey salary bot"
   ```

3. Подключить удалённый репозиторий (создай репозиторий на github.com заранее, без README):
   ```bash
   git remote add origin https://github.com/ВАШ_ЛОГИН/hockey_salary_bot.git
   ```

4. Залить на GitHub:
   ```bash
   git branch -M main
   git push -u origin main
   ```

При необходимости ввод логина/пароля GitHub — используй **Personal Access Token** вместо пароля (Settings → Developer settings → Personal access tokens).

---

## Этап 2. Залить на сервер из GitHub

**На сервере (по SSH):**

1. Установить Git, если ещё нет:
   ```bash
   sudo apt update && sudo apt install -y git
   ```

2. Клонировать репозиторий (подставь свой URL):
   ```bash
   cd ~
   git clone https://github.com/ВАШ_ЛОГИН/hockey_salary_bot.git
   cd hockey_salary_bot
   ```

Готово: код с GitHub лежит на сервере в `~/hockey_salary_bot` (или в выбранной папке).

---

## Этап 3. Развернуть на сервере

**На сервере в каталоге проекта (`~/hockey_salary_bot`):**

1. Установить Python 3.10+ (если нет):
   ```bash
   sudo apt install -y python3 python3-venv python3-pip
   ```

2. Создать виртуальное окружение и установить зависимости:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Создать файл `.env` в корне проекта (рядом с `bot/`, `db/`):
   ```bash
   nano .env
   ```
   Содержимое (подставь свои значения):
   ```
   BOT_TOKEN=123456:ABC...
   ADMIN_PLAYERS=123456789
   ADMIN_WORKER=0
   ADMIN_GOALKEEPER=0
   MAIN=0
   SPARE=0
   ```
   При необходимости добавь `ANCHOR_MONDAY=2026-01-06` и т.п. Сохранить: Ctrl+O, Enter, Ctrl+X.

4. Проверочный запуск (бот пока без БД — создаст пустую при первом запуске, см. этап 4):
   ```bash
   python -m bot.main
   ```
   Должно появиться `bot is working`. Остановить: Ctrl+C.

5. Запуск в фоне (чтобы бот работал после выхода из SSH):
   - Вариант А — через `nohup`:
     ```bash
     nohup python -m bot.main > bot.log 2>&1 &
     ```
     Логи: `tail -f bot.log`.
   - Вариант Б — через systemd (рекомендуется): создать файл
     ```bash
     sudo nano /etc/systemd/system/hockey-bot.service
     ```
     Содержимое (замени `YOUR_USER` на имя пользователя):
     ```ini
     [Unit]
     Description=Hockey Salary Bot
     After=network.target

     [Service]
     Type=simple
     User=YOUR_USER
     WorkingDirectory=/home/YOUR_USER/hockey_salary_bot
     ExecStart=/home/YOUR_USER/hockey_salary_bot/venv/bin/python -m bot.main
     Restart=always
     RestartSec=5

     [Install]
     WantedBy=multi-user.target
     ```
     Затем:
     ```bash
     sudo systemctl daemon-reload
     sudo systemctl enable hockey-bot
     sudo systemctl start hockey-bot
     sudo systemctl status hockey-bot
     ```

Развёртывание завершено. Если БД ещё не подтянута, при первом запуске создастся пустая БД (см. этап 4).

---

## Этап 4. Подтянуть имеющуюся БД для тестирования

Чтобы на сервере была та же БД, что на компе (игроки, расписание и т.д.):

**На своём компьютере:**

1. Остановить бота (если запущен).
2. Скопировать БД на сервер (подставь свой пользователь, хост и путь):
   ```bash
   scp rhl_zapad.db ВАШ_ПОЛЬЗОВАТЕЛЬ@IP_СЕРВЕРА:~/hockey_salary_bot/
   ```
   Пример:
   ```bash
   scp rhl_zapad.db root@123.45.67.89:~/hockey_salary_bot/
   ```

**На сервере:**

3. Убедиться, что файл на месте:
   ```bash
   cd ~/hockey_salary_bot
   ls -la rhl_zapad.db
   ```

4. Если бот уже запущен — перезапустить, чтобы подхватить БД:
   - При nohup: убить процесс (`pkill -f "python -m bot.main"`), затем снова `nohup python -m bot.main > bot.log 2>&1 &`.
   - При systemd: `sudo systemctl restart hockey-bot`.

После этого бот на сервере работает с той же БД, что была на компе — тестирование можно продолжать там.

---

## Краткая шпаргалка

| Этап | Где | Действие |
|------|-----|----------|
| 1 | Комп | `git add .` → `git commit` → `git push` (БД в .gitignore) |
| 2 | Сервер | `git clone https://github.com/.../hockey_salary_bot.git` |
| 3 | Сервер | `python3 -m venv venv` → `source venv/bin/activate` → `pip install -r requirements.txt` → создать `.env` → запуск |
| 4 | Комп → Сервер | Остановить бота на компе → `scp rhl_zapad.db user@server:~/hockey_salary_bot/` → перезапуск бота на сервере |
