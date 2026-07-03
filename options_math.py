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


def gregas_put(preco_ativo, strike, dias_uteis, taxa_livre_risco, vol_implicita):
    """
    Conjunto completo de gregas para PUT europeia via Black-Scholes: delta,
    theta (por dia corrido), vega (por 1 p.p. de IV) e gamma. Retorna None
    em todos os campos se a entrada for inválida — nunca um valor neutro
    que possa ser confundido com um cálculo real.
    """
    saida = {"delta": None, "theta_dia": None, "vega": None, "gamma": None, "erro": None}

    if None in (preco_ativo, strike, dias_uteis, vol_implicita):
        saida["erro"] = "Parâmetro de entrada ausente (preço, strike, dias ou IV)."
        return saida
    if preco_ativo <= 0 or strike <= 0 or dias_uteis <= 0 or vol_implicita <= 0:
        saida["erro"] = "Parâmetro de entrada fora de faixa válida (deve ser > 0)."
        return saida

    try:
        s, k, t, r, sigma = preco_ativo, strike, dias_uteis / 252.0, taxa_livre_risco, vol_implicita
        d1 = _d1(s, k, t, r, sigma)
        d2 = d1 - sigma * math.sqrt(t)

        delta = norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (s * sigma * math.sqrt(t))
        vega = s * norm.pdf(d1) * math.sqrt(t) / 100

        theta_anual = (
            -(s * norm.pdf(d1) * sigma) / (2 * math.sqrt(t))
            + r * k * math.exp(-r * t) * norm.cdf(-d2)
        )
        saida.update(delta=delta, theta_dia=theta_anual / 365, vega=vega, gamma=gamma)
        return saida
    except Exception as e:
        saida["erro"] = f"Falha no cálculo de gregas: {e}"
        return saida


def implied_vol_put(preco_mercado, preco_ativo, strike, dias_uteis, taxa_livre_risco,
                     chute_inicial=0.35, tolerancia=1e-4, max_iter=100):
    """
    Volatilidade implícita de uma PUT via bisseção sobre o preço Black-Scholes.
    Necessário quando a fonte de dados (ex: MetaTrader5) fornece o prêmio de
    mercado mas não a IV pronta — o MT5 expõe strike/vencimento estruturados,
    mas não IV nem gregas via API Python.

    Retorna None se não convergir ou se os parâmetros forem inválidos —
    nunca um valor "chutado" que pareça um resultado real.
    """
    if None in (preco_mercado, preco_ativo, strike, dias_uteis) or preco_mercado <= 0:
        return None
    if preco_ativo <= 0 or strike <= 0 or dias_uteis <= 0:
        return None

    t = dias_uteis / 252.0
    r = taxa_livre_risco

    def preco_bs_put(sigma):
        d1 = _d1(preco_ativo, strike, t, r, sigma)
        d2 = d1 - sigma * math.sqrt(t)
        return strike * math.exp(-r * t) * norm.cdf(-d2) - preco_ativo * norm.cdf(-d1)

    lo, hi = 0.001, 5.0  # 0,1% a 500% a.a. — cobre qualquer caso plausível
    preco_lo, preco_hi = preco_bs_put(lo), preco_bs_put(hi)

    if preco_mercado < preco_lo or preco_mercado > preco_hi:
        return None  # prêmio de mercado fora da faixa modelável — não força um resultado

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        preco_mid = preco_bs_put(mid)
        if abs(preco_mid - preco_mercado) < tolerancia:
            return round(mid, 4)
        if preco_mid > preco_mercado:
            hi = mid
        else:
            lo = mid

    return round((lo + hi) / 2, 4)


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
