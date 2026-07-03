"""
quant_engine.py
Analisa se o ativo selecionado está de fato num bom ponto de montagem de
trava de alta, usando market_data.py como fonte única de preço/histórico
(mesma fonte usada pelo scanner_engine — elimina divergência entre módulos).

Lógica de sugestão de strikes:
  - strike de compra: próximo ao preço atual (ligeiramente OTM), ponto de
    entrada da trava
  - strike de venda: no nível de resistência recente (máxima móvel dos
    últimos N candles), não um percentual fixo — reflete onde o mercado
    historicamente teve dificuldade de romper
  - túnel = diferença entre os strikes, mostrado em R$ e em % do preço
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from utils import normalizar_valor
from market_data import obter_preco_e_niveis, resolver_taxa_livre_risco
from score_engine import calcular_indicadores_tecnicos

SHEET_ID = "1oQmaZiF0f7jc5oSwTDy16QHTHvgU11Vx9GE4eXMauM0"


def buscar_selic_planilha():
    """Lê a coluna SELIC da planilha (primeira linha, é um valor único da mesa)."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        registros = sheet.get_all_records()
        if not registros:
            return None
        linha0 = {str(k).upper().strip(): v for k, v in registros[0].items()}
        if "SELIC" not in linha0:
            return None
        return normalizar_valor(linha0["SELIC"])
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


def analisar_ponto_trava(ticker_symbol, arredondamento=0.05, forcar_atualizacao=False):
    """
    Análise completa do ponto de montagem de trava de alta para o ativo.
    Retorna um dicionário com preço, indicadores, se está ou não no ponto
    de entrada, e os strikes/túnel sugeridos — sempre com a justificativa.
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
        "taxa_livre_risco": None,
        "selic_fallback": None,
        "defasado": False,
        "erro": None,
    }

    dados = obter_preco_e_niveis(ticker_symbol, forcar_atualizacao=forcar_atualizacao)
    if not dados["ok"]:
        resultado["erro"] = dados["motivo"]
        return resultado

    resultado["defasado"] = dados["defasado"]
    preco_atual = dados["preco_atual"]
    hist = dados["hist"]
    resultado["preco_atual"] = preco_atual

    indicadores = calcular_indicadores_tecnicos(hist)
    if indicadores.get("erro"):
        resultado["erro"] = indicadores["erro"]
        return resultado

    selic_planilha = buscar_selic_planilha()
    taxa, usando_fallback = resolver_taxa_livre_risco(selic_planilha)
    resultado["taxa_livre_risco"] = taxa
    resultado["selic_fallback"] = usando_fallback

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
        motivos.append("Tendência forte já em curso — espaço de alta remanescente pode ser menor")
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
    """Compatibilidade com chamadas antigas — delega para a análise completa."""
    r = analisar_ponto_trava(ticker_symbol)
    if r["erro"]:
        raise Exception(r["erro"])
    tendencia = "Alta (critério atendido)" if r["ponto_de_entrada"] else "Aguardar — critério não atendido"
    return r["preco_atual"], r["strike_compra_sugerido"], r["strike_venda_sugerido"], tendencia
