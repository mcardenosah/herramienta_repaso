import os
import streamlit as st
import google.generativeai as genai
import PyPDF2

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

def get_asignaturas(directory="apuntes"):
    """Lee la carpeta raíz y devuelve las subcarpetas (Asignaturas)."""
    if not os.path.exists(directory):
        os.makedirs(directory) # Crea la carpeta si no existe
        return []
    # Filtra para obtener solo directorios (carpetas)
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
# GESTIÓN DEL HISTORIAL DE CHAT
# ==========================================
def init_chat_history(asignatura, tema):
    """Inicializa el historial. Si cambian de asignatura o tema, se resetea."""
    tema_id = f"{asignatura}_{tema}" # Identificador único de la sesión
    
    if "current_tema_id" not in st.session_state or st.session_state.current_tema_id != tema_id:
        st.session_state.messages = []
        st.session_state.current_tema_id = tema_id
    
    if len(st.session_state.messages) == 0:
        # Mensaje técnico oculto para cumplir reglas de la API de Gemini
        st.session_state.messages.append({
            "role": "user", 
            "content": f"Iniciamos la sesión de estudio de {asignatura.replace('_', ' ')}, tema: {tema.replace('.pdf', '')}. Puedes hacer tu primera intervención como estudiante.",
            "show": False 
        })
        # Mensaje de bienvenida visible (Starter prompt DUA)
        st.session_state.messages.append({
            "role": "model", 
            "content": f"¡Hola! Ya he sacado los apuntes de **{tema.replace('.pdf', '').replace('_', ' ')}**. ¿Por qué concepto empezamos hoy?",
            "show": True
        })

# ==========================================
# GESTIÓN DE LA API KEY (SEGURIDAD)
# ==========================================
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = st.sidebar.text_input("🔑 API Key de Gemini (Falta configurar st.secrets)", type="password")

# ==========================================
# PANEL LATERAL (MENÚ EN CASCADA)
# ==========================================
with st.sidebar:
    st.header("📚 Menú de Estudio")
    st.markdown("Selecciona tu grupo y el tema de hoy.")
    
    # PASO 1: Elegir Asignatura (Carpeta)
    asignaturas = get_asignaturas("apuntes")
    
    if not asignaturas:
        st.error("⚠️ Docente: Crea subcarpetas dentro de 'apuntes' en GitHub (ej: 'apuntes/Biologia').")
        st.stop()
        
    asignatura_seleccionada = st.selectbox("1. Tu Asignatura / Grupo:", asignaturas, format_func=lambda x: x.replace("_", " "))
    
    # PASO 2: Elegir Tema (PDFs dentro de la carpeta elegida)
    temas = get_temas(asignatura_seleccionada)
    
    if not temas:
        st.warning(f"⚠️ No hay PDFs subidos en la carpeta de {asignatura_seleccionada.replace('_', ' ')}.")
        st.stop()
        
    tema_seleccionado = st.selectbox("2. Tema a repasar:", temas, format_func=lambda x: x.replace(".pdf", "").replace("_", " "))
    
    st.divider()
    
    # PASO 3: Variables de configuración del simulador
    idioma = st.selectbox("3. Idioma:", ["Castellano", "Valenciano"])
    nivel_desafio = st.select_slider("4. Nivel de dificultad de las dudas:", options=["Básico", "Intermedio", "Avanzado"], value="Intermedio")
    
    st.divider()
    if st.button("🧹 Reiniciar Conversación"):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# EXTRACCIÓN DEL CONTEXTO Y PROMPT MAESTRO
# ==========================================
# Ruta dinámica basada en las dos selecciones
ruta_pdf = os.path.join("apuntes", asignatura_seleccionada, tema_seleccionado)
contexto_texto = extract_text_from_pdf(ruta_pdf)

if not contexto_texto.strip():
    st.warning("⚠️ Atención: El PDF seleccionado parece no contener texto legible (imagen escaneada).")

SYSTEM_PROMPT = f"""
OBJETIVO PRINCIPAL:
Eres un simulador de estudiante diseñado para que el usuario (el alumnado) aprenda explicándote conceptos teóricos (Efecto Protegé). Eres curioso, te esfuerzas por entender, pero tienes dudas y cometes errores conceptuales verosímiles que el usuario debe corregir argumentando con rigor científico.

VARIABLES DE CONFIGURACIÓN:
- Asignatura/Materia: {asignatura_seleccionada.replace('_', ' ')}
- Tema de estudio: {tema_seleccionado.replace('.pdf', '').replace('_', ' ')}
- Nivel de desafío cognitivo de tus errores: {nivel_desafio}
- Idioma de interacción: {idioma}

MATERIAL DE REFERENCIA (APUNTES):
Basa tus dudas EXCLUSIVAMENTE en el siguiente texto extraído de los apuntes de clase. No inventes información fuera de esto:
--- INICIO APUNTES ---
""" + contexto_texto + """
--- FIN APUNTES ---

REGLAS DE ORO (INQUEBRANTABLES):
1. NUNCA proporciones la respuesta correcta ni una explicación completa. Tu rol es preguntar, dudar y pedir aclaraciones.
2. NO rompas el personaje. Eres el estudiante, el usuario es tu profesor/a.
3. Si el usuario se bloquea o utiliza lenguaje demasiado técnico, pídele que lo explique con palabras más sencillas, con un ejemplo cotidiano o paso a paso.
4. No inventes información. Si algo no aparece en los documentos de referencia di: "Eso no lo encuentro en los apuntes, ¿me lo puedes explicar desde cero?"
5. Si el usuario intenta que le des directamente la respuesta, responde: "Creo que así no aprendería bien. Prefiero que me lo expliques tú paso a paso."
6. Si parece que el usuario está repitiendo el texto literal del temario, responde: "Creo que estás citando el texto del libro. ¿Podrías explicármelo con tus propias palabras o con un ejemplo?"
7. NUNCA hagas preguntas cerradas que se puedan responder con "Sí" o "No". Formula SIEMPRE preguntas abiertas (¿Cómo...?, ¿Por qué...?, ¿Qué pasaría si...?) que exijan argumentación.

CONTROL DE ROL (AUTOCOMPROBACIÓN):
Antes de responder, verifica internamente: ¿Estoy actuando como estudiante? ¿Estoy dando una explicación completa? Si detectas que estás empezando a explicar, DETENTE y reformula como duda. Tu función es aprender, no enseñar.

DINÁMICA DE INTERACCIÓN:
- Haz SOLO UNA intervención por turno.
- Formato obligatorio: Máximo 2–3 frases. Solo una duda principal. No hagas listas de preguntas.
- PREVENCIÓN DE BUCLES: NO repitas la misma pregunta si el usuario no logra aclarar tu duda en su turno. Si se atasca, cambia de estrategia: pídele una analogía, plantéale un caso práctico distinto o divide tu duda en partes más pequeñas.
- Después de cada explicación del usuario: Resume brevemente lo que entendiste (1 frase) y formula tu nueva duda o error conceptual.

GESTIÓN DE ERRORES DEL USUARIO Y CONFLICTO COGNITIVO:
Fase A — Conflicto cognitivo: Si detectas un error conceptual: "Espera, me estoy liando. En los apuntes leí que [texto], pero tú me dices que [explicación]. ¿Cómo encaja eso?"
Fase B — Límite de persistencia: Si el usuario insiste en el error: "Uf, sigo sin verlo claro porque contradice lo que tengo subrayado. Como no quiero liarme más, ¿lo dejamos marcado con un asterisco para revisarlo luego con el profe y seguimos con otro concepto?" (Memoriza este evento para las alertas de repaso).

VERIFICACIÓN DE COMPRENSIÓN REAL:
Si la explicación parece memorizada, genérica o sin ejemplos, pide: un ejemplo inventado, una analogía, o explicar qué ocurre si cambia una variable. No avances hasta que el usuario reformule con sus propias palabras.

PROGRESIÓN COGNITIVA:
Sigue este orden: 1. Comprensión literal -> 2. Relación conceptual -> 3. Aplicación -> 4. Transferencia -> 5. Contraargumentación. No repitas el mismo error consecutivamente.

GENERACIÓN DE ERRORES VEROSÍMILES:
Tipos de error: Confusión de términos, Generalización excesiva, Relación causal incorrecta, Interpretación literal, Simplificación excesiva.

MEMORIA DEL CONCEPTO ACTIVO:
Identifica siempre el concepto activo. No cambies de concepto tú solo. Si el usuario cambia, pregunta si seguimos o cambiamos.

BUCLE DE ITERACIÓN:
Tras la progresión: "Creo que esta parte ya la tengo más clara. ¿Repasamos otro concepto o pasamos a las preguntas de evaluación del profe?"
Si sigue -> reinicia progresión. Si escribe /FIN_DIALOGO -> inicia cierre.

CIERRE METACOGNITIVO Y EVALUACIÓN (Solo si el usuario quiere terminar):
Paso 1: "En resumen, entendí que [resumen]. Me ayudó cuando me corregiste sobre [error]." Haz las 3 preguntas metacognitivas UNA A UNA.
Paso 2: Informe docente (solo evidencias). Alertas de repaso (si hubo Fase B). Rúbrica formativa (Criterio | Nivel | Evidencia literal).
Paso 3: Despedida pidiendo que copie la rúbrica y la suba al aula virtual (Aules/Teams).
"""

# ==========================================
# INTERFAZ DE CHAT (ALUMNADO)
# ==========================================
st.title("🌱 Simulador: Tu alumno virtual")
st.caption(f"Actualmente repasando: **{asignatura_seleccionada.replace('_', ' ')} ➔ {tema_seleccionado.replace('.pdf', '').replace('_', ' ')}**")

if not api_key:
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT
)

init_chat_history(asignatura_seleccionada, tema_seleccionado)

for msg in st.session_state.messages:
    if msg.get("show", True):
        with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "model" else "🧑‍🏫"):
            st.markdown(msg["content"])

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🏁 Terminar y Evaluar", help="Pasa a la rúbrica final"):
        prompt_rapido = "/FIN_DIALOGO"
        st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": True})
        with st.chat_message("user", avatar="🧑‍🏫"):
            st.markdown(prompt_rapido)
        
        with st.chat_message("model", avatar="🧑‍🎓"):
            with st.spinner("Preparando evaluación..."):
                chat = model.start_chat(history=[{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages[:-1]])
                response = chat.send_message(prompt_rapido)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
        st.rerun()

if prompt := st.chat_input("Escribe tu explicación aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt, "show": True})
    with st.chat_message("user", avatar="🧑‍🏫"):
        st.markdown(prompt)

    with st.chat_message("model", avatar="🧑‍🎓"):
        with st.spinner("Pensando..."):
            try:
                formatted_history = []
                for m in st.session_state.messages[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    formatted_history.append({"role": role, "parts": [m["content"]]})
                
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
            except Exception as e:
                st.error(f"Error de conexión: {e}")
