# Changelog

Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), agrupado por
fecha en vez de versión (este proyecto no se publica como paquete). Es un registro **breve** de
qué cambió y cuándo -- el *por qué* de cada decisión está en [ROADMAP.md](ROADMAP.md), que sigue
siendo la fuente de verdad del proyecto.

## 2026-10-26

### Agregado
- `CLAUDE.md` (convenciones del proyecto) y `CLAUDE.local.md` (notas personales, no versionado).
- `CHANGELOG.md` (este archivo).
- Carpeta `diagramas/`, con el primer diagrama de flujo (`01-flujo-main.md`) de `main.py`.

### Cambiado
- **Reestructuración del proyecto por paquetes**: `comparacion/`, `persistencia/`, `reporte/`,
  `integraciones/` y `ui/` agrupan los módulos por responsabilidad; `scripts/` concentra todos los
  de un solo uso (antes repartidos en la raíz). Los puntos de entrada (`main.py`,
  `generar_reporte.py`, `migrate.py`) se quedan en la raíz, sin cambios para quien los corre.

### Corregido
- Un `.jpg` dañado ya no tumba la ventana de revisión ni la generación del PDF -- se muestra un
  marcador ("Imagen no disponible") en su lugar.
- `backfill_reportes.py` quedó desactualizado tras agregar la escalada de ámbar a morado del día
  anterior; ya vuelve a reflejar la máquina de estados real.

## 2026-10-22

### Agregado
- `generar_reporte.py`: genera (y envía) el reporte ejecutivo de un día ya procesado, sin repetir
  la comparación de cámaras.
- Columna "No concluyente" en el resumen del PDF; "Base de imágenes desactualizada" ahora cuenta
  como falla.
- Valor especial `NINGUNO` en `REPORTE_DESTINATARIOS_<CLIENTE>` para suprimir el correo de un
  cliente a propósito.

### Cambiado
- Las cámaras "no concluyentes" (ámbar) se fuerzan a revisión humana al 3er día seguido, en vez de
  quedarse en ámbar indefinidamente sin que nadie las vea.
- Banderas de `main.py` renombradas al inglés (`--client`, `--date`, `--no-interaction`); el texto
  de ayuda (`-h`) se tradujo al español.
- README reescrito para reflejar las Fases 1-5 (antes solo cubría la comparación de
  configuración).
- Reporte ejecutivo: orden de servidores de AbInBev, layout de la columna de disco, etiquetas de
  falla separadas del motivo técnico.

### Corregido
- `--client` ahora resuelve el nombre del cliente sin importar mayúsculas/minúsculas, en vez de
  generar un PDF vacío.
- Una caída de la API de `Monit_Servers_V2` ya no tumba el reporte ejecutivo completo.
- Orden de servidores en las hojas de detalle del PDF, para que coincida con el resumen.
- El valor `NINGUNO` no se respetaba cuando venía de `REPORTE_DESTINATARIOS_DEFAULT`.
- El par de imágenes base/actual se salía del borde derecho de la tabla de fallas.
- Formato de fecha en el nombre del PDF (ahora `DDMMYYYY`) y cierre tardío de la ventana de
  revisión.
- `--cliente` no acotaba el paso de generación/envío del reporte (causó el reenvío accidental de
  un correo).

## 2026-10-21

### Agregado
- Fase 3: persistencia en PostgreSQL, ingestión del `.log` del servidor, observaciones por
  cámara.
- Fase 4: generación del reporte ejecutivo en PDF.
- Fase 5: envío del reporte ejecutivo por correo.
- Scripts puntuales para llenar las bases de configuración/imagen y auditar datos reales de
  octubre.
- Bandera `--fecha` en `main.py`.

### Cambiado
- Fases 3-5 conectadas a `main.py`, con filtro `--cliente`.

## 2026-10-03

### Agregado
- Fase 2 implementada: módulo de comparación de imagen (ORB+RANSAC, correlación de fase).
- Ventanas de revisión humana (`ventana_revision.py`) y de reemplazo de base (`ventana_bases.py`).
- Soporte DAHUA en la comparación de configuración (Fase 1).
- Script independiente de captura de imagen para AXIS/DAHUA/HIKVISION/VIVOTEK.
- Campos de zoom para HIKVISION y VIVOTEK en la comparación de configuración.

### Cambiado
- Documentados los Experimentos 8 y 9, y el diseño del perfil estadístico por cámara (ver
  ROADMAP).

## 2026-09-30 a 2026-10-02

### Cambiado
- Definido el método de comparación de imagen de la Fase 2 con evidencia experimental
  (Experimentos 4 a 7b) -- ver ROADMAP.md para el detalle completo de cada uno.

## 2026-09-22

### Agregado
- Fase 1 implementada: comparación de configuración JSON de cámaras (AXIS, HIKVISION, VIVOTEK).
- Atajo `'h'` para usar la fecha de hoy en `main.py`.

### Cambiado
- Documentadas las decisiones de diseño de la Fase 1; se agrega la Fase 6 (envío de correo) al
  ROADMAP.

## 2026-09-18 a 2026-09-19

### Agregado
- Primer commit del proyecto; `ROADMAP.md` inicial.
- `log_sorter` para reordenar las líneas por cámara en los logs de revisión.

### Eliminado
- El ordenamiento de logs se quitó del alcance del proyecto -- lo asumió el programa externo de
  revisión de cámaras.
