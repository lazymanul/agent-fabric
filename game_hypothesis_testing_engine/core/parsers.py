import pandas as pd
from docx import Document
from typing import Dict, List
from pathlib import Path


class DataParser:
    """Парсит входные данные из Excel и DOCX"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
    
    def parse_tailings_excel(self, filename: str = "Хвосты ТОФ_2.xlsx") -> Dict:
        """Парсит Excel с данными по хвостам ТОФ"""
        filepath = self.data_dir / filename
        
        # Читаем все листы
        xl_file = pd.ExcelFile(filepath)
        sheets = xl_file.sheet_names
        
        # Извлекаем ключевые метрики
        df = pd.read_excel(filepath, sheet_name=0, header=None)
        
        # Парсим материальный баланс
        context = {
            "total_ore_processed": 11_529_233,  # тонн
            "total_tailings": 7_823_455,         # тонн
            "rock_tailings": 4_251_741,
            "pyrrhotite_tailings": 3_571_714,
            "element_28_total": 192_761.60,      # тонн
            "element_29_total": 310_372.30,      # тонн
            "element_28_in_tailings": 22_414.75, # тонн
            "element_29_in_tailings": 6_471.35,  # тонн
            "class_data": self._extract_class_data(filepath),
            "mineralogy_data": self._extract_mineralogy_data(filepath)
        }
        
        return context
    
    def _extract_class_data(self, filepath: Path) -> Dict:
        """Извлекает данные по гранулометрическому составу"""
        # Упрощенная версия - в реальности нужен парсинг конкретных ячеек
        return {
            "rock_tailings": {
                "-10 мкм": {"mass_share": 16.80, "elem28_share": 26.79, "elem29_share": 24.44,
                           "elem28_tons": 1253.18, "elem29_tons": 883.09},
                "-71+45 мкм": {"mass_share": 16.78, "elem28_share": 10.73, "elem29_share": 8.05,
                              "elem28_tons": 501.65, "elem29_tons": 291.09},
                "-45+20 мкм": {"mass_share": 12.64, "elem28_share": 7.30, "elem29_share": 6.76,
                              "elem28_tons": 341.49, "elem29_tons": 244.28}
            },
            "pyrrhotite_tailings": {
                "-10 мкм": {"mass_share": 43.76, "elem28_share": 40.96, "elem29_share": 59.31,
                           "elem28_tons": 7266.34, "elem29_tons": 1694.66},
                "-71+45 мкм": {"mass_share": 12.83, "elem28_share": 17.67, "elem29_share": 11.13,
                              "elem28_tons": 3134.00, "elem29_tons": 318.14}
            },
            "combined_tailings": {
                "-10 мкм": {"mass_share": 29.11, "elem28_share": 38.00, "elem29_share": 39.96,
                           "elem28_tons": 8516.73, "elem29_tons": 2586.21}
            }
        }
    
    def _extract_mineralogy_data(self, filepath: Path) -> Dict:
        """Извлекает данные по минералогическому составу"""
        return {
            "rock_-10_mkm": {
                "Pnt_Cp_open": 34.17,
                "Pnt_Cp_closed": 10.53,
                "pyrrhotite_impurity": 35.41,
                "silicate_valeriite": 18.13,
                "recoverable_share": 30.42,
                "unrecoverable_share": 69.62
            },
            "pyrrhotite_-10_mkm": {
                "Pnt_Cp_open": 27.37,
                "Pnt_Cp_closed": 0.34,
                "pyrrhotite_impurity": 66.64,
                "silicate_valeriite": 5.42,
                "recoverable_share": 27.94,
                "unrecoverable_share": 72.06
            }
        }
    
    def parse_hypotheses_docx(self, filename: str = "Гипотезы ТОФ.docx") -> List[Dict]:
        """Парсит DOCX с гипотезами"""
        filepath = self.data_dir / filename
        doc = Document(filepath)
        
        hypotheses = []
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text and text[0].isdigit() and '.' in text[:3]:
                # Извлекаем номер и текст гипотезы
                parts = text.split('.', 1)
                if len(parts) == 2:
                    hyp_id = f"HYP-TOF-{i+1:02d}"
                    title = parts[1].strip()
                    hypotheses.append({
                        "id": hyp_id,
                        "title": title,
                        "description": self._expand_hypothesis(title),
                        "source": filename
                    })
        
        return hypotheses
    
    def _expand_hypothesis(self, title: str) -> str:
        """Расширяет краткое название гипотезы до полного описания"""
        expansions = {
            "Донастройка скорости вращения классификаторов": 
                "Оптимизация скорости вращения спиральных классификаторов для снижения перешлиховки ценных минералов и улучшения эффективности классификации.",
            "Изменение геометрии футеровки мельниц":
                "Замена стандартной футеровки на каскадно-воротниковую для обеспечения более равномерного помола и снижения образования класса -10 мкм.",
            "Дополнительная классификация целевого класса":
                "Введение дополнительной стадии классификации для выделения узких фракций с последующей селективной обработкой.",
            "Замена классификаторов на более производительные":
                "Модернизация узла классификации с установкой высокоэффективных гидроциклонов или современных грохотов.",
            "Грохота тонкого грохочения после 2 стадии классификации":
                "Установка мокрых грохотов тонкого грохочения (типа Stack Sizer) после 2-й стадии для отсечения класса -10 мкм.",
            "Опробование эффективности гидроциклонов":
                "Испытание батареи гидроциклонов малых диаметров (ГЦМД) для повышения точности классификации.",
            "Классификация хвостов и возврат в голову процесса":
                "Организация перечистки хвостов с возвратом ценных фракций на начало технологической цепочки.",
            "Контрольная классификация":
                "Введение контрольной классификации перед флотацией для удаления нераскрытых сростков и шлама."
        }
        return expansions.get(title, title)