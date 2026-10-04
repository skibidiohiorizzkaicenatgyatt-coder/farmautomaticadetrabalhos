# Agente de Documentos

Agente local em Python que recebe um pedido em linguagem natural (e, opcionalmente, arquivos de apoio) e entrega **um documento Word (.docx)** pronto, já formatado.

Ele roda no seu computador e usa a API da Anthropic para planejar, escrever, revisar e corrigir o texto.

> **Resumo rápido:** você coloca arquivos em `entrada/`, roda `python main.py`, descreve o que quer, e pega o resultado em `saida/`.

---

## Índice

1. [O que ele faz (e o que não faz)](#o-que-ele-faz-e-o-que-não-faz)
2. [Estrutura do projeto](#estrutura-do-projeto)
3. [Instalação](#instalação)
4. [Como usar](#como-usar)
5. [Entradas](#entradas)
6. [Saídas](#saídas)
7. [Como o agente trabalha](#como-o-agente-trabalha)
8. [Tom de escrita](#tom-de-escrita)
9. [Detalhes importantes](#detalhes-importantes)
10. [Custo](#custo)
11. [Personalização](#personalização)
12. [Problemas comuns](#problemas-comuns)

---

## O que ele faz (e o que não faz)

**Faz:**
- Gera **um único arquivo `.docx`** por trabalho
- Lê arquivos de apoio (PDF, DOCX, XLSX, PPTX, TXT, MD, CSV) e usa como instrução, modelo ou fonte de dados
- Formata o documento automaticamente (fonte, margens, parágrafos, títulos, número de página)
- Revisa o próprio texto e faz uma correção se encontrar problemas
- Guarda cada trabalho numa pasta própria, com tudo que foi usado

**Não faz (ainda):**
- Não gera PDF, PPTX, Excel nem imagens. **A única saída é DOCX.**
- Não pesquisa na web
- Não lê imagens nem PDFs escaneados
- Não monta tabelas, imagens, notas de rodapé nem cabeçalhos. A estrutura é livre, mas limitada às peças descritas em [Estrutura do documento](#estrutura-do-documento)

---

## Estrutura do projeto

```
meu_projeto/
├── main.py            # o agente (fluxo com LangGraph)
├── ferramentas.py     # cria o DOCX e define o visual
├── leitor.py          # lê os arquivos de entrada e arquiva os trabalhos
├── .env               # sua chave da API (não compartilhe)
├── venv/              # ambiente virtual
│
├── entrada/           # você coloca os arquivos aqui
│   ├── instrucoes/
│   ├── modelos/
│   └── fontes/
│
└── saida/             # os resultados aparecem aqui
    └── trabalho_AAAA-MM-DD_HH-MM-SS/
        ├── instrucoes/
        ├── modelos/
        ├── fontes/
        └── resultado/
            └── trabalho.docx
```

As pastas `entrada/` e `saida/` (e as subpastas de `entrada/`) são criadas automaticamente se não existirem.

---

## Instalação

### 1. Ambiente virtual

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

No Linux/Mac: `source venv/bin/activate`

Se o PowerShell reclamar de permissão, rode uma vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 2. Dependências

```powershell
pip install langgraph langchain-anthropic python-docx pydantic python-dotenv pypdf openpyxl python-pptx
```

### 3. Chave da API

1. Crie uma chave em **console.anthropic.com** (é preciso ter crédito na conta)
2. Crie um arquivo chamado `.env` na pasta do projeto, com este conteúdo:

```
ANTHROPIC_API_KEY=sk-ant-sua-chave-aqui
```

O nome da variável precisa ser exatamente `ANTHROPIC_API_KEY`, sem aspas e sem espaços em volta do `=`. Confira que o arquivo não ficou como `.env.txt`.

**Nunca** coloque a chave direto no código nem envie o `.env` para o GitHub.

---

## Como usar

1. **Ative o ambiente virtual** (`venv\Scripts\Activate.ps1`)
2. **Coloque os arquivos de apoio** nas subpastas de `entrada/` (opcional, veja [Entradas](#entradas))
3. **Feche os arquivos no Word/Excel**, para o Windows não bloquear a movimentação no final
4. **Rode:**
   ```powershell
   python main.py
   ```
5. **Descreva o que você quer** quando aparecer `O que você precisa?`. Escreva tudo em uma linha só, porque o Enter envia o pedido.
6. **Aguarde.** O terminal mostra cada etapa e o tempo. Normalmente leva de 2 a 5 minutos.
7. **Pegue o resultado** em `saida/trabalho_.../resultado/trabalho.docx`
8. **Abra no Word** e atualize o sumário (veja [Detalhes importantes](#detalhes-importantes))

### Exemplos de pedido

```
um resumo de 1 página sobre tolerância religiosa, sem capa e sem sumário
```

```
relatório sobre energia nuclear para o 3º ano, com introdução, conclusão e referências
```

```
projeto de lei sobre discurso de ódio na internet, tom formal, sem capa
```

Você pode controlar a estrutura pelo próprio pedido: "sem capa", "sem sumário", "sem introdução", "sem conclusão", "sem referências".

---

## Entradas

Tudo é opcional. Sem nenhum arquivo, o agente trabalha só com o seu pedido.

O **papel** de cada arquivo é definido pela **pasta** onde ele está:

| Pasta | Papel | Como a IA usa |
|---|---|---|
| `entrada/instrucoes/` | Regras | Segue à risca (tom, tamanho, formato, o que incluir ou evitar) |
| `entrada/modelos/` | Exemplos | Imita a estrutura, a organização e o tom. **Não copia o conteúdo e não muda o visual.** |
| `entrada/fontes/` | Dados | Usa como fonte principal de fatos e cita nas referências |

### Formatos suportados

| Formato | O que é lido |
|---|---|
| `.pdf` | Texto de todas as páginas |
| `.docx` | Parágrafos e tabelas |
| `.xlsx` | Todas as planilhas, linha por linha (valores, não fórmulas) |
| `.pptx` | Texto de cada slide e notas do apresentador |
| `.txt`, `.md`, `.csv` | Texto puro |

Arquivos de outros formatos são **ignorados**, com um aviso no terminal.

### Limites de tamanho

- Cada arquivo é cortado em **25.000 caracteres**
- `modelos/` + `fontes/` somam no máximo **60.000 caracteres** (cerca de 15 mil tokens)
- Quando o limite estoura, o agente corta primeiro as **fontes**, depois os modelos. **As instruções nunca são cortadas.**
- O terminal mostra uma estimativa de tokens depois de ler os arquivos

### Regras e avisos

- **Arquivos soltos direto em `entrada/`** (fora das subpastas) são ignorados, e o terminal avisa. Coloque-os em uma das três subpastas.
- **PDF escaneado** (foto de página) não tem texto para extrair. O terminal avisa e o arquivo é ignorado.
- **Imagens dentro de PDFs, DOCX e gráficos** são ignoradas. Só o texto entra.
- **Arquivos temporários do Office** (que começam com `~$`) são ignorados.
- Se tiver arquivos de outro trabalho na `entrada/`, a IA vai usar todos. Deixe só o que vale para o trabalho atual.

---

## Saídas

Cada execução cria **uma pasta nova** em `saida/`, com a data e a hora do computador no nome:

```
saida/trabalho_2026-10-03_17-40-12/
├── instrucoes/    ← o que você colocou em entrada/instrucoes
├── modelos/       ← o que você colocou em entrada/modelos
├── fontes/        ← o que você colocou em entrada/fontes
└── resultado/
    └── trabalho.docx
```

Ou seja, cada trabalho vira um pacote completo: o que foi pedido, com quais materiais, e o que saiu.

**Depois que o trabalho termina com sucesso**, os arquivos de `entrada/` são **movidos** para a pasta do trabalho, e `entrada/` volta com as três subpastas vazias, pronta para o próximo.

Pontos importantes:
- Trabalhos anteriores **nunca são alterados**. Nada em `saida/` é apagado ou sobrescrito.
- Se o programa der erro no meio, os arquivos **continuam em `entrada/`**, e você pode rodar de novo sem refazer nada.
- Se algum arquivo estiver aberto no Word, o Windows pode impedir a movimentação. Nesse caso o programa copia, avisa no terminal e segue. Feche os arquivos antes de rodar.
- O nome do arquivo final é sempre `trabalho.docx`. A pasta é que identifica cada trabalho.

---

## Como o agente trabalha

```
ler arquivos → planejar → escrever → revisar ─┬─ aprovado ──────────────→ gerar DOCX → arquivar
                                              └─ reprovado → corrigir ──→ gerar DOCX → arquivar
```

| Etapa | O que acontece | Modelo |
|---|---|---|
| Ler arquivos | Extrai o texto de `entrada/` | (sem IA) |
| Planejar | Divide o pedido em seções | Haiku (barato) |
| Escrever | Escreve o documento completo como uma lista de blocos (títulos, parágrafos, tópicos...) | Sonnet |
| Revisar | Confere estrutura, clareza e se cumpre o pedido e as instruções. Responde "aprovado" ou lista problemas. | Haiku |
| Corrigir | Reescreve o documento corrigindo os problemas. **Só acontece uma vez.** | Sonnet |
| Gerar DOCX | Monta o arquivo com o visual padrão | (sem IA) |
| Arquivar | Move os arquivos de entrada para a pasta do trabalho | (sem IA) |

Detalhes:
- Depois da correção, o agente **não revisa de novo**. Segue direto para gerar o arquivo.
- Se a correção falhar (timeout, por exemplo), o DOCX sai com a **versão anterior**, e você não perde o trabalho.
- O Sonnet escreve porque a qualidade do texto importa mais. O Haiku cuida do que é mais simples, para gastar menos.

---

## Tom de escrita

**Não existe um tom definido no código.** Nenhum prompt manda a IA escrever de um jeito específico. Sem nenhuma instrução sua, ela escreve em **português neutro e formal**, que é o comportamento natural do modelo.

Você controla o tom de três formas:

1. **No pedido:** "em tom simples, para aluno do 3º ano"
2. **Em `entrada/instrucoes/`:** um arquivo `.txt` com regras, por exemplo "tom jurídico formal, frases curtas, sem jargão". É o jeito mais confiável, porque a IA segue as instruções à risca.
3. **Em `entrada/modelos/`:** um documento de exemplo. A IA imita o estilo dele.

Em caso de conflito, a ordem de prioridade que o agente recebe é: **instruções > pedido > modelos**. É uma orientação dada à IA, não uma garantia absoluta, então evite conflitos entre eles.

---

## Detalhes importantes

### Só gera DOCX
Cada trabalho produz **um único arquivo Word**. Não há PDF, slides, planilhas nem imagens. Se você precisar de PDF, abra o DOCX no Word e use "Salvar como PDF".

### Estrutura do documento

**Quem define a estrutura é você.** A estrutura pode vir de três lugares:

1. `entrada/instrucoes/`
2. o pedido
3. `entrada/modelos/`

**Regra:** se **qualquer um** dos três define ou indica a estrutura, a estrutura padrão é **ignorada por completo**. Só quando **nenhum** dos três diz nada sobre estrutura é que vale o padrão. Em caso de conflito entre eles, prevalece: instruções > pedido > modelos.

O que conta como "definir a estrutura":
- Existir **qualquer arquivo** em `entrada/modelos/`
- As instruções falarem de estrutura ou formato
- O pedido descrever a estrutura, ou pedir um tipo de documento com formato próprio e conhecido (projeto de lei, ata, ofício, carta, currículo, contrato...)

Tipos genéricos (relatório, resumo, trabalho, texto) **não** definem estrutura, então nesses casos vale o padrão.

**Estrutura padrão** (só quando nada define): capa, sumário, introdução, seções com subtítulos, conclusão e referências (em página própria, no final).

Quando a estrutura é definida por você, capa, sumário e título avulso ficam **desligados**, a menos que você ou o modelo peçam. O cabeçalho do documento (por exemplo "PROJETO DE LEI Nº ...") é escrito como parte do conteúdo, no formato que você indicou.

Isso é uma orientação dada à IA, não uma trava no código, então confira o resultado. Se ela errar, diga no pedido: "sem capa, sem sumário e sem título".

O código monta o arquivo a partir de uma lista de **blocos**. Estas são as únicas peças disponíveis:

| Bloco | Como aparece no Word |
|---|---|
| `titulo1`, `titulo2`, `titulo3` | Títulos de nível 1, 2 e 3 (entram no sumário os níveis 1 e 2) |
| `paragrafo` | Texto corrido, justificado, com recuo na primeira linha |
| `topico` | Item de lista com marcador |
| `numerado` | Item de lista numerada (a numeração é automática e recomeça em 1 depois de qualquer outro bloco) |
| `recuado` | Bloco recuado à esquerda, fonte menor, espaçamento simples (ementa, citação longa) |
| `referencia` | Referência bibliográfica, alinhada à esquerda. Referências seguidas ficam em ordem alfabética. |
| `quebra_pagina` | Começa uma nova página |

Dentro do texto, a IA pode usar `**negrito**` e `*itálico*`.

Capa, sumário e título avulso são ligados ou desligados pela IA conforme a regra acima. Você também pode pedir direto: "sem capa", "sem sumário". Na estrutura padrão, o título aparece na capa (ou no topo da primeira página, se não houver capa).

**Exemplo:** se você colocar em `modelos/` um projeto de lei real e pedir um parecido sobre outro tema, a IA organiza em ementa (`recuado`), capítulos (`titulo1`) e artigos (`paragrafo` com "**Art. 1º**" em negrito). O que o código não sabe montar (tabelas, imagens, notas de rodapé, cabeçalhos) sai como parágrafo de texto simples.

### Visual fixo
O visual vem do `ferramentas.py` e é o mesmo para qualquer trabalho, **independente do modelo**:

- Fonte Times New Roman, tamanho 12
- Parágrafos justificados, recuo de 1,25 cm na primeira linha, espaçamento 1,5
- Títulos pretos em negrito
- Margens: 3 cm (superior e esquerda), 2 cm (inferior e direita)
- Número de página no rodapé
- Referências alinhadas à esquerda, espaçamento simples

Resumindo: **o modelo e o seu pedido decidem o que escrever e como organizar. O código decide como aquilo aparece no Word.** Mesmo que você coloque um DOCX bonito da escola em `modelos/`, o resultado sai com o visual padrão acima.

### Sumário vazio
O sumário é um campo do Word que só preenche quando atualizado. Ao abrir o DOCX, clique com o botão direito na área do sumário e escolha **Atualizar campo** (ou aperte `F9`), depois **Atualizar o índice inteiro**.

### Referências podem ser inventadas
O agente **não pesquisa na web**. Se você não fornecer fontes em `entrada/fontes/`, a IA pode criar referências que parecem reais, mas não existem. **Confira todas as referências antes de usar o documento.** Com fontes fornecidas, ela cita os arquivos que usou.

### Revisão automática não é garantia
A revisão é feita por uma IA mais simples. Ela ajuda a pegar problemas de estrutura e clareza, mas não substitui a sua leitura. Confira fatos, números e citações.

### Revise antes de usar
O conteúdo gerado deve ser sempre revisado por você, principalmente se for um trabalho escolar, acadêmico ou um documento formal. Você é responsável pelo que entrega.

### Pedido em uma linha
O terminal lê uma linha por vez, então escreva o pedido inteiro antes de apertar Enter. Se quiser dar instruções longas, coloque-as em um arquivo em `entrada/instrucoes/`.

---

## Custo

A API da Anthropic é paga por uso. O custo de cada trabalho depende de:

- **Tamanho do texto:** o texto final é a parte mais cara (tokens de saída do Sonnet)
- **Arquivos de entrada:** o texto deles é enviado em várias chamadas (planejar, escrever e, se houver, corrigir)
- **Se houve correção:** ela reescreve o documento inteiro, o que dobra o custo da escrita

O programa já inclui proteções:

- Sem tentativas automáticas repetidas (`max_retries=0`)
- Tamanho máximo do texto controlado pela constante `PALAVRAS` (padrão 1200)
- Só uma correção por trabalho
- Limite de caracteres nos arquivos de entrada
- Contador de tokens por modelo no final da execução

**Recomendações:**
- Configure um **limite de gasto** em console.anthropic.com (Billing)
- Mantenha a **recarga automática desligada**
- Teste primeiro com pedidos pequenos e poucos arquivos
- Consulte os preços atuais na página oficial da Anthropic

---

## Personalização

| O que mudar | Onde |
|---|---|
| Tamanho máximo do documento | `PALAVRAS` no topo do `main.py` |
| Modelos de IA | `llm` e `llm_barato` no `main.py` |
| Visual do DOCX (fonte, margens, espaçamento) | `ferramentas.py` |
| Limites de leitura dos arquivos | `LIMITE_POR_ARQUIVO` e `LIMITE_TOTAL` no `leitor.py` |
| Formatos de arquivo aceitos | dicionário `LEITORES` no `leitor.py` |
| Número de correções | funções `decidir` e `corrigir` no `main.py` |
| Tipos de bloco e estrutura padrão | classe `Bloco` e texto `INSTRUCAO_BLOCOS` no `main.py`, e `criar_docx` no `ferramentas.py` |

---

## Problemas comuns

**`Chave carregada: False` ou erro de autenticação**
O `.env` não está sendo lido. Confira o nome `ANTHROPIC_API_KEY`, se o arquivo está na pasta do `main.py` e se não é `.env.txt`.

**O terminal parece travado**
Durante a escrita, o texto vem inteiro no final e pode levar 1 a 3 minutos. A cada 10 segundos aparece uma mensagem "ainda em andamento". Se passar de uns 10 minutos sem nada, pare com `Ctrl + C`. No Windows, clicar com o mouse dentro do terminal pausa o programa; aperte `Esc` ou `Enter` para continuar.

**`max_tokens stop reason` ou erro de validação (Pydantic)**
O texto passou do limite e foi cortado. Reduza o valor de `PALAVRAS` ou aumente o `max_tokens` do `llm` no `main.py`.

**Timeout na escrita ou na correção**
O texto é muito longo. Reduza o `PALAVRAS`. Se a correção falhar, o DOCX sai com a versão anterior.

**`PermissionError` ao salvar**
Um arquivo está aberto no Word. Feche e rode de novo.

**Um arquivo foi ignorado**
Leia o aviso no terminal. Os motivos comuns: formato não suportado, PDF escaneado, arquivo solto fora das subpastas, ou limite de tamanho atingido.

**Os arquivos de entrada não foram movidos**
Algum arquivo provavelmente estava aberto. O terminal avisa quando isso acontece. Feche os arquivos e mova a pasta manualmente.

**Erro de crédito ou limite**
Verifique o saldo em console.anthropic.com. Sem crédito, as chamadas falham e o programa para sozinho.

---

## Ideias futuras

- Perfis prontos de formato (relatório ABNT, projeto de lei) com estrutura e visual próprios
- Tabelas, notas de rodapé e imagens nos blocos
- Visual herdado de um DOCX de modelo
- Pesquisa na web para referências reais
- Saídas em PDF e PPTX
- Leitura de imagens e PDFs escaneados
- Resumo ou busca de trechos para arquivos muito grandes
- Interface gráfica em vez do terminal