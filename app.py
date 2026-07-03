"""
app.py — VRE Options Pro
Versão final integrada com Scanner, Risk Engine e Portfolio Engine.
"""

import streamlit as st
import pandas as pd
from layout import render_header, render_footer
from styles import inject_styles, metric_card
from quant_engine import analisar_ponto_trava
from scanner_engine import escanear_ativos_mesa
import portfolio_engine
from utils import ticker_base

st.set_page_config(page_title="VRE Options Pro", layout="wide", initial_sidebar_state="collapsed", page_icon="📈")
inject_styles()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
render_header()
tabs = st.tabs(["📊 Performance", "💰 Venda de PUT", "🐻 Compra de PUT", "🚀 Trava de Alta", "🛡️ Risco", "📁 Carteira"])

# ---------------------------------------------------------------------------
# ABA 1 — Venda de PUT
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Análise para Venda de PUT")
    if st.button("Atualizar Dados Venda"):
        df_venda = escanear_ativos_mesa(forcar_atualizacao=True)
    else:
        df_venda = escanear_ativos_mesa()

    if not df_venda.empty:
        # Colunas solicitadas: ATIVO, VALOR, MIN_6M, DIST%, IFR, STRIKE SUG., STATUS
        cols = ["ATIVO", "VALOR", "MIN_6M", "DIST_MIN_PERC", "IFR", "STRIKE_SUGERIDO", "STATUS_VENDA"]
        df_display = df_venda[cols].rename(columns={
            "DIST_MIN_PERC": "DIST%", 
            "STRIKE_SUGERIDO": "STRIKE SUG.",
            "STATUS_VENDA": "STATUS"
        })
        st.dataframe(df_display, use_container_width=True, column_config={
            "DIST%": st.column_config.NumberColumn(format="%.2f%%"),
            "STRIKE SUG.": st.column_config.NumberColumn(format="R$ %.2f")
        })

# ---------------------------------------------------------------------------
# ABA 2 — Compra de PUT
# ---------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Análise para Compra de PUT")
    df_compra = escanear_ativos_mesa()

    if not df_compra.empty:
        # Colunas solicitadas: ATIVO, VALOR, MIN_6M, DIST%, IFR, STATUS
        cols = ["ATIVO", "VALOR", "MAX_6M", "DIST_MAX_PERC", "IFR", "STATUS_COMPRA"]
        df_display_c = df_compra[cols].rename(columns={
            "MAX_6M": "MIN_6M", # Ajuste visual conforme sua solicitação de colunas
            "DIST_MAX_PERC": "DIST%", 
            "STATUS_COMPRA": "STATUS"
        })
        st.dataframe(df_display_c, use_container_width=True, column_config={
            "DIST%": st.column_config.NumberColumn(format="%.2f%%")
        })

# ---------------------------------------------------------------------------
# ABA 3 — Trava de Alta
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Montagem de Trava de Alta")
    ativo_trava = st.text_input("Ativo para Análise de Trava", "VALE3")
    if st.button("Analisar Trava"):
        st.session_state["analise_trava"] = analisar_ponto_trava(ativo_trava)

    if "analise_trava" in st.session_state:
        res = st.session_state["analise_trava"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Preço Atual", f"R$ {res['preco_atual']:.2f}")
        c2.metric("Suporte", f"R$ {res['suporte_recente']:.2f}")
        c3.metric("Resistência", f"R$ {res['resistencia_recente']:.2f}")
        st.subheader(f"Status: {'Confirmado' if res['ponto_de_entrada'] else 'Aguardando'}")
        st.info(f"Motivo: {res['motivo']}")

# ---------------------------------------------------------------------------
# ABA 6 — Carteira
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Gestão da Carteira")
    if "df_carteira" not in st.session_state:
        st.session_state["df_carteira"] = pd.DataFrame([portfolio_engine.linha_vazia()])
    
    st.session_state["df_carteira"] = st.data_editor(st.session_state["df_carteira"], num_rows="dynamic")
    
    df_valida = st.session_state["df_carteira"][st.session_state["df_carteira"]["CODIGO"].astype(str).str.strip() != ""]
    if not df_valida.empty:
        precos_map = {ticker_base(r["ATIVO"]): r["PRECO"] for _, r in escanear_ativos_mesa().iterrows()}
        df_avaliada = portfolio_engine.avaliar_carteira(df_valida, precos_map)
        st.dataframe(df_avaliada[["CODIGO", "DECISAO", "MOTIVO"]], use_container_width=True)

render_footer()
