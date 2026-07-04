# Agent Fabric

Фреймворк для локальной обработки документов и изображений с помощью LLM через LM Studio. Предоставляет набор агентов для суммаризации контента, генерации эмбеддингов и семантического поиска — без отправки данных в облако.

## Архитектура

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Raw Data   │────▶│  Summarizer     │────▶│    Summary       │
│ (docs/images)│     │    Agents       │     │    (.md files)   │
└──────────────┘     └────────┬────────┘     └────────┬─────────┘
                              │                       │
                              ▼                       ▼
                    ┌─────────────────┐     ┌──────────────────┐
                    │  Embedding      │────▶│    ChromaDB      │
                    │    Agent        │     │ (vector storage) │
                    └─────────────────┘     └──────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   LM Studio     │
                    │  (local LLM)    │
                    └─────────────────┘
```

## Модули

### `config.py` — Конфигурация

Центральный модуль настроек для всех агентов:

| Парамет | Описание |
|---------|----------|
| `LMSTUDIO_API_URL` | URL API LM Studio (OpenAI-совместимый) |
| `IMAGE_MODEL_NAME` | Модель для анализа изображений (Qwen-VL) |
| `DOC_MODEL_NAME` | Модель для суммаризации документов |
| `EMBEDDING_MODEL_NAME` | Модель для генерации эмбеддингов (BGE-M3) |
| `CHUNK_SIZE / CHUNK_OVERLAP` | Параметры чанкинга текста |
| `CHROMA_DB_PATH` | Путь к хранилищу ChromaDB |

### `image_agent.py` — Агент изображений

Агент для пакетной суммаризации изображений через визуальные модели (Qwen-VL).

**Функционал:**
- Рекурсивное сканирование каталогов
- Поддержка форматов: JPG, PNG, WebP, BMP, GIF
- Кодирование в base64 и отправка в LM Studio
- Генерация структурированных суммаризаций (Markdown)
- Пропуск уже обработанных файлов

**CLI:**
```bash
python src/image_agent.py <input_dir> <output_dir> \
    --model qwen/qwen3-vl-4b \
    [--no-recursive] [--no-skip]
```

### `document_agent.py` — Агент документов

Агент для пакетной суммаризации текстовых документов.

**Функционал:**
- Извлечение текста через MarkItDown (PDF, DOCX, XLSX, PPTX, CSV, JSON, XML, HTML)
- Ограничение размера контекста (~30 000 символов)
- Генерация структурированных суммаризаций
- Сохранение относительной структуры каталогов

**CLI:**
```bash
python src/document_agent.py <input_dir> <output_dir> \
    --model qwen3.6-40b-claude-4.6-opus-deckard-heretic-uncensored-thinking-neo-code-di-imatrix-max \
    [--no-recursive] [--no-skip]
```

### `embedding_agent.py` — Агент эмбеддингов

Агент для создания векторных представлений документов и сохранения в ChromaDB.

**Функционал:**
- Чанкинг текста с перекрытием (1500/200 символов)
- Генерация эмбеддингов через BGE-M3 модель
- Привязка метаданных из summary-файлов
- Хранение в ChromaDB с косинусным расстоянием
- Пропуск уже индексированных документов

**CLI:**
```bash
python src/embedding_agent.py <raw_dir> <summary_dir> \
    --model text-embedding-bge-m3 \
    --chroma-path ./chroma_db \
    --collection documents \
    [--no-recursive] [--no-skip]
```

## Зависимости

```bash
pip install openai requests markitdown chromadb
```

## Предварительные требования

1. **LM Studio** запущен на `localhost:1234`
2. Модели предварительно загружены в LM Studio:
   - Визуальная модель (Qwen-VL) для изображений
   - Текстовая модель (Qwen 3.6) для документов
   - Модель эмбеддингов (BGE-M3)

## Типичный workflow

```bash
# 1. Суммаризация изображений
python src/image_agent.py ./data/images ./summaries/images/

# 2. Суммаризация документов
python src/document_agent.py ./data/docs ./summaries/docs/

# 3. Создание эмбеддингов для семантического поиска
python src/embedding_agent.py ./data/docs ./summaries/docs/
```
