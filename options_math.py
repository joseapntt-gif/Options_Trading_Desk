"""
options_math.py
Cálculo de delta via Black-Scholes para permitir filtrar opções pelo critério
real da estratégia (delta 0,15-0,20), em vez de um desconto percentual fixo
sobre o preço do ativo.
"""

import math
from scipy.stats import norm


def _d1(s, k, t, r, sigma):
    return (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))


def delta_put(preco_ativo, strike, dias_uteis, taxa_livre_risco, vol_implicita):
    """
    Delta de uma opção de venda (PUT) europeia via Black-Scholes.
    Retorna valor negativo (convenção padrão: delta de put é entre -1 e 0).

    preco_ativo: preço à vista do ativo-objeto
    strike: strike da opção
    dias_uteis: dias úteis até o vencimento
    taxa_livre_risco: taxa anual (ex: 0.11 para 11% a.a. — usar Selic/CDI vigente)
    vol_implicita: volatilidade implícita anualizada (ex: 0.35 para 35%)
    """
    if preco_ativo <= 0 or strike <= 0 or dias_uteis <= 0 or vol_implicita <= 0:
        return None
    t = dias_uteis / 252.0
    d1 = _d1(preco_ativo, strike, t, taxa_livre_risco, vol_implicita)
    return norm.cdf(d1) - 1  # delta da put


def delta_call(preco_ativo, strike, dias_uteis, taxa_livre_risco, vol_implicita):
    if preco_ativo <= 0 or strike <= 0 or dias_uteis <= 0 or vol_implicita <= 0:
        return None
    t = dias_uteis / 252.0
    d1 = _d1(preco_ativo, strike, t, taxa_livre_risco, vol_implicita)
    return norm.cdf(d1)


def strike_para_delta_alvo(preco_ativo, dias_uteis, vol_implicita, delta_alvo,
                            taxa_livre_risco=0.11, tipo="put"):
    """
    Busca (por bisseção simples) o strike que produz o delta alvo informado.
    Útil para sugerir automaticamente o strike de venda de put dentro da
    faixa de delta 0,15-0,20 da estratégia, dado o preço e a vol implícita
    observados no momento.
    """
    if preco_ativo <= 0 or dias_uteis <= 0 or vol_implicita <= 0:
        return None

    lo, hi = preco_ativo * 0.5, preco_ativo * 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if tipo == "put":
            d = delta_put(preco_ativo, mid, dias_uteis, taxa_livre_risco, vol_implicita)
            # delta da put fica mais negativo (mais "in the money") conforme strike sobe
            if d is None:
                return None
            if abs(d) > abs(delta_alvo):
                hi = mid
            else:
                lo = mid
        else:
            d = delta_call(preco_ativo, mid, dias_uteis, taxa_livre_risco, vol_implicita)
            if d is None:
                return None
            if d > delta_alvo:
                lo = mid
            else:
                hi = mid
    return round((lo + hi) / 2, 2)
