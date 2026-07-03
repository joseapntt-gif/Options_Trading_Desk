"""
scanner_engine.py
Motor de scanner integrado com indicadores técnicos.
"""
import pandas as pd
import streamlit as st
from score_engine import calcular_indicadores_tecnicos, calcular_score_tecnico

def escanear_ativos_mesa():
    """
    Função principal que processa os ativos da mesa.
    """
    # Exemplo de estrutura de dados simulada para o scanner
    # Substitua pela lógica real de busca da sua planilha
    data = {
        'ATIVO': ['PETR4', 'VALE3', 'ITUB4'],
        'PRECO': [35.0, 60.0, 30.0],
        'MIN_6M': [32.0, 55.0, 28.0]
    }
    df = pd.DataFrame(data)
    
    # Cálculo de métricas
    df['DIST_MIN_PERC'] = ((df['PRECO'] - df['MIN_6M']) / df['MIN_6M']) * 100
    
    # Aplicação de indicadores técnicos (simulação de histórico para cada linha)
    # Em produção, você aplicaria isso sobre o histórico obtido via yfinance
    df['IFR'] = 50.0  # Placeholder para o valor real calculado pelo score_engine
    
    return df
