-- Semáforo de configuración, separado del de imagen (ROADMAP.md, 28/10/2026). Más simple que el de
-- imagen (solo "ok"/"incidencia"): un cambio de configuración es una comparación exacta campo por
-- campo, sin señales ruidosas que ameriten estados intermedios como ámbar/morado.
ALTER TABLE perfil_camara
    ADD COLUMN IF NOT EXISTS config_estado_actual TEXT NOT NULL DEFAULT 'ok',
    ADD COLUMN IF NOT EXISTS config_incidencia_desde DATE;

-- Veredicto humano del cambio de configuración -- columna aparte de veredicto_humano (el de
-- imagen), porque una misma cámara puede tener los dos pendientes el mismo día.
ALTER TABLE historial_comparacion
    ADD COLUMN IF NOT EXISTS config_veredicto_humano TEXT;
