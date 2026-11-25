## [2026-11-26] — Старт рефакторинга `daas_parser`

- **Архитектура:** утверждена модульная структура (`core/` + `projects/` + JSONL-чекпоинты) и формат ведения истории (Conventional Commits + `DECISIONS.md`).
- **`core/logger.py`:** добавлен `setup_logger` (консоль + UTF-8 файл, привязка к `PROJECT_ROOT`, защита от дублей и смена `FileHandler`).
- **`core/fetcher.py`:** функция `get_html` перенесена в `fetch_html` с параметрами `timeout`/`delay_range`/`impersonate`, валидацией задержки и логированием.
