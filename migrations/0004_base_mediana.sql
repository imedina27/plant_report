-- Base de referencia por mediana (ver ROADMAP.md, 26/10/2026 -- "Diseño propuesto: mejoras a
-- image_compare.py", paso 3). Marca que una cámara tiene una base provisional (un solo .jpg,
-- recién puesto a mano en ventana_bases.py) en lo que se junta suficiente historial fresco para
-- reemplazarla sola por una mediana -- NULL significa que no hay ninguna promoción pendiente.
ALTER TABLE perfil_camara ADD COLUMN IF NOT EXISTS base_reemplazada_el DATE;
