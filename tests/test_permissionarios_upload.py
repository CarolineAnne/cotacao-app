import unittest
from unittest.mock import Mock

from permissionarios import (
    BUCKET_FOTOS,
    TAMANHO_MAXIMO_FOTO_BYTES,
    salvar_foto_permissionario,
    validar_foto_permissionario,
)


PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"conteudo"


class ArquivoFake:
    def __init__(self, nome, conteudo, tipo="image/png"):
        self.name = nome
        self.type = tipo
        self._conteudo = conteudo

    def getvalue(self):
        return self._conteudo


class PermissionariosUploadTest(unittest.TestCase):
    def test_valida_imagem_png(self):
        arquivo = ArquivoFake("foto.png", PNG_VALIDO)

        extensao, content_type, conteudo = validar_foto_permissionario(arquivo)

        self.assertEqual(extensao, "png")
        self.assertEqual(content_type, "image/png")
        self.assertEqual(conteudo, PNG_VALIDO)

    def test_recusa_extensao_invalida(self):
        arquivo = ArquivoFake("foto.txt", PNG_VALIDO, "text/plain")

        with self.assertRaises(ValueError):
            validar_foto_permissionario(arquivo)

    def test_recusa_arquivo_disfarcado_de_imagem(self):
        arquivo = ArquivoFake("foto.png", b"nao e uma imagem")

        with self.assertRaises(ValueError):
            validar_foto_permissionario(arquivo)

    def test_recusa_foto_maior_que_limite(self):
        conteudo = b"\x89PNG\r\n\x1a\n" + (b"0" * TAMANHO_MAXIMO_FOTO_BYTES)
        arquivo = ArquivoFake("foto.png", conteudo)

        with self.assertRaises(ValueError):
            validar_foto_permissionario(arquivo)

    def test_salva_foto_validada_no_storage(self):
        bucket = Mock()
        bucket.get_public_url.return_value = "https://exemplo.com/foto.png"
        storage = Mock()
        storage.from_.return_value = bucket
        supabase = Mock()
        supabase.storage = storage
        arquivo = ArquivoFake("foto.png", PNG_VALIDO)

        url, nome_arquivo = salvar_foto_permissionario(
            supabase,
            arquivo,
            permissionario_id=7,
            data_link="2026-07-19",
            produto="Maca bonita"
        )

        storage.from_.assert_any_call(BUCKET_FOTOS)
        bucket.upload.assert_called_once()
        upload_nome, upload_conteudo, upload_opcoes = bucket.upload.call_args.args

        self.assertEqual(url, "https://exemplo.com/foto.png")
        self.assertEqual(upload_nome, nome_arquivo)
        self.assertEqual(upload_conteudo, PNG_VALIDO)
        self.assertEqual(upload_opcoes["content-type"], "image/png")
        self.assertTrue(
            nome_arquivo.startswith("permissionarios/2026-07-19/7/maca_bonita_")
        )
        self.assertTrue(nome_arquivo.endswith(".png"))


if __name__ == "__main__":
    unittest.main()
