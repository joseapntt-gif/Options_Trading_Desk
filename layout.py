"""
layout.py
Header e footer institucionais — agora de fato conectados ao CSS de
styles.py (na versão anterior, inject_styles() nunca era chamada em
app.py e tinha um `pass` que a desativava por completo).
"""

import streamlit as st


def render_header(subtitulo="Mesa de Derivativos — Venda/Compra de PUT e Trava de Alta"):
    st.markdown(f"""
        <div class="vre-header">
            <h1>VRE Options Pro</h1>
            <p>{subtitulo}</p>
        </div>
    """, unsafe_allow_html=True)


def render_footer():
    st.markdown("""
        <div class="vre-footer">
            Mesa Quant de Opções © 2026 · Este aplicativo não constitui recomendação de investimento ·
            Dados sujeitos a atraso/indisponibilidade das fontes (Google Sheets / Yahoo Finance)
        </div>
    """, unsafe_allow_html=True)
