from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ClaimStatus(Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class HypothesisStatus(Enum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"
    APPROVED_FOR_PILOT = "approved_for_pilot"


@dataclass
class Evidence:
    """Доказательство из базы знаний"""
    source: str                    # Источник (файл, статья, патент)
    snippet: str                   # Цитата/фрагмент
    data_point: Optional[Dict] = None  # Конкретная цифра/факт
    confidence: float = 0.9


@dataclass
class Claim:
    """Атомарное утверждение гипотезы"""
    id: str
    text: str
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    evidence: List[Evidence] = field(default_factory=list)
    points_earned: int = 0
    max_points: int = 10
    counterarguments: List[str] = field(default_factory=list)
    rebuttals: List[str] = field(default_factory=list)


@dataclass
class Challenge:
    """Контраргумент от "Адвоката дьявола" """
    round_number: int
    attack_text: str
    defense_text: Optional[str] = None
    resolved: bool = False
    points_delta: int = 0


@dataclass
class Hypothesis:
    """Гипотеза на валидацию"""
    id: str
    title: str
    description: str
    claims: List[Claim] = field(default_factory=list)
    challenges: List[Challenge] = field(default_factory=list)
    total_score: int = 0
    max_possible_score: int = 0
    status: HypothesisStatus = HypothesisStatus.NEEDS_REVISION
    metadata: Dict = field(default_factory=dict)
    
    @property
    def score_percentage(self) -> float:
        if self.max_possible_score == 0:
            return 0.0
        return (self.total_score / self.max_possible_score) * 100


@dataclass
class ValidationResult:
    """Итоговый результат валидации"""
    hypothesis: Hypothesis
    game_log: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    roadmap: List[Dict] = field(default_factory=list)
    risks: List[Dict] = field(default_factory=list)