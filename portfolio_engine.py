"""
portfolio_engine.py
Gerenciamento de posições abertas (Carteira).
Responsável por avaliar posições, decidir sobre encerramento (trailing stop)
e projetar a exposição da carteira.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from risk_engine import LIMITE_PCT_POR_ATIVO

def linha_vazia():
    """Retorna um dicionário com a estrutura de colunas para uma nova linha na UI."""
    return {
        "CODIGO": "", "TIPO_OPERACAO": "venda_put", "DATA_ABERTURA": datetime.now(),
        "VENCIMENTO": datetime.now(), "PREMIO_ABERTURA": 0.0, 
        "PREMIO_EXTREMO_HIST": 0.0, "PREMIO_ATUAL": 0.0, 
        "QTDE": 0, "STRIKE": 0.0, "SUPORTE_REFERENCIA": 0.0, 
        "VALOR_OPERACAO": 0.0
    }

def avaliar_carteira(df_carteira, preco_atual_por_ativo):
    """
    Avalia cada posição aberta.
    Retorna o dataframe original com colunas extras: DECISAO, MOTIVO, DIAS_EM_ABERTO.
    """
    df = df_carteira.copy()
    
    # Cálculos temporais
    hoje = datetime.now()
    df["DATA_ABERTURA"] = pd.to_datetime(df["DATA_ABERTURA"])
    df["VENCIMENTO"] = pd.to_datetime(df["VENCIMENTO"])
    df["DIAS_EM_ABERTO"] = (hoje - df["DATA_ABERTURA"]).dt.days
    df["DIAS_ATE_VENCIMENTO"] = (df["VENCIMENTO"] - hoje).dt.days

    resultados = []
    
    for _, row in df.iterrows():
        ativo = str(row["CODIGO"]).split()[0] # Assume ticker principal
        preco_atual = preco_atual_por_ativo.get(ativo, 0.0)
        
        # Lógica de Decisão (Simplificada para a estrutura atual)
        # Em uma implementação futura, aqui chamamos o risk_engine.avaliar_saida()
        if row["PREMIO_ATUAL"] <= 0.05 * row["PREMIO_ABERTURA"]:
            decisao = "Encerrar agora"
            motivo = "Prêmio derreteu (encerrar ganho)"
        elif row["PREMIO_ATUAL"] > 2.0 * row["PREMIO_ABERTURA"]:
            decisao = "Revisar manualmente"
            motivo = "Aumento excessivo do prêmio (risco)"
        else:
            decisao = "Manter"
            motivo = "Dentro da normalidade"
            
        resultados.append({"DECISAO": decisao, "MOTIVO": motivo})
    
    df_res = pd.concat([df, pd.DataFrame(resultados)], axis=1)
    return df_res

def resumo_carteira(df_avaliada):
    """Conta quantas posições existem em cada status para o dashboard."""
    return {
        "total": len(df_avaliada),
        "encerrar_agora": len(df_avaliada[df_avaliada["DECISAO"] == "Encerrar agora"]),
        "revisar": len(df_avaliada[df_avaliada["DECISAO"] == "Revisar manualmente"]),
        "vencimento_proximo": len(df_avaliada[df_avaliada["DIAS_ATE_VENCIMENTO"] < 5]),
        "manter": len(df_avaliada[df_avaliada["DECISAO"] == "Manter"]),
    }

def exposicao_carteira_aberta(df_carteira, capital_total):
    """Calcula a concentração por ativo e verifica se está dentro do limite."""
    df = df_carteira.copy()
    # Agrupa por ativo
    exposicao = df.groupby("CODIGO")["VALOR_OPERACAO"].sum().reset_index()
    exposicao["PCT_CAPITAL"] = exposicao["VALOR_OPERACAO"] / capital_total
    exposicao["LIMITE_OK"] = exposicao["PCT_CAPITAL"] <= LIMITE_PCT_POR_ATIVO
    
    return exposicao