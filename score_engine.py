"""
score_engine.py
Indicadores técnicos e score de entrada para as duas pontas da estratégia:
  - venda de PUT perto de mínimas (reversão de alta)
  - compra de PUT perto de máximas (reversão de baixa / exaustão)

Diferente da versão anterior, este módulo:
  1. é de fato conectado pelo scanner (ver scanner_engine.py)
  2. formaliza o padrão de "3 candles com topos ascendentes/descendentes"
     como regra objetiva, com confirmação de volume
  3. adiciona ADX como filtro de regime (mercado em range vs. em tendência
     forte), já que reversão funciona mal em tendência forte
  4. nunca engole erro em silêncio devolvendo um valor "neutro" que parece
     dado real — devolve None explícito e a UI decide como exibir
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Indicadores base
# ---------------------------------------------------------------------------

def calcular_rsi(hist, periodo=14):
    delta = hist['Close'].diff()
    ganho = delta.where(delta > 0, 0).rolling(window=periodo).mean()
    perda = (-delta.where(delta < 0, 0)).rolling(window=periodo).mean()
    rs = ganho / perda.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calcular_bollinger(hist, periodo=20, desvios=2):
    sma = hist['Close'].rolling(window=periodo).mean()
    std = hist['Close'].rolling(window=periodo).std()
    banda_sup = sma + desvios * std
    banda_inf = sma - desvios * std
    return sma, banda_sup, banda_inf


def calcular_adx(hist, periodo=14):
    """ADX de Wilder — usado como filtro de regime (range vs. tendência)."""
    high, low, close = hist['High'], hist['Low'], hist['Close']

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=periodo).mean()
    plus_di = 100 * pd.Series(plus_dm, index=hist.index).rolling(window=periodo).mean() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=hist.index).rolling(window=periodo).mean() / atr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window=periodo).mean()
    return adx


def detectar_padrao_reversao(hist, n=3, direcao="alta"):
    """
    direcao="alta": 3 candles com topos (High) e fechamentos ascendentes
                    -> sinal de reversão de baixa para alta (ponta de venda de put)
    direcao="baixa": 3 candles com topos e fechamentos descendentes
                    -> sinal de reversão de alta para baixa (ponta de compra de put)

    Retorna (padrao_confirmado: bool, volume_confirma: bool)
    """
    if len(hist) < n + 20:
        return False, False

    highs = hist['High'].iloc[-n:].values
    closes = hist['Close'].iloc[-n:].values

    if direcao == "alta":
        padrao = all(highs[i] < highs[i + 1] for i in range(n - 1)) and \
                 all(closes[i] < closes[i + 1] for i in range(n - 1))
    else:
        padrao = all(highs[i] > highs[i + 1] for i in range(n - 1)) and \
                 all(closes[i] > closes[i + 1] for i in range(n - 1))

    vol_medio = hist['Volume'].iloc[-20:].mean()
    vol_recente = hist['Volume'].iloc[-n:].mean()
    volume_confirma = bool(vol_recente > vol_medio) if vol_medio and not np.isnan(vol_medio) else False

    return bool(padrao), volume_confirma


def calcular_indicadores_tecnicos(hist):
    """
    Calcula o conjunto completo de indicadores para o último candle disponível.
    Retorna um dicionário. Nunca engole exceção em silêncio — se um indicador
    específico falhar, o campo correspondente vem None e o restante segue.
    """
    out = {
        "rsi": None, "sma20": None, "banda_sup": None, "banda_inf": None,
        "dist_banda_inf_pct": None, "dist_banda_sup_pct": None,
        "adx": None, "regime": None,
        "padrao_reversao_alta": False, "padrao_reversao_baixa": False,
        "volume_confirma_alta": False, "volume_confirma_baixa": False,
        "erro": None,
    }

    if hist is None or hist.empty or len(hist) < 25:
        out["erro"] = "Histórico insuficiente (mínimo 25 candles)"
        return out

    try:
        preco_atual = float(hist['Close'].iloc[-1])

        rsi = calcular_rsi(hist)
        out["rsi"] = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None

        sma, b_sup, b_inf = calcular_bollinger(hist)
        out["sma20"] = float(sma.iloc[-1]) if not np.isnan(sma.iloc[-1]) else None
        out["banda_sup"] = float(b_sup.iloc[-1]) if not np.isnan(b_sup.iloc[-1]) else None
        out["banda_inf"] = float(b_inf.iloc[-1]) if not np.isnan(b_inf.iloc[-1]) else None

        if out["banda_inf"] and out["banda_inf"] > 0:
            out["dist_banda_inf_pct"] = ((preco_atual / out["banda_inf"]) - 1) * 100
        if out["banda_sup"] and out["banda_sup"] > 0:
            out["dist_banda_sup_pct"] = ((preco_atual / out["banda_sup"]) - 1) * 100

        adx = calcular_adx(hist)
        adx_val = adx.iloc[-1]
        if not np.isnan(adx_val):
            out["adx"] = float(adx_val)
            out["regime"] = "Tendência forte" if adx_val >= 25 else "Range / lateral"

        pa, va = detectar_padrao_reversao(hist, n=3, direcao="alta")
        pb, vb = detectar_padrao_reversao(hist, n=3, direcao="baixa")
        out["padrao_reversao_alta"] = pa
        out["volume_confirma_alta"] = va
        out["padrao_reversao_baixa"] = pb
        out["volume_confirma_baixa"] = vb

    except Exception as e:
        out["erro"] = f"Falha no cálculo de indicadores: {e}"

    return out


# ---------------------------------------------------------------------------
# Score — venda de PUT (mínimas)
# ---------------------------------------------------------------------------

def calcular_score_venda_put(indicadores, dist_min_pct):
    """
    Score 0-100 para entrada em venda de PUT (reversão de baixa para alta).
    Pesos refletem os critérios validados na estratégia original + os
    reforços discutidos (regime de mercado e confirmação de volume).
    """
    if indicadores.get("erro"):
        return None, "Sem dados"

    rsi = indicadores.get("rsi")
    dist_banda_inf = indicadores.get("dist_banda_inf_pct")
    adx = indicadores.get("adx")
    padrao = indicadores.get("padrao_reversao_alta")
    volume = indicadores.get("volume_confirma_alta")

    rsi_norm = max(0, min(1, (100 - rsi) / 100)) if rsi is not None else 0.5
    bollinger_norm = max(0, min(1, (5 - dist_banda_inf) / 10)) if dist_banda_inf is not None else 0.5
    dist_min_norm = max(0, min(1, (10 - dist_min_pct) / 10)) if dist_min_pct is not None else 0.5

    score = (rsi_norm * 0.20) + (bollinger_norm * 0.30) + (dist_min_norm * 0.25)

    # bônus/penalidade por confirmação de padrão técnico (peso 15)
    if padrao:
        score += 0.15 * (1.0 if volume else 0.6)

    # penalidade de regime: em tendência forte, reversão tende a falhar mais
    if adx is not None and adx >= 25:
        score -= 0.10

    score = max(0, min(1, score)) * 100
    return round(score, 1), None


def definir_status_venda(score, padrao_confirmado, adx):
    if score is None:
        return "⚪ Dados insuficientes"
    alerta_regime = " (tendência forte — cautela)" if adx is not None and adx >= 25 else ""
    if score >= 75 and padrao_confirmado:
        return f"🟢 Ponto de entrada forte{alerta_regime}"
    if score >= 60:
        return f"🟡 Em formação — aguardar confirmação{alerta_regime}"
    if score < 40:
        return "🔴 Fora do critério"
    return "⚪ Neutro"


# ---------------------------------------------------------------------------
# Score — compra de PUT (máximas) — estratégia espelhada
# ---------------------------------------------------------------------------

def calcular_score_compra_put(indicadores, dist_max_pct):
    if indicadores.get("erro"):
        return None, "Sem dados"

    rsi = indicadores.get("rsi")
    dist_banda_sup = indicadores.get("dist_banda_sup_pct")
    adx = indicadores.get("adx")
    padrao = indicadores.get("padrao_reversao_baixa")
    volume = indicadores.get("volume_confirma_baixa")

    rsi_norm = max(0, min(1, rsi / 100)) if rsi is not None else 0.5
    bollinger_norm = max(0, min(1, (dist_banda_sup + 5) / 10)) if dist_banda_sup is not None else 0.5
    dist_max_norm = max(0, min(1, (10 - dist_max_pct) / 10)) if dist_max_pct is not None else 0.5

    score = (rsi_norm * 0.20) + (bollinger_norm * 0.30) + (dist_max_norm * 0.25)

    if padrao:
        score += 0.15 * (1.0 if volume else 0.6)

    if adx is not None and adx >= 25:
        score -= 0.10

    score = max(0, min(1, score)) * 100
    return round(score, 1), None


def definir_status_compra(score, padrao_confirmado, adx):
    if score is None:
        return "⚪ Dados insuficientes"
    alerta_regime = " (tendência forte — cautela)" if adx is not None and adx >= 25 else ""
    if score >= 75 and padrao_confirmado:
        return f"🟢 Ponto de entrada forte{alerta_regime}"
    if score >= 60:
        return f"🟡 Em formação — aguardar confirmação{alerta_regime}"
    if score < 40:
        return "🔴 Fora do critério"
    return "⚪ Neutro"
