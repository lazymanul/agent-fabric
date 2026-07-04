"""
Агент для пакетной суммаризации документов через LM Studio.
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path
from typing import List, Optional

import requests
from openai import OpenAI
from markitdown import MarkItDown

from config import (
    LMSTUDIO_API_URL,
    LMSTUDIO_LOAD_URL,
    DOC_MODEL_NAME,
    TEMPERATURE,
    MAX_TOKENS,
    DOCUMENT_EXTENSIONS,
    DOCUMENT_SUMMARY_PROMPT,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("document_agent")


class DocumentSummarizerAgent:
    """Агент для сканирования каталога и суммаризации документов через LM Studio."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        model_name: str = DOC_MODEL_NAME,
        recursive: bool = True,
        skip_existing: bool = True,
        lmstudio_url: str = LMSTUDIO_API_URL,
        lmstudio_load_url: str = LMSTUDIO_LOAD_URL,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.recursive = recursive
        self.skip_existing = skip_existing
        self.lmstudio_url = lmstudio_url
        self.lmstudio_load_url = lmstudio_load_url

        self.client: Optional[OpenAI] = None
        self.md_converter = MarkItDown()
        self._ensure_directories()

    # ------------------------------------------------------------------ #
    #                          Вспомогательные методы                      #
    # ------------------------------------------------------------------ #
    def _ensure_directories(self) -> None:
        """Проверяет существование каталогов и создаёт их при необходимости."""
        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise FileNotFoundError(
                f"Входной каталог не найден: {self.input_dir}"
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Входной каталог: {self.input_dir}")
        log.info(f"Выходной каталог: {self.output_dir}")

    # ------------------------------------------------------------------ #
    #                      Загрузка модели в LM Studio                    #
    # ------------------------------------------------------------------ #
    def load_model(self, max_retries: int = 3, retry_delay: int = 5) -> None:
        """
        Загружает модель в LM Studio через внутренний REST API.
        LM Studio должен быть запущен.
        """
        log.info(f"Загружаю модель '{self.model_name}' в LM Studio...")

        payload = {"model": self.model_name}

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    self.lmstudio_load_url,
                    json=payload,
                    timeout=60,
                )
                if resp.status_code == 200:
                    log.info("✅ Модель успешно загружена.")
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

        # Инициализируем OpenAI-совместимый клиент
        self.client = OpenAI(
            base_url=self.lmstudio_url,
            api_key="not-needed",  # LM Studio не требует ключ
        )

    # ------------------------------------------------------------------ #
    #                       Сканирование каталога                         #
    # ------------------------------------------------------------------ #
    def scan_documents(self) -> List[Path]:
        """Возвращает список путей ко всем документам во входном каталоге."""
        documents: List[Path] = []
        pattern = "**/*" if self.recursive else "*"

        for path in self.input_dir.glob(pattern):
            if path.is_file() and path.suffix.lower() in DOCUMENT_EXTENSIONS:
                documents.append(path)

        documents.sort()  # Детерминированный порядок обработки
        log.info(f"Найдено документов: {len(documents)}")
        return documents

    # ------------------------------------------------------------------ #
    #                    Извлечение текста из документа                   #
    # ------------------------------------------------------------------ #
    def extract_text(self, doc_path: Path) -> str:
        """
        Извлекает текстовое содержимое из документа с помощью MarkItDown.
        """
        log.info(f"📄 Извлекаю текст: {doc_path.name}")

        try:
            result = self.md_converter.convert(str(doc_path))
            content = result.text_content

            if not content or not content.strip():
                log.warning(f"Файл '{doc_path.name}' пуст или не содержит извлекаемого текста.")
                return ""

            # Ограничение размера текста для защиты от переполнения контекста
            # Примерно 1 токен ≈ 4 символа, оставляем запас для промпта и ответа
            max_chars = 30000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n... [Текст обрезан из-за ограничения длины] ..."
                log.info(f"Текст обрезан до {max_chars} символов")

            return content
        except Exception as e:
            log.error(f"Ошибка при извлечении текста из {doc_path.name}: {e}")
            raise

    # ------------------------------------------------------------------ #
    #                    Суммаризация текста через LLM                    #
    # ------------------------------------------------------------------ #
    def summarize_text(self, doc_path: Path, text: str) -> str:
        """
        Отправляет текст в LLM и возвращает суммаризацию.
        """
        if self.client is None:
            raise RuntimeError("Модель не загружена. Сначала вызовите load_model().")

        log.info(f"🤖 Суммаризирую: {doc_path.name}")

        messages = [
            {
                "role": "system",
                "content": "Ты полезный AI-ассистент для анализа документов. Отвечай на русском языке.",
            },
            {
                "role": "user",
                "content": f"{DOCUMENT_SUMMARY_PROMPT}\n\n---\n\nСодержимое документа:\n\n{text}",
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            summary = response.choices[0].message.content.strip()
            log.info(f"✅ Получена суммаризация ({len(summary)} символов)")
            return summary
        except Exception as e:
            log.error(f"Ошибка при суммаризации {doc_path.name}: {e}")
            raise

    # ------------------------------------------------------------------ #
    #                        Сохранение результата                        #
    # ------------------------------------------------------------------ #
    def save_summary(self, doc_path: Path, summary: str) -> Path:
        """
        Сохраняет суммаризацию в выходной каталог.
        Сохраняет относительную структуру подкаталогов.
        """
        # Вычисляем относительный путь от input_dir
        try:
            rel_path = doc_path.relative_to(self.input_dir)
        except ValueError:
            rel_path = Path(doc_path.name)

        # Меняем расширение на .md (Markdown)
        output_path = self.output_dir / rel_path.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Формируем итоговый документ
        header = f"# Суммаризация: {doc_path.name}\n\n"
        source_line = f"**Источник:** `{doc_path}`\n\n---\n\n"
        content = header + source_line + summary

        output_path.write_text(content, encoding="utf-8")
        log.info(f"💾 Сохранено: {output_path}")
        return output_path

    # ------------------------------------------------------------------ #
    #                         Основной цикл                               #
    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        """
        Запускает полный цикл работы агента:
        загрузка модели → сканирование → обработка → сохранение.
        """
        stats = {"total": 0, "processed": 0, "skipped": 0, "errors": 0}

        # 1. Загрузка модели
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
            if self.skip_existing:
                try:
                    rel_path = doc_path.relative_to(self.input_dir)
                except ValueError:
                    rel_path = Path(doc_path.name)
                target = self.output_dir / rel_path.with_suffix(".md")
                if target.exists():
                    log.info(f"⏭  Пропускаю (уже обработано): {target.name}")
                    stats["skipped"] += 1
                    continue

            try:
                # Извлечение текста
                text = self.extract_text(doc_path)
                if not text:
                    log.warning(f"⚠  Пропускаю пустой документ: {doc_path.name}")
                    stats["skipped"] += 1
                    continue

                # Суммаризация
                summary = self.summarize_text(doc_path, text)
                self.save_summary(doc_path, summary)
                stats["processed"] += 1
            except Exception as e:
                log.error(f"❌ Не удалось обработать {doc_path.name}: {e}")
                stats["errors"] += 1

        log.info("=" * 50)
        log.info("ИТОГИ РАБОТЫ АГЕНТА:")
        log.info(f"  Всего найдено:   {stats['total']}")
        log.info(f"  Обработано:      {stats['processed']}")
        log.info(f"  Пропущено:       {stats['skipped']}")
        log.info(f"  Ошибок:          {stats['errors']}")
        log.info("=" * 50)

        return stats


# ---------------------------------------------------------------------- #
#                           Точка входа CLI                              #
# ---------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Агент для пакетной суммаризации документов через LM Studio"
    )
    parser.add_argument(
        "input_dir",
        help="Каталог для сканирования документов",
    )
    parser.add_argument(
        "output_dir",
        help="Каталог для сохранения суммаризаций (.md)",
    )
    parser.add_argument(
        "--model",
        default=DOC_MODEL_NAME,
        help=f"Имя модели в LM Studio (по умолчанию: {DOC_MODEL_NAME})",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Не рекурсивно сканировать подкаталоги",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Обрабатывать даже уже существующие файлы",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    agent = DocumentSummarizerAgent(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model_name=args.model,
        recursive=not args.no_recursive,
        skip_existing=not args.no_skip,
    )
    agent.run()


if __name__ == "__main__":
    main()