import math
import re
import unicodedata
from collections import Counter

TAM_TRECHO = 1500  # caracteres por trecho
_PAGINA = re.compile(r"^\[p\. (\d+)\]$")
_STOP = set(
    "de da do das dos a o as os e em um uma uns umas para por com que se na no nas nos ao aos "
    "ou mais como mas foi ser tem ter sua seu suas seus este esta estes estas isso essa esse "
    "entre sobre ate sao nao pelo pela pelos pelas ja tambem apos quando muito cada onde qual "
    "quais sem sob seja pode podem deve devem art lei".split()
)


def _tokens(texto):
    """Palavras em minúsculas, sem acento, cortadas nas 6 primeiras letras (aproxima o radical)."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return [t[:6] for t in re.findall(r"[a-z0-9]+", texto) if len(t) >= 3 and t not in _STOP]


def _dividir(texto, tam=TAM_TRECHO):
    """Divide o texto em trechos de ~tam caracteres, guardando a página onde cada um começa."""
    trechos, linhas, tamanho = [], [], 0
    pagina_atual, pagina_trecho = None, None

    def fechar():
        nonlocal linhas, tamanho, pagina_trecho
        if linhas:
            trechos.append({"texto": "\n".join(linhas), "pagina": pagina_trecho})
        linhas, tamanho, pagina_trecho = [], 0, None

    for linha in texto.split("\n"):
        linha = linha.strip()
        if not linha:
            continue
        m = _PAGINA.match(linha)
        if m:
            pagina_atual = int(m.group(1))
        while len(linha) > tam:  # linha enorme: corta em pedaços
            fechar()
            pagina_trecho = pagina_atual
            linhas.append(linha[:tam])
            tamanho = tam
            fechar()
            linha = linha[tam:]
        if not linha:
            continue
        if tamanho + len(linha) > tam and linhas:
            fechar()
        if not linhas:
            pagina_trecho = pagina_atual
        linhas.append(linha)
        tamanho += len(linha) + 1
    fechar()
    return trechos


def _pontuar(trechos, consulta):
    """Pontuação BM25 de cada trecho em relação à consulta."""
    docs = [_tokens(t["texto"]) for t in trechos]
    n = len(docs)
    media = (sum(len(d) for d in docs) / n) if n else 1
    media = media or 1
    df = Counter()
    for d in docs:
        df.update(set(d))
    consulta_tf = Counter(_tokens(consulta))
    k1, b = 1.5, 0.75
    pontos = []
    for d in docs:
        tf, dl, s = Counter(d), len(d), 0.0
        for termo, qf in consulta_tf.items():
            f = tf.get(termo)
            if not f:
                continue
            idf = math.log(1 + (n - df[termo] + 0.5) / (df[termo] + 0.5))
            s += idf * (f * (k1 + 1) / (f + k1 * (1 - b + b * dl / media))) * (1 + math.log(qf))
        pontos.append(s)
    return pontos


def previa_fontes(docs, n=1200):
    """Início de cada arquivo (usado no planejamento, quando as fontes são grandes demais)."""
    partes = []
    for d in docs:
        partes.append(
            f"=== {d['nome']} (arquivo grande, {len(d['texto'])} caracteres; só o início) ===\n"
            + d["texto"][:n]
        )
    return "\n\n".join(partes)


def montar_fontes(docs, consulta, limite):
    """Se as fontes cabem no limite, devolve tudo. Senão, escolhe os trechos mais relevantes
    para a consulta. Retorna (texto, linhas_de_resumo)."""
    total = sum(len(d["texto"]) for d in docs)
    if total <= limite:
        return "\n\n".join(f"=== {d['nome']} ===\n{d['texto']}" for d in docs), []

    todos = []  # (índice do arquivo, posição no arquivo, trecho)
    for i, d in enumerate(docs):
        for j, t in enumerate(_dividir(d["texto"])):
            todos.append((i, j, t))
    pontos = _pontuar([t for _, _, t in todos], consulta)
    escolhidos, usado = set(), 0

    def tentar(k):
        nonlocal usado
        tam = len(todos[k][2]["texto"])
        if k in escolhidos or usado + tam > limite:
            return
        escolhidos.add(k)
        usado += tam

    por_doc = {i: [k for k, (di, _, _) in enumerate(todos) if di == i] for i in range(len(docs))}

    if max(pontos, default=0) <= 0:
        # nenhuma palavra da consulta apareceu: pega trechos espaçados em cada arquivo
        for i, d in enumerate(docs):
            idx = por_doc[i]
            if not idx:
                continue
            quantos = max(1, int(limite * len(d["texto"]) / total // TAM_TRECHO))
            for m in range(quantos):
                tentar(idx[int(m * len(idx) / quantos)])
    else:
        for i in range(len(docs)):  # garante os 2 melhores trechos de cada arquivo
            for k in sorted(por_doc[i], key=lambda k: -pontos[k])[:2]:
                if pontos[k] > 0:
                    tentar(k)
        for k in sorted(range(len(todos)), key=lambda k: -pontos[k]):  # completa pelo ranking geral
            if pontos[k] <= 0:
                break
            tentar(k)
        for k in sorted(escolhidos, key=lambda k: -pontos[k]):  # contexto: trecho anterior e seguinte
            for viz in (k - 1, k + 1):
                if 0 <= viz < len(todos) and todos[viz][0] == todos[k][0]:
                    tentar(viz)
        for i in range(len(docs)):  # arquivo sem nada relevante: pelo menos o começo dele
            if por_doc[i] and not any(k in escolhidos for k in por_doc[i]):
                tentar(por_doc[i][0])

    partes, resumo = [], []
    for i, d in enumerate(docs):
        ks = sorted(k for k in escolhidos if todos[k][0] == i)
        if not ks:
            continue
        blocos, anterior = [], None
        for k in ks:
            _, j, t = todos[k]
            if (anterior is None and j != 0) or (anterior is not None and j != anterior + 1):
                blocos.append("[...]")
            texto = t["texto"]
            if t["pagina"] and not texto.startswith("[p. "):
                texto = f"[p. {t['pagina']}]\n{texto}"
            blocos.append(texto)
            anterior = j
        chars = sum(len(todos[k][2]["texto"]) for k in ks)
        n_total = len(por_doc[i])
        partes.append(
            f"=== {d['nome']} (trechos selecionados: {len(ks)} de {n_total}; "
            f"{chars} de {len(d['texto'])} caracteres) ===\n" + "\n".join(blocos)
        )
        resumo.append(f"{d['nome']}: {len(ks)} de {n_total} trechos ({chars} de {len(d['texto'])} caracteres)")
    return "\n\n".join(partes), resumo