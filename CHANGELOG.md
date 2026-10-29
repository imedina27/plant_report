# Changelog

Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), agrupado por
fecha en vez de versión (este proyecto no se publica como paquete). Es un registro **breve** de
qué cambió y cuándo -- el *por qué* de cada decisión está en [ROADMAP.md](ROADMAP.md), que sigue
siendo la fuente de verdad del proyecto.

## 2026-10-29

### Cambiado

- PDF del reporte, tabla "Cámaras con Falla": la columna "Motivo" ahora muestra una frase amigable
  (ej. `"No se pudo establecer conexión con la cámara"` en vez de `"Puerto 80 Timed out [111]"`) --
  pedido tras ver que un gerente de planta no entendía el detalle técnico original. El texto crudo
  completo (con código de error incluido) se sigue guardando igual en
  `historial_comparacion.log_motivo`/`imagen_motivo`, soporte lo sigue consultando ahí. La fila
  "Cambió la configuración" deja de mostrar el "Motivo" vacío -- ahora resume qué categorías
  cambiaron (Imagen/Video/Compresión/Red); el detalle campo por campo se sigue viendo igual abajo.
- PDF del reporte: la bitácora de `observacion_camara` (hasta ahora invisible en el reporte) se
  agrega debajo del "Motivo" de cada cámara con falla, como "Observaciones:" con fecha por línea, de
  la más vieja a la más nueva. Las resueltas se muestran tachadas y siguen visibles 15 días desde la
  fecha del reporte (no desde la fecha real de corrida); después de esa ventana dejan de aparecer.
  Nueva `db.observaciones_para_reporte()` (antes `observaciones_activas()`, solo traía las activas).
- `db.marcar_base_reemplazada()`: ahora deja una nota corta en la bitácora ("Base reemplazada el
  DD/MM/AAAA.") cada vez que se reemplaza una base -- antes ningún llamador (`main.py`,
  `ui/ventana_bases.py`) dejaba rastro automático. Limpieza de datos: las 26 observaciones reales de
  reemplazos ya hechos, que traían una nota larga y técnica (redactada a mano durante la recuperación
  del bug de cámaras fantasma, 28/10/2026), se reescribieron a este mismo formato corto y se
  marcaron como resueltas (`resuelta_en = base_reemplazada_el`, 27/10/2026 en las 26).

### Corregido

- `comparacion/image_compare.py`, `_orb_ransac()`: con exactamente 1 inlier sobreviviendo RANSAC,
  `cv2.estimateAffinePartial2D` (dentro de `_descomponer_transformacion`) tronaba `main.py` a medio
  reporte -- exige mínimo 2 puntos y la validación previa solo cubría 0. Pasó en producción hoy
  (`AbInBev/ZACATECAS/QLYMSPROD02/C2p`). Corregido cambiando la validación de `== 0` a `< 2`.

## 2026-10-28

### Documentado

- `diagramas/05-modulo-reporte.md`: revisión a fondo de `reporte/datos_reporte.py` y
  `reporte/reporte_ejecutivo.py`. Confirmado (no solo recordado): el PDF no muestra incidencias de
  configuración ni de salud del servicio de IA, y tampoco un cambio de resolución de imagen
  (`RESOLUCION DISTINTA`) -- ninguno de los 3 mueve ni queda reflejado en `estado_actual`.

### Corregido

- PDF del reporte: el pie de página de la simbología partía etiquetas de varias palabras a la mitad
  cuando no cabían en una línea (ej. "Base de" / "imágenes desactualizada" en líneas separadas) --
  los espacios duros/normales estaban invertidos. Ahora cada entrada completa no se parte, y el
  salto de línea solo puede caer entre entradas distintas.
- PDF del reporte: más espacio entre entradas de la simbología del pie (en las dos hojas) -- el
  cuadro de color de una entrada quedaba pegado al texto de la anterior, confuso para saber cuál
  iba con cuál.
- PDF del reporte: cuando una tabla se cortaba entre 2 hojas (ej. una lista larga de "Cámaras con
  Falla"), el borde externo grueso desaparecía justo en el corte -- el pedazo de arriba se quedaba
  sin borde inferior, y el de abajo sin borde superior. Primer intento (usar solo las palabras
  clave de ReportLab `"splitfirst"`/`"splitlast"`) causó una regresión: el borde desaparecía de
  forma inconsistente en tablas que nunca se cortan (esas palabras clave solo se resuelven cuando
  la tabla sí se corta). Arreglo final: usar los índices literales y `"splitfirst"`/`"splitlast"`
  a la vez en `_estilo_base_tabla()`.
- `scripts/revisar_bases.py`: un `--client`/`--plant`/`--server` con mayúsculas distintas a las
  reales (ej. `AbINBEV` en vez de `AbInBev`) creaba una cámara duplicada en la base de datos en vez
  de tocar la real -- Windows no distingue mayúsculas en archivos, pero Postgres sí. Ahora se
  normaliza contra la capitalización real antes de cualquier llamada a la base de datos.
- Corrección de datos de una sola vez: 26 cámaras reales de `AbInBev` (13 en `ZACATECAS/QLYMSPROD01`,
  12 en `ZACATECAS/QLYMSPROD02`, 1 en `TOCANCIPA/QLYMSPROD05`) recuperaron su `base_reemplazada_el`
  y su observación, perdidas en 146 filas "fantasma" creadas por el bug de arriba el 27/10 -- esas
  146 filas (sin historial real) se borraron después.

### Agregado

- Nuevo veredicto "Obstruida" en la ventana de revisión (`ui/ventana_revision.py`) -- para cuando
  algo temporal (camión, objeto de paso) tapó la escena: la cámara sigue bien (semáforo verde), pero
  esa foto no cuenta para la mediana. Botón nuevo en la misma fila que los otros 4, con una línea
  divisoria entre grupos: `Bien` `Obstruida` | `Mal` `Base Desactualizada` | `Actualizar Base`.
- Revisión humana de cambios de configuración, reutilizando la misma ventana
  (`pedir_revision_config()`, se muestra después de la de imagen si una cámara tiene ambas
  pendientes el mismo día): 2 paneles de texto con solo los campos que cambiaron (no el archivo
  completo), y solo `Aceptar Cambio` (reemplaza la base con la de hoy) y `Mal` (abre una incidencia
  de configuración, separada de la de imagen -- no se vuelve a preguntar hasta que se resuelva).
  Nuevas columnas `perfil_camara.config_estado_actual`/`config_incidencia_desde` y
  `historial_comparacion.config_veredicto_humano` (`migrations/0010_config_incidencia.sql`).
- PDF del reporte, cuerpo de la sección de cámaras por servidor (paso 3): nueva tabla "Sistema de
  Visión-Stream" -- muestra el o los puertos de IA de ese servidor, coloreados según su estado ese
  día (verde `ok` / rojo `caido`). Un servidor con Vision-Stream caído ahora recibe su propia hoja
  de detalle aunque todas sus cámaras estén bien.

### Cambiado

- PDF del reporte, hoja de resumen de servidores (`reporte/reporte_ejecutivo.py`, paso 1 de la
  reestructuración pedida): las columnas de conteo de cámaras ya no cambian de color -- siempre
  negro. El pie de página de esta hoja ahora tiene su propia simbología de 4 colores (OK / Cerca
  del umbral / Requiere revisión inmediata / Sin datos de monitoreo), sin mezclar los significados
  de la sección de cámaras por servidor (que se define en un paso siguiente).
- PDF del reporte, hojas de detalle por servidor (paso 2): su pie de página ahora también trae una
  línea de simbología (los 6 colores que antes solo vivían en la hoja de resumen). El alto del
  marco de estas hojas ya no es una constante fija, se mide igual que en la hoja de resumen.
- PDF del reporte, tabla "Cámaras con Falla" (paso 4): orden fijo de 11 categorías acordado con el
  usuario; "Imagen IA"/"Imagen cámara" pasan de una etiqueta roja compartida a 2 etiquetas ámbar
  separadas; se quita el código de error final de todos los motivos (`_sin_codigo_error()`); nuevas
  categorías "Cambió la configuración" (2 paneles de texto, igual que en la ventana de revisión) y
  "Cambio de resolución" (motivo con las dimensiones reales, `Base: W x H | Hoy: W x H`). Imagen y
  configuración ahora son ejes independientes -- una cámara puede aparecer con las 2 fallas el mismo
  día; el conteo de "Cámaras con falla"/"Cámaras OK" del resumen se ajustó para que los totales
  sigan cerrando en ese caso.
- PDF del reporte: los recuadros de imágenes ("Base"/"Actual") y de configuración ("Configuración
  Base"/"Configuración Hoy") ya no quedan pegados al margen de la página -- ahora tienen el mismo
  espacio a los lados que el que hay entre ellos.
- PDF del reporte: ese espacio (márgenes y centro) se redujo a la mitad (10pt → 5pt) y ahora también
  está arriba y abajo del recuadro, no solo a los lados -- simétrico en las 4 direcciones.
- PDF del reporte: las tablas "Resumen de Servidores", "Sistema de Visión-Stream" y "Cámaras con
  Falla" ahora tienen el mismo borde externo grueso que ya tenía el encabezado.
- PDF del reporte: la fila de títulos de columna de esas 3 tablas ahora se rellena de gris (igual
  que las etiquetas del encabezado) en vez de confundirse con el rayado de las filas de datos.
- `compare_camera_image()` ya no guarda la foto de hoy al historial de imágenes por su cuenta --
  ahora `main.py` lo hace explícitamente, después de conocer el veredicto humano (si lo hay), y lo
  omite para cualquier veredicto distinto de "Bien" (`Mal`, `Base Desactualizada`, `Obstruida`) --
  "Actualizar Base" sigue reiniciando su propio historial como antes. Efecto colateral bueno:
  `scripts/backfill_reportes.py` deja de modificar archivos reales de `IMAGE_HISTORY_ROOT` al
  correrlo (nunca debió hacerlo, según su propio docstring), y la detección de nitidez ya no se
  compara sin querer contra una línea base que incluía la foto del propio día.

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

- Salud del servicio de IA, Fase 1 (captura): nuevas tablas `servicio_ia` e
  `historial_servicio_ia` (`migrations/0009_servicio_ia.sql`), nueva
  `comparacion.log_parse.parsear_servicios_ia_servidor()` y `db.guardar_estado_servicio_ia()`.
  `main.py` ahora detecta y persiste, por servidor, si el servicio de IA de cada uno de sus puertos
  configurados está caído (lectura de YAML fallida) -- un mismo servidor puede tener varios puertos
  de IA a la vez. Pendiente la Fase 2 (mostrarlo en el PDF del reporte ejecutivo).

### Cambiado

- `Pipfile`: se agregó `ultralytics` (y su dependencia `torch`, CPU) -- la usa únicamente
  `scripts/separar_base_mediana.py`, no el resto del programa.
- El programa externo de revisión de cámaras ahora imprime `Puerto IA configurado <N>` antes de
  cada intento de lectura de YAML, sin importar si falla o no -- antes, una falla no dejaba
  registro del puerto, imposible de atribuir en un servidor con más de uno.

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
