"""
styles.py
Identidade visual do VRE Options Pro — mesa de operações de derivativos.

Direção de design:
  - Fundo quase-preto (terminal de operações, não "app bonito de consumo")
  - Tipografia monoespaçada para todo dado numérico (preço, delta, %, R$)
    — como um terminal de trading real, não uma fonte genérica de UI
  - Vermelho da marca original (#CC0033) mantido como accent primário,
    mas usado com moderação — verde/vermelho semânticos reservados
    exclusivamente para ganho/perda, nunca para decoração
  - Elemento de assinatura: barra de exposição por ativo sempre visível
    no topo — resposta direta ao achado de 61% de capital concentrado
    num único ativo. É um "instrumento de cockpit", não um gráfico solto.

Correção de bug: a versão anterior tinha `pass` antes do CSS (nunca
executava) e usava `unsafe_html=True` (parâmetro inexistente no Streamlit;
o correto é `unsafe_allow_html=True`). Ambos corrigidos aqui.
"""

import streamlit as st

BG = "#0E0F11"
SURFACE = "#17181C"
SURFACE_2 = "#1D1F24"
BORDER = "#26282E"
ACCENT = "#C4344F"
ACCENT_SOFT = "rgba(196,52,79,0.12)"
SUCCESS = "#1BAF7A"
SUCCESS_SOFT = "rgba(27,175,122,0.12)"
DANGER = "#E34948"
DANGER_SOFT = "rgba(227,73,72,0.12)"
WARNING = "#D9A441"
TEXT_PRIMARY = "#EDEDEC"
TEXT_SECONDARY = "#8A8D93"
FONT_MONO = "'IBM Plex Mono', 'JetBrains Mono', monospace"
FONT_UI = "'Inter', -apple-system, sans-serif"


def inject_styles():
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: {FONT_UI};
    }}

    .stApp {{
        background-color: {BG};
        color: {TEXT_PRIMARY};
    }}

    /* Header institucional */
    .vre-header {{
        background: linear-gradient(135deg, {SURFACE} 0%, {SURFACE_2} 100%);
        border: 1px solid {BORDER};
        border-left: 3px solid {ACCENT};
        color: {TEXT_PRIMARY};
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 12px;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .vre-header h1 {{
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
        color: {TEXT_PRIMARY} !important;
    }}
    .vre-header p {{
        font-size: 0.8rem;
        color: {TEXT_SECONDARY};
        margin: 0;
        font-family: {FONT_MONO};
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}

    /* Barra de exposição — elemento de assinatura, sempre visível */
    .vre-exposure-bar {{
        display: flex;
        width: 100%;
        height: 10px;
        border-radius: 6px;
        overflow: hidden;
        margin: 6px 0 4px 0;
        background: {SURFACE_2};
        border: 1px solid {BORDER};
    }}
    .vre-exposure-segment {{
        height: 100%;
        transition: opacity 0.2s;
    }}
    .vre-exposure-legend {{
        display: flex;
        justify-content: space-between;
        font-family: {FONT_MONO};
        font-size: 0.7rem;
        color: {TEXT_SECONDARY};
        margin-bottom: 8px;
    }}

    /* Cards de métrica */
    .vre-metric-card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 14px 16px;
        height: 100%;
    }}
    .vre-metric-label {{
        font-size: 0.72rem;
        color: {TEXT_SECONDARY};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        font-family: {FONT_UI};
    }}
    .vre-metric-value {{
        font-size: 1.5rem;
        font-weight: 600;
        font-family: {FONT_MONO};
        color: {TEXT_PRIMARY};
    }}
    .vre-metric-value.positivo {{ color: {SUCCESS}; }}
    .vre-metric-value.negativo {{ color: {DANGER}; }}
    .vre-metric-sub {{
        font-size: 0.72rem;
        color: {TEXT_SECONDARY};
        margin-top: 2px;
        font-family: {FONT_MONO};
    }}

    /* Badges de status/alerta */
    .vre-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        font-family: {FONT_MONO};
    }}
    .vre-badge.ok {{ background: {SUCCESS_SOFT}; color: {SUCCESS}; }}
    .vre-badge.alerta {{ background: {DANGER_SOFT}; color: {DANGER}; }}
    .vre-badge.atencao {{ background: rgba(217,164,65,0.12); color: {WARNING}; }}

    .vre-alert-box {{
        background: {DANGER_SOFT};
        border: 1px solid {DANGER};
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 10px;
        font-size: 0.85rem;
        color: {TEXT_PRIMARY};
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {SURFACE};
        border-radius: 10px;
        padding: 4px;
        border: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px;
        color: {TEXT_SECONDARY};
        font-family: {FONT_UI};
        font-weight: 500;
        font-size: 0.85rem;
    }}
    .stTabs [aria-selected="true"] {{
        background: {ACCENT_SOFT} !important;
        color: {ACCENT} !important;
    }}

    /* Botões */
    div.stButton > button {{
        background-color: {ACCENT} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-family: {FONT_UI} !important;
        padding: 0.5rem 1rem !important;
    }}
    div.stButton > button:hover {{
        background-color: #A82A41 !important;
    }}

    /* Dataframes: números em mono */
    [data-testid="stDataFrame"] {{
        font-family: {FONT_MONO};
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {SURFACE};
        border-right: 1px solid {BORDER};
    }}

    .vre-footer {{
        text-align: center;
        font-size: 0.72rem;
        color: {TEXT_SECONDARY};
        margin-top: 40px;
        padding: 16px;
        border-top: 1px solid {BORDER};
        font-family: {FONT_MONO};
    }}

    /* Mobile: reduz padding e empilha métricas */
    @media (max-width: 640px) {{
        .vre-header {{ padding: 14px 16px; }}
        .vre-header h1 {{ font-size: 1.1rem; }}
        .vre-metric-value {{ font-size: 1.25rem; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def metric_card(label, valor, sub=None, tipo=None):
    """
    tipo: None | 'positivo' | 'negativo' — colore o valor semanticamente.
    Retorna o HTML pronto para st.markdown(..., unsafe_allow_html=True).
    """
    classe = f"vre-metric-value {tipo}" if tipo else "vre-metric-value"
    sub_html = f'<div class="vre-metric-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="vre-metric-card">
        <div class="vre-metric-label">{label}</div>
        <div class="{classe}">{valor}</div>
        {sub_html}
    </div>
    """


def badge(texto, tipo="ok"):
    return f'<span class="vre-badge {tipo}">{texto}</span>'


def alert_box(texto):
    return f'<div class="vre-alert-box">⚠️ {texto}</div>'


def exposure_bar_html(df_concentracao, limite_pct=10.0):
    """
    Elemento de assinatura: barra segmentada mostrando % de capital por
    ativo. Segmentos acima do limite piscam em vermelho (via cor sólida
    de alerta) — é a materialização visual direta do achado de concentração.
    """
    if df_concentracao is None or df_concentracao.empty:
        return '<div class="vre-exposure-legend">Sem operações abertas para calcular exposição.</div>'

    cores_paleta = ["#4A90D9", "#7B61C7", "#3FA5A5", "#D9A441", "#8A8D93"]
    segmentos = []
    legendas = []
    for i, row in df_concentracao.iterrows():
        pct = row["PCT_CAPITAL"]
        cor = DANGER if pct > limite_pct else cores_paleta[i % len(cores_paleta)]
        segmentos.append(f'<div class="vre-exposure-segment" style="width:{pct}%;background:{cor};" title="{row["ATIVO_BASE"]}: {pct:.1f}%"></div>')
        legendas.append(f'{row["ATIVO_BASE"]} {pct:.0f}%')

    bar_html = f'<div class="vre-exposure-bar">{"".join(segmentos)}</div>'
    legend_html = f'<div class="vre-exposure-legend"><span>{" · ".join(legendas[:6])}</span><span>Limite: {limite_pct:.0f}%/ativo</span></div>'
    return bar_html + legend_html
