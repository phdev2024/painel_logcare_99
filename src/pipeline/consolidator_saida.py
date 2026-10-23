"""
Pipeline de Consolidação: Relatórios de Saída (Expedição / Entregas)
Foco em Capilaridade Geográfica e Esforço Operacional (Peças, Pedidos e Volumes Físicos).
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Garante que o Python encontra a pasta src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_SAIDA, ARQUIVO_PARQUET_SAIDA, ARQUIVO_PARQUET_PACK

def limpar_cep(cep) -> str:
    """Garante que o CEP seja uma string limpa apenas com números."""
    cep_limpo = str(cep).replace(".0", "").replace("-", "").replace(".", "").strip()
    if cep_limpo == "NAN" or cep_limpo == "NONE" or cep_limpo == "":
        return "00000000"
    return cep_limpo.zfill(8)

def consolidar_relatorios_saida() -> tuple[bool, str, int]:
    if not PASTA_SAIDA.exists():
        return False, f"Pasta {PASTA_SAIDA} não encontrada.", 0

    arquivos = [arq for arq in PASTA_SAIDA.iterdir() if arq.is_file() and arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum ficheiro Excel encontrado na pasta data/saida/.", 0

    colunas_alvo = [
        "numero_pedido", "requested_at", "UF", "CIDADE", 
        "BAIRRO", "CEP", "ENDERECO", "SKU", "QUANTIDADE", "STATUS"
    ]

    lista_dfs = []
    for arq in arquivos:
        try:
            df_temp = pd.read_excel(arq, usecols=colunas_alvo, dtype=str)
            lista_dfs.append(df_temp)
        except Exception as e:
            return False, f"Erro ao ler {arq.name}: {str(e)}", 0

    if not lista_dfs:
        return False, "Nenhum dado válido extraído das saídas.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # 1. Filtro de Status
    df_consolidado["STATUS"] = df_consolidado["STATUS"].astype(str).str.strip().str.upper()
    df_consolidado = df_consolidado[~df_consolidado["STATUS"].str.contains("CANCELADO", na=False)].copy()

    # 2. Tratamento Temporal
    df_consolidado = df_consolidado.rename(columns={"requested_at": "Data_Emissao"})
    df_consolidado["Data_Emissao"] = pd.to_datetime(df_consolidado["Data_Emissao"], errors="coerce", dayfirst=True)
    df_consolidado = df_consolidado.dropna(subset=["Data_Emissao"]).reset_index(drop=True)
    df_consolidado["Ano"] = df_consolidado["Data_Emissao"].dt.year
    df_consolidado["Mes"] = df_consolidado["Data_Emissao"].dt.month
    df_consolidado["Ano_Mes"] = df_consolidado["Data_Emissao"].dt.strftime("%Y-%m")

    # 3. Limpeza Geográfica e de Texto
    for col in ["UF", "CIDADE", "BAIRRO", "ENDERECO"]:
        df_consolidado[col] = df_consolidado[col].astype(str).str.strip().str.upper()
    df_consolidado["CEP"] = df_consolidado["CEP"].apply(limpar_cep)
    df_consolidado["numero_pedido"] = df_consolidado["numero_pedido"].astype(str).str.strip()
    df_consolidado["SKU"] = df_consolidado["SKU"].astype(str).str.strip().str.upper()

    # 4. Tratamento Numérico
    df_consolidado["QUANTIDADE"] = pd.to_numeric(df_consolidado["QUANTIDADE"], errors="coerce").fillna(0).astype(int)
    df_consolidado = df_consolidado[df_consolidado["QUANTIDADE"] > 0].copy()

    # --- A MAGIA DO CRUZAMENTO (Cálculo de Volumes) ---
    if ARQUIVO_PARQUET_PACK.exists():
        df_pack = pd.read_parquet(ARQUIVO_PARQUET_PACK)
        df_consolidado = df_consolidado.merge(df_pack[["SKU", "Pack_Caixa"]], on="SKU", how="left")
    else:
        df_consolidado["Pack_Caixa"] = 1 # Fallback caso o ficheiro não exista

    # Se um SKU não existir na tabela de pack, consideramos que a caixa leva 1 unidade
    df_consolidado["Pack_Caixa"] = df_consolidado["Pack_Caixa"].fillna(1).astype(int)
    
    # Arredonda para cima (np.ceil) para contar caixas quebradas como 1 volume de esforço
    df_consolidado["Volumes_Calculados"] = np.ceil(df_consolidado["QUANTIDADE"] / df_consolidado["Pack_Caixa"]).astype(int)

    # 5. Gravação
    arquivo_temp = ARQUIVO_PARQUET_SAIDA.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_SAIDA)

    return True, f"Sucesso! {len(df_consolidado):,} itens expedidos consolidados.", len(df_consolidado)

if __name__ == "__main__":
    sucesso, msg, total = consolidar_relatorios_saida()
    print(msg)
    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_SAIDA)
        print("\n--- VALIDAÇÃO DE ESFORÇO ---")
        print(f"Pedidos Trabalhados: {df_teste['numero_pedido'].nunique():,.0f}".replace(",", "."))
        print(f"Peças Movimentadas (un): {df_teste['QUANTIDADE'].sum():,.0f}".replace(",", "."))
        print(f"Caixas Físicas (Volumes): {df_teste['Volumes_Calculados'].sum():,.0f}".replace(",", "."))