"""
diagnostico.py
Ferramenta de diagnóstico isolada — NÃO faz parte do app principal.
Use via linha de comando para depurar problemas de obtenção de dados
de um ticker específico: `python diagnostico.py PETR3`

Correção em relação à versão anterior: os testes agora só rodam dentro de
`if __name__ == "__main__"`, em vez de executar automaticamente ao importar
o módulo (o que quebraria qualquer tentativa de reuso de suas funções).
"""

import sys
import yfinance as yf


def testar_ticker_detalhado(ticker_base):
    print(f"\n{'='*60}")
    print(f"DIAGNÓSTICO COMPLETO: {ticker_base}")
    print(f"{'='*60}")

    tickers_para_testar = [f"{ticker_base}.SA"]

    for ticker in tickers_para_testar:
        print(f"\n1. Testando ticker: {ticker}")
        try:
            ticker_obj = yf.Ticker(ticker)
            print("   ✓ Objeto Ticker criado")

            try:
                info = ticker_obj.info
                print(f"   Nome: {info.get('longName', 'N/D')}")
                print(f"   Setor: {info.get('sector', 'N/D')}")
                print(f"   Preço atual: {info.get('currentPrice', 'N/D')}")
            except Exception:
                print("   ⚠️ Não foi possível obter info básica")

            print("\n2. Obtendo histórico 6 meses...")
            hist = ticker_obj.history(period="6mo")

            if hist.empty:
                print("   ❌ DataFrame VAZIO!")
                for periodo in ['1mo', '3mo', '1y']:
                    hist_temp = ticker_obj.history(period=periodo)
                    print(f"   Período {periodo}: {len(hist_temp)} registros")
                    if not hist_temp.empty:
                        print(f"   Último dado: {hist_temp.index[-1]}")
                        print(f"   Preço: R$ {hist_temp['Close'].iloc[-1]:.2f}")
            else:
                print(f"   ✓ {len(hist)} registros obtidos")
                print(f"   Período: {hist.index[0].date()} a {hist.index[-1].date()}")
                print(f"   Preço atual: R$ {hist['Close'].iloc[-1]:.2f}")
                print(f"   Volume médio: {hist['Volume'].mean():.0f}")
                print(f"   Mínima 6m: R$ {hist['Low'].min():.2f}")
                print(f"   Máxima 6m: R$ {hist['High'].max():.2f}")
                print(f"\n3. Colunas disponíveis: {list(hist.columns)}")
                nulos = hist.isnull().sum()
                print(f"   Valores nulos: {dict(nulos[nulos > 0])}")

                print("\n4. Teste de elegibilidade para score:")
                print(f"   Mínimo 25 registros (score_engine): {'✓' if len(hist) >= 25 else '✗'} ({len(hist)})")

                if len(hist) >= 15:
                    min_6m = hist['Low'].min()
                    preco_atual = hist['Close'].iloc[-1]
                    dist = ((preco_atual - min_6m) / min_6m) * 100
                    print(f"   Distância da mínima: {dist:.2f}%")

        except Exception as e:
            print(f"   ❌ ERRO: {type(e).__name__}: {e}")

        print(f"\n{'-'*40}")


if __name__ == "__main__":
    ativos = sys.argv[1:] if len(sys.argv) > 1 else ["PETR3", "VALE3", "BBSE3"]
    print("INICIANDO DIAGNÓSTICO DETALHADO")
    print("=" * 60)
    for a in ativos:
        testar_ticker_detalhado(a)
