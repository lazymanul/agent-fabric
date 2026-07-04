#!/usr/bin/env python3
"""
Игровой движок валидации гипотез
Главный модуль запуска
"""

from core.parsers import DataParser
from core.game_engine import ValidationGameEngine
from core.llm_adapter import LLMAdapter
from core.reporter import ReportGenerator


def main():
    print("=" * 70)
    print("🎮 ИГРОВОЙ ДВИЖОК ВАЛИДАЦИИ ГИПОТЕЗ")
    print("=" * 70)
    
    # 1. Загрузка и парсинг данных
    print("\n📂 Загрузка данных...")
    parser = DataParser(data_dir="data")
    
    context = parser.parse_tailings_excel("Хвосты ТОФ_2.xlsx")
    print(f"   ✅ Контекст загружен: {context['total_ore_processed']:,} т руды в переработке")
    
    hypotheses_data = parser.parse_hypotheses_docx("Гипотезы ТОФ.docx")
    print(f"   ✅ Загружено гипотез: {len(hypotheses_data)}")
    
    # 2. Инициализация компонентов
    llm_adapter = LLMAdapter()
    game_engine = ValidationGameEngine(context, llm_adapter)
    reporter = ReportGenerator(output_dir="output")
    
    # 3. Валидация гипотез
    print("\n" + "=" * 70)
    print("🚀 ЗАПУСК ВАЛИДАЦИИ")
    print("=" * 70)
    
    results = []
    
    # Валидируем первые 3 гипотезы для демо
    for hyp_data in hypotheses_data[:3]:
        result = game_engine.validate(hyp_data)
        results.append(result)
        
        # Генерация отчетов
        reporter.generate_json(result)
        reporter.generate_markdown(result)
        reporter.generate_jira_json(result)
    
    # 4. Итоговая сводка
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 70)
    
    for result in results:
        hyp = result.hypothesis
        print(f"\n{hyp.id}: {hyp.title}")
        print(f"   Статус: {hyp.status.value}")
        print(f"   Оценка: {hyp.total_score}/{hyp.max_possible_score} ({hyp.score_percentage:.1f}%)")
    
    # Сортировка по оценке
    sorted_results = sorted(results, key=lambda r: r.hypothesis.score_percentage, reverse=True)
    
    print("\n🏆 ТОП-3 гипотезы:")
    for i, result in enumerate(sorted_results[:3], 1):
        hyp = result.hypothesis
        print(f"   {i}. {hyp.title} — {hyp.score_percentage:.1f}%")
    
    print("\n✅ Все отчеты сохранены в папке 'output/'")
    print("=" * 70)


if __name__ == "__main__":
    main()