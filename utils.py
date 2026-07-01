"""
utils.py
Funções utilitárias compartilhadas — normalização de valores numéricos vindos
de planilha (formato brasileiro: R$, %, milhar com ponto, decimal com vírgula).

IMPORTANTE: a versão anterior deste projeto tinha uma heurística perigosa
(`if num > 1000: num/100`) que corrigia "silenciosamente" qualquer preço acima
de R$ 100, corrompendo ativos legítimos que passam desse valor. Esta versão
faz o parse correto do formato BR e, quando o valor parece implausível, marca
um alerta em vez de adulterar o número sem avisar.
"""

import math


def normalizar_valor(val):
    """
    Converte string no formato brasileiro (R$ 1.234,56 / 12,5% / 1234.56)
    para float. Não aplica nenhuma divisão heurística por magnitude —
    isso corrompia preços válidos acima de R$ 100.

    Retorna None se não for possível converter (em vez de 0.0 silencioso,
    que se parece com um dado real).
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)

    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "-"):
        return None

    s = s.replace("R$", "").replace("%", "").strip()

    # Formato BR: milhar com ponto, decimal com vírgula -> "1.234,56"
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # só vírgula: é decimal -> "12,5"
        s = s.replace(",", ".")
    # só ponto ou nenhum separador: assume já é formato float padrão

    try:
        return float(s)
    except ValueError:
        return None


def preco_plausivel(preco, referencia=None, tolerancia=0.6):
    """
    Verifica se um preço parece plausível, SEM corrigir nada automaticamente.
    Se houver um preço de referência (ex: fechamento anterior via yfinance),
    sinaliza se o novo valor se desviou mais que `tolerancia` (60% por padrão)
    — isso pega tanto erro de formatação quanto erro de digitação na planilha.

    Retorna (bool_plausivel, motivo_str_ou_None).
    """
    if preco is None or preco <= 0:
        return False, "Preço nulo, vazio ou não positivo"

    if referencia is not None and referencia > 0:
        desvio = abs(preco - referencia) / referencia
        if desvio > tolerancia:
            return False, (
                f"Desvio de {desvio*100:.0f}% frente à referência "
                f"(R$ {referencia:.2f}) — possível erro de formatação na planilha"
            )

    return True, None


def formatar_moeda(valor):
    if valor is None:
        return "—"
    sinal = "-" if valor < 0 else ""
    return f"{sinal}R$ {abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor, casas=2):
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}%"


def ticker_base(codigo_opcao):
    """Extrai o código do ativo-objeto a partir do código da opção (4 letras)."""
    if not codigo_opcao:
        return ""
    s = str(codigo_opcao).strip().upper()
    return s[:4]
