-- Salud absoluta de imagen (ver ROADMAP.md, 26/10/2026 -- punto 3 del plan de mejoras a
-- image_compare.py): detecta obstrucción total del lente de forma directa (varianza casi nula o
-- brillo en un extremo), sin necesitar base ni historial -- funciona desde el primer día.
-- A diferencia de la nitidez (punto 2), es un disparador inmediato de un solo día, no necesita
-- contador de racha en perfil_camara.
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS salud_varianza REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS salud_brillo REAL;
ALTER TABLE historial_comparacion ADD COLUMN IF NOT EXISTS salud_sospechosa BOOLEAN;
