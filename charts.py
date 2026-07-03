"""
charts.py
Gráficos do aplicativo:
  - plot_payoff: payoff da trava de alta, agora com túnel destacado,
    ponto de equilíbrio calculado e anotações de lucro/risco máximos
  - tradingview_widget: embed do gráfico avançado do TradingView para
    análise visual do ativo (candles, indicadores nativos da plataforma)
  - gráficos de performance: curva de capital, concentração por ativo,
    distribuição de resultados
"""

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd

COR_LUCRO = "#1BAF7A"
COR_PREJUIZO = "#E34948"
COR_LINHA = "#CC0033"
COR_TUNEL = "rgba(204, 0, 51, 0.08)"


def plot_payoff(strike_compra, strike_venda, preco_ativo, custo_montagem, qtd=1):
    """
    Payoff da trava de alta (compra de call/put strike menor + venda de
    call/put strike maior). custo_montagem deve ser negativo quando há
    débito líquido na montagem.

    Adições em relação à versão anterior:
      - área do túnel destacada visualmente
      - ponto de equilíbrio calculado e anotado
      - lucro/risco máximo anotados diretamente no gráfico, não só em texto ao lado
    """
    range_min = strike_compra * 0.85
    range_max = strike_venda * 1.15
    passos = 150
    x_range = [range_min + i * (range_max - range_min) / passos for i in range(passos + 1)]

    y_payoff = []
    for x in x_range:
        lucro = (max(0, x - strike_compra) - max(0, x - strike_venda) + custo_montagem) * qtd
        y_payoff.append(lucro)

    lucro_max = ((strike_venda - strike_compra) + custo_montagem) * qtd
    risco_max = custo_montagem * qtd  # negativo

    # ponto de equilíbrio (breakeven): onde payoff cruza zero
    breakeven = strike_compra - custo_montagem

    fig = go.Figure()

    # área do túnel
    fig.add_vrect(
        x0=strike_compra, x1=strike_venda,
        fillcolor=COR_TUNEL, line_width=0,
        annotation_text="Túnel", annotation_position="top left",
        annotation_font_color="#CC0033"
    )

    fig.add_trace(go.Scatter(
        x=x_range, y=y_payoff,
        mode='lines', name='Payoff',
        line=dict(color=COR_LINHA, width=3),
        fill='tozeroy',
        fillcolor='rgba(204,0,51,0.05)'
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="#999", opacity=0.7)
    fig.add_vline(x=preco_ativo, line_dash="dot", line_color="#F5A623",
                  annotation_text=f"Preço atual R$ {preco_ativo:.2f}",
                  annotation_position="top")
    fig.add_vline(x=breakeven, line_dash="dot", line_color="#4A90D9",
                  annotation_text=f"Breakeven R$ {breakeven:.2f}",
                  annotation_position="bottom")

    fig.add_annotation(
        x=strike_venda, y=lucro_max,
        text=f"Lucro máx: R$ {lucro_max:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        showarrow=True, arrowhead=2, ay=-40,
        font=dict(color=COR_LUCRO, size=13)
    )
    fig.add_annotation(
        x=strike_compra, y=risco_max,
        text=f"Risco máx: R$ {abs(risco_max):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        showarrow=True, arrowhead=2, ay=40,
        font=dict(color=COR_PREJUIZO, size=13)
    )

    fig.update_layout(
        title="Análise de Payoff — Trava de Alta (no vencimento)",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color="#E5E5E5",
        xaxis=dict(title="Preço do ativo no vencimento (R$)", showgrid=True, gridcolor='#333'),
        yaxis=dict(title="Resultado financeiro (R$)", showgrid=True, gridcolor='#333'),
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=False,
        height=420,
    )

    return fig


def tradingview_widget(ticker_b3, altura=520, tema="dark"):
    """
    Embed do widget avançado do TradingView para o ativo selecionado.
    ticker_b3: código sem sufixo (ex: 'PETR4') — mapeado para BMFBOVESPA.
    """
    simbolo = f"BMFBOVESPA:{ticker_b3.upper().strip()}"
    html = f"""
    <div class="tradingview-widget-container" style="height:{altura}px;width:100%;">
      <div id="tv_chart" style="height:100%;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{simbolo}",
          "interval": "D",
          "timezone": "America/Sao_Paulo",
          "theme": "{tema}",
          "style": "1",
          "locale": "br",
          "toolbar_bg": "#1E1E1E",
          "enable_publishing": false,
          "allow_symbol_change": true,
          "studies": ["RSI@tv-basicstudies", "BB@tv-basicstudies"],
          "container_id": "tv_chart"
        }});
      </script>
    </div>
    """
    components.html(html, height=altura)


def plot_curva_capital(df_curva):
    """Curva de capital acumulado (resultado das operações ao longo do tempo)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_curva["DATA_VENDA"], y=df_curva["RESULTADO_ACUMULADO"],
        mode='lines', name='Resultado acumulado',
        line=dict(color=COR_LUCRO, width=2.5),
        fill='tozeroy', fillcolor='rgba(27,175,122,0.08)'
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#999", opacity=0.5)
    fig.update_layout(
        title="Evolução do resultado acumulado",
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font_color="#E5E5E5",
        xaxis=dict(title="Data", showgrid=False),
        yaxis=dict(title="R$ acumulado", showgrid=True, gridcolor='#333'),
        margin=dict(l=20, r=20, t=50, b=20), height=340,
    )
    return fig


def plot_concentracao_ativos(df_concentracao):
    """Barras de capital alocado por ativo, com destaque para os acima do limite."""
    cores = [COR_PREJUIZO if acima else "#4A90D9" for acima in df_concentracao["ACIMA_DO_LIMITE"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_concentracao["ATIVO_BASE"], y=df_concentracao["PCT_CAPITAL"],
        marker_color=cores, name="% do capital"
    ))
    fig.add_hline(y=10, line_dash="dash", line_color="#F5A623",
                  annotation_text="Limite recomendado (10%)", annotation_position="top right")
    fig.update_layout(
        title="Concentração de capital por ativo",
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font_color="#E5E5E5",
        xaxis=dict(title=""), yaxis=dict(title="% do capital total", showgrid=True, gridcolor='#333'),
        margin=dict(l=20, r=20, t=50, b=20), height=340,
    )
    return fig


def plot_distribuicao_resultados(df):
    """Histograma de resultados (R$) por operação — mostra a assimetria real."""
    fig = go.Figure()
    cores = [COR_LUCRO if v >= 0 else COR_PREJUIZO for v in df["LUCPREJ"]]
    fig.add_trace(go.Bar(
        x=list(range(len(df))), y=df["LUCPREJ"].sort_values().values,
        marker_color=sorted(cores, key=lambda c: c == COR_LUCRO),
    ))
    fig.add_hline(y=0, line_color="#999")
    fig.update_layout(
        title="Distribuição de resultados por operação",
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font_color="#E5E5E5",
        xaxis=dict(title="Operações (ordenadas)", showticklabels=False),
        yaxis=dict(title="R$", showgrid=True, gridcolor='#333'),
        margin=dict(l=20, r=20, t=50, b=20), height=300,
    )
    return fig
