async function pedir(url, opcoes = {}) {
  const resposta = await fetch(url, {
    ...opcoes,
    credentials: "same-origin",
    headers: {
      ...(opcoes.body ? { "Content-Type": "application/json" } : {}),
      ...opcoes.headers,
    },
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    const erro = new Error(dados.erro || "Erro na requisição");
    erro.status = resposta.status;
    throw erro;
  }
  return dados;
}

export const obterSessao = () => pedir("/api/sessao");
export const obterOpcoes = () => pedir("/api/opcoes");
export const buscar = async (q, tipo) => {
  const perfis = await pedir("/api/sugestoes?limite=50");
  const consulta = q.trim().toLowerCase();

  return perfis.filter((perfil) => {
    const habilidades = tipo === "oferta"
      ? perfil.skills_out
      : tipo === "demanda"
        ? perfil.skills_in
        : [...perfil.skills_out, ...perfil.skills_in];
    const textos = [
      perfil.nome,
      perfil.curso,
      perfil.instituicao,
      perfil.bio,
      perfil.cidade,
      perfil.zona,
      ...habilidades,
    ];
    return !consulta || textos.some((texto) => texto?.toLowerCase().includes(consulta));
  });
};
export const cadastrar = (dados) =>
  pedir("/api/usuarios", { method: "POST", body: JSON.stringify(dados) });
export const entrar = (dados) =>
  pedir("/api/login", { method: "POST", body: JSON.stringify(dados) });
export const sair = () => pedir("/api/logout", { method: "POST", body: "{}" });
export const obterMatches = () => pedir("/api/matches");
export const conectarPerfil = (para_usuario_id) =>
  pedir("/api/interacoes", {
    method: "POST",
    body: JSON.stringify({ para_usuario_id, acao: "CONECTAR" }),
  });

export function notificarMudancaSessao() {
  window.dispatchEvent(new Event("trocai-sessao-alterada"));
}
