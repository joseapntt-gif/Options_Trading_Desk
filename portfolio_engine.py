"""
portfolio_engine.py
Módulo de gestão de posições abertas.
Responsável por integrar a lógica de risco (trailing/alvos) com a carteira.
"""

import pandas as pd
from datetime import datetime
from risk_engine import avaliar_saida_posicao, LIMITE_PCT_POR_ATIVO

def linha_vazia():
    """Retorna um dicionário com a estrutura de colunas para o data_editor."""
    return {
        "CODIGO": "", 
        "TIPO_OPERACAO": "venda_put", 
        "DATA_ABERTURA": datetime.now(),
        "VENCIMENTO": datetime.now(), 
        "PREMIO_ABERTURA": 0.0, 
        "PREMIO_EXTREMO_HIST": 0.0, 
        "PREMIO_ATUAL": 0.0, 
        "QTDE": 0, 
        "STRIKE": 0.0, 
        "SUPORTE_REFERENCIA": 0.0, 
        "VALOR_OPERACAO": 0.0
    }

def avaliar_carteira(df_carteira, preco_atual_por_ativo):
    """
    Processa cada posição e aplica a regra de avaliação do risk_engine.
    """
    df = df_carteira.copy()
    
    # Cálculos temporais básicos
    hoje = datetime.now()
    df["DATA_ABERTURA"] = pd.to_datetime(df["DATA_ABERTURA"])
    df["VENCIMENTO"] = pd.to_datetime(df["VENCIMENTO"])
    df["DIAS_EM_ABERTO"] = (hoje - df["DATA_ABERTURA"]).dt.days
    df["DIAS_ATE_VENCIMENTO"] = (df["VENCIMENTO"] - hoje).dt.days

    decisoes = []
    
    for _, row in df.iterrows():
        # Identifica ticker (assume que a célula CODIGO contém "PETR4")
        ticker = str(row["CODIGO"]).split()[0]
        
        # Chama a inteligência centralizada no risk_engine
        # Passa os dados da posição atual para análise
        resultado = avaliar_saida_posicao(
            premio_abertura=row["PREMIO_ABERTURA"],
            premio_atual=row["PREMIO_ATUAL"],
            premio_maximo_historico=row["PREMIO_EXTREMO_HIST"],
            dias_em_aberto=row["DIAS_EM_ABERTO"]
        )
        
        decisoes.append({
            "DECISAO": "Encerrar agora" if resultado.get("encerrar") else (
                "Revisar manualmente" if resultado.get("tipo_gatilho") == "revisao" else "Manter"
            ),
            "MOTIVO": resultado.get("motivo", "N/A")
        })
    
    # Concatena os resultados de decisão ao dataframe original
    df_decisoes = pd.DataFrame(decisoes)
    df_final = pd.concat([df.reset_index(drop=True), df_decisoes], axis=1)
    
    return df_final

def resumo_carteira(df_avaliada):
    """Conta posições por status para os cartões de métricas da UI."""
    return {
        "total": len(df_avaliada),
        "encerrar_agora": len(df_avaliada[df_avaliada["DECISAO"] == "Encerrar agora"]),
        "revisar": len(df_avaliada[df_avaliada["DECISAO"] == "Revisar manualmente"]),
        "vencimento_proximo": len(df_avaliada[df_avaliada["DIAS_ATE_VENCIMENTO"] < 5]),
        "manter": len(df_avaliada[df_avaliada["DECISAO"] == "Manter"]),
    }

def exposicao_carteira_aberta(df_carteira, capital_total):
    """Calcula concentração por ativo e verifica limites."""
    df = df_carteira.copy()
    if df.empty or capital_total <= 0:
        return pd.DataFrame()
        
    # Agrupa valores por ticker base
    exposicao = df.groupby("CODIGO")["VALOR_OPERACAO"].sum().reset_index()
    exposicao["ATIVO_BASE"] = exposicao["CODIGO"] # Pode-se refinar com ticker_base()
    exposicao["PCT_CAPITAL"] = exposicao["VALOR_OPERACAO"] / capital_total
    exposicao["LIMITE_OK"] = exposicao["PCT_CAPITAL"] <= LIMITE_PCT_POR_ATIVO
    
    return exposicao
