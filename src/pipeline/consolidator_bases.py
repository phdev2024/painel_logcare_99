"""
Pipeline de Consolidação: Cadastro de Bases e Hubs
Geocodificação Inteligente, Fallback para Capitais e Anti-Empilhamento.
"""

import math
import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from collections import defaultdict
from pathlib import Path
import sys

# --- CORREÇÃO DE ROTA: Garante que o Python encontra a pasta src ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import PASTA_CADASTRO_BASES, ARQUIVO_PARQUET_MAPA_BASES, DATA_DIR

# Ficheiro de cache local para não sobrecarregar a API
CACHE_GEO = DATA_DIR / "geocache_bases.csv"

# Dicionário de Segurança: Capitais do Brasil
CAPITAIS_BR = {
    "AC": (-9.974, -67.807), "AL": (-9.665, -35.735), "AP": (0.034, -51.066),
    "AM": (-3.101, -60.025), "BA": (-12.971, -38.510), "CE": (-3.717, -38.543),
    "DF": (-15.779, -47.929), "ES": (-20.315, -40.312), "GO": (-16.686, -49.264),
    "MA": (-2.530, -44.302), "MT": (-15.595, -56.096), "MS": (-20.442, -54.646),
    "MG": (-19.920, -43.937), "PA": (-1.455, -48.502), "PB": (-7.115, -34.863),
    "PR": (-25.428, -49.273), "PE": (-8.047, -34.877), "PI": (-5.089, -42.801),
    "RJ": (-22.902, -43.207), "RN": (-5.794, -35.211), "RS": (-30.027, -51.228),
    "RO": (-8.761, -63.903), "RR": (2.819, -60.671), "SC": (-27.596, -48.549),
    "SP": (-23.550, -46.633), "SE": (-10.947, -37.073), "TO": (-10.212, -48.360)
}

def carregar_cache() -> pd.DataFrame:
    if CACHE_GEO.exists():
        return pd.read_csv(CACHE_GEO)
    return pd.DataFrame(columns=["Chave_Busca", "Latitude", "Longitude"])

def salvar_cache(df_cache: pd.DataFrame):
    df_cache.drop_duplicates(subset=["Chave_Busca"], inplace=True)
    df_cache.to_csv(CACHE_GEO, index=False)

def obter_coordenadas(cidade, uf, df_cache, geolocator):
    cidade_str = str(cidade).strip().upper()
    uf_str = str(uf).strip().upper()
    chave = f"{cidade_str} - {uf_str}"

    filtro = df_cache[df_cache["Chave_Busca"] == chave]
    if not filtro.empty:
        return filtro.iloc[0]["Latitude"], filtro.iloc[0]["Longitude"], df_cache

    query_busca = f"{cidade_str}, {uf_str}, Brasil"
    
    try:
        location = geolocator(query_busca)
        if location:
            lat, lon = location.latitude, location.longitude
            novo_registro = pd.DataFrame([{"Chave_Busca": chave, "Latitude": lat, "Longitude": lon}])
            df_cache = pd.concat([df_cache, novo_registro], ignore_index=True)
            salvar_cache(df_cache)
            return lat, lon, df_cache
    except Exception:
        pass

    lat_fall, lon_fall = CAPITAIS_BR.get(uf_str, (-15.779, -47.929))
    return lat_fall, lon_fall, df_cache

def consolidar_bases() -> tuple[bool, str, int]:
    if not PASTA_CADASTRO_BASES.exists():
        return False, f"Pasta {PASTA_CADASTRO_BASES} não encontrada.", 0

    arquivos = [arq for arq in PASTA_CADASTRO_BASES.iterdir() if arq.suffix.lower() in [".xlsx", ".xls"] and not arq.name.startswith("~$")]
    
    if not arquivos:
        return False, "Nenhum ficheiro Excel de bases encontrado.", 0

    df = pd.read_excel(arquivos[0])

    for col in ["Tipo", "UF", "Cidade", "STATUS"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    for col in ["RAIO_ATENDIMENTO", "EQUIPE_ALOCADA", "VEICULOS_OPERANTES"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df_cache = carregar_cache()
    geolocator = RateLimiter(Nominatim(user_agent="painel_logcare_v8"), min_delay_seconds=1.2)

    lats_originais, lons_originais = [], []
    for _, row in df.iterrows():
        lat, lon, df_cache = obter_coordenadas(row.get("Cidade", ""), row.get("UF", ""), df_cache, geolocator)
        lats_originais.append(lat)
        lons_originais.append(lon)

    # --- DESEMPILHADOR UNIVERSAL ---
    coord_counts = defaultdict(int)
    lats_finais, lons_finais = [], []

    for lat, lon in zip(lats_originais, lons_originais):
        chave = (round(lat, 3), round(lon, 3))
        contagem = coord_counts[chave]
        coord_counts[chave] += 1

        if contagem > 0:
            offset_lat = (contagem * 0.015) * (1 if contagem % 2 == 0 else -1)
            offset_lon = (contagem * 0.015) * (1 if contagem % 3 == 0 else -1)
            lats_finais.append(lat + offset_lat)
            lons_finais.append(lon + offset_lon)
        else:
            lats_finais.append(lat)
            lons_finais.append(lon)

    df["Latitude"] = lats_finais
    df["Longitude"] = lons_finais

    # Gravação atómica em Parquet
    arquivo_temp = ARQUIVO_PARQUET_MAPA_BASES.with_suffix(".tmp")
    df.to_parquet(arquivo_temp, engine="pyarrow", index=False)
    
    if arquivo_temp.exists():
        arquivo_temp.replace(ARQUIVO_PARQUET_MAPA_BASES)

    return True, f"Sucesso! {len(df)} bases e hubs consolidados.", len(df)

if __name__ == "__main__":
    sucesso, msg, total = consolidar_bases()
    print(msg)