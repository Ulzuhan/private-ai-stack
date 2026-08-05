# private-ai-stack

**Un stack de IA local con mentalidad de producción — chat general y preguntas
sobre tus documentos con citas verificables — en un solo
`docker compose up -d`.** Nada sale de tu máquina: sin APIs cloud, sin
telemetría, con los modelos en tu propio hardware.

> 🚧 **En construcción, camino de la v0.1.0.** Todo lo publicado funciona y se
> verifica en CI sobre un runner limpio; el caso de estudio completo
> (arquitectura, hardening, air-gap, benchmarks) está aterrizando.

Esta es la versión resumida en español; la documentación técnica completa
vive en el [README en inglés](README.md).

## Qué resuelve

Equipos que no pueden mandar datos a la nube — RGPD, acuerdos de tratamiento,
sectores regulados — se quedan sin la mitad de las herramientas de IA
modernas. Este stack demuestra que la alternativa on-prem no es una promesa
de marketing: chat con modelos locales (Open WebUI + Ollama) y RAG documental
con citas clicables ([Reed](https://github.com/Ulzuhan/reed)) sobre Qdrant,
levantado con un comando, endurecido por defecto y con cada afirmación
verificada en CI.

## Arranque

```bash
docker compose up -d
```

El primer arranque descarga los modelos (~4 GB) automáticamente. Después:

- **Chat**: <http://127.0.0.1:3000>
- **Tus documentos**: <http://127.0.0.1:8000>

En Mac, usa tu Ollama nativo (Metal) con el override BYO — detalles en el
[README](README.md#on-a-mac-bring-your-own-ollama).

## Licencia

[Apache-2.0](LICENSE).

---

*Creado por José M. Cotarelo — en [Hesperia Labs](https://hesperialabs.com)
desplegamos y operamos stacks como este on-premises para industrias
reguladas.*
