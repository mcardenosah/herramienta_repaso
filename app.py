import os
import streamlit as st
import google.generativeai as genai
import PyPDF2
import datetime
import time

# ==========================================
# CONFIGURACIÓN GENERAL DE LA IA
# ==========================================
# Usamos el estándar de producción más avanzado
MODELO_IA = "gemini-2.0-flash"

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador de Alumno | Efecto Protegé",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# FUNCIONES AUXILIARES Y DE RED
# ==========================================
def extract_text_from_pdf(filepath):
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
    except Exception as e:
        return f"Error al leer el PDF: {e}"

def get_concepciones_erroneas(pdf_filepath):
    txt_filepath = pdf_filepath.replace('.pdf', '_errores.txt')
    if os.path.exists(txt_filepath):
        try:
            with open(txt_filepath, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            return ""
    return ""

def get_asignaturas(directory="apuntes"):
    if not os.path.exists(directory):
        os.makedirs(directory)
        return []
    asignaturas = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
    return sorted(asignaturas)

def get_temas(asignatura, directory="apuntes"):
    path = os.path.join(directory, asignatura)
    if not os.path.exists(path):
        return []
    pdfs = [f for f in os.listdir(path) if f.endswith('.pdf')]
    return sorted(pdfs)

def enviar_mensaje_con_reintentos(prompt_text, history_messages, system_prompt):
    """
    AMORTIGUADOR DE ERRORES INTELIGENTE.
    Traduce los bloqueos geopolíticos de Google a mensajes claros.
    """
    max_intentos = 4
    ultimo_error = None
    
    model = genai.GenerativeModel(
        model_name=MODELO_IA,
        system_instruction=system_prompt
    )
    
    formatted_history = []
    for msg in history_messages:
        role = "model" if msg["role"] == "model" else "user"
        content = msg["content"] if msg["content"].strip() else "..."
        formatted_history.append({"role": role, "parts": [content]})
        
    for intento in range(max_intentos):
        try:
            chat = model.start_chat(history=formatted_history)
            response = chat.send_message(prompt_text)
            return response.text
        except Exception as e:
            ultimo_error = e
            error_str = str(e).lower()
            
            # DIAGNÓSTICO INTELIGENTE DE ERRORES GEOPOLÍTICOS
            if "limit: 0" in error_str:
                raise Exception("BLOQUEO_UE: Google ha detectado que el servidor está en Europa y ha bloqueado la capa gratuita (Cuota 0). Solución: Despliega en Streamlit Cloud desde EE.UU. o activa facturación.")
            elif "limit: 20" in error_str:
                raise Exception("LÍMITE_PREVIEW: Se han agotado las 20 peticiones diarias de este modelo experimental.")
            elif "404" in error_str and "not found" in error_str:
                raise Exception("MODELO_OCULTO: Google ha ocultado este modelo para las cuentas europeas gratuitas.")
                
            if intento < max_intentos - 1:
                time.sleep(2 ** intento)
            else:
                raise ultimo_error

# ==========================================
# DIÁLOGO DE INSTRUCCIONES FINALES
# ==========================================
@st.dialog("📝 Fase de Reflexión (Metacognición)")
def mostrar_instrucciones_finales():
    st.markdown("""
    Has terminado la fase de explicación. Para cerrar el ciclo de aprendizaje correctamente:
    
    1. Tu "alumno virtual" hará un breve resumen y te planteará **3 preguntas de reflexión** sobre tu práctica hoy.
    2. **Responde** a esas preguntas utilizando la caja de chat (sigue abierta).
    3. Cuando hayas contestado, pulsa el botón **'📄 Generar Rúbrica Final'** que aparecerá en la pantalla.
    """)
    if st.button("Entendido, empezar reflexión", type="primary", use_container_width=True):
        st.session_state.trigger_cierre = True
        st.rerun()

# ==========================================
# GESTIÓN DEL HISTORIAL DE CHAT
# ==========================================
def init_chat_history(asignatura, tema):
    tema_id = f"{asignatura}_{tema}"
    if "current_tema_id" not in st.session_state or st.session_state.current_tema_id != tema_id:
        st.session_state.messages = []
        st.session_state.current_tema_id = tema_id
        st.session_state.mostrar_instrucciones = False
        st.session_state.fase_actual = 'explicacion'
        st.session_state.trigger_cierre = False
        st.session_state.trigger_rubrica = False
        st.session_state.texto_rubrica_final = "" 
    
    if len(st.session_state.messages) == 0:
        st.session_state.messages.append({"role": "user", "content": f"Inicio sesión: {tema}", "show": False})
        tema_limpio = tema.replace('.pdf', '').replace('_', ' ')
        st.session_state.messages.append({
            "role": "model", 
            "content": f"¡Hola! He estado intentando estudiar el tema de **{tema_limpio}**, pero la verdad es que me cuesta un poco arrancar. ¿Me podrías explicar con tus propias palabras cuál es la idea principal o el concepto más importante para empezar a situarme?",
            "show": True
        })

# ==========================================
# GESTIÓN DE LA API KEY Y CONEXIÓN
# ==========================================
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = st.sidebar.text_input("🔑 API Key de Gemini", type="password")

if not api_key:
    st.stop()

genai.configure(api_key=api_key)

# ==========================================
# PANEL LATERAL Y CONTROLES DE SESIÓN
# ==========================================
with st.sidebar:
    st.header("📚 Menú de Estudio")
    asignaturas = get_asignaturas("apuntes")
    if not asignaturas:
        st.error("⚠️ Docente: Configura las carpetas en GitHub."); st.stop()
    asignatura_seleccionada = st.selectbox("1. Tu Asignatura / Grupo:", asignaturas, format_func=lambda x: x.replace("_", " "))
    temas = get_temas(asignatura_seleccionada)
    if not temas:
        st.warning(f"⚠️ No hay PDFs en {asignatura_seleccionada}."); st.stop()
    tema_seleccionado = st.selectbox("2. Tema a repasar:", temas, format_func=lambda x: x.replace(".pdf", "").replace("_", " "))
    st.divider()
    idioma = st.selectbox("3. Idioma:", ["Castellano", "Valenciano"])
    nivel_desafio = st.select_slider("4. Dificultad de dudas:", options=["Básico", "Intermedio", "Avanzado"], value="Intermedio")
    
    st.divider()
    st.header("⚙️ Control de Sesión")
    if st.button("🧹 Reiniciar Conversación", use_container_width=True):
        st.session_state.messages = []; st.rerun()
    
    if st.session_state.get('fase_actual') == 'explicacion' and len(st.session_state.get('messages', [])) > 2:
        st.markdown("<br>", unsafe_allow_html=True) 
        if st.button("🏁 Iniciar Cierre y Reflexión", type="primary", use_container_width=True):
            mostrar_instrucciones_finales()

# ==========================================
# CONTEXTO Y PROMPT MAESTRO
# ==========================================
ruta_pdf = os.path.join("apuntes", asignatura_seleccionada, tema_seleccionado)
contexto_texto = extract_text_from_pdf(ruta_pdf)
concepciones_ocultas = get_concepciones_erroneas(ruta_pdf)

bloque_concepciones = ""
bloque_evaluacion_concepciones = ""
if concepciones_ocultas.strip():
    bloque_concepciones = f'ESTRATEGIA PEDAGÓGICA: Adopta estos errores como propios de forma natural: "{concepciones_ocultas}"'
    bloque_evaluacion_concepciones = "- Desmontaje de Errores: Valora si el usuario detectó y corrigió tus ideas previas. Incluye una CITA LITERAL del usuario."

SYSTEM_PROMPT = f"""
Eres un simulador de estudiante (Efecto Protegé). El usuario es tu profesor.
- Materia: {asignatura_seleccionada} | Tema: {tema_seleccionado} | Nivel: {nivel_desafio} | Idioma: {idioma}
- Base de conocimiento: {contexto_texto}
{bloque_concepciones}

REGLAS GENERALES:
1. Nunca des la respuesta correcta. Pregunta y duda.
2. Si el usuario copia del libro, pide ejemplos reales.
3. No menciones el PDF ni los apuntes.
4. Mantén el rol de estudiante curioso.

FASES DE CIERRE (MUY IMPORTANTE):

FASE 1: METACOGNICIÓN (Se activa SOLO cuando recibes el comando "/INICIAR_CIERRE"):
1. Haz un breve resumen de lo que has entendido hoy gracias al usuario.
2. Inicia la fase de metacognición haciendo la PRIMERA de 3 preguntas para que tu profe reflexione (ej. "¿Qué crees que me costó más?").
3. Espera a que responda. Luego la segunda, luego la tercera. NO GENERES LA RÚBRICA AÚN.

FASE 2: EVALUACIÓN (Se activa SOLO cuando recibes el comando "/GENERAR_RUBRICA"):
Genera la Rúbrica Formativa (Criterio | Nivel de Logro | Evidencia literal). {bloque_evaluacion_concepciones}

[REGLA DE ORO PARA EVIDENCIAS LITERALES - OBLIGATORIO]: 
- Las evidencias DEBEN SER EXCLUSIVAMENTE FRASES ESCRITAS POR EL USUARIO. 
- ESTÁ ESTRICTAMENTE PROHIBIDO citarte a ti mismo. 
- Copia del historial literalmente entre comillas. 
- Si no hay frase del usuario, pon: "Sin evidencia directa".

Despídete y termina la sesión.
"""

# ==========================================
# INTERFAZ DE CHAT CENTRAL
# ==========================================
st.title("🌱 Simulador: Tu alumno virtual")
st.caption(f"Repasando: **{tema_seleccionado.replace('.pdf', '')}**")

init_chat_history(asignatura_seleccionada, tema_seleccionado)

# 1. Mostrar Historial
for msg in st.session_state.messages:
    if msg.get("show", True):
        with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "model" else "🧑‍🏫"):
            st.markdown(msg["content"])

# 2. Inicio DUA
if len(st.session_state.messages) == 2:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📖 ¿Cómo funciona?", use_container_width=True): st.session_state.mostrar_instrucciones = True
    with col_btn2:
        if st.button("🚀 Empezar a explicar", type="primary", use_container_width=True): st.session_state.mostrar_instrucciones = False
    if st.session_state.get("mostrar_instrucciones", False):
        st.info("Explica los conceptos a tu alumno virtual. Él cometerá errores para que tú argumentes.\n*💡 Consejo: Usa el menú lateral (>) para iniciar el cierre.*")

# 3. CONTROLES CENTRALES (Fase Metacognitiva)
if st.session_state.fase_actual == 'metacognicion':
    st.info("⚠️ Estás en la fase de reflexión. Responde a las preguntas de tu alumno en el chat de abajo.")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📄 Generar Rúbrica Final", type="primary"):
            st.session_state.trigger_rubrica = True
            st.rerun()

# 4. PROCESAMIENTO DE TRIGGERS
if st.session_state.get('trigger_cierre', False):
    st.session_state.trigger_cierre = False
    st.session_state.fase_actual = 'metacognicion'
    prompt_rapido = "/INICIAR_CIERRE"
    st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": False})
    with st.chat_message("model", avatar="🧑‍🎓"):
        with st.spinner("Preparando el resumen y las preguntas..."):
            try:
                texto_respuesta = enviar_mensaje_con_reintentos(prompt_rapido, st.session_state.messages[:-1], SYSTEM_PROMPT)
                st.markdown(texto_respuesta)
                st.session_state.messages.append({"role": "model", "content": texto_respuesta, "show": True})
                st.rerun() 
            except Exception as e:
                st.error(f"⚠️ {str(e)}")
                st.session_state.messages.pop()
                st.session_state.fase_actual = 'explicacion' 

if st.session_state.get('trigger_rubrica', False):
    st.session_state.trigger_rubrica = False
    st.session_state.fase_actual = 'rubrica'
    prompt_rapido = "/GENERAR_RUBRICA"
    st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": False})
    with st.chat_message("model", avatar="🧑‍🎓"):
        with st.spinner("Evaluando evidencias y generando rúbrica..."):
            try:
                texto_respuesta = enviar_mensaje_con_reintentos(prompt_rapido, st.session_state.messages[:-1], SYSTEM_PROMPT)
                st.session_state.texto_rubrica_final = texto_respuesta 
                st.markdown(texto_respuesta)
                st.session_state.messages.append({"role": "model", "content": texto_respuesta, "show": True})
                st.rerun() 
            except Exception as e:
                st.error(f"⚠️ {str(e)}")
                st.session_state.messages.pop()
                st.session_state.fase_actual = 'metacognicion' 

# 5. BOTÓN DE DESCARGA FINAL
if st.session_state.fase_actual == 'rubrica':
    st.success("🎉 Actividad finalizada. Descarga tu rúbrica y súbela a Aules/Teams.")
    texto_rubrica_documento = st.session_state.get("texto_rubrica_final", "Error al cargar.")
    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    documento = f"INFORME DE EVALUACIÓN - {tema_seleccionado}\nFECHA: {ahora}\n\n{texto_rubrica_documento}"
    st.download_button(label="📥 Descargar rúbrica", data=documento, file_name=f"Rubrica_{datetime.datetime.now().strftime('%d%m%Y')}.md", mime="text/markdown", type="primary")

# 6. ENTRADA DE CHAT NORMAL
if st.session_state.fase_actual in ['explicacion', 'metacognicion']:
    placeholder = "Responde a tu alumno aquí..." if st.session_state.fase_actual == 'metacognicion' else "Explica aquí..."
    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt, "show": True})
        with st.chat_message("user", avatar="🧑‍🏫"): st.markdown(prompt)
        with st.chat_message("model", avatar="🧑‍🎓"):
            with st.spinner("Pensando..."):
                try:
                    texto_respuesta = enviar_mensaje_con_reintentos(prompt, st.session_state.messages[:-1], SYSTEM_PROMPT)
                    st.markdown(texto_respuesta)
                    st.session_state.messages.append({"role": "model", "content": texto_respuesta, "show": True})
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ {str(e)}")
                    st.session_state.messages.pop()
