-- Bug real: UNIQUE (cliente, planta, servidor, [camara|puerto]) distinguia mayusculas, asi que un
-- --plant tecleado con otra capitalizacion (ej. "Apan" vs "APAN") no chocaba con la fila real y
-- creaba una camara/servicio "fantasma" aparte (ROADMAP.md, 27/10/2026 y 02/11/2026). La limpieza
-- de datos de esta ronda (61 perfiles de camara duplicados) se hizo aparte, antes de esta migracion,
-- igual que la de 146 filas del 28/10/2026 -- no se repite aqui a proposito (solo esquema).
ALTER TABLE perfil_camara DROP CONSTRAINT perfil_camara_cliente_planta_servidor_camara_key;
CREATE UNIQUE INDEX perfil_camara_identidad_ci_idx
    ON perfil_camara (lower(cliente), lower(planta), lower(servidor), lower(camara));

ALTER TABLE servicio_ia DROP CONSTRAINT servicio_ia_cliente_planta_servidor_puerto_key;
CREATE UNIQUE INDEX servicio_ia_identidad_ci_idx
    ON servicio_ia (lower(cliente), lower(planta), lower(servidor), puerto);
