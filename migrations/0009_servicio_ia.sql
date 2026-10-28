-- Salud del servicio de IA (ROADMAP.md, 27/10/2026) -- el programa externo de revisión baja,
-- por cada cámara, una imagen "anotada" por un sistema de IA aparte (ver `[CAMARA]_ai.jpg`, que
-- Plant Report ignora). Antes de poder comparar imagen por cámara, el log de cada servidor intenta
-- leer el YAML de configuración de ese servicio por un puerto propio -- si eso falla, el problema
-- es de nuestro lado (Quantum Labs), no de la red/cámara del cliente, y hoy esa distinción se
-- perdía en el primer error de cada cámara. Un mismo servidor puede tener más de un puerto de IA
-- activo a la vez (ej. Api_Manzanillo, con hasta 4), cada uno con su propia salud.
CREATE TABLE IF NOT EXISTS servicio_ia (
    id              SERIAL PRIMARY KEY,
    cliente         TEXT NOT NULL,
    planta          TEXT NOT NULL,
    servidor        TEXT NOT NULL,
    puerto          INT NOT NULL,
    UNIQUE (cliente, planta, servidor, puerto),

    estado_actual   TEXT NOT NULL DEFAULT 'ok',  -- ok | caido
    estado_desde    DATE,

    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una fila por servicio por día: registro crudo, alimenta el reporte ejecutivo.
CREATE TABLE IF NOT EXISTS historial_servicio_ia (
    id          BIGSERIAL PRIMARY KEY,
    servicio_id INT NOT NULL REFERENCES servicio_ia(id),
    fecha       DATE NOT NULL,
    estado      TEXT NOT NULL,  -- ok | caido
    motivo      TEXT,
    UNIQUE (servicio_id, fecha)
);

CREATE INDEX IF NOT EXISTS historial_servicio_ia_servicio_fecha_idx
    ON historial_servicio_ia (servicio_id, fecha DESC);
