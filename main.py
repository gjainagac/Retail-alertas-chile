import os
import re
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
OFFER_PERCENT_BELOW_NORMAL = float(os.getenv("OFFER_PERCENT_BELOW_NORMAL", "15"))

TRACKED_PRODUCTS = [
    {
        "name": "PS5 Slim - Falabella",
        "product": "PS5 Slim",
        "store": "Falabella",
        "url": "PEGA_AQUI_LINK_ESPECIFICO_PS5_SLIM_FALABELLA",
        "normal_price": 570000,
        "min_price": 350000,
        "max_price": 800000,
        "must_include": ["ps5"],
        "exclude": [
            "control",
            "dualsense",
            "juego",
            "funda",
            "cargador",
            "audífono",
            "audifono",
            "headset",
            "soporte",
            "base",
            "cable",
            "repuesto",
            "servicio técnico",
        ],
    },
    {
        "name": "PS5 Pro - Falabella",
        "product": "PS5 Pro",
        "store": "Falabella",
        "url": "PEGA_AQUI_LINK_ESPECIFICO_PS5_PRO_FALABELLA",
        "normal_price": 850000,
        "min_price": 550000,
        "max_price": 1200000,
        "must_include": ["ps5", "pro"],
        "exclude": [
            "control",
            "dualsense",
            "juego",
            "funda",
            "cargador",
            "audífono",
            "audifono",
            "headset",
            "soporte",
            "base",
            "cable",
            "repuesto",
            "servicio técnico",
        ],
    },
    {
        "name": "Nintendo Switch 2 - Falabella",
        "product": "Nintendo Switch 2",
        "store": "Falabella",
        "url": "PEGA_AQUI_LINK_ESPECIFICO_SWITCH_2_FALABELLA",
        "normal_price": 630000,
        "min_price": 400000,
        "max_price": 850000,
        "must_include": ["switch"],
        "exclude": [
            "juego",
            "control",
            "joy-con",
            "joycon",
            "funda",
            "cargador",
            "audífono",
            "audifono",
            "headset",
            "soporte",
            "base",
            "cable",
            "repuesto",
            "servicio técnico",
            "amiibo",
        ],
    },
    {
        "name": "PS5 Slim - Paris",
        "product": "PS5 Slim",
        "store": "Paris",
        "url": "PEGA_AQUI_LINK_ESPECIFICO_PS5_SLIM_PARIS",
        "normal_price": 570000,
        "min_price": 350000,
        "max_price": 800000,
        "must_include": ["ps5"],
        "exclude": [
            "control",
            "dualsense",
            "juego",
            "funda",
            "cargador",
            "audífono",
            "audifono",
            "headset",
            "soporte",
            "base",
            "cable",
            "repuesto",
            "servicio técnico",
        ],
    },
    {
        "name": "Nintendo Switch 2 - Paris",
        "product": "Nintendo Switch 2",
        "store": "Paris",
        "url": "PEGA_AQUI_LINK_ESPECIFICO_SWITCH_2_PARIS",
        "normal_price": 630000,
        "min_price": 400000,
        "max_price": 850000,
        "must_include": ["switch"],
        "exclude": [
            "juego",
            "control",
            "joy-con",
            "joycon",
            "funda",
            "cargador",
            "audífono",
            "audifono",
            "headset",
            "soporte",
            "base",
            "cable",
            "repuesto",
            "servicio técnico",
            "amiibo",
        ],
    },
]

sent_alerts = set()


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID", flush=True)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)

        if response.status_code != 200:
            print("Error enviando mensaje a Telegram:", response.text, flush=True)
        else:
            print("Mensaje enviado a Telegram correctamente", flush=True)

    except Exception as e:
        print("Error conectando con Telegram:", e, flush=True)


def get_page(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        return response.text

    except Exception as e:
        print(f"Error leyendo {url}: {e}", flush=True)
        return None


def normalize_text(text):
    return text.lower().replace("\n", " ").replace("\t", " ").strip()


def extract_prices_from_text(text):
    prices = []

    matches = re.findall(r"\$\s?[\d\.]{5,12}", text)

    for match in matches:
        digits = re.sub(r"\D", "", match)

        if not digits:
            continue

        if len(digits) > 10:
            continue

        try:
            price = int(digits)
            prices.append(price)
        except ValueError:
            continue

    return prices


def page_matches_product(html, item):
    text = normalize_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

    for word in item["must_include"]:
        if word.lower() not in text:
            print(f"No se encontró palabra obligatoria '{word}' en {item['name']}", flush=True)
            return False

    for word in item["exclude"]:
        if word.lower() in text and item["product"].lower() not in text:
            print(f"Página posiblemente no corresponde por palabra excluida: {word}", flush=True)
            return False

    return True


def detect_product_price(html, item):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    all_prices = extract_prices_from_text(text)

    valid_prices = [
        price
        for price in all_prices
        if item["min_price"] <= price <= item["max_price"]
    ]

    valid_prices = sorted(set(valid_prices))

    print(f"{item['name']}: precios válidos detectados {valid_prices[:10]}", flush=True)

    if not valid_prices:
        return None

    return min(valid_prices)


def format_price(price):
    return f"${price:,.0f}".replace(",", ".")


def alert_key(item, current_price):
    return f"{item['name']}|{current_price}"


def build_alert_message(item, current_price, alert_price_limit, discount_vs_normal):
    return f"""
🚨 <b>Alerta de precio bajo en consola</b>

🎮 <b>{item['product']}</b>
🏬 Tienda: {item['store']}

💰 Precio detectado: <b>{format_price(current_price)}</b>
📌 Precio normal estimado: {format_price(item['normal_price'])}
🎯 Aviso configurado bajo: {format_price(alert_price_limit)}
🔥 Baja vs. precio normal: <b>{discount_vs_normal}%</b>

🔗 Ver producto:
{item['url']}
""".strip()


def check_tracked_product(item):
    if item["url"].startswith("PEGA_AQUI"):
        print(f"Falta configurar URL para {item['name']}", flush=True)
        return

    print(f"Revisando {item['name']}", flush=True)

    html = get_page(item["url"])

    if not html:
        return

    if not page_matches_product(html, item):
        print(f"La página no parece corresponder a {item['name']}", flush=True)
        return

    current_price = detect_product_price(html, item)

    if not current_price:
        print(f"No se pudo detectar precio para {item['name']}", flush=True)
        return

    alert_price_limit = int(
        item["normal_price"] * (1 - OFFER_PERCENT_BELOW_NORMAL / 100)
    )

    print(
        f"{item['name']}: precio detectado {current_price} | precio normal {item['normal_price']} | alerta bajo {alert_price_limit}",
        flush=True,
    )

    if current_price > alert_price_limit:
        print(f"Sin alerta para {item['name']}: precio sobre el límite", flush=True)
        return

    discount_vs_normal = round(
        ((item["normal_price"] - current_price) / item["normal_price"]) * 100,
        1,
    )

    key = alert_key(item, current_price)

    if key in sent_alerts:
        print(f"Alerta ya enviada para {item['name']} a {current_price}", flush=True)
        return

    message = build_alert_message(
        item=item,
        current_price=current_price,
        alert_price_limit=alert_price_limit,
        discount_vs_normal=discount_vs_normal,
    )

    send_telegram_message(message)
    sent_alerts.add(key)
    print(f"Alerta enviada para {item['name']} a {current_price}", flush=True)


def run_check():
    print("Iniciando revisión de links específicos...", flush=True)

    for item in TRACKED_PRODUCTS:
        try:
            check_tracked_product(item)
            time.sleep(5)

        except Exception as e:
            print(f"Error revisando {item['name']}: {e}", flush=True)

    print("Revisión terminada.", flush=True)


def main():
    print("Bot iniciado", flush=True)
    send_telegram_message("✅ Bot de alertas por link específico iniciado correctamente.")

    while True:
        run_check()
        print(f"Esperando {CHECK_INTERVAL_MINUTES} minutos...", flush=True)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
