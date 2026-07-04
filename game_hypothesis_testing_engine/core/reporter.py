import json
from typing import Dict
from pathlib import Path
from .models import ValidationResult


class ReportGenerator:
    """Генерирует отчеты в различных форматах"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_json(self, result: ValidationResult, filename: str = None):
        """Экспорт в JSON"""
        if filename is None:
            filename = f"{result.hypothesis.id}_result.json"
        
        filepath = self.output_dir / filename
        
        data = {
            "hypothesis": {
                "id": result.hypothesis.id,
                "title": result.hypothesis.title,
                "description": result.hypothesis.description,
                "status": result.hypothesis.status.value,
                "score": {
                    "total": result.hypothesis.total_score,
                    "max": result.hypothesis.max_possible_score,
                    "percentage": result.hypothesis.score_percentage
                }
            },
            "claims": [
                {
                    "id": c.id,
                    "text": c.text,
                    "status": c.status.value,
                    "points": c.points_earned,
                    "evidence_count": len(c.evidence),
                    "counterarguments": c.counterarguments,
                    "rebuttals": c.rebuttals
                }
                for c in result.hypothesis.claims
            ],
            "recommendations": result.recommendations,
            "roadmap": result.roadmap,
            "risks": result.risks,
            "game_log": result.game_log
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 JSON отчет сохранен: {filepath}")
        return filepath
    
    def generate_markdown(self, result: ValidationResult, filename: str = None):
        """Экспорт в Markdown (паспорт гипотезы)"""
        if filename is None:
            filename = f"{result.hypothesis.id}_passport.md"
        
        filepath = self.output_dir / filename
        hypothesis = result.hypothesis
        
        md = []
        md.append(f"# Паспорт гипотезы: {hypothesis.title}\n")
        md.append(f"**ID:** {hypothesis.id}  ")
        md.append(f"**Статус:** {hypothesis.status.value}  ")
        md.append(f"**Оценка:** {hypothesis.total_score}/{hypothesis.max_possible_score} ({hypothesis.score_percentage:.1f}%)\n")
        
        md.append("## 📝 Описание\n")
        md.append(f"{hypothesis.description}\n")
        
        md.append("## ✅ Проверенные утверждения\n")
        for i, claim in enumerate(hypothesis.claims, 1):
            status_emoji = {"verified": "✅", "partially_verified": "⚠️", 
                          "unverified": "❌", "contradicted": "🔴"}
            emoji = status_emoji.get(claim.status.value, "❓")
            md.append(f"{i}. {emoji} **{claim.text}**")
            md.append(f"   - Очки: {claim.points_earned}/{claim.max_points}")
            if claim.evidence:
                md.append(f"   - Доказательств: {len(claim.evidence)}")
            md.append("")
        
        if hypothesis.challenges:
            md.append("## 🛡️ Отработанные контраргументы\n")
            for i, challenge in enumerate(hypothesis.challenges, 1):
                md.append(f"### Атака {i}")
                md.append(f"**Атака:** {challenge.attack_text}\n")
                md.append(f"**Защита:** {challenge.defense_text}\n")
        
        md.append("## 📋 Рекомендации\n")
        for i, rec in enumerate(result.recommendations, 1):
            md.append(f"{i}. {rec}")
        
        md.append("\n## 🗺️ Дорожная карта\n")
        for stage in result.roadmap:
            md.append(f"### {stage['stage']} ({stage['duration']})")
            for task in stage['tasks']:
                md.append(f"- {task}")
            md.append("")
        
        md.append("## ⚠️ Оценка рисков\n")
        md.append("| Риск | Вероятность | Влияние | Митигация |")
        md.append("|------|-------------|---------|-----------|")
        for risk in result.risks:
            md.append(f"| {risk['risk']} | {risk['probability']} | {risk['impact']} | {risk['mitigation']} |")
        
        content = "\n".join(md)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📄 Markdown паспорт сохранен: {filepath}")
        return filepath
    
    def generate_jira_json(self, result: ValidationResult, filename: str = None):
        """Экспорт в формате задачи для Jira/YouTrack"""
        if filename is None:
            filename = f"{result.hypothesis.id}_jira.json"
        
        filepath = self.output_dir / filename
        
        jira_task = {
            "project": "RND",
            "issuetype": {"name": "Research Hypothesis"},
            "summary": f"[{result.hypothesis.id}] {result.hypothesis.title}",
            "description": self._format_jira_description(result),
            "priority": {"name": self._map_priority(result.hypothesis.score_percentage)},
            "labels": ["hypothesis-validation", "game-engine"],
            "customfield_10100": result.hypothesis.score_percentage,  # Score
            "customfield_10101": result.hypothesis.status.value       # Status
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(jira_task, f, ensure_ascii=False, indent=2)
        
        print(f"🎫 Jira задача сохранена: {filepath}")
        return filepath
    
    def _format_jira_description(self, result: ValidationResult) -> str:
        """Форматирует описание для Jira"""
        desc = []
        desc.append("h2. Описание гипотезы")
        desc.append(result.hypothesis.description)
        desc.append("")
        
        desc.append("h2. Результаты валидации")
        desc.append(f"*Оценка:* {result.hypothesis.score_percentage:.1f}%")
        desc.append(f"*Статус:* {result.hypothesis.status.value}")
        desc.append("")
        
        desc.append("h2. Проверенные утверждения")
        for claim in result.hypothesis.claims:
            desc.append(f"* {claim.status.value.upper()}: {claim.text}")
        desc.append("")
        
        desc.append("h2. Рекомендации")
        for rec in result.recommendations:
            desc.append(f"* {rec}")
        
        return "\n".join(desc)
    
    def _map_priority(self, score: float) -> str:
        """Маппинг оценки в приоритет Jira"""
        if score >= 80:
            return "High"
        elif score >= 60:
            return "Medium"
        else:
            return "Low"