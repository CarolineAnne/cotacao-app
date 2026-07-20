import unittest

from datetime import datetime, timedelta

from auth_utils import (
    CHAVE_TENTATIVAS_LOGIN,
    MAX_TENTATIVAS_LOGIN,
    TEMPO_BLOQUEIO_LOGIN_SEGUNDOS,
    limpar_tentativas_login,
    registrar_falha_login,
    segundos_bloqueio_login,
)


class AuthUtilsTest(unittest.TestCase):
    def test_registra_falhas_e_bloqueia_no_limite(self):
        estado = {}
        agora = datetime(2026, 7, 19, 8, 0, 0)

        for _ in range(MAX_TENTATIVAS_LOGIN - 1):
            self.assertEqual(registrar_falha_login(estado, agora), 0)

        self.assertEqual(
            estado[CHAVE_TENTATIVAS_LOGIN],
            MAX_TENTATIVAS_LOGIN - 1
        )

        bloqueio = registrar_falha_login(estado, agora)

        self.assertEqual(bloqueio, TEMPO_BLOQUEIO_LOGIN_SEGUNDOS)
        self.assertGreater(segundos_bloqueio_login(estado, agora), 0)

    def test_bloqueio_expirado_limpa_estado(self):
        estado = {}
        agora = datetime(2026, 7, 19, 8, 0, 0)

        for _ in range(MAX_TENTATIVAS_LOGIN):
            registrar_falha_login(estado, agora)

        depois_do_bloqueio = agora + timedelta(
            seconds=TEMPO_BLOQUEIO_LOGIN_SEGUNDOS + 1
        )

        self.assertEqual(
            segundos_bloqueio_login(estado, depois_do_bloqueio),
            0
        )
        self.assertEqual(estado[CHAVE_TENTATIVAS_LOGIN], 0)

    def test_limpa_tentativas_no_login_com_sucesso(self):
        estado = {}
        agora = datetime(2026, 7, 19, 8, 0, 0)

        registrar_falha_login(estado, agora)
        limpar_tentativas_login(estado)

        self.assertEqual(estado[CHAVE_TENTATIVAS_LOGIN], 0)
        self.assertEqual(segundos_bloqueio_login(estado, agora), 0)


if __name__ == "__main__":
    unittest.main()
