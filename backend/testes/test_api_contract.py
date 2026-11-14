"""Testes HTTP do contrato público da API.

Execute na raiz do repositório com: python -m unittest backend.test_api_contract -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd_Troc.AI"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import banco
from backend.app import create_app


class ApiContractTestCase(unittest.TestCase):
    def setUp(self):
        self.iteracoes_originais = banco.ITERACOES_SENHA
        banco.ITERACOES_SENHA = 1000
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tempdir.name) / "api-test.db")
        self.app = create_app({
            "TESTING": True,
            "DATABASE": db_path,
            "SEED_DEMO": True,
            "SECRET_KEY": "test-secret-key",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()
        banco.ITERACOES_SENHA = self.iteracoes_originais

    def login(self, email="lucas.andrade@troc.ai", senha="senha123"):
        return self.client.post("/api/login", json={"email": email, "senha": senha})

    def assert_json_error(self, response, status):
        self.assertEqual(status, response.status_code)
        self.assertTrue(response.is_json)
        payload = response.get_json()
        self.assertEqual({"erro"}, set(payload.keys()))
        self.assertTrue(payload["erro"])

    def test_endpoint_inexistente_retorna_404_json(self):
        response = self.client.get("/api/nao-existe")
        self.assert_json_error(response, 404)

    def test_metodo_nao_permitido_retorna_405_json(self):
        response = self.client.post("/api/opcoes")
        self.assert_json_error(response, 405)

    def test_identificador_malformado_retorna_400_json(self):
        response = self.client.get("/api/usuarios/abc")
        self.assert_json_error(response, 400)

    def test_perfil_publico_de_usuario_inexistente_retorna_404(self):
        resposta = self.client.get("/api/usuarios/999999")
        self.assert_json_error(resposta, 404)

    def test_contrato_de_matches_usa_indice_afinidade(self):
        login_lucas = self.login()
        self.assertEqual(200, login_lucas.status_code)

        primeira = self.client.post("/api/interacoes", json={
            "para_usuario_id": 1046,
            "acao": "CONECTAR",
        })
        self.assertEqual(200, primeira.status_code)
        self.assertTrue(primeira.is_json)

        # A consulta deve representar apenas a conta autenticada (Lucas).
        sem_match = self.client.get("/api/matches")
        self.assertEqual(200, sem_match.status_code)
        self.assertEqual([], sem_match.get_json())

        # Um novo login substitui a identidade da sessão anterior.
        login_marina = self.login("marina.costa@troc.ai")
        self.assertEqual(200, login_marina.status_code)
        segunda = self.client.post("/api/interacoes", json={
            "para_usuario_id": 1045,
            "acao": "CONECTAR",
        })
        self.assertEqual(201, segunda.status_code)
        self.assertTrue(segunda.get_json()["match"])

        # Lucas volta a autenticar e consulta o mesmo match.
        self.login()
        resposta = self.client.get("/api/matches")
        self.assertEqual(200, resposta.status_code)
        match = resposta.get_json()[0]
        self.assertIn("indice_afinidade", match)
        self.assertNotIn("afinidade", match)
        self.assertIn("outro_usuario", match)
        self.assertEqual(1046, match["outro_usuario"]["id"])

    def test_conflito_de_integridade_retorna_409_sem_expor_sql(self):
        payload = {
            "nome": "Outro Lucas",
            "email": "lucas.andrade@troc.ai",
            "senha": "senha123",
        }
        resposta = self.client.post("/api/usuarios", json=payload)
        self.assert_json_error(resposta, 409)
        self.assertNotIn("UNIQUE constraint", resposta.get_json()["erro"])


if __name__ == "__main__":
    unittest.main()
