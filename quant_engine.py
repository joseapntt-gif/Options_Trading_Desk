"""
quant_engine.py
Analisa se o ativo selecionado está de fato num bom ponto de montagem de
trava de alta, com base em dados reais (yfinance) — substitui a versão
anterior que usava tendência fixa ("Alta" hardcoded) e strikes por um
desconto percentual arbitrário.

Lógica de sugestão de strikes:
  - strike de compra: próximo ao preço atual (ligeiramente OTM), ponto de
    entrada da trava
  - strike de venda: no nível de resistência recente (máxima móvel dos
    últimos N candles), não um percentual fixo — reflete onde o mercado
    historicamente teve dificuldade de romper
  - túnel = diferença entre os strikes. Túnel maior = mais espaço para o
    ativo se valorizar até o teto da trava (mais resiliente a erro de
    timing), mas normalmente exige mais capital/menor relação prêmio-risco.
    O app mostra o túnel em R$ e em % do preço do ativo para o usuário
    calibrar a resiliência desejada.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from utils import normalizar_valor
from score_engine import calcular_indicadores_tecnicos

SHEET_ID = "1oQmaZiF0f7jc5oSwTDy16QHTHvgU11Vx9GE4eXMauM0"


def buscar_preco_planilha(ticker_symbol):
    """Mantido como fallback manual — busca só o preço cadastrado na planilha da mesa."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        df.columns = [str(c).upper().strip() for c in df.columns]
        linha = df[df["ATIVO"] == ticker_symbol.upper().strip()]
        if linha.empty:
            return None
        return normalizar_valor(linha.iloc[0]["PRECO"])
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def _historico(ticker_b3, periodo="6mo"):
    try:
        hist = yf.Ticker(f"{ticker_b3.upper().strip()}.SA").history(period=periodo)
        return hist if not hist.empty else None
    except Exception:
        return None


def _nivel_resistencia(hist, janela=20):
    """Máxima dos últimos `janela` candles, excluindo o candle atual — resistência recente."""
    if hist is None or len(hist) < janela + 1:
        return None
    return float(hist['High'].iloc[-(janela + 1):-1].max())


def _nivel_suporte(hist, janela=20):
    if hist is None or len(hist) < janela + 1:
        return None
    return float(hist['Low'].iloc[-(janela + 1):-1].min())


def analisar_ponto_trava(ticker_symbol, arredondamento=0.05):
    """
    Análise completa do ponto de montagem de trava de alta para o ativo.
    Retorna um dicionário com preço, indicadores, se está ou não no ponto
    de entrada, e os strikes/túnel sugeridos — sempre com a justificativa,
    nunca um "Alta" fixo sem base.
    """
    resultado = {
        "ticker": ticker_symbol.upper().strip(),
        "preco_atual": None,
        "ponto_de_entrada": False,
        "motivo": "",
        "strike_compra_sugerido": None,
        "strike_venda_sugerido": None,
        "tunel_rs": None,
        "tunel_pct": None,
        "resistencia_recente": None,
        "suporte_recente": None,
        "rsi": None,
        "adx": None,
        "regime": None,
        "padrao_confirmado": False,
        "erro": None,
    }

    hist = _historico(ticker_symbol)
    if hist is None:
        resultado["erro"] = "Não foi possível obter histórico via yfinance para este ticker."
        return resultado

    preco_atual = float(hist['Close'].iloc[-1])
    resultado["preco_atual"] = preco_atual

    indicadores = calcular_indicadores_tecnicos(hist)
    if indicadores.get("erro"):
        resultado["erro"] = indicadores["erro"]
        return resultado

    resistencia = _nivel_resistencia(hist)
    suporte = _nivel_suporte(hist)
    resultado["resistencia_recente"] = resistencia
    resultado["suporte_recente"] = suporte
    resultado["rsi"] = indicadores.get("rsi")
    resultado["adx"] = indicadores.get("adx")
    resultado["regime"] = indicadores.get("regime")
    resultado["padrao_confirmado"] = indicadores.get("padrao_reversao_alta", False)

    # --- Critério objetivo de "ponto de entrada" para trava de alta ---
    rsi = indicadores.get("rsi")
    adx = indicadores.get("adx")
    padrao = indicadores.get("padrao_reversao_alta", False)
    volume_ok = indicadores.get("volume_confirma_alta", False)

    motivos = []
    apto = True

    if rsi is not None and rsi > 70:
        apto = False
        motivos.append(f"RSI em sobrecompra ({rsi:.0f}) — risco de entrar tarde no movimento")
    if adx is not None and adx >= 25 and rsi is not None and rsi > 60:
        motivos.append("Tendência forte já em curso — considerar que o espaço de alta remanescente pode ser menor")
    if not padrao:
        apto = False
        motivos.append("Padrão de reversão (3 candles com topos ascendentes) não confirmado")
    elif not volume_ok:
        motivos.append("Padrão de reversão presente, mas sem confirmação de volume — sinal mais fraco")

    if apto and not motivos:
        motivos.append("RSI saudável, padrão de reversão confirmado com volume — critério técnico atendido")

    resultado["ponto_de_entrada"] = apto
    resultado["motivo"] = " | ".join(motivos)

    # --- Sugestão de strikes baseada em suporte/resistência real ---
    strike_compra = round(preco_atual / arredondamento) * arredondamento
    if resistencia and resistencia > strike_compra:
        strike_venda = round(resistencia / arredondamento) * arredondamento
    else:
        # sem resistência clara acima do preço: usa banda de Bollinger superior como proxy
        banda_sup = indicadores.get("banda_sup")
        strike_venda = round(banda_sup / arredondamento) * arredondamento if banda_sup else round(preco_atual * 1.05 / arredondamento) * arredondamento

    if strike_venda <= strike_compra:
        strike_venda = strike_compra + arredondamento * 2

    resultado["strike_compra_sugerido"] = strike_compra
    resultado["strike_venda_sugerido"] = strike_venda
    resultado["tunel_rs"] = round(strike_venda - strike_compra, 2)
    resultado["tunel_pct"] = round((resultado["tunel_rs"] / preco_atual) * 100, 2) if preco_atual else None

    return resultado


def sugerir_melhor_trava(ticker_symbol):
    """
    Mantido por compatibilidade com chamadas antigas — agora delega para a
    análise completa e retorna a tupla (preco, strike_compra, strike_venda, tendencia).
    `tendencia` deixou de ser fixa: reflete o resultado real da análise.
    """
    r = analisar_ponto_trava(ticker_symbol)
    if r["erro"]:
        raise Exception(r["erro"])
    tendencia = "Alta (critério atendido)" if r["ponto_de_entrada"] else "Aguardar — critério não atendido"
    return r["preco_atual"], r["strike_compra_sugerido"], r["strike_venda_sugerido"], tendencia
