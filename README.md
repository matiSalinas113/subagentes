# Subagentes y mini login

El repositorio conserva los agentes de Codex, Claude y OpenCode, el mini login
en `login-app/` y el ejemplo de notas en `proyecto-demo/`.

## Validacion local

Requiere Python 3.14 y Git; las pruebas usan la biblioteca estandar.

```powershell
git config --local core.hooksPath .githooks
python scripts/check.py
```

`pre-commit` prueba una copia del contenido preparado con `git add`.
`pre-push` prueba copias de los commits que se enviaran. Si faltan las pruebas,
Python no esta disponible o una prueba falla, Git cancela la operacion.
Cada clon debe activar los hooks. Git permite omitirlos con `--no-verify`;
por eso el bloqueo remoto requiere tambien proteger la rama.

Al preparar por primera vez estos archivos para subirlos, conserva el permiso
ejecutable de los hooks (necesario en Linux/macOS):

```powershell
git add --chmod=+x .githooks/pre-commit .githooks/pre-push
```

## GitHub Actions y bloqueo de main

El workflow `Tests` ejecuta ambas suites en cada push, pull request y grupo de
fusion. El check requerido se llama `tests`. No hay filtros de rutas que puedan
dejar el check sin ejecutar.

Para activar el bloqueo remoto en `matiSalinas113/subagentes`:

1. Sube estos archivos y espera la primera ejecucion en la pestaña Actions.
2. En Settings > Branches crea una regla de proteccion para `main`.
3. Activa Require a pull request before merging.
4. Activa Require status checks to pass before merging y selecciona `tests`.
5. Activa Require branches to be up to date before merging y Do not allow
   bypassing the above settings; no permitas force pushes ni eliminaciones.
6. Guarda la regla y trabaja en ramas con pull requests.

Un workflow fallido por si solo no bloquea una fusion: el check debe ser
obligatorio en la configuracion del repositorio. Actions se ejecuta despues
de recibir el push; el hook local permite detenerlo antes de enviarlo.

Documentacion: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches

Consulta `login-app/README.md` para iniciar el servidor y crear el administrador.
