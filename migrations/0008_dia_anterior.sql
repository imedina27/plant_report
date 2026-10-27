-- Comparación contra el día anterior, además de la base fija (ver ROADMAP.md, 26/10/2026 --
-- punto 5 del plan de mejoras a image_compare.py). Puramente informativa por ahora: no cambia la
-- decisión OK/REVISAR/NO CONCLUYENTE existente.
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS diaanterior_status TEXT;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS diaanterior_motivo TEXT;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS diaanterior_orb_desplazamiento REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS diaanterior_fase_desplazamiento REAL;
