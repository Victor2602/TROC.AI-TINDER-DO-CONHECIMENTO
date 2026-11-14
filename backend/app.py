"""API HTTP do Troc.ai.

Execute na raiz do repositório com: python -m backend.app
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Dict, Optional
from pathlib import Path
from datetime import timedelta

from flask import Flask, g, jsonify, request, session
from werkzeug.exceptions import BadRequest, HTTPException, UnsupportedMediaType

from . import services

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd - Troc.AI"
if str(DB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(DB_DIR))
import banco  # noqa: E402


def _id_positivo(valor: Optional[str], nome: str) -> int:
    # Query/path params chegam como texto. Não aceitar sinais, decimais,
    # espaços ou valores parcialmente numéricos evita coerções ambíguas.
    if (
        not isinstance(valor, str)
        or len(valor) > 19
        or re.fullmatch(r"[0-9]+", valor) is None
    ):
        raise services.DadosInvalidosError(f"Informe um '{nome}' inteiro positivo válido.")
    identificador = int(valor)
    if identificador <= 0 or identificador > services.MAX_SQLITE_INTEGER:
        raise services.DadosInvalidosError(f"Informe um '{nome}' inteiro positivo.")
    return identificador


def _json_body() -> dict:
    if not request.is_json:
        raise UnsupportedMediaType("Content-Type deve ser application/json.")
    try:
        dados = request.get_json(silent=False)
    except BadRequest as erro:
        raise services.DadosInvalidosError("O corpo da requisição contém JSON malformado.") from erro
    if not isinstance(dados, dict):
        raise services.DadosInvalidosError("Envie um objeto JSON no corpo da requisição.")
    return dados


def create_app(test_config: Optional[Dict] = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("TROCAI_DATABASE", str(DB_DIR / "trocai.db")),
        SEED_DEMO=os.environ.get("TROCAI_SEED_DEMO", "1") == "1",
        # Chave padrão apenas para desenvolvimento local. Para qualquer ambiente
        # compartilhado, configure TROCAI_SECRET_KEY com um valor aleatório forte.
        SECRET_KEY=(
            os.environ.get("TROCAI_SECRET_KEY")
            or "dev-only-trocai-secret-change-before-deployment"
        ),
        SESSION_COOKIE_NAME="trocai_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("TROCAI_COOKIE_SECURE", "0").lower()
        in {"1", "true", "yes"},
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024,  # limite técnico de 64 KiB por requisição
    )
    if test_config:
        app.config.update(test_config)

    _inicializar_banco(app)

    if (
        app.config["SECRET_KEY"] == "dev-only-trocai-secret-change-before-deployment"
        and not app.testing
    ):
        app.logger.warning(
            "TROCAI_SECRET_KEY não configurada; usando chave de desenvolvimento. "
            "Não utilize essa chave em ambiente compartilhado ou produção."
        )

    def get_db():
        if "db" not in g:
            g.db = banco.conectar(app.config["DATABASE"])
        return g.db

    @app.teardown_appcontext
    def fechar_conexao(_erro=None):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.errorhandler(services.DadosInvalidosError)
    def tratar_dados_invalidos(erro):
        return jsonify({"erro": str(erro)}), 400

    @app.errorhandler(services.RecursoNaoEncontradoError)
    def tratar_recurso_nao_encontrado(erro):
        return jsonify({"erro": str(erro)}), 404

    @app.errorhandler(services.AutenticacaoNecessariaError)
    def tratar_autenticacao_necessaria(erro):
        return jsonify({"erro": str(erro)}), 401

    @app.errorhandler(banco.RegraDeNegocioError)
    def tratar_regra_de_negocio(erro):
        return jsonify({"erro": str(erro)}), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def tratar_integridade(_erro):
        # Não expõe detalhes SQL; conflitos de unicidade/integridade usam 409.
        return jsonify({
            "erro": "A operação viola uma restrição de integridade ou entra em conflito com dados existentes."
        }), 409

    @app.errorhandler(HTTPException)
    def tratar_erro_http(erro):
        mensagens = {
            400: "Requisição inválida.",
            404: "Rota não encontrada.",
            405: "Método HTTP não permitido para esta rota.",
            413: "O corpo da requisição excede o tamanho permitido.",
            415: "Tipo de conteúdo não suportado.",
        }
        status = erro.code or 500
        return jsonify({"erro": mensagens.get(status, "Não foi possível processar a requisição.")}), status

    @app.errorhandler(Exception)
    def tratar_erro_interno(erro):
        app.logger.error(
            "Erro não tratado durante o processamento da requisição",
            exc_info=(type(erro), erro, erro.__traceback__),
        )
        return jsonify({"erro": "Erro interno do servidor."}), 500

    def usuario_autenticado_id() -> int:
        """Obtém o principal autenticado; nunca confia em IDs enviados pelo cliente."""
        usuario_id = session.get("usuario_id")
        if (
            isinstance(usuario_id, bool)
            or not isinstance(usuario_id, int)
            or usuario_id <= 0
            or usuario_id > services.MAX_SQLITE_INTEGER
        ):
            raise services.AutenticacaoNecessariaError(
                "Autenticação necessária. Faça login para continuar."
            )
        return usuario_id

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "servico": "trocai-api"})

    @app.get("/api/opcoes")
    def opcoes():
        return jsonify(services.obter_opcoes(get_db()))

    @app.post("/api/usuarios")
    def cadastrar_usuario():
        usuario_id = services.criar_usuario(get_db(), _json_body())
        return jsonify({
            "mensagem": "Usuário cadastrado com sucesso.",
            "usuario_id": usuario_id,
        }), 201

    @app.post("/api/login")
    def login():
        payload = _json_body()
        # Um novo login substitui qualquer identidade anteriormente autenticada
        # neste navegador, inclusive quando as credenciais enviadas forem inválidas.
        session.clear()
        usuario_id = services.autenticar_usuario(get_db(), payload)
        if usuario_id is None:
            return jsonify({"erro": "E-mail ou senha inválidos."}), 401
        session["usuario_id"] = usuario_id
        session.permanent = True
        return jsonify({"usuario_id": usuario_id, "mensagem": "Autenticação realizada."})

    @app.get("/api/sessao")
    def sessao_atual():
        usuario_id = usuario_autenticado_id()
        perfil = services.obter_perfil(get_db(), usuario_id)
        if perfil is None:
            session.clear()
            raise services.AutenticacaoNecessariaError(
                "A sessão não corresponde a um usuário ativo. Faça login novamente."
            )
        return jsonify({
            "autenticado": True,
            "usuario": {"id": perfil["id"], "nome": perfil["nome"]},
        })

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"mensagem": "Sessão encerrada."})

    @app.get("/api/usuarios/<usuario_id>")
    def perfil(usuario_id: str):
        identificador = _id_positivo(usuario_id, "usuario_id")
        dados = services.obter_perfil(get_db(), identificador)
        if dados is None:
            return jsonify({"erro": "Usuário não encontrado."}), 404
        return jsonify(dados)

    @app.get("/api/sugestoes")
    def sugestoes():
        # O usuário vem da sessão. Rejeitar o antigo parâmetro evita que clientes
        # continuem acreditando que podem escolher a identidade por query string.
        if "usuario_id" in request.args:
            raise services.DadosInvalidosError(
                "O usuário é identificado pela sessão; não envie 'usuario_id'."
            )
        valor_limite = request.args.get("limite", "10")
        if len(valor_limite) > 2 or re.fullmatch(r"[0-9]+", valor_limite) is None:
            raise services.DadosInvalidosError("O limite deve ser um número inteiro positivo.")
        limite = int(valor_limite)
        usuario_id = usuario_autenticado_id()
        return jsonify(services.obter_sugestoes(get_db(), usuario_id, limite))

    @app.post("/api/interacoes")
    def interacoes():
        usuario_id = usuario_autenticado_id()
        resultado = services.registrar_interacao(get_db(), usuario_id, _json_body())
        status = 201 if resultado["match"] else 200
        return jsonify(resultado), status

    @app.get("/api/matches")
    def matches():
        if request.args:
            raise services.DadosInvalidosError(
                "O usuário é identificado pela sessão; não envie parâmetros de usuário."
            )
        usuario_id = usuario_autenticado_id()
        return jsonify(services.listar_matches(get_db(), usuario_id))

    return app


def _inicializar_banco(app: Flask) -> None:
    caminho = app.config["DATABASE"]
    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conn = banco.conectar(caminho)
    try:
        existe_schema = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if existe_schema is None:
            banco.criar_banco(conn)
            if app.config["SEED_DEMO"]:
                banco.popular_demo(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=3001, debug=True)
