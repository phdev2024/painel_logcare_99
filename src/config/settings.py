"""
Configurações Globais do Painel de Bases e Hubs
Centraliza caminhos de pastas, nomes de arquivos e identidade visual.
"""
from pathlib import Path

# --- 1. MAPEAMENTO DE PASTAS RAIZ ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
SRC_DIR = BASE_DIR / "src"

# --- 2. SUBPASTAS DE DADOS BRUTOS ---
PASTA_ENTRADA = DATA_DIR / "entrada"
PASTA_VOLUME_ENTRADA = DATA_DIR / "volume"
PASTA_SAIDA = DATA_DIR / "saida"
PASTA_ESTOQUE = DATA_DIR / "estoque"
PASTA_DEVOLUCAO = DATA_DIR / "devolucao"
PASTA_POSITIVACAO = DATA_DIR / "positivacao"
PASTA_PACK = DATA_DIR / "pack"
PASTA_DCE = DATA_DIR / "DCE"
PASTA_CADASTRO_BASES = DATA_DIR / "Cadastro_bases"

# Pasta onde os Parquets rápidos serão salvos
PASTA_PROCESSADOS = DATA_DIR / "processed"

# Cria a pasta processed automaticamente se ela não existir
PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)

# --- 3. ARQUIVOS CONSOLIDADOS (PARQUETS) ---
ARQUIVO_PARQUET_ENTRADA = PASTA_PROCESSADOS / "historico_entrada.parquet"
ARQUIVO_PARQUET_VOLUME_ENTRADA = PASTA_PROCESSADOS / "historico_volume_entrada.parquet"
ARQUIVO_PARQUET_SAIDA = PASTA_PROCESSADOS / "historico_saida.parquet"
ARQUIVO_PARQUET_ESTOQUE = PASTA_PROCESSADOS / "historico_estoque.parquet"
ARQUIVO_PARQUET_DEVOLUCAO = PASTA_PROCESSADOS / "historico_devolucao.parquet"
ARQUIVO_PARQUET_MAPA_BASES = PASTA_PROCESSADOS / "geocache_bases.parquet"
ARQUIVO_PARQUET_PACK = PASTA_PROCESSADOS / "historico_pack.parquet"
ARQUIVO_PARQUET_POSITIVACAO = PASTA_PROCESSADOS / "historico_positivacao.parquet"

# --- 4. IDENTIDADE VISUAL & REGRAS DE NEGÓCIO ---
BRAND_NAME = "LOGCARE LOGÍSTICA"
CLIENT_NAME = "OPERAÇÃO 99"
TAMANHO_MAXIMO_NOME_CLIENTE = 20

COLOR_PRIMARY = "#00BBA9"   # Verde Logcare
COLOR_SECONDARY = "#2D655A" # Verde Escuro
COLOR_ACCENT = "#FFEA00"    # Amarelo Cliente (99)
COLOR_BG_DARK = "#0A1110"   # Fundo Preto/Cinza Escuro
COLOR_CARD_BG = "#12201D"   # Fundo dos Cartões