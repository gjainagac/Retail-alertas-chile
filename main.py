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

PRODUCTS = [
    {
        "name": "PS5 Slim",
        "search_query": "PS5 Slim consola",
        "must_include": ["ps5", "slim"],
        "console_words": ["consola", "console", "playstation 5", "ps5"],
        "normal_price": 570000,
        "min_price": 350000,
        "max_price": 800000,
    },
    {
        "name": "PS5 Pro",
        "search_query": "PS5 Pro consola",
        "must_include": ["ps5", "pro"],
        "console_words": ["consola", "console", "playstation 5", "ps5"],
        "normal_price": 850000,
        "min_price": 550000,
        "max_price": 1200000,
    },
    {
        "name": "Nintendo Switch 2",
        "search_query": "Nintendo Switch 2 consola",
        "must_include": ["switch", "2"],
        "console_words": ["consola", "console", "nintendo switch 2", "system"],
        "normal_price": 630000,
        "min_price": 400000,
        "max_price": 850000,
    },
]

STORES = [
    {
        "name": "Mercado Libre Chile",
        "search_url": "https://listado.mercadolibre.cl/{query}",
    },
    {
        "name": "Falabella",
        "search_url": "https://www.falabella.com/falabella-cl/search?Ntt={query}",
    },
    {
        "name": "Paris",
        "search_url": "https://www.paris.cl/search?q={query}",
    },
]

EXCLUDED_WORDS = [
    "control",
    "dualsense",
    "joystick",
    "juego",
    "games",
    "game",
    "funda",
    "carcasa",
    "protector",
    "cargador",
    "carga",
    "cable",
    "soporte",
    "base",
    "dock",
    "audifono",
    "audífono",
    "headset",
    "cover",
    "skin",
    "grip",
    "mando",
    "portal",
    "lector",
    "disco duro",
    "ssd",
    "memoria",
    "gift card",
    "tarjeta",
    "servicio técnico",
    "reparación",
    "repuesto",
    "adaptador",
    "estuche",
    "bolso",
    "amiibo",
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


def looks_like_console_product(text, product):
    text = normalize_text(text)

    if any(word in text for word in EXCLUDED_WORDS):
        return False

    if not all(word in text for word in product["must_include"]):
        return False

    if not any(word in text for word in product["console_words"]):
        return False

    return True


def find_candidate_blocks(soup):
    selectors = [
        "li",
        "article",
        "div.pod",
        "div[data-testid]",
        "div.ui-search-result",
        "div.poly-card",
        "div",
    ]

    blocks = []

    for selector in selectors:
        for element in soup.select(selector):
            text = element.get_text(" ", strip=True)

            if "$" not in text:
                continue

            if len(text) < 20:
                continue

            if len(text) > 1500:
                continue

            blocks.append(text)

    unique_blocks = []
    seen = set()

    for block in blocks:
        compact = " ".join(block.split())

        if compact in seen:
            continue

        seen.add(compact)
        unique_blocks.append(compact)

    return unique_blocks


def extract_price_alerts(html, store_name, product, url):
    soup = BeautifulSoup(html, "html.parser")
    blocks = find_candidate_blocks(soup)

    alert_price_limit = int(
        product["normal_price"] * (1 - OFFER_PERCENT_BELOW_NORMAL / 100)
    )

    print(
        f"{store_name} / {product['name']}: precio normal {product['normal_price']} | alerta bajo {alert_price_limit}",
        flush=True,
    )

    candidates = []

    for block in blocks:
        if not looks_like_console_product(block, product):
            continue

        prices = extract_prices_from_text(block)

        valid_prices = [
            price
            for price in prices
            if product["min_price"] <= price <= product["max_price"]
        ]

        if not valid_prices:
            continue

        detected_price = min(valid_prices)

        candidates.append(
            {
                "price": detected_price,
                "text": block[:250],
            }
        )

    if not candidates:
        print(f"No se encontraron consolas válidas para {product['name']} en {store_name}", flush=True)
        return []

    candidates = sorted(candidates, key=lambda item: item["price"])

    print(
        f"{store_name} / {product['name']}: candidatos válidos {[c['price'] for c in candidates[:5]]}",
        flush=True,
    )

    best_candidate = candidates[0]
    current_price = best_candidate["price"]

    if current_price > alert_price_limit:
        print(
            f"Sin alerta: {product['name']} en {store_name} está en {current_price}, sobre el límite {alert_price_limit}",
            flush=True,
        )
        return []

    discount_vs_normal = round(
        ((product["normal_price"] - current_price) / product["normal_price"]) * 100,
        1,
    )

    return [
        {
            "store": store_name,
            "product": product["name"],
            "current_price": current_price,
            "normal_price": product["normal_price"],
            "alert_price_limit": alert_price_limit,
            "discount_vs_normal": discount_vs_normal,
            "url": url,
            "matched_text": best_candidate["text"],
        }
    ]


def check_store_product(store, product):
    query = product["search_query"].replace(" ", "-")
    url = store["search_url"].format(query=query)

    print(f"Revisando {product['name']} en {store['name']}", flush=True)

    html = get_page(url)

    if not html:
        return []

    return extract_price_alerts(
        html=html,
        store_name=store["name"],
        product=product,
        url=url,
    )


def format_price(price):
    return f"${price:,.0f}".replace(",", ".")


def alert_key(result):
    return f"{result['store']}|{result['product']}|{result['current_price']}"


def build_alert_message(result):
    return f"""
🚨 <b>Alerta de consola bajo precio normal</b>

🎮 <b>{result['product']}</b>
🏬 Tienda: {result['store']}

💰 Precio detectado: <b>{format_price(result['current_price'])}</b>
📌 Precio normal estimado: {format_price(result['normal_price'])}
🎯 Aviso configurado bajo: {format_price(result['alert_price_limit'])}
🔥 Baja vs. precio normal: <b>{result['discount_vs_normal']}%</b>

🧾 Coincidencia detectada:
{result['matched_text']}

🔗 Revisar tienda:
{result['url']}
""".strip()


def run_check():
    print("Iniciando revisión de consolas...", flush=True)

    for store in STORES:
        for product in PRODUCTS:
            try:
                results = check_store_product(store, product)

                if not results:
                    print(
                        f"Sin alertas para {product['name']} en {store['name']}",
                        flush=True,
                    )

                for result in results:
                    key = alert_key(result)

                    if key not in sent_alerts:
                        message = build_alert_message(result)
                        send_telegram_message(message)
                        sent_alerts.add(key)
                        print("Alerta enviada:", key, flush=True)
                    else:
                        print("Alerta ya enviada:", key, flush=True)

                time.sleep(5)

            except Exception as e:
                print(
                    f"Error revisando {product['name']} en {store['name']}: {e}",
                    flush=True,
                )

    print("Revisión terminada.", flush=True)


def main():
    print("Bot iniciado", flush=True)
    send_telegram_message("✅ Bot de alertas de consolas iniciado correctamente.")

    while True:
        run_check()
        print(f"Esperando {CHECK_INTERVAL_MINUTES} minutos...", flush=True)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
