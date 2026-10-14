"""Sistema de gestión de notas para la materia de Programación I.

Escala de notas: 0 a 100. Se aprueba con 51 o más.
"""
import sqlite3

NOTA_APROBACION = 51


def calcular_promedio(notas):
    if not notas:
        raise ValueError("La lista de notas no puede estar vacia")

    total = 0
    for n in notas:
        if not validar_nota(n):
            raise ValueError("Nota invalida")
        total += n
    return total / len(notas)


def nota_final(parcial1, parcial2, examen_final, practicas):
    # Ponderación oficial: parciales 20% c/u, examen final 40%, prácticas 20%
    componentes = (parcial1, parcial2, examen_final, practicas)
    if not all(validar_nota(componente) for componente in componentes):
        raise ValueError("Componente invalido")
    return parcial1 * 0.2 + parcial2 * 0.2 + examen_final * 0.4 + practicas * 0.2


def estado(nota):
    if not validar_nota(nota):
        raise ValueError("Nota invalida")
    if nota >= NOTA_APROBACION:
        return "APROBADO"
    return "REPROBADO"


def validar_nota(nota):
    return isinstance(nota, (int, float)) and not isinstance(nota, bool) and 0 <= nota <= 100


def crear_base_demo():
    conexion = sqlite3.connect(":memory:")
    conexion.execute(
        "CREATE TABLE estudiantes ("
        "id INTEGER PRIMARY KEY, "
        "nombre TEXT NOT NULL, "
        "nota REAL NOT NULL CHECK (typeof(nota) IN ('integer', 'real') AND nota >= 0 AND nota <= 100)"
        ")"
    )
    conexion.executemany(
        "INSERT INTO estudiantes VALUES (?, ?, ?)",
        [(1, "Ana", 85), (2, "Luis", 51), (3, "Sofia", 40), (4, "Diego", 72)],
    )
    return conexion


def buscar_estudiante(conexion, nombre):
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("Nombre invalido")
    cursor = conexion.cursor()
    try:
        consulta = "SELECT id, nombre, nota FROM estudiantes WHERE nombre = ?"
        cursor.execute(consulta, (nombre,))
        return cursor.fetchall()
    finally:
        cursor.close()


def _validar_estudiante(estudiante):
    if not isinstance(estudiante, dict) or "nombre" not in estudiante or "nota" not in estudiante:
        raise ValueError("Estudiante invalido")
    if not validar_nota(estudiante["nota"]):
        raise ValueError("Nota invalida")


def mejores_estudiantes(estudiantes, cantidad=3):
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad < 1:
        raise ValueError("Cantidad invalida")
    for estudiante in estudiantes:
        _validar_estudiante(estudiante)
    ordenados = sorted(estudiantes, key=lambda e: e["nota"], reverse=True)
    return ordenados[:cantidad]


def reporte_aprobados(estudiantes):
    resultado = []
    for e in estudiantes:
        _validar_estudiante(e)
        if e["nota"] >= NOTA_APROBACION:
            resultado.append(e["nombre"])
    return resultado


def reporte_reprobados(estudiantes):
    resultado = []
    for e in estudiantes:
        _validar_estudiante(e)
        if e["nota"] < NOTA_APROBACION:
            resultado.append(e["nombre"])
    return resultado


if __name__ == "__main__":
    db = crear_base_demo()
    print("Buscar Ana:", buscar_estudiante(db, "Ana"))
    print("Nota final (80, 70, 90, 100):", nota_final(80, 70, 90, 100))
    print("Estado con 51:", estado(51))
