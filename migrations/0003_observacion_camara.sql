-- Notas de contexto humano por cámara (ROADMAP.md, "Observaciones por cámara"). Viven ligadas a la
-- cámara, no a un día puntual -- una bitácora, no una fila por corrida: varias pueden coexistir a
-- lo largo del tiempo, y "borrar" una la cierra (resuelta_en) en vez de eliminarla, para no perder
-- el contexto de por qué algo se ignoró en su momento.
CREATE TABLE IF NOT EXISTS observacion_camara (
    id          BIGSERIAL PRIMARY KEY,
    camara_id   INT NOT NULL REFERENCES perfil_camara(id),
    texto       TEXT NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resuelta_en TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS observacion_camara_camara_idx
    ON observacion_camara (camara_id, resuelta_en);
