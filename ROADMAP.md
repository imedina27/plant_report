# ROADMAP - Plant Report

## Objetivo general

Automatizar la revisión de plantas: tomar los logs de inspección existentes, validar que las
cámaras de cada planta no se hayan movido (comparando contra una imagen base), completar el log
con el resultado de esa validación, persistir todo en una base de datos y generar un reporte
ejecutivo con los hallazgos.

## Flujo de alto nivel

1. **Ingesta y ordenamiento de logs**
   Leer los logs existentes de revisión de plantas y ordenarlos (criterio por definir: fecha,
   planta, cámara, etc.).
   - Decidido: los logs son archivos de texto plano con extensión `.log`.
   - Decidido: ubicación y estructura real de carpetas (confirmada explorando el disco):

     ```text
     D:\Imágenes\Quantum Labs\Check Plants\
       [Cliente]\                     (ej. AbInBev, Others)
         [NN- Mes]\                   (ej. "09- Septiembre")
           [ddmmyy]\                  (ej. "180926" = 18/09/26, una carpeta por día de corrida)
             [PLANTA]\                (ej. APAN, ATLANTICO, MEDELLIN... una planta puede tener
                                        más de un servidor, ej. MEXICO -> QBYMSPROD07 y QBYMSPROD08)
               [SERVIDOR]\            (ej. QLYMSPROD03)
                 [SERVIDOR].log       (log de la corrida completa de ese servidor/planta)
                 [CAMARA].jpg         (imagen cruda tomada de la cámara)
                 [CAMARA].json        (dump completo de configuración VAPIX de la cámara, Axis)
                 [CAMARA]_ai.jpg      (imagen procesada/anotada, probablemente salida de IA)
     ```

     Con datos de ejemplo (18/09/2026): 2 clientes, 10 plantas, 11 servidores, 399 imágenes .jpg,
     14 archivos .log. Solo existe la carpeta del día actual (no hay histórico de días previos en
     este disco todavía).
   - Decidido: el `.log` NO es un log tabular simple, es un log de proceso con timestamp y nivel
     (INFO/ERROR), que registra, por servidor: apertura de túneles SSH, ping, y por cada cámara:
     IP, verificación de puerto 80, obtención de "Imagen IA", "Imagen cámara", "Configuración" y
     tiempo de proceso. Incluye errores (ej. `Timed out [111]`) cuando una cámara no responde.
     Ejemplo real visto en `QLYMSPROD03.log`:

     ```text
     APAN - 18/09/2026 - 19:06
     [19:06:49] INFO    Ping to Server QLYMSPROD03 on Plant APAN
     [19:06:56] INFO    Total de camaras 12, Camaras Activas 11 en el puerto: 8045
     [19:06:56] INFO    ENE IP: 192.168.20.31
     [19:06:56] INFO    ENE: Puerto 80       OK                  [200]
     [19:06:58] INFO    ENE: Imagen IA       OK                  [200]
     [19:06:59] INFO    ENE: Imagen cámara   OK                  [200]
     [19:07:00] INFO    ENE: Configuración   OK                  [200]
     [19:07:00] INFO    ENE: Tiempo de proceso 4.37s
     [19:07:08] ERROR   AD1l1: Puerto 80       Timed out           [111]
     ```

   - **Implementado** (`log_sorter.py` + `main.py`): agrupa y ordena las líneas por cámara dentro
     de cada `.log` (IP, Puerto, Imagen IA, Imagen cámara, Configuración, Tiempo de proceso, en
     ese orden fijo), cámaras en orden alfabético, dejando intacto el encabezado/YAML/cierre.
     `main.py` pide la fecha (`ddmmyy`) por consola y procesa todos los `.log` de ese día bajo
     `Check Plants`. Hace un `.bak` antes de sobrescribir cada archivo. Validado contra los 14
     `.log` reales del 18/09/2026 y corrido ya una vez sobre el disco real.
   - Hallazgos al implementar:
     - Algunos `.log` (ej. `APIMAN-FASE1` del cliente "Others") contienen **varias rondas** en un
       solo archivo (una por puerto/zona escaneado: 12046, 12047, 13045, 13048), cada una con su
       propio `YAML Read successful` / `Total de camaras` / cierre `====`. El sorter ya detecta y
       ordena cada ronda por separado sin mezclarlas.
     - El fin de línea varía entre archivos: los de AbInBev usan `LF`, el de `API-MANZANILLO` usa
       `CRLF`. El sorter preserva el estilo original de cada archivo.
     - Sí existe un log "por cliente" a nivel superior: `[Cliente]\[Mes]\[ddmmyy]\resumen_[fecha].log`
       (ej. `AbInBev\09- Septiembre\180926\resumen_18-09-2026.log`), con un resumen agregado
       (servidores revisados, cámaras con fallas por planta). Formato totalmente distinto (sin
       timestamps por línea) — el sorter lo detecta automáticamente y lo deja intacto.
     - Hay líneas `[ERROR] <ip>: ...` que no mencionan la cámara por nombre; se resuelven contra
       la IP vista en esa misma ronda y ocupan el lugar de "Configuración". Cuando además existe
       una línea posterior con nombre de cámara para el mismo campo (ej. reintento exitoso), esa
       línea posterior es la que queda (se respeta el orden cronológico de resolución).
   - Preguntas abiertas:
     - Cuando ya haya varios días acumulados, ¿el programa debe procesar solo el día más reciente,
       un rango de fechas, o todos los pendientes de procesar?
     - ¿El `resumen_[fecha].log` por cliente debe incorporarse al flujo (fases 3-5) o es solo
       para referencia humana?

2. **Comparación de imágenes de cámara**
   Para cada cámara, obtener la imagen actual y compararla contra una imagen base de referencia
   para detectar si la cámara se movió.
   - Decidido: las imágenes se obtienen de la misma carpeta local/red descrita en la Fase 1
     (`[CAMARA].jpg` por servidor/planta/día).
   - Decidido: ya existe un sistema Python que hace esta comparación. Pendiente que el usuario
     comparta el código para revisarlo, mejorarlo e integrarlo a este proyecto (en vez de
     construir la lógica de comparación desde cero).
   - Preguntas abiertas:
     - ¿Dónde está el script/proyecto existente? (ruta local, repo, etc.) — el usuario lo
       compartirá cuando lleguemos a esta fase.
     - No se encontró ninguna carpeta de "imagen base"/referencia en el disco explorado — ¿dónde
       vive o cómo se define? (¿la maneja el script existente, es la primera imagen capturada de
       cada cámara, o se cura manualmente?)
     - Decidido: `[CAMARA]_ai.jpg` es la salida de un sistema de IA ya existente (a reutilizar,
       no a reconstruir). Falta confirmar con el script existente qué hace exactamente y si se
       relaciona con la comparación contra la imagen base.
     - ¿Cuántas cámaras totales se manejan? (ejemplo visto: ~11-12 cámaras por servidor, 11
       servidores activos ese día)
     - ¿El sistema existente ya define un umbral/método de sensibilidad, o también está pendiente
       de ajustar?

3. **Actualización del log**
   Completar el log original con los resultados de la comparación (por cámara).
   - Decidido: se sobrescribe el `.log` original agregándole las líneas con el resultado de la
     comparación (no se genera un archivo aparte).
   - Preguntas abiertas:
     - ¿Qué campos/formato exacto se deben agregar (ej. `[HH:MM:SS] INFO <CAMARA>: Comparación
       con base OK/MOVIDA [score]`, siguiendo el mismo estilo del log actual)?
     - ¿Qué pasa si el programa se corre más de una vez sobre el mismo log (evitar duplicar
       líneas de resultado)?

4. **Persistencia en base de datos**
   Guardar los resultados (logs + comparaciones) en una base de datos.
   - Decidido: PostgreSQL, ya hay un servidor disponible.
   - Preguntas abiertas:
     - ¿Datos de conexión al servidor (host, puerto, nombre de BD)? ¿Cómo se van a manejar las
       credenciales (variables de entorno, archivo `.env`, etc.)?
     - ¿Ya existe un esquema o hay que diseñarlo desde cero?
     - ¿Se necesita conservar histórico de todas las corridas o solo el estado más reciente?

5. **Reporte ejecutivo**
   Generar un reporte ejecutivo con los resultados.
   - Decidido: formato PDF, generación diaria (automática).
   - Decidido: reporte detallado por planta, dirigido a Gerencia de Operaciones.
   - Pendiente: el contenido específico del reporte (secciones, tablas, gráficos) se definirá
     más adelante.
   - Preguntas abiertas:
     - ¿Qué debe contener exactamente (resumen de cámaras movidas, tablas, gráficos,
       comparativas históricas)?
     - ¿Cómo se dispara la generación diaria (tarea programada/cron, servicio corriendo en
       segundo plano)?
     - ¿El reporte se envía a alguien (correo) o solo se guarda en una ubicación?
     - ¿Existe una plantilla o identidad visual corporativa a seguir?

## Preguntas generales de ejecución

- Decidido: por ahora la ejecución es manual (vía CLI). La automatización (tarea programada de
  Windows, servicio, etc.) para que el reporte diario salga solo se define más adelante.
- ¿Dónde corre (equipo local, servidor)?
- ¿Necesita interfaz gráfica o es suficiente con línea de comandos?

## Estado

- [ ] Fase 1 definida
- [ ] Fase 2 definida
- [ ] Fase 3 definida
- [ ] Fase 4 definida
- [ ] Fase 5 definida
