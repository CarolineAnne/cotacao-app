import unittest

from db import ler_config_supabase


class DbConfigTest(unittest.TestCase):
    def test_ler_config_supabase_completo(self):
        url, key = ler_config_supabase({
            "SUPABASE_URL": " https://exemplo.supabase.co ",
            "SUPABASE_KEY": " chave ",
        })

        self.assertEqual(url, "https://exemplo.supabase.co")
        self.assertEqual(key, "chave")

    def test_ler_config_supabase_incompleto(self):
        with self.assertRaisesRegex(ValueError, "SUPABASE_KEY"):
            ler_config_supabase({
                "SUPABASE_URL": "https://exemplo.supabase.co",
            })


if __name__ == "__main__":
    unittest.main()
