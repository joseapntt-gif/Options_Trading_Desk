"""
scanner_engine.py
Varre a lista de ativos da planilha (Google Sheets) e usa market_data.py
como FONTE ÚNICA de preço/mínima/máxima/histórico — corrigindo a
inconsistência da versão anterior, em que preço vinha da planilha e os
indicadores técnicos vinham de uma busca separada no yfinance, podendo
divergir entre si para o mesmo ativo na mesma leitura.

A planilha agora é usada apenas para:
  - a lista de tickers acompanhados (coluna ATIVO)
  - capital alocado por ativo, se preenchido (coluna VALOR)
  - taxa livre de risco (coluna SELIC) — com fallback explícito e sinalizado
    se ausente (ver market_data.resolver_taxa_livre_risco)

Nenhuma falha é silenciosa: cada linha carrega um campo DADOS_OK e, quando
False, MOTIVO_FALHA explica o que não pôde ser calculado — a UI decide como
destacar isso, mas o dado nunca se mistura com um resultado válido.
"""

import pandas as pd
import numpy as np
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from utils import normalizar_valor
from market_data import obter_preco_e_niveis, resolver_taxa_livre_risco
from score_engine import (
    calcular_indicadores_tecnicos,
    calcular_score_venda_put, definir_status_venda,
    calcular_score_compra_put, definir_status_compra,
)

SHEET_ID = "1oQmaZiF0f7jc5oSwTDy16QHTHvgU11Vx9GE4eXMauM0"


def _get_client():
    creds_dict = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_data(ttl=300, show_spinner=False)
def _carregar_planilha():
    client = _get_client()
    sheet = client.open_by_key(SHEET_ID).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [str(c).upper().strip() for c in df.columns]
    return df


def escanear_ativos_mesa(forcar_atualizacao=False):
    df = _carregar_planilha().copy()

    if "ATIVO" not in df.columns:
        st.session_state["_alertas_normalizacao"] = ["Coluna ATIVO não encontrada na planilha — verifique o cabeçalho."]
        return pd.DataFrame()

    # capital alocado (VALOR) — opcional, usado pelo risk_engine se presente
    if "VALOR" in df.columns:
        df["VALOR_NORM"] = df["VALOR"].apply(normalizar_valor)
    else:
        df["VALOR_NORM"] = np.nan

    # taxa livre de risco (SELIC) — lida uma vez, vale para todas as linhas
    selic_planilha = None
    if "SELIC" in df.columns and len(df) > 0:
        selic_planilha = normalizar_valor(df["SELIC"].iloc[0])
    taxa_livre_risco, usando_fallback_selic = resolver_taxa_livre_risco(selic_planilha)

    alertas = []
    if usando_fallback_selic:
        alertas.append(
            f"Coluna SELIC não encontrada/inválida na planilha — usando taxa de fallback "
            f"({taxa_livre_risco*100:.2f}% a.a.). Atualize a planilha ou o valor em market_data.SELIC_FALLBACK."
        )

    linhas = []
    for _, row in df.iterrows():
        ativo = str(row.get("ATIVO", "")).strip()
        base = {
            "ATIVO": ativo,
            "VALOR": row.get("VALOR_NORM"),
            "DADOS_OK": False,
            "MOTIVO_FALHA": None,
            "DEFASADO": False,
        }

        if not ativo:
            base["MOTIVO_FALHA"] = "Código de ativo vazio na planilha."
            linhas.append(base)
            continue

        dados = obter_preco_e_niveis(ativo, forcar_atualizacao=forcar_atualizacao)

        if not dados["ok"]:
            base["MOTIVO_FALHA"] = dados["motivo"]
            linhas.append(base)
            alertas.append(f"{ativo}: {dados['motivo']}")
            continue

        preco = dados["preco_atual"]
        min_p = dados["min_periodo"]
        max_p = dados["max_periodo"]
        hist = dados["hist"]

        indicadores = calcular_indicadores_tecnicos(hist)
        dist_min_pct = ((preco - min_p) / min_p * 100) if min_p else None
        dist_max_pct = ((max_p - preco) / preco * 100) if preco else None

        sv, _ = calcular_score_venda_put(indicadores, dist_min_pct)
        sc, _ = calcular_score_compra_put(indicadores, dist_max_pct)

        base.update({
            "DADOS_OK": True,
            "DEFASADO": dados["defasado"],
            "MOTIVO_FALHA": dados["motivo"] if dados["defasado"] else None,
            "PRECO": preco,
            "MIN_6M": min_p,
            "MAX_6M": max_p,
            "DIST_MIN_PERC": dist_min_pct,
            "DIST_MAX_PERC": dist_max_pct,
            "IFR": indicadores.get("rsi"),
            "ADX": indicadores.get("adx"),
            "REGIME": indicadores.get("regime"),
            "SCORE_VENDA": sv,
            "STATUS_VENDA": definir_status_venda(sv, indicadores.get("padrao_reversao_alta", False), indicadores.get("adx")),
            "SCORE_COMPRA": sc,
            "STATUS_COMPRA": definir_status_compra(sc, indicadores.get("padrao_reversao_baixa", False), indicadores.get("adx")),
            "TAXA_LIVRE_RISCO": taxa_livre_risco,
        })
        linhas.append(base)

    df_final = pd.DataFrame(linhas)

    # compatibilidade com nomes usados no app.py
    if "SCORE_VENDA" in df_final.columns:
        df_final["SCORE"] = df_final["SCORE_VENDA"]
        df_final["STATUS"] = df_final["STATUS_VENDA"]
        df_final["STRIKE_SUGERIDO"] = df_final["PRECO"] * 0.88

    st.session_state["_alertas_normalizacao"] = alertas
    st.session_state["_taxa_livre_risco_atual"] = taxa_livre_risco
    st.session_state["_selic_fallback_em_uso"] = usando_fallback_selic

    return df_final

