-- Esquema inicial de Fase 3 (ver ROADMAP.md, sección "Persistencia en base de datos").
-- Una fila por cámara física: catálogo (identidad) + estado vivo (semáforo, sección 2.7) +
-- perfil estadístico (Experimentos 1-9 de Fase 2).
CREATE TABLE IF NOT EXISTS perfil_camara (
    id                      SERIAL PRIMARY KEY,
    cliente                 TEXT NOT NULL,
    planta                  TEXT NOT NULL,
    servidor                TEXT NOT NULL,
    camara                  TEXT NOT NULL,
    UNIQUE (cliente, planta, servidor, camara),

    estado_actual                     TEXT NOT NULL DEFAULT 'verde',
        -- verde | amarillo | rojo | morado | base_desactualizada
    estado_desde                      DATE,
    dias_no_concluyente_consecutivos  INT NOT NULL DEFAULT 0,

    mediana_desplazamiento    REAL,
    p95_desplazamiento        REAL,
    metodo_preferido          TEXT,     -- orb | fase | ambos | NULL (arranque en frío)
    n_confirmaciones_humanas  INT NOT NULL DEFAULT 0,
    ultimo_recalculo          DATE,

    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una fila por cámara por día: registro crudo, alimenta el reporte ejecutivo y el recálculo de perfil.
CREATE TABLE IF NOT EXISTS historial_comparacion (
    id              BIGSERIAL PRIMARY KEY,
    camara_id       INT NOT NULL REFERENCES perfil_camara(id),
    fecha           DATE NOT NULL,

    config_status        TEXT,    -- OK | REVISAR | MARCA_NO_SOPORTADA | SIN_ARCHIVO
    config_marca          TEXT,
    config_diferencias    JSONB,

    imagen_status         TEXT,    -- OK | NO_CONCLUYENTE | REVISAR | BASE_DESACTUALIZADA | SIN_ARCHIVO
    imagen_motivo          TEXT,
    orb_inliers            INT,
    orb_desplazamiento     REAL,
    fase_confianza         REAL,
    fase_desplazamiento    REAL,

    veredicto_humano   TEXT,    -- bien | mal | desactualizada | NULL
    modo               TEXT NOT NULL,  -- interactivo | sin_interaccion
    corrida_ts         TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (camara_id, fecha)
);

CREATE INDEX IF NOT EXISTS historial_comparacion_camara_fecha_idx
    ON historial_comparacion (camara_id, fecha DESC);
