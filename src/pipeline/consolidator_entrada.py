"""
Pipeline de Consolidação: Relatórios de Entrada Detalhada (Custo, Peças e SKUs)
"""

import pandas as pd
from pathlib import Path
from src.config.settings import PASTA_ENTRADA, TAMANHO_MAXIMO_NOME_CLIENTE, PASTA_PROCESSADOS

ARQUIVO_PARQUET_ENTRADA = PASTA_PROCESSADOS / "historico_entrada.parquet"


def formatar_nome_cliente(nome: str, limite: int = TAMANHO_MAXIMO_NOME_CLIENTE) -> str:
    """Padroniza e trunca nome de clientes longos com reticências."""
    if pd.isna(nome):
        return "NÃO INFORMADO"
    nome_limpo = str(nome).strip().upper()
    if len(nome_limpo) > limite:
        return f"{nome_limpo[:limite]}..."
    return nome_limpo


def limpar_numero_br(serie: pd.Series) -> pd.Series:
    """Converte padrão '1.300,00' ou '179.400,00' para float real do Python."""
    return pd.to_numeric(
        serie.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip(),
        errors="coerce"
    ).fillna(0.0)


def consolidar_relatorios_entrada() -> tuple[bool, str, int]:
    """
    Lê, limpa, padroniza e converte relatórios CSV de entrada para Parquet.
    """
    if not PASTA_ENTRADA.exists():
        return False, f"Pasta {PASTA_ENTRADA} não encontrada.", 0

    arquivos = [arq for arq in PASTA_ENTRADA.iterdir() if arq.is_file() and arq.suffix.lower() == ".csv" and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum arquivo CSV encontrado em data/entrada/.", 0

    lista_dfs = []

    # Adicionado o índice 18 para capturar a coluna de "Devolução" do CSV
    colunas_alvo = [13, 16, 17, 18, 29, 30, 33, 34, 35]

    for arq in arquivos:
        try:
            try:
                df_temp = pd.read_csv(
                    arq, 
                    sep=",", 
                    header=None, 
                    usecols=colunas_alvo, 
                    dtype=str, 
                    encoding="utf-8-sig"
                )
            except UnicodeDecodeError:
                df_temp = pd.read_csv(
                    arq, 
                    sep=",", 
                    header=None, 
                    usecols=colunas_alvo, 
                    dtype=str, 
                    encoding="latin1"
                )

            # Renomeia as colunas por posição, incluindo a Devolução
            df_temp = df_temp.rename(columns={
                13: "Cliente_Bruto",
                16: "Data_Entrada",
                17: "Nota_Fiscal",
                18: "Devolucao",
                29: "SKU",
                30: "Descricao_Produto",
                33: "Qtde_Entrada",
                34: "Valor_Unitario",
                35: "Valor_Total"
            })

            lista_dfs.append(df_temp)

        except Exception as e:
            return False, f"Erro ao ler {arq.name}: {str(e)}", 0

    if not lista_dfs:
        return False, "Nenhum dado válido extraído das entradas.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # --- 1. LIMPEZA DE LINHAS DE CABEÇALHO/RODAPÉ REPETIDAS ---
    df_consolidado["Data_Entrada"] = pd.to_datetime(
        df_consolidado["Data_Entrada"], errors="coerce", dayfirst=True
    )
    df_consolidado = df_consolidado.dropna(subset=["Data_Entrada"]).reset_index(drop=True)
    
    # --- 2. FILTRO CIRÚRGICO DE DEVOLUÇÕES ---
    # Limpa a coluna (remove espaços e põe em maiúsculo) e descarta tudo que contiver "SIM"
    df_consolidado["Devolucao"] = df_consolidado["Devolucao"].astype(str).str.strip().str.upper()
    df_consolidado = df_consolidado[~df_consolidado["Devolucao"].str.contains("SIM", na=False)].copy()

    df_consolidado = df_consolidado.sort_values(by="Data_Entrada", ascending=True)

    # --- 3. COLUNAS TEMPORAIS ---
    df_consolidado["Ano"] = df_consolidado["Data_Entrada"].dt.year
    df_consolidado["Mes"] = df_consolidado["Data_Entrada"].dt.month
    df_consolidado["Ano_Mes"] = df_consolidado["Data_Entrada"].dt.strftime("%Y-%m")
    df_consolidado["Dia"] = df_consolidado["Data_Entrada"].dt.day

    # --- 4. PADRONIZAÇÃO DE CLIENTES ---
    df_consolidado["Cliente_Original"] = df_consolidado["Cliente_Bruto"].astype(str).str.strip().str.upper()
    df_consolidado["Cliente_Exibicao"] = df_consolidado["Cliente_Original"].apply(formatar_nome_cliente)
    df_consolidado = df_consolidado.drop(columns=["Cliente_Bruto", "Devolucao"]) # A devolução já fez o seu trabalho, podemos descartar

    # --- 5. TRATAMENTO FINANCEIRO E QUANTITATIVO ---
    df_consolidado["Qtde_Entrada"] = limpar_numero_br(df_consolidado["Qtde_Entrada"])
    df_consolidado["Valor_Unitario"] = limpar_numero_br(df_consolidado["Valor_Unitario"])
    df_consolidado["Valor_Total"] = limpar_numero_br(df_consolidado["Valor_Total"])

    # A NOVA ORDEM: "Mantenha apenas as linhas onde a Quantidade é estritamente maior que zero"
    # O porquê: Isso limpa fretes, taxas administrativas, cancelamentos e linhas vazias do relatório cru.
    # O para que: Garantir que o valor financeiro bata apenas com operações de produtos físicos.
    df_consolidado = df_consolidado[df_consolidado["Qtde_Entrada"] > 0].copy()

    # --- 6. IDENTIFICADORES COMO STRING LIMPA ---
    df_consolidado["Nota_Fiscal"] = df_consolidado["Nota_Fiscal"].astype(str).str.strip()
    df_consolidado["SKU"] = df_consolidado["SKU"].astype(str).str.strip()
    df_consolidado["Descricao_Produto"] = df_consolidado["Descricao_Produto"].astype(str).str.strip().str.upper()

    # --- 7. GRAVAÇÃO ATÔMICA EM PARQUET ---
    arquivo_temp = ARQUIVO_PARQUET_ENTRADA.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_ENTRADA)

    return True, f"Sucesso! {len(df_consolidado):,} itens de entrada consolidados em Parquet.", len(df_consolidado)


if __name__ == "__main__":
    print("Iniciando consolidação dos relatórios de entrada...")
    sucesso, msg, total = consolidar_relatorios_entrada()
    print(f"Resultado: {msg}")

    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_ENTRADA)
        print("\n--- VALIDAÇÃO FINANCEIRA ---")
        print(f"Unidades Totais: {df_teste['Qtde_Entrada'].sum():,.0f}".replace(",", "."))
        print(f"Valor Contábil Total: R$ {df_teste['Valor_Total'].sum():,.2f}")