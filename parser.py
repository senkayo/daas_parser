import os
import time
import random
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv
import pandas as pd
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


def save_to_csv(books_data: list[dict], filename: str = "books_dataset.csv") -> bool:
    if not books_data:
        print("[WARNING] Сохранение отменено: передан пустой список данных.")
        return False

    #Валидация и фильтрация входных данных
    valid_books = [b for b in books_data if isinstance(b, dict) and b]
    skipped_count = len(books_data) - len(valid_books)
    if skipped_count > 0:
        print(f"[INFO] Отфильтровано невалидных элементов: {skipped_count}")

    if not valid_books:
        print("[WARNING] Сохранение отменено: список не содержит валидных словарей.")
        return False

    #Определение пути: первый запуск -> filename, повторный -> filename_YYYYMMDD_HHMMSS.ext
    target_path = filename
    if os.path.exists(target_path):
        base, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = f"{base}_{timestamp}{ext}"

        # Защита на случай нескольких запусков в течение одной секунды
        counter = 1
        while os.path.exists(target_path):
            target_path = f"{base}_{timestamp}_{counter}{ext}"
            counter += 1

        print(f"[INFO] Файл '{filename}' уже существует. Предыдущая выгрузка не тронута.")
        print(f"[INFO] Для текущих данных создан новый файл: '{target_path}'")

    #Создание директории и экспорт DataFrame
    try:
        dirname = os.path.dirname(target_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        df = pd.DataFrame(valid_books)
        df.to_csv(target_path, index=False, encoding="utf-8-sig")

        abs_path = os.path.abspath(target_path)
        print(f"[SUCCESS] Успешно сохранено строк: {len(df)}")
        print(f"Путь к файлу: {abs_path}")
        return True

    except PermissionError:
        print(f"[ERROR] Доступ запрещен к '{target_path}'. Возможно, файл открыт в Excel или нет прав на запись.")
        return False
    except OSError as e:
        print(f"[ERROR] Ошибка файловой системы при сохранении в '{target_path}': {e}")
        return False
    except (ValueError, TypeError) as e:
        print(f"[ERROR] Ошибка структуры данных при конвертации в DataFrame: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Непредвиденная ошибка при сохранении '{target_path}': {e}")
        return False


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
        cleaned_books = []
        for book in test_sample:
            print(f"Отправка в ИИ сырых данных: {book}")
            clean_book = enrich_with_ai(book)
            if clean_book:
                cleaned_books.append(clean_book)
                print(f"Результат от ИИ: {clean_book}\n")
            else:
                print("Пропуск: не удалось получить данные от ИИ.\n")

            # Пауза между запросами к ИИ для соблюдения лимитов
            time.sleep(2)

        print("\n--- 4. Сохранение данных (Load) ---")
        save_to_csv(cleaned_books, filename="books_dataset.csv")
