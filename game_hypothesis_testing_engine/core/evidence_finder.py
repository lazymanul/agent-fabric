from typing import List, Dict
from .models import Evidence


class EvidenceFinder:
    """Ищет доказательства для утверждений в базе знаний"""
    
    def __init__(self, context: Dict):
        self.context = context
    
    def find_evidence(self, claim_text: str) -> List[Evidence]:
        """Основной метод поиска доказательств"""
        evidence_list = []
        
        # Паттерн-матчинг для ключевых утверждений
        if self._mentions_overgrinding(claim_text):
            evidence_list.extend(self._find_overgrinding_evidence())
        
        if self._mentions_class_minus_10(claim_text):
            evidence_list.extend(self._find_class_minus_10_evidence())
        
        if self._mentions_closed_srostki(claim_text):
            evidence_list.extend(self._find_closed_srostki_evidence())
        
        if self._mentions_unrecoverable(claim_text):
            evidence_list.extend(self._find_unrecoverable_evidence())
        
        return evidence_list
    
    def _mentions_overgrinding(self, text: str) -> bool:
        keywords = ["перешлиховк", "шлих", "-10 мкм", "шлам", "тонкий класс"]
        return any(kw in text.lower() for kw in keywords)
    
    def _mentions_class_minus_10(self, text: str) -> bool:
        return "-10 мкм" in text or "минус 10" in text.lower()
    
    def _mentions_closed_srostki(self, text: str) -> bool:
        return "сростк" in text.lower() or "закрытый" in text.lower()
    
    def _mentions_unrecoverable(self, text: str) -> bool:
        return "неизвлекаем" in text.lower() or "силикат" in text.lower()
    
    def _find_overgrinding_evidence(self) -> List[Evidence]:
        """Доказательства проблемы перешлиховки"""
        data = self.context["class_data"]["combined_tailings"]["-10 мкм"]
        return [
            Evidence(
                source="Хвосты ТОФ_2.xlsx",
                snippet=f"В классе -10 мкм отвальных хвостов теряется {data['elem28_share']}% Элемента 28 ({data['elem28_tons']:.1f} т) и {data['elem29_share']}% Элемента 29 ({data['elem29_tons']:.1f} т).",
                data_point={"class": "-10 мкм", "elem28_loss_tons": data['elem28_tons']},
                confidence=0.95
            )
        ]
    
    def _find_class_minus_10_evidence(self) -> List[Evidence]:
        """Детальные данные по классу -10 мкм"""
        rock_data = self.context["class_data"]["rock_tailings"]["-10 мкм"]
        pyr_data = self.context["class_data"]["pyrrhotite_tailings"]["-10 мкм"]
        
        return [
            Evidence(
                source="Хвосты ТОФ_2.xlsx (породные хвосты)",
                snippet=f"В породных хвостах класс -10 мкм составляет {rock_data['mass_share']}% массы, содержит {rock_data['elem28_share']}% Элемента 28.",
                confidence=0.95
            ),
            Evidence(
                source="Хвосты ТОФ_2.xlsx (пирротиновые хвосты)",
                snippet=f"В пирротиновых хвостах класс -10 мкм составляет {pyr_data['mass_share']}% массы, содержит {pyr_data['elem29_share']}% Элемента 29.",
                confidence=0.95
            )
        ]
    
    def _find_closed_srostki_evidence(self) -> List[Evidence]:
        """Доказательства по нераскрытым сросткам"""
        mineralogy = self.context["mineralogy_data"]
        
        return [
            Evidence(
                source="Хвосты ТОФ_2.xlsx (минералогия, породные -10 мкм)",
                snippet=f"Доля закрытых сростков Pnt/Cp: {mineralogy['rock_-10_mkm']['Pnt_Cp_closed']}%. Примесь в пирротине: {mineralogy['rock_-10_mkm']['pyrrhotite_impurity']}%.",
                confidence=0.90
            ),
            Evidence(
                source="Хвосты ТОФ_2.xlsx (минералогия, пирротиновые -10 мкм)",
                snippet=f"В пирротиновых хвостах -10 мкм: примесь в пирротине {mineralogy['pyrrhotite_-10_mkm']['pyrrhotite_impurity']}%, неизвлекаемый металл {mineralogy['pyrrhotite_-10_mkm']['unrecoverable_share']}%.",
                confidence=0.90
            )
        ]
    
    def _find_unrecoverable_evidence(self) -> List[Evidence]:
        """Доказательства по неизвлекаемому металлу"""
        mineralogy = self.context["mineralogy_data"]
        
        return [
            Evidence(
                source="Хвосты ТОФ_2.xlsx",
                snippet=f"Неизвлекаемый металл в классе -10 мкм: породные хвосты — {mineralogy['rock_-10_mkm']['unrecoverable_share']}%, пирротиновые — {mineralogy['pyrrhotite_-10_mkm']['unrecoverable_share']}%. Основная форма — силикаты/валлериит и изоморфная примесь в пирротине.",
                confidence=0.92
            )
        ]