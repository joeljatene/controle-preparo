import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time
from fpdf import FPDF

# --- Configuração da Página ---
st.set_page_config(
    page_title="Controle de Chá Artesanal Pro",
    page_icon="🍃",
    layout="wide" # Layout expandido para caber mais informações
)

# --- GERENCIAMENTO DE ESTADO (SESSION STATE) ---
if 'apuro_log' not in st.session_state:
    st.session_state.apuro_log = [] # Lista para guardar histórico de adições no apuro

# --- FUNÇÕES DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('producao_cha_v3.db')
    c = conn.cursor()
    # Tabela expandida com novos campos
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
    conn = sqlite3.connect('producao_cha_v3.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO lotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (lote_id, str(data), mestre, tipo, total_bruto, total_apuro, volume_final, percentual, status, str(detalhes)))
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÃO GERADORA DE ETIQUETA PDF ---
def gerar_etiqueta(lote, data, mestre, tipo, validade="6 Meses"):
    pdf = FPDF(format=(100, 60)) # Tamanho aproximado de uma etiqueta grande (10cm x 6cm)
    pdf.add_page()
    pdf.set_margins(5, 5, 5)
    
    # Borda
    pdf.rect(2, 2, 96, 56)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=f"CHÁ ARTESANAL - {tipo.upper()}", ln=True, align='C')
    pdf.ln(2)
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt=f"Lote: {lote}", ln=True)
    pdf.cell(0, 5, txt=f"Data Fabricação: {data.strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 5, txt=f"Mestre do Preparo: {mestre}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, txt="Produto Artesanal - Conservar em local fresco", ln=True, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE DO APP ---

st.title("🍃 Controle de Produção - Versão Mestre")

# --- SIDEBAR: IDENTIFICAÇÃO ---
with st.sidebar:
    st.header("📋 Dados do Lote")
    if 'lote_id' not in st.session_state:
        st.session_state.lote_id = datetime.now().strftime("%Y%m%d")
    
    lote_id = st.text_input("ID Lote", value=st.session_state.lote_id)
    data_lote = st.date_input("Data", datetime.now())
    mestre = st.text_input("Mestre do Preparo", placeholder="Nome do responsável")
    tipo_cha = st.selectbox("Tipo de Chá", ["Tradicional", "Ervas Mistas", "Especial", "Outro"])
    
    st.divider()
    st.info("Utilize as abas acima para navegar entre as fases.")

# --- ABAS PRINCIPAIS ---
tab_cozimento, tab_apuro, tab_final = st.tabs(["1. Cozinhamento (Extração)", "2. Fase de Apuro (Concentração)", "3. Finalização e Etiquetas"])

# Variáveis globais para cálculo
total_bruto = 0.0

# =========================================================
# ABA 1: COZINHAMENTO
# =========================================================
with tab_cozimento:
    st.header("Fase de Cozinhamento (Extração)")
    
    # Configuração de Nomes das Panelas
    with st.expander("⚙️ Nomes das 6 Panelas", expanded=False):
        cols_cfg = st.columns(6)
        nomes_panelas = []
        for i in range(6):
            key_name = f"nome_p{i+1}"
            if key_name not in st.session_state: st.session_state[key_name] = f"P{i+1}"
            nome = cols_cfg[i].text_input(f"Panela {i+1}", key=key_name)
            nomes_panelas.append(nome)

    # Sub-abas para as 3 rodadas
    subtab1, subtab2, subtab3 = st.tabs(["1º Cozinhamento", "2º Cozinhamento", "3º Cozinhamento"])
    
    rodadas_data = [] # Para guardar volumes e tempos
    
    metas = [30.0, 20.0, 15.0]
    
    for r_idx, subtab in enumerate([subtab1, subtab2, subtab3]):
        with subtab:
            st.caption(f"Meta esperada: {metas[r_idx]} Litros por panela")
            
            # Grid layout
            cols = st.columns(3) # 2 panelas por coluna visualmente (total 6 panelas)
            
            soma_desta_rodada = 0
            
            for p_idx in range(6):
                # Organização visual: 2 panelas por linha
                col_atual = cols[p_idx % 3]
                
                with col_atual:
                    with st.container(border=True):
                        st.write(f"**{nomes_panelas[p_idx]}**")
                        
                        # Input de Volume
                        vol = st.number_input(
                            f"Litros (Meta {metas[r_idx]})", 
                            min_value=0.0, step=1.0, 
                            key=f"vol_r{r_idx}_p{p_idx}",
                            value=metas[r_idx]
                        )
                        soma_desta_rodada += vol
                        
                        # Input de Tempo (Expander para não poluir)
                        with st.expander("⏱️ Tempo de Fogo"):
                            c_t1, c_t2 = st.columns(2)
                            h_inicio = c_t1.time_input("Início", value=time(8,0), key=f"hi_r{r_idx}_p{p_idx}")
                            h_fim = c_t2.time_input("Fim", value=time(9,0), key=f"hf_r{r_idx}_p{p_idx}")
                            
                            # Cálculo simples de duração visual
                            duracao = datetime.combine(datetime.today(), h_fim) - datetime.combine(datetime.today(), h_inicio)
                            st.caption(f"Duração: {duracao}")
                            
            st.metric(f"Total Cozinhamento {r_idx+1}", f"{soma_desta_rodada} L")
            rodadas_data.append(soma_desta_rodada)

    total_bruto = sum(rodadas_data)
    st.success(f"💧 Volume Total Extraído das Panelas: **{total_bruto} Litros**")

# =========================================================
# ABA 2: APURO (NOVA FUNÇÃO)
# =========================================================
with tab_apuro:
    st.header("Fase de Apuro (Concentração)")
    st.info("Registre aqui a entrada de líquido nas panelas de apuro conforme o processo.")
    
    col_apuro_config, col_apuro_add = st.columns([1, 2])
    
    with col_apuro_config:
        st.subheader("Configuração")
        nome_apuro_1 = st.text_input("Nome Panela Apuro 1", "Apuro A")
        nome_apuro_2 = st.text_input("Nome Panela Apuro 2", "Apuro B")
        
        if st.button("🗑️ Limpar Registro de Apuro"):
            st.session_state.apuro_log = []
            st.rerun()

    with col_apuro_add:
        st.subheader("Adicionar Líquido")
        with st.form("form_apuro"):
            c1, c2 = st.columns(2)
            panela_selecionada = c1.selectbox("Destino", [nome_apuro_1, nome_apuro_2])
            qtd_adicionada = c2.number_input("Quantidade (Litros)", min_value=0.0, step=5.0)
            
            btn_add = st.form_submit_button("➕ Registrar Adição")
            
            if btn_add and qtd_adicionada > 0:
                # Adiciona ao log
                st.session_state.apuro_log.append({
                    "panela": panela_selecionada,
                    "qtd": qtd_adicionada,
                    "hora": datetime.now().strftime("%H:%M")
                })
                st.rerun()

    st.divider()
    
    # Visão Geral do Apuro
    col_res_a, col_res_b = st.columns(2)
    
    # Filtrar dados para P1 e P2
    df_apuro = pd.DataFrame(st.session_state.apuro_log)
    
    total_apuro_1 = 0.0
    total_apuro_2 = 0.0
    
    if not df_apuro.empty:
        total_apuro_1 = df_apuro[df_apuro['panela'] == nome_apuro_1]['qtd'].sum()
        total_apuro_2 = df_apuro[df_apuro['panela'] == nome_apuro_2]['qtd'].sum()
        
        st.write("### Histórico de Adições")
        st.dataframe(df_apuro, use_container_width=True)
    
    with col_res_a:
        st.metric(f"Total em {nome_apuro_1}", f"{total_apuro_1:.1f} L")
        st.progress(min(total_apuro_1/200, 1.0)) # Barra de progresso visual (assumindo max 200L)

    with col_res_b:
        st.metric(f"Total em {nome_apuro_2}", f"{total_apuro_2:.1f} L")
        st.progress(min(total_apuro_2/200, 1.0))
        
    total_apuro_geral = total_apuro_1 + total_apuro_2
    
    st.markdown("---")
    # Verificação de consistência
    diff = total_bruto - total_apuro_geral
    c_check1, c_check2 = st.columns(2)
    c_check1.metric("Total Extraído (Fase 1)", f"{total_bruto} L")
    c_check2.metric("Total Colocado no Apuro (Fase 2)", f"{total_apuro_geral} L", delta=f"{diff} L")
    
    if diff > 0:
        st.warning(f"⚠️ Ainda faltam {diff} Litros para colocar no apuro!")
    elif diff < 0:
        st.error(f"🚨 Erro: Você colocou {abs(diff)} Litros a mais no apuro do que foi extraído!")
    else:
        st.success("✅ Todo o líquido extraído foi transferido para o apuro.")

# =========================================================
# ABA 3: FINALIZAÇÃO E ETIQUETA
# =========================================================
with tab_final:
    st.header("3. Finalização do Lote")
    
    meta_min = total_bruto * 0.20
    meta_max = total_bruto * 0.25
    
    st.info(f"🎯 Meta de Apuro: Entre **{meta_min:.1f}L** e **{meta_max:.1f}L**")
    
    volume_final = st.number_input("Volume Final Obtido (Soma das panelas de apuro no final)", min_value=0.0, step=0.5, format="%.1f")
    
    percentual = 0.0
    status_msg = "Pendente"
    
    if volume_final > 0 and total_bruto > 0:
        percentual = (volume_final / total_bruto) * 100
        st.write(f"Rendimento: **{percentual:.1f}%**")
        
        if 20 <= percentual <= 25:
            st.success("✅ APROVADO")
            status_msg = "Aprovado"
        else:
            st.warning("⚠️ FORA DA META PADRÃO")
            status_msg = "Fora da Meta"
            
        st.divider()
        c_save, c_print = st.columns(2)
        
        # Botão Salvar
        if c_save.button("💾 Salvar Lote e Encerrar"):
            if not mestre:
                st.error("Preencha o nome do Mestre do Preparo na barra lateral!")
            else:
                salvar_lote(lote_id, data_lote, mestre, tipo_cha, total_bruto, total_apuro_geral, volume_final, percentual, status_msg, "Tempos registrados")
                st.toast("Lote salvo com sucesso!", icon="🔒")
        
        # Botão Imprimir Etiqueta
        if mestre:
            pdf_bytes = gerar_etiqueta(lote_id, data_lote, mestre, tipo_cha)
            c_print.download_button(
                label="🏷️ Baixar Etiqueta para Garrafas",
                data=pdf_bytes,
                file_name=f"etiqueta_{lote_id}.pdf",
                mime="application/pdf"
            )
        else:
            c_print.warning("Preencha o Mestre do Preparo para gerar etiqueta.")
