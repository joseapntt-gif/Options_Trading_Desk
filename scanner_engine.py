"""
scanner_engine.py
Varre a lista de ativos da planilha (Google Sheets) e, para cada um, busca o
histórico real via yfinance para calcular os indicadores técnicos e o score
de entrada nas duas pontas (venda de PUT / compra de PUT).

Correções em relação à versão anterior:
  - normalização de preço sem heurística de divisão por magnitude (ver utils.py)
  - SCORE agora é de fato calculado e conectado (score_engine.py)
  - status de entrada reflete padrão de candle + regime de mercado, não só
    distância percentual da mínima
  - erros de indicador ficam visíveis na UI em vez de virarem "neutro" silencioso
"""

import pandas as pd
import numpy as np
import streamlit as st
import gspread
import yfinance as yf
from google.oauth2.service_account import Credentials

from utils import normalizar_valor, preco_plausivel, ticker_base
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


@st.cache_data(ttl=900, show_spinner=False)
def _historico_ativo(ticker_b3, periodo="6mo"):
    """Histórico OHLCV via yfinance, cacheado por 15 min."""
    try:
        hist = yf.Ticker(f"{ticker_b3.upper().strip()}.SA").history(period=periodo)
        return hist if not hist.empty else None
    except Exception:
        return None


def escanear_ativos_mesa():
    df = _carregar_planilha().copy()

    if "IFR" not in df.columns:
        for col in df.columns:
            if "IFR" in col:
                df.rename(columns={col: "IFR_PLANILHA"}, inplace=True)
                break

    cols_valor = ["PRECO", "MIN_6M", "MAX_6M"]
    alertas_normalizacao = []
    for col in cols_valor:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_valor)

    # Validação de plausibilidade — sem correção automática, só alerta
    for idx, row in df.iterrows():
        ok, motivo = preco_plausivel(row.get("PRECO"))
        if not ok:
            alertas_normalizacao.append(f"{row.get('ATIVO', '?')}: {motivo}")

    df["DIST_MIN_PERC"] = ((df["PRECO"] - df["MIN_6M"]) / df["MIN_6M"].replace(0, np.nan)) * 100
    df["DIST_MAX_PERC"] = ((df["MAX_6M"] - df["PRECO"]) / df["PRECO"].replace(0, np.nan)) * 100

    scores_venda, status_venda, scores_compra, status_compra = [], [], [], []
    rsi_col, adx_col, regime_col = [], [], []

    for _, row in df.iterrows():
        ativo = str(row.get("ATIVO", "")).strip()
        hist = _historico_ativo(ativo) if ativo else None
        indicadores = calcular_indicadores_tecnicos(hist) if hist is not None else {"erro": "Sem histórico"}

        sv, _ = calcular_score_venda_put(indicadores, row.get("DIST_MIN_PERC"))
        sc, _ = calcular_score_compra_put(indicadores, row.get("DIST_MAX_PERC"))

        scores_venda.append(sv)
        status_venda.append(definir_status_venda(sv, indicadores.get("padrao_reversao_alta", False), indicadores.get("adx")))
        scores_compra.append(sc)
        status_compra.append(definir_status_compra(sc, indicadores.get("padrao_reversao_baixa", False), indicadores.get("adx")))
        rsi_col.append(indicadores.get("rsi"))
        adx_col.append(indicadores.get("adx"))
        regime_col.append(indicadores.get("regime"))

    df["IFR"] = rsi_col
    df["ADX"] = adx_col
    df["REGIME"] = regime_col
    df["SCORE_VENDA"] = scores_venda
    df["STATUS_VENDA"] = status_venda
    df["SCORE_COMPRA"] = scores_compra
    df["STATUS_COMPRA"] = status_compra

    # mantém compatibilidade com nomes usados no app.py original
    df["SCORE"] = df["SCORE_VENDA"]
    df["STATUS"] = df["STATUS_VENDA"]
    df["STRIKE_SUGERIDO"] = df["PRECO"] * 0.88  # fallback simples; ver quant_engine para sugestão por delta real

    st.session_state["_alertas_normalizacao"] = alertas_normalizacao

    return df
