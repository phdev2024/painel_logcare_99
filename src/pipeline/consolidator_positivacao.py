"""
Pipeline de Consolidação: Relatórios de Positivação (Trabalho de Campo)
Foco no esforço de deslocação, classificação de Zonas de SP e equipa de rua.
"""

import pandas as pd
from pathlib import Path
import sys
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

# Garante que o Python encontra a pasta src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_POSITIVACAO, ARQUIVO_PARQUET_POSITIVACAO, DATA_DIR

CACHE_GEO_POS = DATA_DIR / "geocache_positivacao.csv"

def limpar_cep(cep) -> str:
    cep_limpo = str(cep).replace(".0", "").replace("-", "").replace(".", "").strip()
    if cep_limpo == "NAN" or cep_limpo == "NONE" or cep_limpo == "":
        return "00000000"
    return cep_limpo.zfill(8)

def classificar_zona_sp(cidade: str, cep: str) -> str:
    """Algoritmo de roteirização: Transforma Cidades e CEPs em Macrorregiões."""
    cid = str(cidade).upper().strip()
    prefixo_cep = str(cep)[:2]

    if cid in ["SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL", "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA"]:
        return "ABC Paulista"
    elif cid in ["GUARULHOS", "OSASCO", "BARUERI", "CARAPICUIBA", "ITAPEVI", "JANDIRA", "SANTANA DE PARNAIBA", "TABOAO DA SERRA", "EMBU DAS ARTES", "COTIA"]:
        return "Grande SP"
    elif cid in ["SAO PAULO", "SÃO PAULO", "SP"]:
        if prefixo_cep == "01": return "Zona Central"
        elif prefixo_cep == "02": return "Zona Norte"
        elif prefixo_cep in ["03", "08"]: return "Zona Leste"
        elif prefixo_cep == "04": return "Zona Sul"
        elif prefixo_cep == "05": return "Zona Oeste"
        else: return "Capital - Outros"
    else:
        return "Interior / Litoral"

def carregar_cache_positivacao():
    if CACHE_GEO_POS.exists():
        return pd.read_csv(CACHE_GEO_POS, dtype=str)
    return pd.DataFrame(columns=["CEP", "Latitude", "Longitude"])

def consolidar_relatorios_positivacao() -> tuple[bool, str, int]:
    if not PASTA_POSITIVACAO.exists():
        return False, f"Pasta {PASTA_POSITIVACAO} não encontrada.", 0

    arquivos = [arq for arq in PASTA_POSITIVACAO.iterdir() if arq.is_file() and arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]

    if not arquivos:
        return False, "Nenhum ficheiro Excel encontrado na pasta data/positivacao/.", 0

    lista_dfs = []
    for arq in arquivos:
        try:
            # Lê o ficheiro todo como texto
            df_temp = pd.read_excel(arq, dtype=str)
            # O SEGREDO ESTÁ AQUI: Remove os espaços invisíveis de todos os cabeçalhos!
            df_temp.columns = df_temp.columns.astype(str).str.strip()
            lista_dfs.append(df_temp)
        except Exception as e:
            print(f"Erro ao ler {arq.name}: {e}")

    if not lista_dfs:
        return False, "Nenhum dado válido extraído.", 0

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # --- 1. LIMPEZA BASE ---
    # Renomeia as colunas com os nomes que já limpámos os espaços
    df_consolidado = df_consolidado.rename(columns={
        "Positivado": "Nome_Positivador", 
        "Observaçõ": "Observacoes_Campo",
        "Data Finali": "Data_Visita",
        "ID Loja": "ID_Loja",
        "Endereço": "Endereco_Rua"
    })

    # TRAVA DE SEGURANÇA: Se por algum motivo bizarro a coluna não existir, cria-se uma para não dar erro (KeyError)
    for col_essencial in ["Nome_Positivador", "CEP", "Cidade", "Status"]:
        if col_essencial not in df_consolidado.columns:
            df_consolidado[col_essencial] = "NÃO INFORMADO"

    # Foca apenas no trabalho realizado
    df_consolidado["Status"] = df_consolidado["Status"].astype(str).str.strip().str.upper()
    df_consolidado = df_consolidado[df_consolidado["Status"].str.contains("FINALIZADO", na=False)].copy()

    df_consolidado["CEP"] = df_consolidado["CEP"].apply(limpar_cep)
    df_consolidado["Cidade"] = df_consolidado["Cidade"].astype(str).str.strip().str.upper()
    df_consolidado["Nome_Positivador"] = df_consolidado["Nome_Positivador"].astype(str).str.strip().str.upper()

    # --- 2. INTELIGÊNCIA GEOGRÁFICA (ZONAS) ---
    df_consolidado["Zona_Executiva"] = df_consolidado.apply(lambda row: classificar_zona_sp(row["Cidade"], row["CEP"]), axis=1)

    # --- 3. OTIMIZAÇÃO DE COORDENADAS ---
    print("A analisar mapa de rotas (Geocodificação por CEP)...")
    df_cache = carregar_cache_positivacao()
    ceps_unicos = df_consolidado["CEP"].unique()
    
    ceps_para_buscar = [c for c in ceps_unicos if c not in df_cache["CEP"].values and c != "00000000"]
    
    if ceps_para_buscar:
        print(f"A mapear {len(ceps_para_buscar)} novos locais no mapa. Pode demorar alguns segundos...")
        geolocator = RateLimiter(Nominatim(user_agent="logcare_campo_v2"), min_delay_seconds=1.1)
        novos_registos = []
        
        for cep in ceps_para_buscar:
            try:
                location = geolocator(f"{cep}, Brasil")
                if location:
                    novos_registos.append({"CEP": cep, "Latitude": location.latitude, "Longitude": location.longitude})
            except:
                pass
                
        if novos_registos:
            df_novos = pd.DataFrame(novos_registos)
            df_cache = pd.concat([df_cache, df_novos], ignore_index=True)
            df_cache.to_csv(CACHE_GEO_POS, index=False)

    df_consolidado = df_consolidado.merge(df_cache, on="CEP", how="left")
    df_consolidado["Latitude"] = pd.to_numeric(df_consolidado["Latitude"], errors="coerce").fillna(-23.5505)
    df_consolidado["Longitude"] = pd.to_numeric(df_consolidado["Longitude"], errors="coerce").fillna(-46.6333)

    # --- 4. GRAVAÇÃO ---
    arquivo_temp = ARQUIVO_PARQUET_POSITIVACAO.with_suffix(".tmp")
    df_consolidado.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_POSITIVACAO)

    return True, f"Sucesso! {len(df_consolidado):,} visitas de campo mapeadas.", len(df_consolidado)

if __name__ == "__main__":
    print("Iniciando processamento da Positivação...")
    sucesso, msg, total = consolidar_relatorios_positivacao()
    print(msg)
    
    if sucesso:
        df_teste = pd.read_parquet(ARQUIVO_PARQUET_POSITIVACAO)
        print("\n--- RESUMO DO ESFORÇO DE CAMPO ---")
        print(f"Total de Visitas Realizadas: {len(df_teste):,.0f}".replace(",", "."))
        print(f"Lojas Únicas Visitadas: {df_teste['ID_Loja'].nunique():,.0f}".replace(",", "."))
        print(f"Positivadores em Campo: {df_teste['Nome_Positivador'].nunique()}")
        print("\n--- VISITAS POR MACRORREGIÃO ---")
        print(df_teste["Zona_Executiva"].value_counts().to_string())