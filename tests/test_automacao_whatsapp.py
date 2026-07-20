import unittest

from datetime import datetime

from automacao_whatsapp import (
    TZ,
    limpar_whatsapp,
    montar_link,
    montar_payload_whatsapp,
    montar_validade_link,
    normalizar_hora,
    pode_enviar_agora,
)


class AutomacaoWhatsappTest(unittest.TestCase):
    def test_normaliza_hora(self):
        self.assertEqual(normalizar_hora("07:30:00"), "07:30")
        self.assertEqual(normalizar_hora("08:15"), "08:15")
        self.assertEqual(normalizar_hora("", "09:00"), "09:00")

    def test_limpa_whatsapp_com_ddi_brasil(self):
        self.assertEqual(limpar_whatsapp("(74) 99999-8888"), "5574999998888")
        self.assertEqual(limpar_whatsapp("5574999998888"), "5574999998888")
        self.assertIsNone(limpar_whatsapp(""))

    def test_valida_janela_de_envio(self):
        config = {
            "hora_envio": "07:00:00",
            "hora_limite": "09:00:00",
        }

        self.assertFalse(
            pode_enviar_agora(
                config,
                datetime(2026, 7, 19, 6, 59, tzinfo=TZ),
                avisar=False
            )
        )
        self.assertTrue(
            pode_enviar_agora(
                config,
                datetime(2026, 7, 19, 7, 0, tzinfo=TZ),
                avisar=False
            )
        )
        self.assertTrue(
            pode_enviar_agora(
                config,
                datetime(2026, 7, 19, 9, 0, tzinfo=TZ),
                avisar=False
            )
        )
        self.assertFalse(
            pode_enviar_agora(
                config,
                datetime(2026, 7, 19, 9, 1, tzinfo=TZ),
                avisar=False
            )
        )

    def test_monta_validade_e_link(self):
        validade = montar_validade_link(
            {"hora_limite": "08:45:00"},
            datetime(2026, 7, 19, 7, 0, tzinfo=TZ)
        )

        self.assertEqual(validade.strftime("%Y-%m-%d %H:%M"), "2026-07-19 08:45")
        self.assertEqual(
            montar_link("https://exemplo.com/", "abc123"),
            "https://exemplo.com?token=abc123"
        )

    def test_monta_link_recusa_http(self):
        with self.assertRaises(ValueError):
            montar_link("http://exemplo.com", "abc123")

    def test_monta_payload_do_template(self):
        payload = montar_payload_whatsapp(
            telefone="5574999998888",
            nome="Maria",
            mensagem="Informe os preços.",
            link="https://exemplo.com?token=abc",
            valido_ate=datetime(2026, 7, 19, 9, 0, tzinfo=TZ),
            config_whatsapp={
                "template_nome": "template_teste",
                "idioma": "pt_BR",
            },
            config_ambiente={
                "whatsapp_template_name": "fallback",
                "whatsapp_template_language": "en_US",
            }
        )

        self.assertEqual(payload["to"], "5574999998888")
        self.assertEqual(payload["template"]["name"], "template_teste")
        self.assertEqual(payload["template"]["language"]["code"], "pt_BR")
        parametros = payload["template"]["components"][0]["parameters"]
        self.assertEqual([p["text"] for p in parametros], [
            "Maria",
            "Informe os preços.",
            "https://exemplo.com?token=abc",
            "09:00",
        ])


if __name__ == "__main__":
    unittest.main()
