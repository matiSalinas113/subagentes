# Instrucciones del proyecto

- El mini login vive en `login-app/`; el ejemplo de notas en `proyecto-demo/`.
- Conserva los agentes existentes en `.codex/agents/` y los cambios del usuario.
- Ejecuta `python scripts/check.py` antes de dar por terminado un cambio.
- No omitas pruebas ni cambies expectativas para ocultar fallos.
- Los hooks de Git viven en `.githooks/`. Instalalos con `git config --local core.hooksPath .githooks` al preparar un clon.
- El hook pre-commit valida el contenido preparado; pre-push valida los commits enviados, incluso si el directorio de trabajo tiene cambios adicionales.
- GitHub Actions debe ejecutar ambas suites y devolver error cuando alguna falle.
