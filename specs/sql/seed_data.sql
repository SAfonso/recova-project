-- =========================================================
-- AI LineUp Architect - Seed Data con casos de borde
-- Genera silver.proveedores, silver.comicos, bronze.solicitudes
-- y silver.solicitudes con linaje bronze_id
-- =========================================================

BEGIN;

-- 1) Proveedores (Silver)
INSERT INTO silver.proveedores (id, nombre_comercial, slug)
VALUES
  ('10000000-0000-0000-0000-000000000001', 'La Recova Open Mic', 'recova-om'),
  ('10000000-0000-0000-0000-000000000002', 'Comedy Lab', 'comedy-lab')
ON CONFLICT (id) DO NOTHING;

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

-- 3) Solicitudes Bronze asociadas (origen de linaje)
INSERT INTO bronze.solicitudes (
  id,
  proveedor_id,
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
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 1001, 'Mati General', '@general_mati', '+5491111111106', 'intermedio', to_char(current_date + 1, 'YYYY-MM-DD'), 'si', 'Show barrial', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 1002, 'Mati General', '@general_mati', '+5491111111106', 'intermedio', to_char(current_date + 4, 'YYYY-MM-DD'), 'si', 'Show barrial', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000002', 1003, 'Mati General', '@general_mati', '+5491111111106', 'intermedio', to_char(current_date + 7, 'YYYY-MM-DD'), 'no', 'Bar local', 'recomendacion', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002', 1004, 'Mati General', '@general_mati', '+5491111111106', 'intermedio', to_char(current_date + 10, 'YYYY-MM-DD'), 'si', 'Open mic', 'whatsapp', '{"seed": true}'::jsonb, true),

  ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', 1005, 'Nora Priority', '@prioridad_nora', '+5491111111103', 'avanzado', to_char(current_date + 5, 'YYYY-MM-DD'), 'si', 'Teatro', 'instagram', '{"seed": true, "caso": "doblete"}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000002', 1006, 'Nora Priority', '@prioridad_nora', '+5491111111103', 'avanzado', to_char(current_date + 6, 'YYYY-MM-DD'), 'si', 'Teatro', 'instagram', '{"seed": true, "caso": "doblete"}'::jsonb, true),

  ('30000000-0000-0000-0000-000000000007', '10000000-0000-0000-0000-000000000001', 1007, 'El Cancelado', '@el_cancelado', '+5491111111111', 'intermedio', to_char(current_date + 2, 'YYYY-MM-DD'), 'si', 'N/A', 'instagram', '{"seed": true, "caso": "restringido"}'::jsonb, true),

  ('30000000-0000-0000-0000-000000000008', '10000000-0000-0000-0000-000000000001', 1008, 'Veterano Alpha', '@veterano_alpha', '+5491111111101', 'pro', to_char(current_date + 3, 'YYYY-MM-DD'), 'no', 'Teatro', 'referido', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000009', '10000000-0000-0000-0000-000000000002', 1009, 'Veterano Beta', '@veterano_beta', '+5491111111102', 'pro', to_char(current_date + 6, 'YYYY-MM-DD'), 'si', 'Show privado', 'referido', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000010', '10000000-0000-0000-0000-000000000001', 1010, 'Tomi Priority', '@prioridad_tomi', '+5491111111104', 'intermedio', to_char(current_date + 8, 'YYYY-MM-DD'), 'si', 'Open mic', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000002', 1011, 'Luz Priority', '@prioridad_luz', '+5491111111105', 'intermedio', to_char(current_date + 9, 'YYYY-MM-DD'), 'no', 'Bar local', 'amigos', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001', 1012, 'Ro General', '@general_ro', '+5491111111107', 'inicial', to_char(current_date + 11, 'YYYY-MM-DD'), 'si', 'Primera vez', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000013', '10000000-0000-0000-0000-000000000002', 1013, 'Santi General', '@general_santi', '+5491111111108', 'intermedio', to_char(current_date + 12, 'YYYY-MM-DD'), 'no', 'Ronda de bares', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000014', '10000000-0000-0000-0000-000000000001', 1014, 'Eli General', '@general_eli', '+5491111111109', 'inicial', to_char(current_date + 13, 'YYYY-MM-DD'), 'si', 'Escenario chico', 'whatsapp', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000015', '10000000-0000-0000-0000-000000000002', 1015, 'Fer General', '@general_fer', '+5491111111110', 'intermedio', to_char(current_date + 14, 'YYYY-MM-DD'), 'si', 'Open set', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000016', '10000000-0000-0000-0000-000000000001', 1016, 'Tomi Priority', '@prioridad_tomi', '+5491111111104', 'intermedio', to_char(current_date + 15, 'YYYY-MM-DD'), 'si', 'Open set', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000017', '10000000-0000-0000-0000-000000000002', 1017, 'Ro General', '@general_ro', '+5491111111107', 'inicial', to_char(current_date + 2, 'YYYY-MM-DD'), 'no', 'Primera vez', 'instagram', '{"seed": true}'::jsonb, true),
  ('30000000-0000-0000-0000-000000000018', '10000000-0000-0000-0000-000000000001', 1018, 'Santi General', '@general_santi', '+5491111111108', 'intermedio', to_char(current_date + 4, 'YYYY-MM-DD'), 'si', 'Bar local', 'recomendacion', '{"seed": true}'::jsonb, true)
ON CONFLICT (id) DO NOTHING;

-- 4) Solicitudes Silver (18 registros)
INSERT INTO silver.solicitudes (
  id,
  bronze_id,
  proveedor_id,
  comico_id,
  fecha_evento,
  nivel_experiencia,
  disponibilidad_ultimo_minuto,
  score_final,
  status,
  metadata_ia
)
VALUES
  ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000006', current_date + 1, 2, true,  72.00, 'normalizado', '{"caso": "spammer"}'::jsonb),
  ('40000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000006', current_date + 4, 2, true,  70.00, 'normalizado', '{"caso": "spammer"}'::jsonb),
  ('40000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000006', current_date + 7, 2, false, 66.00, 'normalizado', '{"caso": "spammer"}'::jsonb),
  ('40000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000006', current_date + 10,2, true,  69.00, 'normalizado', '{"caso": "spammer"}'::jsonb),

  ('40000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000003', current_date + 5, 3, true,  84.00, 'normalizado', '{"caso": "doblete"}'::jsonb),
  ('40000000-0000-0000-0000-000000000006', '30000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000003', current_date + 6, 3, true,  85.00, 'normalizado', '{"caso": "doblete"}'::jsonb),

  ('40000000-0000-0000-0000-000000000007', '30000000-0000-0000-0000-000000000007', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000011', current_date + 2, 2, true,  78.00, 'normalizado', '{"caso": "restringido_activo"}'::jsonb),

  ('40000000-0000-0000-0000-000000000008', '30000000-0000-0000-0000-000000000008', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', current_date + 3, 3, false, 91.00, 'scorado', '{"ai_modifier": 6}'::jsonb),
  ('40000000-0000-0000-0000-000000000009', '30000000-0000-0000-0000-000000000009', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', current_date + 6, 3, true,  93.00, 'aprobado', '{"ai_modifier": 8}'::jsonb),
  ('40000000-0000-0000-0000-000000000010', '30000000-0000-0000-0000-000000000010', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', current_date + 8, 2, true,  79.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000011', '30000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000005', current_date + 9, 2, false, 77.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000012', '30000000-0000-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000007', current_date + 11,1, true,  60.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000013', '30000000-0000-0000-0000-000000000013', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000008', current_date + 12,2, false, 64.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000014', '30000000-0000-0000-0000-000000000014', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000009', current_date + 13,1, true,  58.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000015', '30000000-0000-0000-0000-000000000015', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000010', current_date + 14,2, true,  62.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000016', '30000000-0000-0000-0000-000000000016', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', current_date + 15,2, true,  73.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000017', '30000000-0000-0000-0000-000000000017', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000007', current_date + 2, 1, false, 55.00, 'normalizado', '{}'::jsonb),
  ('40000000-0000-0000-0000-000000000018', '30000000-0000-0000-0000-000000000018', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000008', current_date + 4, 2, true,  65.00, 'normalizado', '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;

COMMIT;
