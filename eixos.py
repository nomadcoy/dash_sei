from __future__ import annotations

"""Eixos de trabalho das diretorias — classificação honesta a partir do texto real
que o SEI entrega no Controle de Processos.

Cada processo recebe um eixo a partir de `tipo_processo`, `especificacao` e
`assunto`. As regras são declarativas (palavras-chave), na ordem de prioridade:
os temas específicos (terminais, transferência de linhas, pedágio...) vencem os
genéricos. Onde nenhuma regra casa, cai em 'Outros e temas diversos' — nunca
inventamos um eixo.

Este módulo é usado pelo ETL (para gravar o eixo no banco) e pelo motor de
análise do dashboard (para leitura). Sem IA externa: é pandas + somatórios.
"""

# Regras específicas (testadas primeiro). Cada eixo tem uma lista de termos —
# a presença de qualquer um deles no texto classifica o processo.
EIXOS_ESPECIFICOS: list[tuple[str, list[str]]] = [
    (
        "Transferência e anuência de linhas",
        ["transferênc", "transferenc", "delegação", "delegacao", "anuência",
         "anuencia", "cessão", "cessao", "renúncia", "renuncia", "substituição de",
         "substituicao de"],
    ),
    (
        "Terminais e plataformas",
        ["terminal", "estação", "estacao", "garagem", "embarque",
         "desembarque", "plataforma de embarque"],
    ),
    (
        "Infraestrutura viária e pedágio",
        ["pedágio", "pedagio", "br-040", "br-381", "br 040", "br 381", "rodovia",
         "pavimenta", "sinaliza", "mau estado", "via cristais", "infraestrutura",
         "acesso à", "retorno na", "viaduto", "ponte"],
    ),
    (
        "Alteração contratual e operacional (QCO/QRF)",
        ["alteração contratual", "alteracao contratual", " altera", "qco", "qrf",
         "reajuste", "aditivo", "quadro de roteiros", "quadro de horários",
         "quadro de horarios", "remanej", "quebra técnica", "quebra tecnica",
         "suspensão", "suspensao", "implantação de linha", "implantacao de linha",
         "extinção de linha", "extincao de linha"],
    ),
    (
        "Acessibilidade, bilhetagem e gratuidade",
        ["bilhetagem", "bilhetag", "carrís", "carris", "cartão de", "cartao de",
         "passe livre", "gratuit", "acessibilidade", "meia passagem", "isenção",
         "isencao", "cadeirante", "passe especial"],
    ),
    (
        "Fiscalização, penalidades e ouvidoria",
        ["fiscaliz", "vistoria", "auto de infração", "auto de infracao",
         "penalidade", "multa", "interdição", "interdicao", "processo administrativo",
         "reclamação", "reclamacao", "ouvidoria", "denúncia", "denuncia",
         "apuração", "apuracao", "comissão para apuração", "comissao para apuracao"],
    ),
    (
        "Demandas políticas e institucionais",
        ["deputado", "vereador", "câmara municipal", "camara municipal",
         "câmara de vereadores", "camara de vereadores", "prefeitura", "promotoria",
         "ministério público", "ministerio publico", "mpe ", "associação de usuários",
         "associacao de usuarios", "dpmg", "idero", "der/", "age/", "comissão",
         "comissao", "ofício", "oficio", "requerimento", "indicação", "indicacao"],
    ),
    (
        "Veículos e frota",
        ["veículo", "veiculo", "frota", "placa", "chassi", "veículos especiais",
         "veiculos especiais", "renovação de frota", "renovacao de frota",
         "ônibus", "onibus", "micro-ônibus", "micro-onibus"],
    ),
    (
        "Contratos, convênios e licitações",
        ["contrato", "convênio", "convenio", "licitação", "licitacao", "pregão",
         "pregao", "mgs", "terceiriza", "comodato", "credenciamento"],
    ),
    (
        "Empresa e outorga",
        ["viação", "viacao", "delegatária", "delegataria", "outorga",
         "representatividade", "empresa", "linha empresarial", "atividade empresarial"],
    ),
]

# Eixos por categoria do SEI (usados quando nenhuma regra específica casou).
EIXOS_POR_TIPO: list[tuple[str, str]] = [
    ("metropolitano", "Metropolitano (alterações e rotas)"),
    ("linhas de transporte", "Linhas e itinerários"),
    ("linhas", "Linhas e itinerários"),
    ("veículos", "Veículos e frota"),
    ("pedidos, oferecimentos", "Pedidos e informações"),
    ("informações diversas", "Pedidos e informações"),
    ("assinatura", "Assinatura e citações"),
    ("documental", "Documentos e certidões"),
]

EIXO_OUTROS = "Outros e temas diversos"


def normalizar(texto: object | None) -> str:
    if texto is None:
        return ""
    t = str(texto)
    return " ".join(t.split()).lower()


def classificar(
    tipo_processo: object | None,
    especificacao: object | None,
    assunto: object | None,
) -> str:
    """Atribui um eixo ao processo. Retorna sempre uma rótulo não-vazio."""
    alvo = " | ".join(
        n for n in (normalizar(x) for x in (tipo_processo, especificacao, assunto)) if n
    )
    if not alvo:
        return EIXO_OUTROS

    for eixo, termos in EIXOS_ESPECIFICOS:
        for termo in termos:
            if termo.lower() in alvo:
                return eixo

    tipo_norm = normalizar(tipo_processo)
    for chave, eixo in EIXOS_POR_TIPO:
        if chave in tipo_norm:
            return eixo
    return EIXO_OUTROS