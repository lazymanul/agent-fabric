from typing import List, Dict
from .models import (
    Hypothesis, Claim, ClaimStatus, Challenge, 
    ValidationResult, HypothesisStatus, Evidence
)
from .evidence_finder import EvidenceFinder
from .llm_adapter import LLMAdapter


class ValidationGameEngine:
    """Игровой движок валидации гипотез"""
    
    def __init__(self, context: Dict, llm_adapter: LLMAdapter = None):
        self.context = context
        self.evidence_finder = EvidenceFinder(context)
        self.llm = llm_adapter or LLMAdapter()
        self.game_log = []
    
    def validate(self, hypothesis_data: Dict) -> ValidationResult:
        """Основной метод валидации гипотезы"""
        print(f"\n🎮 Запуск игры валидации для: {hypothesis_data['title']}")
        print("=" * 70)
        
        # Создаем объект гипотезы
        hypothesis = Hypothesis(
            id=hypothesis_data["id"],
            title=hypothesis_data["title"],
            description=hypothesis_data["description"]
        )
        
        # РАУНД 1: Декомпозиция и фактологическая проверка
        print("\n⚔️  РАУНД 1: Декомпозиция и фактологическая проверка")
        print("-" * 70)
        self._round_1_fact_checking(hypothesis)
        
        # РАУНД 2: Контраргументы и защита
        print("\n⚔️  РАУНД 2: Контраргументы (Адвокат дьявола)")
        print("-" * 70)
        self._round_2_counterarguments(hypothesis)
        
        # Подсчет итогов
        self._calculate_final_score(hypothesis)
        
        # ✅ ИСПРАВЛЕНО: передаём hypothesis (а не будущий result)
        recommendations = self._generate_recommendations(hypothesis)
        roadmap = self._generate_roadmap(hypothesis)
        risks = self._generate_risks(hypothesis)
        
        # Теперь создаём ValidationResult
        result = ValidationResult(
            hypothesis=hypothesis,
            game_log=self.game_log,
            recommendations=recommendations,
            roadmap=roadmap,
            risks=risks
        )
        
        self._print_final_report(result)
        return result
    
    def _round_1_fact_checking(self, hypothesis: Hypothesis):
        """Раунд 1: Декомпозиция и проверка фактов"""
        claim_texts = self.llm.decompose_hypothesis(hypothesis.description)
        
        for i, text in enumerate(claim_texts, 1):
            claim = Claim(
                id=f"{hypothesis.id}-C{i:02d}",
                text=text,
                max_points=15
            )
            
            print(f"\n📋 Claim {i}: {text}")
            
            evidence_list = self.evidence_finder.find_evidence(text)
            claim.evidence = evidence_list
            
            if evidence_list:
                avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
                if avg_confidence >= 0.9:
                    claim.status = ClaimStatus.VERIFIED
                    claim.points_earned = claim.max_points
                    print(f"   ✅ ПОДТВЕРЖДЕНО (уверенность: {avg_confidence:.0%})")
                    print(f"   📊 Очки: +{claim.points_earned}/{claim.max_points}")
                elif avg_confidence >= 0.7:
                    claim.status = ClaimStatus.PARTIALLY_VERIFIED
                    claim.points_earned = int(claim.max_points * 0.6)
                    print(f"   ⚠️  ЧАСТИЧНО ПОДТВЕРЖДЕНО (уверенность: {avg_confidence:.0%})")
                    print(f"   📊 Очки: +{claim.points_earned}/{claim.max_points}")
                else:
                    claim.status = ClaimStatus.UNVERIFIED
                    claim.points_earned = 0
                    print(f"   ❌ НЕ ПОДТВЕРЖДЕНО (уверенность: {avg_confidence:.0%})")
            else:
                claim.status = ClaimStatus.UNVERIFIED
                claim.points_earned = 0
                print(f"   ❌ НЕТ ДОКАЗАТЕЛЬСТВ")
            
            for ev in evidence_list:
                print(f"   🔍 {ev.snippet[:80]}...")
            
            hypothesis.claims.append(claim)
            hypothesis.max_possible_score += claim.max_points
            hypothesis.total_score += claim.points_earned
            
            self.game_log.append({
                "round": 1,
                "claim_id": claim.id,
                "claim_text": text,
                "status": claim.status.value,
                "evidence_count": len(evidence_list),
                "points": claim.points_earned
            })
    
    def _round_2_counterarguments(self, hypothesis: Hypothesis):
        """Раунд 2: Контраргументы и защита"""
        for i, claim in enumerate(hypothesis.claims, 1):
            if claim.status in [ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_VERIFIED]:
                counterargument = self.llm.generate_counterargument(claim.text, self.context)
                
                challenge = Challenge(
                    round_number=2,
                    attack_text=counterargument
                )
                
                print(f"\n🛡️  Атака на Claim {i}:")
                print(f"   🔴 {counterargument}")
                
                rebuttal = self.llm.generate_rebuttal(claim.text, counterargument, self.context)
                challenge.defense_text = rebuttal
                challenge.resolved = True
                challenge.points_delta = 2
                
                print(f"   🟢 Защита: {rebuttal[:80]}...")
                print(f"   📊 Очки: -3 (адаптация) +5 (защита) = +2")
                
                claim.counterarguments.append(counterargument)
                claim.rebuttals.append(rebuttal)
                claim.points_earned += 2
                hypothesis.total_score += 2
                
                hypothesis.challenges.append(challenge)
                
                self.game_log.append({
                    "round": 2,
                    "claim_id": claim.id,
                    "attack": counterargument,
                    "defense": rebuttal,
                    "resolved": True,
                    "points_delta": 2
                })
    
    def _calculate_final_score(self, hypothesis: Hypothesis):
        """Подсчет итогового счета и статуса"""
        percentage = hypothesis.score_percentage
        
        if percentage >= 80:
            hypothesis.status = HypothesisStatus.APPROVED_FOR_PILOT
        elif percentage >= 60:
            hypothesis.status = HypothesisStatus.APPROVED
        elif percentage >= 40:
            hypothesis.status = HypothesisStatus.NEEDS_REVISION
        else:
            hypothesis.status = HypothesisStatus.REJECTED
    
    # ✅ ИСПРАВЛЕНО: принимаем Hypothesis, а не ValidationResult
    def _generate_recommendations(self, hypothesis: Hypothesis) -> List[str]:
        """Генерирует рекомендации по результатам игры"""
        recommendations = []
        
        if hypothesis.status == HypothesisStatus.APPROVED_FOR_PILOT:
            recommendations.append("Гипотеза готова к пилотным испытаниям на одном из потоков.")
            recommendations.append("Рекомендуется параллельно внедрять несколько связанных гипотез для синергетического эффекта.")
        elif hypothesis.status == HypothesisStatus.APPROVED:
            recommendations.append("Гипотеза одобрена, но требует дополнительных лабораторных испытаний.")
        elif hypothesis.status == HypothesisStatus.NEEDS_REVISION:
            recommendations.append("Гипотеза требует доработки. Слабые места выявлены в Раунде 2.")
        else:
            recommendations.append("Гипотеза отклонена. Требуется фундаментальный пересмотр подхода.")
        
        # Добавляем рекомендации на основе контраргументов
        for challenge in hypothesis.challenges:
            if "капитальные затраты" in challenge.attack_text.lower():
                recommendations.append("Подготовить детальный расчет ROI перед внедрением.")
            if "нагрузк" in challenge.attack_text.lower():
                recommendations.append("Провести аудит текущей загрузки оборудования.")
            if "грохот" in challenge.attack_text.lower() or "забьются" in challenge.attack_text.lower():
                recommendations.append("Рассмотреть альтернативу: батарея ГЦМД вместо мокрых грохотов.")
        
        return recommendations
    
    # ✅ ИСПРАВЛЕНО: принимаем Hypothesis
    def _generate_roadmap(self, hypothesis: Hypothesis) -> List[Dict]:
        """Генерирует дорожную карту проверки"""
        # Базовая дорожная карта
        roadmap = [
            {"stage": "Лабораторный", "duration": "2 недели", "tasks": [
                "Грохо-фракционный анализ проб хвостов",
                "Минералогический анализ класса -10 мкм"
            ]},
            {"stage": "Пилотный", "duration": "1 месяц", "tasks": [
                "Установка пилотной батареи ГЦМД",
                "Сбор технологических проб",
                "Оценка эффекта на извлечение"
            ]},
            {"stage": "Промышленный", "duration": "3 месяца", "tasks": [
                "Масштабирование на всю ТОФ",
                "Мониторинг KPI",
                "Корректировка параметров"
            ]}
        ]
        
        # Добавляем специфичные задачи на основе контраргументов
        for challenge in hypothesis.challenges:
            if "футеровк" in challenge.attack_text.lower():
                roadmap[1]["tasks"].append("Плановая замена футеровки во время остановки мельниц")
            if "скорость" in challenge.attack_text.lower():
                roadmap[0]["tasks"].append("Лабораторные испытания различных режимов вращения классификаторов")
        
        return roadmap
    
    # ✅ ИСПРАВЛЕНО: принимаем Hypothesis
    def _generate_risks(self, hypothesis: Hypothesis) -> List[Dict]:
        """Генерирует оценку рисков"""
        risks = [
            {"risk": "Забивание мокрых грохотов", "probability": "Высокая", "impact": "Крит.",
             "mitigation": "Замена на батарею ГЦМД"},
            {"risk": "Увеличение нагрузки на мельницы", "probability": "Средняя", "impact": "Среднее",
             "mitigation": "Оптимизация футеровки и загрузки мелющих тел"},
            {"risk": "Капитальные затраты", "probability": "Высокая", "impact": "Высокое",
             "mitigation": "Расчет ROI на основе возврата потерянного металла"}
        ]
        
        # Добавляем специфичные риски на основе контраргументов
        for challenge in hypothesis.challenges:
            if "баланс" in challenge.attack_text.lower() or "схем" in challenge.attack_text.lower():
                risks.append({
                    "risk": "Нарушение баланса технологической схемы",
                    "probability": "Средняя",
                    "impact": "Высокое",
                    "mitigation": "Поэтапное внедрение с контролем ключевых параметров"
                })
        
        return risks
    
    def _print_final_report(self, result: ValidationResult):
        """Выводит итоговый отчет"""
        hypothesis = result.hypothesis
        
        print("\n" + "=" * 70)
        print("🏆 ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 70)
        print(f"Гипотеза: {hypothesis.title}")
        print(f"Статус: {hypothesis.status.value}")
        print(f"Счет: {hypothesis.total_score} / {hypothesis.max_possible_score} ({hypothesis.score_percentage:.1f}%)")
        print(f"Утверждений проверено: {len(hypothesis.claims)}")
        print(f"Контраргументов отработано: {len(hypothesis.challenges)}")
        
        print("\n📋 Рекомендации:")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"   {i}. {rec}")
        
        print("\n🗺️  Дорожная карта:")
        for stage in result.roadmap:
            print(f"   • {stage['stage']} ({stage['duration']})")
            for task in stage['tasks']:
                print(f"      - {task}")