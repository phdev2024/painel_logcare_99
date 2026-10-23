"""
Pipeline de Consolidação: Tabela de Packs (Master Data)
Cria o dicionário de conversão de Unidades para Caixas Físicas.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Garante que o Python encontra a pasta src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_PACK, ARQUIVO_PARQUET_PACK

def consolidar_tabela_pack() -> tuple[bool, str, int]:
    """Lê a planilha de pack e cria um dicionário único por SKU."""
    if not PASTA_PACK.exists():
        return False, f"Pasta {PASTA_PACK} não encontrada.", 0

    arquivos = [arq for arq in PASTA_PACK.iterdir() if arq.is_file() and arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum ficheiro Excel encontrado na pasta data/pack/.", 0

    colunas_alvo = ["SKU", "Nome", "Pack_Caixa"]
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
        return False, "Nenhum dado válido extraído da pasta pack.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # --- 1. LIMPEZA E PADRONIZAÇÃO DE CHAVES ---
    df_consolidado["SKU"] = df_consolidado["SKU"].astype(str).str.strip().str.upper()
    df_consolidado["Nome"] = df_consolidado["Nome"].astype(str).str.strip().str.upper()

    # --- 2. TRATAMENTO MATEMÁTICO DE SEGURANÇA ---
    # Converte para inteiro. Se for texto ou vazio, vira nulo (coerce) e depois assume 1
    df_consolidado["Pack_Caixa"] = pd.to_numeric(df_consolidado["Pack_Caixa"], errors="coerce").fillna(1).astype(int)
    
    # Prevenção contra Divisão por Zero: Qualquer pack menor ou igual a zero é forçado a 1
    df_consolidado["Pack_Caixa"] = np.where(df_consolidado["Pack_Caixa"] <= 0, 1, df_consolidado["Pack_Caixa"])

    # --- 3. DEDUPLICAÇÃO ---
    # Se o mesmo SKU aparecer duas vezes na planilha, mantemos o último (mais atualizado)
    df_consolidado = df_consolidado.drop_duplicates(subset=["SKU"], keep="last")

    # --- 4. GRAVAÇÃO ATÓMICA NO PARQUET ---
    arquivo_temp = ARQUIVO_PARQUET_PACK.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_PACK)

    return True, f"Sucesso! {len(df_consolidado):,} SKUs mapeados com fator de conversão de caixas.", len(df_consolidado)

if __name__ == "__main__":
    print("Iniciando mapeamento dos Packs de Produtos...")
    sucesso, msg, total = consolidar_tabela_pack()
    print(f"Resultado: {msg}")
    
    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_PACK)
        print("\n--- AMOSTRA DO DICIONÁRIO ---")
        print(df_teste.head(3))