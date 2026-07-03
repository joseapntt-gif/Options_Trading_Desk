"""
app.py
VRE Options Pro — aplicativo principal.

Estrutura de abas:
  📊 Performance     — análise real das operações concretizadas (win rate,
                        expectância, concentração, ciclos de rolagem)
  💰 Venda de PUT     — scanner de mínimas + score técnico + gráfico TradingView
  🐻 Compra de PUT    — scanner de máximas (espelho) + score técnico
  🚀 Trava de Alta    — montagem inteligente com payoff, túnel e ponto de entrada
  🛡️ Risco            — limites de exposição e concentração em tempo real

Tudo o que foi discutido está aplicado:
  - normalização de preço segura (utils.py)
  - score técnico real conectado (score_engine.py)
  - delta real via Black-Scholes (options_math.py / scanner_options.py)
  - motor de risco com limites de concentração (risk_engine.py)
  - saída dinâmica por trailing (risk_engine.py)
  - análise de performance com expectância e ciclos de rolagem (performance_engine.py)
"""

import streamlit as st
import pandas as pd

from layout import render_header, render_footer
from styles import inject_styles, metric_card, badge, alert_box, exposure_bar_html
from charts import plot_payoff, tradingview_widget, plot_curva_capital, plot_concentracao_ativos, plot_distribuicao_resultados
from quant_engine import analisar_ponto_trava
from scanner_engine import escanear_ativos_mesa
from scanner_options import buscar_puts_venda
import cotahist_provider
from performance_engine import calcular_metricas_gerais, calcular_concentracao_por_ativo, analisar_ciclos_rolagem, curva_de_capital
from risk_engine import validar_nova_entrada, LIMITE_PCT_POR_ATIVO
import portfolio_engine
from utils import formatar_moeda, formatar_pct, ticker_base


st.set_page_config(
    page_title="VRE Options Pro",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="📈",
)

inject_styles()


# ---------------------------------------------------------------------------
# Carregamento de operações históricas (upload manual — evita depender só
# da planilha ao vivo para a aba de performance)
# ---------------------------------------------------------------------------

def carregar_operacoes():
    if "df_operacoes" in st.session_state:
        return st.session_state["df_operacoes"]
    return None


def normalizar_df_operacoes(df_raw):
    """Converte um CSV/TSV de operações no padrão usado nas colunas discutidas
    (CODIGO, DATA_VENDA, STATUS, LUCPREJ, VALOR_OP, DIAS) para tipos numéricos."""
    from utils import normalizar_valor

    df = df_raw.copy()
    df.columns = [str(c).upper().strip() for c in df.columns]

    mapa_possiveis = {
        "LUCPREJ": ["LUCPREJ", "LUC/PREJ", "LUC_PREJ"],
        "VALOR_OP": ["VALOR_OP", "VALOR OPERAÇÃO", "VALOR_OPERACAO"],
        "DIAS": ["DIAS2", "DIAS", "DIAS3"],
        "STATUS": ["STATUS"],
        "CODIGO": ["CODIGO", "CÓDIGO"],
        "DATA_VENDA": ["DATA_VENDA", "DATA VENDA"],
    }
    renomeacoes = {}
    for alvo, opcoes in mapa_possiveis.items():
        for op in opcoes:
            if op in df.columns and alvo not in df.columns:
                renomeacoes[op] = alvo
                break
    df.rename(columns=renomeacoes, inplace=True)

    for col in ["LUCPREJ", "VALOR_OP", "DIAS"]:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_valor)

    if "STATUS" in df.columns:
        df["STATUS"] = df["STATUS"].astype(str).str.strip()

    return df


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header()

col_status, col_refresh = st.columns([4, 1])
with col_status:
    if "_ultima_atualizacao" not in st.session_state:
        st.session_state["_ultima_atualizacao"] = None
    ts = st.session_state["_ultima_atualizacao"]
    st.caption(f"Última atualização: {ts.strftime('%d/%m/%Y %H:%M:%S') if ts else 'ainda não atualizado nesta sessão'} · Cache automático: 5 min (planilha) / conforme consulta (yfinance)")
with col_refresh:
    forcar_refresh = st.button("🔄 Atualizar agora", use_container_width=True)

if forcar_refresh:
    st.cache_data.clear()
    import datetime
    st.session_state["_ultima_atualizacao"] = datetime.datetime.now()
    st.session_state.pop("df_scan_cache", None)
    st.rerun()

tabs = st.tabs(["📊 Performance", "💰 Venda de PUT", "🐻 Compra de PUT", "🚀 Trava de Alta", "🛡️ Risco", "📁 Carteira"])


# ---------------------------------------------------------------------------
# ABA 1 — Performance
# ---------------------------------------------------------------------------

with tabs[0]:
    st.subheader("Análise de performance das operações")

    with st.expander("📁 Carregar operações (CSV/TSV exportado da planilha)", expanded=(carregar_operacoes() is None)):
        arquivo = st.file_uploader("Selecione o arquivo", type=["csv", "tsv", "txt"])
        if arquivo is not None:
            sep = "\t" if arquivo.name.endswith((".tsv", ".txt")) else ","
            df_raw = pd.read_csv(arquivo, sep=sep, dtype=str)
            df_norm = normalizar_df_operacoes(df_raw)
            st.session_state["df_operacoes"] = df_norm
            st.success(f"{len(df_norm)} operações carregadas.")

    df_ops = carregar_operacoes()

    if df_ops is None:
        st.info("Carregue o histórico de operações acima para ver a análise completa de performance.")
    else:
        metricas = calcular_metricas_gerais(df_ops)

        if metricas is None:
            st.warning("Não foi possível calcular métricas — verifique se a coluna de resultado (LUCPREJ) está presente e numérica.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(metric_card("Taxa de acerto", f"{metricas['win_rate_pct']:.1f}%",
                                         f"{metricas['total_operacoes']} operações"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Expectância por operação", formatar_moeda(metricas['expectancia_rs']),
                                         "acerto × ganho − erro × perda",
                                         "positivo" if metricas['expectancia_rs'] >= 0 else "negativo"), unsafe_allow_html=True)
            with c3:
                st.markdown(metric_card("Resultado total", formatar_moeda(metricas['lucro_total_rs']),
                                         f"{formatar_pct(metricas['retorno_pct'])} sobre capital alocado" if metricas['retorno_pct'] else None,
                                         "positivo" if metricas['lucro_total_rs'] >= 0 else "negativo"), unsafe_allow_html=True)
            with c4:
                st.markdown(metric_card("Drawdown máximo", formatar_moeda(metricas['max_drawdown_rs']),
                                         "maior recuo desde um pico", "negativo"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            c5, c6, c7 = st.columns(3)
            with c5:
                st.markdown(metric_card("Ganho médio (acertos)", formatar_moeda(metricas['ganho_medio_rs']), tipo="positivo"), unsafe_allow_html=True)
            with c6:
                st.markdown(metric_card("Perda média (erros)", formatar_moeda(metricas['perda_media_rs']), tipo="negativo"), unsafe_allow_html=True)
            with c7:
                st.markdown(metric_card("Tempo médio em aberto", f"{metricas['tempo_medio_dias']:.0f} dias" if metricas['tempo_medio_dias'] else "—"), unsafe_allow_html=True)

            st.markdown("---")

            col_esq, col_dir = st.columns([1.3, 1])

            with col_esq:
                st.markdown("##### Evolução do resultado acumulado")
                df_curva = curva_de_capital(df_ops)
                if not df_curva.empty and "DATA_VENDA" in df_curva.columns:
                    st.plotly_chart(plot_curva_capital(df_curva), use_container_width=True)
                else:
                    st.caption("Sem coluna de data para plotar a evolução.")

                st.markdown("##### Distribuição de resultados por operação")
                st.plotly_chart(plot_distribuicao_resultados(df_ops[df_ops["LUCPREJ"].notna()]), use_container_width=True)

            with col_dir:
                st.markdown("##### Concentração de capital por ativo")
                df_conc = calcular_concentracao_por_ativo(df_ops)
                if not df_conc.empty:
                    maior = df_conc.iloc[0]
                    if maior["PCT_CAPITAL"] > LIMITE_PCT_POR_ATIVO * 100:
                        st.markdown(alert_box(
                            f"{maior['ATIVO_BASE']} concentra {maior['PCT_CAPITAL']:.0f}% do capital alocado "
                            f"(limite recomendado: {LIMITE_PCT_POR_ATIVO*100:.0f}%). "
                            f"Resultado da estratégia está fortemente dependente deste ativo."
                        ), unsafe_allow_html=True)
                    st.plotly_chart(plot_concentracao_ativos(df_conc), use_container_width=True)
                    st.dataframe(
                        df_conc[["ATIVO_BASE", "N_OPERACOES", "CAPITAL_RS", "PCT_CAPITAL", "PCT_LUCRO_TOTAL"]],
                        use_container_width=True, hide_index=True,
                        column_config={
                            "ATIVO_BASE": "Ativo", "N_OPERACOES": "Nº ops",
                            "CAPITAL_RS": st.column_config.NumberColumn("Capital", format="R$ %.0f"),
                            "PCT_CAPITAL": st.column_config.NumberColumn("% capital", format="%.1f%%"),
                            "PCT_LUCRO_TOTAL": st.column_config.NumberColumn("% do lucro", format="%.1f%%"),
                        }
                    )

            st.markdown("---")
            st.markdown("##### Ciclos de rolagem — resultado real (não presumido)")
            rolagem = analisar_ciclos_rolagem(df_ops)
            if rolagem["n_rolagens"] == 0:
                st.caption("Nenhuma operação marcada como ROLAGEM no histórico carregado.")
            else:
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    st.markdown(metric_card("Rolagens no período", str(rolagem["n_rolagens"])), unsafe_allow_html=True)
                with rc2:
                    st.markdown(metric_card("Resultado total dos ciclos", formatar_moeda(rolagem["resultado_total_rs"]),
                                             tipo="positivo" if rolagem["resultado_total_rs"] >= 0 else "negativo"), unsafe_allow_html=True)
                with rc3:
                    st.markdown(metric_card("Fecharam no prejuízo", f'{rolagem["n_prejuizo"]} de {rolagem["n_rolagens"]}',
                                             tipo="negativo" if rolagem["n_prejuizo"] > 0 else "positivo"), unsafe_allow_html=True)
                if rolagem["n_prejuizo"] > 0:
                    st.markdown(alert_box(
                        "A maioria dos ciclos de rolagem fechou no prejuízo, não em zero. "
                        "Vale recalibrar a expectativa de 'recuperação garantida' via rolagem."
                    ), unsafe_allow_html=True)
                st.dataframe(rolagem["detalhe"], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# ABA 2 — Venda de PUT (mínimas)
# ---------------------------------------------------------------------------

with tabs[1]:
    st.subheader("Painel de Venda de PUT — ativos próximos de mínimas")

    with st.spinner("Escaneando ativos da mesa..."):
        try:
            df_scan = escanear_ativos_mesa()
        except Exception as e:
            df_scan = None
            st.error(f"Erro ao acessar a planilha/dados: {e}")

    alertas = st.session_state.get("_alertas_normalizacao", [])
    if alertas:
        with st.expander(f"⚠️ {len(alertas)} alerta(s) de dados — revisar antes de operar", expanded=True):
            for a in alertas:
                st.markdown(f"- {a}")

    if st.session_state.get("_selic_fallback_em_uso"):
        st.markdown(alert_box(
            f"Taxa livre de risco (Selic) usando valor de fallback "
            f"({st.session_state.get('_taxa_livre_risco_atual', 0)*100:.2f}% a.a.) — "
            f"coluna SELIC não encontrada/inválida na planilha. Delta e gregas calculados com este valor."
        ), unsafe_allow_html=True)

    if df_scan is not None and not df_scan.empty:
        df_ok = df_scan[df_scan["DADOS_OK"] == True].copy()
        df_falha = df_scan[df_scan["DADOS_OK"] == False].copy()

        df_venda = df_ok.drop(columns=["MAX_6M", "DIST_MAX_PERC", "SCORE_COMPRA", "STATUS_COMPRA", "DADOS_OK"], errors="ignore")
        st.dataframe(
            df_venda, use_container_width=True, hide_index=True,
            column_config={
                "PRECO": st.column_config.NumberColumn("Preço Atual", format="R$ %.2f"),
                "MIN_6M": st.column_config.NumberColumn("Mínima 6M", format="R$ %.2f"),
                "DIST_MIN_PERC": st.column_config.NumberColumn("Dist. Mín %", format="%.2f%%"),
                "STRIKE_SUGERIDO": st.column_config.NumberColumn("Strike Ref.", format="R$ %.2f"),
                "IFR": st.column_config.NumberColumn("RSI", format="%.1f"),
                "ADX": st.column_config.NumberColumn("ADX", format="%.1f"),
                "SCORE_VENDA": st.column_config.NumberColumn("Score", format="%.0f"),
                "STATUS_VENDA": "Status de Entrada",
                "DEFASADO": st.column_config.CheckboxColumn("Dado defasado?"),
                "MOTIVO_FALHA": "Observação",
                "VALOR": st.column_config.NumberColumn("Capital (planilha)", format="R$ %.0f"),
            }
        )

        if not df_falha.empty:
            with st.expander(f"⚠️ {len(df_falha)} ativo(s) sem dados válidos nesta consulta — não entram no scanner", expanded=False):
                st.dataframe(df_falha[["ATIVO", "MOTIVO_FALHA"]], use_container_width=True, hide_index=True)
    elif df_scan is not None and df_scan.empty:
        st.warning("A planilha retornou vazia ou sem a coluna ATIVO — verifique o cabeçalho da planilha.")

    st.markdown("---")
    st.markdown("##### Cadeia de opções por delta real (critério: delta 0,15–0,20 · 50–75 dias)")

    fonte_opcoes = st.radio(
        "Fonte de dados de opções",
        ["COTAHIST/B3 (gratuito, D-1)", "MetaTrader5 (broker local — Windows)", "yfinance (cobertura B3 não validada)"],
        horizontal=True, key="fonte_opcoes_venda"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        ativo_put = st.text_input("Ativo (ex: PETR4)", "PETR4", key="ativo_venda_put")
        if st.button("Buscar cadeia de PUTs", key="btn_scan_puts"):
            with st.spinner("Consultando cadeia de opções..."):
                if fonte_opcoes.startswith("COTAHIST"):
                    preco_ref = df_scan[df_scan["ATIVO"] == ativo_put]["PRECO"].iloc[0] if (
                        df_scan is not None and not df_scan.empty and (df_scan["ATIVO"] == ativo_put).any()
                    ) else None
                    taxa_ref = st.session_state.get("_taxa_livre_risco_atual", 0.1075)
                    if preco_ref is None:
                        st.session_state["df_puts"] = None
                        st.session_state["erro_puts"] = f"Preço atual de {ativo_put} não encontrado no scanner — rode o scanner primeiro."
                    else:
                        candidatas, erro, data_usada = cotahist_provider.buscar_puts_cotahist(ativo_put, preco_ref, taxa_ref)
                        if erro:
                            st.session_state["df_puts"] = None
                            st.session_state["erro_puts"] = erro
                        else:
                            st.session_state["df_puts"] = pd.DataFrame(candidatas)
                            st.session_state["erro_puts"] = None
                            st.session_state["data_cotahist_usada"] = data_usada
                elif fonte_opcoes.startswith("MetaTrader5"):
                    if not mt5_provider.MT5_DISPONIVEL:
                        st.session_state["df_puts"] = None
                        st.session_state["erro_puts"] = (
                            "Pacote MetaTrader5 não disponível neste ambiente "
                            "(só funciona localmente, no Windows, com o terminal aberto)."
                        )
                    else:
                        ok, motivo = mt5_provider.conectar()
                        if not ok:
                            st.session_state["df_puts"] = None
                            st.session_state["erro_puts"] = motivo
                        else:
                            preco_ref = df_scan[df_scan["ATIVO"] == ativo_put]["PRECO"].iloc[0] if (
                                df_scan is not None and not df_scan.empty and (df_scan["ATIVO"] == ativo_put).any()
                            ) else None
                            taxa_ref = st.session_state.get("_taxa_livre_risco_atual", 0.1075)
                            if preco_ref is None:
                                st.session_state["df_puts"] = None
                                st.session_state["erro_puts"] = f"Preço atual de {ativo_put} não encontrado no scanner — rode o scanner primeiro."
                            else:
                                candidatas, erro = mt5_provider.buscar_puts_por_criterio(ativo_put, preco_ref, taxa_ref)
                                if erro:
                                    st.session_state["df_puts"] = None
                                    st.session_state["erro_puts"] = erro
                                else:
                                    df_mt5 = pd.DataFrame(candidatas).rename(columns={
                                        "ticker": "TICKER", "strike": "STRIKE", "dias": "DIAS",
                                        "premio": "PREMIO", "iv": "IV", "delta": "DELTA",
                                        "theta_dia": "THETA_DIA", "vega": "VEGA", "gamma": "GAMMA",
                                    })
                                    st.session_state["df_puts"] = df_mt5
                                    st.session_state["erro_puts"] = None
                else:
                    st.session_state["df_puts"] = buscar_puts_venda(ativo_put)
                    st.session_state["erro_puts"] = None
    with col2:
        if st.session_state.get("erro_puts"):
            st.error(st.session_state["erro_puts"])
        elif "df_puts" in st.session_state and st.session_state["df_puts"] is not None:
            df_puts_exibir = st.session_state["df_puts"]
            if "ERRO" in df_puts_exibir.columns:
                st.error(df_puts_exibir["ERRO"].iloc[0])
            else:
                aviso = df_puts_exibir.attrs.get("aviso")
                if aviso:
                    st.markdown(alert_box(aviso), unsafe_allow_html=True)
                if st.session_state.get("data_cotahist_usada"):
                    st.caption(f"📅 Dados de fechamento de {st.session_state['data_cotahist_usada'].strftime('%d/%m/%Y')} (COTAHIST — não é tempo real).")
                st.dataframe(
                    df_puts_exibir, use_container_width=True, hide_index=True,
                    column_config={
                        "STRIKE": st.column_config.NumberColumn("Strike", format="R$ %.2f"),
                        "PREMIO": st.column_config.NumberColumn("Prêmio", format="R$ %.2f"),
                        "IV": st.column_config.NumberColumn("IV %", format="%.1f%%"),
                        "DELTA": st.column_config.NumberColumn("Delta", format="%.3f"),
                        "THETA_DIA": st.column_config.NumberColumn("Theta/dia", format="%.4f"),
                        "VEGA": st.column_config.NumberColumn("Vega", format="%.4f"),
                        "GAMMA": st.column_config.NumberColumn("Gamma", format="%.4f"),
                        "PRECO_ATIVO": st.column_config.NumberColumn("Preço Ativo", format="R$ %.2f"),
                    }
                )
                st.caption(
                    "⚠️ Cobertura de opções da B3 via yfinance ainda não validada empiricamente para todos os "
                    "tickers — confirme manualmente os primeiros resultados antes de operar em cima deles."
                )

    st.markdown("---")
    st.markdown("##### Gráfico para análise visual")
    ativo_chart_venda = st.text_input("Ativo para gráfico", "PETR4", key="chart_venda")
    tradingview_widget(ativo_chart_venda, altura=480)


# ---------------------------------------------------------------------------
# ABA 3 — Compra de PUT (máximas) — estratégia espelhada
# ---------------------------------------------------------------------------

with tabs[2]:
    st.subheader("Painel de Compra de PUT — ativos próximos de máximas")
    st.caption(
        "Atenção: esta ponta tem perfil estatístico diferente da venda de PUT — "
        "theta trabalha contra a posição e o sucesso se mede pela relação ganho/perda "
        "por operação, não por taxa de acerto alta."
    )

    if df_scan is not None and not df_scan.empty:
        df_ok_compra = df_scan[df_scan["DADOS_OK"] == True].copy()
        df_compra = df_ok_compra.drop(columns=["MIN_6M", "DIST_MIN_PERC", "SCORE_VENDA", "STATUS_VENDA", "DADOS_OK"], errors="ignore")
        st.dataframe(
            df_compra, use_container_width=True, hide_index=True,
            column_config={
                "PRECO": st.column_config.NumberColumn("Preço Atual", format="R$ %.2f"),
                "MAX_6M": st.column_config.NumberColumn("Máxima 6M", format="R$ %.2f"),
                "DIST_MAX_PERC": st.column_config.NumberColumn("Dist. Máx %", format="%.2f%%"),
                "IFR": st.column_config.NumberColumn("RSI", format="%.1f"),
                "ADX": st.column_config.NumberColumn("ADX", format="%.1f"),
                "SCORE_COMPRA": st.column_config.NumberColumn("Score", format="%.0f"),
                "STATUS_COMPRA": "Status de Entrada",
            }
        )

    st.markdown("---")
    st.markdown("##### Gráfico para análise visual")
    ativo_chart_compra = st.text_input("Ativo para gráfico", "VALE3", key="chart_compra")
    tradingview_widget(ativo_chart_compra, altura=480)


# ---------------------------------------------------------------------------
# ABA 4 — Trava de Alta
# ---------------------------------------------------------------------------

with tabs[3]:
    st.subheader("Montagem inteligente de Trava de Alta")

    col1, col2 = st.columns([1, 2.3])

    with col1:
        ativo_trava = st.text_input("Ativo (ex: TOTS3)", "TOTS3", key="ativo_trava")

        if st.button("🔍 Analisar ponto de entrada", key="btn_analisar_trava"):
            with st.spinner("Analisando indicadores técnicos e níveis de suporte/resistência..."):
                st.session_state["analise_trava"] = analisar_ponto_trava(ativo_trava)

        analise = st.session_state.get("analise_trava")

        if analise:
            if analise["erro"]:
                st.error(analise["erro"])
            else:
                if analise["ponto_de_entrada"]:
                    st.markdown(badge("🟢 Ponto de entrada favorável", "ok"), unsafe_allow_html=True)
                else:
                    st.markdown(badge("🟡 Critério não plenamente atendido", "atencao"), unsafe_allow_html=True)
                st.caption(analise["motivo"])

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(metric_card("Preço atual", f"R$ {analise['preco_atual']:.2f}"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                rsi_txt = f"{analise['rsi']:.0f}" if analise['rsi'] is not None else "—"
                st.markdown(metric_card("RSI (14)", rsi_txt), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                regime_txt = analise['regime'] or "—"
                st.markdown(metric_card("Regime (ADX)", regime_txt), unsafe_allow_html=True)

        st.markdown("---")

        preco_default = analise["preco_atual"] if analise and not analise.get("erro") else 27.93
        sc_default = analise["strike_compra_sugerido"] if analise and not analise.get("erro") else 29.00
        sv_default = analise["strike_venda_sugerido"] if analise and not analise.get("erro") else 30.00

        preco = st.number_input("Preço Atual", value=float(preco_default), step=0.01, format="%.2f")
        qtd = st.number_input("Quantidade de Opções", value=100, step=100)
        sc = st.number_input("Strike Compra", value=float(sc_default), step=0.01, format="%.2f")
        sv = st.number_input("Strike Venda", value=float(sv_default), step=0.01, format="%.2f")

        tunel_rs = abs(sv - sc)
        tunel_pct = (tunel_rs / preco * 100) if preco else 0
        st.markdown(metric_card("Túnel (diferença de strikes)", f"R$ {tunel_rs:.2f}", f"{tunel_pct:.1f}% do preço do ativo"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        pc = st.number_input("Prêmio Pago (Compra)", value=1.51, step=0.01, format="%.2f")
        pv = st.number_input("Prêmio Recebido (Venda)", value=1.05, step=0.01, format="%.2f")

        custo_liquido = pc - pv

        capital_total_trava = st.number_input("Capital total da carteira (para checagem de exposição)", value=100000.0, step=1000.0, format="%.2f")
        valor_operacao = custo_liquido * qtd
        permitido, motivos_risco = validar_nova_entrada(
            ticker_base(ativo_trava), valor_operacao, capital_total_trava, None
        )
        cor_risco = "ok" if permitido else "alerta"
        st.markdown(badge("✅ Dentro do limite de exposição" if permitido else "🚫 Excede limite de exposição", cor_risco), unsafe_allow_html=True)
        for m in motivos_risco:
            st.caption(m)

    with col2:
        st.markdown("##### Análise de Payoff")
        st.plotly_chart(plot_payoff(sc, sv, preco, -custo_liquido, qtd), use_container_width=True)

        lucro_t = ((sv - sc) - custo_liquido) * qtd
        risco_t = custo_liquido * qtd
        relacao = abs(lucro_t / risco_t) if risco_t else None

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("Lucro Máximo", f"R$ {lucro_t:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), tipo="positivo"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Risco Máximo", f"R$ {risco_t:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), tipo="negativo"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Relação Ganho/Risco", f"{relacao:.2f}x" if relacao else "—"), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### Gráfico do ativo")
        tradingview_widget(ativo_trava, altura=420)


# ---------------------------------------------------------------------------
# ABA 5 — Risco (visão consolidada de exposição)
# ---------------------------------------------------------------------------

with tabs[4]:
    st.subheader("Painel de Risco e Exposição")

    df_ops_risco = carregar_operacoes()

    if df_ops_risco is None:
        st.info("Carregue o histórico de operações na aba Performance para visualizar a exposição consolidada.")
    else:
        df_conc_risco = calcular_concentracao_por_ativo(df_ops_risco)

        st.markdown("##### Barra de exposição por ativo")
        st.markdown(exposure_bar_html(df_conc_risco, LIMITE_PCT_POR_ATIVO * 100), unsafe_allow_html=True)

        acima_limite = df_conc_risco[df_conc_risco["ACIMA_DO_LIMITE"]] if not df_conc_risco.empty else pd.DataFrame()
        if not acima_limite.empty:
            for _, row in acima_limite.iterrows():
                st.markdown(alert_box(
                    f"{row['ATIVO_BASE']}: {row['PCT_CAPITAL']:.1f}% do capital "
                    f"(limite: {LIMITE_PCT_POR_ATIVO*100:.0f}%) — considerar reduzir antes de nova entrada."
                ), unsafe_allow_html=True)
        else:
            st.markdown(badge("✅ Nenhum ativo acima do limite de concentração", "ok"), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### Simulador — validar nova entrada antes de operar")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            ativo_sim = st.text_input("Código do ativo", "PETR4", key="sim_ativo")
        with rc2:
            valor_sim = st.number_input("Valor da nova operação (R$)", value=5000.0, step=500.0)
        with rc3:
            capital_sim = st.number_input("Capital total da carteira (R$)", value=100000.0, step=1000.0)

        if st.button("Validar entrada", key="btn_validar_risco"):
            df_abertas = df_ops_risco.copy()
            df_abertas["ATIVO_BASE"] = df_abertas["CODIGO"].apply(ticker_base)
            df_abertas = df_abertas.rename(columns={"VALOR_OP": "VALOR_OPERACAO"})
            permitido, motivos = validar_nova_entrada(ticker_base(ativo_sim), valor_sim, capital_sim, df_abertas)
            if permitido:
                st.markdown(badge("✅ Entrada permitida", "ok"), unsafe_allow_html=True)
            else:
                st.markdown(badge("🚫 Entrada bloqueada pelos limites de risco", "alerta"), unsafe_allow_html=True)
            for m in motivos:
                st.caption(m)


# ---------------------------------------------------------------------------
# ABA 6 — Carteira (gestão de posições abertas até o vencimento)
# ---------------------------------------------------------------------------

with tabs[5]:
    st.subheader("Gestão da Carteira — posições abertas até o vencimento")
    st.caption(
        "Acompanhe cada posição aberta e veja se o gatilho de saída dinâmica (trailing) já foi "
        "atingido. Atualize o Prêmio Atual periodicamente (manualmente, por enquanto) para manter "
        "a avaliação em dia."
    )

    if "df_carteira" not in st.session_state:
        st.session_state["df_carteira"] = pd.DataFrame([portfolio_engine.linha_vazia()])

    st.markdown("##### Posições abertas")
    df_editada = st.data_editor(
        st.session_state["df_carteira"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "TIPO_OPERACAO": st.column_config.SelectboxColumn("Tipo", options=["venda_put", "compra_put"]),
            "DATA_ABERTURA": st.column_config.DateColumn("Data Abertura"),
            "VENCIMENTO": st.column_config.DateColumn("Vencimento"),
            "PREMIO_ABERTURA": st.column_config.NumberColumn("Prêmio Abertura", format="R$ %.2f"),
            "PREMIO_EXTREMO_HIST": st.column_config.NumberColumn(
                "Prêmio Mín/Máx Hist.",
                help="Para venda de PUT: menor prêmio já observado desde a abertura. Para compra de PUT: maior prêmio já observado.",
                format="R$ %.2f"
            ),
            "PREMIO_ATUAL": st.column_config.NumberColumn("Prêmio Atual", format="R$ %.2f"),
            "QTDE": st.column_config.NumberColumn("Quantidade"),
            "STRIKE": st.column_config.NumberColumn("Strike", format="R$ %.2f"),
            "SUPORTE_REFERENCIA": st.column_config.NumberColumn(
                "Suporte Ref. (opcional)",
                help="Nível técnico que justificou a entrada — usado para invalidação técnica na venda de PUT.",
                format="R$ %.2f"
            ),
            "VALOR_OPERACAO": st.column_config.NumberColumn("Capital Alocado", format="R$ %.0f"),
        },
        key="editor_carteira",
    )
    st.session_state["df_carteira"] = df_editada

    df_valida = df_editada[df_editada["CODIGO"].astype(str).str.strip() != ""]

    if df_valida.empty:
        st.info("Adicione ao menos uma posição na tabela acima para ver a avaliação de saída.")
    else:
        preco_atual_por_ativo = {}
        if df_scan is not None and not df_scan.empty and "PRECO" in df_scan.columns:
            for _, r in df_scan.iterrows():
                if r.get("DADOS_OK"):
                    preco_atual_por_ativo[ticker_base(r["ATIVO"])] = r["PRECO"]

        df_avaliada = portfolio_engine.avaliar_carteira(df_valida, preco_atual_por_ativo)
        resumo = portfolio_engine.resumo_carteira(df_avaliada)

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(metric_card("Total de posições", str(resumo["total"])), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("🔴 Encerrar agora", str(resumo["encerrar_agora"]), tipo="negativo" if resumo["encerrar_agora"] else None), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("🟡 Revisar manualmente", str(resumo["revisar"])), unsafe_allow_html=True)
        with c4:
            st.markdown(metric_card("🟠 Vencimento próximo", str(resumo["vencimento_proximo"])), unsafe_allow_html=True)
        with c5:
            st.markdown(metric_card("🟢 Manter", str(resumo["manter"]), tipo="positivo"), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### Avaliação detalhada por posição")
        st.dataframe(
            df_avaliada[["CODIGO", "TIPO_OPERACAO", "DIAS_EM_ABERTO", "DIAS_ATE_VENCIMENTO", "DECISAO", "MOTIVO"]],
            use_container_width=True, hide_index=True,
            column_config={
                "CODIGO": "Ativo/Opção", "TIPO_OPERACAO": "Tipo",
                "DIAS_EM_ABERTO": "Dias em aberto", "DIAS_ATE_VENCIMENTO": "Dias p/ vencimento",
                "DECISAO": "Status", "MOTIVO": "Justificativa",
            }
        )

        capital_ref = st.number_input("Capital total da carteira (para % de exposição)", value=100000.0, step=1000.0, key="capital_carteira")
        df_exp = portfolio_engine.exposicao_carteira_aberta(df_valida, capital_ref)
        if not df_exp.empty:
            st.markdown("##### Concentração da carteira aberta")
            acima = df_exp[~df_exp["LIMITE_OK"]] if "LIMITE_OK" in df_exp.columns else pd.DataFrame()
            if not acima.empty:
                for _, row in acima.iterrows():
                    st.markdown(alert_box(f"{row['ATIVO_BASE']}: {row['PCT_CAPITAL']*100:.1f}% do capital (limite: {LIMITE_PCT_POR_ATIVO*100:.0f}%)."), unsafe_allow_html=True)
            st.dataframe(df_exp, use_container_width=True, hide_index=True)


render_footer()
