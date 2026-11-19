import os
import time
import random
from enum import Enum
from dotenv import load_dotenv
from curl_cffi import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ConfigDict
from google import genai
from google.genai import types

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Ошибка: Ключ GEMINI_API_KEY не найден. Проверьте файл .env!")

client = genai.Client(api_key=API_KEY)


class Currency(str, Enum):
    GBP = "GBP"
    USD = "USD"
    EUR = "EUR"


class BookItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, description="Очищенное название книги")
    price: float = Field(ge=0, description="Числовая цена без символов валюты")
    currency: Currency = Field(description="ISO-код валюты")
    is_available: bool = Field(description="True если книга в наличии, иначе False")
    rating: int = Field(ge=1, le=5, description="Рейтинг от 1 до 5 (One=1, Two=2...)")


def get_html(url):
    time.sleep(random.uniform(1, 3))

    try:
        response = requests.get(url, impersonate="chrome", timeout=10)

        if response.status_code == 200:
            print(f"Success: {url}")
            return response.text

        else:
            print(f"Ошибка сервера {response.status_code} для {url}")
            return None

    except requests.errors.RequestsError as e:
        print(f"Сетевая ошибка или таймаут: {e}")
        return None


def extract_books_data(html):
    parsed_data = []

    soup = BeautifulSoup(html, "html.parser")

    books = soup.find_all("article", class_="product_pod")
    for book in books:
        try:
            title = book.find("h3").find("a")["title"]
            price = book.find("p", class_="price_color").text

            # Извлечение сырых данных о наличии и рейтинге
            availability_el = book.find("p", class_="availability")
            availability = availability_el.text.strip() if availability_el else None

            rating_el = book.find("p", class_="star-rating")
            rating_classes = [c for c in rating_el.get("class", []) if c != "star-rating"] if rating_el else []
            rating = rating_classes[0] if rating_classes else None

            book_data = {
                "title": title,
                "price": price,
                "availability": availability,
                "rating": rating,
            }
            parsed_data.append(book_data)

        except (AttributeError, KeyError) as e:
            print(f"Пропущен сломанный товар. Ошибка: {e}")
            continue

    return parsed_data


def enrich_with_ai(raw_dict: dict) -> dict | None:
    prompt = f"Нормализуй сырые данные о книге: {raw_dict}"

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BookItem,
                    temperature=0.0,
                ),
            )
            if response.parsed:
                return response.parsed.model_dump(mode="json")

        except Exception as e:
            print(f"Попытка {attempt + 1}/3 не удалась: {e}. Ждем повтора...")
            time.sleep(3)

    return None


if __name__ == "__main__":
    TEST_URL = "https://books.toscrape.com/"

    print("--- 1. Сбор HTML ---")
    html = get_html(TEST_URL)

    if html:
        print("\n--- 2. Извлечение сырых данных (BeautifulSoup) ---")
        raw_books = extract_books_data(html)
        print(f"Всего найдено книг на странице: {len(raw_books)}")

        # Берем только 2 книги для теста
        test_sample = raw_books[:2]

        print("\n--- 3. Обогащение через Gemini (AI Transform) ---")
        for book in test_sample:
            print(f"Отправка в ИИ сырых данных: {book}")
            clean_book = enrich_with_ai(book)
            print(f"Результат от ИИ: {clean_book}\n")

            # Пауза между запросами к ИИ для соблюдения лимитов
            time.sleep(2)
