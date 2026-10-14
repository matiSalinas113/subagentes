# Login app

Backend de login same-origin hecho con Python estándar y SQLite. No hay registro público: el primer administrador se crea localmente de forma interactiva y los administradores autenticados pueden crear cuentas mediante la API.

## Uso local

```powershell
cd login-app
python app.py bootstrap
python app.py serve
```

El bootstrap pide el nombre y contraseña con `getpass`; no acepta una contraseña por argumento ni la almacena fuera de SQLite. Por defecto el servicio escucha solo en `127.0.0.1:8000` y espera `Origin: http://127.0.0.1:8000` en cada `POST`.

Para una instalación HTTPS de producción, suministre el origen público exacto y active cookies seguras:

```powershell
python app.py serve --host 0.0.0.0 --origin https://login.example.invalid --secure-cookies
```

No se incluyen dominios ni secretos reales. Un proxy TLS debe terminar HTTPS antes de este servidor y preservar el mismo origen público configurado.

## API

Todos los `POST` exigen `Content-Type: application/json` y el encabezado `Origin` exactamente igual a `--origin`.

| Método y ruta | Cuerpo | Resultado |
|---|---|---|
| `POST /api/auth/login` | `{"username":"…","password":"…"}` | `204` y cookie de sesión; `401` genérico para credenciales inválidas |
| `POST /api/auth/logout` | `{}` | `204` y eliminación de cookie/sesión |
| `GET /api/auth/me` | — | usuario autenticado, o `401` |
| `POST /api/admin/users` | `{"username":"…","password":"…","is_admin":false}` | `201`; requiere sesión de administrador |

Las contraseñas tienen 12–1024 caracteres. Los usuarios tienen 3–64 caracteres ASCII alfanuméricos, `_`, `.` o `-`.

## Interfaz web

La interfaz estática está en `static/` y se sirve en `/` al ejecutar el servidor. Usa el formulario semántico de inicio de sesión y las rutas `GET /api/auth/me`, `POST /api/auth/login` y `POST /api/auth/logout` del mismo origen. Las credenciales se envían con `credentials: "same-origin"`; la sesión permanece únicamente en la cookie `HttpOnly` del servidor, sin usar `localStorage` ni `sessionStorage`.

## Almacenamiento

`data/login.sqlite3` contiene `users` con una sal aleatoria de 16 bytes, hash PBKDF2-HMAC-SHA256 de 600.000 iteraciones y el contador de iteraciones; nunca contraseñas. `sessions` conserva identificadores aleatorios de 32 bytes codificados URL-safe, referencia de usuario y caducidad de ocho horas. La cookie solo contiene el identificador, con `HttpOnly` y `SameSite=Lax` (más `Secure` al activar la opción de producción).

Los archivos estáticos opcionales se sirven desde `static/`; no se proporciona frontend en este cambio.
