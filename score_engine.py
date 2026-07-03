"""
score_engine.py
Cálculo de indicadores técnicos para tomada de decisão.
"""

import pandas as pd
import numpy as np

def calcular_indicadores_tecnicos(df):
    """
    Calcula indicadores técnicos básicos.
    Espera um DataFrame com a coluna 'Close'.
    """
    if 'Close' not in df.columns:
        return df

    # IFR (RSI) - Período 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    df['IFR'] = 100 - (100 / (1 + rs))

    # Bandas de Bollinger
    df['media_movel'] = df['Close'].rolling(window=20).mean()
    df['std_dev'] = df['Close'].rolling(window=20).std()
    df['banda_sup'] = df['media_movel'] + (df['std_dev'] * 2)
    df['banda_inf'] = df['media_movel'] - (df['std_dev'] * 2)

    return df

def calcular_score_tecnico(df):
    """
    Retorna uma pontuação de 0 a 10 baseada na posição do preço
    em relação às bandas e ao IFR.
    """
    score = 0
    preco_atual = df['Close'].iloc[-1]
    
    # Exemplo simples de score: se preço abaixo da banda inferior, score alto
    if preco_atual < df['banda_inf'].iloc[-1]:
        score += 5
    
    # Se IFR abaixo de 30, score alto
    if df['IFR'].iloc[-1] < 30:
        score += 5
        
    return score