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

import pandas as pd
import numpy as np
from utils import ticker_base


# ---------------------------------------------------------------------------
# 1. Limites de exposição e concentração
# ---------------------------------------------------------------------------

LIMITE_PCT_POR_ATIVO = 0.10      # nenhum ativo > 10% do capital total alocado
LIMITE_PCT_POR_SETOR = 0.25      # nenhum setor/grupo > 25% do capital total
JANELA_ROLAGEM_DIAS = 30         # capital de reposição soma ao teto do ativo original por N dias


def calcular_exposicao_atual(df_operacoes_abertas, capital_total):
    """
    df_operacoes_abertas: DataFrame com colunas mínimas
        ['ATIVO_BASE', 'SETOR', 'VALOR_OPERACAO', 'DATA_ABERTURA']
    Retorna um resumo de exposição por ativo e por setor, em R$ e em %.
    """
    if df_operacoes_abertas is None or df_operacoes_abertas.empty or capital_total <= 0:
        return pd.DataFrame(columns=["ATIVO_BASE", "CAPITAL_RS", "PCT_CAPITAL", "LIMITE_OK"])

    g = df_operacoes_abertas.groupby("ATIVO_BASE").agg(
        CAPITAL_RS=("VALOR_OPERACAO", "sum")
    ).reset_index()
    g["PCT_CAPITAL"] = g["CAPITAL_RS"] / capital_total
    g["LIMITE_OK"] = g["PCT_CAPITAL"] <= LIMITE_PCT_POR_ATIVO
    return g.sort_values("PCT_CAPITAL", ascending=False)


def validar_nova_entrada(ativo_base, valor_nova_operacao, capital_total,
                          df_operacoes_abertas, setor=None,
                          df_capital_por_setor=None):
    """
    Verifica se uma nova operação pode ser aberta sem violar os limites de
    concentração. Retorna (permitido: bool, motivos: list[str]).
    Isso deveria ser chamado no app ANTES de confirmar qualquer entrada nova.
    """
    motivos = []
    permitido = True

    if capital_total <= 0:
        return False, ["Capital total não informado ou inválido."]

    exposicao_atual_ativo = 0.0
    if df_operacoes_abertas is not None and not df_operacoes_abertas.empty:
        mask = df_operacoes_abertas["ATIVO_BASE"] == ativo_base
        exposicao_atual_ativo = df_operacoes_abertas.loc[mask, "VALOR_OPERACAO"].sum()

    pct_apos_entrada = (exposicao_atual_ativo + valor_nova_operacao) / capital_total
    if pct_apos_entrada > LIMITE_PCT_POR_ATIVO:
        permitido = False
        motivos.append(
            f"Concentração em {ativo_base} ficaria em {pct_apos_entrada*100:.1f}% "
            f"(limite: {LIMITE_PCT_POR_ATIVO*100:.0f}%). "
            f"Isso é exatamente o padrão identificado no histórico (61% em um único ativo)."
        )

    if setor and df_capital_por_setor is not None and not df_capital_por_setor.empty:
        capital_setor_atual = df_capital_por_setor.get(setor, 0.0)
        pct_setor_apos = (capital_setor_atual + valor_nova_operacao) / capital_total
        if pct_setor_apos > LIMITE_PCT_POR_SETOR:
            permitido = False
            motivos.append(
                f"Concentração no setor '{setor}' ficaria em {pct_setor_apos*100:.1f}% "
                f"(limite: {LIMITE_PCT_POR_SETOR*100:.0f}%)."
            )

    if permitido:
        motivos.append("Dentro dos limites de concentração por ativo e setor.")

    return permitido, motivos


# ---------------------------------------------------------------------------
# 2. Saída dinâmica (trailing sobre o prêmio + invalidação técnica)
# ---------------------------------------------------------------------------

PCT_ARME_TRAILING = 0.40      # a partir de 40% de decaimento do prêmio, o trailing é "armado"
PCT_GATILHO_TRAILING = 0.15   # se o prêmio subir 15% a partir da mínima atingida, dispara saída
PCT_ALVO_MAXIMO = 0.60        # alvo cheio original da estratégia (teto de referência)
MULTIPLICADOR_STOP_TEMPO = 1.5  # 1.5x o tempo médio histórico (31 dias) sem atingir alvo


def avaliar_saida_dinamica(premio_abertura, premio_minimo_historico, premio_atual,
                            dias_em_aberto, tempo_medio_historico_dias=31,
                            preco_ativo_atual=None, suporte_referencia=None,
                            rsi_atual=None):
    """
    Avalia se uma posição de venda de PUT deve ser encerrada agora, com base
    em trailing sobre o prêmio (não um alvo fixo) + invalidação técnica.

    premio_abertura: prêmio recebido na venda
    premio_minimo_historico: menor prêmio já observado desde a abertura
                              (atualizar a cada novo dado — é o "mark" do trailing)
    premio_atual: prêmio de recompra no momento da avaliação

    Retorna dict com decisão e motivo.
    """
    decisao = {"encerrar": False, "motivo": None, "tipo_gatilho": None}

    if premio_abertura <= 0:
        decisao["motivo"] = "Prêmio de abertura inválido."
        return decisao

    decaimento_atual = 1 - (premio_atual / premio_abertura)
    decaimento_minimo = 1 - (premio_minimo_historico / premio_abertura)

    # 1) Alvo cheio original (60%) — sempre respeitado como teto
    if decaimento_atual >= PCT_ALVO_MAXIMO:
        decisao.update(encerrar=True, tipo_gatilho="alvo_cheio",
                        motivo=f"Decaimento de {decaimento_atual*100:.0f}% atingiu o alvo máximo de {PCT_ALVO_MAXIMO*100:.0f}%.")
        return decisao

    # 2) Trailing armado: uma vez que o decaimento mínimo passou de 40%,
    #    monitora se o prêmio subiu X% a partir da mínima (reversão desfavorável)
    if decaimento_minimo >= PCT_ARME_TRAILING:
        subida_desde_minimo = (premio_atual / premio_minimo_historico) - 1
        if subida_desde_minimo >= PCT_GATILHO_TRAILING:
            decisao.update(
                encerrar=True, tipo_gatilho="trailing",
                motivo=(
                    f"Trailing armado (mínimo de decaimento atingiu {decaimento_minimo*100:.0f}%). "
                    f"Prêmio subiu {subida_desde_minimo*100:.0f}% desde a mínima — "
                    f"ganho consistente sendo travado antes de reverter."
                )
            )
            return decisao

    # 3) Invalidação técnica: rompimento do suporte que justificou a entrada
    if preco_ativo_atual is not None and suporte_referencia is not None:
        if preco_ativo_atual < suporte_referencia:
            decisao.update(
                encerrar=True, tipo_gatilho="invalidacao_tecnica",
                motivo=f"Preço (R$ {preco_ativo_atual:.2f}) rompeu o suporte que justificou a entrada (R$ {suporte_referencia:.2f})."
            )
            return decisao

    # 4) Stop de tempo: operação muito além do tempo médio histórico sem atingir alvo
    limite_dias = tempo_medio_historico_dias * MULTIPLICADOR_STOP_TEMPO
    if dias_em_aberto > limite_dias:
        decisao.update(
            encerrar=False, tipo_gatilho="revisao_manual",
            motivo=(
                f"Operação em {dias_em_aberto} dias, além de {limite_dias:.0f} dias "
                f"({MULTIPLICADOR_STOP_TEMPO}x a média histórica de {tempo_medio_historico_dias}). "
                f"Tese pode não estar se confirmando — recomenda-se revisão manual, não fechamento automático."
            )
        )
        return decisao

    decisao["motivo"] = f"Sem gatilho. Decaimento atual: {decaimento_atual*100:.0f}% | mínimo histórico: {decaimento_minimo*100:.0f}%."
    return decisao


def avaliar_saida_dinamica_compra(premio_abertura, premio_maximo_historico, premio_atual,
                                   dias_em_aberto, tempo_medio_historico_dias=31,
                                   pct_alvo_maximo=1.0, pct_gatilho_trailing=0.20,
                                   pct_arme_trailing=0.30):
    """
    Espelho para compra de PUT: aqui o ganho vem da VALORIZAÇÃO do prêmio.
    Trailing mais apertado por padrão, já que o theta corrói o valor rapidamente
    perto do vencimento (conforme discutido: risco assimétrico oposto ao da venda).
    """
    decisao = {"encerrar": False, "motivo": None, "tipo_gatilho": None}

    if premio_abertura <= 0:
        decisao["motivo"] = "Prêmio de abertura inválido."
        return decisao

    valorizacao_atual = (premio_atual / premio_abertura) - 1
    valorizacao_maxima = (premio_maximo_historico / premio_abertura) - 1

    if valorizacao_atual >= pct_alvo_maximo:
        decisao.update(encerrar=True, tipo_gatilho="alvo_cheio",
                        motivo=f"Valorização de {valorizacao_atual*100:.0f}% atingiu o alvo de {pct_alvo_maximo*100:.0f}%.")
        return decisao

    if valorizacao_maxima >= pct_arme_trailing:
        queda_desde_maximo = 1 - (premio_atual / premio_maximo_historico)
        if queda_desde_maximo >= pct_gatilho_trailing:
            decisao.update(
                encerrar=True, tipo_gatilho="trailing",
                motivo=(
                    f"Trailing armado (valorização máxima {valorizacao_maxima*100:.0f}%). "
                    f"Prêmio caiu {queda_desde_maximo*100:.0f}% desde a máxima — travando ganho antes de reverter."
                )
            )
            return decisao

    limite_dias = tempo_medio_historico_dias * MULTIPLICADOR_STOP_TEMPO
    if dias_em_aberto > limite_dias:
        decisao.update(
            encerrar=False, tipo_gatilho="revisao_manual",
            motivo=f"Operação além de {limite_dias:.0f} dias sem atingir alvo — revisar manualmente (theta decay se intensifica)."
        )
        return decisao

    decisao["motivo"] = f"Sem gatilho. Valorização atual: {valorizacao_atual*100:.0f}% | máxima histórica: {valorizacao_maxima*100:.0f}%."
    return decisao
