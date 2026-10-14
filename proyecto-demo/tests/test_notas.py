"""Pruebas de caja negra para las reglas publicadas de gestión de notas."""
import unittest

from notas import (
    buscar_estudiante,
    calcular_promedio,
    crear_base_demo,
    estado,
    mejores_estudiantes,
    nota_final,
    reporte_aprobados,
    reporte_reprobados,
    validar_nota,
)


class TestCalcularPromedio(unittest.TestCase):
    def test_promedio_de_notas_validas(self):
        self.assertEqual(calcular_promedio([40, 60, 80]), 60)

    def test_lista_vacia_es_invalida(self):
        """No existe promedio para una lista vacía."""
        with self.assertRaises(ValueError):
            calcular_promedio([])

    def test_notas_fuera_de_la_escala_son_invalidas(self):
        with self.assertRaises(ValueError):
            calcular_promedio([50, 101])

    def test_rechaza_booleanos_y_valores_no_finitos(self):
        """Un booleano o NaN no representa una calificación de la escala."""
        for nota in (True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(nota=nota):
                with self.assertRaises(ValueError):
                    calcular_promedio([50, nota])


class TestNotaFinal(unittest.TestCase):
    def test_aplica_la_ponderacion_oficial(self):
        self.assertEqual(nota_final(80, 70, 90, 100), 86)

    def test_todos_los_componentes_maximos_dan_cien(self):
        self.assertEqual(nota_final(100, 100, 100, 100), 100)

    def test_componentes_fuera_de_escala_son_invalidos(self):
        with self.assertRaises(ValueError):
            nota_final(80, 70, 90, 101)

    def test_rechaza_booleanos_y_texto_en_componentes(self):
        for componente in (False, "100; DROP TABLE estudiantes"):
            with self.subTest(componente=componente):
                with self.assertRaises(ValueError):
                    nota_final(80, 70, 90, componente)


class TestEstadoYValidacion(unittest.TestCase):
    def test_nota_limite_51_aprueba(self):
        self.assertEqual(estado(51), "APROBADO")

    def test_validar_nota_acepta_los_limites_de_escala(self):
        self.assertTrue(validar_nota(0))
        self.assertTrue(validar_nota(100))

    def test_validar_nota_rechaza_valores_fuera_de_escala(self):
        self.assertFalse(validar_nota(-1))
        self.assertFalse(validar_nota(101))

    def test_validar_nota_rechaza_texto_malicioso_sin_excepcion(self):
        self.assertFalse(validar_nota("0 OR 1=1"))

    def test_validar_nota_rechaza_booleanos_y_no_finitos(self):
        for nota in (True, False, float("nan"), float("inf"), float("-inf")):
            with self.subTest(nota=nota):
                self.assertFalse(validar_nota(nota))

    def test_estado_rechaza_notas_fuera_de_escala(self):
        """La escala publicada no permite asignar estado a -1 ni a 101."""
        for nota in (-1, 101, float("nan"), float("inf")):
            with self.subTest(nota=nota):
                with self.assertRaises(ValueError):
                    estado(nota)

    def test_estado_rechaza_entrada_maliciosa_en_lugar_de_clasificarla(self):
        with self.assertRaises(ValueError):
            estado("51 OR 1=1")


class TestConsultasYReportes(unittest.TestCase):
    def setUp(self):
        self.db = crear_base_demo()
        self.estudiantes = [
            {"nombre": "Ana", "nota": 85},
            {"nombre": "Luis", "nota": 51},
            {"nombre": "Sofia", "nota": 40},
            {"nombre": "Diego", "nota": 72},
        ]

    def tearDown(self):
        self.db.close()

    def test_buscar_estudiante_por_nombre(self):
        self.assertEqual(buscar_estudiante(self.db, "Ana"), [(1, "Ana", 85.0)])

    def test_busqueda_sin_coincidencias_devuelve_lista_vacia(self):
        self.assertEqual(buscar_estudiante(self.db, "Nadie"), [])

    def test_busqueda_resiste_inyeccion_sql(self):
        self.assertEqual(buscar_estudiante(self.db, "' OR 1=1 --"), [])

    def test_busqueda_por_nombre_con_comilla_es_exacta(self):
        self.db.execute("INSERT INTO estudiantes VALUES (?, ?, ?)", (5, "O'Neil", 90))
        self.assertEqual(buscar_estudiante(self.db, "O'Neil"), [(5, "O'Neil", 90.0)])

    def test_mejores_estudiantes_devuelve_notas_mas_altas_primero(self):
        mejores = mejores_estudiantes(self.estudiantes, 2)
        self.assertEqual([e["nombre"] for e in mejores], ["Ana", "Diego"])

    def test_mejores_estudiantes_con_lista_vacia(self):
        self.assertEqual(mejores_estudiantes([]), [])

    def test_mejores_estudiantes_rechaza_cantidad_no_positiva_o_booleana(self):
        for cantidad in (0, -1, True, False, 1.5, "2"):
            with self.subTest(cantidad=cantidad):
                with self.assertRaises(ValueError):
                    mejores_estudiantes(self.estudiantes, cantidad)

    def test_mejores_estudiantes_rechaza_notas_fuera_de_escala(self):
        """Una nota 101 no puede convertirse silenciosamente en la mejor nota."""
        estudiantes_invalidos = self.estudiantes + [{"nombre": "Ataque", "nota": 101}]
        with self.assertRaises(ValueError):
            mejores_estudiantes(estudiantes_invalidos)

    def test_reporte_aprobados_incluye_nota_limite(self):
        self.assertEqual(reporte_aprobados(self.estudiantes), ["Ana", "Luis", "Diego"])

    def test_reporte_reprobados_excluye_nota_limite(self):
        self.assertEqual(reporte_reprobados(self.estudiantes), ["Sofia"])

    def test_reportes_rechazan_notas_fuera_de_la_escala(self):
        """Un registro inválido no es ni aprobado ni reprobado."""
        estudiantes_invalidos = [
            {"nombre": "FueraPorArriba", "nota": 101},
            {"nombre": "FueraPorAbajo", "nota": -1},
        ]
        for reporte in (reporte_aprobados, reporte_reprobados):
            with self.subTest(reporte=reporte.__name__):
                with self.assertRaises(ValueError):
                    reporte(estudiantes_invalidos)


if __name__ == "__main__":
    unittest.main()
