import os
import time
import json
import random
from dotenv import load_dotenv
from curl_cffi import requests
from bs4 import BeautifulSoup
from google import genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Ошибка: Ключ GEMINI_API_KEY не найден. Проверьте файл .env!")

client = genai.Client(api_key=API_KEY)

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

            book_data = {"title": title, "price": price}
            parsed_data.append(book_data)

        except (AttributeError, KeyError) as e:
            print(f"Пропущен сломанный товар. Ошибка: {e}")
            continue

    return parsed_data

def enrich_with_ai(raw_dict):
    prompt = f"""Ты ETL-процессор. Я дам тебе грязные данные. 
    Верни СТРОГИЙ JSON без markdown-разметки.
    Ключи, которые должны быть в JSON: 'title_clean', 'currency', 'price_numeric' (число).
    Правила для полей:
        - currency: строго трехбуквенный ISO-код (например, 'GBP', 'USD', 'EUR'). Использование спецсимволов вроде '£', '$' строго запрещено.
        - price_numeric: только вещественное число (float) без знаков валют и пробелов.
    Грязные данные:
    {str(raw_dict)}
    """

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt
            )
            text_response = response.text

            clean_text = text_response.replace('```json', '').replace('```', '').strip()

            result_dict = json.loads(clean_text)
            return result_dict

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