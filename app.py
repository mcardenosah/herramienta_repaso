import os
import streamlit as st
from google import genai
from google.genai import types
import PyPDF2
import datetime

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
# FUNCIONES AUXILIARES DE ARCHIVOS
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

# ==========================================
# DIÁLOGO DE INSTRUCCIONES FINALES
# ==========================================
@st.dialog("📝 Próximos pasos para tu evaluación")
def mostrar_instrucciones_finales():
    st.markdown("""
    Has terminado la sesión de explicación. Para completar la actividad correctamente, sigue estos pasos:
    
    1. **Lee el resumen** que ha preparado tu "alumno virtual" para comprobar qué ha aprendido.
    2. **Responde a las 3 preguntas** de reflexión que te hará a continuación.
    3. Al finalizar, pulsa el botón **'📥 Descargar rúbrica'** que aparecerá abajo del todo.
    4. Sube el archivo descargado (`.md`) a la tarea correspondiente en **Aules** o **Microsoft Teams**.
    
    *Ya puedes cerrar esta ventana para ver tu informe.*
    """)
    if st.button("Entendido, cerrar", type="primary", use_container_width=True):
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
        st.session_state.evaluacion_finalizada = False # Control de estado
    
    if len(st.session_state.messages) == 0:
        st.session_state.messages.append({"role": "user", "content": f"Inicio sesión: {tema}", "show": False})
        st.session_state.messages.append({
            "role": "model", 
            "content": f"¡Hola! Ya estoy listo para que repasemos el tema de **{tema.replace('.pdf', '').replace('_', ' ')}**. ¿Por qué concepto empezamos hoy?",
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
# PANEL LATERAL
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
    if st.button("🧹 Reiniciar Conversación"):
        st.session_state.messages = []; st.rerun()

# ==========================================
# CONTEXTO Y PROMPT
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

REGLAS:
1. Nunca des la respuesta correcta. Pregunta y duda.
2. Si el usuario copia del libro, pide ejemplos reales.
3. No menciones el PDF ni los apuntes.
4. Mantén el rol de estudiante curioso.

CIERRE (/FIN_DIALOGO):
1. Resume lo aprendido.
2. Haz 3 preguntas metacognitivas una a una.
3. Genera Rúbrica (Criterio | Nivel | Evidencia literal). {bloque_evaluacion_concepciones}
REGLA CRÍTICA: La "Evidencia literal" debe ser SIEMPRE una frase entre comillas escrita por el USUARIO. Prohibido citarte a ti mismo.
"""

# ==========================================
# INTERFAZ DE CHAT
# ==========================================
st.title("🌱 Simulador: Tu alumno virtual")
st.caption(f"Repasando: **{tema_seleccionado.replace('.pdf', '')}**")

if not api_key: st.stop()
client = genai.Client(api_key=api_key)
init_chat_history(asignatura_seleccionada, tema_seleccionado)

# Estado de finalización
dialogo_terminado = st.session_state.evaluacion_finalizada or (len(st.session_state.messages) > 2 and st.session_state.messages[-1].get("content") == "/FIN_DIALOGO")

# 1. Historial
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
        if st.button("🚀 Empezar", type="primary", use_container_width=True): st.session_state.mostrar_instrucciones = False
    if st.session_state.get("mostrar_instrucciones", False):
        st.info("Explica los conceptos a tu alumno virtual. Él dudará para que tú tengas que argumentar.")

# 3. Botón Terminar y Evaluación
if len(st.session_state.messages) > 2 and not st.session_state.evaluacion_finalizada:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🏁 Terminar", help="Finaliza y evalúa"):
            # ACTIVAMOS EL DIÁLOGO EMERGENTE
            mostrar_instrucciones_finales()
            
            prompt_rapido = "/FIN_DIALOGO"
            st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": True})
            with st.chat_message("model", avatar="🧑‍🎓"):
                with st.spinner("Generando evaluación..."):
                    try:
                        formatted_history = [types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                        chat = client.chats.create(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT), history=formatted_history)
                        response = chat.send_message(prompt_rapido)
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                        st.session_state.evaluacion_finalizada = True
                        st.rerun()
                    except Exception as e:
                        print(f"ERROR DE API: {e}")
                        st.error("⚠️ Error de conexión. Reintenta.")
                        st.session_state.messages.pop()

# 4. Descarga
if st.session_state.evaluacion_finalizada:
    st.success("🎉 Actividad finalizada. Descarga tu rúbrica.")
    texto_rubrica = st.session_state.messages[-1]["content"]
    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    documento = f"INFORME - {tema_seleccionado}\nFECHA: {ahora}\n\n{texto_rubrica}"
    st.download_button(label="📥 Descargar rúbrica", data=documento, file_name=f"Rubrica_{datetime.datetime.now().strftime('%d%m%Y')}.md", mime="text/markdown", type="primary")

# 5. Entrada Chat (Se oculta al terminar)
if not st.session_state.evaluacion_finalizada:
    if prompt := st.chat_input("Explica aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt, "show": True})
        with st.chat_message("user", avatar="🧑‍🏫"): st.markdown(prompt)
        with st.chat_message("model", avatar="🧑‍🎓"):
            with st.spinner("Pensando..."):
                try:
                    formatted_history = [types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                    chat = client.chats.create(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT), history=formatted_history)
                    response = chat.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                    st.rerun()
                except Exception as e:
                    print(f"ERROR DE API: {e}")
                    st.error("⚠️ Ha habido un microcorte de conexión. Por favor, vuelve a intentar enviar el mensaje.")
                    st.session_state.messages.pop()
