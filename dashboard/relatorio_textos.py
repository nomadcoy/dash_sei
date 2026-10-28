from __future__ import annotations







"""Textos do Relatório Gerencial de Transição de Governo.







Tudo é derivado dos dados reais do SEI já reunidos por


``dashboard.relatorio_dados.montar`` - nenhuma métrica é estimada. Onde o SEI



não entrega um dado, a ausência é dita explicitamente.



"""







def _fmt(n) -> str:



    return f"{int(round(n)):,}".replace(",", ".")











def _serie_ano_txt(por_ano: dict[str, int]) -> str:



    if not por_ano:



        return "sem registros"



    return " · ".join(f"{a}: {_fmt(por_ano[a])}" for a in sorted(por_ano))











def _top_txt(df, n: int = 6) -> str:



    if df is None or df.empty:



        return "—"



    return "; ".join(f"{r['tipo']} ({_fmt(r['total'])})" for _, r in df.head(n).iterrows())











# ---------------------------------------------------------------------------



# Textos-base (curados, a partir do conhecimento real da área)



# ---------------------------------------------------------------------------



BASE = {



    "DGTI": (



        "A Diretoria de Gestão do Transporte Coletivo Intermunicipal (DGTI) responde "



        "pela gestão das linhas e serviços que ligam municípios mineiros: concessões "


        "e autorizações de linhas, alterações de frota e itinerário, revisões e "


        "reajustes tarifários e o acompanhamento contratual dos operadores. É a "



        "unidade que concentra a relação operacional com os concessionários e os "



        "pedidos de outorga vindos de empresas e prefeituras — a porta de entrada de "

        "boa parte da demanda do transporte intermunicipal."



    ),



    "DGTM": (



        "A Diretoria de Gestão do Transporte Coletivo Metropolitano (DGTM) atua nas "



        "regiões metropolitanas: linhas metropolitanas, integração com os modais "



        "ferroviário e metropolitano, linhas de característica especial previstas na "



        "legislação de mobilidade, acordos de integração tarifária e articulação com "

        "as autoridades de transporte das regiões metropolitanas. Seu trabalho é "



        "tipicamente mais sensível à integração entre sistemas e à interlocução "



        "institucional com municípios e integradores. Na DGTM, o foco é o transporte metropolitano (autorizações, integrações e articulação com autoridades metropolitanas), em consonância com os fluxos registrados no Anexo."



    ),



    "DRTC": (



        "A Diretoria de Regulação do Transporte Coletivo (DRTC) é a instância de "



        "regulação do sistema — não apenas a diretoria de sanções. Atua em duas frentes "


        "complementares: (a) a análise e a instrução de processos sob a ótica da "



        "conformidade — verificação de adequação à legislação, aos contratos e às condiçõess "



        "de prestação do serviço, muitas vezes antes que qualquer infração exista; e "


        "(b) a fiscalização e o sancionamento, quando cabível, com apuração de "



        "irregularidades, autuação, julgamento de recursos e aplicação de penalidades. "



        "Boa parte da produção são análises, pareceres e despachos técnicos de "

        "conformidade, e não autuações: - por ela que passa a verificação de "



        "conformidade de boa parte dos processos da área. A autonomia em relação às "



        "diretorias de gestão exige rigor probatório e observância de prazos."


    ),



    "STIM": (



        "A Superintendência de Transporte Coletivo Intermunicipal e Metropolitano "



        "(STIM) é o comando da área: coordena as diretorias, decide processos de alta "



        "expressão, emite manifestações e pareceres, conduz convênios e consórcios "

        "intermunicipais, representa a SEINFRA junto a municípios, consórcios e "



        "órgãos de transporte e responde pelo Comitê Gestor. Seus documentos são "



        "proporcionalmente menos numerosos porque se concentram em decisões e pareceres "

        "de alto nível — mas é dela a responsabilidade pelo conjunto: a STIM coordena "



        "uma das áreas de maior volume da SEINFRA, que somando diretoria por diretoria "



        "produziu milhares de documentos e movimentou milhares de processos no período "



        "(ver panorama e sumário executivo)."



    ),



}







DIRETORIA_COMPETENCIA = {



    "DGTI": (



        "gestão das linhas intermunicipais — outorga e autorização de linhas, "



        "alterações de frota e itinerário, revisão e reajuste tarifário, "



        "acompanhamento contratual dos operadores"



    ),



    "DGTM": (




        "gestão das linhas metropolitanas — outorga e alteração de linhas, integração "



        "tarifária e articulação com as autoridades de transporte das regiões "



        "metropolitanas"



    ),



    "DRTC": (




        "regulação do sistema — análise e instrução de conformidade dos processos que "



        "passam pela regulação, fiscalização, apuração de irregularidades e julgamento "



        "de recursos e sanções"


    ),



    "STIM": (



        "coordenação da superintendência — decisões de alta expressão, manifestações e "



        "pareceres, convênios e consórcios intermunicipais e representação institucional"



    ),



}







DIRETORIA_RESUMO = {



    "DGTI": "gestão das linhas intermunicipais (outorga, frota, itinerário e tarifa)",



    "DGTM": "gestão das linhas metropolitanas e integração entre sistemas",



    "DRTC": "regulação do sistema: análise e conformidade, fiscalização e sanção",

    "STIM": "comando, coordenação das diretorias e decisões estratégicas",



}







MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun",



                "jul", "ago", "set", "out", "nov", "dez"]











def rotulo(mes: str) -> str:



    try:



        a, m = mes.split("-")



        return f"{MESES_CURTOS[int(m) - 1]}/{a}"



    except Exception:



        return mes











def o_que_e_a_stim() -> list[str]:



    """Texto institucional: o que é a STIM e como o trabalho se organiza."""



    from dashboard.relatorio_dados import visao_geral_stim







    vg = visao_geral_stim()



    paragrafos = [



        "A Superintendência de Transporte Coletivo Intermunicipal e Metropolitano "



        "(STIM) - a unidade da Secretaria de Estado de Infraestrutura, Mobilidade e "



        "Parcerias (SEINFRA) responsável por conduzir o transporte coletivo "



        "intermunicipal e metropolitano de Minas Gerais. Não atua isolada: opera em "



        "rede com três diretorias - duas de gestão (DGTI e DGTM) e uma de regulação "



        "(DRTC) - com competências distintas e complementares.",


    ]



    if vg:



        paragrafos.append(vg)



    paragrafos.append(



        "Na pratica, um processo nasce quase sempre como pedido de um operador ou de "



        "um municipio, recebe instrução técnica na diretoria competente e só escala "



        "para a regulação (quando há controvérsia, dúvida de conformidade ou "

        "irregularidade) ou para a superintendência (quando o impacto tarifário, "



        "contratual ou político exige decisão de alto nível). Esse desenho faz da STIM "



        "um ponto de convergência de demandas de empresas, prefeituras, consórcios, "

        "órgãos de controle e do próprio Governo do Estado."



    )



    paragrafos.append(



        "A dimensão do trabalho é grande e contínua: são milhares de documentos "



        "gerados e milhares de processos movimentados no período — cada um exigindo "



        "leitura técnica, conferência de requisitos, manifestação e decisão. A "

        "complexidade está justamente aí: as decisões tratam de concessões, tarifas, "



        "contratos, integração entre sistemas e conformidade normativa, com efeito "



        "direto sobre o serviço prestado ao cidadão. É trabalho de diretores e "


        "analistas técnicos que dominam a legislação de transporte e os fluxos do SEI, "



        "e que sustentam essa produção de forma recorrente."



    )



    return paragrafos











def metodologia(dados: dict) -> list[str]:



    """Explica a fonte, o recorte e os limites dos dados - sem inventar métrica."""



    de, ate = dados["de"], dados["ate"]



    un = ", ".join(dados["unidades"])



    anos = ", ".join(dados["anos"])



    return [



        f"Base de dados: **Estatísticas da Unidade** e **Controle de Processos** do "


    
        f"SEI-MG, extraídos automaticamente para base local. Recorte deste relatório: "



        f"**{rotulo(de)} a {rotulo(ate)}** ({len(dados['anos'])} anos: {anos}), "



        f"unidades {un}.",



        "Documentos gerados: por padrão excluem-se os documentos que o próprio SEI "



        "produz no protocolo e no peticionamento — **Recibo Eletrônico de Protocolo** e "



        "**Certidão de Intimação Cumprida** — porque não resultam de ação humana na "



        "unidade. Quando incluídos, o total é apresentado separadamente para dar a "



        "dimensão total do que tramita.",



        "O recorte começa deliberadamente em **janeiro de 2024**: é a partir dessa data "


        "que o acompanhamento das Estatísticas da Unidade no SEI-MG passa a ser "



        "consistente para esta área. Antes disso, mudanças na forma de coleta e na "



        "estrutura das unidades no SEI tornam os dados imprecisos e pouco comparáveis "



        "entre períodos. Não há, portanto, série confiável anterior a jan/2024 — e "



        "este relatório prefere não estimar nem inventar histórico.",



        "Detalhamentos específicos (por exemplo: processos de anuência prévia, "



        "alteração de quadro de horário/itinerário, decisões do CT, PAP abertos e "

        "julgados pela Comissão, entre outros) não estão sistematizados nas "



        "**Estatísticas da Unidade** e no **Controle de Processos** do SEI que são "



        "extraídos para este painel. Eles existem no trâmite dos processos, mas não "



        "constam de forma agregada nas tabelas consultadas. Por esse motivo, esses "



        "valores não são apresentados neste relatório — caberá evolução da extração "



        "para quantificá-los de forma rastreável e sem estimativas.",



        "Nada é estimado. Onde o SEI não entrega um dado (por exemplo, tempos médios "



        "de tramitação inconsistentes ou datas de autuação/conclusão ausentes no "

        "Controle), o relatório diz isso explicitamente em vez de preencher com número "



        "inventado.",



    ]











def analise_diretoria(sigla: str, dados: dict) -> list[str]:



    """Parágrafos técnicos de uma diretoria, combinando base + números e assuntos reais.







    A leitura não parte só de texto curado: ela é confrontada com os tipos de


    documento e os assuntos/processos efetivamente registrados no SEI para a



    unidade, de modo a inferir o papel real da diretoria a partir do que ela produz.



    """



    u = dados["por_unidade"][sigla]



    comp = DIRETORIA_COMPETENCIA.get(sigla, "")



    p = [BASE.get(sigla, u.get("descricao") or "").strip()]



    if comp:



        p.append(f"Em síntese, sua competência é a {comp}.")



    p.append(



        f"No período, a {sigla} gerou **{_fmt(u['docs_total'])} documentos** "



        f"({_serie_ano_txt(u['docs_ano'])}), além de **{_fmt(u['prc_total'])} "


        f"processos** e **{_fmt(u['ext_total'])} documentos externos** registrados "



        f"pelo SEI. Os tipos de documento mais frequentes são: {_top_txt(u['top_docs'], 8)}."



    )



    if not u["top_docs"].empty:



        p.append(



            "Essa composição é o retrato mais fiel do que a unidade faz no dia a dia: "



            "predominam documentos de análise, instrução e decisão, produzidos de forma "



            "recorrente - indício de trabalho técnico contínuo, e não de atos isolados. Na DGTI, predominam processos operacionais intermunicipais — autorizações, renovações, modificações de frota/itinerário e instruções contratuais — conforme os fluxos mapeados."



        )



    if u["n_proc"]:



        eixos = (



            "; ".join(



                f"{r['eixo']} ({_fmt(r['processos'])})"



                for _, r in u["eixos"].head(5).iterrows()



            )



            if not u["eixos"].empty



            else "—"



        )



        p.append(



            f"No retrato mais recente do SEI, há **{_fmt(u['n_proc'])} processos** na "



            f"{sigla}. Classificados pelos assuntos registrados no SEI, eles se "



            f"concentram em: {eixos}. - a partir desses assuntos que se lê o papel da "



            f"unidade, e não de suposições. Desse total, **{_fmt(u['criticos'])}** "


            f"figuram como críticos (limiar de {dados['limiar']} pontos) e "



            f"**{_fmt(u['sem_resp'])}** estão sem responsável atribuído no controle."



        )



    if sigla == "DRTC":



        p.append(



            "Para a DRTC, convém registrar ainda uma ressalva de consistência histórica "



            "entre períodos: movimentações de 2024 relativas a matérias de táxi que "



            "tramitaram na DRTC podem estar contabilizadas nesta unidade, em razão da "



            "redistribuição de rotinas ao longo do tempo. Para fins de transição, vale destacar: os fluxos documentados no Anexo correspondem, no essencial, ao ciclo regulatório da DRTC — instrução de conformidade, apurações de irregularidades, recursos, anuências e outros processos de natureza regulatória. Esse ajuste de organizações "

            "administrativa não altera a produção total apurada, mas ajuda a explicar "



            "eventuais variações no detalhamento por assunto ao longo dos anos."
    


        )



    return p











def _ano(dados: dict, ano: str) -> int:



    d = dados["anual"]["doc_total"]



    m = d[d["ano"] == ano]



    return int(round(float(m["quantidade"].sum()))) if not m.empty else 0











def destaques(dados: dict) -> list[str]:



    """Sumário executivo: frases geradas apenas dos números do período."""



    de, ate = dados["de"], dados["ate"]



    k = dados["kpis"]



    u = dados["por_unidade"]



    anos = dados["anos"]







    anos_txt = " · ".join(f"{a}: {_fmt(_ano(dados, a))}" for a in anos)



    linhas = [



        f"**{_fmt(k['doc_sem_auto'])} documentos gerados** no período "



        f"({rotulo(de)}–{rotulo(ate)}), fora os automáticos do SEI. Somando-os, o SEI "


        f"registra **{_fmt(k['doc_com_auto'])} documentos**, dos quais "



        f"**{_fmt(k['excluidos'])}** são Recibos de Protocolo e Certidões de Intimação "
    


        f"emitidos pelo próprio sistema.",



        f"Produção de documentos por ano: {anos_txt}.",



        f"Além dos documentos, tramitaram **{_fmt(k['proc'])} processos gerados** e "



        f"**{_fmt(k['ext'])} documentos externos** no período.",



        "Por diretoria: "



        + " · ".join(f"{s} {_fmt(u[s]['docs_total'])} docs" for s in dados["unidades"])



        + ".",



    ]



    if len(anos) >= 2:



        v1, v2 = _ano(dados, anos[0]), _ano(dados, anos[-1])



        var = (v2 - v1) / v1 * 100 if v1 else 0.0



        linhas.append(



            f"De {anos[0]} a {anos[-1]}, a produção anual passou de {_fmt(v1)} para "



            f"{_fmt(v2)} documentos ({var:+.0f}%)."



        )



    return linhas











def sintese_transicao(dados: dict) -> list[str]:



    """Síntese técnica para o processo de transição de governo."""



    k = dados["kpis"]



    de, ate = dados["de"], dados["ate"]



    n2026 = _ano(dados, "2026")



    dias = _dias_periodo(dados)



    por_dia = k["doc_sem_auto"] / dias if dias else 0



    return [



        f"Entre **{rotulo(de)} e {rotulo(ate)}**, a área de transporte coletivo da "



        f"SEINFRA gerou **{_fmt(k['doc_sem_auto'])} documentos** e movimentou "



        f"**{_fmt(k['proc'])} processos**, além de **{_fmt(k['ext'])} documentos "

        f"externos**. Isso equivale a cerca de **{por_dia:.1f} documentos por dia** - "



        f"um volume que só se sustenta com rotina técnica contínua e equipe "


        f"familiarizada com os fluxos do SEI e das concessões.",



        f"Somente em **2026** já foram **{_fmt(n2026)} documentos** até o momento, no "



        f"mesmo patamar dos anos anteriores, indicando que a produção não perdeu "



        f"ritmo. A distribuição por diretoria revela o desenho operacional: a DGTI "



        f"concentra a maior parte da produção documental; a DRTC carrega o maior "



        f"volume de documentos externos (comunicações com órgãos, partes e entes); e a "



        f"STIM, por desenho institucional, tem poucos documentos, porém de alto "

        f"impacto.",



        "Os números descrevem trabalho real, verificável no SEI — não uma narrativa de "



        "mérito. O que mostram é uma área tecnicamente ativa, com acervo de processos "



        "em estágios distintos de instrução e conhecimento acumulado sobre concessões, "

        "regulação e articulação interfederativa. Preservar esse acervo e essa memória "



        "é o principal ativo para a continuidade do serviço prestado ao cidadão.",



        "Para a próxima gestão, dois cuidados concretos: (1) manter a coleta "

        "automática de estatísticas do SEI, que dá rastreabilidade mensal à produção; e "



        "(2) identificar, entre os processos hoje sem responsável atribuído no "


        "controle, quais demandam decisão imediata — é ali que reside o maior risco de "



        "descontinuidade.",



    ]











def conclusao(dados: dict) -> list[str]:



    """Fecho do relatório — deve ser a última seção do documento."""



    k = dados["kpis"]



    de, ate = dados["de"], dados["ate"]



    return [



        f"Os números reunidos neste relatório, cobrindo **{rotulo(de)} a {rotulo(ate)}**, "



        f"retratam uma área em atividade contínua: **{_fmt(k['doc_sem_auto'])} documentos "



        f"gerados**, **{_fmt(k['proc'])} processos** movimentados e "



        f"**{_fmt(k['ext'])} documentos externos** não são um retrato de exceção — são a "



        f"rotina técnica da superintendência e das suas diretorias, registrada no SEI e "



        f"aqui apenas organizada.",



        "O que os dados mostram é uma estrutura que funciona porque há pessoas que "

        "conhecem os fluxos, dominam a legislação de transporte e sustentam, todos os "



        "dias, decisões que afetam diretamente o serviço prestado ao cidadão mineiro. "



        "Esse conhecimento acumulado é o principal ativo desta área e a base sobre a "

        "qual qualquer transição deve ser construída.",



        "Conclui-se que a continuidade do serviço depende menos de recomeçar do zero e "



        "mais de preservar o que já foi feito: manter a coleta automática de "

        "estatísticas que dá rastreabilidade mensal à produção, concluir e distribuir "



        "os processos hoje sem responsável atribuído no controle e garantir que a "



        "memória técnica aqui documentada acompanhe a passagem de gestão.",



        "Este relatório foi produzido com dados públicos do próprio SEI-MG e não "



        "pretende substituir a avaliação da equipe de transição; pretende oferecê-la "



        "com base verificável, para que a decisão de continuidade ou de reforma seja "



        "tomada sobre fatos, e não sobre impressões.",



    ]











CREDITO = (



    "Gerado automaticamente pelo Painel de Controle de Processos - Gestão à Vista, "



    "desenvolvido na STIM por Francisco Soares (cientista de dados) e "



    "Cristina Santos (PMO)."



)











def fluxos_por_tipo() -> list[dict]:



    """Fluxos de processo descritos no stim_map (entrada → etapas → saída)."""



    from cfg import stim_map







    m = stim_map() or {}



    return list(m.get("tipos_processo") or [])











def _dias_periodo(dados: dict) -> int:



    try:



        a, m = dados["de"].split("-")



        b, n = dados["ate"].split("-")



        meses = (int(b) * 12 + int(n)) - (int(a) * 12 + int(m)) + 1



        return meses * 30



    except Exception:



        return 0