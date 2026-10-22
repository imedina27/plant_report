-- Diagnóstico del .log por servidor (ver ROADMAP.md, sección 3 y log_parse.py), independiente del
-- resultado de las comparaciones de Fase 1/2 -- responde "¿el programa externo logró capturar esta
-- cámara ese día?", no "¿cambió su configuración/imagen?".
ALTER TABLE historial_comparacion
    ADD COLUMN IF NOT EXISTS log_ip              TEXT,
    ADD COLUMN IF NOT EXISTS log_estado          TEXT,    -- OK | ERROR | NULL (cámara no vista en el .log)
    ADD COLUMN IF NOT EXISTS log_motivo          TEXT,
    ADD COLUMN IF NOT EXISTS tiempo_proceso_seg  REAL;
