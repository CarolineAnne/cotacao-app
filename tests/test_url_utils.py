import unittest

from url_utils import normalizar_base_url_publica


class UrlUtilsTest(unittest.TestCase):
    def test_normaliza_url_https(self):
        self.assertEqual(
            normalizar_base_url_publica(" https://exemplo.com/ "),
            "https://exemplo.com"
        )

    def test_recusa_url_http(self):
        with self.assertRaises(ValueError):
            normalizar_base_url_publica("http://exemplo.com")

    def test_recusa_url_vazia(self):
        with self.assertRaises(ValueError):
            normalizar_base_url_publica("")


if __name__ == "__main__":
    unittest.main()
