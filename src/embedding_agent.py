"""
Агент для создания эмбеддингов raw-данных и сохранения в ChromaDB.
"""
import os
import sys
import time
import logging
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import requests
import chromadb
from openai import OpenAI
from markitdown import MarkItDown
from config import (
    LMSTUDIO_API_URL,
    LMSTUDIO_LOAD_URL,
    EMBEDDING_MODEL_NAME,
    DOCUMENT_EXTENSIONS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHROMA_DB_PATH,
    COLLECTION_NAME,
)

# ------------------------------------------------------------------ #
#                            Логирование                              #
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("embedding_agent")


class EmbeddingAgent:
    """Агент для сканирования raw-данных, генерации эмбеддингов
    и сохранения их в ChromaDB вместе с метаданными из summary."""

    def __init__(
        self,
        raw_dir: str,
        summary_dir: str,
        model_name: str = EMBEDDING_MODEL_NAME,
        chroma_path: str = CHROMA_DB_PATH,
        collection_name: str = COLLECTION_NAME,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        recursive: bool = True,
        skip_existing: bool = True,
        lmstudio_url: str = LMSTUDIO_API_URL,
        lmstudio_load_url: str = LMSTUDIO_LOAD_URL,
    ):
        self.raw_dir = Path(raw_dir)
        self.summary_dir = Path(summary_dir)
        self.model_name = model_name
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.recursive = recursive
        self.skip_existing = skip_existing
        self.lmstudio_url = lmstudio_url
        self.lmstudio_load_url = lmstudio_load_url

        self.client: Optional[OpenAI] = None
        self.chroma_client: Optional[chromadb.PersistentClient] = None
        self.collection: Optional[chromadb.Collection] = None
        self.md_converter = MarkItDown()

        self._ensure_directories()

    # ------------------------------------------------------------------ #
    #                          Вспомогательные методы                      #
    # ------------------------------------------------------------------ #
    def _ensure_directories(self) -> None:
        """Проверяет существование каталогов и создаёт их при необходимости."""
        if not self.raw_dir.exists() or not self.raw_dir.is_dir():
            raise FileNotFoundError(f"Каталог raw-данных не найден: {self.raw_dir}")
        if not self.summary_dir.exists() or not self.summary_dir.is_dir():
            raise FileNotFoundError(f"Каталог summary не найден: {self.summary_dir}")
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        log.info(f"Raw-каталог:       {self.raw_dir}")
        log.info(f"Summary-каталог:   {self.summary_dir}")
        log.info(f"ChromaDB:          {self.chroma_path}")

    # ------------------------------------------------------------------ #
    #                      Загрузка модели в LM Studio                    #
    # ------------------------------------------------------------------ #
    def load_model(self, max_retries: int = 3, retry_delay: int = 5) -> None:
        """Загружает модель эмбеддингов в LM Studio."""
        log.info(f"Загружаю модель эмбеддингов '{self.model_name}' в LM Studio...")
        payload = {"model": self.model_name}
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    self.lmstudio_load_url, json=payload, timeout=60
                )
                if resp.status_code == 200:
                    log.info("✅ Модель эмбеддингов успешно загружена.")
                    break
                else:
                    log.warning(
                        f"Попытка {attempt}/{max_retries}: "
                        f"код {resp.status_code}, ответ: {resp.text[:200]}"
                    )
            except requests.exceptions.ConnectionError:
                log.error(
                    "Не удалось подключиться к LM Studio. "
                    "Убедитесь, что LM Studio запущен."
                )
                sys.exit(1)
            except requests.exceptions.RequestException as e:
                log.warning(f"Попытка {attempt}/{max_retries}: ошибка {e}")

            if attempt < max_retries:
                log.info(f"Ожидание {retry_delay} сек перед повтором...")
                time.sleep(retry_delay)
        else:
            raise RuntimeError(
                f"Не удалось загрузить модель '{self.model_name}' "
                f"после {max_retries} попыток."
            )

        # OpenAI-совместимый клиент для embeddings
        self.client = OpenAI(
            base_url=self.lmstudio_url,
            api_key="not-needed",
        )

        # Инициализация ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            f"ChromaDB коллекция '{self.collection_name}': "
            f"{self.collection.count()} документов"
        )

    # ------------------------------------------------------------------ #
    #                       Сканирование каталога                         #
    # ------------------------------------------------------------------ #
    def scan_documents(self) -> List[Path]:
        """Возвращает список путей ко всем raw-документам."""
        documents: List[Path] = []
        pattern = "**/*" if self.recursive else "*"
        for path in self.raw_dir.glob(pattern):
            if path.is_file() and path.suffix.lower().strip() in DOCUMENT_EXTENSIONS:
                documents.append(path)
        documents.sort()
        log.info(f"Найдено raw-документов: {len(documents)}")
        return documents

    # ------------------------------------------------------------------ #
    #                 Поиск соответствующего summary                      #
    # ------------------------------------------------------------------ #
    def _find_matching_summary(self, raw_path: Path) -> Tuple[Optional[Path], Optional[str]]:
        """Ищет соответствующий .md файл в summary-каталоге и читает его."""
        try:
            rel_path = raw_path.relative_to(self.raw_dir)
        except ValueError:
            rel_path = Path(raw_path.name)
        summary_path = self.summary_dir / rel_path.with_suffix(".md")
        if summary_path.exists():
            try:
                text = summary_path.read_text(encoding="utf-8")
                return summary_path, text
            except Exception as e:
                log.warning(f"Не удалось прочитать summary {summary_path}: {e}")
        return None, None

    # ------------------------------------------------------------------ #
    #                    Извлечение текста из документа                   #
    # ------------------------------------------------------------------ #
    def extract_text(self, doc_path: Path) -> str:
        """Извлекает текстовое содержимое из документа через MarkItDown."""
        log.info(f"📄 Извлекаю текст: {doc_path.name}")
        try:
            result = self.md_converter.convert(str(doc_path))
            content = result.text_content
            if not content or not content.strip():
                log.warning(f"Файл '{doc_path.name}' пуст.")
                return ""
            return content
        except Exception as e:
            log.error(f"Ошибка при извлечении текста из {doc_path.name}: {e}")
            raise

    # ------------------------------------------------------------------ #
    #                         Чанкинг текста                              #
    # ------------------------------------------------------------------ #
    def _chunk_text(self, text: str) -> List[str]:
        """Разбивает текст на перекрывающиеся чанки."""
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return chunks

    # ------------------------------------------------------------------ #
    #                   Генерация эмбеддингов через LLM                   #
    # ------------------------------------------------------------------ #
    def _generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Получает векторы эмбеддингов для списка чанков."""
        if self.client is None:
            raise RuntimeError("Модель не загружена. Сначала вызовите load_model().")
        if not chunks:
            return []
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=chunks,
            )
            # Сортируем по индексу, чтобы порядок совпадал с chunks
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            log.error(f"Ошибка при генерации эмбеддингов: {e}")
            raise

    # ------------------------------------------------------------------ #
    #                      Сохранение в ChromaDB                          #
    # ------------------------------------------------------------------ #
    def _save_to_chroma(
        self,
        doc_path: Path,
        chunks: List[str],
        embeddings: List[List[float]],
        summary_path: Optional[Path],
        summary_text: Optional[str],
    ) -> int:
        """Сохраняет чанки и их эмбеддинги в ChromaDB."""
        if not chunks or not embeddings:
            return 0

        try:
            rel_path = doc_path.relative_to(self.raw_dir)
        except ValueError:
            rel_path = Path(doc_path.name)

        base_id = str(rel_path).replace(os.sep, "__").replace(" ", "_")
        ids = [f"{base_id}__chunk_{i}" for i in range(len(chunks))]

        metadatas = [
            {
                "source": str(doc_path),
                "filename": doc_path.name,
                "extension": doc_path.suffix.lower(),
                "chunk_index": i,
                "total_chunks": len(chunks),
                "has_summary": summary_path is not None,
                "summary_path": str(summary_path) if summary_path else "",
            }
            for i in range(len(chunks))
        ]

        # Сохраняем summary как метаданные (только для первого чанка, чтобы не дублировать)
        if summary_text:
            # Ограничим длину summary для метаданных (ChromaDB чувствителен к размеру)
            short_summary = summary_text[:2000]
            metadatas[0]["summary_preview"] = short_summary

        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        return len(chunks)

    # ------------------------------------------------------------------ #
    #               Проверка: уже обработан документ?                     #
    # ------------------------------------------------------------------ #
    def _is_already_processed(self, doc_path: Path) -> bool:
        """Проверяет, есть ли уже чанки этого документа в коллекции."""
        try:
            rel_path = doc_path.relative_to(self.raw_dir)
        except ValueError:
            rel_path = Path(doc_path.name)
        prefix = str(rel_path).replace(os.sep, "__").replace(" ", "_") + "__chunk_"
        existing = self.collection.get(ids=[f"{prefix}0"])
        return bool(existing and existing["ids"])

    # ------------------------------------------------------------------ #
    #                         Основной цикл                               #
    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        """Запускает полный цикл: загрузка модели → сканирование → эмбеддинги → ChromaDB."""
        stats = {
            "total": 0,
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "chunks_created": 0,
        }

        # 1. Загрузка модели и инициализация ChromaDB
        self.load_model()

        # 2. Сканирование
        documents = self.scan_documents()
        stats["total"] = len(documents)
        if not documents:
            log.warning("Документы не найдены. Завершаю работу.")
            return stats

        # 3. Цикл обработки
        for i, doc_path in enumerate(documents, start=1):
            log.info(f"[{i}/{len(documents)}] {doc_path}")

            # Пропуск уже обработанных
            if self.skip_existing and self._is_already_processed(doc_path):
                log.info(f"⏭  Пропускаю (уже в ChromaDB): {doc_path.name}")
                stats["skipped"] += 1
                continue

            try:
                # Извлечение текста
                text = self.extract_text(doc_path)
                if not text:
                    log.warning(f"⚠  Пропускаю пустой документ: {doc_path.name}")
                    stats["skipped"] += 1
                    continue

                # Поиск summary
                summary_path, summary_text = self._find_matching_summary(doc_path)
                if summary_path:
                    log.info(f"📎 Найден summary: {summary_path.name}")

                # Чанкинг
                chunks = self._chunk_text(text)
                log.info(f"🔪 Создано чанков: {len(chunks)}")

                # Генерация эмбеддингов
                embeddings = self._generate_embeddings(chunks)

                # Сохранение в ChromaDB
                saved = self._save_to_chroma(
                    doc_path, chunks, embeddings, summary_path, summary_text
                )
                stats["chunks_created"] += saved
                stats["processed"] += 1
                log.info(f"💾 Сохранено в ChromaDB: {saved} чанков")

            except Exception as e:
                log.error(f"❌ Не удалось обработать {doc_path.name}: {e}")
                stats["errors"] += 1

        log.info("=" * 50)
        log.info("ИТОГИ РАБОТЫ АГЕНТА ЭМБЕДДИНГОВ:")
        log.info(f"  Всего найдено:       {stats['total']}")
        log.info(f"  Обработано:          {stats['processed']}")
        log.info(f"  Пропущено:           {stats['skipped']}")
        log.info(f"  Ошибок:              {stats['errors']}")
        log.info(f"  Создано чанков:      {stats['chunks_created']}")
        log.info(f"  Всего в коллекции:   {self.collection.count()}")
        log.info("=" * 50)
        return stats


# ---------------------------------------------------------------------- #
#                          Точка входа CLI                                #
# ---------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Агент для создания эмбеддингов raw-данных в ChromaDB"
    )
    parser.add_argument("raw_dir", help="Каталог с raw-данными")
    parser.add_argument("summary_dir", help="Каталог с суммаризациями (.md)")
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL_NAME,
        help=f"Имя модели эмбеддингов (по умолчанию: {EMBEDDING_MODEL_NAME})",
    )
    parser.add_argument(
        "--chroma-path",
        default=CHROMA_DB_PATH,
        help=f"Путь к хранилищу ChromaDB (по умолчанию: {CHROMA_DB_PATH})",
    )
    parser.add_argument(
        "--collection",
        default=COLLECTION_NAME,
        help=f"Имя коллекции (по умолчанию: {COLLECTION_NAME})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help=f"Размер чанка в символах (по умолчанию: {CHUNK_SIZE})",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=CHUNK_OVERLAP,
        help=f"Перекрытие чанков (по умолчанию: {CHUNK_OVERLAP})",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Не рекурсивно сканировать подкаталоги",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Переиндексировать даже уже существующие документы",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = EmbeddingAgent(
        raw_dir=args.raw_dir,
        summary_dir=args.summary_dir,
        model_name=args.model,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        recursive=not args.no_recursive,
        skip_existing=not args.no_skip,
    )
    agent.run()


if __name__ == "__main__":
    main()