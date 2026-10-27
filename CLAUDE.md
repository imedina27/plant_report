# CLAUDE.md

Instrucciones para trabajar en **Plant Report** con Claude Code. Esto se sube a git -- es para
cualquiera que trabaje en el proyecto, no solo para Ismael (ver `CLAUDE.local.md`, no versionado,
para lo específico de su máquina).

## Fuente de verdad

- **[ROADMAP.md](ROADMAP.md)** es la fuente de verdad del proyecto: decisiones de diseño,
  experimentos, y el estado real de cada fase. Léelo antes de proponer próximos pasos -- en
  particular su checklist de estado.
- **[README.md](README.md)** es la guía práctica de instalación/uso. Debe reflejar el
  comportamiento real del programa, no el histórico -- a diferencia del ROADMAP, que sí es un
  registro histórico.
- **[CHANGELOG.md](CHANGELOG.md)** es el registro breve y cronológico de qué cambió y cuándo. El
  *por qué* de cada cambio vive en el ROADMAP, no aquí -- el CHANGELOG es solo para ubicar rápido
  cuándo pasó algo.
- **`diagramas/`** contiene diagramas de flujo en Mermaid (uno por módulo o punto de entrada),
  usados para planear la posible reescritura del programa ("v2").

## Después de cada cambio de código

- **Siempre** actualiza `ROADMAP.md` después de cada interacción que termine en un cambio
  correcto, o como mínimo antes de cualquier push -- nunca debe quedar una corrida de cambios sin
  reflejar ahí.
- **Siempre** actualiza `CHANGELOG.md` después de cada interacción que termine en un cambio -- una
  línea breve por cambio relevante, con la fecha del día.
- Actualiza también `README.md` si cambió algo del uso real del programa.
- No hagas commit ni push a menos que se pida explícitamente. Cuando se pida, el patrón habitual
  en este proyecto es: actualizar los `.md` primero, luego commit, luego push, en ese orden, en la
  misma tanda.

## Antes de programar

- Para cambios de diseño (esquema de base de datos, flujo nuevo, cambio de comportamiento del
  semáforo de cámaras, etc.): propone el diseño primero y espera confirmación antes de
  implementar.
- Para bugs claros con una corrección obvia: puedes corregir directo y explicar qué pasó y por
  qué, sin esperar confirmación previa.

## Convenciones del proyecto

- Las banderas de línea de comandos van en **inglés** (`--client`, `--date`, `--no-interaction`),
  para que coincidan con las convenciones de los demás programas del usuario. Todo lo demás --
  mensajes de consola, comentarios, nombres de función y variable -- va en **español**.
- Comentarios: solo cuando el *por qué* no es obvio (una decisión de diseño, un bug real que
  motivó el cambio, una restricción externa). No describas qué hace el código si ya se entiende
  por el nombre.
- Antes de dar un cambio por terminado, pruébalo contra datos/base de datos reales cuando sea
  posible -- que compile no es suficiente.
- Antes de un cambio de comportamiento del semáforo o de las reglas del reporte, revisa si algún
  script de un solo uso (`backfill_reportes.py`, `scripts/mock_reporte_ejecutivo.py`, etc.)
  depende de la misma lógica y quedaría desincronizado.

## Entorno

- Proyecto en Windows. Ver **`CLAUDE.local.md`** (no versionado) para detalles específicos de la
  máquina de desarrollo (rutas de virtualenv, workarounds de `pipenv`, lanzadores `.ps1`, etc.).
