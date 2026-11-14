"""Testes de autenticação por sessão e autorização básica.

Execute na raiz do repositório com:
    python -m unittest backend.test_auth -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd - Troc.AI"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import banco
from backend.app import create_app


class AuthenticationTestCase(unittest.TestCase):
    def setUp(self):
        self.iteracoes_originais = banco.ITERACOES_SENHA
        banco.ITERACOES_SENHA = 1000
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tempdir.name) / "auth-test.db")
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
        self.assertEqual({"erro"}, set(response.get_json()))

    def test_endpoints_privados_exigem_autenticacao(self):
        respostas = [
            self.client.get("/api/sessao"),
            self.client.get("/api/sugestoes"),
            self.client.get("/api/matches"),
            self.client.post("/api/interacoes", json={
                "para_usuario_id": 1046,
                "acao": "CONECTAR",
            }),
        ]
        for resposta in respostas:
            self.assert_json_error(resposta, 401)

    def test_login_cria_sessao_e_endpoint_sessao_identifica_usuario(self):
        resposta_login = self.login()
        self.assertEqual(200, resposta_login.status_code)
        self.assertEqual(1045, resposta_login.get_json()["usuario_id"])

        resposta_sessao = self.client.get("/api/sessao")
        self.assertEqual(200, resposta_sessao.status_code)
        self.assertEqual({
            "autenticado": True,
            "usuario": {"id": 1045, "nome": "Lucas Andrade"},
        }, resposta_sessao.get_json())

    def test_login_invalido_remove_sessao_anterior(self):
        self.assertEqual(200, self.login().status_code)
        resposta = self.login(senha="senha-incorreta")
        self.assert_json_error(resposta, 401)
        self.assert_json_error(self.client.get("/api/sessao"), 401)

    def test_logout_limpa_sessao(self):
        self.assertEqual(200, self.login().status_code)
        resposta = self.client.post("/api/logout")
        self.assertEqual(200, resposta.status_code)
        self.assert_json_error(self.client.get("/api/sessao"), 401)

    def test_perfil_publico_pode_ser_consultado_sem_login(self):
        resposta = self.client.get("/api/usuarios/1045")
        self.assertEqual(200, resposta.status_code)
        perfil = resposta.get_json()
        self.assertEqual("Lucas Andrade", perfil["nome"])
        self.assertNotIn("email", perfil)

    def test_interacao_usa_usuario_da_sessao_e_rejeita_autor_no_payload(self):
        self.assertEqual(200, self.login().status_code)

        tentativa_de_impersonacao = self.client.post("/api/interacoes", json={
            "de_usuario_id": 1046,
            "para_usuario_id": 1045,
            "acao": "CONECTAR",
        })
        self.assert_json_error(tentativa_de_impersonacao, 400)

        resposta = self.client.post("/api/interacoes", json={
            "para_usuario_id": 1046,
            "acao": "CONECTAR",
        })
        self.assertEqual(200, resposta.status_code)
        self.assertFalse(resposta.get_json()["match"])

        with self.app.app_context():
            conn = banco.conectar(self.app.config["DATABASE"])
            try:
                registro = conn.execute(
                    "SELECT de_usuario_id, para_usuario_id FROM interacoes"
                ).fetchone()
            finally:
                conn.close()
        self.assertEqual((1045, 1046), tuple(registro))

    def test_usuario_id_na_query_nao_pode_escolher_identidade(self):
        self.assertEqual(200, self.login().status_code)
        resposta = self.client.get("/api/sugestoes?usuario_id=1046")
        self.assert_json_error(resposta, 400)

    def test_configuracao_basica_do_cookie_de_sessao(self):
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual("Lax", self.app.config["SESSION_COOKIE_SAMESITE"])
        self.assertEqual(8 * 60 * 60, self.app.config["PERMANENT_SESSION_LIFETIME"].total_seconds())


if __name__ == "__main__":
    unittest.main()
