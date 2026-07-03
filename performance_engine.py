"""
performance_engine.py
Analisa o histórico de operações concretizadas e devolve as métricas que
realmente importam para avaliar a estratégia — não só win rate, mas
expectância matemática, concentração por ativo e resultado real dos ciclos
de rolagem (que a análise manual do CSV mostrou fechar no prejuízo, não em
zero como presumido inicialmente).

Espera um DataFrame com pelo menos as colunas:
  CODIGO, DATA_VENDA, STATUS (RECOMPRA/ROLAGEM), LUCPREJ (R$), VALOR_OP (R$),
  DIAS (dias em aberto)
"""

import pandas as pd
import numpy as np
from utils import ticker_base


def calcular_metricas_gerais(df):
    """Métricas agregadas: win rate, expectância, drawdown, tempo médio."""
    d = df.copy()
    d = d[d["LUCPREJ"].notna()]

    total = len(d)
    if total == 0:
        return None

    wins = d[d["LUCPREJ"] > 0]
    losses = d[d["LUCPREJ"] < 0]
    zeros = d[d["LUCPREJ"] == 0]

    win_rate = len(wins) / total * 100
    loss_rate = len(losses) / total * 100

    ganho_medio = wins["LUCPREJ"].mean() if len(wins) else 0
    perda_media = losses["LUCPREJ"].mean() if len(losses) else 0

    # Expectância matemática: (%acerto x ganho médio) - (%erro x |perda média|)
    expectancia = (win_rate / 100 * ganho_medio) + (loss_rate / 100 * perda_media)

    lucro_total = d["LUCPREJ"].sum()
    capital_alocado = d["VALOR_OP"].sum() if "VALOR_OP" in d.columns else None
    retorno_pct = (lucro_total / capital_alocado * 100) if capital_alocado else None

    # Drawdown simples sobre a sequência cronológica de resultados
    if "DATA_VENDA" in d.columns:
        d_sorted = d.sort_values("DATA_VENDA")
    else:
        d_sorted = d
    curva = d_sorted["LUCPREJ"].cumsum()
    pico = curva.cummax()
    drawdown = curva - pico
    max_drawdown = drawdown.min()

    tempo_medio = d["DIAS"].mean() if "DIAS" in d.columns else None

    return {
        "total_operacoes": total,
        "win_rate_pct": round(win_rate, 1),
        "loss_rate_pct": round(loss_rate, 1),
        "zero_rate_pct": round(len(zeros) / total * 100, 1),
        "ganho_medio_rs": round(ganho_medio, 2),
        "perda_media_rs": round(perda_media, 2),
        "expectancia_rs": round(expectancia, 2),
        "lucro_total_rs": round(lucro_total, 2),
        "capital_alocado_rs": round(capital_alocado, 2) if capital_alocado else None,
        "retorno_pct": round(retorno_pct, 2) if retorno_pct is not None else None,
        "max_drawdown_rs": round(max_drawdown, 2),
        "tempo_medio_dias": round(tempo_medio, 1) if tempo_medio is not None else None,
    }


def calcular_concentracao_por_ativo(df):
    """
    Reproduz a análise que revelou 61% do capital em um único ativo (LREN).
    Retorna DataFrame ordenado por % do capital total, com alerta quando
    ultrapassa o limite de concentração definido em risk_engine.
    """
    from risk_engine import LIMITE_PCT_POR_ATIVO

    d = df.copy()
    d["ATIVO_BASE"] = d["CODIGO"].apply(ticker_base)

    capital_total = d["VALOR_OP"].sum()
    if capital_total == 0:
        return pd.DataFrame()

    g = d.groupby("ATIVO_BASE").agg(
        N_OPERACOES=("CODIGO", "count"),
        CAPITAL_RS=("VALOR_OP", "sum"),
        LUCRO_RS=("LUCPREJ", "sum"),
    ).reset_index()

    g["PCT_CAPITAL"] = (g["CAPITAL_RS"] / capital_total * 100).round(1)
    g["PCT_LUCRO_TOTAL"] = (g["LUCRO_RS"] / d["LUCPREJ"].sum() * 100).round(1) if d["LUCPREJ"].sum() != 0 else 0
    g["ACIMA_DO_LIMITE"] = g["PCT_CAPITAL"] > (LIMITE_PCT_POR_ATIVO * 100)

    return g.sort_values("PCT_CAPITAL", ascending=False)


def analisar_ciclos_rolagem(df):
    """
    Isola as operações marcadas como ROLAGEM e mostra o resultado real do
    ciclo — a análise do CSV mostrou que a maioria fecha no prejuízo, não em
    zero como presumido. Essencial para calibrar corretamente a expectância.
    """
    d = df[df["STATUS"] == "ROLAGEM"].copy()
    if d.empty:
        return {
            "n_rolagens": 0,
            "resultado_total_rs": 0,
            "n_prejuizo": 0,
            "n_zero_ou_positivo": 0,
            "detalhe": pd.DataFrame(),
        }

    return {
        "n_rolagens": len(d),
        "resultado_total_rs": round(d["LUCPREJ"].sum(), 2),
        "n_prejuizo": int((d["LUCPREJ"] < 0).sum()),
        "n_zero_ou_positivo": int((d["LUCPREJ"] >= 0).sum()),
        "detalhe": d[["CODIGO", "DATA_VENDA", "LUCPREJ", "DIAS"]].sort_values("LUCPREJ"),
    }


def curva_de_capital(df):
    """Série cronológica cumulativa de resultado — para o gráfico de evolução."""
    d = df.copy()
    d = d[d["LUCPREJ"].notna()]
    if "DATA_VENDA" in d.columns:
        d = d.sort_values("DATA_VENDA")
    d["RESULTADO_ACUMULADO"] = d["LUCPREJ"].cumsum()
    return d[["DATA_VENDA", "CODIGO", "LUCPREJ", "RESULTADO_ACUMULADO"]] if "DATA_VENDA" in d.columns else d
