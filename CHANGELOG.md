# Changelog

Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), agrupado por
fecha en vez de versión (este proyecto no se publica como paquete). Es un registro **breve** de
qué cambió y cuándo -- el *por qué* de cada decisión está en [ROADMAP.md](ROADMAP.md), que sigue
siendo la fuente de verdad del proyecto.

## 2026-10-27

### Agregado

- Separación de la base "para mostrar" (`IMAGE_BASE_ROOT`, foto real de un solo día) y la base
  "para calcular" (`IMAGE_BASE_MEDIANA_ROOT`, nueva variable de entorno, la mediana por píxel):
  la mediana podía mostrar "fantasmas" de vehículos/personas presentes solo algunos de los 10 días
  mezclados, confusos para un humano aunque válidos para medir desplazamiento. `base_path()` ya
  nunca se sobrescribe con la mediana; `compare_camera_image()` mide contra la mediana si ya existe,
  si no contra la foto de un solo día (igual que antes de que existiera la mediana). Nueva
  `limpiar_base_mediana()`, llamada junto con `limpiar_historial_imagen()` al reemplazar una base a
  mano (`main.py`, `ui/ventana_bases.py`), para no seguir midiendo contra una mediana vieja.
- `scripts/separar_base_mediana.py`: migración de una sola vez para las cámaras ya promovidas antes
  de este cambio (su `IMAGE_BASE_ROOT` ya tenía la mediana, sin la foto original). Mueve lo que
  hubiera en `IMAGE_BASE_ROOT` hacia `IMAGE_BASE_MEDIANA_ROOT` tal cual (cero cambio para el
  cálculo) y elige, de las fotos del mes en curso **sin contar hoy**, la más libre de vehículos y
  personas según un detector de objetos preentrenado (YOLOv8m, vía nueva dependencia `ultralytics`)
  para dejarla en `IMAGE_BASE_ROOT`. Corrido contra producción: 212 cámaras migradas (190 con una
  foto totalmente limpia, 22 sin opción perfecta por tráfico casi constante), 5 sin fotos
  utilizables este mes.

- `scripts/revisar_bases.py`: auditoría visual rápida de bases ya existentes -- recorre cámara por
  cámara las bases de un servidor elegido (`--client`/`--plant`/`--server`) y deja marcar
  `base_desactualizada` con un clic (deja nota en la bitácora de la cámara), o seguir sin hacer
  nada. Las cámaras ya marcadas se saltan solas. Nueva `db.marcar_base_desactualizada_manual()`.

### Cambiado

- `Pipfile`: se agregó `ultralytics` (y su dependencia `torch`, CPU) -- la usa únicamente
  `scripts/separar_base_mediana.py`, no el resto del programa.

## 2026-10-26

### Agregado

- `CLAUDE.md` (convenciones del proyecto) y `CLAUDE.local.md` (notas personales, no versionado).
- `CHANGELOG.md` (este archivo).
- Carpeta `diagramas/`, con el primer diagrama de flujo (`01-flujo-main.md`) de `main.py`.
- `diagramas/02-modulo-comparacion-imagen.md`: documentación a fondo de
  `comparacion/image_compare.py` (señales de geometría, tabla de decisión, estados, constantes).
- `.markdownlint.json`.
- Historial de imágenes por cámara (`IMAGE_HISTORY_ROOT`, nueva variable de entorno): se guarda una
  copia fechada del `.jpg` de cada cámara cada día, conservando solo las 10 más recientes -- primer
  paso hacia una base de referencia por mediana en vez de la foto de un solo día.
- `construir_base_por_mediana()`: arma esa mediana por píxel a partir del historial (exige los 10
  días completos, sin mezclar resoluciones distintas).
- `scripts/bootstrap_image_history.py`: completa el historial de cada cámara desde el archivo real
  de `CHECK_PLANTS_ROOT`, sin esperar 10 días reales hacia adelante. Corrido contra producción:
  208 cámaras quedaron con historial completo, 9 todavía no tienen suficiente archivo real.
- Promoción de base provisional a mediana: al reemplazar una base en `ui/ventana_bases.py`, una vez
  que se junten 10 días frescos `main.py` la reemplaza solo por la mediana real (columna nueva
  `perfil_camara.base_reemplazada_el`, migración `0004_base_mediana.sql`).
- `scripts/promover_bases_pendientes.py`: promoción inicial de una sola vez. Corrido contra
  producción: 208 bases promovidas a mediana, 9 cámaras sin suficiente historial todavía.
- Detección de lente sucio/desenfocado: compara la nitidez de hoy contra la mediana+MAD histórica
  de cada cámara; una caída sospechosa sostenida 3 días seguidos pasa a morado y pide revisión
  humana, igual que un movimiento detectado (columnas nuevas en `historial_comparacion` y
  `perfil_camara`, migración `0005_nitidez_lente.sql`).
- Salud absoluta de imagen: detecta obstrucción total del lente (varianza/brillo extremos) de
  forma inmediata, sin esperar varios días ni necesitar historial -- funciona desde el primer día
  de una cámara nueva. Umbrales validados contra las 217 cámaras reales (migración
  `0006_salud_imagen.sql`).
- Desplazamiento de RANSAC descompuesto en traslación/rotación/escala (`orb_tx`/`orb_ty`/
  `orb_rotacion_deg`/`orb_escala`), visible en el diagnóstico de la ventana de revisión -- no
  cambia la decisión OK/REVISAR existente, solo la enriquece (migración
  `0007_orb_transformacion.sql`).
- Comparación contra el día anterior (además de la base fija): reutiliza `evaluar_par()` contra la
  foto más reciente del historial. Puramente informativa por ahora, visible en el diagnóstico
  (migración `0008_dia_anterior.sql`).
- `scripts/analizar_veredictos.py`: compara las señales guardadas contra el veredicto humano real,
  agrupado y con estadísticas básicas -- pensado para correrse periódicamente. Primer análisis
  (65 veredictos, 21-26/10) confirmó con datos reales la necesidad de calibración por cámara y
  validó el diseño de escalada de `NO CONCLUYENTE` a los 3 días con un caso real -- sin tocar
  ningún umbral todavía (muestra aún chica para eso).
- `umbral_para()` conectado por fin a `perfil_camara` (reutilizando columnas sin usar desde
  `0001_init.sql`, sin migración nueva): cada cámara con al menos 20 lecturas "normales" propias
  (días `OK` o `REVISAR` confirmados como "bien") recalibra su umbral de movimiento solo, una vez
  al final de cada corrida -- solo puede volverse menos sensible que el umbral global, nunca más.
  Corrido contra producción: 0 cámaras calificaron todavía (máximo real: 8 muestras) -- esperado
  con solo 5-6 días de historial real.
- `diagramas/03-modulo-ventana-revision.md`: documentación a fondo de `ui/ventana_revision.py` --
  los dos paneles de la ventana única, el ciclo de vida de una corrida, y los detalles de
  implementación (tema oscuro, cuadrícula de ayuda, manejo de imágenes dañadas, bloqueo de un solo
  hilo).
- Botón "Actualizar Base" en la ventana de revisión: si la foto de hoy ya sirve, la usa de
  inmediato como base nueva (igual que un reemplazo en `ui/ventana_bases.py`, sin tener que abrir
  esa ventana por separado) -- en 10 días frescos se promueve sola a mediana.
- `scripts/preview_ventana_revision.py`: ve la ventana de revisión con datos e imágenes reales sin
  tocar la base de datos ni correr `main.py` completo.
- `diagramas/04-modulo-persistencia-db.md`: documentación a fondo de `persistencia/db.py` -- los 5
  estados del semáforo, la máquina de estados completa, y cómo se arman las rachas de revisión
  forzada.
- `base_desactualizada` sin resolver 3+ días se ve en el PDF con la misma urgencia que un "Mal"
  confirmado ("Base de imágenes desactualizada (N días sin resolver)") -- sin cambiar el estado
  real de la cámara (sigue congelada, sigue en la lista de `ui/ventana_bases.py`), solo cómo se
  reporta.

### Cambiado

- `diagramas/01-flujo-main.md` actualizado con las rutas de módulo nuevas tras la
  reestructuración por paquetes.
- **Reestructuración del proyecto por paquetes**: `comparacion/`, `persistencia/`, `reporte/`,
  `integraciones/` y `ui/` agrupan los módulos por responsabilidad; `scripts/` concentra todos los
  de un solo uso (antes repartidos en la raíz). Los puntos de entrada (`main.py`,
  `generar_reporte.py`, `migrate.py`) se quedan en la raíz, sin cambios para quien los corre.

### Corregido

- Un `.jpg` dañado ya no tumba la ventana de revisión ni la generación del PDF -- se muestra un
  marcador ("Imagen no disponible") en su lugar.
- `backfill_reportes.py` quedó desactualizado tras agregar la escalada de ámbar a morado del día
  anterior; ya vuelve a reflejar la máquina de estados real.
- Avisos de `markdownlint` en este archivo (encabezados/listas sin línea en blanco); se agregó
  `.markdownlint.json` para que MD024 (encabezado duplicado) no marque las secciones repetidas
  bajo cada fecha, y para desactivar MD013 (largo de línea, no es la convención de este proyecto).
- Dos problemas de sintaxis Mermaid que impedían ver algunos diagramas: IDs de nodo con punto sin
  comillas en el mapa de módulos de `01-flujo-main.md`, y símbolos `<`/`>` sueltos en las etiquetas
  del diagrama de decisión de `02-modulo-comparacion-imagen.md`.
- IDs de nodo duplicados entre los dos diagramas Mermaid de `02-modulo-comparacion-imagen.md`
  (ambos usaban `A`, `B`, `C`...), que seguían impidiendo ver uno de los dos -- cada diagrama ahora
  tiene sus propios IDs únicos (`ep_*` / `cc_*`).
- La ventana de revisión se quedaba con los botones fuera de la vista -- el diagnóstico creció de
  2 a 6 líneas hoy y el alto de la ventana no. Ventana más alta (1280x880) y diagnóstico compactado
  (nitidez + salud en una sola línea).

### Diseño

- Plan de mejoras a `comparacion/image_compare.py` para la v2: referencia por mediana de N días,
  detección de lente sucio/desenfocado calibrada por cámara, salud absoluta de imagen, desplazamiento
  descompuesto de RANSAC, comparación contra el día anterior, y aprovechar `veredicto_humano` como
  set de validación -- ver ROADMAP.md para el detalle y el orden de prioridad acordado.

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
