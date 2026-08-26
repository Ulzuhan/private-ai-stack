# private-ai-stack

**Un stack de IA local con mentalidad de producción — chat general y preguntas
sobre tus documentos con citas verificables — en un solo
`docker compose up -d`.** Nada sale de tu máquina: sin APIs cloud, sin
telemetría, con los modelos en tu propio hardware.

> **Estado: v0.2.0 publicada.** Todo lo que está en `main` funciona y se
> verifica en CI sobre un runner limpio en cada cambio, incluido el pipe que
> lleva las preguntas sobre documentos al chat. Los benchmarks y los perfiles
> GPU y air-gap están incluidos, y la release publica un paquete air-gap con
> procedencia atestada; el override de producción queda en la hoja de ruta.

Esta es la versión ejecutiva en español; la documentación técnica completa
(arquitectura, operación, hardening) vive en el
[README en inglés](README.md).

## Qué resuelve

Equipos que no pueden mandar datos a la nube — RGPD, acuerdos de tratamiento
de datos, sectores regulados — se quedan fuera de buena parte de la IA
moderna, o la pagan por token sin control de coste. Este stack demuestra que
la alternativa on-prem no es una promesa de marketing: chat con modelos
locales (Open WebUI + Ollama) y RAG documental con citas clicables
([Reed](https://github.com/Ulzuhan/reed)) sobre Qdrant, levantado con un
comando, endurecido por defecto y con cada afirmación verificada en CI.

## Cómo se verifica

Cada cambio levanta el stack completo en un runner limpio de GitHub: los
modelos se descargan, el LLM responde, Reed ingesta un documento y contesta
con cita, las dos interfaces sirven, y una copia de seguridad se restaura
tras borrar todos los volúmenes. Un navegador automatizado recorre las dos
UIs en cada PR. Si la insignia está en verde, el quickstart funciona.

Los números de rendimiento (36 tok/s en un Apple M5, 19 s de arranque en CI
con modelos en caché, ~2,9 GiB de RAM para todo el stack) se publican con
la plataforma declarada en [docs/benchmarking.md](docs/benchmarking.md).

## Arranque

```bash
docker compose up -d
```

El primer arranque descarga los modelos (~4 GB) automáticamente. Después:

- **Chat**: <http://127.0.0.1:3000>
- **Tus documentos**: <http://127.0.0.1:8000>

Y si prefieres preguntar a tus documentos sin salir del chat,
`./scripts/install-reed-pipe.sh` instala el pipe «Reed Documents»: aparece
como un modelo más en el selector, pero quien recupera, responde y cita sigue
siendo Reed. Es opcional; sin él, el stack es exactamente el mismo.

En Mac, usa tu Ollama nativo (Metal) con el override BYO — detalles en el
[README](README.md#on-a-mac-bring-your-own-ollama).

## Licencia

[Apache-2.0](LICENSE).

---

*Creado por José M. Cotarelo — en [Hesperia Labs](https://hesperialabs.com)
desplegamos y operamos stacks como este on-premises para industrias
reguladas.*
