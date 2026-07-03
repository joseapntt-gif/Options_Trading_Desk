"""
market_data.py
Fonte única de verdade para preço, histórico e níveis técnicos (mín/máx 6M).

Correção de arquitetura em relação à versão anterior: preço/mínima/máxima
vinham da planilha do Google Sheets, enquanto os indicadores técnicos
(RSI, ADX, Bollinger) eram calculados a partir de um histórico buscado
separadamente no yfinance. Isso permitia inconsistência — preço da planilha
podendo divergir do preço usado para calcular os indicadores no mesmo
instante, para o mesmo ativo.

Este módulo resolve isso: o yfinance passa a ser a ÚNICA fonte de preço,
mínima, máxima e indicadores. A planilha do Google passa a ser usada
apenas para os dados que o yfinance não tem: a lista de tickers acompanhados,
o capital alocado por operação (VALOR) e a taxa livre de risco (SELIC).

Princípio seguido em todo o módulo: nenhuma função aqui retorna um valor
"neutro" ou "estimado" quando o dado real falha — ou retorna o dado real
validado, ou retorna um erro explícito que a camada de UI precisa exibir.
Isso evita que uma falha silenciosa produza uma análise que parece confiável
mas não é.
"""

import time
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Janela mínima de candles exigida para considerar o histórico utilizável
# (score_engine.py exige pelo menos 25 para todos os indicadores)
MIN_CANDLES_NECESSARIOS = 25

# Tolerância de "idade" do dado antes de ser considerado potencialmente
# obsoleto (ex: mercado fechado há muito tempo, feed travado)
TOLERANCIA_DEFASAGEM_DIAS = 5


class DadoMercado:
    """
    Envelope de resultado para qualquer busca de dado de mercado.
    Nunca deixa a UI adivinhar se um valor é real ou um fallback —
    o campo `ok` é explícito e `motivo` descreve a falha quando houver.
    """
    def __init__(self, ok, valor=None, motivo=None, defasado=False):
        self.ok = ok
        self.valor = valor
        self.motivo = motivo
        self.defasado = defasado

    def __repr__(self):
        return f"DadoMercado(ok={self.ok}, valor={self.valor}, motivo={self.motivo})"


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_historico_raw(ticker_b3, periodo="6mo", _tentativa_cache_buster=0):
    """
    Busca crua no yfinance, cacheada por 5 minutos. `_tentativa_cache_buster`
    permite forçar um novo fetch (botão de atualização manual) sem esperar
    o TTL expirar — basta incrementar o valor para invalidar o cache daquela
    chamada específica.
    """
    ticker_final = f"{ticker_b3.upper().strip()}.SA"
    ultimo_erro = None
    for tentativa in range(3):
        try:
            hist = yf.Ticker(ticker_final).history(period=periodo)
            if hist is not None and not hist.empty:
                return hist, None
            ultimo_erro = "Histórico retornado vazio pelo yfinance."
        except Exception as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
        time.sleep(0.6)
    return None, ultimo_erro


def obter_historico(ticker_b3, periodo="6mo", forcar_atualizacao=False):
    """
    Retorna DadoMercado com o histórico OHLCV validado.
    Validações aplicadas (nenhuma corrige o dado — só sinaliza):
      - histórico não vazio
      - quantidade mínima de candles para os indicadores funcionarem
      - defasagem do último candle frente à data atual (mercado pode estar
        fechado por feriado — isso é normal e não devia gerar 'erro forte',
        apenas um aviso quando muito além do esperado)
    """
    cache_buster = int(time.time() // 300) if not forcar_atualizacao else int(time.time())
    hist, erro = _fetch_historico_raw(ticker_b3, periodo, cache_buster)

    if hist is None:
        return DadoMercado(ok=False, motivo=erro or "Falha desconhecida ao buscar histórico.")

    if len(hist) < MIN_CANDLES_NECESSARIOS:
        return DadoMercado(
            ok=False,
            motivo=f"Histórico insuficiente: {len(hist)} candles (mínimo necessário: {MIN_CANDLES_NECESSARIOS})."
        )

    ultimo_candle = hist.index[-1]
    if hasattr(ultimo_candle, "tz_localize") and ultimo_candle.tzinfo is not None:
        ultimo_candle = ultimo_candle.tz_localize(None)
    dias_defasagem = (pd.Timestamp.now() - ultimo_candle).days
    defasado = dias_defasagem > TOLERANCIA_DEFASAGEM_DIAS

    return DadoMercado(ok=True, valor=hist, defasado=defasado,
                        motivo=f"Último candle há {dias_defasagem} dia(s)." if defasado else None)


def obter_preco_e_niveis(ticker_b3, janela_meses="6mo", forcar_atualizacao=False):
    """
    Retorna dict com preco_atual, min_periodo, max_periodo — todos derivados
    do MESMO histórico (elimina a inconsistência preço-planilha vs
    indicador-yfinance da versão anterior).
    """
    dado_hist = obter_historico(ticker_b3, janela_meses, forcar_atualizacao)

    if not dado_hist.ok:
        return {
            "ok": False, "motivo": dado_hist.motivo,
            "preco_atual": None, "min_periodo": None, "max_periodo": None,
            "defasado": False, "hist": None,
        }

    hist = dado_hist.valor
    try:
        preco_atual = float(hist["Close"].iloc[-1])
        min_periodo = float(hist["Low"].min())
        max_periodo = float(hist["High"].max())
    except Exception as e:
        return {
            "ok": False, "motivo": f"Falha ao extrair preço/níveis do histórico: {e}",
            "preco_atual": None, "min_periodo": None, "max_periodo": None,
            "defasado": False, "hist": None,
        }

    if preco_atual <= 0:
        return {
            "ok": False, "motivo": "Preço atual retornado é zero ou negativo — dado inválido.",
            "preco_atual": None, "min_periodo": None, "max_periodo": None,
            "defasado": False, "hist": None,
        }

    return {
        "ok": True, "motivo": dado_hist.motivo, "defasado": dado_hist.defasado,
        "preco_atual": preco_atual, "min_periodo": min_periodo, "max_periodo": max_periodo,
        "hist": hist,
    }


# ---------------------------------------------------------------------------
# Taxa livre de risco (Selic) — planilha é a fonte, com fallback explícito
# ---------------------------------------------------------------------------

SELIC_FALLBACK = 0.1075  # usado SOMENTE se a planilha não tiver o valor; deve ser mantido atualizado manualmente


def resolver_taxa_livre_risco(valor_planilha):
    """
    valor_planilha: valor já normalizado (float) lido da coluna SELIC da
    planilha, ou None se ausente/inválido.
    Retorna (taxa: float, usando_fallback: bool) — a UI deve exibir um aviso
    sempre que usando_fallback for True, para nunca esconder que o número
    não veio da fonte real.
    """
    if valor_planilha is not None and 0 < valor_planilha < 1:
        return valor_planilha, False
    if valor_planilha is not None and valor_planilha >= 1:
        # valor provavelmente veio em formato "10,75" em vez de "0,1075"
        return valor_planilha / 100, False
    return SELIC_FALLBACK, True
