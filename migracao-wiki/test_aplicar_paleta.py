"""Testes de substituir_cores."""
import unittest

from aplicar_paleta import substituir_cores


class TestSubstituirCores(unittest.TestCase):
    def test_substitui_cor_principal_lowercase(self) -> None:
        entrada = 'style="border: 2px solid #b38600;"'
        esperado = 'style="border: 2px solid #{{Cor|principal}};"'
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_caso_uppercase(self) -> None:
        entrada = "color:#B38600"
        esperado = "color:#{{Cor|principal}}"
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_caso_mixed(self) -> None:
        entrada = "background: #FfEcB3"
        esperado = "background: #{{Cor|fundo-medio}}"
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_todas_quatro_cores(self) -> None:
        entrada = (
            'style="border:#b38600;background:#fff9e6;color:#262626;'
            "outline:#ffecb3;\""
        )
        resultado = substituir_cores(entrada)
        self.assertIn("{{Cor|principal}}", resultado)
        self.assertIn("{{Cor|fundo-claro}}", resultado)
        self.assertIn("{{Cor|texto}}", resultado)
        self.assertIn("{{Cor|fundo-medio}}", resultado)
        # nenhum hex remanescente
        for hex_ in ("b38600", "fff9e6", "262626", "ffecb3"):
            self.assertNotIn(hex_, resultado.lower())

    def test_nao_toca_em_outros_hex(self) -> None:
        entrada = "color:#ff0000;border:#b38600;"
        resultado = substituir_cores(entrada)
        self.assertIn("#ff0000", resultado)
        self.assertIn("{{Cor|principal}}", resultado)

    def test_idempotente(self) -> None:
        entrada = "color:#b38600"
        uma_vez = substituir_cores(entrada)
        duas_vezes = substituir_cores(uma_vez)
        self.assertEqual(uma_vez, duas_vezes)

    def test_preserva_texto_sem_cores(self) -> None:
        entrada = "{{Capítulo|title1=Foo|capítulo=[[Parte 1]]}}"
        self.assertEqual(substituir_cores(entrada), entrada)

    def test_match_com_hash(self) -> None:
        entrada = "version b38600 build"
        self.assertEqual(substituir_cores(entrada), entrada)


if __name__ == "__main__":
    unittest.main()
