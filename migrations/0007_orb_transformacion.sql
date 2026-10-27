-- Desplazamiento de RANSAC descompuesto en traslación/rotación/escala (ver ROADMAP.md,
-- 26/10/2026 -- punto 4 del plan de mejoras a image_compare.py), en vez de solo el promedio de
-- distancia entre puntos -- para poder distinguir un giro de un desplazamiento lineal. Puramente
-- informativo por ahora: no cambia la decisión OK/REVISAR existente.
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS orb_tx REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS orb_ty REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS orb_rotacion_deg REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS orb_escala REAL;
