# Agent Fabric

Фреймворк для локальной обработки документов и изображений с помощью LLM через LM Studio. Предоставляет набор агентов для суммаризации контента, генерации эмбеддингов, семантического поиска и построения графа знаний — без отправки данных в облако.

## Структура репозитория

```
agent-fabric/
├── readme.md
├── requirements.txt          # Зависимости Python
├── images/
│   └── architecture.png      # Схема архитектуры
└── src/
    ├── config.py             # Центральная конфигурация
    ├── image_agent.py        # Агент суммаризации изображений
    ├── document_agent.py     # Агент суммаризации документов
    ├── embedding_agent.py    # Агент векторизации (эмбеддинги)
    └── ontology_agent.py     # Агент построения онтологии (граф знаний)
```

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
                     └────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Ontology Agent  │
                    │  (knowledge      │
                    │   graph → HTML)  │
                    └──────────────────┘
```

## Модули

### `config.py` — Конфигурация

Центральный модуль настроек для всех агентов:

| Параметр | Описание |
|----------|----------|
| `LMSTUDIO_BASE_URL` | Базовый URL LM Studio (по умолчанию `http://localhost:1234`) |
| `LMSTUDIO_API_URL` | URL OpenAI-совместимого API (`/v1`) |
| `LMSTUDIO_LOAD_URL` | URL внутреннего REST API для загрузки моделей (`/api/v0/load`) |
| `IMAGE_MODEL_NAME` | Модель для анализа изображений (Qwen-VL) |
| `DOC_MODEL_NAME` | Модель для суммаризации документов |
| `ONTOLOGY_MODEL_NAME` | Модель для извлечения онтологии (по умолчанию = `DOC_MODEL_NAME`) |
| `EMBEDDING_MODEL_NAME` | Модель для генерации эмбеддингов (BGE-M3) |
| `TEMPERATURE` | Температура генерации (0.3) |
| `MAX_TOKENS` | Максимум токенов в ответе (20000) |
| `CHUNK_SIZE / CHUNK_OVERLAP` | Параметры чанкинга текста (1500 / 200 символов) |
| `CHROMA_DB_PATH` | Путь к хранилищу ChromaDB (`./chroma_db`) |
| `COLLECTION_NAME` | Имя коллекции в ChromaDB (`documents`) |
| `IMAGE_EXTENSIONS` | Поддерживаемые форматы изображений |
| `DOCUMENT_EXTENSIONS` | Поддерживаемые форматы документов |

### `image_agent.py` — Агент изображений

Агент для пакетной суммаризации изображений через визуальные модели (Qwen-VL).

**Функционал:**
- Рекурсивное сканирование каталогов
- Поддержка форматов: JPG, JPEG, PNG, WebP, BMP, GIF
- Кодирование в base64 и отправка в LM Studio
- Генерация структурированных суммаризаций (Markdown)
- Пропуск уже обработанных файлов
- Автоматическая загрузка модели в LM Studio через REST API

**CLI:**
```bash
python src/image_agent.py <input_dir> <output_dir> \
    --model qwen/qwen3-vl-4b \
    [--no-recursive] [--no-skip]
```

### `document_agent.py` — Агент документов

Агент для пакетной суммаризации текстовых документов.

**Функционал:**
- Извлечение текста через MarkItDown (PDF, DOCX, XLSX, XLS, PPTX, HTML, CSV, JSON, XML, MD, TXT)
- Ограничение размера контекста (~30 000 символов)
- Генерация структурированных суммаризаций
- Сохранение относительной структуры каталогов
- Автоматическая загрузка модели в LM Studio через REST API

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
- Привязка метаданных из summary-файлов (превью суммаризации, путь к source-файлу)
- Хранение в ChromaDB с косинусным расстоянием
- Пропуск уже индексированных документов
- Детальная статистика: количество чанков, размер коллекции

**CLI:**
```bash
python src/embedding_agent.py <raw_dir> <summary_dir> \
    --model text-embedding-bge-m3 \
    --chroma-path ./chroma_db \
    --collection documents \
    --chunk-size 1500 \
    --chunk-overlap 200 \
    [--no-recursive] [--no-skip]
```

### `ontology_agent.py` — Агент онтологии

Агент для извлечения сущностей и связей из документов с построением интерактивного графа знаний.

**Функционал:**
- Извлечение текста через MarkItDown (PDF, DOCX, XLSX, XLS, PPTX, HTML, CSV, JSON, XML, MD, TXT)
- Рекурсивное сканирование каталогов
- Идентификация сущностей и их взаимосвязей через LLM (структурированный JSON)
- Построение графа знаний на основе NetworkX
- Экспорт в интерактивный HTML-файл через pyvis (с визуализацией, физикой и цветовой кодировкой)
- Ограничение размера текста (~15 000 символов на документ)

**CLI:**
```bash
python src/ontology_agent.py <input_dir> <output_dir>
```

**Выходной файл:** `knowledge_graph.html` — интерактивный граф с:
- Узлами, окрашенными по типу сущности (Component — красный, Process — жёлтый, остальные — синий)
- Рёбрами с подписями типов связей
- Физическим движком для автоматического расположения узлов

## Зависимости

Основные библиотеки:

```bash
pip install openai requests markitdown chromadb networkx pyvis
```

Полный список зависимостей — в `requirements.txt`.

## Предварительные требования

1. **LM Studio** запущен на `localhost:1234`
2. Модели предварительно загружены в LM Studio:
   - Визуальная модель (Qwen-VL) для изображений
   - Текстовая модель (Qwen 3.6) для документов и онтологии
   - Модель эмбеддингов (BGE-M3)

## Типичный workflow

```bash
# 1. Суммаризация изображений
python src/image_agent.py ./data/images ./summaries/images/

# 2. Суммаризация документов
python src/document_agent.py ./data/docs ./summaries/docs/

# 3. Создание эмбеддингов для семантического поиска
python src/embedding_agent.py ./data/docs ./summaries/docs/

# 4. Построение онтологии (интерактивный граф знаний)
python src/ontology_agent.py ./data/docs ./summaries/ontology/