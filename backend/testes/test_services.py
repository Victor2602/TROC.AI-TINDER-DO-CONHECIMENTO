"""Testes da camada de aplicação, sem depender do servidor HTTP."""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd - Troc.AI"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import banco
from backend import services


class ServicesTestCase(unittest.TestCase):
    def setUp(self):
        self.iteracoes_originais = banco.ITERACOES_SENHA
        banco.ITERACOES_SENHA = 1000
        self.conn = banco.conectar(":memory:")
        banco.criar_banco(self.conn)
        banco.popular_demo(self.conn)

    def tearDown(self):
        self.conn.close()
        banco.ITERACOES_SENHA = self.iteracoes_originais

    def test_catalogo_retorna_habilidades_e_categorias(self):
        opcoes = services.obter_opcoes(self.conn)
        self.assertTrue(opcoes["habilidades"])
        self.assertTrue(opcoes["categorias"])
        self.assertEqual({"OUT", "IN"}, {x["codigo"] for x in opcoes["tipos_habilidade"]})

    def test_sugestoes_priorizam_maior_afinidade(self):
        sugestoes = services.obter_sugestoes(self.conn, 1045)
        self.assertEqual(1046, sugestoes[0]["id"])
        self.assertEqual(98.0, sugestoes[0]["indice_afinidade"])

    def test_match_exige_interesse_reciproco(self):
        primeiro = services.registrar_interacao(self.conn, 1045, {
            "para_usuario_id": 1046,
            "acao": "CONECTAR",
        })
        self.assertFalse(primeiro["match"])
        segundo = services.registrar_interacao(self.conn, 1046, {
            "para_usuario_id": 1045,
            "acao": "CONECTAR",
        })
        self.assertTrue(segundo["match"])
        matches = services.listar_matches(self.conn, 1045)
        self.assertEqual(1, len(matches))
        self.assertEqual("Marina Costa", matches[0]["outro_usuario"]["nome"])

    def test_nao_permite_interacao_consigo_mesmo(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.registrar_interacao(self.conn, 1045, {
                "para_usuario_id": 1045,
                "acao": "CONECTAR",
            })

    def test_cadastro_cria_usuario_com_skills(self):
        usuario_id = services.criar_usuario(self.conn, {
            "nome": "Ana Souza",
            "email": "ana@example.com",
            "senha": "senha123",
            "skills_out": ["Python", "SQL", "Git", "Python"],
            "skills_in": ["Inglês"],
        })
        perfil = banco.obter_perfil(self.conn, usuario_id)
        self.assertEqual(["Git", "Python", "SQL"], perfil["skills_out"])
        self.assertEqual(["Inglês"], perfil["skills_in"])


if __name__ == "__main__":
    unittest.main()
