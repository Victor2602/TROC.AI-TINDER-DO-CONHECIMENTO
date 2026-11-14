"""Camada de aplicação: valida entradas e coordena operações do domínio.

As regras centrais de persistência e matching permanecem em ``banco.py``.
Este módulo não conhece Flask nem detalhes de HTTP.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "Bd_Troc.AI"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import banco  # noqa: E402  (módulo existente da camada de dados)


class DadosInvalidosError(ValueError):
    """Entrada ausente ou em formato inválido para um caso de uso."""


class RecursoNaoEncontradoError(LookupError):
    """Usuário ou outro recurso solicitado não existe."""


class AutenticacaoNecessariaError(PermissionError):
    """A operação exige uma sessão autenticada."""


EMAIL_RE = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
)
NIVEIS_TECNOLOGIA = ("Básico", "Intermediário", "Avançado")

# Limites técnicos do contrato HTTP. Não substituem as regras do domínio.
LIMITES_TEXTO = {
    "nome": 100,
    "email": 254,
    "curso": 120,
    "instituicao": 160,
    "bio": 1000,
    "foto_url": 2048,
    "cidade": 120,
    "zona": 120,
    "nivel_tecnologia": 30,
}
MAX_SENHA = 128
MAX_NOME_HABILIDADE = 80
MAX_SQLITE_INTEGER = (2 ** 63) - 1


def _rejeitar_campos_desconhecidos(payload: Dict[str, Any], permitidos) -> None:
    desconhecidos = sorted(set(payload) - set(permitidos))
    if desconhecidos:
        campos = ", ".join(desconhecidos)
        raise DadosInvalidosError(f"Campo(s) não reconhecido(s): {campos}.")


def _texto(
    payload: Dict[str, Any],
    campo: str,
    *,
    obrigatorio: bool = False,
    max_chars: Optional[int] = None,
) -> Optional[str]:
    valor = payload.get(campo)
    if valor is None:
        if obrigatorio:
            raise DadosInvalidosError(f"O campo '{campo}' é obrigatório.")
        return None
    if not isinstance(valor, str):
        raise DadosInvalidosError(f"O campo '{campo}' deve ser texto.")
    valor = valor.strip()
    if obrigatorio and not valor:
        raise DadosInvalidosError(f"O campo '{campo}' é obrigatório.")
    if max_chars is not None and len(valor) > max_chars:
        raise DadosInvalidosError(
            f"O campo '{campo}' deve ter no máximo {max_chars} caracteres."
        )
    return valor or None


def _senha(payload: Dict[str, Any], *, cadastro: bool = False) -> str:
    valor = payload.get("senha")
    if not isinstance(valor, str) or not valor:
        raise DadosInvalidosError("O campo 'senha' é obrigatório.")
    # Senhas não são normalizadas: espaços podem fazer parte da credencial.
    if len(valor) > MAX_SENHA:
        raise DadosInvalidosError(
            f"A senha deve ter no máximo {MAX_SENHA} caracteres."
        )
    if cadastro and len(valor) < 6:
        raise DadosInvalidosError("A senha deve ter ao menos 6 caracteres.")
    return valor


def _lista_textos(payload: Dict[str, Any], campo: str) -> List[str]:
    valores = payload.get(campo, [])
    if not isinstance(valores, list) or any(not isinstance(v, str) for v in valores):
        raise DadosInvalidosError(f"O campo '{campo}' deve ser uma lista de textos.")

    # A chave casefold evita duplicatas que o catálogo SQLite considera iguais
    # por COLLATE NOCASE (por exemplo, "Python" e "python").
    resultado = []
    vistos = set()
    for item in valores:
        nome = item.strip()
        if not nome:
            continue
        if len(nome) > MAX_NOME_HABILIDADE:
            raise DadosInvalidosError(
                f"Cada habilidade em '{campo}' deve ter no máximo "
                f"{MAX_NOME_HABILIDADE} caracteres."
            )
        chave = nome.casefold()
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(nome)
    return resultado


def _id_positivo(payload: Dict[str, Any], campo: str) -> int:
    valor = payload.get(campo)
    # bool é subclasse de int em Python, mas não é identificador JSON válido.
    if (
        isinstance(valor, bool)
        or not isinstance(valor, int)
        or valor <= 0
        or valor > MAX_SQLITE_INTEGER
    ):
        raise DadosInvalidosError(
            f"O campo '{campo}' deve ser um inteiro positivo."
        )
    return valor


def obter_opcoes(conn) -> Dict[str, List[Any]]:
    """Retorna o catálogo real do banco para montar formulários no front-end."""
    habilidades = banco.listar_habilidades(conn)
    categorias = sorted({item["categoria"] for item in habilidades})
    return {
        "categorias": categorias,
        "habilidades": habilidades,
        "niveis_tecnologia": ["Básico", "Intermediário", "Avançado"],
        "tipos_habilidade": [
            {"codigo": "OUT", "descricao": "Ofereço / sei ensinar"},
            {"codigo": "IN", "descricao": "Quero aprender"},
        ],
    }


def criar_usuario(conn, payload: Dict[str, Any]) -> int:
    if not isinstance(payload, dict):
        raise DadosInvalidosError("O corpo da requisição deve ser um objeto JSON.")

    permitidos = {
        "nome", "email", "senha", "curso", "instituicao", "bio",
        "foto_url", "cidade", "zona", "nivel_tecnologia",
        "skills_out", "skills_in",
    }
    _rejeitar_campos_desconhecidos(payload, permitidos)

    nome = _texto(payload, "nome", obrigatorio=True, max_chars=LIMITES_TEXTO["nome"])
    email = _texto(payload, "email", obrigatorio=True, max_chars=LIMITES_TEXTO["email"])
    if not EMAIL_RE.fullmatch(email):
        raise DadosInvalidosError("Informe um endereço de e-mail válido.")
    email = email.lower()
    senha = _senha(payload, cadastro=True)

    skills_out = _lista_textos(payload, "skills_out")
    skills_in = _lista_textos(payload, "skills_in")
    sobreposicao = {item.casefold() for item in skills_out} & {
        item.casefold() for item in skills_in
    }
    if sobreposicao:
        raise DadosInvalidosError(
            "Uma mesma habilidade não pode constar em 'skills_out' e 'skills_in'."
        )

    # Valida nomes antes da persistência para que erros de catálogo sejam
    # tratados como entrada inválida, sem depender de uma exceção SQL.
    catalogo = {
        item["nome"].casefold(): item["nome"]
        for item in banco.listar_habilidades(conn)
    }
    desconhecidas = [
        nome_habilidade
        for nome_habilidade in skills_out + skills_in
        if nome_habilidade.casefold() not in catalogo
    ]
    if desconhecidas:
        raise DadosInvalidosError(
            "Habilidade(s) não encontrada(s) no catálogo: "
            + ", ".join(desconhecidas)
            + "."
        )
    # Persistir o nome canônico do catálogo evita divergência entre a comparação
    # Unicode do Python e a collation NOCASE (ASCII) utilizada pelo SQLite.
    skills_out = [catalogo[item.casefold()] for item in skills_out]
    skills_in = [catalogo[item.casefold()] for item in skills_in]

    campos_opcionais = {
        campo: _texto(
            payload,
            campo,
            max_chars=LIMITES_TEXTO[campo],
        )
        for campo in (
            "curso", "instituicao", "bio", "foto_url", "cidade", "zona",
            "nivel_tecnologia",
        )
    }
    nivel = campos_opcionais["nivel_tecnologia"]
    if nivel is not None and nivel not in NIVEIS_TECNOLOGIA:
        raise DadosInvalidosError(
            "O campo 'nivel_tecnologia' deve ser Básico, Intermediário ou Avançado."
        )

    foto_url = campos_opcionais["foto_url"]
    if foto_url is not None:
        partes_url = urlsplit(foto_url)
        if partes_url.scheme not in {"http", "https"} or not partes_url.netloc:
            raise DadosInvalidosError(
                "O campo 'foto_url' deve ser uma URL absoluta com esquema http ou https."
            )

    return banco.criar_usuario(
        conn,
        nome=nome,
        email=email,
        senha=senha,
        skills_out=skills_out,
        skills_in=skills_in,
        **campos_opcionais,
    )


def autenticar_usuario(conn, payload: Dict[str, Any]) -> Optional[int]:
    if not isinstance(payload, dict):
        raise DadosInvalidosError("O corpo da requisição deve ser um objeto JSON.")
    _rejeitar_campos_desconhecidos(payload, {"email", "senha"})
    email = _texto(payload, "email", obrigatorio=True, max_chars=LIMITES_TEXTO["email"])
    if not EMAIL_RE.fullmatch(email):
        raise DadosInvalidosError("Informe um endereço de e-mail válido.")
    senha = _senha(payload)
    return banco.autenticar(conn, email.lower(), senha)


def _perfil_publico(perfil: dict) -> dict:
    """Projeta apenas atributos apropriados para exibição a outros usuários."""
    campos = (
        "id", "nome", "curso", "instituicao", "bio", "foto_url", "cidade",
        "zona", "nivel_tecnologia", "criado_em", "skills_out", "skills_in",
        "perfil_ativo", "reputacao", "selos",
    )
    return {campo: perfil.get(campo) for campo in campos}


def obter_perfil(conn, usuario_id: int) -> Optional[dict]:
    perfil = banco.obter_perfil(conn, usuario_id)
    return _perfil_publico(perfil) if perfil is not None else None


def obter_sugestoes(conn, usuario_id: int, limite: int = 10) -> List[dict]:
    if limite < 1 or limite > 50:
        raise DadosInvalidosError("O limite deve estar entre 1 e 50.")
    if not banco.usuario_existe(conn, usuario_id):
        raise RecursoNaoEncontradoError("Usuário não encontrado.")
    perfis = banco.sugestoes(conn, usuario_id, limite=limite)
    return [
        {**_perfil_publico(perfil), "indice_afinidade": perfil["indice_afinidade"]}
        for perfil in perfis
    ]


def registrar_interacao(
    conn, usuario_autenticado_id: int, payload: Dict[str, Any]
) -> dict:
    """Registra uma ação em nome do usuário identificado pela sessão.

    O identificador do autor não faz parte do payload recebido do cliente:
    ele é fornecido pelo Controller a partir da sessão autenticada.
    """
    if not isinstance(payload, dict):
        raise DadosInvalidosError("O corpo da requisição deve ser um objeto JSON.")
    if (
        isinstance(usuario_autenticado_id, bool)
        or not isinstance(usuario_autenticado_id, int)
        or usuario_autenticado_id <= 0
        or usuario_autenticado_id > MAX_SQLITE_INTEGER
    ):
        raise DadosInvalidosError("A identificação do usuário autenticado é inválida.")
    _rejeitar_campos_desconhecidos(payload, {"para_usuario_id", "acao"})

    de_usuario_id = usuario_autenticado_id
    para_usuario_id = _id_positivo(payload, "para_usuario_id")
    if de_usuario_id == para_usuario_id:
        raise DadosInvalidosError("Um usuário não pode interagir consigo mesmo.")
    if not banco.usuario_existe(conn, de_usuario_id):
        raise RecursoNaoEncontradoError("Usuário autenticado não encontrado.")
    if not banco.usuario_existe(conn, para_usuario_id):
        raise RecursoNaoEncontradoError("Usuário destinatário não encontrado.")

    acao = _texto(payload, "acao", obrigatorio=True, max_chars=20)
    acao = acao.upper()
    if acao not in {"CONECTAR", "DESCARTAR"}:
        raise DadosInvalidosError("A ação deve ser CONECTAR ou DESCARTAR.")
    return banco.registrar_interacao(conn, de_usuario_id, para_usuario_id, acao)


def listar_matches(conn, usuario_id: int) -> List[dict]:
    """Retorna matches mútuos com o perfil do outro participante.

    A tabela ``matches`` só recebe registros após interesse recíproco; por isso
    não existe aqui o conceito de match parcial.
    """
    if not banco.usuario_existe(conn, usuario_id):
        raise RecursoNaoEncontradoError("Usuário não encontrado.")
    resultado = []
    for match in banco.listar_matches(conn, usuario_id):
        perfil = banco.obter_perfil(conn, match["outro_usuario_id"])
        if perfil is None:
            continue
        resultado.append({
            "match_id": match["match_id"],
            "indice_afinidade": match["indice_afinidade"],
            "criado_em": match["criado_em"],
            "outro_usuario": _perfil_publico(perfil),
        })
    return resultado
