import unittest

from cotacao_repository import (
    preparar_registro_cotacao,
    salvar_cotacoes_com_protecao
)


class RespostaFake:
    def __init__(self, data):
        self.data = data


class ConsultaFake:
    def __init__(self, supabase):
        self.supabase = supabase
        self.modo = None
        self.filtros = {}
        self.payload = None

    def select(self, *_args):
        self.modo = "select"
        return self

    def delete(self):
        self.modo = "delete"
        return self

    def insert(self, payload):
        self.modo = "insert"
        self.payload = payload
        return self

    def eq(self, campo, valor):
        self.filtros[campo] = valor
        return self

    def execute(self):
        if self.modo == "select":
            return RespostaFake([
                item.copy()
                for item in self.supabase.registros
                if self._combina(item)
            ])

        if self.modo == "delete":
            self.supabase.registros = [
                item
                for item in self.supabase.registros
                if not self._combina(item)
            ]
            return RespostaFake([])

        if self.modo == "insert":
            if self.supabase.falhar_proximo_insert:
                self.supabase.falhar_proximo_insert = False
                raise RuntimeError("falha simulada")

            self.supabase.registros.extend([
                item.copy()
                for item in self.payload
            ])
            return RespostaFake(self.payload)

        raise RuntimeError("modo não informado")

    def _combina(self, item):
        return all(
            item.get(campo) == valor
            for campo, valor in self.filtros.items()
        )


class SupabaseFake:
    def __init__(self, registros=None, falhar_proximo_insert=False):
        self.registros = list(registros or [])
        self.falhar_proximo_insert = falhar_proximo_insert

    def table(self, _nome):
        return ConsultaFake(self)


def registro_cotacao(preco_min):
    return {
        "id": 99,
        "data": "2026-07-17",
        "classe": "Frutas",
        "produto": "TOMATE",
        "unidade": "Kg",
        "kg": 1,
        "preco_min": preco_min,
        "preco_max": preco_min + 1,
        "preco_medio": preco_min + 0.5,
        "valor_kg": preco_min + 0.5,
        "precos_digitados": [preco_min, preco_min + 1],
    }


class CotacaoRepositoryTest(unittest.TestCase):
    def test_prepara_registro_remove_campos_fora_da_tabela(self):
        preparado = preparar_registro_cotacao({
            **registro_cotacao(10),
            "campo_extra": "ignorar",
        })

        self.assertNotIn("id", preparado)
        self.assertNotIn("campo_extra", preparado)
        self.assertEqual(preparado["produto"], "TOMATE")

    def test_salva_nova_cotacao_sem_registro_anterior(self):
        supabase = SupabaseFake()
        novo = preparar_registro_cotacao(registro_cotacao(10))

        resposta = salvar_cotacoes_com_protecao(
            supabase,
            "2026-07-17",
            [novo],
            produto="TOMATE"
        )

        self.assertTrue(resposta.data)
        self.assertEqual(len(supabase.registros), 1)
        self.assertEqual(supabase.registros[0]["preco_min"], 10)

    def test_substitui_registro_anterior_quando_insert_funciona(self):
        supabase = SupabaseFake([registro_cotacao(1)])
        novo = preparar_registro_cotacao(registro_cotacao(10))

        salvar_cotacoes_com_protecao(
            supabase,
            "2026-07-17",
            [novo],
            produto="TOMATE"
        )

        self.assertEqual(len(supabase.registros), 1)
        self.assertEqual(supabase.registros[0]["preco_min"], 10)

    def test_restaura_registro_anterior_quando_insert_falha(self):
        supabase = SupabaseFake(
            [registro_cotacao(1)],
            falhar_proximo_insert=True
        )
        novo = preparar_registro_cotacao(registro_cotacao(10))

        with self.assertRaisesRegex(RuntimeError, "restaurados"):
            salvar_cotacoes_com_protecao(
                supabase,
                "2026-07-17",
                [novo],
                produto="TOMATE"
            )

        self.assertEqual(len(supabase.registros), 1)
        self.assertEqual(supabase.registros[0]["preco_min"], 1)
        self.assertNotIn("id", supabase.registros[0])

    def test_recusa_lista_vazia(self):
        supabase = SupabaseFake()

        with self.assertRaises(ValueError):
            salvar_cotacoes_com_protecao(
                supabase,
                "2026-07-17",
                [],
                produto="TOMATE"
            )


if __name__ == "__main__":
    unittest.main()
