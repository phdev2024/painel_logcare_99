"""
Pipeline de Consolidação: Relatórios de Devolução (Logística Reversa)
Extrai inteligência do texto de observação para separar produtos Bons de Avariados.
"""

import pandas as pd
from pathlib import Path
import sys
import numpy as np

# Garante que o Python encontra a pasta src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_DEVOLUCAO, ARQUIVO_PARQUET_DEVOLUCAO

def consolidar_relatorios_devolucao() -> tuple[bool, str, int]:
    """Lê, filtra retornos e extrai qualidade da devolução (Boa vs Avaria)."""
    if not PASTA_DEVOLUCAO.exists():
        return False, f"Pasta {PASTA_DEVOLUCAO} não encontrada.", 0

    arquivos = [arq for arq in PASTA_DEVOLUCAO.iterdir() if arq.is_file() and arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum ficheiro Excel encontrado na pasta data/devolucao/.", 0

    # Ignoramos intencionalmente "Estado" e "Saldo"
    colunas_alvo = ["Produto", "Entrada", "Saída", "Tipo Produto", "Data", "Operação", "Observação"]

    lista_dfs = []

    for arq in arquivos:
        try:
            df_temp = pd.read_excel(arq, usecols=colunas_alvo, dtype=str)
            lista_dfs.append(df_temp)
        except ValueError as e:
            print(f"Aviso: Faltam colunas no ficheiro {arq.name}. Erro: {e}")
        except Exception as e:
            return False, f"Erro ao ler {arq.name}: {str(e)}", 0

    if not lista_dfs:
        return False, "Nenhum dado válido extraído das devoluções.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # --- 1. FILTRO CIRÚRGICO DE OBSERVAÇÃO ---
    df_consolidado["Observação"] = df_consolidado["Observação"].astype(str).str.strip().str.upper()
    
    # Mantém apenas as linhas onde a Observação contém a frase exata de retorno
    df_consolidado = df_consolidado[df_consolidado["Observação"].str.contains("RETORNO DE DEVOLUÇÃO", na=False)].copy()

    # --- 2. INTELIGÊNCIA ARTIFICIAL: EXTRAÇÃO DE DADOS DO TEXTO ---
    # Extrai o número do pedido (Ex: "PEDIDO: 1176")
    df_consolidado["Pedido_Origem"] = df_consolidado["Observação"].str.extract(r"PEDIDO:\s*(\d+)").fillna("0")
    
    # Extrai a quantidade Boa (Ex: "QTD BOA: 1")
    df_consolidado["Qtd_Boa_Texto"] = df_consolidado["Observação"].str.extract(r"QTD BOA:\s*(\d+)").fillna(0).astype(int)
    
    # Extrai a quantidade Avariada (Ex: "QTD AVARIA: 0")
    df_consolidado["Qtd_Avaria_Texto"] = df_consolidado["Observação"].str.extract(r"QTD AVARIA:\s*(\d+)").fillna(0).astype(int)

    # --- 3. TRATAMENTO TEMPORAL ---
    df_consolidado["Data"] = pd.to_datetime(df_consolidado["Data"], errors="coerce", dayfirst=True)
    df_consolidado = df_consolidado.dropna(subset=["Data"]).reset_index(drop=True)
    df_consolidado["Ano_Mes"] = df_consolidado["Data"].dt.strftime("%Y-%m")

    # --- 4. TRATAMENTO NUMÉRICO E BALANÇO DE REVERSA ---
    df_consolidado["Entrada"] = pd.to_numeric(df_consolidado["Entrada"], errors="coerce").fillna(0).astype(int)
    df_consolidado["Qtd_Devolvida"] = df_consolidado["Entrada"]

    # Validação de Segurança: Se a extração de texto falhar por algum erro de digitação de quem preencheu, 
    # assumimos que tudo o que entrou foi "Bom" para a conta bater.
    df_consolidado["Qtd_Boa"] = np.where(
        (df_consolidado["Qtd_Boa_Texto"] == 0) & (df_consolidado["Qtd_Avaria_Texto"] == 0), 
        df_consolidado["Entrada"], 
        df_consolidado["Qtd_Boa_Texto"]
    )
    df_consolidado["Qtd_Avaria"] = df_consolidado["Qtd_Avaria_Texto"]

    # --- 5. LIMPEZA FINAL ---
    # Extrai SKU (O que vem antes do hífen em Produto)
    df_consolidado["SKU"] = df_consolidado["Produto"].apply(lambda x: str(x).split("-")[0].strip() if "-" in str(x) else "N/A")
    df_consolidado["Produto"] = df_consolidado["Produto"].astype(str).str.strip().str.upper()
    df_consolidado["Tipo Produto"] = df_consolidado["Tipo Produto"].astype(str).str.strip().str.upper()

    # --- 6. GRAVAÇÃO ATÓMICA NO PARQUET ---
    arquivo_temp = ARQUIVO_PARQUET_DEVOLUCAO.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_DEVOLUCAO)

    return True, f"Sucesso! {len(df_consolidado):,} registos de devolução consolidados.", len(df_consolidado)

if __name__ == "__main__":
    print("Iniciando processamento da Logística Reversa...")
    sucesso, msg, total = consolidar_relatorios_devolucao()
    print(f"Resultado: {msg}")
    
    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_DEVOLUCAO)
        total_voltou = df_teste["Qtd_Devolvida"].sum()
        total_reaproveitado = df_teste["Qtd_Boa"].sum()
        total_lixo = df_teste["Qtd_Avaria"].sum()
        print(f"\n--- PERFORMANCE DE LOGÍSTICA REVERSA ---")
        print(f"Total de Peças Devolvidas: {total_voltou:,.0f}".replace(",", "."))
        print(f"Aptas para Reuso (Boa): {total_reaproveitado:,.0f}".replace(",", "."))
        print(f"Avariadas/Perdidas: {total_lixo:,.0f}".replace(",", "."))