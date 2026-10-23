import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# --- 1. CONFIGURAÇÃO BASE ---
st.set_page_config(page_title="Painel Executivo Logcare", page_icon="📦", layout="wide")

# ORDEM DE CSS: Transformando números soltos em Cartões Executivos
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #1E1E1E;
        border-radius: 8px;
        padding: 15px 20px;
        border-left: 5px solid #00BBA9;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS REAIS ---
from src.config.settings import ARQUIVO_PARQUET_SAIDA, ARQUIVO_PARQUET_ESTOQUE

@st.cache_data
def carregar_dados():
    # 1. Carrega Expedição (Saída)
    if ARQUIVO_PARQUET_SAIDA.exists():
        df_sai = pd.read_parquet(ARQUIVO_PARQUET_SAIDA)
    else:
        st.error("Ficheiro Parquet de Saída não encontrado.")
        df_sai = pd.DataFrame()
    
    if not df_sai.empty:
        col_cidade = "Cidade" if "Cidade" in df_sai.columns else "CIDADE"
        df_sai["CIDADE_LIMPA"] = df_sai[col_cidade].astype(str).str.upper().str.strip() if col_cidade in df_sai.columns else "NÃO INFORMADA"
        df_sai["Data_Real"] = pd.to_datetime(df_sai["Data_Emissao"], errors="coerce")
        df_sai["Dia_Apenas"] = df_sai["Data_Real"].dt.strftime("%Y-%m-%d")
        if "Ano_Mes" not in df_sai.columns:
            df_sai["Ano_Mes"] = df_sai["Data_Real"].dt.strftime("%Y-%m")

    # --- 2. MOTOR DE DADOS REAIS ---
from src.config.settings import ARQUIVO_PARQUET_SAIDA, ARQUIVO_PARQUET_ESTOQUE, ARQUIVO_PARQUET_DEVOLUCAO

@st.cache_data
def carregar_dados():
    # 1. Carrega Expedição (Saída)
    df_sai = pd.read_parquet(ARQUIVO_PARQUET_SAIDA) if ARQUIVO_PARQUET_SAIDA.exists() else pd.DataFrame()
    if not df_sai.empty:
        col_cidade = "Cidade" if "Cidade" in df_sai.columns else "CIDADE"
        df_sai["CIDADE_LIMPA"] = df_sai[col_cidade].astype(str).str.upper().str.strip() if col_cidade in df_sai.columns else "NÃO INFORMADA"
        df_sai["Data_Real"] = pd.to_datetime(df_sai["Data_Emissao"], errors="coerce")
        df_sai["Dia_Apenas"] = df_sai["Data_Real"].dt.strftime("%Y-%m-%d")
        if "Ano_Mes" not in df_sai.columns:
            df_sai["Ano_Mes"] = df_sai["Data_Real"].dt.strftime("%Y-%m")

    # 2. Carrega Armazenagem (Estoque)
    df_est = pd.read_parquet(ARQUIVO_PARQUET_ESTOQUE) if ARQUIVO_PARQUET_ESTOQUE.exists() else pd.DataFrame()
    if not df_est.empty:
        df_est["Saldo"] = pd.to_numeric(df_est["Saldo"], errors="coerce").fillna(0)
        # Limpeza Financeira Corrigida
        if "Valor" in df_est.columns:
            # Se for texto (com pontos e vírgulas), nós limpamos e criamos a nova coluna
            if df_est["Valor"].dtype == object:
                df_est["Valor_Numerico"] = df_est["Valor"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                df_est["Valor_Numerico"] = pd.to_numeric(df_est["Valor_Numerico"], errors="coerce").fillna(0)
            else:
                # A ORDEM NOVA: Se já for um número nativo, apenas copie para a nova coluna!
                df_est["Valor_Numerico"] = pd.to_numeric(df_est["Valor"], errors="coerce").fillna(0)
        else:
            df_est["Valor_Numerico"] = 0
            
        # A Mágica: Multiplica linha por linha instantaneamente
        df_est["Capital_Imobilizado"] = df_est["Saldo"] * df_est["Valor_Numerico"]

    # 3. Carrega Logística Reversa (Devoluções)
    df_dev = pd.read_parquet(ARQUIVO_PARQUET_DEVOLUCAO) if ARQUIVO_PARQUET_DEVOLUCAO.exists() else pd.DataFrame()
    if not df_dev.empty:
        # A Ordem de Limpeza Bruta
        df_dev = df_dev[df_dev["Operação"].astype(str).str.strip().str.upper() == "ENTRADA"]
        df_dev = df_dev[df_dev["Observação"].astype(str).str.contains("Retorno de Devolução", case=False, na=False)]
        
        # A Ordem de Extração Inteligente (Regex) - BLINDADA CONTRA MAIÚSCULAS
        texto_obs = df_dev["Observação"].astype(str).str.upper()
        df_dev["Qtd_Boa"] = texto_obs.str.extract(r'QTD BOA:\s*(\d+)', expand=False).astype(float).fillna(0)
        df_dev["Qtd_Avaria"] = texto_obs.str.extract(r'QTD AVARIA:\s*(\d+)', expand=False).astype(float).fillna(0)
        df_dev["Entrada"] = pd.to_numeric(df_dev["Entrada"], errors="coerce").fillna(0)
        
        df_dev["Data_Real"] = pd.to_datetime(df_dev["Data"], format="%d/%m/%Y %H:%M", errors="coerce")
        df_dev["Ano_Mes"] = df_dev["Data_Real"].dt.strftime("%Y-%m")

    return df_sai, df_est, df_dev

df_saida_bruto, df_estoque_bruto, df_dev_bruto = carregar_dados()

# --- 3. BARRA LATERAL (FILTROS GLOBAIS) ---
st.sidebar.title("Filtros")

# Filtro de Mês (Expedição)
lista_meses = sorted(df_saida_bruto["Ano_Mes"].dropna().unique().tolist(), reverse=True) if not df_saida_bruto.empty else []
if lista_meses: lista_meses.insert(0, "Todos")
mes_selecionado = st.sidebar.selectbox("Período de Análise (Expedição):", lista_meses)

# Filtro de Estado (UF para Expedição e Mapa)
lista_estados = sorted(df_saida_bruto["UF"].dropna().astype(str).unique().tolist()) if not df_saida_bruto.empty and "UF" in df_saida_bruto.columns else []
if lista_estados: lista_estados.insert(0, "Todos")
estado_selecionado = st.sidebar.selectbox("Filtro Geográfico (Estado):", lista_estados) if lista_estados else "Todos"

# Filtro de Base (Estoque)
lista_bases = sorted(df_estoque_bruto["Base"].dropna().unique().tolist()) if not df_estoque_bruto.empty else []
if lista_bases: lista_bases.insert(0, "Todas as Bases")
base_selecionada = st.sidebar.selectbox("Polo Logístico (Estoque):", lista_bases)

# --- 4. CÁLCULOS DE INTELIGÊNCIA (Com Duplo Filtro) ---
# 1º Passo: Aplica o filtro de Estado (Afeta cartões, mapa e gráfico histórico)
if estado_selecionado != "Todos" and "UF" in df_saida_bruto.columns:
    df_base_ativa = df_saida_bruto[df_saida_bruto["UF"] == estado_selecionado]
else:
    df_base_ativa = df_saida_bruto

# 2º Passo: Aplica o filtro de Mês (Afeta apenas cartões e mapa)
if mes_selecionado == "Todos":
    df_atual = df_base_ativa
    df_anterior = pd.DataFrame()
    texto_delta = ""
else:
    df_atual = df_base_ativa[df_base_ativa["Ano_Mes"] == mes_selecionado]
    meses_cronologicos = sorted(df_base_ativa["Ano_Mes"].dropna().unique().tolist())
    indice_atual = meses_cronologicos.index(mes_selecionado) if mes_selecionado in meses_cronologicos else 0
    
    if indice_atual > 0:
        mes_passado = meses_cronologicos[indice_atual - 1]
        df_anterior = df_base_ativa[df_base_ativa["Ano_Mes"] == mes_passado]
        texto_delta = " vs mês anterior"
    else:
        df_anterior = pd.DataFrame()
        texto_delta = ""

# --- 5. TELA FRONTAL: CABEÇALHO E CARTÕES ---
col_logo, col_espaco, col_titulo = st.columns([1.5, 0.5, 8], vertical_alignment="center")

with col_logo:
    pasta_media = Path("media")
    if pasta_media.exists():
        logos = list(pasta_media.glob("*.png")) + list(pasta_media.glob("*.jpg"))
        if logos: st.image(str(logos[0]), use_container_width=True)

with col_titulo:
    st.title("Métricas de Esforço Operacional")

# Cálculos Matemáticos Atuais
total_pedidos_atual = df_atual["numero_pedido"].nunique()
total_pecas_atual = df_atual["QUANTIDADE"].sum()
cidades_atendidas = df_atual["CIDADE_LIMPA"].nunique()
estados_atendidos = df_atual["UF"].nunique() if "UF" in df_atual.columns else 0

# Cálculos do Mês Anterior para os Deltas
total_pecas_ant = df_anterior["QUANTIDADE"].sum() if not df_anterior.empty else 0
total_pedidos_ant = df_anterior["numero_pedido"].nunique() if not df_anterior.empty else 0

delta_pecas, delta_pedidos = None, None
if total_pecas_ant > 0:
    pct_pecas = ((total_pecas_atual - total_pecas_ant) / total_pecas_ant) * 100
    delta_pecas = f"{pct_pecas:.1f}%{texto_delta}"
if total_pedidos_ant > 0:
    pct_pedidos = ((total_pedidos_atual - total_pedidos_ant) / total_pedidos_ant) * 100
    delta_pedidos = f"{pct_pedidos:.1f}%{texto_delta}"

if not df_atual.empty:
    agrupamento_dias = df_atual.groupby("Dia_Apenas")["QUANTIDADE"].sum()
    dia_pico, valor_pico = agrupamento_dias.idxmax(), agrupamento_dias.max()
else:
    dia_pico, valor_pico = "-", 0

# A ORDEM NOVA: 5 Colunas para os Cartões
col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric(label="Volume Físico (Peças)", value=f"{total_pecas_atual:,.0f}".replace(",", "."), delta=delta_pecas)
with col2: st.metric(label="Pedidos Despachados", value=f"{total_pedidos_atual:,.0f}".replace(",", "."), delta=delta_pedidos)
with col3: st.metric(label="Capilaridade (Estados)", value=estados_atendidos)
with col4: st.metric(label="Capilaridade (Cidades)", value=f"{cidades_atendidas:,.0f}".replace(",", "."))
with col5: st.metric(label="Pico Máximo de Esforço", value=f"{valor_pico:,.0f}".replace(",", "."), delta=f"Ocorrido em {dia_pico}", delta_color="off")

st.write("---")

# --- 6. ESTRUTURA DE ABAS ---
aba_operacional, aba_estoque,aba_reversa, aba_mapa = st.tabs(["📈 Visão Operacional", "🏢 Armazenagem (Estoque)","♻️ Logística Reversa", "📍 Capilaridade (Mapa)"])

with aba_operacional:
    st.subheader("Curva de Tendência de Expedição (Histórico Global)")
    
    if not df_base_ativa.empty:
        df_tendencia = df_base_ativa.groupby("Ano_Mes")["QUANTIDADE"].sum().reset_index()
        df_tendencia = df_tendencia.sort_values("Ano_Mes")
        
        fig_linha = px.line(
            df_tendencia, 
            x="Ano_Mes", 
            y="QUANTIDADE", 
            markers=True,
            text="QUANTIDADE",
            title="Evolução do Volume Físico Expedido",
            color_discrete_sequence=["#00BBA9"]
        )
        
        fig_linha.update_traces(textposition="top center")
        fig_linha.update_layout(
            yaxis_title="Total de Peças",
            xaxis_title="",
            hoverlabel=dict(font_color="white", bgcolor="#1E1E1E"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        st.plotly_chart(fig_linha, use_container_width=True)
    else:
        st.warning("Não há dados históricos suficientes para traçar a curva.")

with aba_estoque:
    st.subheader(f"Posição Física e Financeira - {base_selecionada}")
    
    if not df_estoque_bruto.empty:
        # A Ordem do Filtro Isolado: Filtra o estoque sem mexer na expedição
        if base_selecionada == "Todas as Bases":
            df_est_filtrado = df_estoque_bruto
        else:
            df_est_filtrado = df_estoque_bruto[df_estoque_bruto["Base"] == base_selecionada]
            
        # Cálculos Gerenciais
        total_pecas_est = df_est_filtrado["Saldo"].sum()
        capital_total = df_est_filtrado["Capital_Imobilizado"].sum()
        skus_ativos = df_est_filtrado["Produto"].nunique()
        
        # Cartões de Estoque
        ce1, ce2, ce3 = st.columns(3)
        with ce1: st.metric(label="Carga de Armazenagem (Peças)", value=f"{total_pecas_est:,.0f}".replace(",", "."))
        with ce2: st.metric(label="Capital Imobilizado (R$)", value=f"R$ {capital_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        with ce3: st.metric(label="Mix de Produtos (SKUs Únicos)", value=skus_ativos)
        
        st.write("---")
        
        # Gráfico: Curva ABC de Produtos (Top 10 mais estocados)
        st.subheader("Top 10 Sub-Grupos em Prateleira")
        df_produtos = df_est_filtrado.groupby("Sub-Grupo")["Saldo"].sum().reset_index()
        df_produtos = df_produtos.sort_values("Saldo", ascending=False).head(10)
        
        fig_prod = px.bar(
            df_produtos, 
            x="Saldo", 
            y="Sub-Grupo", 
            orientation="h",
            text_auto=True,
            color_discrete_sequence=["#00BBA9"]
        )
        fig_prod.update_layout(yaxis={'categoryorder':'total ascending'}, yaxis_title="", xaxis_title="Peças em Estoque", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_prod, use_container_width=True)
        
    else:
        st.warning("Dados de estoque indisponíveis no momento.")

with aba_reversa:
    st.subheader(f"Auditoria de Retornos - {mes_selecionado}")
    
    if mes_selecionado == "Todos":
        df_dev_atual = df_dev_bruto
    else:
        df_dev_atual = df_dev_bruto[df_dev_bruto["Ano_Mes"] == mes_selecionado]
        
    if not df_dev_atual.empty:
        # Filtro de Avaria na tela
        mostrar_apenas_avarias = st.checkbox("Filtrar apenas retornos com Avaria/Perda")
        if mostrar_apenas_avarias:
            df_dev_atual = df_dev_atual[df_dev_atual["Qtd_Avaria"] > 0]
            
        c_rev1, c_rev2 = st.columns([1, 2])
        
        with c_rev1:
            st.markdown("**Índice de Reaproveitamento**")
            total_boa = df_dev_atual["Qtd_Boa"].sum()
            total_avaria = df_dev_atual["Qtd_Avaria"].sum()
            
            # Ordem: Só desenha a pizza se existirem peças extraídas!
            if total_boa + total_avaria > 0:
                df_pie = pd.DataFrame({'Estado': ['Pronto para Reuso', 'Avaria / Perda'], 'Volume': [total_boa, total_avaria]})
                fig_pie = px.pie(df_pie, values='Volume', names='Estado', hole=0.5, color='Estado', color_discrete_map={'Pronto para Reuso': '#00BBA9', 'Avaria / Perda': '#FF5252'})
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("As quantidades extraídas estão zeradas ou não há retornos processados para este período.")
            
        with c_rev2:
            st.markdown("**Volume Devolvido por Tipo de Produto**")
            df_tipo = df_dev_atual.groupby("Tipo Produto")[["Qtd_Boa", "Qtd_Avaria"]].sum().reset_index()
            fig_bar_rev = px.bar(df_tipo, x="Tipo Produto", y=["Qtd_Boa", "Qtd_Avaria"], title="", color_discrete_map={"Qtd_Boa": "#00BBA9", "Qtd_Avaria": "#FF5252"}, barmode="stack")
            fig_bar_rev.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title="Estado")
            st.plotly_chart(fig_bar_rev, use_container_width=True)
            
        
    else:
        st.info("Sem registo de retornos para os filtros selecionados.")

with aba_mapa:
    st.subheader(f"Capilaridade Geográfica - {mes_selecionado}")
    
    if not df_atual.empty and "UF" in df_atual.columns:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter
        import os
        
        # 1. Cria a Chave de Busca única (Cidade - UF) para não pesquisar a mesma cidade duas vezes
        df_atual_mapa = df_atual.copy()
        df_atual_mapa["Chave_Busca"] = df_atual_mapa["CIDADE_LIMPA"] + " - " + df_atual_mapa["UF"].astype(str).str.upper().str.strip()
        
        cidades_unicas = df_atual_mapa["Chave_Busca"].unique()
        
        # 2. Carrega a "Memória" (Cache) do computador
        arquivo_cache = Path("geocache_entregas.csv")
        if arquivo_cache.exists():
            df_cache = pd.read_csv(arquivo_cache)
        else:
            df_cache = pd.DataFrame(columns=["Chave_Busca", "Latitude", "Longitude"])
            
        # 3. Descobre quem é novo e precisa ser pesquisado na internet
        cidades_para_pesquisar = [cid for cid in cidades_unicas if cid not in df_cache["Chave_Busca"].values and cid != "NÃO INFORMADA - NAN"]
        
        # 4. Vai à internet pesquisar apenas as cidades novas
        if cidades_para_pesquisar:
            with st.status(f"A mapear {len(cidades_para_pesquisar)} novas cidades. Isto acontece apenas uma vez...", expanded=True) as status:
                geolocator = Nominatim(user_agent="logcare_expedicao")
                geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)
                
                novos_dados = []
                barra_progresso = st.progress(0)
                
                for i, cidade in enumerate(cidades_para_pesquisar):
                    # Tenta encontrar a coordenada
                    try:
                        busca = f"{cidade.split(' - ')[0]}, {cidade.split(' - ')[1]}, Brasil"
                        location = geocode(busca)
                        if location:
                            novos_dados.append({"Chave_Busca": cidade, "Latitude": location.latitude, "Longitude": location.longitude})
                    except Exception:
                        pass # Se a internet falhar numa cidade, ignora e segue em frente
                    
                    # Atualiza a barra de progresso visual
                    barra_progresso.progress((i + 1) / len(cidades_para_pesquisar))
                
                # Guarda as novas descobertas na memória para sempre
                if novos_dados:
                    df_novos = pd.DataFrame(novos_dados)
                    df_cache = pd.concat([df_cache, df_novos], ignore_index=True)
                    df_cache.to_csv(arquivo_cache, index=False)
                
                status.update(label="Mapeamento concluído e guardado em Cache!", state="complete", expanded=False)

        # 5. Cruza os dados das encomendas com as coordenadas conhecidas
        df_plot = pd.merge(df_atual_mapa, df_cache, on="Chave_Busca", how="left")
        
        # Remove as linhas que não têm coordenada para não dar erro no mapa
        df_plot = df_plot.dropna(subset=["Latitude", "Longitude"])
        
        if not df_plot.empty:
            # Agrupa o volume por cidade para fazer as bolhas do mapa maiores onde há mais esforço
            df_mapa_agrupado = df_plot.groupby(["Chave_Busca", "Latitude", "Longitude"])["QUANTIDADE"].sum().reset_index()
            
            # 6. Desenha o Mapa Colorido e Nítido (open-street-map)
            fig_mapa = px.scatter_map(
                df_mapa_agrupado,
                lat="Latitude",
                lon="Longitude",
                size="QUANTIDADE", # Bolhas maiores onde entregou mais peças
                hover_name="Chave_Busca",
                hover_data={"QUANTIDADE": True, "Latitude": False, "Longitude": False},
                zoom=4, # Um pouco mais de zoom para focar no Brasil
                center={"lat": -15.0, "lon": -52.0},
                map_style="open-street-map", # A NOVA ORDEM: Mapa detalhado com estados
                color_discrete_sequence=["#00BBA9"]
            )
            
            # Garante que as bolhas fiquem fortes e visíveis
            fig_mapa.update_traces(marker=dict(opacity=0.9, sizemin=5))
            
            fig_mapa.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
            st.plotly_chart(fig_mapa, use_container_width=True)
        else:
            st.warning("Não foi possível plotar as cidades no mapa.")
    else:
        st.warning("Sem dados suficientes ou coluna 'UF' ausente para gerar o mapa.")