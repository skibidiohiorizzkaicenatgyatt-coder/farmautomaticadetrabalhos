import base64
import hashlib
import io
import re
from pathlib import Path

# ---------- CONFIGURAÇÃO ----------
OCR_ATIVO = True                  # False = não lê imagens nem páginas escaneadas
MODELO_VISAO = "claude-haiku-4-5"
MAX_PAGINAS_OCR = 40              # páginas escaneadas lidas por PDF
PAGINAS_POR_LOTE = 10             # páginas enviadas por chamada
LIMITE_IMAGEM = 4_500_000         # bytes; acima disso a imagem é reduzida
PASTA_CACHE = Path(".cache_ocr")  # leituras ficam salvas: não paga duas vezes pelo mesmo arquivo

TIPOS_IMAGEM = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}
USO = {"chamadas": 0, "entrada": 0, "saida": 0}
_MARCA = re.compile(r"(?m)^\[p\. (\d+)\]\s*$")

TRANSCRICAO = (
    "Transcreva fielmente todo o texto visível, na ordem de leitura e no idioma original. "
    "Tabelas: uma linha por linha da tabela, com as colunas separadas por ' | '. "
    "Gráficos, fotos e diagramas: descreva em uma ou duas frases entre colchetes, "
    "por exemplo [Imagem: ...]. Não comente, não resuma e não traduza. "
    "Se não houver nada legível, responda apenas: [sem texto legível]"
)


def _cliente():
    import anthropic
    return anthropic.Anthropic()


def _chave(dados: bytes, extra: str) -> str:
    return hashlib.sha1(dados + (MODELO_VISAO + extra).encode()).hexdigest()


def _cache_ler(chave):
    arq = PASTA_CACHE / f"{chave}.txt"
    return arq.read_text(encoding="utf-8") if arq.exists() else None


def _cache_gravar(chave, texto):
    PASTA_CACHE.mkdir(exist_ok=True)
    (PASTA_CACHE / f"{chave}.txt").write_text(texto, encoding="utf-8")


def _pedir(bloco, instrucao):
    resp = _cliente().messages.create(
        model=MODELO_VISAO, max_tokens=16000,
        messages=[{"role": "user", "content": [bloco, {"type": "text", "text": instrucao}]}],
    )
    uso = getattr(resp, "usage", None)
    USO["chamadas"] += 1
    USO["entrada"] += getattr(uso, "input_tokens", 0) or 0
    USO["saida"] += getattr(uso, "output_tokens", 0) or 0
    if getattr(resp, "stop_reason", "") == "max_tokens":
        print("   AVISO: a transcrição foi cortada por tamanho (diminua PAGINAS_POR_LOTE).", flush=True)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def _reduzir(dados):
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("imagem grande demais e a biblioteca Pillow não está instalada (pip install pillow)")
    img = Image.open(io.BytesIO(dados)).convert("RGB")
    lado = 2000
    while True:
        copia = img.copy()
        copia.thumbnail((lado, lado))
        buf = io.BytesIO()
        copia.save(buf, format="JPEG", quality=85)
        if buf.tell() <= LIMITE_IMAGEM or lado <= 500:
            return buf.getvalue(), "image/jpeg"
        lado = int(lado * 0.7)


def transcrever_imagem(caminho):
    """Lê uma imagem com o Claude: transcreve o texto e descreve o que não for texto."""
    caminho = Path(caminho)
    media = TIPOS_IMAGEM[caminho.suffix.lower()]
    dados = caminho.read_bytes()
    if len(dados) > LIMITE_IMAGEM:
        dados, media = _reduzir(dados)
    chave = _chave(dados, "img")
    texto = _cache_ler(chave)
    if texto is None:
        bloco = {"type": "image", "source": {"type": "base64", "media_type": media,
                                              "data": base64.b64encode(dados).decode()}}
        texto = _pedir(bloco, TRANSCRICAO + " Se for uma foto ou ilustração sem texto, descreva o "
                       "conteúdo com os detalhes relevantes para escrever um documento.")
        if texto:
            _cache_gravar(chave, texto)
    return texto


def _separar_paginas(texto, lote):
    partes = _MARCA.split(texto)  # [antes, n1, texto1, n2, texto2, ...]
    if len(partes) == 1:
        return {lote[0]: texto.strip()}
    resultado = {}
    for k in range(1, len(partes), 2):
        n = int(partes[k])
        if n in lote:
            resultado[n] = partes[k + 1].strip()
    return resultado


def transcrever_paginas_pdf(caminho, paginas):
    """Lê páginas escaneadas de um PDF (números começando em 1). Retorna {página: texto}."""
    from pypdf import PdfReader, PdfWriter
    caminho = Path(caminho)
    original = caminho.read_bytes()
    leitor = PdfReader(str(caminho))
    resultado = {}
    for ini in range(0, len(paginas), PAGINAS_POR_LOTE):
        lote = paginas[ini:ini + PAGINAS_POR_LOTE]
        chave = _chave(original, "pdf" + ",".join(map(str, lote)))
        texto = _cache_ler(chave)
        if texto is None:
            w = PdfWriter()
            for n in lote:
                w.add_page(leitor.pages[n - 1])
            buf = io.BytesIO()
            w.write(buf)
            bloco = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                    "data": base64.b64encode(buf.getvalue()).decode()}}
            texto = _pedir(
                bloco,
                f"Este PDF contém {len(lote)} página(s), que correspondem às páginas "
                f"{', '.join(map(str, lote))} do documento original, nesta ordem. "
                "Comece cada página com uma linha exatamente assim: [p. N], usando o número original. "
                + TRANSCRICAO,
            )
            if texto:
                _cache_gravar(chave, texto)
        resultado.update(_separar_paginas(texto, lote))
    return resultado