import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF
import io

# --- Configuração da Página ---
st.set_page_config(
    page_title="Controle de Chá Artesanal",
    page_icon="🍃",
    layout="centered"
)

# --- FUNÇÕES DE BANCO DE DADOS (SQLite) ---
def init_db():
    conn = sqlite3.connect('producao_cha.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lotes (
            id TEXT PRIMARY KEY,
            data TEXT,
            total_bruto REAL,
            volume_final REAL,
            percentual REAL,
            status TEXT,
            detalhes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_lote(lote_id, data, total_bruto, volume_final, percentual, status, detalhes):
    conn = sqlite3.connect('producao_cha.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO lotes (id, data, total_bruto, volume_final, percentual, status, detalhes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (lote_id, str(data), total_bruto, volume_final, percentual, status, str(detalhes)))
    conn.commit()
    conn.close()

def carregar_dados():
    conn = sqlite3.connect('producao_cha.db')
    df = pd.read_sql_query("SELECT * FROM lotes", conn)
    conn.close()
    return df

# Inicializa o banco ao abrir
init_db()

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf(lote_id, data, nomes_panelas, dados_cozinhamento, total_bruto, volume_final, status):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"Relatório de Produção - Lote {lote_id}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Data: {data}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Detalhamento por Cozinhamento", ln=True)
    
    pdf.set_font("Arial", size=10)
    # Loop pelos dados para imprimir no PDF
    for i, rodada in enumerate(dados_cozinhamento):
        pdf.cell(200, 8, txt=f"Cozinhamento {i+1}", ln=True)
        texto_panelas = " | ".join([f"{nomes_panelas[j]}: {val}L" for j, val in enumerate(rodada)])
        pdf.multi_cell(0, 8, txt=texto_panelas)
        pdf.ln(2)
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Resumo Final", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 8, txt=f"Total Bruto (Extraído): {total_bruto:.1f} Litros", ln=True)
    pdf.cell(200, 8, txt=f"Volume Final (Apurado): {volume_final:.1f} Litros", ln=True)
    pdf.cell(200, 8, txt=f"Status: {status}", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE DO APP ---

st.title("🍃 Controle de Produção")

# --- CONFIGURAÇÃO INICIAL (Nomes das Panelas) ---
with st.expander("⚙️ Configuração das Panelas (Editável)", expanded=False):
    st.caption("Dê nomes para suas panelas (ex: P1, Caldeirão, Frente-Esq)")
    cols_cfg = st.columns(3)
    nomes_panelas = []
    for i in range(6):
        nome_padrao = f"P{i+1}"
        # Salva nomes no session_state para não perder ao recarregar
        key_name = f"nome_p{i+1}"
        if key_name not in st.session_state:
            st.session_state[key_name] = nome_padrao
            
        nome = cols_cfg[i%3].text_input(f"Panela {i+1}", key=key_name)
        nomes_panelas.append(nome)

st.divider()

# --- DADOS DO LOTE ---
col1, col2 = st.columns(2)
if 'lote_id' not in st.session_state:
    st.session_state.lote_id = datetime.now().strftime("%Y%m%d-%H%M")
    
lote_id = col1.text_input("ID do Lote", value=st.session_state.lote_id)
data_lote = col2.date_input("Data", datetime.now())

# --- FASE 1: EXTRAÇÃO ---
st.header("1. Fase de Extração")

# Mudança de nomenclatura: Rodada -> Cozinhamento
tab1, tab2, tab3 = st.tabs(["Cozinhamento 1 (30L)", "Cozinhamento 2 (20L)", "Cozinhamento 3 (15L)"])

# Matriz para guardar os valores [ [c1_p1, c1_p2...], [c2_p1...] ]
dados_cozinhamento = [] 
totais_cozinhamento = []

padroes = [30.0, 20.0, 15.0]

# Loop para criar as abas dinamicamente
for i, tab in enumerate([tab1, tab2, tab3]):
    with tab:
        st.caption(f"Meta: {padroes[i]} Litros por panela")
        cols = st.columns(3)
        valores_desta_rodada = []
        soma_desta_rodada = 0
        
        for j in range(6):
            with cols[j%3]:
                # O label agora usa o nome customizado da panela
                val = st.number_input(
                    f"{nomes_panelas[j]}", 
                    min_value=0.0, 
                    value=padroes[i], 
                    step=0.5, 
                    key=f"c{i+1}_p{j+1}"
                )
                valores_desta_rodada.append(val)
                soma_desta_rodada += val
        
        dados_cozinhamento.append(valores_desta_rodada)
        totais_cozinhamento.append(soma_desta_rodada)
        st.metric(f"Total Cozinhamento {i+1}", f"{soma_desta_rodada:.1f} L")

total_bruto = sum(totais_cozinhamento)

st.info(f"💧 **Total Líquido Bruto:** {total_bruto:.1f} Litros")

# --- FASE 2: APURO ---
st.divider()
st.header("2. Fase de Apuro")

meta_min = total_bruto * 0.20
meta_max = total_bruto * 0.25

col_m1, col_m2 = st.columns(2)
col_m1.metric("Meta Min (20%)", f"{meta_min:.1f} L")
col_m2.metric("Meta Max (25%)", f"{meta_max:.1f} L")

volume_final = st.number_input("Volume Final Obtido (Litros)", min_value=0.0, step=0.5, format="%.1f")

status_msg = "Pendente"
percentual = 0.0

if volume_final > 0:
    percentual = (volume_final / total_bruto) * 100
    st.write(f"Percentual atingido: **{percentual:.1f}%**")
    
    if 20 <= percentual <= 25:
        st.success("✅ APROVADO (Dentro da meta)")
        status_msg = "Aprovado"
    elif percentual < 20:
        st.error("⚠️ BAIXO RENDIMENTO (Apurou demais)")
        status_msg = "Baixo"
    else:
        st.error("⚠️ ALTO RENDIMENTO (Falta apurar)")
        status_msg = "Alto"

# --- ÁREA DE AÇÃO E SALVAMENTO ---
st.divider()
col_btn1, col_btn2 = st.columns(2)

# Botão Salvar no Banco
if col_btn1.button("💾 Salvar Lote no Banco"):
    detalhes_str = str(dados_cozinhamento) # Convertendo lista para texto para salvar simples
    salvar_lote(lote_id, data_lote, total_bruto, volume_final, percentual, status_msg, detalhes_str)
    st.toast("Dados salvos com sucesso no banco de dados!", icon="🎉")

# Botão Gerar PDF
if volume_final > 0:
    pdf_bytes = gerar_pdf(lote_id, data_lote, nomes_panelas, dados_cozinhamento, total_bruto, volume_final, status_msg)
    col_btn2.download_button(
        label="📄 Baixar Relatório PDF",
        data=pdf_bytes,
        file_name=f"relatorio_lote_{lote_id}.pdf",
        mime="application/pdf"
    )

# --- VISUALIZAÇÃO DO BANCO E EXPORTAÇÃO ---
st.markdown("---")
with st.expander("📂 Histórico e Banco de Dados"):
    df_historico = carregar_dados()
    st.dataframe(df_historico)
    
    # Botão para baixar o banco todo em Excel/CSV
    csv = df_historico.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Baixar Banco de Dados Completo (CSV)",
        csv,
        "historico_producao.csv",
        "text/csv",
        key='download-csv'
    )
