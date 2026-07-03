"""
score_engine.py
Cálculo de indicadores técnicos.
"""
import pandas as pd

def calcular_indicadores_tecnicos(df):
    """Calcula IFR (RSI) período 14 e retorna o dataframe com a nova coluna."""
    if 'Close' not in df.columns:
        return df
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    df['IFR'] = 100 - (100 / (1 + rs))
    return df

def calcular_score_tecnico(df):
    """Retorna um score numérico baseado no IFR atual."""
    if 'IFR' not in df.columns or df['IFR'].isnull().all():
        return 0
    
    ifr_atual = df['IFR'].iloc[-1]
    # Exemplo: IFR abaixo de 30 é sinal de sobrevenda (score 5)
    if ifr_atual < 30:
        return 5
    return 0
