import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DISCOUNT_THRESHOLD = float(os.getenv("DISCOUNT_THRESHOLD", "30"))
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))

PRODUCTS = [
    {
        "name": "PS5 Slim",
        "keywords": ["ps5 slim", "playstation 5 slim"],
    },
    {
        "name": "PS5 Pro",
        "keywords": ["ps5 pro", "playstation 5 pro"],
    },
    {
        "name": "Nintendo Switch 2",
        "keywords": ["switch 2", "nintendo switch 2"],
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
    {
        "name": "Ripley",
        "search_url": "https://simple.ripley.cl/search/{query}",
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


def clean_price(price_text):
    if not price_text:
        return None

    cleaned = (
        price_text.replace("$", "")
        .replace(".", "")
        .replace(",", "")
        .replace("CLP", "")
        .strip()
    )

    digits = "".join(char for char in cleaned if char.isdigit())

    if not digits:
        return None

    return int(digits)


def calculate_discount(original_price, current_price):
    if not original_price or not current_price:
        return None

    if original_price <= current_price:
        return None

    return round(((original_price - current_price) / original_price) * 100, 1)


def get_page(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error leyendo {url}: {e}", flush=True)
        return None


def extract_products_generic(html, store_name, product_name, url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()

    results = []

    product_keywords = []
    for product in PRODUCTS:
        if product["name"] == product_name:
            product_keywords = product["keywords"]

    if not any(keyword in text for keyword in product_keywords):
        return results

    price_candidates = []

    for element in soup.find_all(string=True):
        content = element.strip()

        if "$" in content and any(char.isdigit() for char in content):
            price = clean_price(content)

            if price and 100000 <= price <= 2000000:
                price_candidates.append(price)

    price_candidates = sorted(set(price_candidates))

    if len(price_candidates) < 2:
        return results

    current_price = price_candidates[0]
    original_price = price_candidates[-1]

    discount = calculate_discount(original_price, current_price)

    if discount and discount >= DISCOUNT_THRESHOLD:
        results.append(
            {
                "store": store_name,
                "product": product_name,
                "current_price": current_price,
                "original_price": original_price,
                "discount": discount,
                "url": url,
            }
        )

    return results


def check_store_product(store, product):
    query = product["name"].replace(" ", "-")
    url = store["search_url"].format(query=query)

    print(f"Revisando {product['name']} en {store['name']}", flush=True)

    html = get_page(url)

    if not html:
        return []

    return extract_products_generic(
        html=html,
        store_name=store["name"],
        product_name=product["name"],
        url=url,
    )


def format_price(price):
    return f"${price:,.0f}".replace(",", ".")


def alert_key(result):
    return f"{result['store']}|{result['product']}|{result['current_price']}|{result['url']}"


def build_alert_message(result):
    return f"""
🚨 <b>Alerta de descuento</b>

🎮 <b>{result['product']}</b>
🏬 Tienda: {result['store']}

💰 Precio actual: <b>{format_price(result['current_price'])}</b>
💸 Precio referencia: {format_price(result['original_price'])}
🔥 Descuento estimado: <b>{result['discount']}%</b>

🔗 Ver oferta:
{result['url']}
""".strip()


def run_check():
    print("Iniciando revisión de ofertas...", flush=True)

    for store in STORES:
        for product in PRODUCTS:
            try:
                results = check_store_product(store, product)

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
                print(f"Error revisando {product['name']} en {store['name']}: {e}", flush=True)

    print("Revisión terminada.", flush=True)


def main():
    print("Bot iniciado", flush=True)
    send_telegram_message("✅ Bot de alertas iniciado correctamente.")

    while True:
        run_check()
        print(f"Esperando {CHECK_INTERVAL_MINUTES} minutos...", flush=True)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
