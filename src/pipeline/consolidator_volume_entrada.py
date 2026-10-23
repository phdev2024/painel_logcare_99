"""
Pipeline de Consolidação: Relatórios de Volumes de Entrada (.csv)
"""

import pandas as pd
from pathlib import Path
from src.config.settings import PASTA_VOLUME_ENTRADA, TAMANHO_MAXIMO_NOME_CLIENTE, PASTA_PROCESSADOS

ARQUIVO_PARQUET_VOLUME_ENTRADA = PASTA_PROCESSADOS / "historico_volume_entrada.parquet"


def formatar_nome_cliente(nome: str, limite: int = TAMANHO_MAXIMO_NOME_CLIENTE) -> str:
    """Padroniza e trunca nome de clientes longos."""
    if pd.isna(nome):
        return "NÃO INFORMADO"
    nome_limpo = str(nome).strip().upper()
    if len(nome_limpo) > limite:
        return f"{nome_limpo[:limite]}..."
    return nome_limpo


def limpar_numero_br(serie: pd.Series) -> pd.Series:
    """Converte padrão '179.400,00' ou '1300' para float real do Python."""
    return pd.to_numeric(
        serie.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip(),
        errors="coerce"
    ).fillna(0.0)


def consolidar_relatorios_volume_entrada() -> tuple[bool, str, int]:
    """
    Lê, limpa, deduplica notas fiscais e converte relatórios de volumes de entrada para Parquet.
    """
    if not PASTA_VOLUME_ENTRADA.exists():
        return False, f"Pasta {PASTA_VOLUME_ENTRADA} não encontrada.", 0

    arquivos = list(PASTA_VOLUME_ENTRADA.glob("*.csv")) + list(PASTA_VOLUME_ENTRADA.glob("*.CSV"))
    arquivos = [arq for arq in arquivos if not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum arquivo CSV encontrado em data/volume_entrada/.", 0

    lista_dfs = []
    # Mapeamento: N(13), Q(16), R(17), S(18), W(22)
    colunas_alvo = [13, 16, 17, 18, 22]

    for arq in arquivos:
        try:
            try:
                df_temp = pd.read_csv(
                    arq, sep=",", header=None, usecols=colunas_alvo, dtype=str, encoding="utf-8-sig"
                )
            except UnicodeDecodeError:
                df_temp = pd.read_csv(
                    arq, sep=",", header=None, usecols=colunas_alvo, dtype=str, encoding="latin1"
                )

            df_temp = df_temp.rename(columns={
                13: "Cliente_Bruto",
                16: "Data_Entrada",
                17: "Nota_Fiscal",
                18: "Volumes",
                22: "Valor_Total"
            })

            lista_dfs.append(df_temp)

        except Exception as e:
            return False, f"Erro ao ler {arq.name}: {str(e)}", 0

    if not lista_dfs:
        return False, "Nenhum dado válido extraído.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # 1. Filtro de Datas Válidas
    df_consolidado["Data_Entrada"] = pd.to_datetime(
        df_consolidado["Data_Entrada"], errors="coerce", dayfirst=True
    )
    df_consolidado = df_consolidado.dropna(subset=["Data_Entrada"]).reset_index(drop=True)
    df_consolidado = df_consolidado.sort_values(by="Data_Entrada", ascending=True)

    # 2. Colunas Temporais
    df_consolidado["Ano"] = df_consolidado["Data_Entrada"].dt.year
    df_consolidado["Mes"] = df_consolidado["Data_Entrada"].dt.month
    df_consolidado["Ano_Mes"] = df_consolidado["Data_Entrada"].dt.strftime("%Y-%m")
    df_consolidado["Dia"] = df_consolidado["Data_Entrada"].dt.day

    # 3. Tratamento de Clientes
    df_consolidado["Cliente_Original"] = df_consolidado["Cliente_Bruto"].astype(str).str.strip().str.upper()
    df_consolidado["Cliente_Exibicao"] = df_consolidado["Cliente_Original"].apply(formatar_nome_cliente)
    df_consolidado = df_consolidado.drop(columns=["Cliente_Bruto"])

    # 4. Tratamento Numérico e Deduplicação por Documento/NF
    df_consolidado["Volumes"] = limpar_numero_br(df_consolidado["Volumes"]).astype(int)
    df_consolidado["Valor_Total"] = limpar_numero_br(df_consolidado["Valor_Total"])
    df_consolidado["Nota_Fiscal"] = df_consolidado["Nota_Fiscal"].astype(str).str.strip()

    # DEDUPLICAÇÃO: Evita somar a mesma NF de volume mais de uma vez
    df_consolidado = df_consolidado.drop_duplicates(
        subset=["Nota_Fiscal", "Cliente_Original", "Data_Entrada", "Volumes", "Valor_Total"]
    ).reset_index(drop=True)

    # 5. Gravação Atômica em Parquet
    arquivo_temp = ARQUIVO_PARQUET_VOLUME_ENTRADA.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_VOLUME_ENTRADA)

    return True, f"Sucesso! {len(df_consolidado):,} notas/registros de volume de entrada consolidados.", len(df_consolidado)


if __name__ == "__main__":
    sucesso, msg, total = consolidar_relatorios_volume_entrada()
    print(f"Resultado: {msg}")