import unittest
from unittest.mock import Mock, patch

from dados_utils import verificar_login


class DadosUtilsTest(unittest.TestCase):
    def test_verificar_login_usa_fluxo_seguro(self):
        supabase = Mock()
        esperado = {"nome": "Ana", "nivel": "admin"}

        with patch(
            "dados_utils.verificar_login_seguro",
            return_value=esperado
        ) as login_seguro:
            resultado = verificar_login(supabase, "admin", "senha")

        self.assertEqual(resultado, esperado)
        login_seguro.assert_called_once_with(supabase, "admin", "senha")
        supabase.table.assert_not_called()


if __name__ == "__main__":
    unittest.main()
