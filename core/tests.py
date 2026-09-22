from django.test import SimpleTestCase


class SaludTests(SimpleTestCase):
    def test_salud_responde_200_sin_base_de_datos(self):
        # SimpleTestCase prohíbe cualquier consulta a la BD: si /salud/ la
        # tocara, este test fallaría.
        respuesta = self.client.get("/salud/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content, b"ok")
