import unittest

import pandas as pd

from relatorio_utils import (
    classificar_alerta,
    formatar_moeda,
    formatar_numero,
    formatar_percentual,
    ordenar_classes,
    texto_seguro
)


class RelatorioUtilsTest(unittest.TestCase):
    def test_formatacoes_em_padrao_brasileiro(self):
        self.assertEqual(formatar_moeda(1234.5), "R$ 1.234,50")
        self.assertEqual(formatar_numero(1234.4, 0), "1.234")
        self.assertEqual(formatar_numero(1234.56, 2), "1.234,56")
        self.assertEqual(formatar_percentual(12.34), "12,34%")

    def test_formatacoes_com_valor_invalido(self):
        self.assertEqual(formatar_moeda("abc"), "R$ 0,00")
        self.assertEqual(formatar_numero("abc"), "0")
        self.assertEqual(formatar_percentual("abc"), "0,00%")

    def test_texto_seguro_escapa_caracteres_para_pdf(self):
        self.assertEqual(texto_seguro(None), "")
        self.assertEqual(texto_seguro("A&B <C>"), "A&amp;B &lt;C&gt;")

    def test_classifica_alertas_por_faixa(self):
        self.assertEqual(classificar_alerta(60), "Alta crítica")
        self.assertEqual(classificar_alerta(30), "Alta acentuada")
        self.assertEqual(classificar_alerta(10), "Alta moderada")
        self.assertEqual(classificar_alerta(-30), "Queda acentuada")
        self.assertEqual(classificar_alerta(-10), "Queda relevante")
        self.assertEqual(classificar_alerta(0), "Variação normal")

    def test_ordena_classes_com_produto(self):
        df = pd.DataFrame([
            {"classe": "Cereais", "produto": "MILHO"},
            {"classe": "Hortaliças", "produto": "ALFACE"},
            {"classe": "Frutas", "produto": "BANANA"},
        ])

        ordenado = ordenar_classes(df)

        self.assertEqual(
            ordenado["classe"].tolist(),
            ["Hortaliças", "Frutas", "Cereais"]
        )


if __name__ == "__main__":
    unittest.main()
