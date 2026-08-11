"""Testes de funções puras do subir_miraheze."""
import unittest
from pathlib import Path

from subir_miraheze import paginas_do_dump, precisa_atualizar


class TestPaginasDoDump(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path("/tmp/test_dump.xml")
        self.tmp.write_text(
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.11/ '
            'http://www.mediawiki.org/xml/export-0.11.xsd" version="0.11" xml:lang="pt-br">'
            "<page><title>Daniel</title><ns>0</ns>"
            "<revision><text>Conteúdo do Daniel</text></revision></page>"
            "<page><title>Predefinição:Cor</title><ns>10</ns>"
            "<revision><text>{{#switch...}}</text></revision></page>"
            "<page><title>Categoria:Capítulos</title><ns>14</ns>"
            "<revision><text>Lista de capítulos</text></revision></page>"
            "</mediawiki>",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.unlink(missing_ok=True)

    def test_parse_retorna_lista_correta(self) -> None:
        pgs = paginas_do_dump(self.tmp)
        self.assertEqual(len(pgs), 3)

    def test_parse_preserva_titulo_ns_texto(self) -> None:
        pgs = paginas_do_dump(self.tmp)
        d = pgs[0]
        self.assertEqual(d["title"], "Daniel")
        self.assertEqual(d["ns"], 0)
        self.assertEqual(d["text"], "Conteúdo do Daniel")

    def test_parse_namespaces_diferentes(self) -> None:
        pgs = paginas_do_dump(self.tmp)
        ns_set = {p["ns"] for p in pgs}
        self.assertEqual(ns_set, {0, 10, 14})

    def test_parse_dump_vazio_retorna_lista_vazia(self) -> None:
        empty = Path("/tmp/empty_dump.xml")
        empty.write_text(
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" '
            'version="0.11"></mediawiki>',
            encoding="utf-8",
        )
        try:
            pgs = paginas_do_dump(empty)
            self.assertEqual(pgs, [])
        finally:
            empty.unlink()


class TestPrecisaAtualizar(unittest.TestCase):
    def test_iguais_retorna_false(self) -> None:
        self.assertFalse(precisa_atualizar("foo", "foo"))

    def test_diferentes_retorna_true(self) -> None:
        self.assertTrue(precisa_atualizar("foo", "bar"))

    def test_remoto_none_retorna_true(self) -> None:
        self.assertTrue(precisa_atualizar("foo", None))

    def test_whitespace_diferente_retorna_true(self) -> None:
        self.assertTrue(precisa_atualizar("foo\n", "foo"))


if __name__ == "__main__":
    unittest.main()
