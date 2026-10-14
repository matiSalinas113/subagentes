# Codex en este proyecto

Se conservan los perfiles existentes de `agents/`. Las instrucciones compartidas
estan en `../AGENTS.md` y el comando de validacion es `python scripts/check.py`.

Los hooks son hooks de Git versionados en `../.githooks/`; se activan por clon con:

```powershell
git config --local core.hooksPath .githooks
```

La automatizacion remota vive en `../.github/workflows/tests.yml`.
