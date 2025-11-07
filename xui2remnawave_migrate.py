#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция пользователей 3x-UI → Remnawave
Авторизация по логину/паролю (совместимо с MHSanaei/3x-ui)
С поддержкой записи логов и подсчётом скорости миграции.
"""

import os
import json
import asyncio
import logging
import httpx
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# === Настройка логирования ===
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"migration_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("xui2remnawave")

# === Переменные окружения ===
XUI_URL = os.getenv("XUI_URL", "https://your-xui-panel.com")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "password")

REMN_API_URL = os.getenv("REMN_API_URL", "https://your-remnawave-panel.com/api")
REMN_TOKEN = os.getenv("REMN_TOKEN", "YOUR_REMN_TOKEN")

CONFIG_PATH = os.getenv("XUI_CONFIG_PATH", "config.json")
SOURCE = os.getenv("SOURCE", "login")  # 'file' или 'login'

HEADERS_REMN = {
    "Authorization": f"Bearer {REMN_TOKEN}",
    "Content-Type": "application/json"
}

# === 1. Авторизация и получение пользователей из 3x-UI ===
async def login_xui(client: httpx.AsyncClient) -> str:
    """Авторизация в панели 3x-UI по логину и паролю"""
    url = f"{XUI_URL}/login"
    data = {"username": XUI_USERNAME, "password": XUI_PASSWORD}
    resp = await client.post(url, json=data)
    resp.raise_for_status()
    cookie = resp.cookies.get("session")
    if not cookie:
        raise Exception("Не удалось получить cookie-сессию от 3x-UI")
    logger.info("✅ Авторизация 3x-UI успешна")
    return cookie


async def get_xui_clients_from_login(client: httpx.AsyncClient, cookie: str) -> List[Dict[str, Any]]:
    """Получение пользователей из панели 3x-UI"""
    url = f"{XUI_URL}/panel/api/inbounds/list"
    headers = {"Cookie": f"session={cookie}"}
    resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    inbounds = resp.json().get("obj", [])
    users = []
    for inbound in inbounds:
        proto = inbound.get("protocol")
        port = inbound.get("port")
        for c in inbound.get("settings", {}).get("clients", []):
            users.append({
                "username": c.get("email"),
                "uuid": c.get("id"),
                "flow": c.get("flow"),
                "protocol": proto,
                "port": port
            })
    logger.info(f"📡 Получено {len(users)} пользователей из 3x-UI")
    return users


async def get_xui_clients_from_file(path: str) -> List[Dict[str, Any]]:
    """Загрузка пользователей из локального JSON"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = []
    for inbound in data.get("inbounds", []):
        proto = inbound.get("protocol")
        port = inbound.get("port")
        for client in inbound.get("settings", {}).get("clients", []):
            users.append({
                "username": client.get("email"),
                "uuid": client.get("id"),
                "flow": client.get("flow"),
                "protocol": proto,
                "port": port
            })
    logger.info(f"📄 Получено {len(users)} пользователей из {path}")
    return users

# === 2. Работа с Remnawave API ===
async def remn_get_user_by_uuid(client: httpx.AsyncClient, uuid: str) -> Optional[Dict[str, Any]]:
    url = f"{REMN_API_URL}/users?uuid={uuid}"
    resp = await client.get(url, headers=HEADERS_REMN)
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        return data[0] if data else None
    return None


async def remn_create_user(client: httpx.AsyncClient, user: Dict[str, Any]):
    url = f"{REMN_API_URL}/users"
    resp = await client.post(url, headers=HEADERS_REMN, json=user)
    if resp.status_code in (200, 201):
        logger.info(f"✅ Создан пользователь {user['username']}")
    else:
        logger.error(f"❌ Ошибка при создании {user['username']}: {resp.text}")


async def remn_update_user(client: httpx.AsyncClient, user_id: str, user: Dict[str, Any]):
    url = f"{REMN_API_URL}/users/{user_id}"
    resp = await client.put(url, headers=HEADERS_REMN, json=user)
    if resp.status_code in (200, 201):
        logger.info(f"🔄 Обновлён {user['username']}")
    else:
        logger.error(f"⚠️ Ошибка при обновлении {user['username']}: {resp.text}")

# === 3. Основной процесс ===
async def migrate_clients():
    start_time = time.time()
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        if SOURCE == "file":
            xui_users = await get_xui_clients_from_file(CONFIG_PATH)
        else:
            cookie = await login_xui(client)
            xui_users = await get_xui_clients_from_login(client, cookie)

        created = updated = errors = 0
        for u in xui_users:
            try:
                existing = await remn_get_user_by_uuid(client, u["uuid"])
                if existing:
                    await remn_update_user(client, existing["id"], u)
                    updated += 1
                else:
                    await remn_create_user(client, u)
                    created += 1
            except Exception as e:
                errors += 1
                logger.exception(f"Ошибка при обработке {u.get('username', '?')}: {e}")

        elapsed = time.time() - start_time
        total = len(xui_users)
        speed = total / elapsed if elapsed > 0 else 0
        logger.info("------------------------------------------------")
        logger.info(f"✅ Миграция завершена. Создано: {created}, обновлено: {updated}, ошибок: {errors}")
        logger.info(f"⏱️ Время выполнения: {elapsed:.2f} сек, скорость: {speed:.2f} пользователей/сек")
        logger.info(f"📘 Подробный лог: {LOG_FILE}")

if __name__ == "__main__":
    asyncio.run(migrate_clients())
