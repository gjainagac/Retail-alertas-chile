# Retail Alertas Chile

Bot en Python que revisa descuentos en productos seleccionados y envía alertas por Telegram cuando detecta descuentos iguales o superiores al porcentaje configurado.

## Productos monitoreados

- PS5 Slim
- PS5 Pro
- Nintendo Switch 2

## Tiendas incluidas

- Mercado Libre Chile
- Falabella
- Paris
- Ripley

## Variables de entorno

TELEGRAM_BOT_TOKEN=tu_token_de_telegram
TELEGRAM_CHAT_ID=tu_chat_id
DISCOUNT_THRESHOLD=30
CHECK_INTERVAL_MINUTES=60

## Despliegue

Este proyecto está preparado para desplegarse en Railway.

El comando de inicio es:

python main.py