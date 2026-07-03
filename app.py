"""
app.py — VRE Options Pro
Versão integrada com Portfolio Engine e Dashboard de Trava.
"""

import streamlit as st
import pandas as pd
import datetime

# Importações de módulos locais
from layout import render_header, render_footer
from styles import inject_styles, metric_card, alert_box, exposure_bar_html
from charts import plot_curva_capital, plot_concentracao_ativos
from quant_engine import analisar_ponto_trava
from scanner_engine import escanear_ativos_mesa
from performance_engine import calcular_metricas_gerais, calcular_concentracao_por_ativo, curva_de_capital
from risk_engine import LIMITE_PCT_POR_ATIVO
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
# ABA 3 — Trava de Alta (Layout Corrigido)
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
        
        st.markdown("##### Estrutura sugerida")
        col_a, col_b = st.columns(2)
        col_a.write(f"**Strike Compra:** R$ {res['strike_compra_sugerido']:.2f}")
        col_b.write(f"**Strike Venda:** R$ {res['strike_venda_sugerido']:.2f}")
        st.write(f"**Amplitude:** R$ {res['tunel_rs']:.2f} ({res['tunel_pct']:.2f}%)")

# ---------------------------------------------------------------------------
# ABA 6 — Carteira (Integrada)
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Gestão da Carteira — posições abertas")
    
    if "df_carteira" not in st.session_state:
        st.session_state["df_carteira"] = pd.DataFrame([portfolio_engine.linha_vazia()])

    df_editada = st.data_editor(
        st.session_state["df_carteira"],
        num_rows="dynamic",
        key="editor_carteira",
        column_config={
            "TIPO_OPERACAO": st.column_config.SelectboxColumn("Tipo", options=["venda_put", "compra_put"]),
            "PREMIO_ABERTURA": st.column_config.NumberColumn(format="R$ %.2f"),
            "PREMIO_ATUAL": st.column_config.NumberColumn(format="R$ %.2f"),
            "STRIKE": st.column_config.NumberColumn(format="R$ %.2f"),
        }
    )
    st.session_state["df_carteira"] = df_editada

    df_valida = df_editada[df_editada["CODIGO"].astype(str).str.strip() != ""]

    if not df_valida.empty:
        # Pega preços atuais do scanner se disponível
        precos_map = {}
        df_scan = escanear_ativos_mesa() # Reutiliza lógica de scan
        if not df_scan.empty:
            for _, r in df_scan.iterrows():
                precos_map[ticker_base(r["ATIVO"])] = r["PRECO"]

        df_avaliada = portfolio_engine.avaliar_carteira(df_valida, precos_map)
        resumo = portfolio_engine.resumo_carteira(df_avaliada)

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(metric_card("Total", str(resumo["total"])), unsafe_allow_html=True)
        c2.markdown(metric_card("Encerrar", str(resumo["encerrar_agora"])), unsafe_allow_html=True)
        c3.markdown(metric_card("Revisar", str(resumo["revisar"])), unsafe_allow_html=True)
        c4.markdown(metric_card("Manter", str(resumo["manter"])), unsafe_allow_html=True)

        st.dataframe(df_avaliada[["CODIGO", "DECISAO", "MOTIVO"]], use_container_width=True)

render_footer()
