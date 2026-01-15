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
with tab_cozimento:
    st.subheader("Fase de Cozinhamento (Extração)")
    
    subtab1, subtab2, subtab3 = st.tabs(["1º Cozinhamento", "2º Cozinhamento", "3º Cozinhamento"])
    metas = [30.0, 20.0, 15.0]
    somas_rodadas = []
    
    for r_idx, subtab in enumerate([subtab1, subtab2, subtab3]):
        with subtab:
            st.caption(f"Meta: {metas[r_idx]} L/panela")
            cols = st.columns(3)
            soma_r = 0
            
            log_detalhado_cozinhamento += f"\n--- Cozinhamento {r_idx+1} ---\n"
            
            for p_idx in range(6):
                with cols[p_idx % 3]:
                    with st.container(border=True):
                        st.write(f"**{nomes_panelas[p_idx]}**")
                        
                        # Input Volume
                        val = st.number_input(
                            f"Litros", 
                            min_value=0.0, step=1.0, 
                            key=f"vol_r{r_idx}_p{p_idx}",
                            value=metas[r_idx]
                        )
                        soma_r += val
                        
                        # --- FUNCIONALIDADE RESTAURADA: CONTROLE DE TEMPO ---
                        with st.expander("⏱️ Tempo de Fogo"):
                            c_t1, c_t2 = st.columns(2)
                            h_inicio = c_t1.time_input("Início", value=time(8,0), key=f"hi_r{r_idx}_p{p_idx}")
                            h_fim = c_t2.time_input("Fim", value=time(9,0), key=f"hf_r{r_idx}_p{p_idx}")
                            
                            duracao = datetime.combine(datetime.today(), h_fim) - datetime.combine(datetime.today(), h_inicio)
                            st.caption(f"Duração: {duracao}")
                            
                            # Adiciona ao log para o PDF
                            log_detalhado_cozinhamento += f"{nomes_panelas[p_idx]}: {val}L ({h_inicio.strftime('%H:%M')} - {h_fim.strftime('%H:%M')})\n"
            
            somas_rodadas.append(soma_r)
            st.metric(f"Total Cozinhamento {r_idx+1}", f"{soma_r} L")

    total_bruto = sum(somas_rodadas)
    st.info(f"💧 **Total Extraído (Soma): {total_bruto} Litros**")

# =========================================================
# ABA 2: APURO
# =========================================================
with tab_apuro:
    st.subheader("Fase de Apuro")
    
    c_conf, c_add = st.columns([1, 2])
    with c_conf:
        st.markdown("**Panelas de Apuro**")
        nome_apuro_1 = st.text_input("Nome Apuro 1", "Apuro A")
        nome_apuro_2 = st.text_input("Nome Apuro 2", "Apuro B")
        if st.button("Limpar Histórico Apuro"):
            st.session_state.apuro_log = []
            st.rerun()
            
    with c_add:
        with st.form("add_apuro"):
            st.markdown("**Registrar Entrada de Líquido**")
            cc1, cc2 = st.columns(2)
            panela_sel = cc1.selectbox("Destino", [nome_apuro_1, nome_apuro_2])
            qtd_sel = cc2.number_input("Litros", min_value=0.0, step=5.0)
            if st.form_submit_button("➕ Adicionar"):
                st.session_state.apuro_log.append({
                    "panela": panela_sel, "qtd": qtd_sel, "hora": datetime.now().strftime("%H:%M")
                })
                st.rerun()

    df_apuro = pd.DataFrame(st.session_state.apuro_log)
    total_apuro_geral = 0.0
    if not df_apuro.empty:
        st.dataframe(df_apuro, use_container_width=True)
        total_apuro_geral = df_apuro['qtd'].sum()
    
    diff = total_bruto - total_apuro_geral
    st.metric("Total no Apuro", f"{total_apuro_geral} L", delta=f"Faltam {diff} L" if diff > 0 else "OK")

# =========================================================
# ABA 3: FINALIZAÇÃO
# =========================================================
with tab_final:
    st.subheader("Fechamento do Lote")
    
    meta_min = total_bruto * 0.20
    meta_max = total_bruto * 0.25
    
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Meta Mínima (20%)", f"{meta_min:.1f} L")
    col_m2.metric("Meta Máxima (25%)", f"{meta_max:.1f} L")
    
    vol_final = st.number_input("Volume Final Obtido (Litros)", min_value=0.0, step=0.5)
    
    status_msg = "Pendente"
    percentual = 0.0
    
    if vol_final > 0 and total_bruto > 0:
        percentual = (vol_final / total_bruto) * 100
        st.write(f"**Rendimento Final: {percentual:.1f}%**")
        
        if 20 <= percentual <= 25:
            st.success("✅ APROVADO")
            status_msg = "Aprovado"
        else:
            st.warning("⚠️ FORA DO PADRÃO")
            status_msg = "Fora do Padrão"
            
        st.markdown("---")
        st.write("### 🖨️ Documentação")
        
        col_pdf1, col_pdf2, col_save = st.columns(3)
        
        # 1. Botão Salvar
        if col_save.button("💾 Salvar Lote"):
            if not mestre or not tipo_cha:
                st.error("Preencha Mestre e Tipo na barra lateral!")
            else:
                salvar_lote(lote_id, data_lote, mestre, tipo_cha, total_bruto, total_apuro_geral, vol_final, percentual, status_msg, log_detalhado_cozinhamento)
                st.toast("Salvo com sucesso!", icon="✅")

        # 2. Botão Relatório PDF (Completo)
        if mestre and tipo_cha:
            pdf_relatorio = gerar_relatorio_pdf(lote_id, data_lote, mestre, tipo_cha, log_detalhado_cozinhamento, total_bruto, st.session_state.apuro_log, total_apuro_geral, vol_final, status_msg)
            col_pdf1.download_button(
                "📄 Relatório Completo",
                data=pdf_relatorio,
                file_name=f"Relatorio_{lote_id}.pdf",
                mime="application/pdf"
            )
            
            # 3. Botão Etiqueta PDF (Pequena)
            pdf_etiqueta = gerar_etiqueta_pdf(lote_id, data_lote, mestre, tipo_cha)
            col_pdf2.download_button(
                "🏷️ Etiqueta Garrafa",
                data=pdf_etiqueta,
                file_name=f"Etiqueta_{lote_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.caption("Preencha os dados do Mestre para habilitar os downloads.")
