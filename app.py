import os
import streamlit as st
from google import genai
from google.genai import types
import PyPDF2
import datetime
import time

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
    """Extrae el texto de un archivo PDF dado su ruta."""
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
    """Busca de forma invisible un archivo .txt con el sufijo '_errores.txt'."""
    txt_filepath = pdf_filepath.replace('.pdf', '_errores.txt')
    if os.path.exists(txt_filepath):
        try:
            with open(txt_filepath, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error al leer el archivo de concepciones: {e}")
            return ""
    return ""

def get_asignaturas(directory="apuntes"):
    """Lee la carpeta raíz y devuelve las subcarpetas (Asignaturas)."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        return []
    asignaturas = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
    return sorted(asignaturas)

def get_temas(asignatura, directory="apuntes"):
    """Devuelve los PDFs dentro de la carpeta de la asignatura seleccionada."""
    path = os.path.join(directory, asignatura)
    if not os.path.exists(path):
        return []
    pdfs = [f for f in os.listdir(path) if f.endswith('.pdf')]
    return sorted(pdfs)

def enviar_mensaje_con_reintentos(client, prompt_text, history, system_prompt):
    """
    AMORTIGUADOR DE ERRORES ABSOLUTO (Exponential Backoff).
    Atrapa cualquier fallo de la API de Google y reintenta de forma silenciosa.
    """
    max_intentos = 4
    ultimo_error = None
    
    for intento in range(max_intentos):
        try:
            chat = client.chats.create(
                model="gemini-2.0-flash", # CAMBIO CRÍTICO: Bajada a la versión estable 2.0
                config=types.GenerateContentConfig(system_instruction=system_prompt),
                history=history
            )
            response = chat.send_message(prompt_text)
            return response
        except Exception as e:
            ultimo_error = e
            if intento < max_intentos - 1:
                time.sleep(2 ** intento)  # Espera 1s, luego 2s, luego 4s...
            else:
                raise ultimo_error # Si después de 4 intentos sigue roto, lanza el error real.

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
        st.session_state.fase_actual = 'explicacion' # Estados: 'explicacion', 'metacognicion', 'rubrica'
        st.session_state.trigger_cierre = False
        st.session_state.trigger_rubrica = False
        st.session_state.texto_rubrica_final = "" 
    
    if len(st.session_state.messages) == 0:
        st.session_state.messages.append({"role": "user", "content": f"Inicio sesión: {tema}", "show": False})
        
        # El alumno virtual toma la iniciativa
        tema_limpio = tema.replace('.pdf', '').replace('_', ' ')
        st.session_state.messages.append({
            "role": "model", 
            "content": f"¡Hola! He estado intentando estudiar el tema de **{tema_limpio}**, pero la verdad es que me cuesta un poco arrancar. ¿Me podrías explicar con tus propias palabras cuál es la idea principal o el concepto más importante para empezar a situarme?",
            "show": True
        })

# ==========================================
# GESTIÓN DE LA API KEY
# ==========================================
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = st.sidebar.text_input("🔑 API Key de Gemini", type="password")

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
        if st.button("🏁 Iniciar Cierre y Reflexión", type="primary", use_container_width=True, help="Termina la explicación y pasa a la metacognición"):
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

FASE 1: METACOGNICIÓN (Se activa SOLO cuando recibes el comando oculto "/INICIAR_CIERRE"):
1. Haz un breve resumen de lo que has entendido hoy gracias al usuario.
2. Inicia la fase de metacognición haciendo la PRIMERA de 3 preguntas para que el usuario (tu profe) reflexione sobre su forma de explicar (ej. "¿Qué parte crees que me ha costado más entender?", "¿Qué cambiarías si me lo tuvieras que explicar mañana?").
3. Espera a que el usuario responda en su turno. Luego haz la segunda pregunta, y luego la tercera. NO GENERES LA RÚBRICA AÚN.

FASE 2: EVALUACIÓN (Se activa SOLO cuando recibes el comando oculto "/GENERAR_RUBRICA"):
Genera la Rúbrica Formativa (Criterio | Nivel de Logro | Evidencia literal). {bloque_evaluacion_concepciones}

[REGLA DE ORO PARA EVIDENCIAS LITERALES - OBLIGATORIO]: 
- Las evidencias de la rúbrica DEBEN SER EXCLUSIVAMENTE FRASES ESCRITAS POR EL USUARIO. 
- ESTÁ ESTRICTAMENTE PROHIBIDO citar tus propios textos (los del estudiante virtual). 
- Busca en el historial lo que te ha escrito el usuario y cópialo literalmente entre comillas. 
- Si no hay una frase del usuario que sirva de evidencia para un criterio concreto, pon obligatoriamente: "Sin evidencia directa en el texto del alumno".

Despídete y da por terminada la sesión.
"""

# ==========================================
# INTERFAZ DE CHAT CENTRAL
# ==========================================
st.title("🌱 Simulador: Tu alumno virtual")
st.caption(f"Repasando: **{tema_seleccionado.replace('.pdf', '')}**")

if not api_key: st.stop()
client = genai.Client(api_key=api_key)
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
        st.info("""
        **Tu objetivo:** Explica los conceptos a tu alumno virtual respondiendo a sus dudas. Él cometerá errores para que tú tengas que argumentar científicamente.
        *💡 Consejo: Cuando consideres que la explicación ha terminado, abre el menú lateral izquierdo (>) y pulsa 'Iniciar Cierre y Reflexión'.*
        """)

# 3. CONTROLES CENTRALES (Fase Metacognitiva)
if st.session_state.fase_actual == 'metacognicion':
    st.info("⚠️ Estás en la fase de reflexión. Responde a las preguntas de tu alumno en el chat de abajo.")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📄 Generar Rúbrica Final", type="primary", help="Cierra el chat y evalúa"):
            st.session_state.trigger_rubrica = True
            st.rerun()

# 4. PROCESAMIENTO DE TRIGGERS CON REINTENTOS BLINDADOS
if st.session_state.get('trigger_cierre', False):
    st.session_state.trigger_cierre = False
    st.session_state.fase_actual = 'metacognicion'
    prompt_rapido = "/INICIAR_CIERRE"
    st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": False})
    with st.chat_message("model", avatar="🧑‍🎓"):
        with st.spinner("Preparando el resumen y las preguntas..."):
            try:
                formatted_history = [types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                response = enviar_mensaje_con_reintentos(client, prompt_rapido, formatted_history, SYSTEM_PROMPT)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                st.rerun() 
            except Exception as e:
                print(f"ERROR DE API: {e}")
                # AHORA IMPRIME EL ERROR EXACTO PARA PODER DEPURAR
                st.error(f"⚠️ Error de la API de Google. Detalle técnico: {str(e)}")
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
                formatted_history = [types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                response = enviar_mensaje_con_reintentos(client, prompt_rapido, formatted_history, SYSTEM_PROMPT)
                st.session_state.texto_rubrica_final = response.text 
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                st.rerun() 
            except Exception as e:
                print(f"ERROR DE API: {e}")
                st.error(f"⚠️ Error de la API de Google. Detalle técnico: {str(e)}")
                st.session_state.messages.pop()
                st.session_state.fase_actual = 'metacognicion' 

# 5. BOTÓN DE DESCARGA FINAL
if st.session_state.fase_actual == 'rubrica':
    st.success("🎉 Actividad finalizada. Descarga tu rúbrica y súbela a Aules/Teams.")
    texto_rubrica_documento = st.session_state.get("texto_rubrica_final", "Error al cargar la rúbrica.")
    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    documento = f"INFORME DE EVALUACIÓN - {tema_seleccionado}\nFECHA: {ahora}\n\n{texto_rubrica_documento}"
    st.download_button(label="📥 Descargar rúbrica", data=documento, file_name=f"Rubrica_{datetime.datetime.now().strftime('%d%m%Y')}.md", mime="text/markdown", type="primary")

# 6. ENTRADA DE CHAT NORMAL CON REINTENTOS BLINDADOS
if st.session_state.fase_actual in ['explicacion', 'metacognicion']:
    placeholder = "Responde a tu alumno aquí..." if st.session_state.fase_actual == 'metacognicion' else "Explica aquí..."
    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt, "show": True})
        with st.chat_message("user", avatar="🧑‍🏫"): st.markdown(prompt)
        with st.chat_message("model", avatar="🧑‍🎓"):
            with st.spinner("Pensando..."):
                try:
                    formatted_history = [types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                    response = enviar_mensaje_con_reintentos(client, prompt, formatted_history, SYSTEM_PROMPT)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                    st.rerun()
                except Exception as e:
                    print(f"ERROR DE API: {e}")
                    # AHORA IMPRIME EL ERROR EXACTO PARA PODER DEPURAR
                    st.error(f"⚠️ Fallo en el servidor. Detalle técnico: {str(e)}")
                    st.session_state.messages.pop()
