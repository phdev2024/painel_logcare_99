"""
Pipeline de Consolidação: Relatórios de Posição de Estoque Multi-base
Foco na quantificação de Saldo Físico, Avarias e Volumes (Caixas).
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_ESTOQUE, ARQUIVO_PARQUET_ESTOQUE, ARQUIVO_PARQUET_PACK

def limpar_moeda_br(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(
        serie.astype(str).str.replace("R$", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0.0)

def consolidar_relatorios_estoque() -> tuple[bool, str, int]:
    if not PASTA_ESTOQUE.exists():
        return False, f"Pasta {PASTA_ESTOQUE} não encontrada.", 0

    arquivos = [arq for arq in PASTA_ESTOQUE.iterdir() if arq.is_file() and arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum ficheiro Excel encontrado na pasta data/estoque/.", 0

    colunas_alvo = ["Produto", "Grupo", "Sub-Grupo", "SKU", "Fornecedor", "Saldo", "Valor", "Avaria", "Base"]
    lista_dfs = []

    for arq in arquivos:
        try:
            df_temp = pd.read_excel(arq, usecols=colunas_alvo, dtype=str)
            lista_dfs.append(df_temp)
        except Exception as e:
            return False, f"Erro ao ler {arq.name}: {str(e)}", 0

    if not lista_dfs:
        return False, "Nenhum dado válido extraído do estoque.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # 1. Limpeza
    for col in ["Base", "SKU", "Produto", "Grupo", "Sub-Grupo", "Fornecedor"]:
        df_consolidado[col] = df_consolidado[col].astype(str).str.strip().str.upper()

    # 2. Tratamento Numérico
    df_consolidado["Saldo"] = pd.to_numeric(df_consolidado["Saldo"], errors="coerce").fillna(0).astype(int)
    df_consolidado["Avaria"] = pd.to_numeric(df_consolidado["Avaria"], errors="coerce").fillna(0).astype(int)
    df_consolidado["Valor"] = limpar_moeda_br(df_consolidado["Valor"])
    df_consolidado = df_consolidado[(df_consolidado["Saldo"] > 0) | (df_consolidado["Avaria"] > 0)].copy()

    # --- A MAGIA DO CRUZAMENTO (Cálculo de Volumes Armazenados) ---
    if ARQUIVO_PARQUET_PACK.exists():
        df_pack = pd.read_parquet(ARQUIVO_PARQUET_PACK)
        df_consolidado = df_consolidado.merge(df_pack[["SKU", "Pack_Caixa"]], on="SKU", how="left")
    else:
        df_consolidado["Pack_Caixa"] = 1

    df_consolidado["Pack_Caixa"] = df_consolidado["Pack_Caixa"].fillna(1).astype(int)
    df_consolidado["Volumes_Estoque"] = np.ceil(df_consolidado["Saldo"] / df_consolidado["Pack_Caixa"]).astype(int)

    # 3. Gravação
    arquivo_temp = ARQUIVO_PARQUET_ESTOQUE.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_ESTOQUE)

    return True, f"Sucesso! {len(df_consolidado):,} registos de posição de estoque consolidados.", len(df_consolidado)

if __name__ == "__main__":
    sucesso, msg, total = consolidar_relatorios_estoque()
    print(msg)
    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_ESTOQUE)
        print("\n--- VALIDAÇÃO DE ARMAZENAGEM ---")
        print(f"Bases com Estoque Ativo: {df_teste['Base'].nunique()}")
        print(f"Volume de Saldo Bom (un): {df_teste['Saldo'].sum():,.0f}".replace(",", "."))
        print(f"Caixas Armazenadas (Volumes): {df_teste['Volumes_Estoque'].sum():,.0f}".replace(",", "."))