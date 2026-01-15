import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta, time
from fpdf import FPDF

# --- Configuração da Página ---
st.set_page_config(
    page_title="APP PREPARO",
    page_icon="🍃",
    layout="wide"
)

# --- GERENCIAMENTO DE ESTADO (SESSION STATE) ---
if 'apuro_log' not in st.session_state:
    st.session_state.apuro_log = [] 
if 'timers' not in st.session_state:
    st.session_state.timers = {} 

# --- FUNÇÕES DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('producao_cha_v5.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lotes (
            id TEXT PRIMARY KEY,
            data TEXT,
            mestre TEXT,
            tipo_cha TEXT,
            total_bruto REAL,
            total_apuro_entrada REAL,
            volume_final REAL,
            percentual REAL,
            status TEXT,
            detalhes_tempo TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_lote(lote_id, data, mestre, tipo, total_bruto, total_apuro, volume_final, percentual, status, detalhes):
    conn = sqlite3.connect('producao_cha_v5.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO lotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (lote_id, str(data), mestre, tipo, total_bruto, total_apuro, volume_final, percentual, status, str(detalhes)))
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÕES DE PDF (Relatório e Etiqueta) ---
class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'APP PREPARO - Relatório de Lote', 0, 1, 'C')
        self.ln(5)

def gerar_relatorio_pdf(lote, data, mestre, tipo, dados_coz, total_bruto, log_apuro, total_apuro, final, status):
    pdf = PDFRelatorio()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Cabeçalho
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 10, f"Lote: {lote}  |  Data: {data}", 1, 1, 'L', 1)
    pdf.cell(0, 10, f"Mestre: {mestre}  |  Tipo: {tipo}", 1, 1, 'L', 1)
    pdf.ln(5)
    
    # Fase 1
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Fase de Cozinhamento (Extração)", 0, 1)
    pdf.set_font("Arial", size=10)
    # Imprime o resumo textual das panelas e tempos
    pdf.multi_cell(0, 6, f"{dados_coz}")
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"Total Extraído: {total_bruto:.1f} Litros", 0, 1)
    pdf.ln(5)
    
    # Fase 2
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Fase de Apuro", 0, 1)
    pdf.set_font("Arial", size=10)
    
    if log_apuro:
        for item in log_apuro:
            pdf.cell(0, 6, f"- {item['hora']}: {item['qtd']}L em {item['panela']}", 0, 1)
    else:
        pdf.cell(0, 6, "Sem registro individual de adições.", 0, 1)
        
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"Total Colocado no Apuro: {total_apuro:.1f} Litros", 0, 1)
    pdf.ln(5)
    
    # Resultado Final
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "RESULTADO FINAL", 0, 1)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, f"Volume Final Obtido: {final:.1f} Litros", 0, 1)
    pdf.cell(0, 8, f"Status: {status}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

def gerar_etiqueta_pdf(lote, data, mestre, tipo):
    pdf = FPDF(format=(100, 60))
    pdf.add_page()
    pdf.set_margins(5, 5, 5)
    pdf.rect(2, 2, 96, 56)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=f"CHA - {tipo.upper()}", ln=True, align='C')
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt=f"Lote: {lote}", ln=True)
    pdf.cell(0, 5, txt=f"Data: {data.strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 5, txt=f"Resp: {mestre}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, txt="Produto Artesanal", ln=True, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE DO APP ---

st.title("🍃 APP PREPARO")

# --- SIDEBAR: CONTROLE E DADOS ---
with st.sidebar:
    st.header("📋 Identificação")
    
    if 'lote_id' not in st.session_state:
        st.session_state.lote_id = datetime.now().strftime("%Y%m%d")
    
    lote_id = st.text_input("ID Lote", value=st.session_state.lote_id)
    data_lote = st.date_input("Data", datetime.now())
    mestre = st.text_input("Mestre do Preparo", placeholder="Nome do Mestre")
    
    # Tipos de Chá Específicos
    tipo_selecao = st.selectbox("Tipo de Chá", ["Caupuri", "Tucunacá", "Outros"])
    if tipo_selecao == "Outros":
        tipo_cha = st.text_input("Digite o nome do chá:", placeholder="Ex: Misto Especial")
    else:
        tipo_cha = tipo_selecao

    st.divider()
    
    # --- CRONÔMETRO DE FERVURA (REGRESSIVO) ---
    st.header("⏱️ Timer de Alerta")
    st.caption("Avisar quando desligar uma panela.")
    
    with st.expander("Novo Alerta", expanded=True):
        timer_panela = st.text_input("Qual Panela?", placeholder="Ex: P1")
        minutos = st.number_input("Avisar em (minutos):", min_value=1, value=10, step=1)
        
        if st.button("▶️ Iniciar Timer"):
            agora = datetime.now()
            fim = agora + timedelta(minutes=minutos)
            st.session_state.timers[timer_panela] = fim
            st.rerun()
            
    # Exibir Timers Ativos
    if st.session_state.timers:
        st.markdown("---")
        st.write("**Alertas Ativos:**")
        
        chaves_remocao = []
        agora_atual = datetime.now()
        
        for p, fim in st.session_state.timers.items():
            restante = (fim - agora_atual).total_seconds()
            
            if restante > 0:
                min_rest = int(restante // 60)
                seg_rest = int(restante % 60)
                st.info(f"**{p}**: Faltam {min_rest}m {seg_rest}s\n(Fim: {fim.strftime('%H:%M')})")
            else:
                st.error(f"🚨 **{p}: TEMPO ESGOTADO!**")
                if st.button(f"🗑️ Limpar {p}"):
                    chaves_remocao.append(p)
        
        for k in chaves_remocao:
            del st.session_state.timers[k]
            st.rerun()
            
        if st.button("🔄 Atualizar Timers"):
            st.rerun()

# --- ÁREA PRINCIPAL ---

# Nomes das Panelas
with st.expander("⚙️ Configuração dos Nomes das Panelas", expanded=False):
    cols_cfg = st.columns(6)
    nomes_panelas = []
    for i in range(6):
        key_name = f"nome_p{i+1}"
        if key_name not in st.session_state: st.session_state[key_name] = f"P{i+1}"
        nome = cols_cfg[i].text_input(f"Panela {i+1}", key=key_name)
        nomes_panelas.append(nome)

tab_cozimento, tab_apuro, tab_final = st.tabs(["1. Cozinhamento", "2. Apuro", "3. Finalização & Relatórios"])

total_bruto = 0.0
# Variável para acumular texto pro PDF
log_detalhado_cozinhamento = "" 

# =========================================================
# ABA 1: COZINHAMENTO (COM CONTROLE DE TEMPO RESTAURADO)
# =========================================================
with tab_
