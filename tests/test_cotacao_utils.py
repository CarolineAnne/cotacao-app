import unittest

import pandas as pd

from cotacao_utils import (
    calcular_precos_validos,
    calcular_resumo_precos,
    calcular_variacao_percentual,
    montar_registro_cotacao,
    montar_registros_cotacoes,
    obter_sugestoes_cotacao,
    ordenar_produtos_para_cotacao,
    preparar_ultimas_cotacoes
)


class CotacaoUtilsTest(unittest.TestCase):
    def test_ordena_produtos_por_classe_e_nome(self):
        produtos = pd.DataFrame([
            {"nome": "ZABUMBA", "classe": "Cereais"},
            {"nome": "ABACATE", "classe": "Frutas"},
            {"nome": "ALFACE", "classe": "Hortaliças"},
        ])

        ordenado = ordenar_produtos_para_cotacao(produtos)

        self.assertEqual(
            ordenado["nome"].tolist(),
            ["ALFACE", "ABACATE", "ZABUMBA"]
        )

    def test_prepara_ultimas_cotacoes_por_produto(self):
        cotacoes = pd.DataFrame([
            {"data": "2026-07-16", "produto": "tomate", "valor_kg": 3},
            {"data": "2026-07-17", "produto": " TOMATE ", "valor_kg": 4},
            {"data": "2026-07-15", "produto": "banana", "valor_kg": 2},
        ])

        ultimas = preparar_ultimas_cotacoes(cotacoes)

        self.assertEqual(len(ultimas), 2)
        tomate = ultimas[ultimas["produto"] == "TOMATE"].iloc[0]
        self.assertEqual(tomate["valor_kg"], 4)

    def test_obtem_sugestoes_da_lista_salva_ou_minimo_maximo(self):
        com_lista = {
            "precos_digitados": [1, "2,5", 0],
            "preco_min": 10,
            "preco_max": 20,
        }
        sem_lista = {
            "precos_digitados": [],
            "preco_min": 10,
            "preco_max": 20,
        }

        self.assertEqual(obter_sugestoes_cotacao(com_lista), [1.0])
        self.assertEqual(obter_sugestoes_cotacao(sem_lista), [10.0, 20.0])

    def test_calcula_precos_validos_usando_sugestoes_quando_campo_vazio(self):
        precos = ["", "12,50", "abc", "-1"]
        sugestoes = [10, None, None, 8]

        self.assertEqual(
            calcular_precos_validos(precos, sugestoes),
            [10.0, 12.5]
        )

    def test_calcula_resumo_e_variacao(self):
        self.assertEqual(
            calcular_resumo_precos([10, 20, 30], 2),
            (10, 30, 20.0, 10.0)
        )
        self.assertEqual(calcular_resumo_precos([], 2), (0, 0, 0, 0.0))
        self.assertEqual(calcular_variacao_percentual(15, 10), 50.0)
        self.assertEqual(calcular_variacao_percentual(15, 0), 0)

    def test_monta_registro_cotacao(self):
        registro = montar_registro_cotacao(
            data_str="2026-07-17",
            produto=" tomate ",
            classe="hortalicas",
            unidade="Kg",
            kg=2,
            lista_precos=[10, 20],
            normalizar_kg_salvo=True
        )

        self.assertEqual(registro["produto"], "TOMATE")
        self.assertEqual(registro["classe"], "Hortaliças")
        self.assertEqual(registro["kg"], 2)
        self.assertEqual(registro["preco_medio"], 15.0)
        self.assertEqual(registro["valor_kg"], 7.5)

    def test_monta_registros_cotacoes_em_lote(self):
        registros = montar_registros_cotacoes(
            [
                ("TOMATE", "Hortaliças", "Kg", 2, 10, 20, [10, 20]),
                ("BANANA", "Frutas", "Cx", 1, 5, 7, [5, 7]),
            ],
            "2026-07-17"
        )

        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0]["produto"], "TOMATE")
        self.assertEqual(registros[1]["classe"], "Frutas")


if __name__ == "__main__":
    unittest.main()
