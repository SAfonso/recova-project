-- =========================================================
-- AI LineUp Architect - Seed Data con casos de borde
-- Genera silver.proveedores, silver.comicos, bronze.solicitudes
-- y silver.solicitudes con linaje bronze_id
-- v3: incluye silver.open_mics y silver.organization_members
-- =========================================================

BEGIN;

-- 1) Proveedores (Silver)
INSERT INTO silver.proveedores (id, nombre_comercial, slug)
VALUES
  ('10000000-0000-0000-0000-000000000001', 'La Recova Open Mic', 'recova-om'),
  ('10000000-0000-0000-0000-000000000002', 'Comedy Lab', 'comedy-lab')
ON CONFLICT (id) DO NOTHING;

-- 1b) Open Mics (v3)
INSERT INTO silver.open_mics (id, proveedor_id, nombre, config)
VALUES
  (
    '20000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'Recova Open Mic — Edición principal',
    '{
      "available_slots": 8,
      "categories": {
        "standard":   {"base_score": 50,   "enabled": true},
        "priority":   {"base_score": 70,   "enabled": true},
        "gold":       {"base_score": 90,   "enabled": true},
        "restricted": {"base_score": null, "enabled": true}
      },
      "recency_penalty":   {"enabled": true,  "last_n_editions": 2, "penalty_points": 20},
      "single_date_boost": {"enabled": true,  "boost_points": 10},
      "gender_parity":     {"enabled": false, "target_female_nb_pct": 40}
    }'::jsonb
  ),
  (
    '20000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000002',
    'Comedy Lab — Sesión mensual',
    '{}'::jsonb
  )
ON CONFLICT (id) DO NOTHING;

-- 1c) Organization Members (v3)
-- IMPORTANTE: sustituye el UUID de abajo por tu auth.uid() real antes de ejecutar.
-- Puedes obtenerlo en Supabase → Authentication → Users → copia el User UID.
-- INSERT INTO silver.organization_members (user_id, proveedor_id, role)
-- VALUES
--   ('<TU-AUTH-UID-AQUI>', '10000000-0000-0000-0000-000000000001', 'host')
-- ON CONFLICT (user_id, proveedor_id) DO NOTHING;

-- 2) Cómicos Silver (2 gold, 3 priority, 5 general, 1 restricted)
INSERT INTO silver.comicos (
  id,
  instagram,
  nombre,
  telefono,
  categoria,
  metadata_comico
)
VALUES
  ('20000000-0000-0000-0000-000000000001', 'veterano_alpha', 'Veterano Alpha', '+5491111111101', 'gold', '{}'),
  ('20000000-0000-0000-0000-000000000002', 'veterano_beta',  'Veterano Beta',  '+5491111111102', 'gold', '{}'),

  ('20000000-0000-0000-0000-000000000003', 'prioridad_nora', 'Nora Priority',  '+5491111111103', 'priority', '{}'),
  ('20000000-0000-0000-0000-000000000004', 'prioridad_tomi', 'Tomi Priority',  '+5491111111104', 'priority', '{}'),
  ('20000000-0000-0000-0000-000000000005', 'prioridad_luz',  'Luz Priority',   '+5491111111105', 'priority', '{}'),

  ('20000000-0000-0000-0000-000000000006', 'general_mati',   'Mati General',   '+5491111111106', 'general', '{}'),
  ('20000000-0000-0000-0000-000000000007', 'general_ro',     'Ro General',     '+5491111111107', 'general', '{}'),
  ('20000000-0000-0000-0000-000000000008', 'general_santi',  'Santi General',  '+5491111111108', 'general', '{}'),
  ('20000000-0000-0000-0000-000000000009', 'general_eli',    'Eli General',    '+5491111111109', 'general', '{}'),
  ('20000000-0000-0000-0000-000000000010', 'general_fer',    'Fer General',    '+5491111111110', 'general', '{}'),

  (
    '20000000-0000-0000-0000-000000000011',
    'el_cancelado',
    'El Cancelado',
    '+5491111111111',
    'restricted',
    '{"motivo": "Falta de respeto al público", "fecha_veto": "2026-01-01"}'::jsonb
  )
ON CONFLICT (instagram) DO NOTHING;

-- 3) Solicitudes Bronze asociadas (origen de linaje) — v3: incluye open_mic_id
--    Escenario controlado: 5 cómicos distintos para el mismo show (2026-04-04)
INSERT INTO bronze.solicitudes (
  id,
  proveedor_id,
  open_mic_id,
  sheet_row_id,
  nombre_raw,
  instagram_raw,
  telefono_raw,
  experiencia_raw,
  fechas_seleccionadas_raw,
  disponibilidad_ultimo_minuto,
  info_show_cercano,
  origen_conocimiento,
  raw_data_extra,
  procesado
)
VALUES
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 1001, 'Veterano Alpha', '@veterano_alpha', '+5491111111101', 'Llevo tiempo haciendo stand-up', '04-04-26', 'Sí', 'Teatro', 'referido', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 1002, 'Veterano Beta',  '@veterano_beta',  '+5491111111102', 'Soy un profesional / tengo cachés', '04-04-26', 'No', 'Show privado', 'referido', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 1003, 'Nora Priority',  '@prioridad_nora', '+5491111111103', 'Llevo tiempo haciendo stand-up', '04-04-26', 'Sí', 'Open mic', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 1004, 'Tomi Priority',  '@prioridad_tomi', '+5491111111104', 'He probado alguna vez', '04-04-26', 'Sí', 'Bar local', 'whatsapp', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 1005, 'Luz Priority',   '@prioridad_luz',  '+5491111111105', 'He probado alguna vez', '04-04-26', 'No', 'Escenario chico', 'amigos', '{"seed": true}'::jsonb, true)
ON CONFLICT (id) DO NOTHING;

-- 4) Solicitudes Silver (5 registros, mismo día: 2026-04-04, distinto status) — v3: incluye open_mic_id
INSERT INTO silver.solicitudes (
  id,
  bronze_id,
  proveedor_id,
  open_mic_id,
  comico_id,
  fecha_evento,
  nivel_experiencia,
  disponibilidad_ultimo_minuto,
  status,
  metadata_ia
)
VALUES
  ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', DATE '2026-04-04', 3, true,  'normalizado',      '{"seed_case": "same_day_status_mix"}'::jsonb),
  ('40000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', DATE '2026-04-04', 3, false, 'scorado',          '{"seed_case": "same_day_status_mix"}'::jsonb),
  ('40000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000003', DATE '2026-04-04', 3, true,  'aprobado',         '{"seed_case": "same_day_status_mix"}'::jsonb),
  ('40000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000004', DATE '2026-04-04', 2, true,  'no_seleccionado',  '{"seed_case": "same_day_status_mix"}'::jsonb),
  ('40000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000005', DATE '2026-04-04', 2, false, 'rechazado',        '{"seed_case": "same_day_status_mix"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

COMMIT;
