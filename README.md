# Painel de Controle de Processos — Gestão à Vista

**Da extração bruta do SEI-MG a um produto de dados para a gestão pública.**

Este repositório não é apenas um dashboard. É um projeto de **ciência de dados
de ponta a ponta** construído sobre um sistema que **não oferece API**. Ele
automatiza a aquisição de dados, estrutura um armazém analítico, aplica
engenharia de atributos, scoring e estatística para transformar registros
operacionais de processos em **indicadores, narrativas e relatórios** acionáveis.

O domínio é o transporte coletivo de Minas Gerais: a **STIM** (Superintendência
de Transporte Coletivo Intermunicipal e Metropolitano) e as diretorias
**DGTI**, **DGTM** e **DRTC**, da SEINFRA/SEI-MG.

---

## Visão geral

O SEI-MG (Sistema Eletrônico de Informações) é onde tramitam os processos. Ele
não expõe API pública e mostra os dados apenas em telas dinâmicas. Este projeto:

1. **Coleta** os dados dessas telas de forma automatizada e resiliente.
2. **Modela** tudo em um banco analítico local (SQLite).
3. **Deriva atributos** que o SEI não entrega prontos (criticidade, eixos de
   trabalho, estágios, categorias de documento).
4. **Analisa** volumes, séries temporais, estoque, envelhecimento, fluxo e tempo.
5. **Comunica** por um painel interativo, narrativas automáticas em PT-BR e
   relatórios em PDF.

Princípio que atravessa o projeto inteiro: **nada de métrica inventada**. Quando
o dado não existe, o sistema diz explicitamente que não é computável, em vez de
estimar ou preencher.

---

## Por que isso é um projeto de ciência de dados

O projeto percorre o ciclo completo de um pipeline analítico — da fonte crua à
decisão — e concentra o esforço justamente onde a ciência de dados agrega valor:
transformar dados sujos e incompletos em informação confiável.

### 1. Aquisição de dados (data acquisition)

- Automação de navegador com **Playwright** sobre um sistema legado, dinâmico e
  sem API.
- Sessão autenticada, troca de unidade, paginação e coleta do **Controle de
  Processos**, do **Painel de Controle** e das **Estatísticas da Unidade**.
- Tratamento de falhas: retomada, lock de concorrência (uma extração por vez),
  logs estruturados e registro de cada execução em banco.

### 2. Engenharia de dados (data engineering)

- **ETL** com normalização de datas, listas de marcadores, valores e textos.
- Modelo relacional pensado para análise: séries mensais, retratos por extração e
  histórico de snapshots (`historico_processos`).
- Idempotência e integridade: extrações versionadas por `extracao_id`; o painel
  lê sempre a última extração válida por unidade.

### 3. Engenharia de atributos (feature engineering)

Features derivadas que não existem na origem:

- **Índice de criticidade (0–100)** — score composto por prioridade, marcador
  crítico, imobilidade, prazo vencido, idade relativa ao tipo e reprocessamento.
- **Eixos de trabalho** — classificação temática dos processos por regras
  declarativas (palavras-chave sobre tipo, especificação e assunto).
- **Estágios de fluxo** — reconstrução de etapas a partir dos marcadores do SEI.
- **Categorias de documento** — agrupamento dos tipos de documento em macro
  categorias (comunicações oficiais, notas técnicas, despachos, termos, etc.).
- **Indicadores temporais** — variação, média móvel de 3 meses, sazonalidade,
  distribuição por faixas de permanência.

### 4. Modelagem heurística (sem caixa-preta)

- Scoring de risco explicável (pesos versionados em YAML).
- Classificação por regras interpretáveis, não "caixa-preta" — cada decisão é
  auditável e reproduzível.
- **Sem API externa e sem LLM**: é pandas + estatística. A "inteligência" é
  transparente por design.

### 5. Análise estatística

- Séries temporais de produção (documentos e processos) por unidade.
- Comparativos entre diretorias e rankings.
- Mediana e média de tempo de tramitação (com tratamento de outliers).
- Balanço de fluxo: abertos, em tramitação, fechados e taxa de conclusão.
- Detecção de valores suspeitos (ex.: tempos ≥ 300 dias, provável truncamento na
  origem) que são **excluídos explicitamente** dos resumos.

### 6. Geração automática de narrativa (NLG)

- Textos analíticos em português gerados **a partir dos números**: tendência do
  período, concentração de volume, mix de categorias, eficiência e perfil de cada
  diretoria.
- Sem IA generativa: templates determinísticos preenchidos por estatísticas —
  reproduzíveis e auditáveis.

### 7. Comunicação e entrega

- Painel interativo em **Streamlit** com múltiplas visões.
- **Relatórios em PDF** gerados a partir dos mesmos dados (boletim e relatório de
  transição de governo).
- Deploy do painel via **Tailscale Funnel** (HTTPS público, sem abrir porta).

---

## Arquitetura

```
             ┌──────────────────────────────┐
             │            SEI-MG            │
             │ (Controle de Processos,      │
             │  Painel, Estatísticas)       │
             └──────────────┬───────────────┘
                            │  Playwright (scraping autenticado)
                            ▼
             ┌──────────────────────────────┐
             │        extractor/            │
             │  session · scraping · etl    │
             └──────────────┬───────────────┘
                            │  ETL + engenharia de atributos
                            ▼
             ┌──────────────────────────────┐
             │         data/sei.db          │
             │  extracoes · processos ·     │
             │  painel_unidades ·           │
             │  historico_processos ·       │
             │  estatisticas                │
             └──────────────┬───────────────┘
                            │  pandas + heurísticas + estatística
                            ▼
             ┌──────────────────────────────┐
             │          dashboard/          │
             │  queries · analise · eixos   │
             │  Streamlit  →  PDF           │
             └──────────────┬───────────────┘
                            │
                            ▼
                   Painel web / PDF / Funnel
```

---

## Estrutura do repositório

```
.
├── extractor/            # Aquisição de dados no SEI (Playwright) + ETL
│   ├── session.py        # Sessão autenticada e login
│   ├── scraping.py       # Coleta de controle, painel e estatísticas
│   ├── etl_sei.py        # Normalização e gravação
│   └── main.py           # CLI da extração
├── dashboard/            # Produto de dados (Streamlit)
│   ├── app.py            # Navegação e autenticação
│   ├── pages/            # Uma página por visão
│   ├── queries.py        # Camada de consulta (SQLite → pandas)
│   ├── analise.py        # Motor de análise e narrativa
│   ├── gestao_dados.py   # Indicadores de fluxo/tempo
│   ├── boletim_*.py      # Boletim de produtividade (+ PDF)
│   ├── relatorio_*.py    # Relatório de transição de governo (+ PDF)
│   ├── periodo.py        # Widgets de período e séries
│   ├── style.py          # Tema e CSS institucional
│   └── serve.py / sw.js  # Launcher e service worker (resiliência)
├── config/               # Configuração declarativa (YAML)
│   ├── unidades.yaml     # Unidades, cores e descrições
│   ├── criterios.yaml    # Pesos do índice de criticidade
│   ├── prazos.yaml       # Prazos por tipo de processo
│   └── stim_map.yaml     # Fluxos de processo (anexos)
├── synthetic/            # Gerador de base sintética (desenvolvimento)
├── scripts/              # Subida do painel, túnel, firewall (Windows)
├── etl.py, eixos.py      # Normalização e classificação temática
├── db.py                 # Schema, migrações e conexão
├── cfg.py                # Configuração e credenciais (.env)
├── requirements.txt
└── .streamlit/config.toml
```

---

## Principais análises e "modelos"

| Componente | O que faz | Onde |
|---|---|---|
| Índice de criticidade | Score 0–100 explicável por pesos | `config/criterios.yaml`, `dashboard/queries.py` |
| Eixos de trabalho | Classificação temática por regras | `eixos.py` |
| Estágios de fluxo | Etapas a partir dos marcadores | `dashboard/analise.py` |
| Categorias de documento | Agrupamento de 68 tipos em macro categorias | `dashboard/boletim_dados.py` |
| Séries de produção | Tendência, média móvel, variação | `dashboard/boletim_analise.py` |
| Balanço de fluxo | Abertos / tramitação / fechados + conclusão | `dashboard/gestao_dados.py` |
| Tempo de tramitação | Mediana/média com remoção de outliers | `dashboard/gestao_dados.py` |
| Narrativa automática | Textos PT-BR gerados dos números | `dashboard/analise.py`, `boletim_analise.py` |

---

## O painel

Páginas disponíveis:

- **Visão Geral** — cartões clicáveis (que abrem a lista de processos), série de
  produção e top processos críticos.
- **Painel de Controle** — espelha os cartões do SEI por diretoria.
- **Diretorias** — comparativo entre DGTI, DGTM, DRTC e STIM.
- **Indicadores de Gestão** — balanço de fluxo, processos gerados/mês, tempo de
  tramitação e volume por tipo, com filtro por período.
- **Processos Críticos** — ranking pelo índice de criticidade.
- **Panorama das Diretorias** — leitura do conjunto: estoque, envelhecimento,
  eixos, gargalos e fluxo entre unidades.
- **Boletim de Produtividade** — documentos e processos por mês, categorias de
  documento, documentos externos, eficiência e síntese automática (com PDF).
- **Transição de Governo** — relatório gerencial para troca de gestão (com PDF).
- **Dados & Extração** — saúde da extração, auditoria e disparo manual.

---

## Stack

- **Python 3.11+**
- **Streamlit** — interface
- **Playwright** — automação do SEI
- **pandas** — ETL e análise
- **Plotly / Matplotlib** — visualizações (tela e PDF)
- **SQLite** — armazém analítico local
- **PyYAML** — configuração declarativa
- **python-dotenv** — credenciais por ambiente

---

## Como executar

### 1. Instalar dependências

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configurar credenciais

Crie um arquivo `.env` na raiz (ele está no `.gitignore` e **não deve ser
versionado**):

```ini
SEI_LOGIN=seu_usuario
SEI_SENHA=sua_senha
SEI_URL_LOGIN=https://www.sei.mg.gov.br/...
SEI_HEADLESS=true

# Login do painel
DASH_USUARIO=algum_usuario
DASH_SENHA=alguma_senha
```

### 3. Extrair dados do SEI

```bash
# Controle de Processos + Painel de Controle
python -m extractor.main

# Somente o Painel (mais rápido)
python -m extractor.main --somente-painel

# Incluir Estatísticas da Unidade (documentos, tempos médios etc.)
python -m extractor.main --estatisticas --estatisticas-periodo 01/01/2024 31/12/2025

# Filtrar unidades
python -m extractor.main --unidades DGTI DGTM DRTC STIM
```

### 4. Subir o painel

```bash
streamlit run dashboard/app.py
# ou, no Windows, com o launcher de resiliência:
scripts\subir_dash.ps1
```

Acesse `http://localhost:8599` (porta definida em `.streamlit/config.toml`).

### 5. Base sintética (para desenvolvimento, sem acessar o SEI)

```bash
python synthetic/gerar_sinteticos.py
```

---

## Configuração (YAML)

- `config/unidades.yaml` — siglas, nomes, cores e descrições das diretorias.
- `config/criterios.yaml` — pesos e marcadores do índice de criticidade.
- `config/prazos.yaml` — prazos por tipo de processo (usados na imobilidade).
- `config/stim_map.yaml` — fluxos de processo (entrada, etapas, saída).

Mudar um peso ou um limiar é editar o YAML — sem tocar em código.

---

## Modelo de dados

| Tabela | Conteúdo |
|---|---|
| `extracoes` | Cada execução da extração (fonte, status, totais). |
| `processos` | Retrato do Controle de Processos por unidade (com features). |
| `painel_unidades` | Cartões e tabelas do Painel de Controle (JSON por extração). |
| `historico_processos` | Snapshots por extração (evolução do estoque). |
| `estatisticas` | Estatísticas da Unidade: documentos gerados/externos, processos gerados/abertos/fechados/em tramitação, tempos médios. |

---

## Deploy (Tailscale Funnel)

O painel roda localmente e é publicado via **Tailscale Funnel** (HTTPS público,
sem abrir portas no roteador):

```bash
tailscale funnel --bg 8599
```

O comando publica `http://127.0.0.1:8599` em uma URL `https://<node>.ts.net`
válida. Para desligar:

```bash
tailscale funnel --https=443 off
```

---

## Princípios do projeto

- **Honestidade de dados:** nenhuma métrica é estimada. Onde falta dado, isso é
  declarado explicitamente na interface e nos relatórios.
- **Transparência:** scoring e classificações são regras interpretáveis, não
  caixas-pretas; pesos e limiares são versionados em YAML.
- **Reprodutibilidade:** extrações versionadas, snapshots históricos e narrativas
  determinísticas.
- **Privacidade:** credenciais ficam em `.env` (fora do versionamento); o painel
  exige autenticação; o banco e os logs não são versionados.

---

## Limitações conhecidas

- O SEI **não expõe API**; a coleta depende de automação de tela e pode ser
  afetada por mudanças de layout.
- Algumas métricas de ciclo de vida (tempo até conclusão por tipo, histórico de
  tramitação detalhado) dependem de dados que o SEI não entrega de forma
  consistente e são tratadas como **não computáveis** quando for o caso.
- A consulta de Estatísticas da Unidade é limitada a **1 ano por vez**; o painel
  fatia o período anual e recompõe as séries.
- Valores de tempo de tramitação ≥ 300 dias são tratados como suspeitos
  (truncamento na origem) e excluídos dos resumos.

---

## Autoria

Desenvolvido na **STIM / SEINFRA-MG** por **Francisco Soares** (Cientista de
Dados) e **Cristina Santos** (PMO).

---

## Licença

Defina a licença adequada ao uso institucional antes de publicar (ex.: uso
interno SEINFRA-MG). Credenciais, banco de dados e logs **não** são versionados.
