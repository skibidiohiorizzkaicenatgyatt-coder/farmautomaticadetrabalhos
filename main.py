import os
import time
import threading
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import TypedDict, Literal

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from ferramentas import criar_docx
from leitor import ler_entrada, arquivar_entrada

# ---------- CONFIGURAÇÃO ----------
PALAVRAS = 1200  # tamanho máximo do documento. Sobe (ex: 3500) quando o formato estiver certo.

# Modelo bom, só pra escrever e corrigir (caro)
llm = ChatAnthropic(model="claude-sonnet-4-5", max_tokens=16000, timeout=900, max_retries=0)
# Modelo barato, pra planejar e revisar
llm_barato = ChatAnthropic(model="claude-haiku-4-5", max_tokens=4000, timeout=120, max_retries=0)


# ---------- AVISOS DE PROGRESSO ----------
@contextmanager
def etapa(nome):
    """Mostra quando a etapa começa, avisa a cada 10s que ainda roda e mostra o tempo."""
    inicio = time.time()
    parar = threading.Event()

    def batimento():
        while not parar.wait(10):
            print(f"   ... {nome} ainda em andamento ({int(time.time() - inicio)}s)", flush=True)

    print(f">> {nome}...", flush=True)
    threading.Thread(target=batimento, daemon=True).start()
    try:
        yield
        print(f"   ok: {nome} ({time.time() - inicio:.1f}s)", flush=True)
    except Exception as e:
        print(f"   ERRO em {nome}: {type(e).__name__}: {e}", flush=True)
        raise
    finally:
        parar.set()


# ---------- MODELOS DE DADOS ----------
class Bloco(BaseModel):
    tipo: Literal[
        "titulo1", "titulo2", "titulo3",
        "paragrafo", "topico", "numerado", "recuado",
        "referencia", "quebra_pagina",
    ]
    texto: str = ""

class Documento(BaseModel):
    titulo: str
    subtitulo: str = ""
    incluir_capa: bool
    incluir_sumario: bool
    incluir_titulo: bool  # título avulso no topo (só vale quando não há capa)
    blocos: list[Bloco] = []


INSTRUCAO_BLOCOS = (
    "Você escreve o documento como uma LISTA ORDENADA DE BLOCOS. Tipos disponíveis:\n"
    "- titulo1, titulo2, titulo3: títulos de nível 1, 2 e 3\n"
    "- paragrafo: parágrafo de texto corrido\n"
    "- topico: item de lista com marcador\n"
    "- numerado: item de lista numerada (a numeração é automática, não escreva o número)\n"
    "- recuado: bloco recuado, fonte menor (ementa, citação longa)\n"
    "- referencia: uma referência bibliográfica (referências seguidas são ordenadas em ordem alfabética)\n"
    "- quebra_pagina: começa uma nova página\n"
    "Dentro do texto pode usar **negrito** e *itálico*. "
    "Você só pode usar esses tipos: o que não existir (tabelas, imagens, notas de rodapé) "
    "escreva como parágrafo. O título do documento vai no campo 'titulo', não repita como bloco.\n\n"
    "ESTRUTURA: três fontes podem definir como o documento deve ser: "
    "(1) as instruções adicionais, (2) o pedido e (3) os modelos. "
    "Primeiro decida: alguma dessas fontes define ou indica a estrutura ou a forma do documento? "
    "Isso inclui: existir qualquer arquivo em MODELOS; as instruções falarem de estrutura ou formato; "
    "o pedido descrever a estrutura ou pedir um tipo de documento que tem formato próprio e conhecido "
    "(projeto de lei, ata, ofício, carta, currículo, contrato, etc.). "
    "Tipos genéricos (relatório, resumo, trabalho, texto) NÃO definem estrutura.\n\n"
    "SE ALGUMA FONTE DEFINE A ESTRUTURA: IGNORE POR COMPLETO a estrutura padrão. Siga só o que as fontes indicam; "
    "em caso de conflito prevalece: instruções, depois pedido, depois modelos. "
    "Use incluir_capa=false, incluir_sumario=false e incluir_titulo=false, a menos que a própria fonte "
    "peça ou o modelo tenha capa, sumário ou título avulso. "
    "O cabeçalho do documento (por exemplo 'PROJETO DE LEI Nº ...') deve ser escrito como bloco, "
    "conforme o formato indicado.\n\n"
    "SOMENTE SE NENHUMA FONTE DISSER NADA SOBRE A ESTRUTURA, use a PADRÃO: incluir_capa=true, "
    "incluir_sumario=true, incluir_titulo=true, e os blocos: introdução, seções com subtítulos, "
    "conclusão e referências (com quebra_pagina antes do título Referências). "
    "Se o pedido pedir explicitamente 'sem capa' ou 'sem sumário', desligue só isso."
)


# ---------- ESTADO ----------
class Estado(TypedDict):
    pedido: str
    instrucoes: str   # texto de entrada/instrucoes (seguir à risca)
    modelos: str      # texto de entrada/modelos (imitar estrutura e tom)
    fontes: str       # texto de entrada/fontes (usar como dados)
    plano: str
    trabalho: Documento
    arquivos: list[str]
    problemas: str
    aprovado: bool
    pasta: str        # pasta do trabalho dentro de saida/


def contexto(s: Estado) -> str:
    """Monta o bloco com instruções, modelos e fontes pra colocar nos prompts."""
    partes = []
    if s.get("instrucoes"):
        partes.append("INSTRUÇÕES ADICIONAIS (siga à risca):\n" + s["instrucoes"])
    if s.get("modelos"):
        partes.append(
            "MODELOS (imite a estrutura, a organização e o tom "
            "destes documentos; NÃO copie o conteúdo deles):\n" + s["modelos"]
        )
    if s.get("fontes"):
        partes.append(
            "MATERIAL DE BASE (use como fonte principal de fatos e dados; "
            "não invente informações que contradigam este material; cite os "
            "arquivos usados nas referências):\n" + s["fontes"]
        )
    return "\n\n".join(partes)


# ---------- NÓS ----------
def ler_fontes(s: Estado):
    with etapa("Lendo arquivos da pasta 'entrada'"):
        instrucoes, modelos, fontes = ler_entrada("entrada")
    return {"instrucoes": instrucoes, "modelos": modelos, "fontes": fontes}

def planejar(s: Estado):
    with etapa("Planejando"):
        r = llm_barato.invoke(
            "Quebre este pedido em um plano: lista de seções e o que cada uma "
            f"deve cobrir.\n\nPedido: {s['pedido']}\n\n{contexto(s)}"
        )
    return {"plano": r.content}

def escrever(s: Estado):
    with etapa("Escrevendo o documento"):
        escritor = llm.with_structured_output(Documento)
        t = escritor.invoke(
            f"{INSTRUCAO_BLOCOS}\n\n"
            f"Pedido original: {s['pedido']}\n\n"
            f"{contexto(s)}\n\n"
            f"Plano:\n{s['plano']}\n\n"
            "Escreva o documento completo. "
            f"Seja completo, porém conciso: no máximo cerca de {PALAVRAS} palavras no total. "
            "Para parágrafos, um bloco por parágrafo."
        )
    return {"trabalho": t}

def revisar(s: Estado):
    with etapa("Revisando"):
        r = llm_barato.invoke(
            "Revise este documento quanto a estrutura, clareza, coerência e se "
            "cumpre o pedido e as instruções. Responda apenas APROVADO se estiver "
            "bom, ou liste os problemas principais (no máximo 5).\n\n"
            f"Pedido: {s['pedido']}\n\n"
            f"{('INSTRUÇÕES ADICIONAIS:' + chr(10) + s['instrucoes'] + chr(10) + chr(10)) if s.get('instrucoes') else ''}"
            f"Documento:\n{s['trabalho'].model_dump_json()}"
        )
    ok = r.content.strip().upper().startswith("APROVADO")
    print(f"   resultado: {'APROVADO' if ok else 'reprovado'}", flush=True)
    return {"aprovado": ok, "problemas": r.content}

def corrigir(s: Estado):
    """Uma única correção. Se falhar, segue com a versão anterior (não perde o trabalho)."""
    try:
        with etapa("Corrigindo"):
            escritor = llm.with_structured_output(Documento)
            t = escritor.invoke(
                f"{INSTRUCAO_BLOCOS}\n\n"
                f"Pedido original: {s['pedido']}\n\n"
                f"{contexto(s)}\n\n"
                f"Documento atual:\n{s['trabalho'].model_dump_json()}\n\n"
                f"Problemas encontrados:\n{s['problemas']}\n\n"
                "Devolva o documento completo, corrigido, sem aumentar o tamanho "
                f"(máximo cerca de {PALAVRAS} palavras)."
            )
        return {"trabalho": t}
    except Exception:
        print("   Correção falhou. Seguindo com a versão anterior.", flush=True)
        return {}

def gerar_arquivos(s: Estado):
    with etapa("Gerando o DOCX"):
        pasta = Path("saida") / datetime.now().strftime("trabalho_%Y-%m-%d_%H-%M-%S")
        caminho = criar_docx(s["trabalho"].model_dump(), str(pasta / "resultado" / "trabalho.docx"))
    return {"arquivos": [caminho], "pasta": str(pasta)}

def arquivar(s: Estado):
    with etapa("Arquivando os arquivos de entrada"):
        arquivar_entrada("entrada", s["pasta"])
    return {}

def decidir(s: Estado):
    return "gerar_arquivos" if s["aprovado"] else "corrigir"


# ---------- GRAFO ----------
# ler_fontes -> planejar -> escrever -> revisar -> (aprovado? DOCX : corrigir 1x -> DOCX) -> arquivar
g = StateGraph(Estado)
g.add_node("ler_fontes", ler_fontes)
g.add_node("planejar", planejar)
g.add_node("escrever", escrever)
g.add_node("revisar", revisar)
g.add_node("corrigir", corrigir)
g.add_node("gerar_arquivos", gerar_arquivos)
g.add_node("arquivar", arquivar)

g.set_entry_point("ler_fontes")
g.add_edge("ler_fontes", "planejar")
g.add_edge("planejar", "escrever")
g.add_edge("escrever", "revisar")
g.add_conditional_edges("revisar", decidir, {"gerar_arquivos": "gerar_arquivos", "corrigir": "corrigir"})
g.add_edge("corrigir", "gerar_arquivos")
g.add_edge("gerar_arquivos", "arquivar")
g.add_edge("arquivar", END)

app = g.compile()


# ---------- EXECUÇÃO ----------
if __name__ == "__main__":
    print("Chave carregada:", bool(os.getenv("ANTHROPIC_API_KEY")), flush=True)
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ERRO: ANTHROPIC_API_KEY não encontrada. Confere o arquivo .env")

    pedido = input("\nO que você precisa? ")

    config = {}
    try:
        from langchain_core.callbacks import UsageMetadataCallbackHandler
        contador = UsageMetadataCallbackHandler()
        config = {"callbacks": [contador]}
    except ImportError:
        contador = None

    inicio = time.time()
    resultado = app.invoke({"pedido": pedido}, config=config)
    print(f"\nPronto em {time.time() - inicio:.0f}s!")
    print("Pasta do trabalho:", resultado["pasta"])
    print("Arquivos:", resultado["arquivos"])

    if contador and contador.usage_metadata:
        print("\nTokens usados (entrada/saída) por modelo:")
        for modelo, u in contador.usage_metadata.items():
            print(f"  {modelo}: {u.get('input_tokens')} / {u.get('output_tokens')}")