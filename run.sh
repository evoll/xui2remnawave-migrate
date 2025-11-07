#!/bin/bash
# -------------------------------------------
# Интерактивная оболочка для xui2remnawave_migrate.py
# -------------------------------------------

clear
echo "==============================================="
echo " 🚀  Миграция пользователей 3x-UI → Remnawave "
echo "==============================================="

echo ""
read -p "Источник данных (1 - JSON файл, 2 - 3x-UI логин/пароль) [2]: " SOURCE_CHOICE
SOURCE_CHOICE=${SOURCE_CHOICE:-2}

if [[ "$SOURCE_CHOICE" == "1" ]]; then
    read -p "Введите путь к config.json [./config.json]: " XUI_CONFIG_PATH
    XUI_CONFIG_PATH=${XUI_CONFIG_PATH:-"./config.json"}
    export SOURCE="file"
    export XUI_CONFIG_PATH="$XUI_CONFIG_PATH"
else
    echo ""
    echo "=== Подключение к 3x-UI ==="
    read -p "URL панели 3x-UI (например https://xui.example.com): " XUI_URL
    read -p "Имя пользователя: " XUI_USERNAME
    read -s -p "Пароль: " XUI_PASSWORD
    echo ""
    export SOURCE="login"
    export XUI_URL="$XUI_URL"
    export XUI_USERNAME="$XUI_USERNAME"
    export XUI_PASSWORD="$XUI_PASSWORD"
fi

echo ""
echo "=== Подключение к Remnawave ==="
read -p "URL панели Remnawave (например https://panel.remnawave.com/api): " REMN_API_URL
read -p "API-токен Remnawave: " REMN_TOKEN
export REMN_API_URL="$REMN_API_URL"
export REMN_TOKEN="$REMN_TOKEN"

echo ""
echo "-----------------------------------------------"
echo "Источник: $SOURCE"
echo "Панель Remnawave: $REMN_API_URL"
echo "-----------------------------------------------"
read -p "Продолжить миграцию? (y/n): " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "❌ Отменено пользователем."
    exit 1
fi

echo ""
echo "🚀 Запуск миграции..."
python3 xui2remnawave_migrate.py
STATUS=$?

echo ""
if [ $STATUS -eq 0 ]; then
    echo "✅ Миграция завершена успешно!"
else
    echo "⚠️ Миграция завершилась с ошибками (код $STATUS)"
fi

LOG_DIR="logs"
LATEST_LOG=$(ls -1t "$LOG_DIR" | head -n 1)
if [ -f "$LOG_DIR/$LATEST_LOG" ]; then
    echo "📘 Последний лог: $LOG_DIR/$LATEST_LOG"
    read -p "Открыть лог сейчас? (y/n): " VIEW_LOG
    if [[ "$VIEW_LOG" == "y" || "$VIEW_LOG" == "Y" ]]; then
        less "$LOG_DIR/$LATEST_LOG"
    fi
fi
