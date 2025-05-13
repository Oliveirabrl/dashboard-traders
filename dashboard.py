import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import urllib.request
import urllib.error
import re
import numpy as np

# Configurar o layout do Streamlit
st.set_page_config(layout="wide")

# Definir o GID para a aba "FORNECEDOR2"
GID_FORNECEDOR = '1111839866'  # GID da aba "FORNECEDOR2"

# URL de exportação CSV para a aba "FORNECEDOR2"
url_fornecedores = f'https://docs.google.com/spreadsheets/d/14l5BdSDd1dFaKyGHAjgJHIQgGbPs9xU_BfxZDFhaTqY/export?format=csv&gid={GID_FORNECEDOR}'

# Definir os cabeçalhos esperados
fornecedor_headers = [
    'PRODUTO', 'FORNECEDOR', 'MARCA', 'KG da Unidade', 'UNIDADE/EMBALAGEM', 'VALOR UNITÁRIO',
    'MÉDIA/KG', 'VALOR/EMBALAGEM', 'VALOR/TONELADA', 'PREÇO DE VENDA',
    'QUANTIDADE MÍNIMA (Embalagens)', 'LOCAL DE ENTREGA'
]

# Função para carregar os dados
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    try:
        # Ler os dados brutos para depuração
        response = urllib.request.urlopen(url_fornecedores)
        raw_data = response.read().decode('utf-8')
        print("Dados brutos da URL (primeiras 2000 caracteres):")
        print(raw_data[:2000])

        # Contar o número de linhas e colunas no CSV bruto
        lines = raw_data.split('\n')
        print(f"Número de linhas no CSV bruto: {len(lines)}")
        if lines:
            num_columns = len(lines[0].split(','))
            print(f"Número de colunas no CSV bruto: {num_columns}")
        else:
            num_columns = 0

        # Ajustar os cabeçalhos se necessário
        if num_columns != len(fornecedor_headers):
            adjusted_headers = fornecedor_headers[:num_columns]
            if num_columns > len(fornecedor_headers):
                adjusted_headers.extend([f'COLUNA_EXTRA_{i}' for i in range(num_columns - len(fornecedor_headers))])
            print(f"Cabeçalhos ajustados: {adjusted_headers}")
        else:
            adjusted_headers = fornecedor_headers

        # Carregar o CSV, pulando a primeira linha (cabeçalho da planilha)
        df = pd.read_csv(url_fornecedores, names=adjusted_headers, skiprows=1, encoding='utf-8', keep_default_na=False)
        print("Dados brutos carregados pelo pandas:")
        print(df)

        # Processar colunas de texto
        text_columns = [col for col in ['PRODUTO', 'FORNECEDOR', 'MARCA', 'UNIDADE/EMBALAGEM', 'LOCAL DE ENTREGA'] if col in df.columns]
        for col in text_columns:
            df[col] = df[col].astype(str).str.strip()
        print("Dados após conversão de colunas de texto:")
        print(df)

        # Processar colunas numéricas
        numeric_columns = [col for col in ['KG da Unidade', 'VALOR UNITÁRIO', 'MÉDIA/KG', 'VALOR/EMBALAGEM', 'VALOR/TONELADA', 'QUANTIDADE MÍNIMA (Embalagens)'] if col in df.columns]
        for col in numeric_columns:
            df[col] = df[col].astype(str).str.replace('R\\$', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        print("Dados após conversão de colunas numéricas:")
        print(df)

        if 'PREÇO DE VENDA' in df.columns:
            df['PREÇO DE VENDA'] = pd.to_numeric(df['PREÇO DE VENDA'], errors='coerce').fillna(0.0)
        print("Dados finais preparados para o dashboard:")
        print(df)

        return df
    except urllib.error.HTTPError as e:
        st.error(f"Erro ao acessar a URL: {e}")
        st.error("Verifique se a planilha está compartilhada publicamente ('Qualquer pessoa com o link') e se o GID está correto.")
        st.error(f"URL usada: {url_fornecedores}")
        return pd.DataFrame(columns=fornecedor_headers)
    except pd.errors.EmptyDataError:
        st.error("Erro: A aba 'FORNECEDOR2' está vazia ou não contém dados válidos.")
        return pd.DataFrame(columns=fornecedor_headers)
    except Exception as e:
        st.error(f"Erro inesperado ao carregar os dados: {e}")
        return pd.DataFrame(columns=fornecedor_headers)

# Função para extrair unidades e peso por unidade da coluna "UNIDADE/EMBALAGEM"
def parse_unidade_embalagem(unidade_embalagem):
    try:
        # Padrão para extrair "X unidades de Y kg"
        match = re.match(r'(\d+),\d+\s*unidades\s*de\s*([\d,.]+)\s*kg', unidade_embalagem, re.IGNORECASE)
        if match:
            unidades = int(match.group(1).replace(',', ''))
            peso_unidade = float(match.group(2).replace(',', '.'))
            return unidades, peso_unidade
        # Caso o formato seja "X,00"
        match_simple = re.match(r'(\d+),\d+', unidade_embalagem)
        if match_simple:
            unidades = int(match_simple.group(1))
            # Se não houver peso especificado, assumimos que é uma embalagem simples
            return unidades, 0.0
        return 1, 0.0  # Valor padrão se não houver correspondência
    except:
        return 1, 0.0

# Título do dashboard
st.title("Dashboard de Viabilidade")

# Botão para recarregar os dados manualmente
if st.button("Recarregar Dados"):
    st.cache_data.clear()  # Limpar o cache para recarregar os dados
    st.rerun()  # Reexecutar o script para atualizar os dados

# Tabela editável da aba "FORNECEDOR2"
st.subheader("Dados da Aba FORNECEDOR2")

# Carregar os dados
df_fornecedores = load_data()

# Adicionar filtro para a coluna PRODUTO
unique_products = sorted(df_fornecedores['PRODUTO'].unique())
selected_products = st.multiselect("Filtrar por Produto", unique_products, default=unique_products)

# Filtrar o DataFrame com base nos produtos selecionados
if selected_products:
    filtered_df = df_fornecedores[df_fornecedores['PRODUTO'].isin(selected_products)]
else:
    filtered_df = df_fornecedores

# Adicionar colunas para os custos totais e volume, inicializando com 0.0 se não existirem
for cost_column in ['Logística (R$)', 'Impostos (R$)', 'Aduaneiros (R$)', 'Outros Custos (R$)', 'Volume/m³']:
    if cost_column not in filtered_df.columns:
        filtered_df[cost_column] = 0.0

# Configurar a tabela editável com larguras ajustadas
edited_df = st.data_editor(
    filtered_df,
    column_config={
        "PRODUTO": st.column_config.TextColumn(width=100),
        "FORNECEDOR": st.column_config.TextColumn(width=100),
        "MARCA": st.column_config.TextColumn(width=100),
        "KG da Unidade": st.column_config.NumberColumn(width=100, format="%.2f"),
        "UNIDADE/EMBALAGEM": st.column_config.TextColumn(width=150),
        "VALOR UNITÁRIO": st.column_config.NumberColumn(width=100, format="%.2f"),
        "MÉDIA/KG": st.column_config.NumberColumn(width=100, format="%.2f"),
        "VALOR/EMBALAGEM": st.column_config.NumberColumn(width=120, format="%.2f"),
        "VALOR/TONELADA": st.column_config.NumberColumn(width=120, format="%.2f"),
        "QUANTIDADE MÍNIMA (Embalagens)": st.column_config.NumberColumn(
            "QUANTIDADE MÍNIMA (Embalagens)",
            help="Insira a quantidade mínima em número de embalagens",
            format="%.0f",
            required=False,
            width=150
        ),
        "PREÇO DE VENDA": st.column_config.NumberColumn(
            "PREÇO DE VENDA",
            help="Insira o preço de venda em R$/kg",
            format="%.2f",
            required=False,
            width=120
        ),
        "Logística (R$)": st.column_config.NumberColumn(
            "Logística (R$)",
            help="Insira o custo total de logística em R$",
            format="%.2f",
            required=False,
            width=120
        ),
        "Impostos (R$)": st.column_config.NumberColumn(
            "Impostos (R$)",
            help="Insira o custo total de impostos em R$",
            format="%.2f",
            required=False,
            width=120
        ),
        "Aduaneiros (R$)": st.column_config.NumberColumn(
            "Aduaneiros (R$)",
            help="Insira o custo total aduaneiro em R$",
            format="%.2f",
            required=False,
            width=120
        ),
        "Outros Custos (R$)": st.column_config.NumberColumn(
            "Outros Custos (R$)",
            help="Insira outros custos totais em R$",
            format="%.2f",
            required=False,
            width=120
        ),
        "Volume/m³": st.column_config.NumberColumn(
            "Volume/m³",
            help="Insira o volume por embalagem em metros cúbicos (m³)",
            format="%.2f",
            required=False,
            width=100
        ),
        "LOCAL DE ENTREGA": st.column_config.TextColumn(width=150)
    },
    disabled=[col for col in filtered_df.columns if col not in ["QUANTIDADE MÍNIMA (Embalagens)", "PREÇO DE VENDA", "Logística (R$)", "Impostos (R$)", "Aduaneiros (R$)", "Outros Custos (R$)", "Volume/m³"]],
    use_container_width=True,
    num_rows="fixed"
)

# Calcular a margem de lucro com base nos dados editados
st.subheader("Margem de Lucro")
st.markdown("*Insira valores na coluna 'PREÇO DE VENDA', 'QUANTIDADE MÍNIMA (Embalagens)', 'Volume/m³' e nos custos para calcular a margem de lucro e a margem líquida ajustada.*")

# Garantir que as colunas sejam numéricas e lidar com valores nulos
edited_df['MÉDIA/KG'] = pd.to_numeric(edited_df['MÉDIA/KG'], errors='coerce').fillna(0.0)
edited_df['PREÇO DE VENDA'] = pd.to_numeric(edited_df['PREÇO DE VENDA'], errors='coerce').fillna(0.0)
edited_df['QUANTIDADE MÍNIMA (Embalagens)'] = pd.to_numeric(edited_df['QUANTIDADE MÍNIMA (Embalagens)'], errors='coerce').fillna(0.0)
edited_df['Logística (R$)'] = pd.to_numeric(edited_df['Logística (R$)'], errors='coerce').fillna(0.0)
edited_df['Impostos (R$)'] = pd.to_numeric(edited_df['Impostos (R$)'], errors='coerce').fillna(0.0)
edited_df['Aduaneiros (R$)'] = pd.to_numeric(edited_df['Aduaneiros (R$)'], errors='coerce').fillna(0.0)
edited_df['Outros Custos (R$)'] = pd.to_numeric(edited_df['Outros Custos (R$)'], errors='coerce').fillna(0.0)
edited_df['Volume/m³'] = pd.to_numeric(edited_df['Volume/m³'], errors='coerce').fillna(0.0)
edited_df['KG da Unidade'] = pd.to_numeric(edited_df['KG da Unidade'], errors='coerce').fillna(0.0)
edited_df['VALOR/EMBALAGEM'] = pd.to_numeric(edited_df['VALOR/EMBALAGEM'], errors='coerce').fillna(0.0)

# Calcular o peso total por embalagem a partir da coluna "UNIDADE/EMBALAGEM"
edited_df['Unidades por Embalagem'], edited_df['Peso por Unidade (kg)'] = zip(*edited_df['UNIDADE/EMBALAGEM'].apply(parse_unidade_embalagem))

# Ajustar o Peso Total por Embalagem: se Peso por Unidade for 0, usar KG da Unidade; caso contrário, usar Unidades por Embalagem × Peso por Unidade
def calculate_peso_total_por_embalagem(row):
    if row['Peso por Unidade (kg)'] == 0.0:
        # Para embalagens simples (ex.: "1,00"), usar KG da Unidade como peso total
        return row['KG da Unidade'] * row['Unidades por Embalagem']
    else:
        # Para embalagens com múltiplas unidades (ex.: "12,00 unidades de 0,5 kg")
        return row['Unidades por Embalagem'] * row['Peso por Unidade (kg)']

edited_df['Peso Total por Embalagem (kg)'] = edited_df.apply(calculate_peso_total_por_embalagem, axis=1)

# Calcular o peso total (QUANTIDADE MÍNIMA (Embalagens) × Peso Total por Embalagem)
edited_df['Peso Total (kg)'] = edited_df['QUANTIDADE MÍNIMA (Embalagens)'] * edited_df['Peso Total por Embalagem (kg)']

# Calcular o custo total (em R$)
edited_df['Custo Total (R$)'] = (
    edited_df['Logística (R$)'] +
    edited_df['Impostos (R$)'] +
    edited_df['Aduaneiros (R$)'] +
    edited_df['Outros Custos (R$)']
)

# Calcular o custo total por kg (Custo Total / Peso Total)
edited_df['Custo Total por kg (R$/kg)'] = edited_df.apply(
    lambda row: row['Custo Total (R$)'] / row['Peso Total (kg)'] if row['Peso Total (kg)'] != 0 else 0.0,
    axis=1
)

# Calcular o lucro bruto por kg
edited_df['Lucro Bruto por kg (R$/kg)'] = edited_df['PREÇO DE VENDA'] - edited_df['MÉDIA/KG']

# Calcular o lucro líquido por kg
edited_df['Lucro Líquido por kg (R$/kg)'] = edited_df['Lucro Bruto por kg (R$/kg)'] - edited_df['Custo Total por kg (R$/kg)']

# Calcular a margem de lucro considerando os custos por kg
edited_df['Margem de Lucro (%)'] = edited_df.apply(
    lambda row: (
        (row['Lucro Líquido por kg (R$/kg)'] / row['MÉDIA/KG'] * 100)
        if row['MÉDIA/KG'] != 0 else 0.0
    ),
    axis=1
)

# Calcular o valor total da venda (Preço de Venda × Peso Total)
edited_df['Valor Total da Venda (R$)'] = edited_df['PREÇO DE VENDA'] * edited_df['Peso Total (kg)']

# Calcular o lucro bruto total (Lucro Bruto por kg × Peso Total)
edited_df['Lucro Bruto Total (R$)'] = edited_df['Lucro Bruto por kg (R$/kg)'] * edited_df['Peso Total (kg)']

# Calcular o lucro líquido total (Lucro Líquido por kg × Peso Total)
edited_df['Lucro Líquido Total (R$)'] = edited_df['Lucro Líquido por kg (R$/kg)'] * edited_df['Peso Total (kg)']

# Calcular a margem líquida inicial
edited_df['Margem Líquida Inicial (%)'] = edited_df.apply(
    lambda row: (
        (row['Lucro Líquido Total (R$)'] / row['Valor Total da Venda (R$)'] * 100)
        if row['Valor Total da Venda (R$)'] != 0 else 0.0
    ),
    axis=1
)

# Calcular o volume total ocupado (QUANTIDADE MÍNIMA (Embalagens) × Volume/m³)
edited_df['Volume Total Ocupado (m³)'] = edited_df['QUANTIDADE MÍNIMA (Embalagens)'] * edited_df['Volume/m³']

# Criar dados para a tabela de margem com larguras ajustadas
margem_data = []
for _, row in edited_df.iterrows():
    margem_data.append({
        'Fornecedor (Marca)': f"{row['FORNECEDOR']} ({row['MARCA']})",
        'Quantidade Mínima (Embalagens)': round(row['QUANTIDADE MÍNIMA (Embalagens)'], 0) if pd.notna(row['QUANTIDADE MÍNIMA (Embalagens)']) else None,
        'Peso Total (kg)': round(row['Peso Total (kg)'], 2) if pd.notna(row['Peso Total (kg)']) else None,
        'Preço de Compra (R$/kg)': round(row['MÉDIA/KG'], 2) if pd.notna(row['MÉDIA/KG']) else None,
        'Preço de Venda (R$/kg)': round(row['PREÇO DE VENDA'], 2) if pd.notna(row['PREÇO DE VENDA']) else None,
        'Valor Total da Venda (R$)': round(row['Valor Total da Venda (R$)'], 2) if pd.notna(row['Valor Total da Venda (R$)']) else None,
        'Lucro Bruto Total (R$)': round(row['Lucro Bruto Total (R$)'], 2) if pd.notna(row['Lucro Bruto Total (R$)']) else None,
        'Custo Total (R$)': round(row['Custo Total (R$)'], 2) if pd.notna(row['Custo Total (R$)']) else None,
        'Custo Total por kg (R$/kg)': round(row['Custo Total por kg (R$/kg)'], 2) if pd.notna(row['Custo Total por kg (R$/kg)']) else None,
        'Lucro Líquido Total (R$)': round(row['Lucro Líquido Total (R$)'], 2) if pd.notna(row['Lucro Líquido Total (R$)']) else None,
        'Margem de Lucro (%)': round(row['Margem de Lucro (%)'], 2) if pd.notna(row['Margem de Lucro (%)']) else None,
        'Margem Líquida Inicial (%)': round(row['Margem Líquida Inicial (%)'], 2) if pd.notna(row['Margem Líquida Inicial (%)']) else None,
        'Volume Total Ocupado (m³)': round(row['Volume Total Ocupado (m³)'], 2) if pd.notna(row['Volume Total Ocupado (m³)']) else None
    })

# Exibir a tabela de margem de lucro com larguras ajustadas
st.dataframe(
    margem_data,
    use_container_width=True,
    column_config={
        'Fornecedor (Marca)': st.column_config.TextColumn(width=150),
        'Quantidade Mínima (Embalagens)': st.column_config.NumberColumn(width=150, format="%.0f"),
        'Peso Total (kg)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Preço de Compra (R$/kg)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Preço de Venda (R$/kg)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Valor Total da Venda (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Lucro Bruto Total (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Custo Total (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Custo Total por kg (R$/kg)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Lucro Líquido Total (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Margem de Lucro (%)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Margem Líquida Inicial (%)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Volume Total Ocupado (m³)': st.column_config.NumberColumn(width=150, format="%.2f")
    }
)

# Criar uma nova seção para o gráfico de margem de lucro por peso
st.subheader("Margem de Lucro por Peso (KG da Unidade)")
fig = go.Figure()

# Definir uma paleta de cores para as barras
colors = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99']  # Paleta com 4 cores diferentes

# Barra para Margem de Lucro, usando "KG da Unidade" como identificador, com tooltips
fig.add_trace(go.Bar(
    x=[f"{row['KG da Unidade']} kg ({row['FORNECEDOR']} - {row['MARCA']})" for _, row in edited_df.iterrows()],
    y=edited_df['Margem de Lucro (%)'],
    name='Margem de Lucro (%)',
    marker_color=[colors[i % len(colors)] for i in range(len(edited_df))],  # Atribuir uma cor diferente para cada barra
    text=edited_df['Margem de Lucro (%)'].round(2),
    textposition='auto',
    hovertemplate=(
        "<b>%{x}</b><br>" +
        "Margem de Lucro: %{y:.2f}%<br>" +
        "Preço de Compra: R$%{customdata[0]:.2f}/kg<br>" +
        "Preço de Venda: R$%{customdata[1]:.2f}/kg<br>" +
        "Quantidade Mínima (Embalagens): %{customdata[2]:.0f}<br>" +
        "Peso Total: %{customdata[3]:.2f} kg<br>" +
        "Custo Total: R$%{customdata[4]:.2f}<br>" +
        "Custo Total por kg: R$%{customdata[5]:.2f}/kg<br>" +
        "Lucro Bruto Total: R$%{customdata[6]:.2f}<br>" +
        "Lucro Líquido Total: R$%{customdata[7]:.2f}<br>" +
        "Volume Total Ocupado: %{customdata[8]:.2f} m³"
    ),
    customdata=edited_df[['MÉDIA/KG', 'PREÇO DE VENDA', 'QUANTIDADE MÍNIMA (Embalagens)', 'Peso Total (kg)', 'Custo Total (R$)', 'Custo Total por kg (R$/kg)', 'Lucro Bruto Total (R$)', 'Lucro Líquido Total (R$)', 'Volume Total Ocupado (m³)']].values
))

# Ajustar o layout do gráfico
fig.update_layout(
    xaxis_title="Peso (KG da Unidade) e Fornecedor (Marca)",
    yaxis_title="Margem de Lucro (%)",
    height=400,
    xaxis=dict(
        tickangle=45,  # Rotacionar as etiquetas do eixo X em 45 graus
        tickfont=dict(size=8)  # Tamanho da fonte ajustado
    ),
    showlegend=False  # Não precisamos de legenda, pois há apenas uma série de dados
)
st.plotly_chart(fig, use_container_width=True)

# Nova seção: Cálculo da Margem Líquida Ajustada
st.subheader("Margem Líquida Ajustada")

# Controles para ajustar o tempo de estoque e a taxa de juros
tempo_estoque_meses = st.slider("Tempo de Estoque (Meses)", min_value=1, max_value=24, value=12, step=1)
taxa_juros_anual = st.slider("Taxa de Juros Anual (%)", min_value=0.0, max_value=50.0, value=12.0, step=0.5)
taxa_juros_mensal = taxa_juros_anual / 12.0  # Taxa de juros mensal (ex.: 12% ao ano = 1% ao mês)

# Calcular a margem líquida ajustada para cada fornecedor no tempo de estoque especificado
margem_liquida_data = []
for idx, row in edited_df.iterrows():
    # Margem líquida inicial para este fornecedor
    margem_liquida_inicial = row['Margem Líquida Inicial (%)']

    # Ajustar a margem líquida pelo custo do dinheiro (taxa de juros mensal)
    if margem_liquida_inicial != 0.0:  # Verificar se o valor é válido
        # Decréscimo devido ao custo do dinheiro: 1% por mês
        margem_liquida_ajustada = margem_liquida_inicial - (taxa_juros_mensal * (tempo_estoque_meses - 1))
        margem_liquida_ajustada = max(0, margem_liquida_ajustada)  # Garantir que a margem não seja negativa
        # Determinar a viabilidade
        viavel = 'Sim' if margem_liquida_ajustada > taxa_juros_anual else 'Não'
    else:
        margem_liquida_ajustada = None
        viavel = 'Não'

    margem_liquida_data.append({
        'Fornecedor (Marca)': f"{row['FORNECEDOR']} ({row['MARCA']})",
        'Investimento Inicial (R$)': round(row['VALOR/EMBALAGEM'] * row['QUANTIDADE MÍNIMA (Embalagens)'] + row['Custo Total (R$)'], 2) if pd.notna(row['VALOR/EMBALAGEM']) else None,
        'Valor Total da Venda (R$)': round(row['Valor Total da Venda (R$)'], 2) if pd.notna(row['Valor Total da Venda (R$)']) else None,
        'Margem Líquida Inicial (%)': round(margem_liquida_inicial, 2) if margem_liquida_inicial != 0.0 else 'Não Calculável',
        'Margem Líquida Ajustada (%)': round(margem_liquida_ajustada, 2) if margem_liquida_ajustada is not None else 'Não Calculável',
        'Taxa de Juros Anual (%)': taxa_juros_anual,
        'Viável': viavel
    })

# Exibir a tabela de margem líquida ajustada
st.subheader("Margem Líquida por Fornecedor")
st.dataframe(
    margem_liquida_data,
    use_container_width=True,
    column_config={
        'Fornecedor (Marca)': st.column_config.TextColumn(width=150),
        'Investimento Inicial (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Valor Total da Venda (R$)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Margem Líquida Inicial (%)': st.column_config.TextColumn(width=150),
        'Margem Líquida Ajustada (%)': st.column_config.TextColumn(width=150),
        'Taxa de Juros Anual (%)': st.column_config.NumberColumn(width=150, format="%.2f"),
        'Viável': st.column_config.TextColumn(width=100)
    }
)

# Gráfico: Margem Líquida Ajustada em função do tempo de estoque
st.subheader("Margem Líquida Ajustada em Função do Tempo de Estoque")
fig_margem_liquida = go.Figure()

# Calcular a margem líquida ajustada para diferentes tempos de estoque (de 1 a 24 meses)
tempos_estoque_meses = np.arange(1, 25)  # 1 a 24 meses

for idx, row in edited_df.iterrows():
    # Margem líquida inicial para este fornecedor
    margem_liquida_inicial = row['Margem Líquida Inicial (%)']
    margem_liquida_valores = []

    if margem_liquida_inicial != 0.0:  # Verificar se o valor é válido
        for mes in tempos_estoque_meses:
            # Ajustar a margem líquida pelo custo do dinheiro
            margem_liquida_ajustada = margem_liquida_inicial - (taxa_juros_mensal * (mes - 1))
            margem_liquida_ajustada = max(0, margem_liquida_ajustada)  # Garantir que a margem não seja negativa
            margem_liquida_valores.append(margem_liquida_ajustada)
    else:
        margem_liquida_valores = [None] * len(tempos_estoque_meses)

    # Adicionar a linha ao gráfico
    fig_margem_liquida.add_trace(go.Scatter(
        x=tempos_estoque_meses,
        y=margem_liquida_valores,
        mode='lines+markers',
        name=f"Margem Líquida - {row['FORNECEDOR']} ({row['MARCA']})",
        line=dict(color=colors[idx % len(colors)]),
        hovertemplate=(
            "<b>%{x} meses</b><br>" +
            "Margem Líquida: %{y:.2f}%<br>" +
            "Fornecedor: " + f"{row['FORNECEDOR']} ({row['MARCA']})"
        )
    ))

# Adicionar uma linha horizontal para a taxa de juros anual
fig_margem_liquida.add_shape(
    type="line",
    x0=1,
    y0=taxa_juros_anual,
    x1=24,
    y1=taxa_juros_anual,
    line=dict(
        color="red",
        width=2,
        dash="dash"
    ),
    name="Taxa de Juros Anual"
)

# Adicionar uma anotação para a linha da taxa de juros
fig_margem_liquida.add_annotation(
    x=24,
    y=taxa_juros_anual,
    text=f"Taxa de Juros: {taxa_juros_anual}%",
    showarrow=True,
    arrowhead=1,
    ax=20,
    ay=-30
)

# Ajustar o layout do gráfico
fig_margem_liquida.update_layout(
    xaxis_title="Tempo de Estoque (Meses)",
    yaxis_title="Margem Líquida Ajustada (%)",
    height=500,
    legend=dict(
        x=0.01,
        y=0.99,
        bgcolor='rgba(255, 255, 255, 0.5)',
        bordercolor='rgba(0, 0, 0, 0.5)'
    ),
    xaxis=dict(
        tickmode='linear',
        tick0=1,
        dtick=1,
        gridcolor='lightgrey'
    ),
    yaxis=dict(
        range=[0, max([max(margem_liquida_valores) for margem_liquida_valores in [list(filter(None, trace.y)) for trace in fig_margem_liquida.data] if margem_liquida_valores], default=200)]  # Ajustar o limite superior
    ),
    yaxis_showgrid=True,
    yaxis_gridcolor='lightgrey'
)

# Exibir o gráfico
st.plotly_chart(fig_margem_liquida, use_container_width=True)