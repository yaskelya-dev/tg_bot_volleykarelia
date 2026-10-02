#!/bin/bash

set -e

echo "Получаем данные с гита"
git pull origin main

echo "Сборка и перезапуск Docker Compose"
docker compose up -d --build

echo "Удаляем старые образы"
docker image prune -f

echo "Деплой прошёл успешно"
