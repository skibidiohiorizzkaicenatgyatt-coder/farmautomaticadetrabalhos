import re
from datetime import datetime

# ---------- CONFIGURAÇÃO ----------
MODELO_PESQUISA = "claude-haiku-4-5"
MAX_BUSCAS = 5  # buscas na web por trabalho (cada busca tem custo)

USO = {"buscas": 0, "entrada": 0, "saida": 0}
_URL = re.compile(r"https?://[^\s<>\"')\]]+")


def pesquisar_na_web(pedido, plano, instrucoes=""):
    """Pesquisa na web com a ferramenta de busca da Anthropic.
    Retorna (notas, fontes_citadas, todas_as_urls, numero_de_buscas)."""
    import anthropic
    cliente = anthropic.Anthropic()

    prompt = (
        f"Hoje é {datetime.now().strftime('%d/%m/%Y')}. Você é um pesquisador. Use a busca na web "
        "para levantar informações confiáveis e atualizadas que sirvam de base para o documento "
        "descrito abaixo.\n\n"
        f"Pedido: {pedido}\n\nPlano: {plano}\n\n"
        + (f"Instruções do usuário:\n{instrucoes[:3000]}\n\n" if instrucoes else "")
        + f"Regras:\n- Faça no máximo {MAX_BUSCAS} buscas, cada uma com um foco diferente.\n"
        "- Prefira fontes oficiais, institucionais e acadêmicas.\n"
        "- Responda com NOTAS objetivas, organizadas por tema, em português: fatos, dados, datas, "
        "números e, quando o tema for jurídico, nomes e números de leis e artigos relevantes.\n"
        "- Parafraseie com suas palavras; no máximo trechos muito curtos entre aspas.\n"
        "- Não escreva o documento. Não invente nada que você não tenha encontrado."
    )
    mensagens = [{"role": "user", "content": prompt}]
    ferramenta = {"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_BUSCAS}

    notas, citadas, todas, buscas = [], {}, {}, 0
    for _ in range(4):  # a API pode pausar o turno (pause_turn); aí é só continuar
        resp = cliente.messages.create(
            model=MODELO_PESQUISA, max_tokens=4000, tools=[ferramenta], messages=mensagens
        )
        uso = getattr(resp, "usage", None)
        USO["entrada"] += getattr(uso, "input_tokens", 0) or 0
        USO["saida"] += getattr(uso, "output_tokens", 0) or 0
        servidor = getattr(uso, "server_tool_use", None)
        buscas += getattr(servidor, "web_search_requests", 0) or 0

        for bloco in resp.content:
            tipo = getattr(bloco, "type", "")
            if tipo == "text":
                notas.append(bloco.text)
                for c in getattr(bloco, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url and url not in citadas:
                        citadas[url] = getattr(c, "title", None) or url
            elif tipo == "web_search_tool_result":
                conteudo = getattr(bloco, "content", None)
                if isinstance(conteudo, list):
                    for r in conteudo:
                        url = getattr(r, "url", None)
                        if url and url not in todas:
                            todas[url] = getattr(r, "title", None) or url
                else:
                    codigo = getattr(conteudo, "error_code", "desconhecido")
                    print(f"   (uma busca falhou: {codigo})", flush=True)

        if resp.stop_reason == "pause_turn":
            mensagens.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
            continue
        break

    USO["buscas"] += buscas
    if not citadas:  # sem citações: usa as primeiras fontes encontradas
        citadas = dict(list(todas.items())[:8])
    fontes = [{"titulo": t, "url": u} for u, t in citadas.items()]
    return "\n".join(notas).strip(), fontes, list(todas.keys()), buscas


def _normalizar(url):
    url = url.strip().rstrip(".,;:")
    url = re.sub(r"^https?://", "", url, flags=re.I)
    url = re.sub(r"^www\.", "", url, flags=re.I)
    return url.split("#")[0].split("?")[0].rstrip("/").lower()


def verificar_referencias(trabalho, urls_permitidas, nomes_arquivos=()):
    """Mantém só referências verificáveis e remove o resto (provável invenção):
    - referência com endereço: o endereço precisa ter aparecido na pesquisa;
    - referência sem endereço: precisa citar o nome de um arquivo da pasta fontes.
    Retorna (trabalho_corrigido, referencias_removidas)."""
    permitidas = {_normalizar(u) for u in urls_permitidas}
    nomes = []
    for n in nomes_arquivos:
        n = n.lower()
        nomes.append(n)
        stem = n.rsplit(".", 1)[0]
        if len(stem) >= 4:
            nomes.append(stem)
    novos, removidas = [], []
    for b in trabalho.get("blocos", []):
        if b.get("tipo") == "referencia":
            texto = b.get("texto") or ""
            urls = _URL.findall(texto)
            if urls:
                valida = all(_normalizar(u) in permitidas for u in urls)
            else:
                valida = any(n in texto.lower() for n in nomes)
            if not valida:
                removidas.append(texto)
                continue
        novos.append(b)
    if removidas and not any(b.get("tipo") == "referencia" for b in novos):
        # sobrou o título "Referências" sem nada embaixo: tira ele (e a quebra de página antes)
        for i in range(len(novos) - 1, -1, -1):
            b = novos[i]
            if b.get("tipo", "").startswith("titulo") and re.search(r"refer|bibliograf", b.get("texto", ""), re.I):
                del novos[i]
                if i > 0 and novos[i - 1].get("tipo") == "quebra_pagina":
                    del novos[i - 1]
                break
    return {**trabalho, "blocos": novos}, removidas