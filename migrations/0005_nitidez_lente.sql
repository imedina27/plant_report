-- Detección de lente sucio/desenfocado (ver ROADMAP.md, 26/10/2026 -- punto 2 del plan de mejoras
-- a image_compare.py). Mismo patrón que dias_no_concluyente_consecutivos: cuenta cuántos días
-- seguidos la nitidez de la cámara sale sospechosa contra su propia línea base histórica, para
-- alertar solo ante una caída sostenida, no un solo día malo.
ALTER TABLE perfil_camara ADD COLUMN IF NOT EXISTS dias_borroso_consecutivos INT NOT NULL DEFAULT 0;

-- Valores crudos de nitidez del día, para poder revisar/recalibrar después con datos reales
-- (mismo criterio que orb_desplazamiento/fase_desplazamiento).
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS nitidez_actual REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS nitidez_mediana_historica REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS nitidez_mad_historica REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS nitidez_sospechosa BOOLEAN;
