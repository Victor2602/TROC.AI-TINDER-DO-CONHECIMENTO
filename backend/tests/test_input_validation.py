"""Testes de validação de entradas dos Services e da API HTTP.

Execute na raiz do repositório com:
    python -m unittest backend.test_input_validation -v
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
from backend import services
from backend.app import create_app


class InputValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.iteracoes_originais = banco.ITERACOES_SENHA
        banco.ITERACOES_SENHA = 1000
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.tempdir.name) / "validation-test.db")
        self.app = create_app({
            "TESTING": True,
            "DATABASE": db_path,
            "SEED_DEMO": True,
        })
        self.client = self.app.test_client()

    def login_demo(self):
        return self.client.post("/api/login", json={
            "email": "lucas.andrade@troc.ai",
            "senha": "senha123",
        })

    def tearDown(self):
        self.tempdir.cleanup()
        banco.ITERACOES_SENHA = self.iteracoes_originais

    @staticmethod
    def novo_usuario(**alteracoes):
        payload = {
            "nome": "Ana Souza",
            "email": "ana@example.com",
            "senha": "senha123",
            "skills_out": ["Python", "SQL", "Git"],
            "skills_in": ["Inglês"],
        }
        payload.update(alteracoes)
        return payload

    def assert_json_error(self, response, status):
        self.assertEqual(status, response.status_code)
        self.assertTrue(response.is_json)
        payload = response.get_json()
        self.assertEqual({"erro"}, set(payload.keys()))
        self.assertTrue(payload["erro"])

    def test_nome_vazio_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(nome="   ")
        )
        self.assert_json_error(resposta, 400)

    def test_email_malformado_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(email="ana.example.com")
        )
        self.assert_json_error(resposta, 400)

    def test_email_e_normalizado_para_minusculas(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(email="ANA@EXAMPLE.COM")
        )
        self.assertEqual(201, resposta.status_code)
        usuario_id = resposta.get_json()["usuario_id"]
        perfil = self.client.get(f"/api/usuarios/{usuario_id}")
        self.assertEqual(200, perfil.status_code)

    def test_senha_curta_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(senha="12345")
        )
        self.assert_json_error(resposta, 400)

    def test_senha_acima_do_limite_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(senha="s" * 129)
        )
        self.assert_json_error(resposta, 400)

    def test_foto_url_sem_esquema_http_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(foto_url="javascript:alert(1)")
        )
        self.assert_json_error(resposta, 400)

    def test_bio_acima_do_limite_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(bio="x" * 1001)
        )
        self.assert_json_error(resposta, 400)

    def test_nivel_tecnologia_invalido_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(nivel_tecnologia="Expert")
        )
        self.assert_json_error(resposta, 400)

    def test_habilidade_em_out_e_in_retorna_400_sem_criar_usuario(self):
        antes = self.client.get("/api/opcoes")
        self.assertEqual(200, antes.status_code)
        resposta = self.client.post(
            "/api/usuarios",
            json=self.novo_usuario(skills_in=["Python", "Inglês"]),
        )
        self.assert_json_error(resposta, 400)
        with self.app.app_context():
            conn = banco.conectar(self.app.config["DATABASE"])
            try:
                quantidade = conn.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE email = ?",
                    ("ana@example.com",),
                ).fetchone()[0]
            finally:
                conn.close()
        self.assertEqual(0, quantidade)

    def test_habilidade_desconhecida_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios",
            json=self.novo_usuario(skills_out=["Habilidade que não existe"]),
        )
        self.assert_json_error(resposta, 400)

    def test_campo_desconhecido_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(campo_erro="valor")
        )
        self.assert_json_error(resposta, 400)

    def test_habilidade_duplicada_ignorando_caixa_e_removida(self):
        resposta = self.client.post(
            "/api/usuarios",
            json=self.novo_usuario(skills_out=["Python", "python", "SQL", "Git"]),
        )
        self.assertEqual(201, resposta.status_code)
        usuario_id = resposta.get_json()["usuario_id"]
        perfil = self.client.get(f"/api/usuarios/{usuario_id}").get_json()
        self.assertEqual(3, len(perfil["skills_out"]))

    def test_lista_de_habilidades_com_elemento_nao_textual_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios",
            json=self.novo_usuario(skills_out=["Python", 123, "SQL"]),
        )
        self.assert_json_error(resposta, 400)

    def test_senha_nao_textual_retorna_400(self):
        resposta = self.client.post(
            "/api/usuarios", json=self.novo_usuario(senha=123456)
        )
        self.assert_json_error(resposta, 400)

    def test_id_decimal_na_interacao_retorna_400(self):
        self.assertEqual(200, self.login_demo().status_code)
        resposta = self.client.post("/api/interacoes", json={
            "para_usuario_id": 1046.5,
            "acao": "CONECTAR",
        })
        self.assert_json_error(resposta, 400)

    def test_id_booleano_na_interacao_retorna_400(self):
        self.assertEqual(200, self.login_demo().status_code)
        resposta = self.client.post("/api/interacoes", json={
            "para_usuario_id": True,
            "acao": "CONECTAR",
        })
        self.assert_json_error(resposta, 400)

    def test_acao_desconhecida_retorna_400(self):
        self.assertEqual(200, self.login_demo().status_code)
        resposta = self.client.post("/api/interacoes", json={
            "para_usuario_id": 1046,
            "acao": "CURTIR",
        })
        self.assert_json_error(resposta, 400)

    def test_campo_extra_na_interacao_retorna_400(self):
        self.assertEqual(200, self.login_demo().status_code)
        resposta = self.client.post("/api/interacoes", json={
            "de_usuario_id": 1046,
            "para_usuario_id": 1045,
            "acao": "CONECTAR",
        })
        self.assert_json_error(resposta, 400)

    def test_content_type_incorreto_retorna_415_json(self):
        resposta = self.client.post(
            "/api/login", data='{"email":"lucas.andrade@troc.ai"}',
            content_type="text/plain",
        )
        self.assert_json_error(resposta, 415)

    def test_json_malformado_retorna_400_json(self):
        resposta = self.client.post(
            "/api/login", data='{"email":', content_type="application/json"
        )
        self.assert_json_error(resposta, 400)

    def test_corpo_json_array_retorna_400(self):
        resposta = self.client.post(
            "/api/login", json=["lucas.andrade@troc.ai", "senha123"]
        )
        self.assert_json_error(resposta, 400)

    def test_usuario_id_acima_do_limite_sqlite_retorna_400(self):
        resposta = self.client.get("/api/usuarios/9223372036854775808")
        self.assert_json_error(resposta, 400)

    def test_usuario_id_com_muitos_digitos_retorna_400(self):
        resposta = self.client.get("/api/matches?usuario_id=" + ("9" * 5000))
        self.assert_json_error(resposta, 400)

    def test_limite_decimal_retorna_400(self):
        self.assertEqual(200, self.login_demo().status_code)
        resposta = self.client.get("/api/sugestoes?limite=1.5")
        self.assert_json_error(resposta, 400)

    def test_corpo_acima_de_64_kib_retorna_413_json(self):
        resposta = self.client.post(
            "/api/login",
            data=b"{" + (b" " * (64 * 1024)) + b"}",
            content_type="application/json",
        )
        self.assert_json_error(resposta, 413)


if __name__ == "__main__":
    unittest.main()
