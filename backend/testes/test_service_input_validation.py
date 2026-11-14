"""Testes unitários de validação na camada de serviços (sem Flask).

Execute na raiz do repositório com:
    python -m unittest backend.test_service_input_validation -v
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd_Troc.AI"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import banco
from backend import services


class ServiceInputValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.iteracoes_originais = banco.ITERACOES_SENHA
        banco.ITERACOES_SENHA = 1000
        self.conn = banco.conectar(":memory:")
        banco.criar_banco(self.conn)
        banco.popular_demo(self.conn)

    def tearDown(self):
        self.conn.close()
        banco.ITERACOES_SENHA = self.iteracoes_originais

    @staticmethod
    def payload(**alteracoes):
        dados = {
            "nome": "Ana Souza",
            "email": "ana@example.com",
            "senha": "senha123",
            "skills_out": ["Python", "SQL", "Git"],
            "skills_in": ["Inglês"],
        }
        dados.update(alteracoes)
        return dados

    def test_email_malformado_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(self.conn, self.payload(email="ana.example.com"))

    def test_senha_curta_e_rejeitada_na_camada_de_servicos(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(self.conn, self.payload(senha="12345"))

    def test_senha_acima_do_limite_e_rejeitada(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(self.conn, self.payload(senha="x" * 129))

    def test_foto_url_exige_http_ou_https(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(
                self.conn, self.payload(foto_url="javascript:alert(1)")
            )

    def test_texto_opcional_acima_do_limite_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(
                self.conn, self.payload(bio="x" * 1001)
            )

    def test_nivel_tecnologia_fora_do_catalogo_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(
                self.conn, self.payload(nivel_tecnologia="Expert")
            )

    def test_habilidade_nao_pode_constar_em_out_e_in(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(
                self.conn,
                self.payload(skills_out=["Python", "SQL", "Git"],
                             skills_in=["python", "Inglês"]),
            )

    def test_habilidade_desconhecida_e_rejeitada(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(
                self.conn,
                self.payload(skills_out=["Conhecimento inventado"]),
            )

    def test_campos_desconhecidos_sao_rejeitados(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.criar_usuario(self.conn, self.payload(campo_inesperado="x"))

    def test_duplicatas_de_skill_ignoram_maiusculas_e_minusculas(self):
        usuario_id = services.criar_usuario(
            self.conn,
            self.payload(skills_out=["Python", "python", "SQL", "Git"]),
        )
        perfil = banco.obter_perfil(self.conn, usuario_id)
        self.assertEqual(3, len(perfil["skills_out"]))

    def test_id_booleano_na_interacao_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.registrar_interacao(self.conn, 1045, {
                "para_usuario_id": True,
                "acao": "CONECTAR",
            })

    def test_id_decimal_na_interacao_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.registrar_interacao(self.conn, 1045, {
                "para_usuario_id": 1046.5,
                "acao": "CONECTAR",
            })

    def test_id_acima_do_limite_sqlite_e_rejeitado(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.registrar_interacao(self.conn, 2 ** 63, {
                "para_usuario_id": 1046,
                "acao": "CONECTAR",
            })

    def test_acao_nao_documentada_e_rejeitada(self):
        with self.assertRaises(services.DadosInvalidosError):
            services.registrar_interacao(self.conn, 1045, {
                "para_usuario_id": 1046,
                "acao": "CURTIR",
            })


if __name__ == "__main__":
    unittest.main()
