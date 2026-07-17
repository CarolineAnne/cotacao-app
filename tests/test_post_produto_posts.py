import unittest
import zipfile

from io import BytesIO

from post_produto_posts import criar_zip_posts


class PostProdutoPostsTest(unittest.TestCase):
    def test_cria_zip_em_memoria_com_os_dois_posts(self):
        post_1 = b"png-1"
        post_2 = b"png-2"

        zip_bytes = criar_zip_posts("Produto Teste", post_1, post_2)

        self.assertIsInstance(zip_bytes, bytes)

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zipf:
            self.assertEqual(
                sorted(zipf.namelist()),
                [
                    "produto_teste_post_1_cotacao.png",
                    "produto_teste_post_2_informacoes.png",
                ]
            )
            self.assertEqual(zipf.read("produto_teste_post_1_cotacao.png"), post_1)
            self.assertEqual(zipf.read("produto_teste_post_2_informacoes.png"), post_2)


if __name__ == "__main__":
    unittest.main()
