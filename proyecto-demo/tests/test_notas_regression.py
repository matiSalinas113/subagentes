import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import notas


def estudiante(nombre, nota):
    return {"nombre": nombre, "nota": nota}


class TestCalcularPromedio(unittest.TestCase):
    def test_promedio_de_notas_validas(self):
        self.assertAlmostEqual(notas.calcular_promedio([60, 80, 100]), 80)

    def test_promedio_con_una_sola_nota(self):
        self.assertEqual(notas.calcular_promedio([51]), 51)

    def test_lista_vacia_no_tiene_promedio(self):
        with self.assertRaises(ValueError):
            notas.calcular_promedio([])


class TestNotaFinal(unittest.TestCase):
    def test_usa_ponderacion_oficial(self):
        # Parciales 20% c/u, examen final 40%, practicas 20%.
        self.assertAlmostEqual(notas.nota_final(70, 60, 80, 50), 68)

    def test_limite_inferior(self):
        self.assertEqual(notas.nota_final(0, 0, 0, 0), 0)

    def test_limite_superior(self):
        self.assertEqual(notas.nota_final(100, 100, 100, 100), 100)


class TestEstado(unittest.TestCase):
    def test_51_o_mas_aprueba(self):
        self.assertEqual(notas.estado(51), "APROBADO")
        self.assertEqual(notas.estado(100), "APROBADO")

    def test_menos_de_51_reprueba(self):
        self.assertEqual(notas.estado(50), "REPROBADO")
        self.assertEqual(notas.estado(0), "REPROBADO")


class TestValidarNota(unittest.TestCase):
    def test_notas_en_escala_son_validas(self):
        for nota in (0, 51, 100):
            with self.subTest(nota=nota):
                self.assertTrue(notas.validar_nota(nota))

    def test_notas_fuera_de_escala_son_invalidas(self):
        for nota in (-1, 101, 10**6):
            with self.subTest(nota=nota):
                self.assertFalse(notas.validar_nota(nota))


class TestBuscarEstudiante(unittest.TestCase):
    def setUp(self):
        self.conexion = notas.crear_base_demo()

    def tearDown(self):
        self.conexion.close()

    def test_busca_estudiante_existente(self):
        self.assertEqual(notas.buscar_estudiante(self.conexion, "Ana"), [(1, "Ana", 85)])

    def test_busca_estudiante_inexistente(self):
        self.assertEqual(notas.buscar_estudiante(self.conexion, "Nadie"), [])

    def test_nombre_con_comilla_no_rompe_consulta(self):
        try:
            resultado = notas.buscar_estudiante(self.conexion, "O'Brien")
        except Exception as exc:
            self.fail(f"No deberia lanzar {type(exc).__name__}: {exc}")
        self.assertEqual(resultado, [])

    def test_inyeccion_sql_or_no_devuelve_todos_los_registros(self):
        resultado = notas.buscar_estudiante(self.conexion, "' OR '1'='1")
        self.assertEqual(resultado, [])

    def test_inyeccion_sql_union_no_permite_filas_falsas(self):
        resultado = notas.buscar_estudiante(self.conexion, "x' UNION SELECT 999,'Mallory',100 --")
        self.assertEqual(resultado, [])

    def test_inyeccion_sql_drop_no_destruye_tabla(self):
        try:
            notas.buscar_estudiante(self.conexion, "x'; DROP TABLE estudiantes; --")
        except Exception:
            pass

        total = self.conexion.execute("SELECT COUNT(*) FROM estudiantes").fetchone()[0]
        self.assertEqual(total, 4)


class TestMejoresEstudiantes(unittest.TestCase):
    def setUp(self):
        self.estudiantes = [
            estudiante("Ana", 85),
            estudiante("Luis", 51),
            estudiante("Sofia", 40),
            estudiante("Diego", 72),
        ]

    def test_devuelve_los_mejores_en_orden_descendente(self):
        resultado = notas.mejores_estudiantes(self.estudiantes, cantidad=3)
        self.assertEqual([e["nombre"] for e in resultado], ["Ana", "Diego", "Luis"])

    def test_cantidad_personalizada(self):
        resultado = notas.mejores_estudiantes(self.estudiantes, cantidad=1)
        self.assertEqual([e["nombre"] for e in resultado], ["Ana"])

    def test_lista_vacia_devuelve_lista_vacia(self):
        self.assertEqual(notas.mejores_estudiantes([]), [])

    def test_cantidad_mayor_a_lista_devuelve_todos_los_disponibles(self):
        resultado = notas.mejores_estudiantes(self.estudiantes[:2], cantidad=5)
        self.assertEqual(len(resultado), 2)


class TestReportes(unittest.TestCase):
    def setUp(self):
        self.estudiantes = [
            estudiante("Ana", 51),
            estudiante("Luis", 50),
            estudiante("Sofia", 100),
            estudiante("Diego", 0),
        ]

    def test_reporte_aprobados_incluye_nota_51(self):
        self.assertEqual(notas.reporte_aprobados(self.estudiantes), ["Ana", "Sofia"])

    def test_reporte_reprobados_excluye_nota_51(self):
        self.assertEqual(notas.reporte_reprobados(self.estudiantes), ["Luis", "Diego"])

    def test_reportes_con_lista_vacia(self):
        self.assertEqual(notas.reporte_aprobados([]), [])
        self.assertEqual(notas.reporte_reprobados([]), [])


if __name__ == "__main__":
    unittest.main()
