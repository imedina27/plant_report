# captura.py

Captura una imagen directo de una cámara (AXIS, DAHUA, HIKVISION o VIVOTEK), para usarla como base
limpia en `ventana_bases.py` de Plant_Report — útil cuando se necesita tomar la foto en el momento
exacto en que la cámara se ve limpia (sin camión/montacargas en cuadro), en vez de esperar a que la
corrida automática del día traiga una imagen útil.

Carpeta independiente a propósito: se copia completa a cada servidor donde haga falta, sin depender
del resto del proyecto Plant_Report ni de su entorno (Pipenv).

## Instalación

Requiere Python 3.10 o más reciente, y una sola dependencia externa:

```powershell
pip install requests
```

No hace falta nada más (`argparse`, `pathlib`, `datetime` son de la librería estándar).

## Uso

```powershell
python captura.py <ip> <usuario> <password> <marca>
```

- `marca`: una de `AXIS`, `DAHUA`, `HIKVISION`, `VIVOTEK` (no distingue mayúsculas/minúsculas).
- Debe correr con acceso directo a la cámara (red de la planta/servidor), no a través de túneles.

La imagen se guarda en `images/<ip>/<timestamp>.jpg`, dentro de esta misma carpeta (sin importar
desde dónde se invoque el comando).

Ejemplo:

```powershell
python captura.py 192.168.20.31 admin "laContraseña" HIKVISION
```

```text
OK -- 182 KB guardados en images/192.168.20.31/20261003_193045.jpg
```

## Agregar una marca nueva

1. Crear `cameras/<marca>.py` con una función `capturar(ip: str, usuario: str, password: str) ->
   bytes` que regrese los bytes del JPEG (ver `cameras/hikvision.py` como ejemplo simple).
2. Registrarla en `cameras/__init__.py`, agregando una línea a `CAPTURA_POR_MARCA`.

No hace falta tocar `captura.py` ni las demás marcas.
