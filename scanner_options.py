"""
scanner_options.py
Busca a cadeia de opções (puts) via yfinance e calcula o delta real de cada
strike via Black-Scholes (options_math.py), permitindo filtrar pela faixa de
delta 0,15-0,20 e vencimento 50-75 dias definida na estratégia — em vez de
um desconto percentual fixo sobre o preço do ativo.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

from options_math import delta_put, gregas_put

TAXA_LIVRE_RISCO_PADRAO = 0.11  # ajustar conforme Selic/CDI vigente


def buscar_puts_venda(ticker_b3, delta_min=0.15, delta_max=0.20,
                       dias_min=50, dias_max=75, taxa_livre_risco=TAXA_LIVRE_RISCO_PADRAO):
    """
    Retorna a cadeia de puts do ativo com delta e dias até o vencimento
    calculados, já filtrada pela faixa de delta e vencimento da estratégia.
    Quando a faixa filtrada vier vazia, retorna a cadeia completa (não filtrada)
    para o usuário decidir manualmente — nunca falha silenciosamente.
    """
    ticker_final = f"{ticker_b3.upper().strip()}.SA"

    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker_final)
            vencimentos = stock.options
            if not vencimentos:
                return pd.DataFrame([{"ERRO": "Nenhum vencimento de opções disponível para este ticker."}])

            preco_atual = stock.history(period="1d")["Close"].iloc[-1]

            linhas = []
            hoje = datetime.now().date()
            for venc in vencimentos:
                venc_date = datetime.strptime(venc, "%Y-%m-%d").date()
                dias = (venc_date - hoje).days
                if dias <= 0:
                    continue

                try:
                    chain = stock.option_chain(venc)
                except Exception:
                    continue

                df_puts = chain.puts
                if df_puts is None or df_puts.empty:
                    continue

                for _, row in df_puts.iterrows():
                    iv = row.get("impliedVolatility")
                    strike = row.get("strike")
                    premio = row.get("lastPrice")
                    if iv is None or iv <= 0 or strike is None:
                        continue

                    gregas = gregas_put(preco_atual, strike, dias, taxa_livre_risco, iv)
                    if gregas.get("erro"):
                        continue

                    linhas.append({
                        "VENCIMENTO": venc,
                        "DIAS": dias,
                        "STRIKE": strike,
                        "PREMIO": premio,
                        "IV": round(iv * 100, 1),
                        "DELTA": round(gregas["delta"], 3),
                        "THETA_DIA": round(gregas["theta_dia"], 4),
                        "VEGA": round(gregas["vega"], 4),
                        "GAMMA": round(gregas["gamma"], 4),
                        "PRECO_ATIVO": round(float(preco_atual), 2),
                    })

            if not linhas:
                return pd.DataFrame([{"ERRO": "Cadeia de opções obtida, mas sem dados de IV/strike utilizáveis."}])

            df_final = pd.DataFrame(linhas)

            df_filtrado = df_final[
                (df_final["DELTA"].abs() >= delta_min) &
                (df_final["DELTA"].abs() <= delta_max) &
                (df_final["DIAS"] >= dias_min) &
                (df_final["DIAS"] <= dias_max)
            ].sort_values("DIAS")

            if df_filtrado.empty:
                df_final.attrs["aviso"] = (
                    f"Nenhuma opção dentro do critério (delta {delta_min}-{delta_max}, "
                    f"{dias_min}-{dias_max} dias). Exibindo cadeia completa para revisão manual."
                )
                return df_final.sort_values(["DIAS", "STRIKE"])

            return df_filtrado

        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            return pd.DataFrame([{"ERRO": f"Erro crítico: {str(e)}"}])

    return pd.DataFrame([{"ERRO": "Falha persistente de acesso ao Yahoo Finance"}])
