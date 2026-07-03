"""
app.py
VRE Options Pro — aplicativo principal.
"""

import streamlit as st
import pandas as pd
import datetime

from layout import render_header, render_footer
from styles import inject_styles, metric_card, badge, alert_box, exposure_bar_html
from charts import plot_payoff, tradingview_widget, plot_curva_capital, plot_concentracao_ativos, plot_distribuicao_resultados
from quant_engine import analisar_ponto_trava
from scanner_engine import escanear_ativos_mesa
from scanner_options import buscar_puts_venda
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
# Funções de Carregamento
# ---------------------------------------------------------------------------

def carregar_operacoes():
    return st.session_state.get("df_operacoes")

def normalizar_df_operacoes(df_raw):
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
# Header e Refresh
# ---------------------------------------------------------------------------

render_header()

col_status, col_refresh = st.columns([4, 1])
with col_status:
    if "_ultima_atualizacao" not in st.session_state:
        st.session_state["_ultima_atualizacao"] = None
    ts = st.session_state["_ultima_atualizacao"]
    st.caption(f"Última atualização: {ts.strftime('%d/%m/%Y %H:%M:%S') if ts else 'ainda não atualizado'} · Fonte: yfinance (unificada)")

with col_refresh:
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.session_state["_ultima_atualizacao"] = datetime.datetime.now()
        st.rerun()

tabs = st.tabs(["📊 Performance", "💰 Venda de PUT", "🐻 Compra de PUT", "🚀 Trava de Alta", "🛡️ Risco", "📁 Carteira"])

# ---------------------------------------------------------------------------
# ABA 1 — Performance
# ---------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Análise de performance")
    with st.expander("📁 Carregar operações (CSV/TSV)", expanded=(carregar_operacoes() is None)):
        arquivo = st.file_uploader("Selecione o arquivo", type=["csv", "tsv", "txt"])
        if arquivo:
            sep = "\t" if arquivo.name.endswith((".tsv", ".txt")) else ","
            df_raw = pd.read_csv(arquivo, sep=sep, dtype=str)
            st.session_state["df_operacoes"] = normalizar_df_operacoes(df_raw)
            st.rerun()

    df_ops = carregar_operacoes()
    if df_ops is not None:
        metricas = calcular_metricas_gerais(df_ops)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(metric_card("Taxa de acerto", f"{metricas['win_rate_pct']:.1f}%"), unsafe_allow_html=True)
        with c2: st.markdown(metric_card("Expectância", formatar_moeda(metricas['expectancia_rs'])), unsafe_allow_html=True)
        with c3: st.markdown(metric_card("Resultado Total", formatar_moeda(metricas['lucro_total_rs'])), unsafe_allow_html=True)
        with c4: st.markdown(metric_card("Drawdown", formatar_moeda(metricas['max_drawdown_rs']), tipo="negativo"), unsafe_allow_html=True)
        
        col_esq, col_dir = st.columns([1.3, 1])
        with col_esq:
            st.plotly_chart(plot_curva_capital(curva_de_capital(df_ops)), use_container_width=True)
        with col_dir:
            df_conc = calcular_concentracao_por_ativo(df_ops)
            st.plotly_chart(plot_concentracao_ativos(df_conc), use_container_width=True)

# ---------------------------------------------------------------------------
# ABAS 2, 3 e 4 (Scanner e Trava)
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Painel de Venda de PUT")
    df_scan = escanear_ativos_mesa()
    st.dataframe(df_scan, use_container_width=True)
    ativo_venda = st.text_input("Ativo para buscar PUTs", "PETR4")
    if st.button("Buscar"):
        st.session_state["df_puts"] = buscar_puts_venda(ativo_venda)
    st.dataframe(st.session_state.get("df_puts", pd.DataFrame()))

with tabs[2]:
    st.subheader("Painel de Compra de PUT")
    st.dataframe(df_scan, use_container_width=True)

with tabs[3]:
    st.subheader("Montagem de Trava de Alta")
    ativo_trava = st.text_input("Ativo Trava", "VALE3")
    if st.button("Analisar"):
        st.session_state["analise_trava"] = analisar_ponto_trava(ativo_trava)
    if "analise_trava" in st.session_state:
        st.write(st.session_state["analise_trava"])

# ---------------------------------------------------------------------------
# ABA 5 — Risco
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Painel de Risco")
    if df_ops is not None:
        df_conc = calcular_concentracao_por_ativo(df_ops)
        st.markdown(exposure_bar_html(df_conc, LIMITE_PCT_POR_ATIVO * 100), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ABA 6 — Carteira (Integrada conforme solicitado)
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Gestão da Carteira — posições abertas até o vencimento")
    
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
            "PREMIO_ATUAL": st.column_config.NumberColumn("Prêmio Atual", format="R$ %.2f"),
            "QTDE": st.column_config.NumberColumn("Quantidade"),
            "STRIKE": st.column_config.NumberColumn("Strike", format="R$ %.2f"),
            "VALOR_OPERACAO": st.column_config.NumberColumn("Capital Alocado", format="R$ %.0f"),
        },
        key="editor_carteira",
    )
    st.session_state["df_carteira"] = df_editada

    df_valida = df_editada[df_editada["CODIGO"].astype(str).str.strip() != ""]

    if not df_valida.empty:
        # Extração de preços do scan (ou chamada direta se desejar expandir para todo ativo)
        precos_atuais = {}
        if df_scan is not None and not df_scan.empty:
            for _, r in df_scan.iterrows():
                precos_atuais[ticker_base(r["ATIVO"])] = r["PRECO"]

        df_avaliada = portfolio_engine.avaliar_carteira(df_valida, precos_atuais)
        
        st.markdown("---")
        st.markdown("##### Avaliação detalhada por posição")
        st.dataframe(
            df_avaliada[["CODIGO", "TIPO_OPERACAO", "DECISAO", "MOTIVO"]],
            use_container_width=True, hide_index=True
        )

render_footer()
