"""ScoringConfig — configuración de scoring leída desde silver.open_mics.config (JSONB).

Reemplaza las constantes hardcodeadas del scoring_engine:
  · CATEGORY_BONUS           → ScoringConfig.categories
  · penalización recencia     → ScoringConfig.recency_penalty_*
  · bono bala única           → ScoringConfig.single_date_boost_*
  · ventana de ediciones      → ScoringConfig.recency_last_n_editions

La estructura del JSONB esperado está documentada en specs/sql/v3_schema.sql §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Valores por defecto — deben mantenerse sincronizados con el DEFAULT JSONB
# definido en silver.open_mics.config (specs/sql/v3_schema.sql §3).
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    "available_slots": 8,
    "categories": {
        "standard":   {"base_score": 50,   "enabled": True},
        "priority":   {"base_score": 70,   "enabled": True},
        "gold":       {"base_score": 90,   "enabled": True},
        "restricted": {"base_score": None, "enabled": True},
    },
    "recency_penalty": {
        "enabled": True,
        "last_n_editions": 2,
        "penalty_points": 20,
    },
    "single_date_boost": {
        "enabled": True,
        "boost_points": 10,
    },
    "gender_parity": {
        "enabled": False,
        "target_female_nb_pct": 40,
    },
}


@dataclass(frozen=True)
class CustomRule:
    """Regla de scoring basada en un campo no canónico de solicitudes.metadata."""

    field: str        # título del campo en solicitudes.metadata
    condition: str    # "equals" (único en v0.15.0)
    value: str        # valor que activa la regla
    points: int       # bono (+) o penalización (-)
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CustomRule":
        return cls(
            field=raw["field"],
            condition=raw.get("condition", "equals"),
            value=raw["value"],
            points=int(raw["points"]),
            enabled=bool(raw.get("enabled", True)),
            description=raw.get("description", ""),
        )

    def matches(self, metadata: dict) -> bool:
        """True si la respuesta en metadata cumple la condición (case-insensitive)."""
        if not self.enabled:
            return False
        answer = metadata.get(self.field, "")
        if self.condition == "equals":
            return str(answer).strip().lower() == self.value.strip().lower()
        return False


@dataclass(frozen=True)
class CategoryRule:
    """Regla de puntuación para una categoría de cómico."""

    base_score: int | None  # None = restringido (no puede acturar)
    enabled: bool = True

    @property
    def is_restricted(self) -> bool:
        """True si la categoría bloquea la participación del cómico."""
        return self.base_score is None or not self.enabled

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CategoryRule":
        return cls(
            base_score=raw.get("base_score"),  # None es válido (restricted)
            enabled=bool(raw.get("enabled", True)),
        )


@dataclass(frozen=True)
class ScoringConfig:
    """Configuración completa de scoring para un open_mic concreto.

    Instanciar con ``ScoringConfig.from_dict(open_mic_id, raw_jsonb_dict)``.
    """

    open_mic_id: str
    available_slots: int

    # Reglas por categoría — clave: nombre de categoría en minúsculas
    categories: dict[str, CategoryRule] = field(default_factory=dict)

    # Penalización de recencia (scoped por open_mic_id, no global)
    recency_penalty_enabled: bool = True
    recency_last_n_editions: int = 2
    recency_penalty_points: int = 20

    # Bono bala única (disponible solo para una fecha)
    single_date_boost_enabled: bool = True
    single_date_boost_points: int = 10

    # Paridad de género
    gender_parity_enabled: bool = False
    gender_parity_target_pct: int = 40  # % objetivo femenino/nb

    # Scoring custom (Sprint 10)
    scoring_type: str = "basic"  # 'none' | 'basic' | 'custom'
    custom_scoring_rules: list[CustomRule] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Constructor principal
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, open_mic_id: str, raw: dict[str, Any]) -> "ScoringConfig":
        """Construye un ScoringConfig desde el JSONB de silver.open_mics.config.

        Cualquier clave ausente se rellena con _DEFAULTS, por lo que el objeto
        es siempre válido aunque el JSONB esté parcialmente configurado.

        Args:
            open_mic_id: UUID del open_mic al que pertenece esta configuración.
            raw: dict cargado del JSONB (puede estar vacío o incompleto).
        """
        if not isinstance(raw, dict):
            raw = {}

        # Merge a un nivel de categorías (no deep-merge completo)
        default_cats = _DEFAULTS["categories"]
        raw_cats = raw.get("categories", {})
        merged_cats: dict[str, CategoryRule] = {}
        for cat_name, default_rule in default_cats.items():
            raw_rule = raw_cats.get(cat_name, default_rule)
            merged_cats[cat_name] = CategoryRule.from_dict(raw_rule)
        # Categorías extra definidas en el JSONB pero no en defaults
        for cat_name, raw_rule in raw_cats.items():
            if cat_name not in merged_cats:
                merged_cats[cat_name] = CategoryRule.from_dict(raw_rule)

        recency = raw.get("recency_penalty", _DEFAULTS["recency_penalty"])
        boost   = raw.get("single_date_boost", _DEFAULTS["single_date_boost"])
        parity  = raw.get("gender_parity", _DEFAULTS["gender_parity"])

        raw_rules = raw.get("custom_scoring_rules", [])
        custom_rules = [CustomRule.from_dict(r) for r in raw_rules if isinstance(r, dict)]

        return cls(
            open_mic_id=open_mic_id,
            available_slots=int(raw.get("available_slots", _DEFAULTS["available_slots"])),
            categories=merged_cats,
            recency_penalty_enabled=bool(recency.get("enabled", True)),
            recency_last_n_editions=int(recency.get("last_n_editions", 2)),
            recency_penalty_points=int(recency.get("penalty_points", 20)),
            single_date_boost_enabled=bool(boost.get("enabled", True)),
            single_date_boost_points=int(boost.get("boost_points", 10)),
            gender_parity_enabled=bool(parity.get("enabled", False)),
            gender_parity_target_pct=int(parity.get("target_female_nb_pct", 40)),
            scoring_type=raw.get("scoring_type", "basic"),
            custom_scoring_rules=custom_rules,
        )

    @classmethod
    def default(cls, open_mic_id: str) -> "ScoringConfig":
        """Instancia con todos los valores por defecto. Útil en tests y fallbacks."""
        return cls.from_dict(open_mic_id, {})

    # ------------------------------------------------------------------
    # Lógica de scoring
    # ------------------------------------------------------------------

    def category_rule(self, category: str) -> CategoryRule:
        """Devuelve la regla de la categoría, o 'standard' si no existe."""
        return self.categories.get(category.lower(), self.categories.get("standard", CategoryRule(base_score=0)))

    def is_restricted(self, category: str) -> bool:
        """True si el cómico con esta categoría debe ser descartado."""
        return self.category_rule(category).is_restricted

    def compute_score(
        self,
        category: str,
        has_recency_penalty: bool,
        is_single_date: bool,
    ) -> int | None:
        """Calcula el score final para un candidato.

        Returns:
            int  — puntuación calculada.
            None — el cómico está restringido y debe descartarse.
        """
        rule = self.category_rule(category)
        if rule.is_restricted:
            return None

        score = rule.base_score or 0

        if self.recency_penalty_enabled and has_recency_penalty:
            score -= self.recency_penalty_points

        if self.single_date_boost_enabled and is_single_date:
            score += self.single_date_boost_points

        return score

    def apply_custom_rules(self, metadata: dict) -> int:
        """Suma puntos de reglas custom habilitadas que coinciden con metadata.

        Solo aplica si scoring_type == 'custom'. Si no, devuelve 0.
        El campo 'backup' está reservado para el flag de último momento
        y se ignora aunque exista una regla que lo referencie.
        """
        if self.scoring_type != "custom":
            return 0
        return sum(
            r.points
            for r in self.custom_scoring_rules
            if r.field != "backup" and r.matches(metadata)
        )
