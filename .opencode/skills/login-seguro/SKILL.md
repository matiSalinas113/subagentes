---
name: Login seguro
description: Diseña, implementa, prueba y audita un login seguro usando exclusivamente los subagentes nuevos auth-requisitos, auth-implementador, auth-interfaz, auth-pruebas y auth-auditor-seguridad. Úsala cuando se pida crear o cambiar inicio de sesión, registro, credenciales, contraseñas, sesiones o control de acceso en este proyecto.
---

# Login seguro

Coordina exclusivamente estos subagentes nuevos; no uses `depurador`, `documentador`, `generador-tests` ni `revisor-codigo`.

## Flujo

1. Ejecuta `@auth-requisitos` para inspeccionar el proyecto, definir el flujo y exponer decisiones pendientes.
2. Si faltan decisiones que cambien la arquitectura (por ejemplo, aplicación web frente a CLI, registro de usuarios, persistencia o tipo de sesión), detente y pide la aprobación del usuario. No inventes un framework ni credenciales.
3. Pasa el resumen aprobado a `@auth-implementador` para crear la lógica de servidor o dominio.
4. Si el proyecto tiene interfaz, pasa el contrato de autenticación a `@auth-interfaz`. Si no la tiene, informa que la funcionalidad queda expuesta solo mediante la interfaz existente y no fuerces una UI.
5. Pasa el contrato y los cambios a `@auth-pruebas`. Este agente solo modifica pruebas y ejecuta la suite.
6. Pasa la implementación y el resultado de pruebas a `@auth-auditor-seguridad`.
7. Si el auditor informa hallazgos 🔴 o 🟡, pide a `@auth-implementador` que corrija únicamente los hallazgos confirmados y vuelve a ejecutar `@auth-pruebas` y `@auth-auditor-seguridad` una vez.

## Reglas de seguridad

- Nunca aceptar contraseñas en texto plano en almacenamiento, código, pruebas ni registros.
- No exponer secretos ni detalles que permitan enumerar usuarios.
- Validar en el servidor; la interfaz solo mejora la experiencia.
- Usar sesiones o tokens solo cuando el requisito lo justifique y con almacenamiento seguro para el stack.
- No afirmar que el login está listo hasta que las pruebas pasen y no queden hallazgos 🔴/🟡 sin resolver.

## Informe final

Presenta:

| Etapa | Subagente nuevo | Resultado |
|---|---|---|

Después indica: decisiones aprobadas, archivos modificados, pruebas ejecutadas y riesgos pendientes.
