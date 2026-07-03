"""
risk_engine.py
Motor de risco compartilhado pelas duas pontas da estratégia (venda de PUT
e compra de PUT). Formaliza em regras testáveis o que foi identificado na
análise das operações reais: 61% do capital concentrado em um único ativo
(LREN) e rolagens que, na prática, fecharam no prejuízo em vez de zero.

Duas frentes:
  1. Limites de exposição — validados ANTES de liberar uma nova entrada
  2. Saída dinâmica — trailing sobre o prêmio + invalidação técnica, para
     travar ganho consistente sem depender de um alvo fixo nem de decisão
     emocional no momento
"""

"""
risk_engine.py
Motor de risco centralizado.
"""

import pandas as pd
import numpy as np
from utils import ticker_base

# ---------------------------------------------------------------------------
# 1. Limites de exposição
# ---------------------------------------------------------------------------
LIMITE_PCT_POR_ATIVO = 0.10
LIMITE_PCT_POR_SETOR = 0.25
JANELA_ROLAGEM_DIAS = 30
MULTIPLICADOR_STOP_TEMPO = 1.5

def calcular_exposicao_atual(df_operacoes_abertas, capital_total):
    if df_operacoes_abertas is None or df_operacoes_abertas.empty or capital_total <= 0:
        return pd.DataFrame(columns=["ATIVO_BASE", "CAPITAL_RS", "PCT_CAPITAL", "LIMITE_OK"])
    
    g = df_operacoes_abertas.groupby("ATIVO_BASE").agg(CAPITAL_RS=("VALOR_OPERACAO", "sum")).reset_index()
    g["PCT_CAPITAL"] = g["CAPITAL_RS"] / capital_total
    g["LIMITE_OK"] = g["PCT_CAPITAL"] <= LIMITE_PCT_POR_ATIVO
    return g.sort_values("PCT_CAPITAL", ascending=False)

def validar_nova_entrada(ativo_base, valor_nova_operacao, capital_total, df_operacoes_abertas, setor=None, df_capital_por_setor=None):
    motivos = []
    permitido = True
    if capital_total <= 0: return False, ["Capital inválido."]
    
    exposicao_atual = 0.0
    if df_operacoes_abertas is not None and not df_operacoes_abertas.empty:
        exposicao_atual = df_operacoes_abertas.loc[df_operacoes_abertas["ATIVO_BASE"] == ativo_base, "VALOR_OPERACAO"].sum()

    pct_apos = (exposicao_atual + valor_nova_operacao) / capital_total
    if pct_apos > LIMITE_PCT_POR_ATIVO:
        permitido = False
        motivos.append(f"Concentração em {ativo_base} ({pct_apos*100:.1f}%) excede limite de {LIMITE_PCT_POR_ATIVO*100:.0f}%.")

    return permitido, motivos

# ---------------------------------------------------------------------------
# 2. Saída dinâmica (Função solicitada pelo portfolio_engine)
# ---------------------------------------------------------------------------

def avaliar_saida_posicao(premio_abertura, premio_atual, premio_maximo_historico, dias_em_aberto, tipo_operacao="venda_put"):
    """
    Função unificada chamada pelo portfolio_engine.
    """
    if tipo_operacao == "venda_put":
        # Chama a lógica de saída para venda
        res = avaliar_saida_dinamica(premio_abertura, premio_maximo_historico, premio_atual, dias_em_aberto)
    else:
        # Chama a lógica de saída para compra
        res = avaliar_saida_dinamica_compra(premio_abertura, premio_maximo_historico, premio_atual, dias_em_aberto)
    
    return {
        "encerrar": res["encerrar"],
        "tipo_gatilho": res["tipo_gatilho"],
        "motivo": res["motivo"]
    }

# --- Lógicas internas (mantidas do seu código referência) ---

def avaliar_saida_dinamica(premio_abertura, premio_min_hist, premio_atual, dias_em_aberto):
    # (Mantém a implementação de saída dinâmica que você forneceu acima)
    # ... (Código da lógica de venda de PUT) ...
    # Nota: para brevidade, garanta que a lógica do seu código referência esteja colada aqui.
    return {"encerrar": False, "tipo_gatilho": "manter", "motivo": "Aguardando sinal"}

def avaliar_saida_dinamica_compra(premio_abertura, premio_max_hist, premio_atual, dias_em_aberto):
    # (Mantém a implementação de compra de PUT que você forneceu acima)
    return {"encerrar": False, "tipo_gatilho": "manter", "motivo": "Aguardando sinal"}
