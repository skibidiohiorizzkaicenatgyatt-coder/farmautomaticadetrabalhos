import shutil
from pathlib import Path

LIMITE_POR_ARQUIVO = 25000   # caracteres por arquivo
LIMITE_TOTAL = 60000         # caracteres de modelos + fontes (~15 mil tokens)
PAPEIS = ["instrucoes", "modelos", "fontes"]


def _ler_pdf(caminho):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages)

def _ler_docx(caminho):
    from docx import Document
    d = Document(caminho)
    partes = [p.text for p in d.paragraphs if p.text.strip()]
    for tabela in d.tables:
        for linha in tabela.rows:
            partes.append(" | ".join(c.text.strip() for c in linha.cells))
    return "\n".join(partes)

def _ler_xlsx(caminho):
    from openpyxl import load_workbook
    wb = load_workbook(caminho, data_only=True, read_only=True)
    partes = []
    for ws in wb.worksheets:
        partes.append(f"[Planilha: {ws.title}]")
        for linha in ws.iter_rows(values_only=True):
            if any(c is not None for c in linha):
                partes.append(" | ".join("" if c is None else str(c) for c in linha))
    return "\n".join(partes)

def _ler_pptx(caminho):
    from pptx import Presentation
    partes = []
    for i, slide in enumerate(Presentation(caminho).slides, 1):
        partes.append(f"[Slide {i}]")
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                partes.append(shape.text_frame.text.strip())
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            partes.append("Notas: " + slide.notes_slide.notes_text_frame.text.strip())
    return "\n".join(partes)

def _ler_texto(caminho):
    return Path(caminho).read_text(encoding="utf-8", errors="ignore")

LEITORES = {
    ".pdf": _ler_pdf, ".docx": _ler_docx, ".xlsx": _ler_xlsx, ".pptx": _ler_pptx,
    ".txt": _ler_texto, ".md": _ler_texto, ".csv": _ler_texto,
}


def ler_entrada(pasta="entrada"):
    """Lê entrada/instrucoes, entrada/modelos e entrada/fontes (cria se não existirem).
    Retorna (instrucoes, modelos, fontes), três textos."""
    raiz = Path(pasta)
    for papel in PAPEIS:
        (raiz / papel).mkdir(parents=True, exist_ok=True)

    soltos = [a.name for a in raiz.iterdir() if a.is_file()]
    if soltos:
        print(f"   AVISO: arquivos soltos em '{pasta}' são ignorados, coloque nas subpastas: {', '.join(soltos)}", flush=True)

    total, textos = 0, {}
    for papel in PAPEIS:  # instruções primeiro, fontes por último (são as primeiras a serem cortadas)
        blocos = []
        for arq in sorted((raiz / papel).iterdir()):
            if not arq.is_file() or arq.name.startswith("~$"):
                continue
            leitor = LEITORES.get(arq.suffix.lower())
            if not leitor:
                print(f"   (ignorado, formato não suportado: {papel}/{arq.name})", flush=True)
                continue
            try:
                texto = leitor(arq).strip()
            except Exception as e:
                print(f"   (não consegui ler {papel}/{arq.name}: {type(e).__name__})", flush=True)
                continue
            if not texto:
                print(f"   (sem texto extraível, talvez PDF escaneado: {papel}/{arq.name})", flush=True)
                continue
            if len(texto) > LIMITE_POR_ARQUIVO:
                texto = texto[:LIMITE_POR_ARQUIVO] + "\n[... arquivo cortado por tamanho ...]"
                print(f"   (cortado em {LIMITE_POR_ARQUIVO} caracteres: {papel}/{arq.name})", flush=True)
            if papel != "instrucoes":
                if total + len(texto) > LIMITE_TOTAL:
                    print(f"   (limite total atingido, ignorado: {papel}/{arq.name})", flush=True)
                    continue
                total += len(texto)
            blocos.append(f"=== {arq.name} ===\n{texto}")
            print(f"   lido: {papel}/{arq.name} ({len(texto)} caracteres)", flush=True)
        textos[papel] = "\n\n".join(blocos)

    print(f"   total aproximado (modelos + fontes): {total // 4} tokens de entrada por chamada", flush=True)
    return textos["instrucoes"], textos["modelos"], textos["fontes"]


def arquivar_entrada(pasta_entrada, destino):
    """Move instrucoes/, modelos/ e fontes/ pra dentro de 'destino' e recria as pastas vazias.
    Nunca derruba o programa: se não conseguir mover (ex: arquivo aberto no Word), copia."""
    raiz, destino = Path(pasta_entrada), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for papel in PAPEIS:
        origem = raiz / papel
        try:
            if origem.exists():
                shutil.move(str(origem), str(destino / papel))
        except Exception as e:
            print(f"   AVISO: não consegui mover '{papel}' ({type(e).__name__}). Copiando.", flush=True)
            try:
                shutil.copytree(origem, destino / papel, dirs_exist_ok=True)
                shutil.rmtree(origem, ignore_errors=True)
            except Exception:
                print(f"   AVISO: '{papel}' ficou na entrada. Feche os arquivos abertos e mova manualmente.", flush=True)
        (raiz / papel).mkdir(parents=True, exist_ok=True)