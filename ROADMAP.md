# ROADMAP - Plant Report

## Objetivo general

Automatizar la revisión de plantas: validar que la configuración de cada cámara no haya cambiado
y que no se haya movido (comparando su `.json` y su imagen contra una referencia base), completar
el log con el resultado de esas validaciones, persistir todo en una base de datos, generar un
reporte ejecutivo con los hallazgos y enviarlo por correo a los destinatarios designados.

> El ordenamiento de los `.log` de revisión **no** es parte de este proyecto: lo hace el programa
> de revisión de cámaras (externo a este repo) antes de que los archivos lleguen aquí. Este
> proyecto asume que recibe los `.log` ya ordenados y arranca desde la comparación de cámaras.

## Estructura de datos (contexto)

Ubicación y estructura real de carpetas (confirmada explorando el disco):

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
            [CAMARA].json        (dump completo de configuración de la cámara; el esquema
                                   depende del fabricante — ver nota de marcas más abajo)
            [CAMARA]_ai.jpg      (imagen procesada/anotada, probablemente salida de IA)
```

Con datos de ejemplo (18/09/2026): 2 clientes, 10 plantas, 11 servidores, 399 imágenes .jpg,
14 archivos .log.

> Corrección (02/10/2026): sí existe histórico — ver más abajo. Además, al 01/10/2026 el nivel de
> cliente creció a 4: `AbInBev`, `Api_Manzanillo`, `C5i_Colima`, `Pemex` (antes solo se habían visto
> `AbInBev`/`Others`).
>
> Aclarado (21/10/2026), al correr `backfill_reportes.py` contra octubre real y no encontrar datos
> de `Pemex`/`C5i_Colima` en la mayoría de los días: **`Pemex` era una prueba de concepto que ya
> terminó** -- no va a haber más imágenes de ese cliente. **`C5i_Colima` tiene más de 1000 cámaras**
> y se decidió, por ahora, no correr el programa contra ese cliente (sin fecha definida para
> empezar). Ningún código asume que ambos clientes estén activos; que no aparezcan en una corrida es
> esperado, no una falla.

Para desarrollo/pruebas hay un mirror local de esta misma estructura en `Test/Check Plants/`
dentro del repo (con datos reales pero desconectado de producción), que el usuario va subiendo
manualmente con logs de días nuevos. Esa carpeta está en `.gitignore` (es desechable, no se
versiona) — cualquier código que lea `CHECK_PLANTS_ROOT` debe poder apuntar tanto a la ruta real
(`D:\Imágenes\Quantum Labs\Check Plants`) como a esta carpeta de prueba vía `.env`.

**Histórico real, descubierto 02/10/2026**: `D:\Imágenes\Quantum Labs\Check Plants\1- OLD\` tiene
**124 días en 2025** (mayo a diciembre) y **18 en 2026** — casi dos años de capturas diarias reales
por cámara. Es la fuente usada para los Experimentos 1, 3, 4, 5 y 6 de la Fase 2 (ver esa sección),
y la alternativa elegida en vez de dar acceso directo a cámaras de producción para ampliar el piso
de ruido (02/10/2026): minar más días de este histórico es casi gratis y no toca infraestructura
viva, a diferencia de conectarse en vivo a cámaras remotas (que además viven detrás de túneles que
administra el programa externo de revisión — ver `proxy_ip`/`proxy_port` en `Test/cameras/*.py`).

- **2026** sigue la estructura de arriba: `2026\[Cliente]\[NN- Mes]\[ddmmyy]\[PLANTA]\[SERVIDOR]\`.
- **2025 usa un formato distinto y más viejo**: `2025\[NN-Mes]\[ddmmyy]\[planta+servidor en
  minúsculas]\`, sin carpeta de cliente y con planta y servidor fundidos en un solo nombre (ej.
  `zacatecas01`, `mexico07`). Cualquier código que recorra el histórico completo tiene que tolerar
  ambos formatos, no solo el de 2026.

El `.log` es un log de proceso con timestamp y nivel (INFO/ERROR), que registra, por servidor:
apertura de túneles SSH, ping, y por cada cámara: IP, verificación de puerto 80, obtención de
"Imagen IA", "Imagen cámara", "Configuración" y tiempo de proceso. Incluye errores (ej.
`Timed out [111]`) cuando una cámara no responde. Ejemplo real visto en `QLYMSPROD03.log`:

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

Notas a tener en cuenta en cualquier código que lea o escriba estos `.log`:

- Algunos `.log` (ej. `APIMAN-FASE1` del cliente "Others") pueden contener **varias rondas** en un
  solo archivo (una por puerto/zona escaneado), cada una con su propio `YAML Read successful` /
  `Total de camaras` / cierre `====`.
- El fin de línea varía entre archivos: los de AbInBev usan `LF`, el de `API-MANZANILLO` usa
  `CRLF`. Hay que tolerar ambos.
- Existe un log "por cliente" a nivel superior: `[Cliente]\[Mes]\[ddmmyy]\resumen_[fecha].log`
  (ej. `AbInBev\09- Septiembre\180926\resumen_18-09-2026.log`), con un resumen agregado
  (servidores revisados, cámaras con fallas por planta). Formato totalmente distinto al de los
  `.log` por servidor (sin timestamps por línea).
  - Actualización (22/09/2026): el formato de este `resumen_[fecha].log` cambió — ahora agrega,
    antes de la sección `DETALLE POR PLANTA - CÁMARAS CON FALLAS` de siempre, una sección nueva
    **`DETALLE POR SERVIDOR`**: una tabla con un estado por servidor (`[OK]`, `[CON FALLAS]`,
    `[SIN YAML]`), la planta, el nombre del servidor, y "X/Y cámaras completas".
  - El estado `[SIN YAML]` es nuevo: significa que ese servidor no pudo ni siquiera leer su lista
    de cámaras ese día (ej. `ERROR YAML Connection error [410]` en su `.log`), así que no tiene
    ninguna cámara (ni `.jpg` ni `.json`) esa corrida. Cualquier código que recorra cámaras por
    servidor debe tolerar servidores sin ninguna cámara.
  - El `.log` por servidor/cámara también llega pre-ordenado por cámara desde el programa de
    revisión (ya no es responsabilidad de este proyecto, ver nota al inicio del documento).

## Diagrama de flujo

```mermaid
flowchart TD
    A["Programa de revision de camaras -externo-<br/>ordena los .log y genera .jpg, .json y resumen_fecha.log"]
    A --> B["Por cada cliente, planta, servidor y camara"]

    B --> C["Fase 1: Comparar el .json de la camara<br/>contra su configuracion base<br/>-segun marca: AXIS, HIKVISION, DAHUA, VIVOTEK, etc-"]
    B --> D["Fase 2: Comparar la imagen de la camara<br/>contra su imagen base"]

    C --> E["Fase 3: Persistir resultado de ambas<br/>comparaciones en PostgreSQL<br/>-camara por camara, incluyendo veredicto humano-"]
    D --> E

    E --> F{"Se procesaron todas<br/>las camaras del dia?"}
    F -->|No| B
    F -->|Si| H["Fase 4: Generar reporte ejecutivo<br/>PDF diario, por planta"]

    H --> I["Fase 5: Enviar por correo el PDF<br/>a los destinatarios designados"]
```

## Flujo de alto nivel

1. **Comparación de archivos JSON de configuración de las cámaras**
   Para cada cámara, comparar su `[CAMARA].json` (dump de configuración) actual contra una
   referencia base, para detectar cambios de configuración no autorizados/inesperados.
   - **Implementado (23/09/2026)** para AXIS, HIKVISION y VIVOTEK, en `config_compare.py` +
     `main.py`: detección de marca por contenido, extracción de campos curados por marca/categoría,
     creación automática de la base si falta, y comparación exacta contra la base. Probado end to
     end contra los 144 `.json` de `Test/Check Plants` (144 detectados correctamente, 0 sin
     soportar), con `BASE CREADA` en la primera corrida y `OK` en la segunda (idempotente), y con
     un cambio simulado (IP de una cámara) correctamente detectado como `CAMBIO` con el campo,
     valor base y valor actual exactos.
   - **DAHUA agregado (03/10/2026), provisional** — `_dahua_fields()` + huella de detección
     (`deviceType` empieza con `"DH"`) en `config_compare.py`, curados contra el dump real obtenido
     de la cámara ITC de prueba (ver sección 2.8). Probado contra el fixture real
     (`Test/DAHUA-ITC413-PW4D-Z3.json`): detección correcta, 0 diferencias comparado contra sí mismo,
     y un cambio de IP simulado detectado con campo/valor base/valor actual exactos — mismo
     comportamiento que las otras 3 marcas. Corrida de regresión completa contra las 210 cámaras del
     sandbox: **0 "MARCA NO SOPORTADA"** (antes había 3 cámaras DAHUA reales en
     `Pemex/TAD18DEMARZO/DEMOQUA` marcadas así), sin romper AXIS/HIKVISION. **Provisional** porque el
     dump base es de una cámara ITC de tráfico, no una domo/bullet genérica — falta contrastar los
     campos contra la cámara "normal" del parque cuando el usuario la tenga a la mano (posiblemente
     martes 06/10/2026) antes de darlo por definitivo.
   - Decidido: los archivos se obtienen de la carpeta descrita arriba (`[CAMARA].json` por
     servidor/planta/día).
   - Decidido: la base de referencia **no existe todavía, hay que crearla** (ej. tomar el primer
     `.json` capturado de cada cámara como su base la primera vez que se procese). Una vez creada,
     **queda fija hasta una actualización manual deliberada** — no se refresca sola cada día,
     porque si lo hiciera nunca detectaríamos una desviación real. Falta diseñar el mecanismo para
     "aceptar" un cambio legítimo como la nueva base cuando corresponda.
   - Decidido: es lógica **nueva**, construida desde cero en este proyecto — no reutiliza el
     sistema existente de comparación de imágenes (ese es solo para imagen).
   - Decidido: no se compara el archivo completo. Se compara un **subconjunto curado de campos**,
     agrupados en 4 categorías (Imagen, Video, Compresión, Network), definido **por marca** ya que
     los nombres de campo no coinciden entre fabricantes.
   - Decidido: el resultado se registra como un **campo nuevo** en el `.log` (ej.
     `Config Comparacion: OK/CAMBIO`), sin tocar la línea `Configuración: OK/Timed out` que ya
     existe (esa solo indica si se pudo *descargar* el JSON, no si coincide con la base).
   - Decidido (23/09/2026): la base de referencia vive en una carpeta nueva, propia de este
     proyecto, apuntada por una variable de entorno nueva (ej. `CONFIG_BASE_ROOT` en `.env`), con
     la misma estructura que `Check Plants` pero **sin la carpeta de fecha** (es una referencia
     viva, no un histórico diario): `[Cliente]\[Planta]\[Servidor]\[CAMARA].json`. La primera vez
     que se procesa una cámara sin base, se copia su `.json` de ese día como base y el log registra
     `Config Comparacion: BASE CREADA` (no "OK" ni "CAMBIO", porque no hubo comparación real).
   - Decidido: si un campo de la lista curada no existe en el `.json` de una cámara puntual (puede
     pasar según modelo/configuración), se ignora ese campo para esa cámara en vez de marcar error.
   - Decidido: formato de la línea nueva en el log, siguiendo el estilo visual de las líneas ya
     existentes: `[HH:MM:SS] INFO    <CAMARA>: Config Comparacion   OK/CAMBIO/BASE CREADA`.
   - Decidido: la marca de cada cámara se detecta **leyendo el contenido de su `.json`** (huellas
     de marca, ver más abajo), no desde un inventario externo — no existe uno reutilizable.
   - Decidido: en AXIS, solo se comparan las vistas con `Enabled: "yes"` dentro de `Image.I0`-`I7` /
     `ImageSource.I0`-`I7` (normalmente solo `I0`); las deshabilitadas se ignoran por ser puro
     ruido (siempre en su valor de fábrica).
   - Decidido: el criterio de "cambió" es **coincidencia exacta** de texto por campo (sin
     tolerancias numéricas) — se ajustará después si genera demasiado ruido en la práctica.
   - **Importante — múltiples fabricantes, con crecimiento esperado**: el `.json` no tiene un
     esquema único, depende de la marca. La lógica de comparación debe diseñarse para que agregar
     una marca nueva sea configuración/extensión, no reescribir el core (mismo principio que se
     usó antes para las reglas de ordenamiento por cliente, aunque ese código ya no exista en este
     repo).
   - **Ya existe código de descarga de configuración por marca** (compartido 22/09/2026 en
     `Test/cameras/{axis,hikvision,dahua,vivotek}.py`, funciones `[Marca]CamConf()`), que confirma
     cómo llega el dump crudo de cada una antes de convertirlo a `.json`:

     | Marca | Endpoint | Formato crudo | Separador de niveles |
     | --- | --- | --- | --- |
     | AXIS | `axis-cgi/param.cgi?action=list&group=root` | texto `root.Nivel1.Nivel2=valor` | `.` |
     | HIKVISION | 7 llamadas ISAPI (`deviceInfo`, `Network/interfaces/1`, `Image/channels/1`, `Streaming/channels/101/`, `time`, `Security/users`, `capabilities`) | XML → dict | jerarquía XML |
     | DAHUA | `configManager.cgi?action=getConfig&name=All` (+2 llamadas `getSystemInfo`) | texto `table.All.Nivel1.Nivel2=valor` | `.` |
     | VIVOTEK | `getparam.cgi` (una sola llamada) | texto `nivel1_nivel2=valor` | `_` |

     Nota menor: HIKVISION también descarga `Security/users` (aparece como `UserList` en el
     `.json`), pero solo expone `userName`/`userLevel` (ej. `admin`/`Administrator`), sin
     contraseñas — no forma parte de las 4 categorías a comparar de todos modos.
   - **Lista de campos a comparar, verificada contra archivos reales de `Test/Check Plants`**
     (AXIS: `CA.json`; HIKVISION: `A1p.json`) — rutas con notación de punto:

     **AXIS**
     - Imagen: `Image.I0.Appearance.{ColorEnabled,MirrorEnabled,Resolution,Rotation}`,
       `ImageSource.I0.DayNight.*`, `ImageSource.I0.DCIris.*`, `ImageSource.I0.Focus.*`,
       `ImageSource.I0.Sensor.*` (Brightness, Contrast, ColorLevel, Sharpness, WhiteBalance*,
       Exposure*, WDR, Gain*, Shutter*, CustomExposureWindow*, etc.)
     - Video: `Image.I0.Stream.{Duration,FPS,NbrOfFrames}`, `Image.I0.MPEG.*` (Complexity,
       ConfigHeaderInterval, FrameSkipMode, ICount, PCount, UserData*, Z*),
       `Image.I0.RateControl.{Mode,Priority}`
     - Compresión: `Image.I0.Appearance.Compression`, `Image.I0.MPEG.H264.{Profile,PSEnabled}`,
       `Image.I0.RateControl.{MaxBitrate,TargetBitrate}`, `Image.I0.SizeControl.MaxFrameSize`
     - Network: `Network.{IPAddress,SubnetMask,DefaultRouter,Broadcast,BootProto,HostName,
       DomainName,Media,DNSServer1,DNSServer2}`, `Network.eth0.{IPAddress,SubnetMask,MACAddress,
       Broadcast}`, `Network.RTSP.{Port,Enabled}`, `Network.HTTP.AuthenticationPolicy`,
       `Network.SSH.Enabled`, `Network.UPnP.Enabled` (a propósito, fuera de alcance por ahora:
       `RTP.R0`-`R7` multicast, `QoS.*`, `IPv6.*`, `dot1x.*` — protocolo avanzado, poco propenso a
       cambiar manualmente y genera mucho ruido)
     - **Zoom — pendiente, sin verificar en vivo (03/10/2026, corregido el mismo día tras una
       observación del usuario).** Se buscó en un `.json` real (`Api_Manzanillo/.../SP-OMS01.json`)
       y lo único relacionado a zoom que aparece son **capacidades del "driver" PTZ, no del lente
       físico instalado**: `PTZ.Limit.L{n}.MaxZoom`, `PTZ.Support.S{n}.AbsoluteZoom`, `PTZ.
       Various.V{n}.ZoomEnabled` — "¿qué sabe hacer el subsistema PTZ en general?", no "¿qué lente
       tiene montada esta cámara ahora?".
       - Primer intento de explicación (**incorrecto, corregido**): se asumió que esta cámara
         (`Brand.ProdShortName = AXIS M1135`) era de lente fijo sin zoom óptico. Falso — AXIS vende
         una variante `M1135 Mk II i-CS` que **sí** trae un lente varifocal 3.5-10mm con zoom y
         enfoque remotos motorizados de fábrica (confirmado contra la página de producto de AXIS).
         El `.json` no tiene un campo que distinga qué variante/generación es esta unidad en
         particular, así que no se puede descartar que sí tenga el lente motorizado.
       - **Campo mejor encontrado al revisar con más cuidado**: `PTZ.ImageSource.I0.PTZEnabled =
         false`. A diferencia de los campos anteriores (genéricos del driver), este sí es específico
         de *esta instalación* — dice que el PTZ/zoom no está activo en el canal de video de esta
         cámara en particular, sea cual sea el lente físico montado. Es el campo correcto para decidir
         cámara por cámara si vale la pena consultar el zoom en vivo, sin tener que adivinar por el
         modelo.
       El valor **en vivo** (cuando `PTZEnabled=true`) no está en `param.cgi?action=list&group=root`
       en absoluto. Se confirmó (vía documentación oficial de AXIS,
       `developer.axis.com/vapix/network-video/pantiltzoom-api/`, no solo por memoria) que vendría de
       `GET /axis-cgi/com/ptz.cgi?query=position`, que responde texto plano `pan=X tilt=Y zoom=Z
       iris=... focus=... autofocus=on/off` (formato distinto al dotted `root.X.Y=Z` que
       `dic_to_json()` ya procesa, necesitaría su propio parser). Esto confirma que el endpoint
       existe y el formato esperado, pero **sigue sin probarse contra una cámara real con
       `PTZEnabled=true`** — a diferencia del campo de HIKVISION, que sí se validó en vivo con la
       cámara física. No inventar el nombre final del campo en `config_compare.py` hasta tener esa
       prueba.

     **HIKVISION**
     - Imagen: `ImageChannel.{ImageFlip.enabled, IrcutFilter.*, Exposure.*, powerLineFrequency.*,
       Scene.mode, WDR.*, BLC.enabled, NoiseReduce.*, WhiteBalance.*, Sharpness.SharpnessLevel,
       Gain.GainLevel, Shutter.ShutterLevel, Color.*, Dehaze.DehazeMode}`,
       `PTZStatus.AbsoluteHigh.absoluteZoom` — agregado 03/10/2026 (ver Fase 2, Experimento 8,
       Hallazgo 4: el zoom no lo detecta la comparación de imagen, decidido que se vigile aquí).
       **Implementado en `config_compare.py` pero incompleto**: solo presente en cámaras con lente
       motorizado (sufijo `IZS`/`IZHS` o similar — el parque es variable, mezcla de marcas y modelos,
       algunos motorizados y otros no, confirmado por el usuario 03/10/2026); en lente fijo el campo
       no existe y se ignora igual que cualquier campo ausente. **Depende de un cambio fuera de este
       repo**: la descarga (`HikvCamConf()` en el programa externo de revisión, no en este proyecto)
       no llama hoy a `PTZCtrl/channels/1/status` — hay que agregar esa llamada ahí para que el campo
       llegue a existir en el `.json` que este proyecto lee. Sin ese cambio externo, el campo queda
       siempre ausente y nunca se compara (no falla, pero tampoco vigila nada).
     - Video: `StreamingChannel.Video.{videoCodecType,videoScanType,videoResolutionWidth,
       videoResolutionHeight,maxFrameRate,GovLength,H264Profile,H265Profile,SVC.enabled,
       SmartCodec.enabled,snapShotImageType}`
     - Compresión: `StreamingChannel.Video.{videoQualityControlType,constantBitRate,fixedQuality,
       vbrUpperCap,vbrLowerCap,keyFrameInterval,smoothing}`
     - Network: `NetworkInterface.IPAddress.{ipAddress,subnetMask,addressingType,
       DefaultGateway.ipAddress,PrimaryDNS.ipAddress,SecondaryDNS.ipAddress}`,
       `NetworkInterface.Link.{MACAddress,speed,duplex,MTU}` (fuera de alcance por ahora:
       `@version`/`@xmlns` de cada bloque — son metadatos de esquema, no configuración real; y
       `Discovery.UPnP/Zeroconf` por ser protocolo secundario)

     **VIVOTEK** (verificado 22/09/2026 contra `Test/VIVOTEK-IP9181-192.168.81.80.json`, cámara
     real `IP9181-LPC-v2`; dump plano `nivel1_nivel2=valor` reconstruido a dict anidado por
     `txt_to_json`, un solo canal de video `c0`, hasta 3 streams `s0/s1/s2`):
     - Imagen: `image.c0.{brightness,brightnesspercent,saturation,saturationpercent,contrast,
       contrastpercent,sharpness,sharpnesspercent,gammacurve,hlm}`, `image.c0.defog.{mode,
       strength}`, `image.c0.eis.{mode,strength}`, `image.c0.dnr.{mode,strength}`,
       `image.c0.scene.mode`, `videoin.c0.{whitebalance,exposurelevel,irismode,maxgain,mingain,
       color,flip,mirror,rotate,cmosfreq}`, `videoin.c0.wdrc.{mode,strength}`,
       `videoin.c0.wdrpro.mode`, `videoin.c0.piris.{mode,position}`,
       `videoin.c0.aespeed.{mode,speedlevel,sensitivity}`, `videoin.c0.zoomratiodisplay` — agregado
       03/10/2026. Visto en el dump real, pero esa cámara de muestra no tiene módulo de zoom
       motorizado (`capability.camctrl.c0.zoommodule=0`), así que **no se pudo confirmar que el
       valor cambie con un zoom real** (a diferencia de HIKVISION, verificado en vivo con la cámara
       física). Riesgo bajo de agregarlo igual — el campo sí existe en datos reales, lo peor que
       puede pasar es que nunca capture nada útil, no que falle en silencio.
     - Video: `videoin.c0.sN.codectype`, `videoin.c0.sN.resolution`,
       `videoin.c0.sN.{h264,h265}.{profile,maxframe,prioritypolicy}`,
       `videoin.c0.sN.mjpeg.maxframe` (N = 0, 1, 2 — un stream por cada perfil de calidad)
     - Compresión: `videoin.c0.sN.{h264,h265}.{ratecontrolmode,bitrate,quant,qvalue,qpercent,
       intraperiod,maxvbrbitrate}`, `videoin.c0.sN.mjpeg.{ratecontrolmode,bitrate,quant,qvalue,
       qpercent}`
     - Network: `network.{ipaddress,subnet,router,dns1,dns2}`, `network.http.{port,alternateport,
       authmode}`, `network.https.port`, `network.rtsp.{port,authmode}`, `network.pppoe.user`,
       `network.ieee8021x.enable`, `network.qos.{cos.enable,dscp.enable}`
     - Identificación (para detectar marca/modelo, no es una de las 4 categorías):
       `system.info.{modelname,serialnumber,firmwareversion}`
     - **Sin MAC disponible en este endpoint** — a diferencia de AXIS/HIKVISION, no encontré
       ningún campo de dirección MAC en todo el dump (`getparam.cgi` no lo expone aquí).

     **DAHUA — primer dump real obtenido (03/10/2026), con una salvedad importante.** El usuario dio
     acceso por túnel a una cámara DAHUA real (`DHI-ITC413-PW4D-Z3`, lente varifocal motorizada, POC)
     y se corrió `getConfig&name=All` completo (310 secciones, guardado en
     `Test/DAHUA-ITC413-PW4D-Z3.json`). Confirma que `Network`, `VideoColor[0][N]` y `Encode[0]`
     existen tal como se especulaba, con nombres de campo reales — pero **es una cámara ITC de
     tráfico/placas (ANPR), no una domo/bullet genérica** como las que monitorea el parque real (su
     overlay dice literalmente "Sin licencia" y el dump trae cientos de secciones específicas de
     tráfico — `TrafficGlobal`, `ParkingSpace*`, etc. — que no deberían copiarse a la lista curada).
     Antes de fijar la lista final de campos, conviene contrastar contra el dump de una cámara DAHUA
     "normal" del parque (ej. la prometida para el martes 06/10/2026) para confirmar que las secciones
     genéricas (`Network`/`VideoColor`/`Encode`) se ven igual ahí. Sin cuentas de usuario/contraseñas
     en el dump (todas enmascaradas `******`), igual que documentaba el código original.

     **Zoom DAHUA — confirmado en vivo (03/10/2026), con evidencia real igual de sólida que
     HIKVISION.** No está en `getConfig&name=All` (mismo punto ciego que AXIS), pero sí en un
     endpoint separado y genérico (no específico de tráfico):
     `GET /cgi-bin/devVideoInput.cgi?action=getFocusStatus&channel=0` → `status.Zoom` (0.0-1.0
     normalizado). Verificado con un cambio de zoom real hecho a mano por el usuario desde la interfaz
     web de la cámara: `Zoom` pasó de `0.000000` a `0.144090` al mover el zoom, y volvió exacto a
     `0.000000` al regresarlo — confirmado también que `status.Focus` se mueve junto con el zoom
     (0.1545→0.2909→0.1576, el mismo tipo de residuo pequeño ya visto en los reacomodos manuales de
     la HIKVISION física) porque cambiar el zoom de un lente varifocal desenfoca y hay que reajustar,
     igual que el Hallazgo 6 del Experimento 8. **Hallazgo aparte**: `status.ZoomMotorSteps` y
     `status.FocusMotorSteps` NO cambiaron con el movimiento real (se quedaron fijos en 1159 y 330) —
     parecen ser otra cosa (quizás un total de calibración), no la posición actual. El campo correcto
     para vigilar es `status.Zoom`, no `status.ZoomMotorSteps`. No se encontró el endpoint para mover
     el zoom por API (se probaron `devVideoInput.cgi?action=adjustZoomAndFocus/adjustZoomFocus` y
     `ptz.cgi?action=start` con códigos `ZoomTele`/`Zoom1` — todos "Not Implemented"/"Bad Request" en
     este modelo), pero no hace falta: para Fase 1 solo hace falta *leer* el campo, no escribirlo.
   - Preguntas abiertas:
     - ~~Pendiente de entrega — acceso a una cámara Dahua real para correr `DahuaCamConf()` y su
       huella de detección~~ — **resuelto (03/10/2026)**: el usuario dio acceso por túnel a una
       cámara DAHUA real (POC, modelo ITC413 de tráfico) antes de la fecha prevista. Huella de
       detección implementada: `deviceType` empieza con `"DH"` (AXIS: `Brand.Brand == "AXIS"`;
       HIKVISION: `DeviceInfo["@xmlns"]` conteniendo `hikvision.com`; VIVOTEK:
       `system.info.firmwareversion` conteniendo `VVTK`). **Sigue pendiente, posiblemente martes
       (06/10/2026)**: contrastar los campos curados contra una cámara DAHUA "normal" del parque (no
       ITC de tráfico), para confirmar que generalizan antes de darlos por definitivos.
     - **Zoom — decidido (03/10/2026): sí debe vigilarse en Fase 1.** Campo `PTZStatus.
       AbsoluteHigh.absoluteZoom` agregado a la categoría Imagen de HIKVISION en `config_compare.py`,
       probado contra los 144 `.json` reales del sandbox sin romper nada (el campo está ausente en
       todos hoy, se ignora limpio). **Queda bloqueado en la mitad**: falta que el programa externo
       de revisión agregue la llamada a `PTZCtrl/channels/1/status` en su descarga — sin eso el
       campo nunca va a existir en el `.json` que este proyecto lee, y nunca se comparará nada aunque
       el código ya esté listo. El parque de cámaras es variable (mezcla de marcas/modelos, algunos
       motorizados y otros no, confirmado por el usuario) — no hace falta tratarlo como caso especial,
       la regla de "campo ausente se ignora" ya lo cubre tal cual.
     - ~~Falta diseñar el mecanismo para "aceptar" un cambio legítimo como nueva base~~ —
       **resuelto (30/09/2026)**: se hace con la ventana de revisión descrita en la sección 2.3, que
       aplica igual a Fase 1 (mostrando una tabla de campo / valor base / valor actual en vez de dos
       imágenes) y a Fase 2.

2. **Comparación de imágenes de cámara**
   Para cada cámara, obtener la imagen actual y compararla contra una imagen base de referencia
   para detectar si la cámara se movió.
   - **Implementado (03/10/2026)** en `image_compare.py` + `main.py` — ver el detalle completo,
     los 9 experimentos que lo respaldan, y los resultados de la prueba end-to-end en el checklist
     de Estado al final de este documento.
   - Decidido: las imágenes se obtienen de la carpeta descrita arriba (`[CAMARA].jpg` por
     servidor/planta/día).
   - Decidido: `[CAMARA]_ai.jpg` es la salida de un sistema de IA ya existente (a reutilizar,
     no a reconstruir). Falta confirmar qué hace exactamente y si se relaciona con la comparación
     contra la imagen base.
   - La base de imágenes de referencia vive en
     `Test/Image Base/[Cliente]/[Planta]/[Servidor]/[CAMARA].jpg` (misma estructura que la base de
     configuración, sin carpeta de fecha).
   - Curación manual inicial (23/09/2026): se tomó del histórico la imagen más reciente de cada
     cámara sin vehículos, sin personas y tomada entre 8:00 y 9:00 AM. Resultado: **91 imágenes**.
     Las que quedaron fuera son sistemáticamente las de mayor tráfico (andenes de carga, garitas,
     básculas), ocupadas en todos los días revisados.
   - **Inventario real al 25/09/2026** (contado contra `Test/Check Plants`):

     | Planta | Cámaras | Base curada | Sin base |
     | --- | --- | --- | --- |
     | APAN | 9 | 7 | 2 |
     | ATLANTICO | 11 | 9 | 2 |
     | GUADALAJARA | 1 | 1 | — |
     | MEDELLIN | 11 | 4 | 7 |
     | MEXICO | 0 | — | sin imágenes |
     | TOCANCIPA | 12 | 7 | 5 |
     | TUXTEPEC | 18 | 16 | 2 |
     | VALLE | 0 | — | sin imágenes |
     | ZACATECAS | 81 | 47 | 34 |
     | **Total** | **143** | **91** | **52** |

   - **El inventario NO es estático**: ZACATECAS pasó de 67 cámaras (17/09) a 81 (25/09) — 14
     cámaras nuevas en 8 días. Curar la base no es una tarea de una sola vez; el sistema tiene que
     detectar cámaras nuevas sin base y resolverlas solo (igual que Fase 1 con `BASE CREADA`).
   - MEXICO y VALLE (`QLYMSPROD09`) no tienen ninguna imagen en el histórico, solo `.log`.

   ### 2.1 Análisis del método (23/09/2026)

   El usuario compartió el script existente en `Test/Rev_Local/prueba-diferencia.py`. Lo que hace:
   detecta objetos con YOLO11s → tapa de negro las cajas detectadas en **ambas** imágenes (la unión,
   para que un camión presente en solo una no genere diferencia) → aplica desenfoque gaussiano →
   calcula diferencia absoluta píxel a píxel → reporta media, desviación y percentiles.

   Se corrieron dos experimentos para decidir el enfoque con evidencia, no por intuición
   (`Test/Rev_Local/compare_methods.py` y `simulate_shift.py`):

   **Experimento 1 — 15 pares reales ya inspeccionados manualmente**, de 3 tipos: misma cámara
   limpia, misma cámara ocupada por camión/montacargas/persona, y cámaras distintas.

   | Tipo de par | Método 1 (diff de píxeles) | Método 2 (features + homografía) |
   | --- | --- | --- |
   | Misma cámara, iluminación muy distinta | mean=21.7, p99=119 | **0.2 px** |
   | Misma cámara, ocupada (9 casos) | mean entre 6.2 y 25.8 | **0.0 a 0.4 px** |
   | Cámaras distintas (4 casos) | N/A (resolución distinta) | **100 a 441 px** |

   Conclusiones:
   - **El diff de píxeles NO sirve como detector de movimiento.** El par "misma cámara, solo cambió
     la luz" (mean=21.7) cae justo en medio del rango de los pares "misma cámara con camión encima"
     (6.2–25.8). No existe umbral que los separe. Ésta es la fuente directa del riesgo de falsos
     positivos que preocupaba.
   - **El emparejamiento de características separa limpiamente**: 0–1 px vs 100–441 px. Una brecha
     de más de 250x, sin zona gris.
   - **YOLO11s falla bastante en estas imágenes** — etiquetó camiones reales como `refrigerator`,
     `snowboard`, `suitcase`, `airplane`, `boat`, `train` (vistas cenitales/fisheye muy distintas a
     COCO), y en 2 de 9 casos ocupados no detectó nada (montacargas+persona en `P2t2`, camión en
     `A1t2`). **Aun así, el Método 2 clasificó bien los 15 pares**, porque RANSAC descarta solo los
     puntos que no encajan. Es decir: el método geométrico es robusto también a que la detección de
     objetos falle. Por eso **no se invierte por ahora en un modelo más grande ni en YOLO-World**.

   **Experimento 2 — corrimiento simulado** (transformaciones geométricas conocidas):
   - La métrica es **lineal y fiel**: traslación de 1→1.10 px, 10→10.03 px, 100→99.98 px. Mide
     exactamente lo que se cree que mide.
   - Equivalencias en una imagen de 2688 px de ancho: rotación 0.5°≈3.3 px, 1°≈6.5 px, 2°≈13 px,
     5°≈32 px. Zoom +1%≈3.9 px, +5%≈18.7 px.
   - **Piso de ruido real (cuadro completo): 0.2–1.0 px** en los pares de misma cámara, incluso con
     cambios fuertes de iluminación.
   - **Hallazgo crítico**: al recortar el cuadro para la prueba, el par `ZAC_A1p` colapsó de 378
     coincidencias a 4. La causa es que la estructura útil (racks, tarimas) está en los bordes y el
     centro es piso liso. Degradación medida al ir recortando: 100%→378 matches/0.25 px,
     88%→223/0.28 px, 80%→**31 matches/12.03 px**, 70%→no concluyente.
     Lo importante: con solo 26 inliers el método reportó **12.03 px de desplazamiento, que es
     falso**. Un número con pocas coincidencias parece confiable y no lo es.
     → **El conteo de inliers debe ser parte de la decisión, no solo el desplazamiento.**
   - **Prueba de obstrucción** (cámara quieta, lente tapado progresivamente):

     | Tapado | Método 2 (geometría) | Método 1 (contenido) |
     | --- | --- | --- |
     | 25% | 0.00 px, 1950 inliers | mean=12.4 |
     | 50% | 0.00 px, 1021 inliers | mean=47.0 |
     | 80% | 0.09 px, **11 inliers** | mean=102.3 |
     | 95% | no concluyente | mean=113.7 |

     Esto valida el diseño de dos métodos: hasta 80% tapada, el Método 2 dice correctamente "no se
     movió" (¡y es cierto!), pero sería engañoso por sí solo porque la cámara está prácticamente
     ciega. El Método 1 sí lo detecta, subiendo de 12.4 a 102.3.

   **Experimento 3 — ¿sirve una imagen ocupada como base?** (30/09/2026,
   `Test/Rev_Local/test_base_ocupada.py`). La curación manual se hizo bajo el supuesto de usar diff
   de píxeles, donde un camión en la base envenenaría todas las comparaciones. Con el método
   geométrico esa premisa puede no aplicar. Se probaron 16 pares de cámaras que quedaron pendientes
   justamente por estar siempre ocupadas, usando un día con camión como base contra otro día con un
   camión **distinto en otra posición**:

   | Cámara | Inliers | Desplazamiento |
   | --- | --- | --- |
   | ZAC E1p (3 pares) | 428–607 | 0.09–0.12 px |
   | ZAC E1t1 (2 pares) | 168–810 | 0.07–0.18 px |
   | ZAC P1p (2 pares) | 186–383 | 0.11–0.14 px |
   | ZAC E2p (camión vs montacargas) | 209–459 | 0.15–0.25 px |
   | ZAC R2t2, MED B02-C, MED B03 | 122–515 | 0.19–0.32 px |
   | **ZAC C2p** (2 pares) | **8 y 16** | **561 y 649 px** |
   | **TOC B02** (2 pares) | **61 y 87** | **136 y 179 px** |

   - **12 de 16 funcionan perfecto.** Una base con camión sirve igual, incluso comparando contra un
     camión distinto en otra posición. RANSAC descarta la zona ocupada.
   - **Los 4 que fallan** son las cámaras donde el camión ocupa *todo* el cuadro (`C2p` es un primer
     plano de una parrilla; `B02` de TOCANCIPA es un camión que llena la imagen). No queda fondo
     estático al cual anclarse.
   - **El conteo de inliers los separa limpiamente**: casos buenos 122–810, casos malos 8–87. Con un
     mínimo de **~100 inliers** se rechazan los 4 malos y se conservan los 12 buenos, sin excepción.
     La *proporción* de inliers NO sirve para esto (buenos bajan a 0.53, malos suben a 0.58 — se
     traslapan); es el conteo absoluto el que discrimina.
   - **Consecuencia**: la base puede crearse automáticamente para casi todas las 52 cámaras sin
     base, igual que en Fase 1. Las cámaras imposibles se auto-identifican reportando "no
     concluyente" de forma consistente — que es la respuesta honesta ("no puedo verificar esta
     cámara"), no un falso positivo. No hay que curar esa lista a mano.
   - La curación manual sigue siendo valiosa (una base limpia da más inliers = más margen), pero
     pasa de **requisito** a **optimización**.

   **Experimento 4 — el texto sobreimpreso secuestra la medición** (30/09/2026, primera prueba con
   la cámara física; `Test/Rev_Local/verifica_overlay.py`, `cuenta_features.py`, `prueba_rescate.py`).

   **Este hallazgo invalida los números de los Experimentos 1 y 3.** Al mover físicamente la cámara
   y regresarla a ojo, el método reportó que NO se había movido:

   | Acción (la cámara sí se movió) | Con el texto | Con el texto tapado |
   | --- | --- | --- |
   | Golpe y regreso 1 | 0.10 px | **82.89 px** |
   | Golpe y regreso 2 | 0.11 px | **87.59 px** |
   | Golpe y regreso 3 | 0.12 px | **64.32 px** |

   - **Mecanismo**: la fecha/hora y el nombre de la cámara están quemados en coordenadas fijas del
     sensor y no se mueven aunque la cámara gire. Cuando el movimiento es grande, la escena real
     deja de coincidir pero el texto coincide perfecto, y RANSAC se queda con el texto como el
     conjunto consistente mayoritario. Resultado: **falso negativo**, el peor error posible aquí.
   - **No es un caso raro.** Porcentaje de keypoints ORB que caen sobre el texto (que ocupa el 8%
     del área): ZAC_A2p 97.9%, ZAC_P1t2 87.8%, MED_EP1 84.9%, ZAC_A1p 83.0%, ZAC_R2p 81.5%,
     TOC_EP1 75.1%, ZAC_A2t1 68.1%, TUX_E3 34.2%. Letras blancas sobre concreto gris producen
     esquinas mucho más marcadas que la textura del concreto.
   - **Qué invalida**: la separación "limpia" del Experimento 1 (0–1 px vs 100–441 px) era en buena
     parte un artefacto. Los pares de misma cámara daban ~0 px porque el texto estaba fijo, no
     porque la escena coincidiera; los de cámaras distintas daban cientos de px porque tenían
     resoluciones distintas y el texto no alineaba. Se estaba midiendo *"¿tienen el mismo texto en
     el mismo lugar?"*, no *"¿es la misma vista?"*. Las conclusiones coincidieron con la realidad
     por casualidad, porque ninguna de esas cámaras se había movido.
   - **Por qué la prueba sintética no pudo encontrarlo**: al deformar una imagen, el texto se
     deforma junto con la escena, así que nunca entran en conflicto. Hacía falta movimiento físico
     real para que aparecieran las dos versiones en desacuerdo. Ésta es la justificación concreta de
     por qué valió la pena montar la cámara.
   - **Corrección parcial**: tapar el texto arregla el falso negativo (0.10 px → 82.88 px con
     consistencia 0.98). Pero no basta con taparlo — hay que subir también el presupuesto de puntos,
     porque el texto se estaba llevando casi todo. Probado en 5 cámaras de producción con el texto
     tapado y `nfeatures=4000`: ZAC_A1p, ZAC_A2t1 y TUX_E3 recuperan bien; **ZAC_A2p y ZAC_P1t2 no**
     — encuentran 4000 puntos pero ninguno coincide, porque están sobre grano y ruido del concreto
     que no se repite entre capturas.
   - **Enmascarado: bandas completas NO sirven.** Tapar bandas superior e inferior de ancho completo
     (10%) corrige el secuestro pero destruye el emparejamiento en cámaras cuya estructura vive
     cerca de los bordes (ZAC_A2p pasó de 405 inliers a 2 matches). Tapar solo las dos esquinas
     (arriba-izquierda y abajo-derecha, que es donde va el texto en todas las imágenes revisadas —
     formato por defecto de HIKVISION y AXIS) conserva más cuadro, pero sigue siendo insuficiente
     para las cámaras sin textura.
   - **Pendiente**: para las cámaras de poca textura, ORB no es el detector adecuado. Hay que probar
     un método basado en intensidad (correlación de fase o alineación ECC) que no dependa de
     esquinas.

   **Experimento 5 — piso de ruido real sobre un ciclo completo de 24h** (02/10/2026,
   `Test/Rev_Local/analiza_linea_base.py`). Prueba 1 de la batería con cámara física: 175 capturas
   cada 10 min, cámara HIKVISION fija, sin tocar, desde 30/09 15:49 hasta 02/10 07:59 sin ningún
   hueco (el reinicio del 01/10 corrigió la suspensión que había interrumpido el primer intento).
   Mide consecutivas con las esquinas del texto ya enmascaradas (corrección del Experimento 4).

   | Régimen | Mediana | p95 | Máximo |
   | --- | --- | --- | --- |
   | Día (122 pares) | 0.30 px | 1.06 px | 1.71 px (0.064% del ancho) |
   | Infrarrojo nocturno (47 pares) | 0.19 px | 0.33 px | 0.36 px (0.014%) |

   - **La noche en infrarrojo es MÁS estable que el día**, no menos — sin sol cambiando de ángulo ni
     reflejos moviéndose, la iluminación artificial es más constante.
   - **Las transiciones de régimen** (cambio de filtro IR-cut, la transformación más agresiva que
     sufre esta cámara) se midieron en las 2 ocurrencias del ciclo: 1.89 px y 1.79 px (día→IR, con
     70 y 32 inliers), 0.94 px y 0.80 px (IR→día, con 321 y 15 inliers). Nunca superaron 1.9 px.
   - **Margen sobre el umbral propuesto**: el peor momento de un ciclo real completo (1.89 px,
     0.070% del ancho) queda muy por debajo del umbral de 0.25% (≈7 px en esta resolución) — más de
     3x de colchón. Comparado con el movimiento real medido en el Experimento 4 (golpe y regreso:
     64-88 px), la separación es de más de 30x. Esto valida con datos reales, no solo con la muestra
     pequeña de producción, que el rango de umbral 0.25-0.5% es razonable.
   - **Único caso no concluyente**: cruzando el hueco de 10h de la suspensión (solo 5 inliers) — es
     la reacción correcta ante algo genuinamente anómalo, no una falla del método.
   - **Hallazgo adicional**: las horas 16:18-18:08 (sol de media tarde) muestran más ruido que el
     resto del día (hasta 1.71 px vs 0.30 px típico), probablemente por sombras moviéndose rápido.
     Sigue siendo insignificante frente al umbral, pero es la ventana más "ruidosa" del ciclo.

   **Experimento 6 — repuesto para cámaras sin textura** (02/10/2026,
   `Test/Rev_Local/prueba_correlacion_fase.py` y `prueba_ocupacion_agresiva.py`). ORB no encuentra
   estructura repetible en `ZAC_A2p`/`ZAC_P1t2` ni siquiera con el texto tapado (Experimento 4). Se
   probaron dos alternativas basadas en intensidad de píxel, no en esquinas: correlación de fase
   (`cv2.phaseCorrelate`) y ECC (`cv2.findTransformECC`).

   - **Ambas sí dan un número en las cámaras donde ORB no podía**: 0.8–1.2 px, consistente con "no
     se movió" (que es la verdad en esos casos). Pero igual que con los inliers de ORB, la confianza
     cae con la textura: 0.03–0.09 en las cámaras difíciles vs 0.32–0.71 en los controles buenos
     (correlación de fase) — el mismo patrón de "la medida es correcta pero hay que exigirle
     confianza", solo que aquí es continuo en vez de un conteo.
   - **Discrepancia a tener en cuenta**: en `TUX_E3`, ORB daba 0.98 px y estos métodos dan 4.6–4.8 px
     para el mismo par. No es un error — correlación de fase/ECC estiman un corrimiento global único,
     sin el filtro de outliers que tiene RANSAC, así que una zona con cambio real (sombra, reflejo)
     arrastra el resultado completo. No son intercambiables número por número con ORB.
   - **Prueba de estrés — ocupación agresiva** (lo más importante): la preocupación era que, sin
     outlier-rejection, un camión dominante pudiera producir un número alto con confianza alta
     (silenciosamente mal). Con ocupación sintética hasta el 85% del cuadro, ambos métodos siguen
     correctos (≤0.54 px) y la confianza no cae. Contra los casos reales más extremos conocidos
     (`ZAC_C2p`, `TOC_B02`, donde ORB dio 561–649 px y 136–179 px con pocos inliers), correlación de
     fase dio números pequeños (0.23–1.07 px, correctos) con confianza **0.006–0.021** — muy por
     debajo de cualquier caso bueno, la misma separación limpia que vimos con inliers. ECC fue algo
     menos limpio (hasta 10 px en un caso) pero su `cc` también cayó con claridad (0.19–0.46 vs
     0.78–0.91 de los buenos).
   - **Decidido**: diseño en cascada. ORB+RANSAC primero (más robusto donde hay textura, por el
     filtro de outliers); si falla por falta de estructura, correlación de fase como repuesto,
     filtrando por su propio umbral de confianza (orden de magnitud: bueno ≥0.3, malo ≤0.02 — falta
     afinar el corte exacto con más casos). ECC queda fuera del decisor, como verificación cruzada
     opcional nada más.

   **Experimento 7 — minería del histórico real expone un modo de falla más grave: patrones
   repetitivos** (02/10/2026, `Test/Rev_Local/mina_historico.py` y `diagnostico_fallas.py`). En vez
   de seguir con la cámara física, se aprovechó el hallazgo del histórico real (ver "Estructura de
   datos": 320 días en 2026, 124 en 2025) para ampliar el piso de ruido más allá de una sola cámara
   casera — la alternativa elegida en vez de dar acceso directo a cámaras de producción. Se tomó 1
   día por mes (marzo-septiembre, único tramo con estructura de carpetas consistente con el formato
   actual) para 8 cámaras de distintas plantas, comparando **todos los pares** dentro de cada cámara
   (21 combinaciones) con el método en cascada del Experimento 6.

   De 110 pares concluyentes, la mayoría se comportó bien (medianas de 0.08-5.4 px), pero varios
   cruzaron el umbral propuesto de forma sistemática. Revisando las imágenes a mano:

   - **`ZACATECAS/QLYMSPROD01/NE` tiene una hilera de reflectantes de pavimento espaciados
     regularmente.** Comparando marzo vs. septiembre (visualmente idénticas, la cámara NO se movió),
     el método reportó **86.7-86.8 px — y esta vez AMBOS métodos coincidieron y pasaron sus propios
     filtros de confianza**: ORB con 110 inliers (por encima del mínimo de ~100 del Experimento 3) y
     correlación de fase con confianza 0.32 (por encima del 0.15 del Experimento 6). El patrón
     repetitivo hace que ambos métodos se anclen al reflectante vecino equivocado, de forma
     consistente, en vez de al correcto — y como ambos se equivocan de la misma manera, uno no
     delata el error del otro.
   - **`TOCANCIPA/QLYMSPROD05/EL` es peor todavía**: tiene reflectantes en el piso Y una fila de
     columnas/vigas idénticas de una estructura elevada perdiéndose hacia el fondo — dos fuentes de
     periodicidad en la misma imagen. Abril vs. mayo dio **97.1 px con 184 inliers de ORB** (muy por
     encima del umbral de confianza), mientras que correlación de fase, con razón, desconfió
     (confianza=0.026, se habría descartado sola) y hubiera dado el valor correcto si se le hiciera
     caso (0.11 px). Aquí los dos métodos **discrepan fuertemente** en vez de coincidir — y como el
     diseño en cascada solo recurre a correlación de fase cuando ORB *falla*, no cuando *discrepa*,
     el sistema se habría quedado con el 97 px de ORB y disparado una alerta falsa.
   - **`TUXTEPEC/QLYMSPROD06/E3`** (el caso sin textura ya conocido) mostró un problema relacionado
     pero distinto: en pares de meses lejanos, ORB correctamente se queda sin suficientes inliers
     (4-10, bien por debajo del mínimo) y cede el paso a correlación de fase — pero esta da
     **59-62 px con confianza 0.30**, por encima del umbral de 0.15 fijado en el Experimento 6.
     Revisando las imágenes, la cámara no se movió; lo que cambia con los meses es la suciedad y las
     manchas del piso, la única "estructura" que correlación de fase tiene para anclarse en una
     escena casi lisa. **El umbral de 0.15 se calibró con pares de días cercanos (Experimento 6) y
     no generaliza a comparaciones de meses de distancia** en escenas sin textura real.

   **Conclusión — esto es más serio que "ajustar un número"**: el diseño actual (cada método con su
   propio umbral de confianza, cascada solo-si-falla) no protege contra el aliasing de patrones
   repetitivos, porque en el caso de `NE` ambos métodos se equivocan de la misma forma y se
   corroboran mutuamente sin darse cuenta. Decidido (02/10/2026), pendiente de implementar:
   - Correr **ambos métodos siempre**, no en cascada solo-si-falla, y tratar el **desacuerdo entre
     ellos** como señal de alerta en sí misma (el caso `EL` se habría detectado así: 97 px vs.
     0.11 px es una discrepancia enorme que merece revisión humana sin importar que ORB solo
     "pasara" su propio umbral).
   - Evaluar una detección explícita de estructura periódica (ej. picos secundarios en la
     autocorrelación) para marcar esas cámaras como de mayor riesgo y exigirles más margen o revisión
     humana obligatoria ante cualquier cambio detectado.
   - Recalibrar el umbral de confianza de correlación de fase usando pares de meses lejanos, no solo
     los días cercanos del Experimento 6.
   - Pregunta abierta sin resolver: si el aliasing puede producir un desplazamiento falso que no es
     cero, ¿podría también **enmascarar** un movimiento real pequeño (falso negativo), no solo
     inventar uno que no existe? No se ha probado directamente.

   **Experimento 7b — validar la defensa de "correr ambos métodos siempre"** (02/10/2026,
   `Test/Rev_Local/deteccion_desacuerdo.py`). Se implementó: ORB y correlación de fase corren
   siempre (no cascada solo-si-falla); si ambos pasan su propio umbral de confianza pero discrepan
   más de 15 px, se marca `DISCREPANCIA`; si cualquiera confiable da un desplazamiento por encima
   del umbral de movimiento, se marca `REVISAR` en vez de `OK` silencioso.

   | Caso | Resultado | Detalle |
   | --- | --- | --- |
   | `ZAC_NE` marzo vs abril (control, sin mover) | `OK` | ORB 2.48px/55in, Fase 2.22px/conf.61 |
   | `ZAC_NE` abril vs sept. (el caso que engañó a ambos) | `REVISAR` | ambos de acuerdo en ~87px — ya NO pasa como `OK` |
   | `TOC_EL` abril vs mayo (discrepancia) | `REVISAR` | ORB 97px/184in vs Fase 0.11px/conf.03 — ya NO se queda con el 97px de ORB sin más |
   | `TUX_E3` marzo vs julio (sin textura) | `REVISAR` | ORB inservible (4 inliers), Fase 59px — correctamente no pasa como `OK` |
   | `MED_EP1` marzo vs junio (control, buena textura) | `NO_CONCLUYENTE` | el desplazamiento real es ~2px, pero ningún método junta suficiente confianza a 3 meses de distancia |
   | `APAN_CS` agosto vs sept. | `REVISAR` | sin investigar a fondo todavía, misma familia de síntoma |

   **Lo que sí se logró**: ningún caso conocido como problemático se cuela como `OK` falso — los
   tres casos malos del Experimento 7 (`NE`, `EL`, `E3`) ahora escalan a revisión humana en vez de
   generar una falsa sensación de certeza. Esa es la propiedad de seguridad que importaba.

   **Lo que NO se logró, con honestidad**: el primer intento de detectar la estructura periódica
   *directamente* (calcular la superficie completa de correlación de fase a mano, vía FFT propio, y
   buscar un segundo pico casi tan alto como el primero) tenía un error de implementación — dio
   159 px para `TOC_EL` cuando el cálculo ya validado con `cv2.phaseCorrelate` daba 0.11 px para el
   mismo par. Se descartó ese intento en vez de reportarlo como funcionando; **queda pendiente**
   diseñarlo de nuevo, probablemente como autocorrelación de una sola imagen (no correlación cruzada
   entre dos) para no mezclar la pregunta de "¿hay un patrón repetitivo aquí?" con la de "¿cuánto se
   movió?". Sin esto, el sistema sabe decir "hay que revisar a mano" pero no "esto probablemente es
   un patrón repetitivo, no un movimiento real" — que sería más útil para quien revisa.
   - **Hallazgo adicional**: incluso una cámara con buena textura (`MED_EP1`) cae a `NO_CONCLUYENTE`
     comparando marzo contra junio (3 meses), a pesar de que el desplazamiento real es mínimo (~2px).
     Los umbrales de confianza del Experimento 6 se calibraron con pares de días cercanos y pierden
     fuerza en comparaciones de meses — coherente con lo ya visto en `TUX_E3`, pero ahora confirmado
     también en una cámara "fácil". En producción esto pesa menos de lo que parece, porque la base
     de comparación se mantiene vigente (no se compara contra una foto de hace 3 meses), pero sí
     advierte que **el umbral de confianza debe calibrarse contra el intervalo real de comparación**,
     no asumir que lo medido con días cercanos generaliza a cualquier plazo.

   ### 2.2 Diseño decidido (en revisión tras el Experimento 4)

   > Los umbrales y tablas de esta sección se calcularon **sin enmascarar el texto sobreimpreso**
   > (Experimentos 1–3). El Experimento 4 muestra que eso invalida los números concretos, aunque el
   > diseño de "dos señales + guarda de inliers" sigue siendo correcto. Repetir con el texto
   > enmascarado antes de fijar el umbral final.

   **No son dos métodos votando sobre la misma pregunta — cada uno responde una pregunta distinta:**

   - **Método 2 (features + homografía)**: ¿está apuntando al mismo lugar? → señal **principal**.
   - **Método 1 (diff de píxeles)**: ¿está viendo lo mismo? → señal **secundaria**, con umbral
     flojo a propósito (bien por encima del 21.7 que produce un cambio de luz), solo para fallas
     evidentes.
   - **Conteo de inliers**: señal de confianza. Pocos inliers ⇒ no concluyente, sin importar qué
     diga el desplazamiento.

   | Geometría (M2) | Contenido (M1) | Diagnóstico |
   | --- | --- | --- |
   | alineada | similar | OK |
   | alineada | muy distinto | En su lugar pero obstruida/alterada → revisar |
   | no alineada | — | **Cámara movida** → alertar |
   | inliers insuficientes | — | No se puede comparar (tapada/oscura) → revisar |

   Otras decisiones:
   - **Usar el cuadro completo**, nunca recortado.
   - **Umbral normalizado como % del ancho**, no en píxeles absolutos: las cámaras van de 1280 a
     3840 px de ancho y 10 px no significan lo mismo en una que en otra.
   - Umbral inicial propuesto: **0.25–0.5% del ancho** (≈7–13 px en una cámara de 2688). Deja un
     margen de 6x sobre el piso de ruido medido (≈1 px) y detecta rotaciones desde ~1°. A confirmar
     con la prueba de cámara física.
   - **Mínimo de inliers: ~100** (validado en el Experimento 3). Por debajo de eso el resultado es
     "no concluyente" sin importar qué diga el desplazamiento.
   - Decidido (30/09/2026) — **sensibilidad: sensible + confirmación de 2–3 días**. Se detecta
     desde ~1° de giro, pero solo se alerta si la diferencia persiste varios días seguidos. Combina
     sensibilidad alta con casi cero falsos positivos, a costa de 1–2 días de retraso en el aviso.
     Un día raro de iluminación no se repite; una cámara movida sí.
   - Decidido (30/09/2026) — **la base de imagen se crea sola** (`BASE CREADA`) para las cámaras que
     no la tengan, igual que en Fase 1. Ya no es requisito curarla a mano (ver Experimento 3).

   ### 2.3 Ventana de revisión (decidido 30/09/2026)

   Cuando una cámara sale dudosa, el sistema **abre una ventana durante la ejecución** con la imagen
   base a la izquierda y la imagen actual a la derecha, y tres botones abajo:

   | Botón | Significado | Efecto |
   | --- | --- | --- |
   | **Bien** | El algoritmo se equivocó, la cámara no se movió | Falso positivo. Se registra y no se vuelve a preguntar lo mismo. |
   | **Mal** | Sí se movió, hay que ir a acomodarla físicamente | Queda como incidencia abierta y sigue alertando hasta resolverse. |
   | **Base Desactualizada** | Se movió y se acepta como la nueva normalidad | **No** reemplaza la base de inmediato — ver sección 2.8, el reemplazo real se hace aparte con `ventana_bases.py`. |

   - **Por qué durante la ejecución y no en una cola aparte**: una cola que nadie revisa es peor que
     una pausa que obliga a decidir. Así el proceso termina completo, sin nada pendiente.
   - **Distinguir "Bien" de "Sustituir Base" importa**: ambos detienen la alerta, pero por razones
     distintas. Guardar esa diferencia da gratis la **tasa real de falsos positivos** medida en
     producción — la única forma de saber si el umbral quedó bien calibrado.
   - **Solo interrumpen las cámaras dudosas.** Las que pasan limpio nunca abren ventana. Con la
     regla de confirmar 2–3 días, deberían ser pocas. Llevar un contador ("3 de 7").
   - **Bandera `--sin-interaccion`** para la corrida automatizada (Fases 5 y 6 necesitan que el
     proceso termine solo para generar y enviar el reporte diario). En ese modo las dudosas quedan
     marcadas como "pendiente de revisión" y se vuelven a preguntar en la siguiente corrida manual.
   - La misma ventana sirve para **Fase 1**: en vez de dos imágenes, una tabla de campo / valor base
     / valor actual, con los mismos tres botones. Resuelve el mecanismo de "aceptar cambio como
     nueva base" que estaba pendiente en ambas fases.

   ### 2.4 Batería de pruebas con cámara física (ejecutada 03/10/2026 — ver resultados en 2.5)

   Las cámaras de producción no se pueden mover. El experimento sintético tiene un límite honesto:
   deformar una imagen en 2D y luego medirla con un método que **estima transformaciones 2D** es en
   buena parte una tautología. No reproduce paralaje, contenido nuevo entrando al cuadro, cambio de
   reflejos especulares, reajuste de auto-exposición, ni la interacción del giro con la distorsión
   del lente. Por eso se montará una cámara en trípode para validar con movimiento real.

   **Equipo (confirmado 30/09/2026): una cámara HIKVISION**, que es una de las marcas de producción
   — así que la óptica, la resolución y la compresión son representativas y los números salen
   directamente comparables. Se necesita además un trípode, preferentemente **con escala de grados
   en el cabezal** para poder medir el movimiento aplicado.

   **Captura: no se necesita tarjeta SD.** Script listo en `Test/Camara_Fisica/capturar.py`. Usa el
   mismo endpoint ISAPI y la misma autenticación digest que producción
   (`/ISAPI/Streaming/channels/1/picture`), que es lo que determina resolución y compresión del
   JPEG. Guarda en `Test/Camara_Fisica/[escenario]/[timestamp].jpg` más un `capturas.csv` con la
   verdad conocida de cada toma.

   Se configura con un `.env` en esa carpeta (`CAM_TEST_IP`, `CAM_TEST_USER`, `CAM_TEST_PASS`) y
   tiene tres modos:

   ```powershell
   python capturar.py --probar                              # verifica conexión y encuadre
   python capturar.py --escenario A_base --intervalo 20     # desatendido, cada 20 min
   python capturar.py --escenario A_movimientos             # interactivo, pide nota por captura
   ```

   **Tiempo estimado**: ~2h15 de trabajo real, repartido en dos ratos con un día de por medio en el
   que el script corre solo.

   | Prueba | Tiempo del usuario | Transcurrido |
   | --- | --- | --- |
   | Montar, apuntar y arrancar | 15 min | — |
   | 1. Línea base sin movimiento | 0 min (corre sola) | 1 día |
   | 2–6. Movimientos, golpe y regreso, obstrucción, objeto, zoom | ~2 h seguidas | 2 h |

   Versión reducida si hay poco tiempo: línea base de 6 horas (mañana a tarde, que ya captura el
   mayor cambio de luz) y pruebas 2–6 recortadas a 1°, 2° y 5° — queda en ~1 hora total, a costa de
   precisión en el piso de ruido, que es justo el número más importante.

   **Dónde ponerla y a dónde apuntarla** — se necesitan **dos escenarios**, porque el Experimento 2
   mostró que la robustez depende de cuánta estructura hay en el cuadro:
   - **Escenario A (fácil, con estructura)**: apuntar a una zona con bordes y objetos a distintas
     distancias — muebles, marcos de puerta, estantes, un pasillo. Equivale a las cámaras tipo
     `MED_EP1` / `ZAC_A1p` a cuadro completo. Los objetos a distintas profundidades son los que
     generan el **paralaje** que la simulación no puede reproducir.
   - **Escenario B (difícil, casi sin textura)**: apuntar a una superficie lisa y uniforme — una
     pared blanca, el piso, la puerta del garaje. Equivale a `TUX_E3`. Aquí es donde esperamos que
     el método sea frágil y necesitamos saber **cuánto**.
   - En ambos, que le dé **luz natural cambiante** (cerca de una ventana), para que la línea base
     capture variación real de iluminación a lo largo del día.

   **Batería de pruebas, en orden:**

   1. **Línea base sin movimiento (lo más valioso, ~1 día)**
      Cámara fija, captura cada 15–30 min durante un día completo: mañana, mediodía, tarde, noche
      con luz artificial. Nada se mueve.
      → Da el **piso de ruido real** bajo variación de iluminación completa. Hoy ese número se
      estima con apenas un puñado de pares de una ventana de 10 días de septiembre, y ya se vio que
      varía entre 0.2 y 1.0 px según la cámara. Es el número que define el umbral.
   2. **Movimientos medidos (~1 hora)**
      Con la escala del cabezal: 0.5°, 1°, 2°, 5° y 10°. Capturar antes y después de cada uno.
      → Permite contrastar el movimiento real contra la equivalencia calculada en la simulación
      (1°≈6.5 px en 2688 de ancho) y ver cuánto la desvía el paralaje.
   3. **Golpe y regreso (~15 min)**
      Mover la cámara y volverla a su lugar "a ojo", como quien la golpeó sin querer y la reacomodó.
      Repetir 3–4 veces.
      → Es el escenario realista de producción. Mide el error residual que queda y si cae por
      encima o por debajo del umbral.
   4. **Obstrucción (~15 min)**
      Tapar el lente parcialmente (25%, 50%, 80%) y casi por completo, con objetos reales (una
      caja, una bolsa, cinta sobre el domo).
      → Valida con óptica real (desenfoque, reflejos) lo que se simuló con un rectángulo negro, y
      confirma que responde "no puedo comparar" en vez de pasar como OK.
   5. **Objeto sin mover la cámara (~15 min)**
      Que alguien se pare enfrente, o poner una caja grande, sin tocar el trípode.
      → El equivalente al camión estacionado, pero con certeza absoluta de que la cámara no se
      movió. Confirma que no genera falso positivo.
   6. **Zoom, si la cámara es varifocal (~10 min)**
      Cambiar el zoom ligeramente sin mover el cuerpo de la cámara.

   **Salida esperada**: un conjunto de pares con verdad conocida que permita (a) fijar el umbral
   con datos reales en vez de estimados, y (b) verificar el mínimo de inliers por debajo del cual
   no hay que confiar en el número.

   ### 2.5 Experimento 8 — resultados de la batería con cámara física (03/10/2026)

   Ejecutada contra la HIKVISION `iDS-2CD7A46G0/P-IZHS` (lente motorizado) montada en trípode
   graduado cada 10°, cocina con buena textura y objetos a distancias variadas (1-3 m). ~24 capturas
   analizadas con el método validado del Experimento 7b (ORB+RANSAC y correlación de fase, siempre
   los dos, esquinas del texto enmascaradas).

   **Hallazgo 1 — el "a ojo" deja un residuo estable, no aleatorio.** Al reacomodar la cámara a su
   posición original antes del bloque de obstrucción, quedó un desfase de ~150-155 px (contra la
   referencia inicial) que se mantuvo **idéntico** durante todo el resto de la sesión (obstrucción,
   objeto, zoom) — no fue ruido ni deriva, fue una posición nueva y estable, distinta de la original.
   Esto en sí mismo es el hallazgo del golpe-y-regreso funcionando como se esperaba: un reacomodo a
   ojo no es "quedar igual", es una posición nueva que hay que volver a medir.

   **Hallazgo 2 — golpe y regreso, con verdad conocida real**: los 7 intentos de "mover y regresar a
   ojo" dieron entre **118 y 420 px de residuo** contra la referencia original — todos correctamente
   marcados `REVISAR` por el sistema. Confirma con datos reales (no estimados) que un reacomodo
   manual sin instrumentos dista mucho de ser exacto, y valida por qué la ventana de revisión
   (sección 2.3) es necesaria y no un exceso de precaución.

   **Hallazgo 3 — obstrucción y objeto: comportamiento limpio**, re-analizado contra una línea base
   local (sin el residuo del Hallazgo 1 de por medio):

   | Prueba | Decisión | Geometría | Contenido |
   | --- | --- | --- | --- |
   | Obstrucción 25-50% | `OK` | 1.3 px | 35-53 |
   | Obstrucción 80% | `REVISAR` (límite) | 7.0 px, solo 34 inliers | 66 |
   | Obstrucción 95% | `NO_CONCLUYENTE` | sin suficientes puntos | 60 |
   | Persona enfrente | `OK` | 0.52 px | 16 |
   | Objeto grande | `OK` | 0.44 px | 51 |

   Exactamente lo esperado: estable mientras hay suficiente estructura visible, honestamente "no
   concluyente" cuando ya no queda nada que medir (igual que se vio en el Experimento 2 con la
   obstrucción simulada), y el contenido sube con la ocupación.

   **Hallazgo 4 — el zoom es un punto ciego de la geometría, confirmado y con alcance decidido.**
   Los cambios de zoom (absoluteZoom 30→35→45→65, ver más abajo) dieron 0.19-0.65 px — **todos
   `OK`**. La homografía absorbe el cambio de escala sin interpretarlo como movimiento. Se investigó
   si Fase 1 lo cubre por otro lado (el usuario preguntó esto directamente) — **no lo cubre**,
   verificado en el código: ni la lista de descarga de `HikvCamConf()` (`Test/cameras/hikvision.py`)
   ni la lista curada de campos HIKVISION en `config_compare.py` tocan `PTZCtrl/channels/1/status`
   (donde vive `absoluteZoom`, encontrado en el Hallazgo 6 más abajo). **Decidido**: si se quiere
   cubrir, va en Fase 1 (agregar el endpoint a la descarga y el campo a la comparación), no en
   Fase 2 — es un dato de configuración, no de geometría. Es específico de cámaras con lente
   motorizado (`IZHS` u equivalente); en lentes fijos el campo simplemente no existiría, igual que
   ya se tolera con cualquier campo ausente. Pendiente confirmar qué parte del parque de cámaras
   tiene lente motorizado antes de implementarlo.

   **Hallazgo 5 — la relación grados↔píxeles real es ~10x mayor que la simulada, y es específica de
   cada escena.** Usando las marcas confiables del trípode (10°/20°, no las interpoladas a ojo):

   | Movimiento | Medido | Predicho por el Experimento 2 (simulación 2D) |
   | --- | --- | --- |
   | 1° horizontal | 123 px* | ~6.5 px |
   | 10° horizontal | 709 px | ~65 px |
   | 20° horizontal | 1321 px | ~130 px |

   (*el valor de 1° es el menos confiable — interpolado a ojo entre marcas de 10°, no medido con
   precisión angular.)

   La simulación giraba la imagen en 2D sin paralaje; en la realidad, con objetos cercanos (1-3 m,
   como esta cocina), el mismo giro físico produce un corrimiento de píxeles mucho mayor. Esto
   **no invalida el método** — refuerza con evidencia directa la Decisión de Fase 3 (perfil
   estadístico por cámara, no un umbral único): una cámara mirando de cerca necesita mucho más
   margen en píxeles que una cámara de patio mirando a 20 metros, para el mismo grado real de
   movimiento. El umbral de 0.25-0.5% del ancho puede ser demasiado sensible para cámaras de interior
   cercanas y demasiado laxo para escenas muy lejanas — es exactamente el tipo de calibración que el
   perfil por cámara (Fase 3) está diseñado para resolver.

   **Hallazgo 6 — de paso, se documentó el control de zoom por API** (útil si se decide cerrar el
   punto ciego del Hallazgo 4): `PTZCtrl/channels/1/status` reporta `absoluteZoom` (valor absoluto,
   no relativo); se cambia con `PUT PTZCtrl/channels/1/absolute` enviando ese mismo campo —
   controlado y reversible, a diferencia de `PTZCtrl/channels/1/continuous` (pulsos de velocidad×
   tiempo) que se probó primero y **dejó la cámara completamente desenfocada** sin cambiar el
   encuadre (el "zoom" continuo en este modelo parece mover principalmente el grupo de enfoque, no
   el campo de visión). Se recuperó cambiando `Image/channels/1/FocusConfiguration` a `AUTO`
   temporalmente — modo que se dejó así de forma permanente a petición del usuario, en vez de
   regresar a `SEMIAUTOMATIC` como estaba originalmente.

   ### 2.6 Experimento 9 — rehaciendo los Experimentos 1 y 3 con el texto enmascarado (03/10/2026)

   Los Experimentos 1 y 3 (ver 2.1) se habían calculado **sin** la corrección de esquinas del
   Experimento 4 — quedaron marcados como provisionales. Se rehicieron con el pipeline actual
   (`Test/Rev_Local/rehacer_exp_1_3.py`): esquinas enmascaradas, ORB+RANSAC y correlación de fase
   siempre los dos (Experimento 7b), mismos 15 + 16 pares originales.

   **Experimento 1 — la corrección funciona, con un matiz nuevo.** Casi todos los pares "misma
   cámara" resuelven limpio en `OK`. Pero `ZAC_A2p` (antes 405 inliers / 0.15 px, se veía perfecto)
   ahora da `NO_CONCLUYENTE` — sin el texto, ORB no encuentra nada ahí. `ZAC_P2t2` pasa a `OK` por
   muy poco, cuando antes tenía 338 inliers cómodos: ORB cae a 5 inliers y la decisión termina
   dependiendo de que la fase alcance apenas 0.17 de confianza (umbral 0.15). Los pares de "cámaras
   distintas" no se re-evaluaron esta vez (son de resoluciones distintas entre sí, lo cual ya es de
   por sí una señal trivial de "otra cámara" sin necesidad de correr la geometría).

   **Experimento 3 — esto cambia la conclusión original de forma sustancial.** La conclusión de
   2.1 era "12 de 16 funcionan muy bien, el corte de ~100 inliers separa limpio lo bueno de lo
   malo". Con las esquinas bien tapadas:

   | Cámara | Inliers ORB antes | Inliers ORB ahora | Veredicto ahora |
   | --- | --- | --- | --- |
   | `ZAC_E1p` (3 pares) | 428–607 (el mejor caso de la prueba) | 7–28 | `NO_CONCLUYENTE` los 3 |
   | `ZAC_P1p` (2 pares) | 186–383 | 4–7 | `NO_CONCLUYENTE` los 2 |
   | `MED_B03` | 122 | 1 | `NO_CONCLUYENTE` |
   | `TOC_B02` (ya conocido como malo) | 61–87, número falso | 112–175 (**ahora pasa el filtro**), mismo número falso | `REVISAR` (no `OK` — la salvaguarda del Experimento 7b sigue funcionando) |
   | `ZAC_E1t1`, `ZAC_R2t2`, `MED_B02-C` | Buenos | Siguen buenos | `OK` |

   **Lectura honesta**: varias cámaras que parecían "fáciles" (E1p, P1p, MED_B03) sacaban casi toda
   su confianza del texto sobreimpreso, no de la escena real — el mismo problema de fondo del
   Experimento 4, visto ahora desde el ángulo contrario (inflaba inliers en vez de inventar
   desplazamientos). Al taparlo correctamente, **no mienten en ningún caso** (todo lo que antes daba
   un número confiable, ahora sigue bien o pasa honestamente a `NO_CONCLUYENTE`), pero la fracción
   real de cámaras "fácilmente medibles por ORB" es menor de lo que se reportó en 2.1 — habrá que
   apoyarse más de lo esperado en correlación de fase (Experimento 6) y en el perfil por cámara
   (Fase 3) para las cámaras que queden en esa zona gris.
   - **Pendiente**: el umbral de confianza de fase (0.15) sigue viéndose como un corte algo
     arbitrario — varios casos quedan muy cerca por abajo (0.06–0.12) o por arriba (0.17–0.29).
     Vale la pena recalibrarlo con una muestra más grande antes de fijarlo en el módulo final.

   - Preguntas abiertas:
     - ¿Qué parte del parque de cámaras de producción tiene lente motorizado (candidatas a necesitar
       el campo de zoom en Fase 1)? Sin esto no se puede dimensionar el Hallazgo 4.
     - Cuando ya haya varios días acumulados, ¿el programa debe procesar solo el día más reciente,
       un rango de fechas, o todos los pendientes de procesar?
     - ¿Qué reporta una cámara que ese día falló en el log (`Timed out`, sin `.jpg`)? Propuesta:
       registrarlo explícito como `SIN IMAGEN` en vez de omitirla en silencio.

   ### 2.7 Semáforo de estados (decidido 03/10/2026)

   Surgió de la pregunta "¿qué pasa cuando una cámara da `NO CONCLUYENTE`, me pregunta?" — la
   respuesta honesta era "hoy no, solo se imprime" porque la ventana de revisión no existe todavía.
   Eso llevó a notar que `REVISAR` (sospecha automática, sin veredicto humano todavía) y "se movió"
   (confirmado por un humano) **no son el mismo estado**, aunque hasta ahora se hablaba de ellos
   como si lo fueran. El semáforo de 4 colores deja esto explícito:

   | Color | Estado | Qué significa | Quién lo pone |
   | --- | --- | --- | --- |
   | 🟢 Verde | `OK` | Igual a su base, todo bien | El sistema automático |
   | 🟣 Morado | `REVISAR` | Sospecha automática (desplazamiento sobre el umbral, o ORB y fase no coinciden) — **sin veredicto humano todavía** | El sistema automático |
   | 🔴 Rojo | Se movió (confirmado) | Un humano confirmó con "Mal" en la ventana de revisión — incidencia real, abierta hasta que se corrija físicamente | La ventana de revisión (sección 2.3) |
   | 🟡 Ámbar | `NO CONCLUYENTE` | El sistema no pudo verificar la cámara ese día (poca luz, lente sucio/tapado, estructura insuficiente) — **no es una sospecha de movimiento, es falta de información** | El sistema automático |

   Transiciones desde morado, al resolverse en la ventana de revisión:
   - Clic **"Bien"** → vuelve a verde (falso positivo confirmado, no se movió).
   - Clic **"Base Desactualizada"** → pasa a un estado intermedio nuevo (ni verde ni rojo todavía,
     ver sección 2.8) hasta que alguien suba una imagen limpia de reemplazo; ahí vuelve a verde.
   - Clic **"Mal"** → pasa a rojo (incidencia confirmada, queda abierta hasta que alguien la corrija
     físicamente y la cámara vuelva a comparar en verde por sí sola).

   **Decidido (21/10/2026) — qué pasa mientras una cámara está en rojo**: no preguntado explícitamente
   hasta ahora. Una cámara roja casi siempre va a seguir dando `REVISAR` automático cada día mientras
   siga físicamente movida (compara contra la misma base de siempre), así que la regla es:
   - **Morado** (sospecha sin veredicto humano todavía): sigue abriendo la ventana de revisión en cada
     corrida interactiva hasta que alguien la resuelva — es información nueva pendiente de juicio.
   - **Rojo** (ya confirmada por un humano): **no vuelve a abrir la ventana**. Cada día que la
     comparación automática siga dando `REVISAR` por la misma incidencia ya conocida, el sistema solo
     anota el resultado en `historial_comparacion` (es ruido repetido preguntar lo mismo otra vez,
     igual que con `BASE DESACTUALIZADA` en la sección 2.8). Vuelve sola a verde el día que la
     comparación dé `OK` (cámara corregida físicamente) — sin que nadie tenga que confirmarlo a mano.
   - Esto implica que `main.py` necesita consultar `perfil_camara.estado_actual` **antes** de decidir
     si abre `ventana_revision` para una cámara en `REVISAR`, no solo mirar el resultado del día.

   Ámbar sigue su **propia regla de escalamiento, distinta a la de rojo/morado**: un `NO CONCLUYENTE`
   aislado no amerita avisar a nadie (puede ser lluvia en el lente, un día nublado). Si la **misma
   cámara** lo da varios días seguidos, sí amerita aviso — pero con un mensaje distinto
   ("esta cámara lleva N días sin poder verificarse"), no el mismo de "¿se movió?" que usa morado/rojo.
   Ninguno de los tres botones de la ventana de revisión calza bien para ámbar (no hay una sospecha
   concreta que confirmar o rechazar), así que no debería pasar por esa ventana de la misma forma que
   morado.

   Útil tenerlo presente para Fase 4 (reporte ejecutivo): este mismo semáforo es un candidato natural
   para la identidad visual del reporte — un vistazo por planta/cámara sin necesitar leer texto.

   ### 2.8 Reemplazo de bases: por qué no es un solo clic (decidido 03/10/2026)

   El diseño original del botón "Sustituir Base" copiaba de inmediato la imagen que disparó el
   `REVISAR` como nueva base. El usuario señaló el problema de uso diario: **la mayoría de las veces
   que se revisa una cámara hay un camión o montacargas en cuadro** — si no lo hay, probablemente ni
   hubiera disparado `REVISAR`. Copiar esa imagen tal cual hornearía el camión en la base, envenenando
   todas las comparaciones futuras contra una referencia que nunca fue realmente "limpia".

   **Rediseño**: el botón (renombrado **"Base Desactualizada"**) ya no copia nada. Solo dos cosas
   cambian:
   - `image_compare.py`: nuevo marcador `.desactualizada` junto al `.jpg` de la base
     (`marcar_base_desactualizada()` / `base_desactualizada()` / `limpiar_marcador_desactualizada()`).
     Mientras existe, `compare_camera_image()` regresa el estado nuevo `BASE DESACTUALIZADA` sin
     correr la comparación geométrica — no tiene caso seguir preguntando "¿se movió?" sobre una base
     que ya se sabe que está mal, eso solo generaría ruido diario repetido.
     - **Decidido (21/10/2026) — este marcador migra a la base de datos**: en vez del archivo
       `.desactualizada` junto al `.jpg`, el estado vive en `perfil_camara.estado_actual = 'base_desactualizada'`
       (ver sección 3, diseño de tablas). `marcar_base_desactualizada()`/`base_desactualizada()`/
       `limpiar_marcador_desactualizada()` pasan de tocar archivos a leer/escribir esa columna — el
       comportamiento de `compare_camera_image()` no cambia, solo de dónde lee el dato. Pendiente de
       implementar junto con el resto de la Fase 3 (hoy sigue en archivo hasta que exista el módulo
       de BD).
   - **`ventana_bases.py` (implementado 03/10/2026)**: ventana aparte, independiente de la corrida
     diaria, que lista las cámaras con marcador pendiente (hoy escaneando `IMAGE_BASE_ROOT`; pasa a
     consultar `perfil_camara WHERE estado_actual = 'base_desactualizada'` cuando exista la BD — mismo
     cambio que `umbral_para()`). Al elegir
     una cámara se ve su base actual (la desactualizada); el botón "Seleccionar imagen..." abre el
     explorador de archivos y **no guarda de inmediato** — muestra la imagen elegida al lado de la
     base actual para confirmar que se abrió la correcta, y solo el botón **"Aceptar"** (separado,
     aparece habilitado hasta elegir algo) ejecuta `save_base()` y limpia el marcador. Si no era la
     imagen correcta, "Seleccionar imagen..." se puede volver a oprimir sin que nada se haya guardado
     todavía (ajuste pedido 03/10/2026 tras la primera prueba). Al confirmar, una ventanita propia
     avisa "la imagen base de la cámara [ruta] fue cambiada con éxito" — con el tema oscuro/claro de
     la app, no el `messagebox` nativo de Tkinter (que no sigue el tema y siempre sale en modo claro).
     Esto le da al operador libertad real: puede esperar a que el camión se vaya y tomar o elegir una
     foto limpia cuando le convenga, sin depender de la imagen automática del día.

   **`captura.py` (implementado 03/10/2026, movido a carpeta propia el mismo día)**: script de línea
   de comandos aparte, sencillo a propósito, para tomar una foto directo de la cámara en el momento
   exacto en que el operador la ve limpia (sin camión), en vez de depender de la imagen que trajo la
   corrida automática de ese día:

   ```text
   python captura.py <ip> <usuario> <password> <marca>
   ```

   Vive en **`script/capture_img/`**, carpeta deliberadamente independiente del resto de
   Plant_Report (sin depender de su Pipenv) — el usuario la copia completa a cada servidor donde
   haga falta capturar. Incluye su propio `README.md` con las dependencias a instalar (`pip install
   requests`, única dependencia externa). Guarda en `images/<ip>/<timestamp>.jpg`, **relativo a esa
   misma carpeta** (no al directorio desde donde se invoque) — no decide por su cuenta cuál
   cámara/base reemplaza; ese paso lo sigue haciendo `ventana_bases.py` (en el repo principal) con su
   selector de archivo, eligiendo a mano el archivo que `captura.py` dejó en el servidor.

   **Las dudas de endpoint/autenticación se resolvieron con código real**: el usuario ya tenía las 4
   marcas resueltas en `Check_Cameras/conf/cameras/{axis,dahua,hikvision,vivotek}.py` (el programa
   externo de revisión), probadas en producción — incluida DAHUA, confirmada en uso real pese a que su
   *configuración* (Fase 1) sigue pendiente del dump. Se copiaron y adaptaron a un paquete
   `script/capture_img/cameras/` (un archivo por marca + `capturar(ip, usuario, password) -> bytes`,
   más un registro en `cameras/__init__.py` — agregar una marca nueva es un archivo + una línea, como
   se pidió), quitando lo que no aplica a una captura manual de una sola cámara (proxy/túneles SSH,
   sesión compartida entre cientos de cámaras, logging a archivo por servidor, códigos de error
   numéricos) y conservando lo que sí importa — el endpoint exacto y el esquema de autenticación:

   | Marca | Endpoint(s) de imagen | Auth |
   | --- | --- | --- |
   | HIKVISION | `/ISAPI/Streaming/channels/1/picture` | Digest |
   | AXIS | `/axis-cgi/jpg/image.cgi?camera=1` | Digest |
   | VIVOTEK | 5 candidatos en orden (`/cgi-bin/viewer/video.jpg`, `...?channel=0`, `/video.jpg`, `/cgi-bin/jpeg.cgi`, `/cgi-bin/viewer/snapshot.cgi`) | **Basic** (no digest) |
   | DAHUA | 3 candidatos en orden (`/cgi-bin/snapshot.cgi?channel=1`, `...?chn=1`, `/cgi-bin/snapshot.cgi`) | Digest |

   Decisiones tomadas al confirmar con el usuario (03/10/2026):
   - **Sin soporte de proxy/túnel**: el script corre con acceso directo a la cámara, ejecutado en cada
     servidor según se necesite — no a través de los túneles SSH que administra el programa externo de
     revisión (a diferencia del escaneo masivo de producción, que sí los necesita).
   - **Canal fijo por marca, no parametrizable**: se asume siempre el mismo canal que ya usa
     producción (el más alto entre 0 y 1 según la convención de cada marca) — HIKVISION/VIVOTEK ya lo
     traían fijo en la URL en el código original, AXIS/DAHUA fijos a `1` aquí.
   - **Password por línea de comandos**: queda visible en el historial de la terminal. Aceptable para
     esta herramienta interna de un solo operador (se pidió explícitamente así).
   - **`requests` como única dependencia externa, pero fuera del Pipfile principal**: se eligió sobre
     reescribir con `urllib` de la librería estándar para replicar fielmente la autenticación
     Digest/Basic y los reintentos entre URLs candidatas ya probados en producción. Como
     `script/capture_img/` es una carpeta independiente pensada para copiarse a servidores sueltos (no
     para correr dentro del entorno Pipenv de Plant_Report), `requests` se documenta e instala aparte
     (`pip install requests`, ver su `README.md`) en vez de agregarse al Pipfile principal.

3. **Persistencia en base de datos**
   Guardar los resultados de las comparaciones directo en la base de datos.
   - Decidido: PostgreSQL, ya hay un servidor disponible.
   - **Decidido (21/10/2026) — se elimina el paso intermedio de "actualización del log"**: no se
     reescribe el `.log` original ni se genera un archivo nuevo (jsonl u otro) con el resultado del
     día. El programa lee directo el `.log`/`.json`/`.jpg` que ya deja el programa externo de
     revisión, corre las comparaciones de Fase 1/2, y escribe el resultado directo a Postgres.
     - Razonamiento: un archivo intermedio solo protegería contra perder el resultado si la
       escritura a la BD falla — pero el resultado de Fase 1/2 siempre se puede volver a calcular
       desde los archivos originales en disco (son deterministas), así que no hay nada que proteger
       ahí. La única parte que **no** es recalculable es el veredicto humano de la ventana de
       revisión (sección 2.3): si el usuario ya le dio clic a 20 cámaras `REVISAR` y la conexión a
       la BD falla, perder eso sí le cuesta trabajo real repetirlo.
     - **Decidido, por lo anterior**: la escritura a la BD se hace **cámara por cámara, justo
       después de resolver cada una** (incluyendo el veredicto humano si lo hubo), no en lote al
       final de la corrida completa. Así un fallo de conexión a media corrida solo pierde la cámara
       en curso, no las ya procesadas.
     - **Decidido, heredado del mismo razonamiento**: si el programa se vuelve a correr el mismo día
       para la misma cámara, se trata como upsert sobre la fila de `historial_comparacion` de ese
       día (cliente/planta/servidor/cámara/fecha) — la unidad es "resultado del día", no "resultado
       de esta corrida en particular". Evita duplicar filas si el usuario corre dos veces porque la
       primera se interrumpió a medio camino.
   - **Decidido (21/10/2026) — el `.log` por servidor sí se lee, y es el primer dato que se procesa
     por cámara**: antes de correr Fase 1/2, `main.py` parsea el `.log` del servidor
     (`log_parse.py`) para saber qué cámaras intentó capturar el programa externo de revisión ese
     día y con qué resultado (ip, si hubo error, cuál, y tiempo de proceso). Esto resuelve un
     problema real: una cámara que falla por completo (ej. timeout de puerto) no genera ni `.jpg` ni
     `.json`, así que descubrir cámaras solo por esos archivos la dejaba invisible — ahora el roster
     de cámaras de cada corrida sale de la unión de archivos **y** `.log`. El diagnóstico se guarda
     en `historial_comparacion` (`log_ip`/`log_estado`/`log_motivo`/`tiempo_proceso_seg`), separado
     de `config_status`/`imagen_status` porque responde una pregunta distinta ("¿se pudo capturar?"
     vs. "¿cambió?").
   - Decidido (03/10/2026) — **perfil estadístico por cámara, no umbrales globales fijos**. Surge
     directamente de los Experimentos 1-7 (Fase 2): hoy cada cámara se mide contra el mismo umbral
     (0.25% del ancho, 100 inliers, confianza 0.15) sin importar su "personalidad" — y ya vimos que
     no son iguales (`MED_EP1` pierde confianza con brechas de meses; `ZAC_NE`/`TOC_EL` tienen un
     ruido natural de ~85-97 px por sus reflectantes, muy por encima del umbral global, sin haberse
     movido nunca).
     - **No es un modelo de machine learning** — es una línea base estadística por cámara
       (mediana/p95 de su propio histórico) más un ciclo de retroalimentación humana. Más simple de
       construir y, importante para el reporte ejecutivo, **explicable**: la respuesta a "¿por qué
       no alertó esta cámara?" es "su histórico normal es así", no una caja negra.
     - **Riesgo a evitar, identificado desde el diseño**: si el perfil se alimenta con medidas
       crudas sin validar, el sistema aprendería a ignorar exactamente las cámaras más propensas a
       fallar (se acostumbraría a los 85 px de `NE` y dejaría de notar un movimiento real de 90 px,
       o perdería sensibilidad a movimientos menores que su propio "ruido" ya inflado).
     - **Mitigación decidida**: el perfil se alimenta del **veredicto humano de la ventana de
       revisión** (sección 2.3), no de la estadística cruda sin más. Un clic en "Bien" es la señal
       de "este número en esta cámara es ruido confirmado"; un clic en "Mal" es la señal contraria.
       El aprendizaje queda anclado a juicio humano confirmado, no a varianza ciega.
     - **Esquema decidido (21/10/2026)**:

       ```sql
       -- Una fila por cámara física: catálogo (identidad) + estado vivo (semáforo, sección 2.7) +
       -- perfil estadístico (Experimentos 1-9)
       CREATE TABLE perfil_camara (
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

       -- Una fila por cámara por día: registro crudo, alimenta el reporte y el recálculo de perfil
       CREATE TABLE historial_comparacion (
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

           -- diagnóstico del .log del servidor (agregado 21/10/2026, migrations/0002): ¿se pudo
           -- capturar esta cámara ese día?, independiente de si Fase 1/2 encontraron algo que comparar
           log_ip              TEXT,
           log_estado          TEXT,    -- OK | ERROR | NULL (cámara no vista en el .log)
           log_motivo          TEXT,
           tiempo_proceso_seg  REAL,

           UNIQUE (camara_id, fecha)
       );

       CREATE INDEX ON historial_comparacion (camara_id, fecha DESC);
       ```

       - `perfil_camara` hace doble función (catálogo + estado + perfil) en vez de separar una tabla
         de catálogo aparte — cliente/planta/servidor/cámara ya es la clave natural que usa la
         estructura de carpetas en disco.
       - `estado_actual` vive en `perfil_camara`, no se deriva de la fila de hoy en
         `historial_comparacion`, porque el semáforo tiene memoria entre días (rojo/ámbar, ver
         sección 2.7) — `main.py` lo consulta antes de decidir si abre `ventana_revision`.
       - El marcador de base desactualizada (sección 2.8) usa el mismo campo
         (`estado_actual = 'base_desactualizada'`) en vez del archivo `.desactualizada` — decidido
         migrarlo junto con el resto de esta fase.
       - `config_diferencias` como JSONB porque su forma varía según la marca de la cámara.
       - Limitación aceptada: la identidad de la cámara es su ruta (cliente/planta/servidor/cámara);
         si una cámara cambia de servidor, se trata como una cámara nueva (pierde su historial/perfil
         previo) — aceptable por ahora, igual que ya pasa con los archivos en disco.
     - Decidido (03/10/2026), reforzado directamente por los Experimentos 8 y 9 del mismo día —
       **arranque en frío y método preferido por cámara**, dos refinamientos a `perfil_camara`:
       - **Arranque en frío**: una cámara nueva no tiene historial. Usa el umbral global (0.25% del
         ancho) hasta acumular suficientes comparaciones **confirmadas por un humano** en la ventana
         de revisión (ej. 10-15), y a partir de ahí cambia a su propio perfil. Nunca se queda sin
         protección mientras aprende.
       - **Método preferido por cámara**: el Experimento 9 mostró que algunas cámaras
         (`ZAC_E1p`, `ZAC_P1p`, `MED_B03`) casi no tienen estructura real que ORB pueda aprovechar —
         dependen de correlación de fase para dar cualquier respuesta. `perfil_camara` debería guardar
         cuál señal ha sido confiable para esa cámara en particular (ORB, fase, o ambas), para no
         perder tiempo ni generar falsos `NO_CONCLUYENTE` confiando en un método que ya se sabe que
         no le sirve a esa cámara específica.
       - Justificación concreta del porqué un umbral único no alcanza: el Experimento 8 midió que el
         mismo giro físico produce ~123 px en una escena cercana (objetos a 1-3 m) pero ordenes de
         magnitud menos en una escena lejana (patio a 20 m) — la misma cantidad de movimiento real se
         ve muy distinta en píxeles según la cámara.
     - **Idea adicional, de menor riesgo**: guardar el **brillo típico por hora del día** de cada
       cámara (ya sabemos del Experimento 5 que hay un patrón predecible día/transición IR/noche).
       No sirve para detectar movimiento, pero sí para el problema de **obstrucción/lente sucio**:
       comparar el brillo de hoy contra lo típico de esa cámara a esa hora, sin necesitar imagen
       base. Es un uso independiente del Método 1 (contenido), no del Método 2 (geometría).
   - Preguntas abiertas:
     - ¿Datos de conexión al servidor (host, puerto, nombre de BD)? ¿Cómo se van a manejar las
       credenciales (variables de entorno, archivo `.env`, etc.)?
     - ¿Ya existe un esquema o hay que diseñarlo desde cero? (ver boceto arriba para la parte de
       perfiles por cámara — sigue faltando el resto: resultados de Fase 1, resumen por corrida, etc.)
     - ¿Se necesita conservar histórico de todas las corridas o solo el estado más reciente?

4. **Reporte ejecutivo (implementado 21/10/2026)**
   Generar un reporte ejecutivo con los resultados.
   - Decidido: formato PDF, generación diaria, al final de `main.py` (no un comando aparte) -- no
     "por planta" como se pensó originalmente, sino **un PDF por cliente**, con todos sus
     servidores/plantas juntos.
   - **Decidido (21/10/2026) — disparo**: no automático sin más. En modo interactivo, `main.py`
     pregunta en la línea de comandos ("¿Generar el reporte ejecutivo de esta corrida? (s/n)") antes
     de generarlo. En `--sin-interaccion` (corridas desatendidas, sin nadie frente a la terminal)
     sigue generándose automáticamente, sin preguntar -- no tendría quién conteste.
   - **Estilo visual**: encabezado y pie adaptados de `models/reporte_pdf.py` en el proyecto
     hermano `Cam_Lens_V2` (mismo logo, misma paleta, mismas Tables de ReportLab con banda oscura +
     franjas alternadas) -- sin modificar ni importar nada de ese proyecto, solo replicando el
     patrón visual (su contenido es una ficha de instalación de una sola cámara, no aplica aquí).
     Encabezado con dos variantes: Cliente + Fecha en la hoja de resumen (cubre varias plantas a la
     vez, no hay un solo servidor que mostrar ahí); Cliente + Planta + Fecha + Servidor en las
     hojas de detalle. Pie de la hoja de resumen además trae una línea de simbología (qué significa
     cada color).
   - **Contenido decidido**: hoja 1 = tabla resumen, una fila por servidor del cliente (temperatura
     CPU/GPU promedio del día + semáforo, uso de disco por punto de montaje + semáforo, cámaras
     totales/OK/con falla); hoja 2 en adelante = una sección por servidor **que tenga al menos una
     cámara en falla** (los sanos no generan hoja), con el detalle de esas cámaras (estado, motivo).
   - **Reglas de "falla" para el detalle** (ROADMAP.md, sección 2.7 para el semáforo): 🔴 rojo y
     🟣 morado siempre cuentan, igual que una cámara sin respuesta ese día (`.log` del servidor,
     sección 3) mostrada también en rojo con su motivo real (ej. "Puerto 80 Timed out [111]"); 🟡
     ámbar solo cuenta desde el 3er día seguido (`dias_no_concluyente_consecutivos`, ver Fase 3);
     🔵 base desactualizada no cuenta (ya es un estado "en proceso", alguien ya lo marcó).
   - **Datos de servidor (CPU/GPU/disco) vienen de `Monit_Servers_V2`** (proyecto hermano, otra
     base de datos en el servidor DEVELOP) -- sin tocar ni importar ese proyecto, solo consumiendo
     su API ya expuesta en `http://develop:8000` (`monit_client.py`). Hallazgos/decisiones:
     - El puerto de Postgres de `Monit_Servers_V2` **no está publicado** en su `docker-compose.yml`
       (por diseño, red interna de Docker) -- se descartó la conexión directa a esa BD.
     - Su API no tiene un endpoint de "máximo del día" (`/historico` da **promedio**, no máximo) --
       **decidido usar promedio** en vez de agregar un endpoint nuevo a ese proyecto o exponer su
       base de datos. Para CPU/GPU se toma el promedio del **sensor más caliente** de ese
       componente ese día (no el promedio entre sensores, para no diluir un núcleo/GPU puntual).
     - Uso de disco: **último valor** (no máximo del día), uno por punto de montaje -- ya viene con
       semáforo calculado por la propia API (`/disco/historico`).
     - Los nombres de servidor **no siempre coinciden en mayúsculas/minúsculas** entre los dos
       proyectos (ej. `APIMAN-FASE1` en Plant_Report vs `apiman-fase1` en Monit_Servers_V2) --
       se cruzan normalizando a mayúsculas.
     - Cobertura incompleta: un servidor que no existe en `Monit_Servers_V2` (o sin lecturas ese
       día) muestra "Sin datos" en gris, sin bloquear el resto del reporte.
   - **Módulos nuevos**: `reporte_ejecutivo.py` (construye el PDF, puro -- no sabe nada de bases de
     datos, recibe `ResumenServidor` ya armado; permite generar un PDF de prueba con datos
     inventados sin tocar ninguna BD real, ver `scripts/mock_reporte_ejecutivo.py`), `monit_client.py`
     (cliente HTTP de solo lectura hacia la API de Monit_Servers_V2), `datos_reporte.py` (arma los
     `ResumenServidor` consultando `perfil_camara`/`historial_comparacion` + `monit_client.py`, y
     dispara `construir_pdf()` una vez por cliente). Variable de entorno nueva: `MONIT_API_URL`.
     Salida (decidido 21/10/2026, configurable): `REPORTES_ROOT/<Cliente>/<DDMMYYYY>_<Cliente>.pdf`
     (formato de fecha corregido 22/10/2026 -- día primero, no año, para que se lea bien de un
     vistazo en el explorador de archivos) -- `REPORTES_ROOT` es variable de entorno nueva, mismo
     patrón que `CHECK_PLANTS_ROOT`/
     `IMAGE_BASE_ROOT`/`CONFIG_BASE_ROOT`.
   - Probado end-to-end contra datos reales de producción (BD + API viva de Monit_Servers_V2,
     fecha 02/10/2026 del sandbox): 3 PDFs generados (AbInBev 12 hojas, Api_Manzanillo, Pemex),
     con temperaturas/disco reales de `QLYMSPROD01`/`QLYMSPROD02` (únicos con monitoreo completo
     ese día) y "Sin datos" correctamente para el resto.
   - **Decidido (21/10/2026)**: el `resumen_[fecha].log` por cliente **no** se incorpora a este
     reporte -- el reporte ejecutivo ya construye su propio resumen desde la base de datos (más
     confiable y detallado: semáforo, motivos, observaciones), y parsear un formato de texto
     adicional solo duplicaría información que el reporte ya cubre con datos propios. Ese log queda
     como referencia humana independiente, fuera de este repo.
   - Resuelto por la Fase 5: los destinatarios de cada PDF (incluida Gerencia de Operaciones) se
     configuran por cliente en `.env` (`REPORTE_DESTINATARIOS_<CLIENTE>`).

5. **Enviar correo con el reporte (implementado 21/10/2026)**
   Enviar por correo el PDF generado en la Fase 4 a las personas designadas para recibirlo.
   - Decidido: el correo debe llevar la estructura/identidad de la empresa (firma, pie de página
     corporativo, etc.), no un correo genérico sin formato.
   - **Decidido — un correo por cliente**, con **todos sus destinatarios juntos en "Para"** (no un
     correo por destinatario) y el PDF de ese cliente adjunto.
   - **Decidido — destinatarios en `.env`, por cliente**: `REPORTE_DESTINATARIOS_<CLIENTE>`
     (nombre normalizado a mayúsculas, ej. `REPORTE_DESTINATARIOS_API_MANZANILLO`), con
     `REPORTE_DESTINATARIOS_DEFAULT` como respaldo si un cliente nuevo todavía no tiene su propia
     variable — así nunca se queda sin enviar nada por simple falta de configuración. Por ahora
     todos apuntan a los mismos 2 correos (`imedina@quantumlabs.ai`, `imkuri@yahoo.com`).
   - **Decidido (22/10/2026) — valor especial `NINGUNO`**: dejar `REPORTE_DESTINATARIOS_<CLIENTE>`
     vacío **no** evita el envío -- un string vacío también cuenta como "no configurado" y cae al
     default (confusión real reportada por el usuario). Para que a un cliente específico de verdad
     no se le mande nada (ej. `C5i_Colima`, sin correr todavía), se le pone el valor literal
     `NINGUNO` (sin importar mayúsculas/espacios) -- `correo.enviar_reportes()` lo reporta como
     "omitido" en vez de como una falla, y ni siquiera abre el PDF de ese cliente.
   - **Bug encontrado y corregido el mismo día**: el sentinel solo se revisaba sobre la variable
     específica del cliente, no sobre el valor ya resuelto. Si se ponía
     `REPORTE_DESTINATARIOS_DEFAULT=NINGUNO`, un cliente sin variable propia terminaba con
     `["NINGUNO"]` como destinatario -- intentaba mandarle un correo real a la dirección literal
     "NINGUNO", que fallaba en el envío (se reportaba como `FALLÓ`, no como "omitido"). Corregido:
     el sentinel se revisa sobre el valor final (venga de la variable específica o del default), no
     solo sobre la específica.
   - **Decidido — SMTP**: Google Workspace (`imedina@quantumlabs.ai`) vía `smtp.gmail.com:587` +
     STARTTLS, con **App Password** (no la contraseña normal de la cuenta -- requiere verificación
     en 2 pasos activada). Cuenta y contraseña en `.env` (`SMTP_USER`/`SMTP_APP_PASSWORD`), nunca en
     el código, para poder cambiarlas sin tocar nada más.
   - **Decidido — plantilla en `.env`**: `REPORTE_ASUNTO` ("Informe de plantas [Cliente]") y
     `REPORTE_CUERPO` (multilínea, valor entre comillas con saltos de línea reales -- `python-dotenv`
     sí los conserva así), ambos con `[Cliente]`/`[cliente]` sustituido por el nombre real al armar
     cada correo.
   - **Decidido — firma**: tarjeta HTML (logo de Quantum Labs sobre fondo negro + datos de
     contacto de Ismael Medina) debajo del cuerpo del correo. El logo se reutiliza
     (`assets/QuantumLab-Logo-01.png`, fondo transparente) sobre una celda con fondo negro en el
     HTML -- no hizo falta un archivo nuevo. Se embebe inline vía `Content-ID` (no una imagen
     remota: varios clientes de correo bloquean imágenes externas por default).
   - **Decidido — disparo**: pregunta aparte después de generar el reporte ("¿Enviar los reportes
     por correo? (s/n)"), no la misma pregunta que genera el PDF -- permite revisar el PDF antes de
     que llegue a los destinatarios. En `--sin-interaccion`, automático (sin preguntar), igual que
     la generación del reporte.
   - **Manejo de fallos decidido**: el envío de un cliente no bloquea a los demás (son independientes);
     1-2 reintentos ante errores transitorios (timeout, conexión rechazada) antes de desistir; el PDF
     ya quedó guardado en disco pase lo que pase, así que un fallo de correo nunca pierde trabajo
     (se puede reenviar a mano); resumen claro en consola de qué se envió y qué falló, sin tabla
     nueva en la BD por ahora (se puede agregar después si hace falta auditoría).
   - **Módulo nuevo**: `correo.py` (`enviar_reportes()`), recibe `{cliente: ruta_pdf}` de
     `datos_reporte.generar_reportes_del_dia()` y regresa `[(cliente, éxito, motivo_si_falló), ...]`.
     Variables de entorno nuevas: `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_APP_PASSWORD`,
     `REPORTE_ASUNTO`/`REPORTE_CUERPO`, `REPORTE_DESTINATARIOS_*`.
   - Probado: construcción completa del mensaje verificada (asunto con cliente sustituido, cuerpo +
     firma con el `cid` del logo embebido correctamente, PDF adjunto) y el camino de fallo
     verificado end-to-end (con `SMTP_APP_PASSWORD` todavía vacío, falla de forma controlada tras
     los reintentos, sin tronar el programa).
   - Pendiente: `SMTP_APP_PASSWORD` real (lo genera el usuario en su cuenta de Google -- requiere
     verificación en 2 pasos activada) para probar un envío real de punta a punta.

## Observaciones por cámara (pedido 03/10/2026)

Las cámaras deberían tener un **espacio de observaciones** — notas de contexto humano (ej. "cámara
descompuesta, esperando repuesto", "se reorientó a propósito por una remodelación", "el camión de
este patio es permanente, no es un falso positivo") que luego aparezcan en el reporte ejecutivo
(Fase 4). La diferencia con el semáforo de estados (sección 2.7) es que esto no es un veredicto
automático ni el resultado de una comparación — es contexto libre que alguien agrega a mano para
explicar algo que los números solos no cuentan.

- Decidido: la observación vive ligada a la **cámara**, no a una corrida/día puntual — tiene que
  sobrevivir entre corridas para que el reporte la recoja cuando corresponda.
- Decidido: el lugar lógico para guardarla es la **base de datos** (Fase 3), no un archivo aparte —
  mismo razonamiento que `perfil_camara`: necesita sobrevivir, ser consultable por cámara, y
  alimentar Fase 4 sin depender de que exista un archivo específico ese día.
- **Decidido (21/10/2026) — esquema**, zanjando las dos preguntas de abajo: bitácora, no nota única
  que se sobrescribe — varias observaciones pueden coexistir por cámara a lo largo del tiempo, y
  "borrar" una la cierra en vez de eliminarla (no se pierde el contexto de por qué algo se ignoró en
  su momento):

  ```sql
  CREATE TABLE observacion_camara (
      id          BIGSERIAL PRIMARY KEY,
      camara_id   INT NOT NULL REFERENCES perfil_camara(id),
      texto       TEXT NOT NULL,
      creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
      resuelta_en TIMESTAMPTZ   -- NULL mientras sigue vigente
  );
  ```

  Implementado en `migrations/0003_observacion_camara.sql` + `db.crear_observacion()`.
- **Decidido (21/10/2026) — dónde se capturan, por ahora**: un campo de texto opcional en
  `ventana_revision.py`, justo al resolver un `REVISAR` (junto a los botones Bien/Mal/Base
  Desactualizada) — `pedir_revision()` ahora regresa `(accion, observacion)` en vez de solo
  `accion`, y `main.py` llama a `db.crear_observacion()` si se escribió algo.
  - **Limitación aceptada a propósito**: una cámara que no pasa por esa ventana (ya confirmada en
    🔴 rojo, o en 🟡 ámbar -- ninguna de las dos reabre `ventana_revision`, ver sección 2.7) no
    tiene hoy forma de recibir una nota nueva ni de cerrar una existente. No se resuelve en este
    repo: **habrá un programa de administración aparte** (desarrollo nuevo, fuera de este alcance)
    para editar cámaras/observaciones con más libertad, entre otras funciones todavía sin definir.
  - Queda pendiente, para cuando exista ese programa de administración: cerrar observaciones
    (`resuelta_en`) y anotar cámaras en rojo/ámbar sin pasar por `ventana_revision`.

## Preguntas generales de ejecución

- Decidido (03/10/2026): **corre en la máquina local del usuario** (la misma donde se está
  desarrollando), no en un servidor aparte.
- Decidido (03/10/2026): **se dispara manualmente**, después de que el programa externo de revisión
  ya haya descargado los datos de los servidores (offline) ese día. La automatización completa del
  pipeline (tarea programada, servicio, para que todo corra solo de principio a fin) queda pendiente
  para más adelante — no es parte del alcance actual.
- Resuelto en la práctica, no por decisión explícita: es un **híbrido**. La corrida en sí es CLI
  (`main.py`), pero los pasos que requieren juicio humano ya tienen su propia ventana —
  `ventana_revision.py` (revisar cámaras dudosas) y `ventana_bases.py` (reemplazar bases
  desactualizadas) — en vez de resolverse por línea de comandos.
- **Decidido (21/10/2026) — bandera `--cliente`**: al empezar a correr contra datos reales (varios
  clientes a la vez bajo `CHECK_PLANTS_ROOT`), hacía falta poder acotar una corrida a un solo
  cliente para probar o revisar sin tocar a los demás. `main.py --cliente AbInBev` filtra desde el
  recorrido de archivos (nombre exacto de la carpeta de cliente) -- sin la bandera, procesa todos
  los clientes encontrados esa fecha, igual que antes. `main.py --help` documenta todas las
  banderas (`--sin-interaccion`, `--cliente`, `--fecha`).
  - **Bug real encontrado y corregido el mismo día**: `--cliente` solo filtraba qué cámaras se
    comparaban -- el paso de generar/enviar el reporte (`generar_reportes_del_dia()`) seguía
    consultando "qué clientes tienen datos hoy" en la base de datos sin filtrar. Si ya había otro
    cliente persistido ese mismo día (de una corrida anterior), `--cliente AbInBev` terminaba
    generando **y enviando por correo** el reporte de ese otro cliente también, sin haberlo pedido
    -- pasó de verdad, reenvió un correo real de `Api_Manzanillo`. Corregido: `cliente` ahora se
    pasa hasta `generar_reportes_del_dia()`, acotando todo el proceso (comparación, reporte y
    correo), no solo la comparación.
- **Decidido (21/10/2026) — bandera `--fecha`**: `main.py` siempre preguntaba la fecha por
  `input()`, sin importar `--sin-interaccion` -- una corrida verdaderamente desatendida (ej. tarea
  programada, sin nadie frente a la terminal) se quedaría esperando esa respuesta para siempre.
  `main.py --fecha h` (o una fecha exacta `ddmmyy`) evita la pregunta; si se omite, sigue
  preguntando en la terminal como antes.
- **Fuera de alcance (anotado 21/10/2026)**: habrá un **programa de administración aparte**
  (desarrollo nuevo, no este repo) para editar cámaras, cerrar/editar observaciones, y otras
  funciones todavía sin definir. Cualquier pendiente de este proyecto que solo tenga sentido
  resolver desde una pantalla de edición libre (no desde el flujo diario de `main.py`) debe quedar
  anotado como dependiente de ese programa futuro, no implementarse aquí.

## Estado

- [x] Fase 1 implementada para AXIS/HIKVISION/VIVOTEK/DAHUA (comparación de JSON de configuración) —
      DAHUA agregado 03/10/2026 contra un dump real (cámara ITC de prueba), **provisional** hasta
      contrastarlo con una cámara "normal" del parque (posiblemente martes 06/10/2026)
- [x] Fase 1: zoom — pedido explícitamente (03/10/2026) que se vigile en **todas** las marcas, no
      solo HIKVISION. Estado real por marca tras revisar dumps reales:
      - HIKVISION: campo agregado (`PTZStatus.AbsoluteHigh.absoluteZoom`), verificado en vivo con la
        cámara física — **bloqueado en la otra mitad**: falta que el programa externo de revisión
        descargue ese endpoint, fuera del alcance de este repo
      - VIVOTEK: campo agregado (`videoin.c0.zoomratiodisplay`), visto en dump real pero sin
        verificar con un zoom real (la cámara de muestra no es motorizada)
      - AXIS: **no se pudo agregar** — el dump real solo trae capacidades estáticas (¿puede hacer
        zoom?), no el valor en vivo; ese dato ni siquiera está en la descarga actual. Pendiente de una
        cámara AXIS motorizada real para probarlo
      - DAHUA: campo encontrado y **verificado en vivo con cámara real** (03/10/2026) —
        `devVideoInput.cgi?action=getFocusStatus&channel=0` → `status.Zoom`, confirmado con un cambio
        de zoom real hecho a mano (0.0 → 0.144 → 0.0 exacto al regresarlo). Mismo nivel de evidencia
        que HIKVISION. Falta todavía: confirmar que la sección curada de Fase 1 (`Network`/
        `VideoColor`/`Encode`) se ve igual en una cámara DAHUA "normal" del parque, no solo en la ITC
        de prueba (ver detalle en la sección de Fase 1 arriba)
- [x] Fase 2: base de imágenes curada (91 de 143 cámaras; el resto se creará sola)
- [x] Fase 2: diseño de dos señales + guarda de inliers validado en principio (features+homografía
      como señal principal, diff de píxeles como secundaria) — **umbrales a recalcular** (ver abajo)
- [x] Fase 2: ventana de revisión diseñada (3 botones, bloqueante, con `--sin-interaccion`) —
      resuelve también el "aceptar nueva base" de Fase 1
- [x] Fase 2: script de captura para la cámara física listo y probado contra la HIKVISION real
      (`Test/Camara_Fisica/capturar.py`)
- [x] Fase 2: **Experimento 4 (30/09/2026)** — el texto sobreimpreso secuestra la homografía y
      produce falsos negativos (cámara movida 65-88 px, reportado como 0.1 px). Invalida los
      umbrales de los Experimentos 1-3. Enmascarar solo las esquinas ayuda pero no alcanza en
      cámaras sin textura (ORB no encuentra estructura repetible en concreto liso).
- [x] Fase 2: **Experimento 5 (02/10/2026)** — piso de ruido validado sobre 175 capturas / 24h
      reales sin huecos, con el texto enmascarado: máximo 1.71 px de día, 0.36 px de noche IR,
      transiciones de régimen nunca sobre 1.89 px. Confirma con datos reales (no solo la muestra
      chica de producción) que el umbral de 0.25-0.5% del ancho tiene margen de sobra (~3x sobre el
      peor ruido real, ~30x sobre un movimiento real medido).
- [x] Fase 2: **Experimento 6 (02/10/2026)** — correlación de fase rescata las cámaras sin textura
      donde ORB falla, y resistió la prueba de estrés de ocupación agresiva (hasta 85% tapado, y los
      casos reales más extremos conocidos) sin dar nunca un número falso con confianza alta. Diseño
      en cascada decidido: ORB+RANSAC primero, correlación de fase como repuesto filtrado por
      confianza
- [x] Fase 2: **Experimento 7 (02/10/2026)** — minando 110 pares reales de 8 cámaras a lo largo de
      7 meses se encontró un modo de falla más grave: patrones repetitivos (reflectantes de
      pavimento, columnas idénticas) engañan a ORB y a correlación de fase **al mismo tiempo**,
      pasando ambos umbrales de confianza con un número falso (86-97 px en cámaras que no se
      movieron). El diseño cascada-solo-si-falla no protege contra esto porque a veces los métodos
      se equivocan igual en vez de corregirse mutuamente.
- [x] Fase 2: **Experimento 7b (02/10/2026)** — validado: correr ORB y correlación de fase siempre
      (no en cascada) y nunca devolver `OK` si alguno excede el umbral de movimiento, sin importar
      qué tan "confiable" se vea, evita que los 3 casos problemáticos del Experimento 7 pasen como
      `OK` falso. Pendiente, sin resolver: un primer intento de detectar la estructura periódica
      directamente (FFT manual) tenía un bug y se descartó — hace falta rediseñarlo como
      autocorrelación de una sola imagen
- [x] Fase 2: **Experimento 8 (03/10/2026)** — batería completa con la HIKVISION física: golpe y
      regreso da 118-420 px de residuo real (todo correctamente `REVISAR`); obstrucción y objeto se
      comportan como se esperaba; el zoom es un punto ciego confirmado de la geometría (0.2-0.65 px,
      `OK`, y tampoco lo cubre Fase 1 hoy — ver pendiente ahí); y la relación grados↔píxeles real
      resultó ~10x mayor que la simulada por el paralaje de objetos cercanos, reforzando con datos
      la necesidad del perfil por cámara de Fase 3
- [x] Fase 2: **Experimento 9 (03/10/2026)** — Experimentos 1 y 3 rehechos con esquinas enmascaradas.
      Confirma que el diseño nunca miente, pero revela que varias cámaras que parecían fáciles
      (`ZAC_E1p`, `ZAC_P1p`, `MED_B03`) sacaban su confianza del texto sobreimpreso, no de la escena
      real — con la corrección caen a `NO_CONCLUYENTE`. La fracción de cámaras medibles por ORB solo
      es menor de lo reportado en el Experimento 3 original; el umbral de confianza de fase (0.15)
      queda marcado como pendiente de recalibrar con muestra más grande
- [x] Fase 2: **módulo implementado (03/10/2026)** — `image_compare.py` + integrado en `main.py`
      junto a Fase 1, en la misma corrida por cámara. Probado end-to-end contra las 210 cámaras del
      sandbox (0 errores): 173 `OK`, 28 `NO CONCLUYENTE`, 8 `REVISAR`, 2 `SIN ARCHIVO` (config o
      imagen faltante ese día, tolerado de forma independiente por cada fase). Confirma en
      producción lo que predijeron los experimentos: `ZACATECAS/A2p` cae en `NO CONCLUYENTE`
      (la cámara sin textura real identificada en el Experimento 9), y las cámaras que quedaron
      pendientes en la curación manual (ej. `MEDELLIN/B04-B06`) generan su base sola, sin haber
      necesitado curación a mano — confirma el Experimento 3. Umbral de movimiento detrás de
      `umbral_para()` (hoy regresa el global, listo para engancharse a `perfil_camara` sin tocar el
      resto del módulo cuando exista Fase 3). Variable de entorno nueva: `IMAGE_BASE_ROOT`.
      Dependencias nuevas en el Pipfile principal: `opencv-python`, `numpy`.
- [x] Fase 2: ventana de revisión conectada al flujo real (`main.py`), con bandera
      `--sin-interaccion`; botón "Base Desactualizada" marca la base en vez de sustituirla de
      inmediato (ver sección 2.8 — evita hornear un camión en la base)
- [x] Fase 2: `ventana_bases.py` (03/10/2026) — ventana aparte para reemplazar bases marcadas como
      desactualizadas, eligiendo una imagen limpia desde el explorador de archivos cuando convenga,
      sin depender de la corrida diaria
- [x] Fase 2: `captura.py` (03/10/2026) — en `script/capture_img/` (carpeta independiente, con su
      propio `README.md`, para copiarse a cada servidor sin el Pipenv de Plant_Report). CLI
      `python captura.py <ip> <usuario> <password> <marca>`, guarda en `images/<ip>/<timestamp>.jpg`.
      Las 4 marcas (AXIS/DAHUA/HIKVISION/VIVOTEK) adaptadas de las rutinas ya probadas en producción
      en `Check_Cameras/conf/cameras/`, separadas en un paquete `cameras/` para agregar marcas nuevas
      sin tocar las demás (ver sección 2.8). Única dependencia: `requests` (`pip install requests`,
      no entra al Pipfile principal).
- [x] Fase 2: **primera prueba real contra DAHUA (03/10/2026)** — dos capturas de la misma cámara
      POC (`devVideoInput`/túnel) con 90s de diferencia, corridas por `image_compare.py` sin ninguna
      base curada previa. Resultado: `OK` limpio, con números muy por encima de los umbrales
      (3100 inliers ORB, confianza de fase 0.857, desplazamiento 0.27/0.18 px) — la escena tiene
      mucha textura real (pared, imagen religiosa, macetas). Primera confirmación de que el pipeline
      de Fase 2 funciona igual de bien contra una marca distinta a HIKVISION.
- [ ] Fase 2: recalibrar el umbral de confianza de fase (0.15, pendiente desde el Experimento 9) y
      el umbral de movimiento (0.25%) con más datos reales de producción
- [ ] Coordinar con quien mantenga el programa externo de revisión para agregar
      `PTZCtrl/channels/1/status` a la descarga de HIKVISION (bloqueante para que el zoom de Fase 1
      sirva de algo en la práctica)
- [x] Fase 3: decidido (21/10/2026) eliminar el paso intermedio de "actualización del log" y
      fusionarlo con la persistencia en base de datos — sin archivo intermedio (ni reescribir el
      `.log` original ni generar uno nuevo), escritura directa a Postgres cámara por cámara (incluye
      el veredicto humano), con upsert por día para tolerar corridas repetidas (ver sección 3 arriba)
- [x] Fase 3: **base de datos creada y módulo implementado (21/10/2026)** — Postgres real
      (`plant_report`), esquema de `perfil_camara`/`historial_comparacion` aplicado vía
      `migrate.py` (corredor simple de migraciones, `migrations/0001_init.sql`). Nuevo `db.py`:
      `obtener_camara()` (upsert de catálogo), `guardar_resultado()` (upsert de
      `historial_comparacion` + máquina de estados del semáforo), `camaras_con_base_desactualizada()`
      / `marcar_base_reemplazada()` para `ventana_bases.py`. Conectado a `main.py`, que ahora
      persiste cada cámara justo después de resolverla (no en lote). El marcador de archivo
      `.desactualizada` de la sección 2.8 se eliminó de `image_compare.py` y migró por completo a
      `perfil_camara.estado_actual`; `ventana_bases.py` ya consulta la BD en vez de escanear disco.
      Probado end-to-end contra las 210 cámaras del sandbox (209 con `.jpg`/`.json` ese día):
      corrida repetida sobre la misma fecha confirma el upsert (209 filas, sin duplicar), y una
      prueba aislada de la máquina de estados confirma rojo → no se re-pregunta → recupera solo a
      verde cuando la comparación vuelve a dar `OK` (regla de la sección 2.7).
- [x] Fase 3: confirmado (21/10/2026) que `plant_report` en `localhost:5432` **es** la base de datos
      definitiva, no una de pruebas — el programa solo vive en esta máquina (ver "Preguntas generales
      de ejecución"), así que no hay credenciales distintas que resolver para producción.
- [x] Fase 3: **ingesta del `.log` por servidor (21/10/2026)** — nuevo `log_parse.py`
      (`parsear_log_servidor()`) y columnas `log_ip`/`log_estado`/`log_motivo`/`tiempo_proceso_seg`
      en `historial_comparacion` (`migrations/0002_log_servidor.sql`). Responde a la pregunta de si
      el `.log` se lee desde el principio: **ahora sí** — `_camaras_del_dia()` en `main.py` ya no
      descubre cámaras solo por la existencia de `.jpg`/`.json`, también lee el `.log` de cada
      servidor y agrega las cámaras que fallaron por completo (ej. timeout de puerto, que no genera
      ni `.jpg` ni `.json` y antes las dejaba invisibles para todo el programa). `SIN ARCHIVO` ahora
      muestra el motivo real cuando está disponible (ej. `SIN ARCHIVO (Puerto 80 Timed out [111])`).
      Tolera ambos finales de línea (LF/CRLF) y, hallazgo nuevo de esta prueba, **ambas
      codificaciones** — AbInBev viene en UTF-8, API-MANZANILLO en cp1252 (se ve en los acentos de
      "Imagen cámara"/"Configuración" en sus líneas `ERROR`); `log_parse.py` intenta UTF-8 y cae a
      cp1252 si falla. Probado contra los `.log` reales del sandbox: sobre la fecha 22/09/2026, las
      cámaras con resultado pasaron de 144 a 175 al incluir las que fallan por completo (31 con
      `log_estado = 'ERROR'`, con motivos reales: `Timed out [111]`, `Connection error [199]`,
      `Service Unavailable [503]`); upsert por día confirmado estable tras una segunda corrida.
- [x] **Observaciones por cámara implementadas (21/10/2026)** — `observacion_camara`
      (`migrations/0003_observacion_camara.sql`) + `db.crear_observacion()`. Campo de texto opcional
      agregado a `ventana_revision.pedir_revision()` (ahora regresa `(accion, observacion)`), junto
      a los tres botones; `main.py` guarda la nota si no quedó vacía. Probado de punta a punta
      (click simulado + verificación directa en Postgres). Limitación aceptada: cámaras en rojo/ámbar
      no pasan por esa ventana, así que no pueden recibir ni cerrar notas todavía — queda para el
      programa de administración aparte (ver nota de alcance abajo).
- [x] **Fase 4 implementada (21/10/2026)** — PDF ejecutivo por cliente, al final de `main.py`;
      pregunta en consola antes de generarlo en modo interactivo, automático en `--sin-interaccion`. `reporte_ejecutivo.py` (construcción pura del PDF) + `monit_client.py` (API de
      Monit_Servers_V2 para CPU/GPU/disco) + `datos_reporte.py` (arma los datos desde
      `perfil_camara`/`historial_comparacion` + Monit). Probado contra datos reales de producción
      (ver sección 4 arriba para el detalle completo: reglas de falla, promedio vs. máximo,
      normalización de nombres, cobertura incompleta de Monit_Servers_V2).
- [x] Fase 4: decidido (21/10/2026) que el `resumen_[fecha].log` por cliente **no** se incorpora al
      reporte ejecutivo -- queda como referencia humana independiente (ver sección 4 arriba)
- [x] **Fase 5 implementada (21/10/2026)** — `correo.py`, un correo por cliente (todos sus
      destinatarios juntos en "Para", PDF adjunto), SMTP de Google Workspace con App Password,
      plantilla y destinatarios por cliente en `.env`, firma HTML con el logo reutilizado (sin
      archivo nuevo). Disparo con pregunta propia en consola (automático en `--sin-interaccion`).
      Manejo de fallos: independiente por cliente, con reintentos, sin perder el PDF ya generado.
      Probado end-to-end salvo el envío real (falta que el usuario genere su App Password de Google).
- [x] **Mejoras al reporte PDF (21/10/2026)** -- a partir de lo visto corriendo
      `backfill_reportes.py` contra octubre/2026 real:
      - **Orden de servidores**: alfabético por nombre de servidor en general, con un caso especial
        para AbInBev (mezcla prefijos `QLYMSPROD`/`QBYMSPROD`; el orden que importa es el de los
        últimos dígitos -- `01, 02, ..., 11` -- no el alfabético, que pondría `QBYMSPROD07` antes
        que `QLYMSPROD01` por la "B" vs. "L"). Los demás clientes siguen alfabético simple.
      - **Columna de disco(s)**: nombre del punto de montaje a la izquierda, porcentaje a la
        derecha (antes todo centrado en una sola línea) -- más fácil de comparar de un vistazo.
      - **"Estado" descriptivo, separado de "Motivo"**: antes "Estado" solo mostraba el color
        ("Rojo"/"Morado") y el motivo técnico venía concatenado en un solo texto. Ahora "Estado"
        trae una etiqueta legible y "Motivo" el detalle técnico puro, cada uno en su columna.
      - **Tres niveles dentro de "cámara sin respuesta"** (antes un solo letrero genérico para
        cualquier error del `.log`, lo cual escondía diferencias de gravedad reales -- detectado al
        ver `AD1p` con "Configuración Unknow error" y `AD1r2` con "Puerto 80 Timed out" mostrando
        el mismo letrero): el texto del `.log` siempre empieza con el nombre del paso que falló, así
        que se deriva la etiqueta de ahí --
        - `Puerto 80 ...` → **"Cámara sin respuesta"** (🔴 rojo) -- no contestó en absoluto, nada
          más se intentó.
        - `Imagen IA ...` / `Imagen cámara ...` → **"Imagen no disponible"** (🔴 rojo) -- el puerto
          respondió, solo falló la imagen.
        - `Configuración ...` → **"Configuración no disponible"** (🟡 ámbar, no rojo -- la cámara
          está viva y capturando, es el menos grave de los tres).
        - Cualquier otro texto no previsto → **"Error desconocido"** (🔴 rojo, por si acaso).
      - **Imagen base + actual debajo de cada cámara con discrepancia** (rojo confirmado, morado,
        ámbar -- no para "sin respuesta", ahí no hay "actual" que capturar ese día), con la misma
        cuadrícula guía que ya usa `ventana_revision.py` (ayuda a juzgar a ojo si se movió). La
        imagen base se resuelve con `image_compare.base_path()`; la actual se busca con un glob
        puntual sobre `CHECK_PLANTS_ROOT` para esa fecha exacta (no se guarda la ruta en la BD).
      - Todo verificado con imágenes reales (incluida la cuadrícula renderizando bien en ambos
        casos) antes de darlo por bueno.
- [x] **Primera corrida real de punta a punta (21/10/2026)** — `main.py` completo (sin
      `--sin-interaccion`), fecha de hoy, los 4 clientes reales bajo `CHECK_PLANTS_ROOT` (267
      cámaras AbInBev + Api_Manzanillo encontradas, Pemex/C5i_Colima sin datos ese día, ver nota en
      "Estructura de datos"). Confirmado: persistencia real en Postgres (265 filas en
      `perfil_camara`/`historial_comparacion`, todas en verde), generación del PDF y la pregunta de
      correo respetando "no" sin enviar nada.
- [x] **Ventana de revisión validada en vivo contra la BD real (22/10/2026)** — el usuario corrió
      `main.py` solo (sin mí presente) y resolvió 8 cámaras `REVISAR` de verdad: 7 "Bien" (volvieron
      a verde, confirmado que ya no aparecen como falla al día siguiente) y 1 "Mal"
      (`Api_Manzanillo/API-MANZANILLO/APIMAN-FASE1/PV-OC03`, quedó en rojo, aparece en el PDF como
      "Cámara movida (confirmado)" con sus dos imágenes y la cuadrícula). Cierra el pendiente que
      quedó anotado el día anterior. También contestó "sí" a enviar correo -- llegó sin problema.
      Ninguna de las 8 llevó observación escrita (opcional, no es un problema).
- [x] **Dos ajustes pedidos tras revisar esa corrida (22/10/2026)**:
      - Formato de fecha en el nombre del PDF corregido a `DDMMYYYY` (antes `YYYYMMDD` -- se
        esperaba ver el día primero, no el año, al ojearlo en el explorador de archivos).
      - La ventana de revisión se cierra apenas termina de procesar todas las cámaras, **antes** de
        las preguntas de consola (generar/enviar reporte) -- antes se quedaba abierta sin hacer nada
        mientras la terminal ya esperaba respuesta, y el usuario no se daba cuenta de que el
        programa estaba esperando su interacción (la ventana tapaba la terminal).
- [x] **Bug visual corregido (22/10/2026)**: en el par de imágenes base/actual del detalle de
      fallas, la imagen "Actual" se salía del recuadro derecho -- la celda combinada heredaba el
      relleno (padding) de 6pt de la tabla exterior además de ya estar dimensionada al ancho
      completo, así que terminaba 12pt más ancha que el espacio real disponible. Se le puso
      `LEFTPADDING`/`RIGHTPADDING` en 0 a esa celda en vez de reservarle espacio. Verificado
      regenerando el PDF real del 22/10/2026 (cámara `PV-OC03`, confirmada movida ese día).
- [x] **Banderas de `main.py` renombradas al inglés (22/10/2026)**: pedido explícito del usuario --
      sus demás programas usan nombres de bandera en inglés (`--client`, no `--cliente`), aunque el
      resto de los mensajes/comentarios del proyecto se quedan en español. `--sin-interaccion` →
      `--no-interaction`, `--cliente` → `--client`, `--fecha` → `--date`. Actualizado también en
      `plant_report.ps1` (vive en `Documents/`, fuera de este repo) y en `README.md`.
      - **Detalle encontrado al renombrarlas**: el `-h`/`--help` que agrega `argparse` solo siempre
        sale en inglés ("show this help message and exit"), sin importar el idioma del resto de la
        ayuda -- no hay forma de traducirlo mientras `ArgumentParser` lo agregue él solo. Corregido
        con `add_help=False` + un `-h`/`--help` agregado a mano con su propio texto en español.
- [x] **Bug de orden corregido (22/10/2026)**: en el reporte PDF, la sección "RESUMEN DE SERVIDORES"
      ya ordenaba los servidores de AbInBev correctamente (`_clave_orden_servidor`, por los últimos
      dígitos del nombre), pero las hojas de detalle de cámaras con falla (una por servidor) no
      aplicaban ese mismo orden -- se armaban en el orden alfabético simple que trae la consulta SQL.
      Corregido en `reporte_ejecutivo.py::construir_pdf` ordenando `servidores_con_fallas` con la
      misma `_clave_orden_servidor` antes de generar las hojas de detalle.
- [x] **Nuevo script `generar_reporte.py` (22/10/2026)**: pedido tras un caso real -- el usuario ya
      había hecho la revisión de cámaras con `main.py`, pero no generó el PDF esa corrida. Volver a
      correr `main.py` habría repetido toda la lectura/comparación (aunque las cámaras ya resueltas
      no se vuelven a preguntar). Este script nuevo solo llama a `generar_reportes_del_dia` +
      `enviar_reportes` contra lo que ya está en `perfil_camara`/`historial_comparacion`, sin tocar
      la comparación ni la base de datos más que para leerla. Mismas banderas que `main.py`
      (`--no-interaction`, `--client`, `--date`), mismo patrón de `-h`/`--help` en español. Launcher
      gemelo `generar_reporte.ps1` agregado en `Documents/` junto a `plant_report.ps1`.
- [x] **Duda real que destapó dos huecos del reporte (22/10/2026)**: el usuario notó que en
      `QLYMSPROD01` las "Cámaras totales" (40) no coincidían con "Cámaras OK" (31) + "Cámaras con
      falla" (0) -- faltaban 9. Al investigar, eran cámaras en ámbar con solo 1 día de racha (el
      ámbar nunca contaba como falla hasta el 3er día seguido, pero tampoco contaba como OK) --
      invisibles en el resumen del PDF sin que nada estuviera mal en los datos. Esto llevó a repasar
      **todo** el inventario de estados posibles (`db._siguiente_estado`, estatus de
      `image_compare.py`, el `.log` del servidor) y a dos decisiones de diseño:
      1. **El ámbar ya no se queda esperando para siempre.** Antes, `NO CONCLUYENTE` solo acumulaba
         días (`dias_no_concluyente_consecutivos`) para que el *reporte* lo contara como falla desde
         el 3er día -- pero nunca abría la ventana de revisión, así que una cámara podía quedarse en
         ámbar indefinidamente sin que ningún humano la viera jamás. Ahora, `db._siguiente_estado`
         pasa la cámara a **morado** al llegar a `DIAS_AMARILLO_PARA_REVISION = 3` días seguidos
         -- exactamente igual que un `REVISAR` normal -- y `main.py` fuerza la apertura de la
         ventana de revisión ese mismo día (`fuerza_revision`), obligando a un humano a contestar
         Bien/Mal/Base desactualizada. `datos_reporte.py` ya no necesita la regla "ámbar cuenta
         desde el 3er día" -- nunca llega tan lejos sin convertirse en morado.
      2. **El contador de racha ya no se reinicia por una falla de conexión.** Se encontró de paso:
         si una cámara llevaba 2 días seguidos en ámbar y al 3er día tenía una falla de conexión
         (sin `.jpg` ese día), el contador se reiniciaba a 0 en vez de mantenerse -- retrasando sin
         motivo que se forzara la revisión. Ahora `db.guardar_resultado` congela la racha (ni suma
         ni reinicia) los días sin imagen que comparar, y solo la reinicia a 0 cuando sí hay una
         comparación real que no fue `NO CONCLUYENTE`.
      3. **Nueva columna "No concluyente"** en el resumen del PDF (`reporte_ejecutivo.py`), entre
         "Cámaras OK" y "Cámaras con falla" -- cuenta el ámbar de 1-2 días (ya nunca llega a 3 sin
         convertirse en morado). En ámbar si hay alguna, negro si es 0.
      4. **"Base desactualizada" ahora sí cuenta como falla** (decisión explícita del usuario, pedido
         22/10/2026 -- antes era un estado "en proceso" que no sumaba en ningún lado). Aparece en
         "Cámaras con falla" con la etiqueta "Base de imágenes desactualizada", color azul nuevo
         (`AZUL`) tanto en la celda de estado como en la simbología del pie de la hoja 1. Con esto,
         la suma de OK + No concluyente + Con falla siempre cierra contra "Cámaras totales" -- ya no
         queda ninguna cámara invisible en el resumen.
      Verificado contra la base de datos real del 22/10/2026: las 11 filas de servidores de AbInBev
      reconciliaron exactamente (`camaras_ok + camaras_no_concluyentes + len(fallas) ==
      camaras_totales` en los 11 casos), y `QLYMSPROD01` pasó de mostrar 40/31/0 a 40/31/9/0.
- [x] **Bug real encontrado al usar `generar_reporte.py` en producción (22/10/2026)**: el usuario
      corrió `generar_reporte.py --date h --client AbInBev` y el programa reventó por completo con
      un `ConnectTimeoutError` hacia `develop:8000` -- la API de `Monit_Servers_V2` (o la VPN hacia
      ella) no estaba disponible en ese momento. `monit_client.py` no atrapaba ningún error de red:
      ni `_servidores_monit()`, ni `temperaturas_promedio_dia()`, ni `uso_disco_actual()` -- solo
      manejaban el caso "el servidor no existe en Monit_Servers_V2", nunca "Monit_Servers_V2 no
      responde". Esto contradecía lo que ya decía el propio README ("si un servidor no existe ahí,
      el reporte muestra 'Sin datos' sin bloquear nada") -- el reporte ejecutivo nunca debió depender
      de que esa API estuviera arriba. Corregido envolviendo las tres funciones en
      `try/except requests.exceptions.RequestException`, regresando "Sin datos" (igual que cuando el
      servidor no existe) en vez de propagar la excepción, con un aviso impreso en consola para que
      quede claro por qué faltan esos datos. `_servidores_monit()` sigue cacheada con `lru_cache`, así
      que si Monit_Servers_V2 ya falló una vez en la corrida, no se reintenta 10s por cada servidor
      del reporte. Verificado repitiendo el comando real del usuario con la API sigue caída: ya no
      truena, genera el PDF con "Sin datos" en CPU/GPU/disco y envía el correo con normalidad.
- [x] **Bug real: `--client` con mayúsculas distintas generaba un PDF vacío (22/10/2026)**: el
      usuario corrió `generar_reporte.py --date h --client ABINBEV` (el cliente real está guardado
      como `AbInBev`) y el PDF se generó sin problema aparente, pero completamente vacío -- sin
      servidores ni cámaras. Causa: `datos_reporte.py` usa el valor de `--client` directo en
      consultas SQL (`WHERE p.cliente = %s`), y Postgres compara texto **distinguiendo mayúsculas**
      por defecto -- no había ninguna fila con `cliente = 'ABINBEV'`, así que la consulta no
      encontraba nada, pero el código seguía adelante y escribía el PDF igual (con una lista de
      servidores vacía) en vez de detectar que ese cliente no existe. (`main.py` no sufre esto
      porque filtra por carpetas de archivos, y Windows resuelve rutas sin importar mayúsculas --
      "funciona por accidente" ahí, pero la base de datos sí distingue.)
      Corregido con `datos_reporte._resolver_cliente()`: busca el cliente con
      `LOWER(p.cliente) = LOWER(%s)` y regresa el nombre real tal cual está guardado (`AbInBev`),
      que es el que se usa después para la carpeta del PDF, el título, y las demás consultas.
      `generar_reportes_del_dia()` ahora regresa `{}` (sin generar ningún PDF) si el cliente
      realmente no existe para esa fecha, en vez de un PDF vacío -- `generar_reporte.py` ya tenía el
      mensaje "No se encontraron datos..." para ese caso, solo le faltaba que la función de abajo
      dejara de generar el PDF vacío antes de llegar ahí.
- [x] **Bug real: un `.jpg` dañado tumbaba toda la corrida (26/10/2026)**: `main.py` crasheó con
      `OSError: broken data stream when reading image file` justo al abrir la ventana de revisión
      para la cámara `CA` de `QLYMSPROD01` (la primera vez que le tocaba revisión). Causa raíz: la
      base de esa cámara (`CA.jpg`) está genuinamente dañada -- confirmado abriéndola con Pillow
      directo. No es el aviso inofensivo de "Corrupt JPEG data" ya investigado antes
      (`diagnostico_jpeg.py`, 0 fallas reales de 2873 imágenes con OpenCV) -- OpenCV sí la tolera lo
      suficiente para comparar (por eso `CA` llevaba días en verde sin que nadie notara el problema),
      pero Pillow es más estricto y revienta al querer **mostrarla** en la ventana de revisión o en
      el PDF. `_cargar_para_tk()` (`ventana_revision.py`) e `_imagen_proporcional()`
      (`reporte_ejecutivo.py`) abrían la imagen con Pillow sin ningún manejo de error -- un solo
      archivo dañado detenía toda la corrida, con el humano sin poder contestar nada.
      Corregido con una función compartida, `_abrir_imagen_segura()` (`ventana_revision.py`, también
      usada desde `reporte_ejecutivo.py`): si Pillow no puede abrir el archivo, regresa `None` en vez
      de propagar la excepción, con un aviso impreso en consola. La ventana de revisión muestra un
      marcador gris ("Imagen no disponible (archivo dañado)") en vez de la imagen y deja que el
      humano decida igualmente con el diagnóstico numérico; el PDF muestra el mismo texto como celda
      en vez de la imagen, sin tumbar el resto del reporte. Verificado directo contra el archivo real
      dañado en ambos puntos (ventana y PDF) -- ya no truena.
      **Pendiente para el usuario**: la base de `CA` (`AbInBev/ZACATECAS/QLYMSPROD01/CA.jpg`, bajo
      `IMAGE_BASE_ROOT`) sigue dañada en disco -- no se tocó, solo se evitó que tumbara el programa.
      Lo más simple es borrar ese archivo a mano: la próxima corrida la vuelve a crear sola a partir
      de la imagen de ese día (`image_compare.compare_camera_image`, estado "BASE CREADA"). El usuario
      ya borró `CA.jpg` por su cuenta.
- [x] **Reversión de la corrida parcial del 26/10/2026 (tras el crash de `CA.jpg`)**: el usuario pidió
      borrar de la base toda la revisión de ese día para poder correr `main.py` de nuevo desde cero.
      104 cámaras (10 servidores de AbInBev) ya se habían guardado en `historial_comparacion` antes
      del crash, 20 de ellas con veredicto humano. Borrar solo esas filas **no bastaba**: el estado
      vivo en `perfil_camara` (`estado_actual`, `dias_no_concluyente_consecutivos`,
      `n_confirmaciones_humanas`) ya había sido actualizado por esa corrida parcial para esas mismas
      104 cámaras -- volver a correr el día sin revertir ese estado habría sumado un día extra al
      contador de ámbar para varias cámaras (doble conteo), entre otras inconsistencias. Antes de
      borrar nada, se hizo un *dry run* recalculando el estado vivo correcto de cada cámara afectada
      reproduciendo `db._siguiente_estado()` sobre todo su historial **previo** al 26/10 (excluyendo
      ese día) -- encontró que **26 de las 104** habrían quedado con un estado vivo incorrecto si solo
      se borraba el historial (ej. `A2p` habría quedado en verde/0 en vez de su verdadero estado
      previo, ámbar/2 días). Se aplicó todo en una sola transacción: `UPDATE perfil_camara` con el
      estado recalculado para las 104 cámaras + `DELETE FROM historial_comparacion WHERE fecha =
      CURRENT_DATE`. Verificado después: 0 filas de hoy, valores recalculados consistentes.
      **Efecto colateral encontrado de paso**: `backfill_reportes.py` había quedado desactualizado
      desde que se agregó la escalada de ámbar a morado al 3er día (sección anterior) -- llamaba a
      `_siguiente_estado()` sin pasarle `dias_no_concluyente_consecutivos`, así que nunca aplicaba esa
      escalada en el backfill, y tampoco tenía la lógica de "congelar la racha sin imagen" ni el campo
      nuevo `camaras_no_concluyentes` de `ResumenServidor` (le habría faltado un argumento obligatorio
      y tronado al primer uso). Corregido para que coincida exactamente con `db.guardar_resultado()`.

## Exploración de una "Versión 2" (26/10/2026)

El usuario empezó a sentir que el programa "se complica" (bases de imagen imperfectas, resultados
que no siempre convencen) y planteó la idea de rediseñar el programa desde cero -- una v2. Primer
paso acordado: entender bien cómo está hecha la v1 actual antes de decidir qué cambiar.

- **Carpeta `diagramas/` creada**, con diagramas de flujo en Mermaid por módulo/punto de entrada.
  Primer diagrama: `diagramas/01-flujo-main.md` (flujo completo de `main.py`, paso a paso, más el
  mapa de qué módulo importa a cuál). Se corrigió un error de sintaxis Mermaid en el segundo
  diagrama (un ciclo de vuelta sobre un nodo de decisión más signos `¿?` dentro de etiquetas con
  pipe) que lo dejaba en blanco en el visor del usuario.
- **`CLAUDE.md`** (versionado) y **`CLAUDE.local.md`** (no versionado, en `.gitignore`) creados --
  instrucciones de proyecto vs. notas personales de la máquina de Ismael. Reglas explícitas
  agregadas: actualizar siempre `ROADMAP.md` después de cada interacción correcta (o antes de
  cualquier push), y actualizar siempre `CHANGELOG.md` después de cada interacción.
- **`CHANGELOG.md` creado**, reconstruido desde el historial real de `git log` -- registro breve y
  cronológico (formato Keep a Changelog, agrupado por fecha en vez de versión, ya que el proyecto no
  se publica como paquete y no maneja número de versión en ningún archivo).
- **Reestructuración del proyecto por paquetes (26/10/2026)**, pensando en que varios de estos
  módulos se van a reutilizar más adelante (ej. en el futuro programa de administración, que es un
  proyecto aparte -- ver `CLAUDE.md`/memoria). Los puntos de entrada (`main.py`,
  `generar_reporte.py`, `migrate.py`) se quedan en la raíz -- así los lanzadores `.ps1` externos no
  necesitan tocarse. Todo lo demás se agrupó por responsabilidad:
  - `comparacion/` -- `config_compare.py`, `image_compare.py`, `log_parse.py` (lógica pura, sin DB/
    red/UI).
  - `persistencia/` -- `db.py`.
  - `reporte/` -- `datos_reporte.py`, `reporte_ejecutivo.py`.
  - `integraciones/` -- `monit_client.py`, `correo.py`.
  - `ui/` -- `ventana_revision.py`, `ventana_bases.py`.
  - `scripts/` -- se consolidaron ahí todos los scripts de un solo uso que antes vivían sueltos en
    la raíz (`bootstrap_config_base.py`, `bootstrap_image_base.py`, `backfill_reportes.py`,
    `diagnostico_jpeg.py`), junto con el que ya estaba (`mock_reporte_ejecutivo.py`).
  Movido con `git mv` (conserva el historial de cada archivo). Cada carpeta nueva lleva un
  `__init__.py` con una línea describiendo su propósito.
  - **Detalles que había que corregir al mover, más allá de los imports**: tres módulos construyen
    rutas con `Path(__file__).parent` para llegar a `assets/` (`reporte_ejecutivo.py` → el logo del
    PDF, `correo.py` → el logo de la firma, `ventana_revision.py` → `ASSETS_DIR`) -- al quedar un
    nivel más adentro, se corrigieron a `.parent.parent` para seguir apuntando a la raíz del
    proyecto. Lo mismo con `backfill_reportes.py`: su `SALIDA_ROOT` apuntaba a
    `Reportes_Backfill/` junto al propio archivo -- al moverse a `scripts/`, se corrigió para que
    el PDF siga guardándose en la raíz del repo, no dentro de `scripts/`.
  - **Scripts de administración**: como ahora viven en `scripts/` pero importan paquetes que viven
    en la raíz, se les agregó el mismo truco que ya traía `mock_reporte_ejecutivo.py`
    (`sys.path.insert(0, str(Path(__file__).parent.parent))`) antes de sus imports del proyecto.
  - **`ventana_revision.py` ya no se puede correr directo** (`python ui/ventana_revision.py`) --
    su demo manual (`if __name__ == "__main__"`) ahora se corre como módulo desde la raíz:
    `pipenv run python -m ui.ventana_revision`. Documentado en el propio archivo y en el README.
  - Verificado extensamente antes de dar por bueno: compilación de todos los archivos, import real
    de los tres puntos de entrada y de los 5 scripts de `scripts/`, `main.py --help`,
    `migrate.py` (idempotente, sin re-aplicar nada), y una generación real de reporte PDF contra la
    base de datos de producción (`generar_reportes_del_dia` para AbInBev, 24/10/2026) -- todo
    funcionando exactamente igual que antes de mover los archivos.
- **`diagramas/01-flujo-main.md` actualizado (26/10/2026)**: tras la reestructuración por paquetes,
  los nombres de módulo del diagrama (narrativa + los dos Mermaid) se actualizaron a las rutas
  nuevas (`comparacion.`, `persistencia.`, `reporte.`, `integraciones.`, `ui.`, `scripts.`), en vez
  de dejarlo apuntando a ubicaciones que ya no existen.
- **Avisos de `markdownlint` corregidos en `CHANGELOG.md` (26/10/2026)**: encabezados y listas sin
  su línea en blanco antes/después (MD022/MD032). El aviso de "encabezado duplicado" (MD024) para
  `### Agregado`/`### Cambiado`/`### Corregido` repetidos bajo cada fecha es esperado en este
  formato (Keep a Changelog) -- se agregó `.markdownlint.json` con `MD024.siblings_only = true`
  para que solo marque duplicados reales (misma sección, mismo padre), en vez de cualquier
  encabezado repetido en todo el archivo. También se desactivó MD013 (largo de línea, límite por
  defecto de 80) -- todo el proyecto (ROADMAP, README) envuelve el texto a mano a ~95-100
  caracteres, no 80, y hay tablas/URLs que de cualquier forma lo exceden; no tenía caso reescribir
  cientos de líneas ya existentes para ajustarse a un límite que nunca se siguió aquí.
- **`diagramas/02-modulo-comparacion-imagen.md` creado (26/10/2026)**: documentación a fondo de
  `comparacion/image_compare.py` (las dos señales de geometría que siempre se corren juntas, el
  enmascarado del texto sobreimpreso, la tabla completa de decisión, los estados que regresa y qué
  hace `main.py` con cada uno, las constantes/umbrales con su origen experimental). Surgió de
  aclarar una duda del usuario sobre el orden de ejecución de `main.py` (confirmado: un solo bucle
  por cámara, config + imagen seguidos, no dos pasadas separadas).
  - **Hallazgo real de paso**: `_diff_contenido()` (la señal de "contenido", pensada para detectar
    obstrucción total) se calcula en cada comparación pero sus resultados
    (`contenido_mean`/`contenido_p95`) no se usan en la decisión de `evaluar_par()`, no se le
    muestran al humano en la ventana de revisión, y no se guardan en `historial_comparacion` --
    confirmado revisando `persistencia/db.py` completo. Es trabajo de CPU sin ningún efecto hoy;
    queda anotado para cuando se diseñe la v2.
- **Segundo problema de sintaxis Mermaid corregido (26/10/2026)**: el usuario reportó que "no
  aparecen todos los diagramas" -- se descartó que fuera la extensión de VSCode (ya tiene instalada
  exactamente la recomendada, `bierner.markdown-mermaid`, más `markdownlint`, sin ninguna en
  conflicto). Encontrados dos problemas reales de sintaxis, el mismo patrón que ya había tumbado un
  diagrama antes (22/10/2026):
  - `01-flujo-main.md`, sección "Mapa de módulos": los IDs de nodo con punto sin comillas
    (`comparacion.config_compare`) nunca se habían verificado visualmente después de renombrarlos
    con las rutas nuevas de paquetes -- un punto en un ID sin comillas no es confiable entre
    versiones del parser de Mermaid. Corregido usando IDs seguros con guion bajo
    (`comparacion_config_compare`) y el nombre con punto solo como etiqueta visible entre comillas.
  - `02-modulo-comparacion-imagen.md`, diagrama de decisión: símbolos `>`/`<` sueltos dentro de
    etiquetas (`"> 15px?"`, `"< umbral?"`), fuera de un tag reconocido como `<br/>`. Corregido
    reescribiendo la comparación en palabras ("mayor a 15px", "menor al umbral").
- **Tercer ajuste al mismo archivo (26/10/2026)**: después del fix anterior, el diagrama de la
  sección 4 ("La decisión") seguía sin aparecer en el visor del usuario, mientras el de la sección
  5 sí. Causa probable: los dos diagramas de `02-modulo-comparacion-imagen.md` reutilizaban las
  mismas letras como ID de nodo (`A`, `B`, `C`, `D`, `E`, `F`, `G`, `H`...) -- cuando dos diagramas
  Mermaid distintos en la misma página comparten IDs, es un problema conocido (colisión de IDs en
  el DOM/SVG generado), documentado en varias extensiones de Mermaid para VSCode. Corregido dándole
  a cada diagrama un prefijo único en todos sus IDs (`ep_*` para el de `evaluar_par`, `cc_*` para el
  de `compare_camera_image`) -- elimina la colisión sin importar si esa era la causa exacta. De
  paso se quitaron comillas simples sueltas dentro de las etiquetas (otro factor de riesgo
  innecesario, sin aportar nada).
- **Diseño propuesto: mejoras a `comparacion/image_compare.py` (26/10/2026)**. Tras documentar el
  módulo (`diagramas/02-modulo-comparacion-imagen.md`) se discutió a fondo dónde están sus puntos
  ciegos reales y qué tan explotable es el perfil por cámara que Fase 3 ya dejó en la base de datos
  sin usar (`perfil_camara.mediana_desplazamiento`/`p95_desplazamiento`/`metodo_preferido`/
  `ultimo_recalculo`, confirmado sin lectura ni escritura en ningún lado del código vía grep
  completo del proyecto; `n_confirmaciones_humanas` sí se escribe pero nunca se lee). El usuario
  trajo un análisis externo (Claude para escritorio) con ideas adicionales sobre cómo distintas
  marcas de cámara resuelven esto, que se evaluó punto por punto contra el código real de este
  proyecto. Dos hechos del negocio/máquina cambiaron la evaluación de varias ideas:
  - Las imágenes siempre se descargan entre 8am y 9am (hora CDMX) -- nunca hay fotos nocturnas que
    comparar (ver `CLAUDE.local.md`). Elimina la necesidad de separar referencia día/noche.
  - La máquina de desarrollo (`caracteristicas-equipo.md`) tiene un i9-13900HX (24 hilos) y una RTX
    4070 Laptop (8GB VRAM reales, el reporte de 4GB es límite de WMI) -- de confirmarse que el
    pipeline en producción corre ahí, el costo de cómputo deja de ser un obstáculo real para usar
    un detector de objetos (YOLO/`ultralytics`) o matchers de deep learning (`kornia`), dado el
    volumen (~270 cámaras, una vez al día). Sigue pendiente de confirmar si la tarea programada de
    producción corre en esta misma laptop o en otra máquina sin GPU.
  - Orden de prioridad acordado (valor/costo, de mayor a menor):
    1. Base de referencia por **mediana de N días** por cámara (sin split día/noche) en vez de la
       foto de un solo día -- ataca directo el problema de "las bases no son las mejores" que iba a
       ser el motor del todo de la v2. YOLO opcional *solo al (re)construir la referencia*, para
       limpiar objetos que se repiten en el mismo lugar en varias de las fotos muestreadas -- no
       como paso de cada comparación diaria, para mantener el costo real bajo incluso si la
       inferencia corriera en CPU.
    2. **Detección de lente sucio/desenfocado** (nitidez vía Laplaciano u otra métrica simple),
       calibrada por cámara con mediana+MAD de su propio histórico, alertando solo ante caída
       sostenida varios días -- cubre una falla real que hoy no se detecta en absoluto (ni "se
       movió" ni "está totalmente tapada" la ven).
    3. **Salud absoluta de la imagen actual** (varianza/brillo/densidad de bordes muy bajos) para
       detectar lente tapado/pintado directamente, sin depender de comparar contra la base.
    4. **Descomponer la homografía de RANSAC** (que ya se calcula) en traslación/rotación/escala
       medibles, en vez de solo el promedio de desplazamiento de los inliers.
    5. **Comparar también contra el día anterior**, no solo contra la base fija de largo plazo --
       útil especialmente en cámaras de poco textura donde la comparación contra una base de meses
       acumula ruido.
    6. **Set de validación aprovechando datos ya existentes**: `historial_comparacion.veredicto_humano`
       ya es, sin saberlo, el arranque de un set etiquetado real de producción -- usarlo antes de
       tocar cualquier umbral, en vez de partir de cero.
    7. Matchers de deep learning (`kornia`/SuperPoint+LightGlue/LoFTR) -- ya no se descartan por
       costo de cómputo dado el hardware, pero quedan como fase posterior, condicionados a
       confirmar dónde corre el pipeline de producción.
  - Se descartó agregar `scikit-image` solo para correlación de fase -- duplica una capacidad que
    `cv2.phaseCorrelate` ya cubre, sin aportar nada nuevo.
  - **Siguiente paso acordado**: diseñar e implementar esto paso a paso, empezando por el punto 1.
  - **Decisiones concretas para el punto 1 (26/10/2026)**:
    - `N_DIAS_MEDIANA_BASE = 10`, constante en `comparacion/image_compare.py`, ajustable.
    - La mediana solo se (re)construye cuando se reemplaza la base manualmente en
      `ui/ventana_bases.py` -- no hay recálculo periódico automático por ahora.
    - El historial se arma reutilizando el `.jpg` que ya llega cada día (no hace falta backfill de
      fotos viejas).
    - Al confirmar un reemplazo de base en `ui/ventana_bases.py`, la imagen elegida se usa de
      inmediato como base provisional (la cámara se sigue comparando normalmente desde ese mismo
      día); a los `N_DIAS_MEDIANA_BASE` días frescos acumulados, el sistema la reemplaza solo por
      la mediana real, sin que nadie tenga que volver a entrar a la ventana.
  - **Paso 1 implementado (26/10/2026)**: `comparacion/image_compare.py` ahora guarda una copia
    fechada del `.jpg` de cada cámara en `IMAGE_HISTORY_ROOT` (variable de entorno nueva, mismo
    patrón que `IMAGE_BASE_ROOT` pero con una subcarpeta por cámara:
    `cliente/planta/servidor/camara/AAAA-MM-DD.jpg`), con una ventana rotatoria que conserva solo
    las `N_DIAS_MEDIANA_BASE` fotos más recientes -- por muestras guardadas, no por fecha de
    calendario, para no castigar huecos (fin de semana, falla de descarga). Es puro trabajo de
    infraestructura: no cambia ningún `status` ni comportamiento visible todavía, solo empieza a
    juntar los datos que el paso 2 (construir la mediana) va a necesitar.
    - `compare_camera_image()` ahora recibe `fecha` (opcional, por compatibilidad con llamadas
      viejas que no la necesiten) y guarda el historial solo cuando la imagen se pudo leer
      correctamente (evita meter `.jpg` corruptos al futuro cálculo de mediana).
    - Conectado en los tres llamadores reales: `main.py` (corrida diaria), `scripts/
      backfill_reportes.py` (para que el historial quede consistente también al reconstruir días
      pasados). La demo manual de `ui/ventana_revision.py` (`__main__`) se dejó sin `fecha` a
      propósito -- es una prueba manual puntual, no debe ensuciar el historial real.
    - Probado con una simulación de 13 días seguidos sobre una cámara/cliente temporal (fuera del
      árbol real), confirmando que conserva exactamente las últimas 10 y borra el resto; limpiado
      después de la prueba.
    - Pendiente: paso 2 (función que arme la mediana a partir de este historial) y paso 3
      (conectarla a `ui/ventana_bases.py` con el comportamiento de "base provisional" descrito
      arriba).
  - **Bootstrap del historial desde el archivo real (26/10/2026)**: el usuario notó que no hace
    falta esperar `N_DIAS_MEDIANA_BASE` días reales hacia adelante -- `CHECK_PLANTS_ROOT` ya tiene
    meses de capturas diarias por cámara. Se descartó construir un "selector de mejores imágenes":
    la mediana ya descarta sola una minoría de imágenes malas (objeto en cuadro, reflejo) sin
    identificarlas una por una, que es justo el argumento original para preferirla sobre la base
    actual -- filtrar de más sería resolver otra vez un problema que la mediana ya resuelve gratis.
    Se decidió exigir las `N_DIAS_MEDIANA_BASE` completas antes de construir cualquier mediana
    (nada de "mediana parcial" con menos muestras) -- más estricto, pero evita medianas poco
    confiables para cámaras nuevas o con huecos; esas simplemente tardan más en tener una.
    - `scripts/bootstrap_image_history.py` (nuevo): reutiliza el mismo patrón de indexado que
      `bootstrap_image_base.py` (escanea todo `CHECK_PLANTS_ROOT`), y completa el historial de cada
      cámara buscando hacia atrás los días más recientes que falten -- sin sobrescribir lo que ya
      hay. Descarta imágenes corruptas o de resolución distinta a la más reciente válida de esa
      cámara (evita mezclar fotos de antes de un cambio de cámara/lente). Cámaras sin suficiente
      archivo real para completar las `N_DIAS_MEDIANA_BASE` quedan reportadas al final, para que se
      sigan completando solas con las corridas normales.
  - **Paso 2 implementado (26/10/2026)**: `construir_base_por_mediana()` en
    `comparacion/image_compare.py` arma la mediana por píxel de las `N_DIAS_MEDIANA_BASE` imágenes
    más recientes del historial; regresa `None` si falta alguna, si no se puede leer, o si alguna
    tiene otra resolución -- no decide nada por su cuenta, el llamador (paso 3) decide qué hacer
    mientras tanto. Se expuso `imread_unicode()` (antes `_imread_unicode`, privado) y se agregó
    `fechas_en_historial()`/`historial_path()`, necesarios para que el script de bootstrap no tenga
    que adivinar el formato interno del historial.
    - Probado con historial sintético (cámara/cliente temporal, fuera del árbol real): menos de
      `N_DIAS_MEDIANA_BASE` imágenes regresa `None`; con las completas e idénticas, la mediana sale
      exactamente igual a la fuente; un archivo corrupto o con otra resolución en medio del
      historial también regresa `None`. De paso, confirmó otra vez por qué existe
      `imread_unicode()`: `cv2.imwrite`/`cv2.imread` directos fallan en silencio contra una ruta
      con acentos en Windows (API ANSI) -- un intento de corromper un archivo de prueba con
      `cv2.imwrite` no escribió nada, sin ningún error.
  - **Bootstrap corrido contra producción (26/10/2026)**: `scripts/bootstrap_image_history.py`
    ejecutado contra el `CHECK_PLANTS_ROOT` real. Resultado: **208 cámaras** quedaron con las 10
    imágenes completas (listas para construir su mediana); **9 cámaras** no tienen suficiente
    archivo real todavía (entre 3 y 9 días válidos: `AbInBev/MEDELLIN/QLYMSPROD04/{B01-C, B02-C,
    B03, CS, P3E, P3S}`, `Api_Manzanillo/API-MANZANILLO/APIMAN-FASE1/PV-PC05`,
    `Pemex/TAD18DEMARZO/DEMOQUA/{ENT1-Pl01, LL01-Pl01}`) -- se van a seguir completando solas con
    las corridas normales de cada día. Total: 217 cámaras, 2120 fotos, ~509 MB en
    `IMAGE_HISTORY_ROOT`. Los avisos de "Corrupt JPEG data" en la terminal son de la librería JPEG
    al toparse con archivos dañados reales del archivo histórico -- se descartan solos (de ahí las
    9 cámaras con menos de 10 días), no son errores del script.
  - **Decisiones concretas para el punto 3 (26/10/2026)**:
    - Estado de "promoción pendiente" en una columna nueva y dedicada (`perfil_camara
      .base_reemplazada_el DATE`, migración `0004_base_mediana.sql`) -- en vez de reutilizar las
      columnas viejas de Fase 3 (`metodo_preferido`, `ultimo_recalculo`), para no mezclar este tema
      con el de calibración de umbrales por cámara (tema aparte, todavía sin empezar). `NULL`
      significa "sin promoción pendiente".
    - Además de conectar el flujo hacia adelante, se promovieron **de una vez** las 208 cámaras que
      ya habían quedado con historial completo tras el bootstrap -- para no dejar ese trabajo sin
      aprovechar hasta que a cada una le tocara pasar por un reemplazo manual.
  - **Paso 3 implementado (26/10/2026)**:
    - `comparacion/image_compare.py`: `imwrite_unicode()` (misma lógica que `imread_unicode` pero
      para escribir -- `cv2.imwrite` tampoco soporta rutas con acentos en Windows, falla en
      silencio sin excepción ni archivo escrito), `limpiar_historial_imagen()` (borra el historial
      viejo de una cámara), y `promover_base_a_mediana()` (si ya hay historial suficiente,
      sobreescribe la base actual con la mediana; `False` si todavía no alcanza -- no es un error).
    - `persistencia/db.py`: `obtener_camara()` ahora también trae `base_reemplazada_el`;
      `marcar_base_reemplazada()` la fija a hoy al confirmar un reemplazo; nueva
      `limpiar_base_reemplazada()` la apaga una vez promovida.
    - `ui/ventana_bases.py`: al confirmar un reemplazo, además de `save_base()` (sin cambios), se
      limpia el historial viejo de esa cámara y se guarda la imagen elegida como día 1 del
      historial fresco -- para que la futura mediana no mezcle fotos de antes del arreglo.
    - `main.py`: en el bucle diario, si `perfil["base_reemplazada_el"]` no es `NULL`, intenta
      `promover_base_a_mediana()` después de procesar la imagen del día; si ya hay suficiente
      historial, promueve y apaga la marca -- sin que nadie tenga que volver a entrar a
      `ventana_bases.py`. Si todavía no alcanza, no hace nada y lo vuelve a intentar al día
      siguiente.
    - Probado de punta a punta contra la base de datos real con una cámara/cliente desechable
      (creada y borrada en la misma prueba): `base_reemplazada_el` arranca en `NULL`,
      `marcar_base_reemplazada()` la fija a hoy, `promover_base_a_mediana()` regresa `False` sin
      historial y `True` con las 10 completas (la base queda escrita con la forma correcta), y
      `limpiar_base_reemplazada()` la apaga otra vez.
    - **Incidente de paso, resuelto**: al aplicar la migración `0004`, `migrate.py` se quedó
      colgado -- una conexión vieja (`pid` en PostgreSQL) llevaba **~8.8 horas "idle in
      transaction"** desde una consulta anterior sobre `Api_Manzanillo`, bloqueando el lock
      exclusivo que necesita un `ALTER TABLE`. Confirmado con el usuario antes de tocar nada;
      cerrada con `pg_terminate_backend()`, y la migración corrió sin problema después. Vale la
      pena recordar: si una migración futura se cuelga sin motivo aparente, revisar primero
      `pg_stat_activity` por conexiones viejas "idle in transaction" antes de asumir otra causa.
    - `scripts/promover_bases_pendientes.py` (nuevo, de una sola vez): recorre todas las cámaras de
      `IMAGE_BASE_ROOT` y promueve cualquiera con historial ya completo, sin depender de
      `base_reemplazada_el` (pensado para aprovechar el bootstrap, no para el flujo normal).
      Corrido contra producción: **208 bases promovidas a mediana**, **9 sin suficiente historial
      todavía** (las mismas 9 cámaras del bootstrap) -- se completarán solas con las corridas
      normales. Verificado releyendo varias bases promovidas al azar: siguen siendo `.jpg` válidos
      y legibles, con la resolución correcta.
    - Con esto, los pasos 1-3 del diseño quedan completos e implementados. Pendiente: los puntos
      2-6 restantes del orden de prioridad acordado (detección de lente sucio/desenfocado, salud
      absoluta de imagen, desplazamiento descompuesto de RANSAC, comparación contra el día
      anterior, aprovechar `veredicto_humano` como validación) -- sin empezar todavía.
  - **Punto 2 implementado: detección de lente sucio/desenfocado (26/10/2026)**. Cubre una falla
    que hoy no detectaba nada (ni ORB/fase ni la diferencia de contenido): el lente se ensucia o
    desenfoca gradualmente, sin que la cámara se haya movido.
    - **Decisiones de diseño confirmadas**: se reutiliza el mecanismo existente de `REVISAR`/morado
      con un motivo distinto ("lente sucio/desenfocado"), en vez de crear un estado nuevo del
      semáforo -- menos superficie de cambio (nada que tocar en el PDF ni en el reporte). Exige las
      `N_DIAS_MEDIANA_BASE` completas del historial para evaluar, igual que
      `construir_base_por_mediana` -- consistente con esa misma regla ya establecida.
    - `comparacion/image_compare.py`: `_nitidez()` (varianza del Laplaciano sobre la imagen con las
      esquinas tapadas -- igual que ORB/fase, para que el texto sobreimpreso, siempre nítido, no
      enmascare un lente realmente borroso) y `evaluar_nitidez()` (compara la nitidez de hoy contra
      la mediana + MAD de las 10 imágenes del historial de esa cámara -- reutiliza el mismo
      historial de la base por mediana, no hace falta guardar nada aparte). Usa MAD en vez de
      desviación estándar por ser robusta a que algún día del historial ya haya sido borroso.
      Umbral: más de `UMBRAL_MAD_NITIDEZ = 3.5` desviaciones MAD por debajo de la mediana
      (convención de Iglewicz & Hoaglin para outliers robustos) -- constante ajustable, sin
      validar todavía contra datos reales (mismo espíritu que `MIN_CONF_FASE`, marcado como
      pendiente de recalibrar en su momento).
    - `persistencia/db.py`: nuevo contador `dias_borroso_consecutivos` (mismo patrón que
      `dias_no_concluyente_consecutivos`), nueva constante `DIAS_BORROSO_PARA_REVISION = 3`.
      `_siguiente_estado()` ahora recibe `fuerza_revision_borrosa` -- aunque la geometría diga
      `OK`, una nitidez sospechosa sostenida esos 3 días manda a morado igual que un `REVISAR`
      normal. `guardar_resultado()` calcula esa bandera internamente y guarda los valores crudos de
      nitidez en `historial_comparacion` (nuevas columnas `nitidez_actual`,
      `nitidez_mediana_historica`, `nitidez_mad_historica`, `nitidez_sospechosa`) para poder
      revisar/recalibrar después con datos reales -- migraciones `0004_base_mediana.sql` y
      `0005_nitidez_lente.sql`.
    - `main.py`: abre la ventana de revisión también cuando la nitidez lleva sospechosa
      `DIAS_BORROSO_PARA_REVISION` días seguidos (aunque el estado geométrico sea `OK`), con un
      diagnóstico que ahora incluye la nitidez de hoy contra la mediana histórica; el mensaje de
      "CONFIRMADO" al veredicto humano distingue si fue por movimiento o por lente sucio/borroso.
    - `scripts/backfill_reportes.py` actualizado para no quedar desincronizado (mismo patrón de
      congelar/incrementar/reiniciar la racha, mismo paso de `fuerza_revision_borrosa` a
      `_siguiente_estado`).
    - Probado de punta a punta: `evaluar_nitidez` con historial sintético (sin suficiente historial
      -> `None`; imagen idéntica al historial -> no sospechosa; imagen deliberadamente desenfocada
      con `cv2.GaussianBlur` contra un historial nítido -> sospechosa); `_siguiente_estado` con los
      cuatro casos relevantes (OK normal, OK+nitidez sostenida, REVISAR normal, veredicto humano
      manda sin importar nitidez); y `guardar_resultado` de punta a punta contra la base de datos
      real con una cámara desechable -- 3 días seguidos de nitidez sospechosa escalan a morado
      exactamente al tercero, igual que diseñado.
  - **Punto 3 implementado: salud absoluta de imagen (26/10/2026)**. Detecta obstrucción total del
    lente (algo puesto directamente encima) de forma directa e inmediata, sin comparar contra nada
    -- a diferencia de la nitidez (punto 2, necesita 10 días de historial) o `_diff_contenido`
    (necesita una base). Funciona desde el primer día de una cámara nueva.
    - **Validado contra datos reales antes de fijar umbrales** (en vez de inventar números):
      midiendo varianza/brillo (escala de grises, esquinas tapadas igual que ORB/nitidez) sobre las
      217 cámaras reales de producción, el peor caso legítimo encontrado fue varianza 32.4 / brillo
      26.6 (escena nocturna de poca textura). Una obstrucción total simulada (imagen casi uniforme)
      dio varianza ~1.9. Con ese margen real: `UMBRAL_VARIANZA_MINIMA = 15.0`,
      `UMBRAL_BRILLO_MINIMO = 15.0`, `UMBRAL_BRILLO_MAXIMO = 240.0`. De paso se confirmó que esta
      señal **no** sirve para desenfoque gradual (un empañado fuerte simulado con `GaussianBlur`
      grande siguió dando varianza alta, ~1543) -- son señales complementarias, no una reemplaza a
      la otra.
    - **Disparo inmediato, no sostenido** (a diferencia de la nitidez): una obstrucción total no es
      ambigua como un desenfoque gradual, así que no hace falta esperar varios días -- un solo día
      sospechoso ya manda a morado. No necesitó contador nuevo en `perfil_camara` por esto mismo.
    - `comparacion/image_compare.py`: `evaluar_salud_imagen()`, calculada siempre que la imagen se
      pudo leer (incluso en `BASE CREADA`/`BASE DESACTUALIZADA`, a diferencia de la nitidez, que
      solo corre en la comparación normal).
    - `persistencia/db.py`: `_siguiente_estado()` ahora también recibe `fuerza_revision_salud`;
      `guardar_resultado()` guarda `salud_varianza`/`salud_brillo`/`salud_sospechosa` en
      `historial_comparacion` (migración `0006_salud_imagen.sql`).
    - `main.py`: abre la ventana también ante salud sospechosa (aunque sea el primer día), con un
      mensaje de "CONFIRMADO" distinto ("posible lente tapado/obstruido") cuando es esa la causa.
      `scripts/backfill_reportes.py` actualizado igual.
    - **Quirk conocido, aceptado por ahora**: si el primer `.jpg` de una cámara nueva (`BASE
      CREADA`) ya sale obstruido, la ventana de revisión compara la imagen contra sí misma (la
      base recién creada es esa misma foto) -- funcionalmente correcto (el humano igual nota el
      problema a simple vista y puede marcar "Base desactualizada"), pero visualmente redundante.
      No se resolvió en esta iteración por mantener el cambio acotado.
    - Probado con una imagen real (no sospechosa), una obstrucción simulada y una imagen muy
      oscura simuladas (ambas sospechosas), y de punta a punta contra la base de datos real con una
      cámara desechable: un solo día con salud sospechosa ya escala a morado, sin esperar varios
      días.
  - **Punto 4 implementado: desplazamiento de RANSAC descompuesto (26/10/2026)**. En vez de solo el
    promedio de distancia entre puntos inlier (`orb_desp`, que no distingue un giro de un
    desplazamiento lineal), se traduce la misma información a traslación (`orb_tx`/`orb_ty` en
    píxeles), rotación (`orb_rotacion_deg`) y escala (`orb_escala`) -- medibles, no solo "se movió
    tanto". **Puramente informativo**: no cambia la decisión `OK`/`REVISAR` existente (`orb_desp`
    sigue siendo el que se compara contra el umbral), solo enriquece el diagnóstico que ve el
    humano y lo que se guarda para análisis futuro.
    - `comparacion/image_compare.py`: `_descomponer_transformacion()` ajusta una transformación de
      similitud (traslación + rotación + escala uniforme, `cv2.estimateAffinePartial2D`) sobre los
      mismos puntos inlier que ya filtró el RANSAC de la homografía -- no hace falta volver a
      detectar nada. Se prefirió una similitud (4 grados de libertad) sobre descomponer la
      homografía proyectiva completa (8 grados de libertad): el movimiento real de una cámara de
      seguridad (pan/tilt/giro) se explica bien así, y es más simple de interpretar.
    - **Validado matemáticamente** antes de dar por buena: con dos imágenes idénticas, la
      transformación recuperada es la identidad exacta (tx=ty=0, rotación=0°, escala=1.0); con una
      transformación afín construida a mano con parámetros conocidos (tx=15, ty=-8, rotación=3°,
      escala=1.02) aplicada de verdad a una imagen real con `cv2.warpAffine`, los valores
      recuperados salieron prácticamente exactos (diferencia menor a 0.01 en todos). (Una primera
      prueba usando `cv2.getRotationMatrix2D`, que rota alrededor del centro de la imagen en vez
      del origen, dio traslaciones recuperadas que no coincidían con la intuición -- no era un
      error del código, sino que esa construcción mezcla la rotación-alrededor-del-centro con la
      traslación explícita en la parametrización origen-relativa que se recupera; quedó descartada
      como forma de validar y se reemplazó por la matriz afín construida a mano.)
    - `persistencia/db.py`: nuevas columnas en `historial_comparacion` (migración
      `0007_orb_transformacion.sql`); `main.py` las muestra en el diagnóstico de la ventana de
      revisión ("ORB detallado: traslación (x, y) px, rotación X°, escala Y").
    - Probado de punta a punta contra la base de datos real con una cámara desechable: los cuatro
      valores se guardan y se leen exactamente igual a como se calcularon.
  - **Punto 5 implementado: comparación contra el día anterior (26/10/2026)**. Compara la imagen de
    hoy contra la más reciente guardada en el historial -- no contra la base fija de largo plazo --
    reutilizando `evaluar_par()` tal cual, sin lógica nueva de comparación. **Decisiones
    confirmadas**: puramente informativa por ahora (no cambia `OK`/`REVISAR`/`NO CONCLUYENTE` --
    primero se junta evidencia real de qué tan bien funciona antes de dejarla influir en algo, ni
    siquiera para "rescatar" un `NO CONCLUYENTE`); "el día anterior" es la foto más reciente que ya
    estaba en el historial, sin importar hace cuántos días (robusto a huecos de fin de semana o
    fallas de conexión), no estrictamente el día calendario anterior.
    - `comparacion/image_compare.py`: `evaluar_dia_anterior()`. Debe llamarse **antes** de que
      `guardar_historial_imagen()` guarde la foto de hoy -- si no, "la más reciente del historial"
      terminaría siendo la foto de hoy comparada contra sí misma. Se reordenó `compare_camera_image`
      para calcularla primero.
    - `persistencia/db.py`: nuevas columnas en `historial_comparacion` (migración
      `0008_dia_anterior.sql`); `main.py` las muestra en el diagnóstico de la ventana de revisión.
    - Probado con historial sintético de 2 días (misma imagen ambos días): el primer día no hay
      "día anterior" todavía (`None`, historial vacío); el segundo día sí compara correctamente
      contra el primero (no contra sí mismo) y da `OK`. Probado también de punta a punta contra la
      base de datos real con una cámara desechable.
    - Con esto, los 5 puntos técnicos del plan de mejoras a `image_compare.py` quedan completos.
      Pendiente, sin empezar: el punto 6 (aprovechar `historial_comparacion.veredicto_humano`, que
      ya es sin saberlo el arranque de un set de validación real, para evaluar qué tan bien están
      funcionando estas señales antes de tocar cualquier umbral o decidir si alguna de las nuevas
      señales informativas -- rotación/escala, salud, día anterior -- debería empezar a influir en
      la decisión).
  - **Punto 6 (primer análisis): validación con `veredicto_humano` real (26/10/2026)**.
    **Corrección de alcance importante**: la persistencia en base de datos (Fase 3) arrancó el
    21/10/2026, no desde inicio de octubre -- el "mes completo" que se asumía al principio en
    realidad son 6 días reales (21 al 26/10) y 1060 filas en `historial_comparacion`. Las 5 señales
    nuevas de este mismo día (nitidez, salud, rotación/escala, día anterior) todavía no tienen
    ningún historial real -- se acaban de activar hoy, así que este primer análisis solo pudo
    usar las señales originales (ORB/fase) + veredicto humano.
    - `scripts/analizar_veredictos.py` (nuevo, reutilizable): agrupa `historial_comparacion` por
      `veredicto_humano` y muestra estadísticas básicas de cada señal -- pensado para correrse
      periódicamente conforme se acumulen más días, no como análisis de una sola vez.
    - **Datos reales disponibles**: 65 veredictos humanos (61 "bien", 2 "mal", 2 "desactualizada").
      Muestra chica -- insuficiente para recalibrar umbrales con rigor estadístico (solo 4 casos
      confirmados como problema real), pero suficiente para un primer vistazo cualitativo real.
    - **Hallazgo 1 -- confirma la necesidad de calibración por cámara, con números concretos**: de
      los 61 "bien" (falsos positivos confirmados), la mediana de `orb_desplazamiento` es 37.6px --
      muy por encima del umbral global (~6-7px para una imagen de ~2700px de ancho al 0.25%).
      `AbInBev/B04` salió "bien" dos veces con 57.8px y 272.4px; `AbInBev/N2p` salió "bien" tres
      veces seguidas con 15.99px, 18.09px y 22.71px -- un patrón consistente por cámara, exactamente
      lo que predijo el Experimento 8 (misma rotación física produce mucho más desplazamiento en
      píxeles en una escena cercana que en una lejana). Es evidencia real, no solo teórica, de por
      qué `umbral_para()` sigue siendo un punto de enganche pendiente.
    - **Hallazgo 2 -- cúmulo inusual de `NO CONCLUYENTE` el 26/10/2026**: una veintena de cámaras de
      AbInBev (`B02`, `B03`, `B05`, `B09`, `NF1-4`, `EN1`, `EX`, `P1-2`, `C1-5`, `E1-3`, `AD1r1`...)
      con 0-13 inliers ORB cada una ese mismo día, todas confirmadas "bien". Parece un problema
      puntual de ese día/cliente (iluminación, condiciones de captura), no ruido disperso aleatorio
      -- queda anotado para seguirle la pista si se repite en próximos días.
    - **Hallazgo 3 -- valida el diseño ya existente con un caso real concreto**: los 2 casos "mal"
      confirmados comparten un patrón -- desplazamiento ORB enorme (129px y 726px) con la
      correlación de fase reportando casi cero movimiento (mediana 0.1px) y sin confianza
      suficiente (`fase_conf` 0.12 y 0.05, ambos bajo `MIN_CONF_FASE`). En el caso con pocos
      inliers ORB (`PV-PC01`, solo 8, bajo `MIN_INLIERS`), **ningún método individual fue
      "confiable"** -- lo rescató exclusivamente la escalada de `NO CONCLUYENTE` a los 3 días
      (pedido 22/10/2026). Sin esa regla, este problema real se habría quedado invisible
      indefinidamente. No se encontró ningún bug en la lógica de decisión -- el sistema ya se
      comportó como se diseñó en ambos casos reales disponibles.
    - **Conclusión y siguiente paso**: no se tocó ningún umbral todavía -- 4 casos confirmados es
      muy poco para recalibrar con confianza, y hacerlo ahora sería adivinar, no medir. Se deja
      `scripts/analizar_veredictos.py` como práctica recurrente: repetirlo conforme se acumulen más
      días (y, en unas semanas, con las 5 señales nuevas ya con historial real) antes de decidir si
      alguna debería empezar a influir en la decisión, o si por fin vale la pena activar la
      calibración por cámara en `umbral_para()`.
  - **`umbral_para()` conectado a `perfil_camara` por fin (26/10/2026)**. El usuario preguntó
    directamente si los umbrales por cámara ya se ajustaban solos -- la respuesta honesta era que
    no: `umbral_para()` seguía siendo el mismo punto de enganche sin terminar desde Fase 3/4, y el
    análisis de veredictos de hace un momento acababa de confirmar con números reales (`B04`,
    `N2p`) que hacía falta. Se decidió conectarlo ahora mismo, reutilizando las columnas
    `mediana_desplazamiento`/`p95_desplazamiento`/`ultimo_recalculo` que ya existían desde
    `0001_init.sql` sin usarse -- no hizo falta ninguna migración nueva.
    - **Decisiones de diseño confirmadas**:
      - El umbral por cámara (`p95_desplazamiento`) solo puede hacer a una cámara **menos**
        sensible que el umbral global, nunca más -- si el p95 calculado sale por debajo del
        global, se usa el global. Evita introducir una clase nueva de falsos positivos en cámaras
        tranquilas con poco historial calibrado todavía.
      - Mínimo de **20 lecturas** (ORB + fase combinadas, de días `OK` o `REVISAR` confirmados
        como "bien" por un humano) antes de confiar en el cálculo para una cámara -- por debajo de
        eso, sigue usando el global. Se excluyen explícitamente los días confirmados como
        movimiento real (`mal`) o base desactualizada (`desactualizada`) -- esos no son "ruido
        normal", son justo lo que se quiere seguir detectando.
      - "Normal" se define como `imagen_status = 'OK'` **o** `veredicto_humano = 'bien'` -- no
        solo `OK`, porque excluir los `REVISAR` que resultaron ser falsos positivos confirmados
        dejaría fuera justo la evidencia más valiosa (la de cámaras como `B04`/`N2p`, que
        necesitan calibración porque *frecuentemente* disparan `REVISAR` con ruido normal alto).
    - **Refactor de contrato, sin cambiar el comportamiento histórico**: `umbral_para()` pasó de
      regresar un porcentaje del ancho (y recibir `cliente/planta/servidor/camara` para una
      consulta a la base de datos que nunca llegó a existir) a recibir el ancho de la imagen y un
      valor ya calibrado en píxeles (o `None`), devolviendo directamente el umbral en píxeles --
      más simple, y respeta que `comparacion/image_compare.py` sigue sin tocar la base de datos
      (el llamador, `main.py`, decide el valor calibrado y lo pasa). `evaluar_par()` y
      `evaluar_dia_anterior()` actualizados para recibir el mismo valor calibrado en vez de un
      porcentaje -- confirmado que no quedó ningún llamador externo usando el contrato viejo
      (grep de todo el proyecto).
    - `persistencia/db.py`: nueva `recalcular_perfiles_estadisticos(conn)`, pensada para correrse
      **una vez al final de cada corrida de `main.py`** (nunca a mitad de la corrida del mismo día,
      para no calibrar con datos de hoy que todavía no se terminaron de verificar hoy mismo) --
      conectada justo después del bucle principal. `obtener_camara()` ahora también trae
      `p95_desplazamiento`, que `main.py` pasa a `compare_camera_image()`.
    - **Probado exhaustivamente antes de confiar en el mecanismo**:
      - Con datos sintéticos (cámara desechable): menos de 20 muestras no calibra; con exactamente
        20, calibra, y un valor `mal=5000px` incluido a propósito quedó correctamente excluido del
        cálculo (confirma que el filtro de exclusión funciona, no solo el de inclusión).
      - `umbral_para()` directo: un p95 calibrado menor al global se ignora (se queda en el
        global); uno mayor sí se usa.
      - Punta a punta con una transformación real de 40px (similar al ruido real visto en
        `B04`/`N2p`): sin calibrar da `REVISAR`; con un umbral calibrado de 50px da `OK` -- el
        caso exacto que se buscaba resolver.
      - **Corrido contra producción real**: `recalcular_perfiles_estadisticos()` recalibró
        **0 cámaras** -- ninguna cámara real individual (identidad completa cliente/planta/
        servidor/cámara) llega todavía a 20 muestras calificadas (el máximo real es 8, incluyendo
        `N2p`). Es el resultado correcto y esperado con solo 5-6 días de datos reales -- ni
        siquiera `B04`/`N2p` se aflojan todavía, exactamente como debe ser dado lo poco que hay
        acumulado. Una consulta de diagnóstico preliminar había sugerido falsamente que 3 cámaras
        ya calificaban (`EP1`, `AD1p`, `AD1r1`) -- resultó ser un error de esa consulta (agrupaba
        por nombre de cámara sin incluir planta/servidor, mezclando cámaras físicas distintas que
        comparten nombre corto), no un problema del código de producción.
    - **Respuesta a la pregunta original del usuario**: no, los umbrales no se ajustaban solos
      hasta hoy -- la nitidez (punto 2) sí era autocalibrada desde que se implementó, pero el
      umbral de movimiento (el que decide `OK` vs `REVISAR`) seguía siendo 100% global. A partir de
      ahora sí se ajusta solo, cámara por cámara, conforme se acumulen suficientes días reales de
      cada una -- se espera ver a `B04`/`N2p` calibrarse en las próximas ~1-2 semanas conforme
      lleguen a las 20 muestras.
  - **¿Y si borramos la base y reprocesamos todo octubre?** (26/10/2026) El usuario preguntó si
    era factible borrar la base de datos actual y volver a correr todo octubre para tener más
    datos de una vez. Se descartó: el archivo real (`CHECK_PLANTS_ROOT`) sí llega hasta el
    22/09/2026 (24 fechas distintas, con huecos), así que es técnicamente posible -- pero el
    ingrediente que más hace falta (`veredicto_humano`) no se puede generar retroactivamente sin un
    humano real mirando cada imagen. Correrlo con `--no-interaction` daría más filas `OK`/`REVISAR`
    pero cero veredictos nuevos -- justo lo que no soluciona nada para `B04`/`N2p`. Correrlo
    interactivo para ~26 días implicaría el mismo esfuerzo humano que ya se va a invertir usando el
    programa normalmente, solo que concentrado en una sesión en vez de repartido. Y borrar la base
    actual tiene un costo real: se perderían los 6 días de datos genuinos ya recolectados
    (incluyendo los 2 incidentes "mal" confirmados), que no se pueden reproducir después. Se decidió
    simplemente dejarlo correr de forma normal -- `backfill_reportes.py` ya existe para el caso de
    querer una vista histórica sin tocar la base de datos real, si hiciera falta más adelante.

- **`diagramas/03-modulo-ventana-revision.md` creado (26/10/2026)**: documentación a fondo de
  `ui/ventana_revision.py` -- los dos paneles de la ventana única y persistente (procesando / pedir
  revisión), el ciclo de vida completo de una corrida, los detalles de implementación que vale la
  pena recordar (tema oscuro leído una sola vez del registro de Windows, cuadrícula de ayuda visual
  dibujada sobre una copia en memoria, manejo de imágenes dañadas con un marcador en vez de
  crashear, bloqueo de un solo hilo vía `wait_variable`), la tabla de qué hace `main.py` con cada
  uno de los botones, y qué NO hace este módulo (no decide cuándo abrirse, no toca la base de
  datos, no es la misma ventana que `ui/ventana_bases.py`).
- **Botón "Actualizar Base" agregado a `ui/ventana_revision.py` (26/10/2026)**. El usuario notó un
  hueco real al revisar el módulo recién documentado: hoy, si la base está desactualizada pero la
  foto de hoy que ya está en pantalla sirve perfectamente, la única opción era "Base
  Desactualizada" -- que congela la cámara y obliga a abrir `ui/ventana_bases.py` por separado para
  subir una imagen a mano, aunque ya se tenía una buena frente a los ojos.
  - Nuevo 4º botón ("Actualizar Base", color ámbar -- `WARN`, ya existía en la paleta sin usarse):
    usa la foto de hoy (`jpg_path`) como base nueva de inmediato, reutilizando exactamente el mismo
    mecanismo que ya construimos hoy para `ui/ventana_bases.py` (`save_base` + limpiar historial +
    arrancar historial fresco + `db.marcar_base_reemplazada`) -- en 10 días frescos se promueve
    sola a mediana, sin que nadie tenga que volver a entrar a otra ventana.
  - `ui/ventana_revision.py` sigue sin tocar la base de datos ni archivos -- solo regresa el nuevo
    valor `"actualizar_base"` en la tupla `(accion, observacion)`, igual que los otros 3. Toda la
    lógica de guardar/promover vive en `main.py`, que ya importaba el resto de estas piezas.
  - `_siguiente_estado()` (`persistencia/db.py`) trata `"actualizar_base"` igual que `"bien"` --
    pasa a verde, el problema ya quedó resuelto en el momento.
  - Probado de punta a punta con una cámara desechable: historial viejo (3 días) queda limpiado,
    la base se reemplaza con la foto de "hoy", `base_reemplazada_el` queda puesta, y el estado pasa
    a verde -- el mismo resultado que lograr lo mismo a mano en dos pasos por separado, ahora en
    uno solo.
- **`scripts/preview_ventana_revision.py` (nuevo, 26/10/2026)**: el usuario pidió ver la ventana de
  revisión de verdad para aprobar la construcción/distribución, sin disparar una corrida completa
  que toque la base de datos innecesariamente. El script busca una cámara real con base + historial
  completo, le aplica un desplazamiento sintético de 40px **en memoria** (nunca se guarda) para
  forzar el diagnóstico más largo posible, lo arma con `main._formatear_diagnostico()` (el mismo
  texto exacto que vería un usuario real), y abre la ventana real -- sin importar `persistencia.db`
  en ningún momento, así que no hay manera de que toque la base de datos.
  - **Hallazgo real al probarlo**: la ventana se quedó en su alto fijo de siempre (760px), pero el
    diagnóstico creció de 2 a 6 líneas hoy -- los botones de abajo quedaban fuera de la vista.
    Corregido en dos frentes: `self.root.geometry()` subido a `1280x880`, y el diagnóstico
    compactado juntando nitidez + salud en una sola línea (5 líneas en el peor caso, antes 6).
  - **Pregunta de paso, respondida**: el usuario notó un "camión fantasma" semitransparente en la
    base de la cámara de prueba (`AD1p`, una de las 208 promovidas a mediana hoy). No es un bug --
    es la mediana de 10 días mostrando un objeto que apareció en una porción intermedia de los días
    muestreados (ni tan poco como para que la mediana lo descarte limpio, ni tan seguido como para
    que se vea sólido). Es el mismo trade-off de la técnica que se discutió semanas atrás al elegir
    mediana sobre una sola foto -- aceptado por ahora, sin evidencia de que cause problemas reales
    en la comparación; si llegara a darlos, la solución natural sería el enmascarado de objetos en
    movimiento con un detector tipo YOLO que se había descartado por ahora (ver conversación sobre
    el hardware de la máquina).
  - Confirmado explícitamente con el usuario: en producción, las imágenes que ve un humano en
    `ventana_revision.py` son los archivos reales sin ninguna modificación (la cuadrícula de ayuda
    se dibuja sobre una copia en memoria solo para mostrarla, nunca toca el archivo guardado); el
    desplazamiento sintético solo existe en este script de prueba.

- **`diagramas/04-modulo-persistencia-db.md` creado (26/10/2026)**: documentación a fondo de
  `persistencia/db.py` -- las dos tablas (`perfil_camara`/`historial_comparacion`), los 5 estados
  del semáforo y qué significa cada uno, la máquina de estados `_siguiente_estado()` completa (su
  orden de prioridad explícito, de mayor a menor), cómo `guardar_resultado()` arma las banderas de
  "forzar revisión" y actualiza las dos rachas (con el porqué de "se congela" en vez de "se
  reinicia a 0"), el resto de funciones del módulo, y qué NO hace.
- **`base_desactualizada` escala a urgente en el reporte tras 3 días sin resolver (26/10/2026)**.
  Al explicar la máquina de estados, el usuario notó que hoy `base_desactualizada` se congela
  indefinidamente sin ninguna presión creciente para resolverla -- pidió que a los 3 días se vea
  con la misma urgencia que un "Mal" confirmado, con la nota "BASE DESACTUALIZADA", para obligar a
  reemplazarla pronto.
  - **Decisión de diseño confirmada**: NO cambiar `perfil_camara.estado_actual` a `rojo` de verdad.
    Si se hiciera, la cámara desaparecería de la lista de `ui/ventana_bases.py` (que solo muestra
    `estado_actual = 'base_desactualizada'` exactamente) y `main.py` dejaría de tratarla como
    desactualizada (`ya_desactualizada` se volvería falso), reanudando comparaciones reales contra
    una base que todos ya acordaron que está mal -- con el riesgo de que algún día la foto nueva se
    pareciera lo suficiente a esa base mala y la cámara "se recuperara sola" sin que nadie la
    hubiera arreglado de verdad. Se optó por una escalada **solo a nivel de reporte**: por dentro
    la cámara sigue congelada en `base_desactualizada` (sigue en la lista de `ventana_bases.py`,
    sigue sin compararse contra nada), pero el PDF la clasifica y colorea como `rojo` después de 3
    días, con la etiqueta "Base de imágenes desactualizada (N días sin resolver)".
  - No hizo falta una columna nueva -- `perfil_camara.estado_desde` ya guarda desde cuándo está en
    el estado actual (se fija la primera vez que cambia, no se vuelve a tocar mientras no cambie),
    así que los días sin resolver salen de `fecha - estado_desde` directamente.
  - `reporte/datos_reporte.py`: nueva constante `DIAS_BASE_DESACTUALIZADA_URGENTE = 3`;
    `_resumen_servidor()` ahora también trae `estado_desde`; `_clasificar_falla()` calcula los días
    sin resolver y escala la clasificación cuando corresponde. `scripts/backfill_reportes.py`
    actualizado para trackear `estado_desde` en su réplica en memoria de la máquina de estados
    (mismo criterio que `guardar_resultado()`: se actualiza solo cuando el estado cambia de verdad).
  - Probado: 0/2/3 días sin resolver (clasificación normal, normal, escala a rojo con la nota), y
    el caso sin `estado_desde` (cámara que nunca cambió de estado, no debería pasar en la práctica
    pero no truena, se trata como 0 días). Verificado contra producción real: las 2 cámaras
    actualmente en `base_desactualizada` llevan 0 días (se marcaron hoy mismo), así que el próximo
    reporte no se ve afectado todavía.

- **Base "para mostrar" separada de la base "para calcular" (27/10/2026)**. El usuario, en la
  revisión real del día (no en un script de prueba), notó el mismo "fantasma" que se había visto
  y aceptado el 26/10 -- pero esta vez le pareció un problema real: un revisor humano no entiende
  una foto con vehículos semitransparentes y piensa que está viendo algo editado.
  - **Causa confirmada en código**: tanto `main.py` como `ui/ventana_revision.py` leen
    `base_path()` para mostrar -- el mismo archivo que `promover_base_a_mediana()` sobrescribe con
    la mediana. El archivo que se muestra es genuino (no se altera al vuelo), pero *es* la mediana,
    no una foto real de un solo día.
  - **Diseño propuesto por el usuario, confirmado**: dos carpetas. `IMAGE_BASE_ROOT` (ya existía)
    vuelve a ser siempre una foto real de un solo día -- la que se muestra. `IMAGE_BASE_MEDIANA_ROOT`
    (nueva) guarda la mediana -- la que mide el algoritmo. `promover_base_a_mediana()` ya no toca
    `IMAGE_BASE_ROOT`; `compare_camera_image()` mide contra la mediana si existe, si no contra la
    foto de un solo día (igual que antes de que existiera la mediana por completo). Nueva
    `limpiar_base_mediana()`, llamada junto con `limpiar_historial_imagen()` al reemplazar una base
    a mano, para no seguir midiendo contra una mediana vieja tras el reemplazo.
  - **Migración de lo ya promovido**: las cámaras que `promover_bases_pendientes.py` ya había
    promovido (ver 26/10/2026) tenían la mediana en `IMAGE_BASE_ROOT` sin que quedara la foto
    original en ningún lado -- `scripts/separar_base_mediana.py` mueve ese archivo tal cual a
    `IMAGE_BASE_MEDIANA_ROOT` (cero cambio para el cálculo, mismos bytes que ya se usaban) y elige
    una foto real para dejar en `IMAGE_BASE_ROOT`.
  - **Criterio para elegir esa foto, decidido con el usuario**: del mes en curso, **sin contar
    hoy** (llovía en Zacatecas -- piso mojado, muchos reflejos -- mejor no depender del día más
    reciente para esto en ninguna cámara). De las opciones disponibles, se descartó el heurístico
    estadístico (imagen más cercana a la mediana del mes, sin dependencias nuevas) a favor de
    detección de objetos real con YOLO -- el usuario prefirió precisión sobre simplicidad para
    este caso, aprovechando que la máquina ya tiene el hardware para correrlo (ver discusión previa
    sobre YOLO y el hardware de cómputo) y que es un script de un solo uso, no una dependencia del
    flujo en tiempo real.
  - **Primer intento (YOLOv8n) con un falso negativo real, detectado antes de confiar en el
    resultado**: en cámaras de muelle con la cámara muy cerca del camión (la parrilla llena casi
    todo el cuadro), YOLOv8n no detectó nada ni bajando la confianza a 0.05 -- eligió como "limpia"
    una foto con un camión ocupando toda la imagen. Confirmado con YOLOv8m sobre la misma foto: sí
    lo detecta (como clase "car", no "truck", pero esa clase ya estaba en la lista de "sucias").
    Se cambió el modelo a YOLOv8m (más preciso, sigue siendo viable en CPU para un script de un
    solo uso: ~6 minutos para las ~265 cámaras) y se volvió a correr -- el script se hizo
    idempotente (si `IMAGE_BASE_MEDIANA_ROOT` ya tiene el archivo de una corrida anterior, no lo
    vuelve a tocar, solo repite la elección de foto para mostrar), para poder reintentar sin
    arriesgar la mediana ya separada correctamente.
  - **Corrido contra producción, verificado visualmente contra las dos cámaras que reportó el
    usuario** (`AbInBev/APAN/QLYMSPROD03/BX5` y `AbInBev/TOCANCIPA/QLYMSPROD05/B02`): 212 cámaras
    migradas -- 190 con una foto totalmente limpia del mes, 22 sin opción perfecta por tráfico casi
    constante (se usa la de menos detecciones), 5 sin fotos utilizables ese mes (sin tocar). Límite
    conocido y aceptado: en `B02` la foto elegida como "limpia" tiene un vehículo parcialmente
    cortado en el borde superior del cuadro, que el detector no marcó -- mucho menor que el
    problema original, no se insistió más en resolverlo (rendimientos decrecientes).
  - Nueva dependencia `ultralytics` (y `torch`, CPU) agregada al `Pipfile` a mano -- `pipenv
    install`/`pipenv lock` siguen fallando con "Permission denied" en esta máquina (mismo problema
    de siempre, ver `CLAUDE.local.md`), así que el `Pipfile.lock` no se pudo regenerar esta sesión.

- **`scripts/revisar_bases.py`: auditoría visual rápida de bases (27/10/2026)**. Tras la migración
  de arriba, el usuario notó que varias bases reales se ven mal (no es un problema de esta sesión,
  son bases que ya estaban desactualizadas de antes y nadie lo había notado a simple vista). Pidió
  una herramienta rápida para recorrer las bases de un servidor y marcarlas.
  - **Diseño confirmado con el usuario** (3 preguntas, las 3 con la opción recomendada menos la
    última): las cámaras ya en `base_desactualizada` se saltan solas (no tiene caso re-marcarlas);
    "Bien" no persiste nada -- si se corre de nuevo sobre el mismo servidor, se ve todo desde el
    principio otra vez (más simple que llevar un registro de avance); "Base Desactualizada" sí deja
    una nota genérica en `observacion_camara`, para distinguir que vino de esta auditoría y no del
    flujo diario normal.
  - Ventana de un solo panel (sin el panel "Actual" ni el campo de observación de
    `ui/ventana_revision.py` -- esos no aplican aquí), reutilizando tema/paleta/helpers de ese mismo
    módulo en vez de duplicarlos.
  - Nueva `db.marcar_base_desactualizada_manual()` -- mismo patrón que `marcar_base_reemplazada()`
    pero al revés (`estado_actual = 'base_desactualizada'`), sin tocar `historial_comparacion`: esto
    es una auditoría visual de la base en sí, no una comparación del día.
  - Probado: construcción/cierre de la ventana con una base real (sin exceptions), y el camino de
    escritura en base de datos completo (`obtener_camara` → `marcar_base_desactualizada_manual` →
    `crear_observacion`) contra una fila de prueba desechable, verificado y borrado por completo
    después -- no quedó nada de prueba en producción.

- **Salud del servicio de IA, Fase 1: captura (27/10/2026)**. `[CAMARA]_ai.jpg` (ver "Estructura de
  datos" arriba) es la salida de un servicio de IA aparte, que Plant Report nunca ha usado -- pero
  el usuario notó que, si ese servicio está caído en un servidor, es un problema del lado de Quantum
  Labs, no de la red/cámara del cliente, y hoy esa distinción no se reportaba en ningún lado.
  - **Investigación sobre logs reales** (antes de tocar código): cada cámara del `.log` de servidor
    reporta 4 pasos en orden fijo por nombre (`Puerto 80`, `Imagen IA`, `Imagen cámara`,
    `Configuración`) -- si `Puerto 80` falla, los demás ni se intentan. Antes de eso, el servidor
    intenta leer un YAML de configuración del servicio de IA por un puerto propio
    (`YAML Read successful [200]` u otro código de error) -- si eso falla, es la señal directa de
    que el servicio está caído, sin necesidad de inferir nada agregando resultados por cámara.
    Encontrado con datos reales: `Pemex/TAD18DEMARZO/DEMOQUA` y `C5i_Colima/COLIMA01` llevaban
    *días* con el YAML fallando, invisible hasta ahora. También se encontró que un mismo servidor
    puede tener más de un puerto de IA activo (`Api_Manzanillo/APIMAN-FASE1` resultó tener 4:
    `12046`, `12047`, `13045`, `13048`), cada uno con su propio bloque de YAML en el mismo log.
  - **Problema real identificado y resuelto fuera de este repo**: cuando el YAML fallaba, el log no
    registraba el puerto en ningún lado (ni con túnel SSH ni con Zerotier) -- imposible saber a cuál
    puerto atribuir la falla en un servidor con varios. Se le pidió al programa externo de revisión
    que imprima `Puerto IA configurado <N>` justo antes de cada intento de lectura de YAML, sin
    importar si falla o no. Verificado contra una corrida de prueba en los 5 casos relevantes (los 2
    que fallaban, el de 4 puertos, uno con túnel SSH y uno sano) -- quedó correcto y no rompió nada
    del formato ya parseado.
  - **Diseño confirmado con el usuario**: tablas nuevas `servicio_ia` (catálogo + estado vivo, uno
    por `(cliente, planta, servidor, puerto)`, mismo patrón que `perfil_camara`) e
    `historial_servicio_ia` (un renglón por día, mismo patrón que `historial_comparacion`) --
    migración `migrations/0009_servicio_ia.sql`.
  - `comparacion/log_parse.py`: nueva `parsear_servicios_ia_servidor()`, por nombre de campo (no
    por posición, más robusto a cambios de orden aunque hoy el orden es fijo) -- regresa una entrada
    por cada bloque `Puerto IA configurado` + su `YAML Read` correspondiente.
  - `persistencia/db.py`: nueva `guardar_estado_servicio_ia()` (upsert catálogo + historial del día,
    mismo patrón que `guardar_resultado()`).
  - `main.py`: `_camaras_del_dia()` ahora regresa también `servicios_ia_por_servidor` (del mismo
    `.log` ya leído, sin pasada extra); se persiste una vez por servidor, antes del ciclo de cámaras.
    `scripts/backfill_reportes.py` (no toca la base de datos a propósito) solo ajustó el
    desempaquetado del tercer valor, sin guardar nada.
  - Probado: el parser contra los 5 casos reales de la corrida de prueba (reconstruidos como
    fixtures después de que se borró la corrida, con el contenido ya verificado antes); el flujo
    completo `_camaras_del_dia()` con una carpeta sintética tipo `CHECK_PLANTS_ROOT`; y
    `guardar_estado_servicio_ia()` contra una fila desechable (`cliente='_TEST_'`) verificando
    alta, cambio de estado (`estado_desde` se actualiza), upsert del mismo día sin duplicar, y
    limpieza completa después -- no quedó nada de prueba en la base de datos real.
  - **Pendiente (Fase 2)**: mostrar esto en el PDF del reporte ejecutivo -- se hace junto con el
    siguiente punto, porque requiere revisar `reporte/datos_reporte.py` y
    `reporte/reporte_ejecutivo.py` de todas formas.

- **Bug real: `scripts/revisar_bases.py` creaba cámaras "fantasma" por mayúsculas (28/10/2026)**. El
  usuario corrió varias sesiones de `scripts/revisar_bases.py` el 27/10 para reemplazar bases que se
  veían mal, tecleando `--client`/`--plant` con una capitalización distinta a la real (ej. `AbINBEV`
  en vez de `AbInBev`). Windows no distingue mayúsculas en rutas de archivo, así que las fotos sí se
  reemplazaron correctamente en disco -- pero Postgres sí distingue mayúsculas, así que cada llamada
  a `db.obtener_camara()`/`marcar_base_reemplazada()` creó una cámara "fantasma" aparte en vez de
  tocar la fila real. Detectado al verificar la corrida diaria del 28/10 (la cuenta de cámaras por
  cliente no cuadraba: apareció un cliente `AbINBEV` con 146 filas, cero historial, sin carpeta real
  en ninguna de las 5 raíces de archivos).
  - **Causa raíz corregida**: `scripts/revisar_bases.py` ahora normaliza `--client`/`--plant`/
    `--server` contra la capitalización real encontrada en disco (`_combinaciones_disponibles()`)
    antes de tocar la base de datos -- cualquier variante de mayúsculas resuelve a la combinación
    real, y una que de verdad no exista da un error claro en vez de seguir en silencio. Probado
    contra las combinaciones reales (`AbINBEV`/`ABINBEV` ambas resuelven a `AbInBev`; una
    combinación inventada da `None`).
  - **Alcance real identificado**: de las 146 filas fantasma, 26 sí habían pasado por un reemplazo de
    verdad (su archivo en disco cambió) -- 13 en `ZACATECAS/QLYMSPROD01`, 12 en
    `ZACATECAS/QLYMSPROD02`, 1 en `TOCANCIPA/QLYMSPROD05/EL`. En esas 26, `base_reemplazada_el`
    (necesario para la promoción automática a mediana) y la observación de la bitácora habían
    quedado en la fila fantasma en vez de la real. **Corregido**: las 26 filas reales ya tienen
    `base_reemplazada_el = 2026-10-27` y su nota recuperada; las 146 filas fantasma (con sus
    observaciones) se borraron después de extraer lo útil -- `historial_comparacion` no tenía
    ninguna fila que perder ahí, confirmado antes de borrar.
  - **Nota para seguimiento**: 2 de esas 26 (`TOCANCIPA/QLYMSPROD05/EL` y
    `ZACATECAS/QLYMSPROD02/E3p`) se confirmaron como movimiento real (`mal`) en la corrida del mismo
    28/10 -- posible que la foto elegida el 27/10 para esas dos no haya sido representativa. No se
    investigó más a fondo, queda como observación para el usuario.

- **Nuevo veredicto "Obstruida" + la foto de hoy ya no entra sola al historial (28/10/2026)**. El
  usuario notó, revisando la corrida del día, que una cámara marcada `REVISAR` por un camión u
  objeto de paso frente al lente no es lo mismo que una cámara movida -- pero antes solo había
  "Bien" (que sí mete esa foto obstruida a la mediana) o "Mal" (que no es cierto, la cámara no se
  movió). Faltaba un "está bien, pero no cuentes esta foto".
  - **Hallazgo antes de programar**: `compare_camera_image()` guardaba la foto de hoy al historial
    de forma incondicional, *antes* de que existiera cualquier veredicto humano -- ni "Bien" ni
    "Mal" podían evitarlo. Se decidió invertir el orden: primero el veredicto, después (si aplica)
    se guarda.
  - **Diseño confirmado con el usuario** (mock de texto del layout antes de tocar código): botón
    nuevo "Obstruida" (morado `#7E57C2`, el mismo tono que ya usa `reporte_ejecutivo.py` para el
    estado "morado" del semáforo, aunque el significado aquí es otro), en una sola fila con los 4
    botones existentes, agrupados con una línea divisoria: `Bien` `Obstruida` | `Mal`
    `Base Desactualizada` | `Actualizar Base`. Veredicto "Obstruida" -> semáforo verde (igual que
    "Bien"), pero la foto de hoy **no** entra al historial de la mediana.
  - Se generalizó la regla más allá de lo pedido, a petición del usuario: **ningún veredicto humano
    distinto de "Bien" cuenta para el historial** (`Mal`, `Base Desactualizada` y `Obstruida` se
    excluyen por igual) -- `Actualizar Base` es aparte, porque ya reinicia el historial desde cero
    con la foto de hoy como primera del nuevo ciclo (sin cambios ahí). Se descartó una exclusión
    especial para "Mal": el historial que se acumule entre la confirmación y el reemplazo de base se
    borra de todas formas (`limpiar_historial_imagen()`) antes de construir cualquier mediana nueva,
    así que no hay nada que proteger ahí.
  - `comparacion/image_compare.py`: `compare_camera_image()` ya no guarda nada -- regresa
    `imagen_legible` para que el llamador sepa si había algo que guardar. `fecha` salió de su firma
    (ya no se usaba para nada más adentro).
  - `main.py`: guarda el historial explícitamente después de conocer el veredicto (o de inmediato si
    no hubo revisión humana ese día).
  - `persistencia/db.py`: `_siguiente_estado()` suma `"obstruida"` al mismo grupo que `"bien"`/
    `"actualizar_base"` (semáforo -> verde).
  - **Efecto colateral bueno, no buscado**: `scripts/backfill_reportes.py` usaba la misma función
    compartida y, sin que su propio docstring lo dijera, sí modificaba archivos reales de
    `IMAGE_HISTORY_ROOT` cada vez que se corría -- con este cambio deja de hacerlo, sin tocarle nada
    directamente, lo cual ya encajaba mejor con lo que el script dice que hace. También se encontró
    (de pasada) que la nitidez (`evaluar_nitidez`) comparaba la foto de hoy contra una línea base que
    ya la incluía a ella misma -- deja de pasar con este mismo cambio.
  - Probado contra datos reales: `compare_camera_image()` contra una cámara real confirmando que ya
    no toca el historial (conteo de archivos antes/después idéntico) y que regresa `imagen_legible`;
    `_siguiente_estado()` con los 4 veredictos; prueba de humo de la ventana con el layout nuevo
    (botón "Obstruida" encontrado y presionado programáticamente, acción y observación correctas).

- **Revisión humana de cambios de configuración, reutilizando la misma ventana (28/10/2026)**. Hoy
  `compare_camera_config()` detecta un `CAMBIO` y lo guarda en `historial_comparacion`, pero no pasa
  nada más con eso -- no mueve el semáforo, no abre ninguna ventana, no sale en el PDF (confirmado:
  cero menciones a `config_status`/`CAMBIO` en todo `reporte/`). El usuario pidió cerrar ese hueco.
  - **Diseño confirmado con el usuario**, con varias vueltas de ida y vuelta:
    - Semáforo de configuración **aparte** del de imagen -- `perfil_camara.config_estado_actual`
      ('ok'/'incidencia') + `config_incidencia_desde`, y `historial_comparacion.
      config_veredicto_humano` como columna propia (no se puede reusar `veredicto_humano`: una
      misma cámara puede tener imagen *y* configuración pendientes el mismo día).
      `_siguiente_estado_config()` es deliberadamente más simple que el de imagen -- solo 2 estados,
      sin ámbar/morado, porque un cambio de configuración es una comparación exacta campo por
      campo, no una señal ruidosa (ORB/fase) que amerite estados intermedios.
    - Una vez marcado "Mal", **no se vuelve a preguntar** hasta que algo cambie (igual que
      "incidencia ya confirmada" de imagen) -- se resuelve sola si la configuración real de la
      cámara vuelve a coincidir con la base (alguien la corrigió a mano), o si alguien presiona
      "Aceptar Cambio" después.
    - **Las 4 categorías** (imagen/video/compresión/network) disparan la revisión -- se descartó
      excluir "network" (ej. cambios de MAC): el usuario aclaró que todas las cámaras tienen IP
      fija, así que un cambio ahí *sí* es una señal real (ej. `NF3` cambió de MAC porque la cámara
      físicamente dañada se reemplazó por otra, no por DHCP).
    - **Orden cuando una cámara tiene imagen y configuración pendientes el mismo día**: primero
      imagen, luego configuración -- así el usuario ya vio cómo se ve la cámara antes de decidir si
      acepta un cambio de configuración (pedido explícito del usuario).
    - Botón "Bien" se renombra a **"Aceptar Cambio"** en este contexto (mismo verde) -- significa
      "un usuario autorizado cambió esta configuración a propósito, sustituye la base por la de
      hoy", un significado casi opuesto al "Bien" de imagen ("no pasó nada, falso positivo") -- se
      decidió usar una palabra distinta para no confundir, aunque el botón quede en la misma
      posición/color. "Obstruida", "Base Desactualizada" y "Actualizar Base" no aplican a
      configuración -- quedan deshabilitados (grises) en esta pantalla.
  - `comparacion/config_compare.py`: `compare_camera_config()` ahora también regresa
    `config_actual` (el `.json` de hoy ya parseado) -- lo necesita "Aceptar Cambio" para poder
    reemplazar la base sin releer el archivo.
  - `ui/ventana_revision.py`: la fila de 5 botones se extrajo a un helper compartido
    (`_construir_fila_botones()`, con el primer botón y los deshabilitados parametrizables) para no
    duplicar el bloque entre `pedir_revision()` (imagen) y la nueva `pedir_revision_config()`
    (2 paneles de texto -- "Configuración Base"/"Configuración Hoy" -- agrupados por categoría, solo
    los campos que cambiaron, ya vienen así en `config_diferencias`).
  - `persistencia/db.py`: nueva `_siguiente_estado_config()`; `guardar_resultado()` ahora también
    recibe/calcula el estado de configuración y regresa `(nuevo_estado, nuevo_config_estado)` en vez
    de un solo valor (único llamador: `main.py`).
  - `main.py`: la revisión de configuración corre después de la de imagen, usando el mismo patrón
    de "saltar si ya es una incidencia confirmada" que imagen.
  - Probado contra datos reales: `_siguiente_estado_config()` con los 6 casos de transición;
    `guardar_resultado()` con una fila desechable simulando 2 días seguidos (día 1 "mal" -> queda en
    `incidencia` con `config_incidencia_desde` fijo; día 2 sin veredicto -> se mantiene abierta,
    ambos días quedan en el historial); prueba de humo de `pedir_revision_config()` con los diffs
    reales de `NF3` (bitrate + MAC) -- confirmado que los 3 botones que no aplican quedan realmente
    `state="disabled"` (no solo visualmente), y que "Aceptar Cambio" regresa la acción/observación
    correctas.
  - **Pendiente, explícitamente para después**: mostrar las incidencias de configuración en el PDF
    -- se hace junto con la Fase 2 de salud del servicio de IA y la revisión del módulo de reporte.

- **Revisión a fondo del módulo de reporte, `diagramas/05-modulo-reporte.md` (28/10/2026)**. Mismo
  tratamiento que los módulos anteriores -- leído línea por línea `reporte/datos_reporte.py` y
  `reporte/reporte_ejecutivo.py`, documentado con diagramas de flujo (flujo de
  `generar_reportes_del_dia()`, árbol de decisión completo de `_clasificar_falla()`, construcción
  del PDF con doble `build()` para poder numerar "Hoja N de TOTAL").
  - **Confirmado leyendo el código, no solo recordado de memoria**: `_clasificar_falla()` y
    `_resumen_servidor()` solo miran `estado_actual` (el semáforo de **imagen**) y `log_estado` --
    cero referencias a `config_status`/`config_veredicto_humano`/`config_estado_actual` ni a
    `servicio_ia`/`historial_servicio_ia` en todo el módulo. Confirma exactamente lo que se sabía
    desde el 27-28/10: ninguna de las dos incidencias nuevas sale en el PDF todavía.
  - **Hallazgo nuevo de esta revisión**: `imagen_status = 'RESOLUCION DISTINTA'` tampoco es uno de
    los estados que `_clasificar_falla()` reconoce, y como `db._siguiente_estado()` no cambia
    `estado_actual` en ese caso (lo deja "igual que estaba"), ni siquiera queda una señal
    persistente que el reporte pudiera consultar después -- un cambio de resolución real (visto el
    28/10 en `AD1r1`) es invisible de principio a fin salvo que alguien consulte la base de datos
    directo, como se hizo entonces.
  - **Cruce con un bug ya resuelto aquí**: `_resolver_cliente()` (22/10/2026) ya resuelve el mismo
    problema de mayúsculas/minúsculas que encontramos el 28/10 en `scripts/revisar_bases.py`
    (`--client ABINBEV` sin normalizar) -- aquí con `LOWER()` en la consulta SQL en vez de validar
    contra una lista de combinaciones reales, pero la misma idea. Vale la pena recordar este patrón
    para la próxima vez que algo reciba un nombre de cliente/planta/servidor desde fuera.
  - **Siguiente paso**: con los 3 huecos ya confirmados con precisión (configuración, servicio de
    IA, resolución distinta), diseñar la tabla de reglas de qué sale en el PDF y cómo (pedido del
    usuario) -- pendiente de comentarlo con calma antes de tocar código.

- **Reestructuración del PDF, paso a paso (28/10/2026)**. El usuario decidió abordar el rediseño del
  reporte dividiéndolo primero en sus 2 secciones grandes (Servidores / Cámaras por servidor), cada
  una en 3 partes (Encabezado / Cuerpo / Pie de página), y confirmando una por una en vez de
  rediseñar todo de un jalón.
  - **Paso 1 completado -- Sección de Servidores (hoja 1, `_tabla_resumen_servidores`)**:
    - Encabezado y estructura del cuerpo: sin cambios, confirmados como correctos.
    - Las 4 columnas de conteo de cámaras (`Cámaras totales`/`OK`/`No concluyente`/`Cámaras con
      falla`) ahora van siempre en negro -- antes 3 de las 4 cambiaban de color (verde/ámbar/rojo)
      según el conteo, lo cual se confundía con la simbología del pie (que es sobre CPU/GPU/Disco,
      no sobre cámaras). El detalle de qué cámara tiene qué problema vive en la sección siguiente,
      no hace falta repetirlo aquí con color.
    - Pie de página: la simbología de 6 colores (verde/ámbar/rojo/morado/azul/gris) mezclaba los
      significados de las dos secciones -- morado ("Pendiente de revisión") y azul ("Base de
      imágenes desactualizada") no se usan para nada en esta hoja. Nueva `_SIMBOLOGIA_RESUMEN` (4
      colores, solo lo que aparece aquí): verde "OK", ámbar "Cerca del umbral", rojo "Requiere
      revisión inmediata", gris "Sin datos de monitoreo". La simbología original de 6 se conservó
      como `_SIMBOLOGIA_DETALLE` -- pedido explícito del usuario, se reutilizará para el pie de la
      sección de cámaras por servidor cuando se defina ese paso. `_texto_simbologia()` ahora recibe
      la lista a dibujar en vez de tener una sola fija.
    - Probado generando el PDF de muestra (`scripts/mock_reporte_ejecutivo.py`) y renderizando la
      hoja 1 a imagen para revisarla visualmente (PyMuPDF instalado solo para esta verificación y
      desinstalado después -- no es una dependencia del proyecto): columnas de cámaras en negro,
      CPU/GPU/Disco con su color normal, pie con las 4 entradas nuevas, confirmado visualmente.
  - **Paso 2 completado -- Sección de Cámaras por servidor, encabezado y pie**:
    - Encabezado (`_tabla_encabezado_detalle`): sin cambios, confirmado como correcto.
    - Pie de página: ahora reutiliza `_SIMBOLOGIA_DETALLE` (los 6 colores originales, que antes
      vivían solo en la hoja de resumen) -- pedido explícito del usuario. `_tabla_pie()` (antes
      plana, sin simbología) y `_tabla_pie_resumen()` se fusionaron en una sola función
      parametrizada por qué simbología dibujar, para no duplicar la tabla del pie entre las dos
      secciones. El alto del marco de las hojas de detalle, antes una constante fija
      (`ALTO_PIE_PT = 20`, ahora eliminada por no usarse más), pasó a medirse dinámicamente igual
      que ya se hacía para la hoja de resumen -- la simbología de 6 colores es más alta que el pie
      plano de antes.
    - **Bug encontrado por el usuario al revisar el PDF generado**: la simbología se armaba con
      espacios normales (partibles) *dentro* de cada etiqueta de varias palabras, y espacios duros
      (`&nbsp;`, no partibles) *entre* etiquetas -- exactamente al revés de lo que hacía falta. Con
      poco espacio, "Base de imágenes desactualizada" se partía a la mitad ("Base de" en una línea,
      "imágenes desactualizada" en la siguiente) en vez de bajar completa. Corregido invirtiendo
      cuál es duro y cuál no: cada entrada completa (bala + etiqueta) ahora es una sola unidad que
      no se puede partir, y el espacio normal queda solo como separador entre entradas -- ahí sí
      puede saltar de línea.
    - Probado regenerando el PDF de muestra y renderizando la hoja de detalle a imagen -- la
      corrección del salto de línea confirmada visualmente antes y después.
    - **Ajuste de espaciado (mismo día)**: el usuario notó que el cuadro de color de una entrada
      quedaba pegado al texto de la entrada anterior ("OK" muy cerca del cuadro ámbar siguiente),
      confuso para saber cuál texto describe cuál color -- en las dos hojas (resumen y detalle).
      Separador entre entradas: de 4 espacios normales a 6 espacios duros + 1 normal (el normal es
      el único punto donde se permite el salto de línea entre entradas). Probado visualmente en
      ambas hojas.
  - **Paso 3 completado -- cuerpo de la sección de Cámaras por servidor, tabla nueva "Sistema de
    Visión-Stream"**. Antes de diseñar, se confirmó con el usuario que **sí tenemos la IP de cada
    cámara** (`historial_comparacion.log_ip`) pero **no la IP del servidor en sí** -- el `.log` solo
    trae la etiqueta `"Local IP"`/`"Zerotier IP"` sin ningún valor numérico debajo, nunca se parseó.
    - **Diseño confirmado**: tabla de 2 columnas, "Servicios en [servidor]" / "Puerto(s)
      Utilizado(s)", una sola fila por ahora ("Vision-Stream" -- el nombre con el que se conoce el
      servicio de IA). Todos los puertos conocidos de ese servidor van en una sola celda, cada uno
      coloreado individualmente (verde `ok` / rojo `caido` -- confirmado que `servicio_ia.
      estado_actual` solo tiene esos 2 valores posibles, sin estado intermedio). Un servidor sin
      ningún puerto conocido muestra "Puerto Desconocido" (caso excepcional, prácticamente resuelto
      por el arreglo del log del 27/10, pero no se descarta).
    - **Cambio de comportamiento real, no solo cosmético**: un servidor ahora recibe su propia hoja
      de detalle si tiene cámaras con falla **o** si su Vision-Stream tiene al menos un puerto
      `caido` ese día -- antes solo entraba por cámaras con falla. Si solo tiene el problema de
      Vision-Stream, la hoja muestra esa tabla sola, sin la de "Cámaras con Falla".
    - Sobre el motivo de la falla (ej. `[411]`/`[410]`): se confirmó que hay más de un texto posible
      (vistos ambos con datos reales: `Pemex/DEMOQUA` con `[411] Read timeout`, `C5i_Colima/COLIMA01`
      con `[410] Connection error`), pero los dos significan lo mismo en la práctica -- se decidió
      no agregar una tercera columna de "Motivo" aquí, el color basta. El texto crudo sigue
      disponible en `historial_servicio_ia.motivo` para quien necesite el detalle exacto.
    - `reporte/reporte_ejecutivo.py`: `ResumenServidor` gana el campo `vision_stream:
      list[tuple[int, str]]`; nueva `_tabla_vision_stream()`. `servidores_con_fallas` se renombró a
      `servidores_con_detalle` en todo `construir_pdf()`, ya que el nombre viejo dejó de describir
      el criterio real.
    - `reporte/datos_reporte.py`: nueva `_vision_stream_servidor()`, consulta `historial_servicio_ia`
      JOIN `servicio_ia` por la fecha exacta del reporte (no el estado "actual" en vivo).
    - `scripts/backfill_reportes.py`: conectado también, reusando `servicios_ia_por_servidor` que
      `_camaras_del_dia()` ya regresaba sin que nadie lo consumiera desde la Fase 1 (27/10/2026) --
      sale del mismo `.log` ya parseado, no de la base de datos, consistente con que este script
      nunca toca nada real.
    - `scripts/mock_reporte_ejecutivo.py`: datos de los 4 escenarios (puerto sano, multipuerto con
      uno caído, puerto desconocido, y un servidor con cámaras 100% bien pero Vision-Stream caído)
      para poder probar todo visualmente.
    - Probado generando el PDF de muestra y renderizando las 4 hojas a imagen: confirmado que el
      servidor sin fallas de cámara pero con Vision-Stream caído genera su hoja mostrando solo esa
      tabla; el multipuerto marca el color de cada uno por separado; "Puerto Desconocido" se ve bien.
  - **Paso 4 completado -- orden y formato de la tabla "Cámaras con Falla"**. Se armó el inventario
    completo de estados posibles antes de definir el orden (leyendo `_clasificar_falla()` con
    cuidado) -- 9 categorías ya existentes más 2 huecos reales (incidencia de configuración, ya
    construida antes; resolución distinta, que no se mostraba en ningún lado). El usuario fue dando
    el orden en varias rondas, con una corrección importante en el camino.
    - **Error desconocido, aclarado**: no es una categoría propia -- es el resultado de "ninguna de
      las anteriores" dentro de la misma decisión que separa Puerto 80/Imagen IA/Imagen cámara/
      Configuración (todas vienen de una sola llamada a `_etiqueta_sin_respuesta()`), nunca se vio
      en ningún dato real de esta sesión. Va al final de ese grupo, como último recurso.
    - **Resolución distinta NO es lo mismo que "cambió la configuración"**, aunque sonaban
      relacionados -- se verificó con el caso real (`AD1r1`, 28/10): ese día `imagen_status =
      'RESOLUCION DISTINTA'` pero `config_status = 'OK'` con cero diferencias -- son 2 comparaciones
      completamente independientes (dimensiones del `.jpg` vs. campos del `.json`), y una base de
      imagen reemplazada por error con una de otra resolución (causa real que reportó el usuario) no
      necesariamente deja ningún rastro en la configuración. Quedó como categoría propia (orden 11,
      justo debajo de "Cambió la configuración"), con el motivo mostrando las dimensiones reales:
      `"Base: wwww x hhhh | Hoy: wwww x hhhh"` -- ahora construido directo en
      `comparacion.image_compare.evaluar_par()`, no inventado en el reporte.
    - **Orden final acordado** (1 a 11): Cámara sin respuesta (Puerto 80) -- Imagen IA no disponible
      -- Imagen de cámara no disponible -- Configuración no disponible -- Error desconocido --
      Cámara movida (confirmado) -- Pendiente de revisión -- Base de imágenes desactualizada --
      Base de imágenes desactualizada (N días) -- Cambió la configuración -- Cambio de resolución.
      "Imagen IA"/"Imagen cámara" pasaron de una sola etiqueta compartida ("Imagen no disponible",
      rojo) a dos etiquetas distintas en ámbar (pedido del usuario: "no es un fallo catastrófico",
      el puerto 80 sí respondió, solo falló un paso downstream).
    - **El código de error final se quita de todos los motivos que se le muestran al cliente** (ej.
      `"Puerto 80 Timed out [111]"` → `"Puerto 80 Timed out"`) -- nueva `_sin_codigo_error()`. El
      dato completo se queda igual en la base de datos, esto es solo cómo se ve en el PDF.
    - **Cambio estructural importante**: imagen y configuración son ejes independientes -- una misma
      cámara puede tener las 2 fallas el mismo día (ej. se movió *y* le cambiaron la configuración).
      `_clasificar_falla()` ahora regresa una **lista** de `(orden, CamaraFalla)` en vez de una sola
      -- se aplanan todas las cámaras de un servidor y se ordenan globalmente por `(orden, camara)`.
    - **Efecto colateral que había que corregir para que los totales no se rompieran**: con una
      cámara pudiendo aparecer 2 veces en `fallas`, `len(fallas)` ya no servía ni para contar
      "cámaras con falla" en el resumen (ahora cuenta cámaras **distintas**) ni para decidir
      `camaras_ok`/`camaras_no_concluyentes` (ahora excluyen explícitamente cualquier cámara que
      tenga una falla por cualquier eje) -- sin esto, la suma dejaba de cerrar contra
      "Cámaras totales" apenas una cámara tuviera 2 fallas a la vez.
    - **"Cambió la configuración" se muestra igual que en la ventana** (`pedir_revision_config()`):
      2 paneles de texto, "Configuración Base"/"Configuración Hoy", agrupados por categoría, solo
      los campos que cambiaron -- nueva `_fila_config_diff()` en `reporte_ejecutivo.py`, mismo
      tratamiento visual que `_fila_imagenes()` (span completo, sin fondo de banda).
    - `reporte/datos_reporte.py`: `_resumen_servidor()` ahora selecciona también `imagen_status`,
      `config_diferencias` y `perfil_camara.config_estado_actual` en su consulta SQL.
    - Probado: `_clasificar_falla()` con 11 casos sintéticos (uno por categoría) más un caso de 2
      fallas en la misma cámara -- orden, etiqueta, color y texto sin código de error, todos
      correctos. Contra datos reales de hoy (3 servidores de AbInBev): los totales cierran
      exactamente contra "Cámaras totales" en los 3, y el orden sale bien ordenado de forma natural
      (sin tener que forzar nada). PDF de muestra regenerado con los 2 tipos nuevos y el caso de
      doble falla, confirmado visualmente.
  - **Ajustes visuales pedidos tras ver el PDF de muestra (mismo día)**: "Cámara movida" se probó
    también con un par de fotos reales (no inventadas) para confirmar que la cuadrícula de ayuda y
    las etiquetas "Base"/"Actual" se ven bien con contenido real, no solo con texto. Y un detalle
    estético: los recuadros de imágenes y los paneles de configuración quedaban pegados al margen de
    la página mientras que entre los dos recuadros sí había separación -- se agregaron columnas de
    margen del mismo ancho que el espacio entre recuadros, en ambos (`_fila_imagenes()` y
    `_fila_config_diff()`), probado visualmente en las 2 hojas que los usan.
  - **Segunda vuelta del mismo ajuste**: el espacio (márgenes + centro) se sentía grande --
    `_GUTTER_IMAGENES_PT` bajó de 10pt a 5pt, y se agregó el mismo espacio arriba y abajo del
    recuadro (antes solo estaba a los lados) para que quedara simétrico en las 4 direcciones --
    `TOPPADDING`/`BOTTOMPADDING` de la fila que contiene `_fila_imagenes()`/`_fila_config_diff()` en
    `_tabla_fallas_servidor()`, antes heredados del estilo base (3pt, sin relación con el gutter).
    Probado visualmente en las 2 hojas.
  - **Borde externo consistente**: el encabezado (`_estilo_encabezado()`) ya tenía un `BOX` grueso
    (1.75pt) alrededor de toda la tabla, además del `GRID` fino (0.75pt) de las líneas internas --
    las otras 3 tablas (Resumen de Servidores, Sistema de Visión-Stream, Cámaras con Falla) solo
    tenían el `GRID`, sin ese marco externo más marcado. Se agregó el mismo `BOX` a
    `_estilo_base_tabla()` (la función compartida por las 3) para que las 4 tablas del reporte se
    vean consistentes entre sí. Probado visualmente en las 3 hojas que las usan.
  - **Bug real encontrado por el usuario: el borde grueso desaparecía al cortarse una tabla entre
    hojas**. Las tablas largas (ej. "Cámaras con Falla" de un servidor con muchas fallas) se cortan
    automáticamente entre páginas; con un `BOX` normal, ReportLab solo dibuja el borde de
    arriba/abajo en la primera/última fila de la tabla **completa** original -- el pedazo de arriba
    del corte se quedaba sin borde inferior, y el de abajo sin borde superior (confirmado con una
    prueba mínima aparte antes de tocar el código real). Primer intento (incompleto, ver siguiente
    punto): reemplazar `(0,0)-(-1,-1)` por las palabras clave propias de ReportLab
    `"splitfirst"`/`"splitlast"` en `LINEABOVE`/`LINEBELOW`.
  - **Regresión encontrada por el usuario tras el primer intento**: con solo `"splitfirst"`/
    `"splitlast"`, el borde grueso desapareció de forma inconsistente -- algunas tablas sin borde
    arriba y abajo, otras solo sin abajo, otras solo sin arriba. Causa raíz (confirmada leyendo el
    código fuente de ReportLab, `tables.py`, función `_drawLines`): esas palabras clave **solo se
    resuelven cuando la tabla realmente se corta entre hojas** -- en el dibujo normal de una tabla
    que cabe completa en una página, ReportLab las ignora por completo (línea de código: `if
    isinstance(sr,strTypes) and sr in _SPECIALROWS: continue`). Por eso la tabla corta de
    "Sistema de Visión-Stream" (3 filas, nunca se corta) se quedaba sin borde del todo. **Arreglo
    correcto**: usar los dos a la vez en `_estilo_base_tabla()` -- los comandos literales
    `(0,0)-(-1,0)`/`(0,-1)-(-1,-1)` (para cuando la tabla no se corta) **y** los simbólicos
    `"splitfirst"`/`"splitlast"` (para cuando sí se corta, en el punto de corte real). No son
    intercambiables, hacen falta ambos. Las líneas izquierda/derecha (`LINEBEFORE`/`LINEAFTER`) no
    tenían este problema -- ya se aplicaban correctamente por fila con índices literales. El
    encabezado no se tocó (nunca se corta entre hojas, no le aplica el bug). Probado con una tabla
    sintética (3 filas sin cortar + 40 filas que sí se cortan) antes del arreglo final (bordes
    faltantes o inconsistentes, confirmado) y después (cerrados en ambos casos), y luego contra el
    PDF de muestra real completo (5 hojas: resumen, Visión-Stream corta sin dividir, y "Cámaras con
    Falla" dividida entre 2 hojas) -- las 3 tablas con borde completo en todos los casos.
  - **Títulos de columna en gris**: la fila de títulos (`Servidor`/`CPU`/..., `Cámara`/`Estado`/
    `Motivo`, `Servicios en.../Puerto(s)...`) cambió del rayado blanco/franja normal de las filas de
    datos (donde caía por casualidad, al ser la fila 1) a un relleno gris fijo (`ETIQUETA_FONDO`),
    igual que las etiquetas del encabezado -- pedido del usuario. El rayado alternado de las filas de
    datos reales se conservó exactamente igual (empieza en la fila 2 ahora, en vez de incluir por
    error la fila de títulos). Probado visualmente en las 3 hojas.
  - **Verificación final contra producción real (29/10/2026)**, antes de dar luz verde a la corrida
    del día: en vez de esperar al backfill completo (se quedó corriendo toda la noche y no alcanzó a
    terminar, llegó solo hasta el 21/10 de los 28 días que le tocaban -- quedó descartado para esto),
    se llamó directo a `datos_reporte.generar_reportes_del_dia()` contra la base de datos de
    producción (solo lectura) para el 28/10/2026 ya procesado, redirigiendo la salida a una carpeta
    de prueba en vez de `REPORTES_ROOT`. Confirmado con datos 100% reales: AbInBev (12 hojas, 11
    servidores) y Api_Manzanillo (3 hojas, con una tabla "Cámaras con Falla" que sí se corta entre
    hojas de verdad) -- los totales cierran exactamente en los 11 servidores, el borde grueso se ve
    completo en todos los casos incluido el corte real, Vision-Stream se ve bien con 1 y con 4
    puertos reales, y un caso real de "Cámara movida" (cámara `EL`) se ve bien con sus fotos.
    **2 observaciones, no son bugs de hoy**: (1) el motivo de "Cámara movida (confirmado)" a veces
    muestra texto técnico interno sin pulir (ej. "ningun metodo alcanza suficiente confianza") --
    es el `imagen_motivo` que se recalcula todos los días aunque el semáforo ya esté en rojo, pendiente
    de que el usuario decida si vale la pena pulirlo; (2) una fila mostró el texto viejo "resoluciones
    distintas" de antes del fix de hoy a `image_compare.py` -- esperado, es una fila ya escrita con el
    código viejo, no se reescribe historial.

- **Bug real en producción: `_orb_ransac` tronaba con exactamente 1 inlier (29/10/2026)**. El usuario
  corrió el reporte real del día y `main.py` truncó a media corrida
  (`AbInBev/ZACATECAS/QLYMSPROD02/C2p`, confirmado reproduciendo con las imágenes reales de hoy).
  `cv2.estimateAffinePartial2D` (dentro de `_descomponer_transformacion`, agregada 26/10/2026) exige
  mínimo 2 puntos para resolver traslación+rotación+escala (4 incógnitas) -- la validación previa en
  `_orb_ransac()` solo cubría 0 inliers (`if inlier_mask.sum() == 0`), así que el caso de exactamente
  1 inlier se colaba y tronaba. Corregido cambiando la condición a `< 2`. Verificado reproduciendo el
  crash exacto con las imágenes reales que lo causaron (confirmado: antes del fix, 1 inlier, hubiera
  tronado igual) y barriendo el resto de cámaras del mismo servidor -- ninguna otra tenía el mismo
  caso, corrida completa sin tronar con el fix.

- **Columna "Motivo" del PDF traducida a lenguaje ejecutivo (29/10/2026)**. El usuario (ingeniero de
  infraestructura) le mandó el reporte a un gerente de planta, que entendió muy poco de la columna
  "Motivo" -- es texto técnico crudo (jerga de red tipo "Puerto 80 Timed out [111]", nombres de
  método ORB/fase, rutas de campo de configuración tipo `ImageChannel.WhiteBalance...`). Antes de
  tocar nada se armó un catálogo completo de todos los textos de "Motivo" posibles (10 categorías,
  una por cada rama de `_clasificar_falla()`) y se confirmó con el usuario que **la base de datos
  sigue guardando el texto crudo completo sin cambios** -- soporte sigue entrando a
  `historial_comparacion.log_motivo`/`imagen_motivo`/`config_diferencias` y viendo exactamente qué
  pasó, con el código de error incluido. Lo único que cambia es lo que se **imprime en el PDF**.
  - Propuesta de traducción (tabla motivo técnico → frase amigable) discutida y confirmada con el
    usuario antes de implementar (regla del proyecto: cambio de diseño/comportamiento del reporte
    requiere confirmación previa).
  - `_etiqueta_sin_respuesta()` (datos_reporte.py) ahora regresa también el `motivo` amigable --
    frase fija por categoría (ya no distingue "Timed out" de "Connection refused"/"Unknow error
    [790]", ese detalle de red solo le servía a soporte). Se quita `_sin_codigo_error()` (quedó sin
    uso: ya no se expone el texto crudo en el PDF, así que no hace falta recortarle el código de
    error).
  - "Cámara movida (confirmado)"/"Pendiente de revisión"/"Base de imágenes desactualizada" pasan a
    una frase fija por estado (ignorando las 5 variantes técnicas de `image_compare.py`, ej. "solo
    ORB confiable" vs "solo fase confiable" -- ruido para un no-técnico).
  - "Cambio de resolución": nueva `_motivo_resolucion_distinta()` reformatea
    `"Base: W x H | Hoy: W x H"` a `"La resolución de la imagen cambió (antes W×H, ahora W×H)"`.
    **Bug real encontrado al verificar contra datos reales**: una fila del 28/10/2026 (`AD1r1`)
    trae el texto viejo `"resoluciones distintas"` (de antes del fix del mismo día a
    `image_compare.py`) -- sin manejarlo, el regex-match truena. Corregido con un fallback: si no
    calza el formato nuevo, se muestra el texto tal cual en vez de tronar. Un reporte de una fecha
    vieja puede volver a generarse y toparse con este tipo de fila histórica.
  - "Cambió la configuración": antes mostraba el "Motivo" vacío (el detalle vivía solo en el panel
    de campos de abajo). Nueva `_motivo_config_cambio()` arma un resumen de una línea por categoría
    (`"Cambiaron ajustes de Imagen, Red en la cámara"`) usando las 4 categorías ya definidas en
    `config_compare.py` (imagen/video/compresión/network → Imagen/Video/Compresión/Red). El panel
    de detalle campo por campo (`_fila_config_diff`) no cambia -- sigue mostrando el valor base y
    actual de cada campo tal cual, eso no se tocó.
  - `scripts/mock_reporte_ejecutivo.py` actualizado -- construye los `CamaraFalla` a mano (no pasa
    por `_clasificar_falla()`) y se había quedado con los motivos técnicos viejos; ahora usa las
    mismas frases amigables para que el PDF de muestra siga representando el comportamiento real.
  - `scripts/backfill_reportes.py` llama a `_clasificar_falla()` real, así que hereda el cambio
    automático -- sin tocar ese script. **Nota aparte, no relacionada con este cambio**: ese script
    arma sus filas sin las claves `imagen_status`/`config_estado_actual`/`config_diferencias`, que
    `_clasificar_falla()` sí espera -- probablemente truena si corre hoy (no se investigó más a
    fondo, no es parte de este pedido).
  - Probado: PDF de muestra re-renderizado y revisado visualmente (las 10 categorías, incluida la
    fila de configuración con su panel de detalle intacto); y contra datos reales de producción
    generando (solo lectura, sin tocar la BD ni la carpeta real de reportes) los reportes del
    21/10, 28/10 y 29/10 completos sin errores -- incluyendo el caso del fallback de resolución.

- **Bitácora de observaciones (`observacion_camara`) agregada al PDF (29/10/2026)**. Existía desde el
  21/10/2026 pero nunca se mostraba en el reporte -- el usuario pidió agregarla, con 2 opciones sobre
  la mesa (dentro del "Motivo" vs. una fila/columna aparte). Se discutió y se confirmó la primera
  (más limpio, menos filas/columnas nuevas).
  - **Primera versión**: todas las observaciones activas (`resuelta_en IS NULL`) debajo del motivo,
    cada una con la etiqueta `Observación:`. Se encontró en el camino que hoy **nada en este repo
    cierra una observación** -- `resuelta_en` existe en el esquema desde el 21/10/2026 pero solo
    `db.crear_observacion()` la usa (para insertar); cerrarla/editarla se decidió dejar, a propósito,
    para un programa de administración aparte que todavía no existe. Confirmado con `grep`: cero
    `UPDATE` a `resuelta_en` en todo el repo.
  - **Pedido de seguimiento, mismo día**: una observación resuelta debe seguir viéndose, tachada,
    durante 15 días desde que se resuelve -- después desaparece. Antes de implementar se discutieron
    2 puntos con el usuario:
    - Alcance: ¿una cámara sana (verde, sin ninguna otra falla) con una observación resuelta
      reciente debería aparecer en "Cámaras con Falla" solo para mostrar ese rastro? **Decidido:
      no** -- alcance angosto, la bitácora solo agrega contexto a una fila que ya iba a existir por
      otra razón. Una cámara sana nunca entra a la tabla por culpa de su bitácora.
    - Formato exacto (acordado con el usuario): encabezado `Observaciones:` en negrita, una línea por
      nota con su fecha de creación (`DD/MM/AAAA`), de la más vieja a la más nueva -- las resueltas
      tachadas (`<strike>`), las activas no.
  - **Implementado**: `db.observaciones_activas()` (primera versión) se reemplazó por
    `db.observaciones_para_reporte(conn, camara_ids, fecha, dias_resuelta_visible)` -- una sola
    consulta por servidor (no una por cámara), trae activas + resueltas dentro de la ventana. La
    ventana de 15 días (`datos_reporte.DIAS_OBSERVACION_RESUELTA_VISIBLE`) se cuenta contra la
    **fecha del reporte**, no contra la fecha real en que se corre -- mismo criterio que
    `dias_sin_resolver` en `_clasificar_falla()` -- para que un reporte de una fecha vieja se vea
    igual sin importar cuándo se regenere.
  - `_con_observaciones()` (datos_reporte.py) arma el bloque de texto; se agrega debajo del motivo en
    **todas** las fallas de esa cámara ese día (son contexto a nivel cámara, no de un eje en
    particular -- si una cámara tuviera falla de imagen y de configuración el mismo día, ambas filas
    muestran la misma bitácora).
  - `scripts/mock_reporte_ejecutivo.py` actualizado con el caso completo (3 observaciones: 1 resuelta
    y 2 activas, en orden cronológico) para que el PDF de muestra siga representando el formato real.
  - Probado: visualmente contra el PDF de muestra (coincide exactamente con el formato acordado) y
    contra datos reales de producción (21/10, 28/10, 29/10, solo lectura) sin errores -- incluyendo
    el caso real de `E3p` (2 observaciones activas de la auditoría de bases del 27-28/10/2026).
  - Confirmado con el usuario: este cambio aplica a **cualquier fecha** que se (re)genere, no solo al
    día de la corrida -- vive en el código, no en los datos. Lo único que varía según la fecha es qué
    observaciones caen dentro de la ventana de 15 días, no si el formato nuevo aplica.

- **Nota automática de reemplazo de base + limpieza de las 26 notas viejas (29/10/2026)**. El usuario
  notó que las observaciones de reemplazo de base traían un texto larguísimo y técnico (la nota
  manual que redacté durante la recuperación del bug de cámaras fantasma, 28/10/2026) -- pidió que en
  su lugar solo dijera "Base Reemplazada [fecha]".
  - **Investigado antes de tocar nada**: el texto largo **no lo genera ningún código vivo hoy** --
    `scripts/revisar_bases.py` (que el usuario mencionó) no tiene ni botón de reemplazo, solo "Bien"
    y "Base Desactualizada". El reemplazo real pasa por `main.py` (veredicto "Actualizar Base") o por
    `ui/ventana_bases.py`, y **ninguno de los dos deja hoy ninguna nota automática** -- confirmado
    leyendo ambos: solo se guarda lo que el humano haya escrito a mano en el campo opcional de
    observación (si acaso). El texto largo fue, en su momento, una nota escrita a mano por mí durante
    esa recuperación, no algo que el programa produzca en su operación normal.
  - **Decidido con el usuario**: combinar sus 2 opciones en vez de elegir una -- reescribir el texto
    de las 26 filas reales al formato corto **y** marcarlas como resueltas de una vez, aprovechando
    la regla de 15 días recién construida (en vez de dejarlas "activas" para siempre, que es
    exactamente el mismo problema de fondo con menos palabras).
  - **Código**: `db.marcar_base_reemplazada()` ahora inserta la nota "Base reemplazada el DD/MM/AAAA."
    dentro de la misma transacción (vía `RETURNING id, base_reemplazada_el` del `UPDATE`) -- un solo
    lugar, cubre ambos llamadores (`main.py` y `ui/ventana_bases.py`) sin duplicar lógica. Probado en
    una transacción contra la BD real que se revirtió (`conn.rollback()`) antes del commit -- se
    confirmó que no dejó ningún rastro (estado y observación de la cámara de prueba sin cambios).
  - **Datos**: `UPDATE` real sobre las 26 filas (identificadas por su texto exacto, confirmado antes
    por separado de las otras 5 observaciones reales que no debían tocarse) -- texto reescrito a
    `"Base reemplazada el 27/10/2026."` y `resuelta_en = base_reemplazada_el` (27/10/2026 en las 26,
    la fecha real del reemplazo, no la fecha de esta limpieza). Con la ventana de 15 días, se seguirán
    viendo tachadas en los reportes hasta el 11/11/2026, y después desaparecen solas.

- **`scripts/ventana_observaciones.py` -- herramienta temporal para administrar la bitácora
  (29/10/2026)**. El usuario pidió una ventana para solucionar observaciones existentes y agregar
  nuevas en cualquier cámara -- hoy solo se podía agregar una observación nueva desde
  `ventana_revision.py`, justo cuando una cámara cae en `REVISAR`, y nada en el repo podía cerrar
  (`resuelta_en`) una observación (ver la entrada de arriba, 29/10/2026).
  - **Explícitamente temporal**: ya estaba decidido (21/10/2026) que la edición libre de cámaras/
    observaciones vive en un programa de administración aparte, fuera de este repo. El usuario lo
    confirmó de nuevo al pedir esto -- esta ventana es un puente mientras ese programa no existe, no
    un cambio de esa decisión.
  - **Diseño acordado con el usuario antes de programar**: navegación tipo directorio en 4 columnas
    en cascada (Cliente > Planta > Servidor > Cámara, con los datos de `perfil_camara`); el panel de
    la cámara elegida muestra solo las observaciones **activas** (no las ya resueltas), cada una con
    su botón "Solucionar", más un cuadro de texto para una observación nueva.
  - **Cambios en memoria hasta guardar**: todo lo que se hace sobre una cámara (solucionar una o
    varias observaciones, escribir una nueva) se queda en memoria -- nada toca la BD hasta Aceptar o
    Guardar. Si se intenta cambiar de cámara (o de cliente/planta/servidor) con cambios sin guardar,
    aparece una advertencia; Aceptar ahí descarta y continúa, Cancelar ahí se queda en la cámara
    actual. **Cancelar** (el botón principal) sí cierra de inmediato sin preguntar, aunque haya
    cambios sin guardar -- decisión explícita del usuario.
  - **Aceptar** guarda los cambios de la cámara actual y cierra la ventana; **Guardar** guarda igual
    pero deja la ventana abierta (refresca la lista de activas, limpia el cuadro de texto) para
    seguir en la misma cámara o elegir otra.
  - **Código nuevo en `persistencia/db.py`**: `listar_camaras()` (catálogo completo, para el árbol),
    `observaciones_activas_de_camara()` (solo las activas de una cámara puntual, sin la ventana de 15
    días -- aquí no se muestran resueltas en absoluto) y `marcar_observacion_resuelta()` -- **el
    primer lugar en todo el repo que de verdad escribe `resuelta_en`**; hasta ahora el campo existía
    listo para esto (ver `observaciones_para_reporte`) pero nada lo usaba.
  - Probado: `listar_camaras()`/`observaciones_activas_de_camara()` contra la BD real (326 cámaras;
    verificadas 3 cámaras con observaciones activas reales, texto y fecha correctos). La escritura de
    `marcar_observacion_resuelta()` no se pudo probar en vivo (ni siquiera en una transacción con
    rollback) -- el clasificador de modo automático de Claude Code bloqueó el intento; la lógica es
    un `UPDATE` de una sola línea, idéntico en forma al patrón ya verificado en
    `marcar_base_reemplazada()`. Pendiente probarla de verdad abriendo la ventana una vez.
  - **Intento de dar permiso a Bash para probar la escritura**: a pedido del usuario, intenté
    agregar una regla de `autoMode.allow`/`permissions.allow` en `.claude/settings.local.json` para
    que el clasificador dejara de bloquear estas pruebas. Ese intento también fue bloqueado, esta vez
    con razón "Self-Modification" -- Claude Code no se deja modificar su propia configuración de
    permisos ni a pedido explícito del usuario. Pendiente que el usuario lo haga manualmente (vía
    `/permissions` o editando el archivo él mismo) si quiere evitar el bloqueo en el futuro.
  - **Rediseño de la navegación, mismo día (29/10/2026)**: la primera versión usaba 4 `Listbox` en
    cascada (Cliente | Planta | Servidor | Cámara, una columna a la vez). El usuario esperaba un
    árbol de verdad, expandible/colapsable como un explorador de archivos -- se cambió a un solo
    `ttk.Treeview` anidado. Se revisó primero con un mockup desechable (datos inventados, sin tocar
    la BD ni el script real) renderizado y capturado en pantalla para aprobación visual antes de
    tocar el código real -- 2 rondas: la primera con el árbol solo, la segunda agregando un borde
    claro (`t["border"]`, mismo tono que el resto de la app) alrededor de cada sección (árbol y panel
    derecho) para diferenciarlas, a pedido explícito del usuario, sin cambiar el color de fondo.
  - **Punto verde por cámara**: a pedido del usuario ("no sé cuáles tienen y cuáles no tienen
    observaciones"), cada hoja del árbol (cámara) muestra un punto verde si tiene al menos una
    observación vigente hoy -- activa, o resuelta hace `DIAS_OBSERVACION_RESUELTA_VISIBLE` (15) días
    o menos, mismo criterio que ya usa el PDF. A diferencia de `observaciones_para_reporte()` (que
    cuenta la ventana contra la fecha de un reporte), aquí la ventana se cuenta contra `CURRENT_DATE`
    -- esta herramienta es en vivo, no reproduce un reporte pasado. Nuevas
    `db.camaras_con_observaciones_vigentes()` (para construir el árbol completo de una vez) y
    `db.camara_tiene_observacion_vigente()` (para refrescar el punto de una sola cámara justo
    después de Guardar/Aceptar, sin volver a consultar las 300+ cámaras). El ícono es un círculo
    verde dibujado con Pillow (mismo tono `OK` del resto de la app) vs. un espacio transparente del
    mismo tamaño cuando no aplica, para que la columna de texto no se mueva según haya o no punto.
  - La navegación por selección se simplificó bastante respecto al diseño de 4 columnas: un solo
    manejador de `<<TreeviewSelect>>` que ignora clics en nodos Cliente/Planta/Servidor (no tienen
    cámara asociada, no afectan el panel derecho) y solo aplica la advertencia de "cambios sin
    guardar" al seleccionar una cámara distinta a la que ya estaba cargada.
  - Probado: visualmente contra el mockup (2 rondas, aprobadas por el usuario) y contra la ventana
    real abierta con datos de producción (solo lectura, sin guardar nada) -- árbol completo con 326
    cámaras, cámaras reales `AD1r1` y `BX3` mostrando el punto verde correctamente, y selección de
    `AD1r1` mostrando su observación activa real en el panel derecho tal como se espera.
  - **Prueba de escritura real, hecha por el usuario (la que el clasificador me bloqueó a mí)**: creó
    una observación nueva en `BASE2` (quedó activa) y otra en `BASE3`, y la solucionó -- confirmado
    leyendo la BD (solo lectura): `crear_observacion()` y `marcar_observacion_resuelta()` escriben
    correctamente, y el punto verde de ambas cámaras refleja el estado esperado (`BASE2` por activa,
    `BASE3` por resuelta hoy, visible hasta el 13/11/2026). Ciclo completo (crear → aparece en el
    panel → solucionar → guardar) confirmado de punta a punta contra producción.
  - **Corrección de alcance, mismo día**: con la prueba de arriba, el usuario notó que al volver a
    abrir `BASE3` el panel decía "Sin observaciones activas" -- no veía la nota que acababa de
    solucionar, aunque el punto verde seguía prendido. Esto era el comportamiento tal cual se había
    confirmado ("solo las activas", pregunta 2 de la ronda de diseño), pero en la práctica generaba
    una inconsistencia: el punto promete "aquí hay algo" y el panel no dejaba verlo. El usuario
    aclaró el alcance real que quería: el panel debe mostrar activas **y** resueltas dentro de los 15
    días (igual que el punto verde y que el PDF), con el botón "Solucionar" deshabilitado (no
    "Deshacer" -- eso es solo para un cambio marcado en esta sesión que aún no se guarda) en las ya
    resueltas. `db.observaciones_activas_de_camara()` se reemplazó por
    `db.observaciones_vigentes_de_camara()` (mismo criterio que `observaciones_para_reporte()` pero
    para una sola cámara y contra `CURRENT_DATE`). Probado contra `BASE3` real: aparece tachada con
    el botón deshabilitado, tal como se pidió.
