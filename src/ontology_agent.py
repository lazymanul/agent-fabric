"""
Агент для построения онтологии (графа знаний) из документов через LM Studio.
"""
import os
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
import networkx as nx
from pyvis.network import Network
from openai import OpenAI
from markitdown import MarkItDown

from config import (
    LMSTUDIO_API_URL,
    LMSTUDIO_LOAD_URL,
    ONTOLOGY_MODEL_NAME,
    KNOWLEDGE_GRAPH_PROMPT,
    DOCUMENT_EXTENSIONS,
    TEMPERATURE,
    MAX_TOKENS,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ontology_agent")


class OntologyAgent:
    """Агент для извлечения сущностей и связей и построения графа знаний."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        model_name: str = ONTOLOGY_MODEL_NAME,
        recursive: bool = True,
        lmstudio_url: str = LMSTUDIO_API_URL,
        lmstudio_load_url: str = LMSTUDIO_LOAD_URL,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.recursive = recursive
        self.lmstudio_url = lmstudio_url
        self.lmstudio_load_url = lmstudio_load_url
        
        self.client: OpenAI | None = None
        self.md_converter = MarkItDown()
        self.graph = nx.Graph()  # Storage Layer: NetworkX
        self.entity_map: Dict[str, str] = {}  # Для разрешения кореференций (id -> name)

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        if not self.input_dir.exists():
            raise FileNotFoundError(f"Входной каталог не найден: {self.input_dir}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_model(self) -> None:
        """Загружает модель в LM Studio."""
        log.info(f"Загрузка модели '{self.model_name}'...")
        import requests
        payload = {"model": self.model_name}
        try:
            resp = requests.post(self.lmstudio_load_url, json=payload, timeout=60)
            if resp.status_code == 200:
                log.info("✅ Модель загружена.")
            else:
                log.warning(f"Статус загрузки: {resp.status_code}")
        except Exception as e:
            log.error(f"Ошибка подключения к LM Studio: {e}")
            return

        self.client = OpenAI(base_url=self.lmstudio_url, api_key="not-needed")

    def extract_text(self, doc_path: Path) -> str:
        """Извлекает текст из документа."""
        try:
            result = self.md_converter.convert(str(doc_path))
            content = result.text_content
            # Ограничиваем размер, так как граф строится по чанкам или целым документам
            if len(content) > 15000:
                content = content[:15000] + "... [обрезано]"
            return content
        except Exception as e:
            log.error(f"Ошибка чтения {doc_path.name}: {e}")
            return ""

    def extract_knowledge(self, text: str, source_file: str) -> Dict[str, Any]:
        """Отправляет текст в LLM для извлечения JSON с сущностями и связями."""
        if not self.client:
            raise RuntimeError("Клиент не инициализирован")

        messages = [
            {"role": "system", "content": "Ты строгий JSON-парсер. Отвечай только валидным JSON."},
            {"role": "user", "content": f"{KNOWLEDGE_GRAPH_PROMPT}\n\nТекст для анализа:\n{text}"}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,  # Низкая температура для стабильного JSON
                max_tokens=MAX_TOKENS,
            )
            raw_json = response.choices[0].message.content
            # Очистка от markdown-оберток, если LLM их добавила
            raw_json = raw_json.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_json)
        except Exception as e:
            log.error(f"Ошибка при извлечении знаний из {source_file}: {e}")
            return {"entities": [], "relations": []}

    def update_graph(self, data: Dict[str, Any], source_file: str) -> None:
        """Добавляет извлеченные данные в граф NetworkX."""
        
        # 1. Добавляем узлы (сущности)
        for entity in data.get("entities", []):
            eid = entity["id"]
            name = entity["name"]
            etype = entity.get("type", "Unknown")
            
            # Если узел уже есть, обновляем его атрибуты (добавляем источники)
            if self.graph.has_node(eid):
                if source_file not in self.graph.nodes[eid].get("sources", []):
                    self.graph.nodes[eid]["sources"].append(source_file)
            else:
                self.graph.add_node(
                    eid, 
                    label=name, 
                    type=etype, 
                    sources=[source_file],
                    title=f"Type: {etype}<br>Sources: {source_file}"
                )
                self.entity_map[eid] = name

        # 2. Добавляем ребра (связи)
        for relation in data.get("relations", []):
            src = relation["source"]
            tgt = relation["target"]
            rel_type = relation["relation"]

            # Добавляем ребро только если оба узла существуют в графе
            if self.graph.has_node(src) and self.graph.has_node(tgt):
                if self.graph.has_edge(src, tgt):
                    # Если связь уже есть, можно добавить тип связи в список
                    existing_rel = self.graph[src][tgt].get("relations", [])
                    if rel_type not in existing_rel:
                        existing_rel.append(rel_type)
                        self.graph[src][tgt]["relations"] = existing_rel
                        self.graph[src][tgt]["label"] = ", ".join(existing_rel)
                else:
                    self.graph.add_edge(
                        src, tgt, 
                        label=rel_type,
                        relations=[rel_type],
                        title=f"Relation: {rel_type}"
                    )

    def export_to_html(self, filename: str = "knowledge_graph.html") -> Path:
        """Экспортирует граф NetworkX в интерактивный HTML через pyvis."""
        log.info("Генерация HTML-визуализации...")
        
        net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
        
        # Настройка физики для красивого расположения узлов
        net.set_options("""
        var options = {
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 100}
          },
          "nodes": {
            "shape": "dot",
            "size": 20,
            "font": {"size": 14, "color": "#ffffff"}
          },
          "edges": {
            "color": {"inherit": true},
            "smooth": {
              "enabled": true,
              "type": "continuous"
            }
          }
        }
        """)

        # Добавляем узлы и ребра из NetworkX в PyVis
        for node, data in self.graph.nodes(data=True):
            # Цвета в зависимости от типа сущности (простая эвристика)
            color = "#97C2FC" # Default blue
            if "Component" in data.get("type", ""): color = "#FF9999"
            elif "Process" in data.get("type", ""): color = "#FFFF99"
            
            net.add_node(
                node, 
                label=data.get("label", node), 
                title=data.get("title", ""),
                color=color,
                size=25
            )

        for u, v, data in self.graph.edges(data=True):
            net.add_edge(
                u, v, 
                label=data.get("label", ""),
                title=data.get("title", "")
            )

        output_path = self.output_dir / filename
        net.write_html(str(output_path))
        log.info(f"✅ Граф сохранен: {output_path}")
        return output_path

    def run(self) -> None:
        """Основной цикл работы агента."""
        self.load_model()
        
        # Сканирование файлов
        documents = []
        pattern = "**/*" if self.recursive else "*"
        for path in self.input_dir.glob(pattern):
            if path.is_file() and path.suffix.lower() in DOCUMENT_EXTENSIONS:
                documents.append(path)
        
        log.info(f"Найдено {len(documents)} документов для анализа.")

        for i, doc_path in enumerate(documents):
            log.info(f"[{i+1}/{len(documents)}] Обработка: {doc_path.name}")
            
            text = self.extract_text(doc_path)
            if not text:
                continue
                
            knowledge_data = self.extract_knowledge(text, doc_path.name)
            self.update_graph(knowledge_data, doc_path.name)
            
            log.info(f"   Добавлено узлов: {len(knowledge_data.get('entities', []))}, связей: {len(knowledge_data.get('relations', []))}")

        if self.graph.number_of_nodes() > 0:
            self.export_to_html()
        else:
            log.warning("Граф пуст. Ничего не экспортировано.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Агент для построения онтологии")
    parser.add_argument("input_dir", help="Каталог с документами")
    parser.add_argument("output_dir", help="Каталог для сохранения HTML-графа")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    agent = OntologyAgent(input_dir=args.input_dir, output_dir=args.output_dir)
    agent.run()

"""
 python ontology_agent.py ./data ./summaries/ontology
 """


if __name__ == "__main__":
    main()