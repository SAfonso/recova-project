-- E3: Add score_breakdown JSONB column to gold.solicitudes
-- Stores the audit trail of how each score was computed:
--   {"base_score": 50, "categoria": "standard", "recency_penalty": -20, "total": 30}

ALTER TABLE gold.solicitudes
ADD COLUMN IF NOT EXISTS score_breakdown JSONB;

COMMENT ON COLUMN gold.solicitudes.score_breakdown IS
    'Desglose del cálculo de score: base_score, categoria, recency_penalty, single_date_bonus, custom_rules_bonus, total';
