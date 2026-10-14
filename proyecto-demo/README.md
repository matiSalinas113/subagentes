# Sistema de gestión de notas

Proyecto de ejemplo para gestionar calificaciones de Programación I. Valida notas, calcula promedios y notas finales, determina la aprobación y consulta estudiantes en una base de datos SQLite en memoria.

## Funciones

| Nombre | Parámetros | Qué devuelve |
| --- | --- | --- |
| `calcular_promedio` | `notas`: lista de notas | El promedio numérico. Lanza `ValueError` si la lista está vacía o alguna nota no es numérica, no es finita o está fuera de `0..100`. |
| `nota_final` | `parcial1`, `parcial2`, `examen_final`, `practicas` | La nota final ponderada. Lanza `ValueError` si algún componente no es numérico, no es finito o está fuera de `0..100`. |
| `estado` | `nota` | `"APROBADO"` o `"REPROBADO"`. Lanza `ValueError` si la nota no es numérica, no es finita o está fuera de `0..100`. |
| `validar_nota` | `nota` | `True` si es una nota numérica finita en `0..100` (sin booleanos); de lo contrario, `False`. |
| `crear_base_demo` | Sin parámetros | Una conexión SQLite en memoria con la tabla `estudiantes` y datos de ejemplo. |
| `buscar_estudiante` | `conexion`, `nombre` | Lista de filas `(id, nombre, nota)` con coincidencia exacta, o `[]` si no existe. Lanza `ValueError` si `nombre` no es una cadena no vacía. |
| `mejores_estudiantes` | `estudiantes`, `cantidad=3` | Hasta `cantidad` registros ordenados de mayor a menor por `nota`. Lanza `ValueError` si `cantidad` no es un entero positivo o algún registro no es válido. |
| `reporte_aprobados` | `estudiantes` | Nombres de los registros aprobados. Lanza `ValueError` si algún registro no es válido. |
| `reporte_reprobados` | `estudiantes` | Nombres de los registros reprobados. Lanza `ValueError` si algún registro no es válido. |

Los registros usados en rankings y reportes deben ser diccionarios con las claves `nombre` y `nota`; la nota debe ser válida en la escala.

## Reglas de negocio

- **Escala de notas:** de 0 a 100, incluidos ambos límites. Las notas no numéricas, no finitas o fuera de esta escala son inválidas.
- **Ponderación de la nota final:** parcial 1, 20 %; parcial 2, 20 %; examen final, 40 %; prácticas, 20 %.
- **Aprobación:** una nota de **51 o más** aprueba; una nota inferior a 51 reprueba.
- **Base de datos:** SQLite exige `nombre` no nulo y `nota` numérica dentro de `0..100` mediante restricciones de tabla.

## Ejecución

Desde el directorio `proyecto-demo`, ejecute:

```bash
python notas.py
```

El programa crea una base de datos temporal en memoria, busca a `Ana` y muestra ejemplos de cálculo y estado.

## Pruebas

Desde el directorio `proyecto-demo`, ejecute:

```bash
python -m unittest discover -s tests -v
```

## Limpieza de caché

Desde la raíz del repositorio, puede ejecutar:

```powershell
.\reiniciar-demo.ps1
```

El script solo elimina la caché `__pycache__` de `proyecto-demo`; conserva el código, las pruebas y este README.
