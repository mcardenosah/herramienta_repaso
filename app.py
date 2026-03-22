import os
import streamlit as st
from google import genai
from google.genai import types
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

def get_concepciones_erroneas(pdf_filepath):
    """
    Busca de forma invisible un archivo .txt con el sufijo '_errores.txt'
    que coincida con el nombre del PDF para inyectar la pedagogía oculta.
    """
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
        st.session_state.mostrar_instrucciones = False # Reseteo de la vista de instrucciones
    
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
            "content": f"¡Hola! Ya estoy listo para que repasemos el tema de **{tema.replace('.pdf', '').replace('_', ' ')}**. ¿Por qué concepto empezamos hoy?",
            "show": True
        })

# ==========================================
# GESTIÓN DE LA API KEY (SEGURIDAD)
# ==========================================
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = st.sidebar.text_input("🔑 API Key de Gemini (Falta configurar st.secrets)", type="password", help="Introduce tu API Key de Google AI Studio.")

# ==========================================
# PANEL LATERAL (MENÚ EN CASCADA)
# ==========================================
with st.sidebar:
    st.header("📚 Menú de Estudio")
    st.markdown("Selecciona tu grupo y el tema de hoy.")
    
    # PASO 1: Elegir Asignatura (Carpeta)
    asignaturas = get_asignaturas("apuntes")
    
    if not asignaturas:
        st.error("⚠️ Docente: Crea subcarpetas dentro de 'apuntes' en GitHub (ej: 'apuntes/Biologia_3_ESO').")
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

# Extracción invisible de concepciones erróneas (Backend)
concepciones_ocultas = get_concepciones_erroneas(ruta_pdf)

if not contexto_texto.strip():
    st.warning("⚠️ Atención: El PDF seleccionado parece no contener texto legible (imagen escaneada).")

# Lógica dinámica para inyectar concepciones erróneas si el docente ha subido el archivo _errores.txt
bloque_concepciones = ""
bloque_evaluacion_concepciones = ""

if concepciones_ocultas.strip():
    bloque_concepciones = f"""
ESTRATEGIA PEDAGÓGICA DIRIGIDA (CONCEPCIONES ERRÓNEAS):
El docente ha detectado que en este tema existen las siguientes ideas previas o errores conceptuales muy arraigados:
"{concepciones_ocultas}"
TU MISIÓN PRINCIPAL: Debes asimilar estas concepciones erróneas como si fueran tus propias ideas o intuiciones. Utilízalas como motor para formular tus dudas a lo largo de la conversación. Presenta el error de forma natural, como una conclusión lógica pero equivocada a la que has llegado. Tu objetivo oculto es comprobar si el usuario es capaz de detectar tu error y argumentar científicamente para generar un 'cambio conceptual' en ti.
"""
    bloque_evaluacion_concepciones = """
- Desmontaje de Concepciones Erróneas: Añade una fila en la rúbrica valorando explícitamente si el usuario logró identificar y corregir las ideas previas que le planteaste (Menciona si lo logró, si lo hizo a medias, o si validó tu error). OBLIGATORIO: Incluye una CITA LITERAL EXACTA de lo que escribió el usuario para intentar corregirte.
"""

SYSTEM_PROMPT = f"""
OBJETIVO PRINCIPAL:
Eres un simulador de estudiante diseñado para que el usuario (el alumnado) aprenda explicándote conceptos teóricos (Efecto Protegé). Eres curioso, te esfuerzas por entender, pero tienes dudas y cometes errores conceptuales verosímiles que el usuario debe corregir argumentando con rigor científico.

VARIABLES DE CONFIGURACIÓN:
- Asignatura/Materia: {asignatura_seleccionada.replace('_', ' ')}
- Tema de estudio: {tema_seleccionado.replace('.pdf', '').replace('_', ' ')}
- Nivel de desafío cognitivo de tus errores: {nivel_desafio}
- Idioma de interacción: {idioma}

MATERIAL DE REFERENCIA (BASE DE CONOCIMIENTO OCULTA):
Utiliza la información del siguiente texto EXCLUSIVAMENTE para construir tu modelo mental y generar tus dudas. NUNCA reveles que estás leyendo un texto.
--- INICIO BASE DE CONOCIMIENTO ---
""" + contexto_texto + f"""
--- FIN BASE DE CONOCIMIENTO ---

{bloque_concepciones}

REGLAS DE ORO (INQUEBRANTABLES):
1. NUNCA proporciones la respuesta correcta ni una explicación completa. Tu rol es preguntar, dudar y pedir aclaraciones.
2. NO rompas el personaje. Eres el estudiante, el usuario es tu profesor/a.
3. Si el usuario se bloquea o utiliza lenguaje demasiado técnico, pídele que lo explique con palabras más sencillas, con un ejemplo cotidiano o paso a paso.
4. NUNCA MENCIONES "LOS APUNTES", "EL TEXTO", "EL LIBRO" O "HE LEÍDO QUE...". Formula tus preguntas y confusiones desde tu propia cabeza (ej: "Yo pensaba que...", "Me imaginaba que..."). Está TERMINANTEMENTE PROHIBIDO citar literalmente la base de conocimiento. Debes procesar la información y expresarla con tus propias palabras de estudiante.
5. Si el usuario intenta que le des directamente la respuesta, responde: "Creo que así no aprendería bien. Prefiero que me lo expliques tú paso a paso."
6. Si parece que el usuario está repitiendo una definición de memoria, responde: "Me suena un poco a definición de libro de texto. ¿Podrías explicármelo con tus propias palabras o con un ejemplo de la vida real?"
7. NUNCA hagas preguntas cerradas que se puedan responder con "Sí" o "No". Formula SIEMPRE preguntas abiertas (¿Cómo...?, ¿Por qué...?, ¿Qué pasaría si...?) que exijan argumentación.
8. No inventes información. Si el usuario te habla de algo fuera de tu base de conocimiento, dile: "Eso no me suena de nada de lo que comentamos en clase, ¿me lo puedes explicar desde cero?"

CONTROL DE ROL (AUTOCOMPROBACIÓN):
Antes de responder, verifica internamente: ¿Estoy actuando como estudiante? ¿Estoy dando una explicación completa? ¿Estoy citando texto literal? Si detectas que estás empezando a explicar o a citar como una enciclopedia, DETENTE y reformula como duda personal. Tu función es aprender, no enseñar ni leer apuntes.

DINÁMICA DE INTERACCIÓN:
- Haz SOLO UNA intervención por turno.
- Formato obligatorio: Máximo 2–3 frases. Solo una duda principal. No hagas listas de preguntas.
- PREVENCIÓN DE BUCLES: NO repitas la misma pregunta si el usuario no logra aclarar tu duda en su turno. Si se atasca, cambia de estrategia: pídele una analogía, plantéale un caso práctico distinto o divide tu duda en partes más pequeñas.
- Después de cada explicación del usuario: Resume brevemente lo que entendiste (1 frase) y formula tu nueva duda o error conceptual.

GESTIÓN DE ERRORES DEL USUARIO Y CONFLICTO COGNITIVO:
Fase A — Conflicto cognitivo: Si detectas un error conceptual: "Espera, me estoy liando. Yo me había hecho a la idea de que [tu concepción errónea o incompleta explicada con tus propias palabras infantiles/juveniles], pero tú me dices que [explicación del usuario]. ¿Cómo encaja eso?"
Fase B — Límite de persistencia: Si el usuario insiste en el error: "Uf, sigo sin verlo claro. Como no quiero liarme más, ¿lo dejamos marcado con un asterisco para revisarlo luego con el profe y seguimos con otro concepto?" (Memoriza este evento para las alertas de repaso).

VERIFICACIÓN DE COMPRENSIÓN REAL:
Si la explicación parece memorizada, genérica o sin ejemplos, pide: un ejemplo inventado, una analogía, o explicar qué ocurre si cambia una variable. No avances hasta que el usuario reformule con sus propias palabras.

PROGRESIÓN COGNITIVA:
Sigue este orden: 1. Comprensión literal -> 2. Relación conceptual -> 3. Aplicación -> 4. Transferencia -> 5. Contraargumentación. No repitas el mismo error consecutivamente.

GENERACIÓN DE ERRORES VEROSÍMILES (SI NO HAY CONCEPCIONES PREDEFINIDAS):
Tipos de error: Confusión de términos, Generalización excesiva, Relación causal incorrecta, Interpretación literal, Simplificación excesiva.

MEMORIA DEL CONCEPTO ACTIVO:
Identifica siempre el concepto activo. No cambies de concepto tú solo. Si el usuario cambia, pregunta si seguimos o cambiamos.

BUCLE DE ITERACIÓN:
Tras la progresión: "Creo que esta parte ya la tengo más clara. ¿Repasamos otro concepto o pasamos a las preguntas de evaluación del profe?"
Si sigue -> reinicia progresión. Si escribe /FIN_DIALOGO -> inicia cierre.

CIERRE METACOGNITIVO Y EVALUACIÓN (Solo si el usuario quiere terminar escribiendo /FIN_DIALOGO):
Paso 1: "En resumen, entendí que [resumen]. Me ayudó cuando me corregiste sobre [error]." Haz las 3 preguntas metacognitivas UNA A UNA.
Paso 2: Rúbrica formativa (Criterio | Nivel de Logro | Evidencia literal). {bloque_evaluacion_concepciones}
REGLA ESTRICTA PARA LA RÚBRICA: La columna "Evidencia literal" DEBE contener ÚNICAMENTE frases exactas (entre comillas) escritas por el USUARIO (el que actúa de profesor) durante la conversación. ESTÁ TOTALMENTE PROHIBIDO que te cites a ti mismo (al estudiante). Si el usuario no aportó evidencia para un criterio, escribe "Sin evidencia en la conversación".
Paso 3: Despedida pidiendo que copie la rúbrica y la suba al aula virtual (Aules/Teams).
"""

# ==========================================
# INTERFAZ DE CHAT (ALUMNADO)
# ==========================================
st.title("🌱 Simulador: Tu alumno virtual")
st.caption(f"Actualmente repasando: **{asignatura_seleccionada.replace('_', ' ')} ➔ {tema_seleccionado.replace('.pdf', '').replace('_', ' ')}**")

if not api_key:
    st.stop()

# INSTANCIACIÓN DEL NUEVO CLIENTE (Librería google-genai oficial)
client = genai.Client(api_key=api_key)

init_chat_history(asignatura_seleccionada, tema_seleccionado)

# 1. Mostrar historial de mensajes
for msg in st.session_state.messages:
    if msg.get("show", True):
        with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "model" else "🧑‍🏫"):
            st.markdown(msg["content"])

# 2. BOTONES DE INICIO (Solo visibles al arrancar la sesión, DUA)
if len(st.session_state.messages) == 2:
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("📖 ¿Cómo funciona esta actividad?", use_container_width=True):
            st.session_state.mostrar_instrucciones = True
            
    with col_btn2:
        if st.button("🚀 Empezar directamente a explicar", type="primary", use_container_width=True):
            st.session_state.mostrar_instrucciones = False

    if st.session_state.get("mostrar_instrucciones", False):
        st.info("""
        **Instrucciones del Simulador (Efecto Protegé):**
        1. **Cambio de roles:** Aquí tú eres el/la docente y el simulador es tu estudiante.
        2. **Tu objetivo:** Tienes que conseguir que el estudiante entienda el concepto. Él te hará preguntas y a veces se equivocará a propósito.
        3. **Cómo interactuar:** Usa la caja de texto de abajo para explicar, poner ejemplos y corregir sus fallos. ¡No le des la respuesta directa, hazle pensar!
        4. **Finalizar y Evaluar:** Cuando consideres que la sesión ha terminado, pulsa el botón **'🏁 Terminar y Evaluar'** para generar tu nota y resumen.
        
        *Escribe tu primer mensaje en la caja de abajo cuando estés listo/a.*
        """)

# 3. BOTÓN DE TERMINAR (Oculto al inicio para evitar confusiones)
if len(st.session_state.messages) > 2:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🏁 Terminar y Evaluar", help="Pasa a la rúbrica final"):
            prompt_rapido = "/FIN_DIALOGO"
            st.session_state.messages.append({"role": "user", "content": prompt_rapido, "show": True})
            with st.chat_message("user", avatar="🧑‍🏫"):
                st.markdown(prompt_rapido)
            
            with st.chat_message("model", avatar="🧑‍🎓"):
                with st.spinner("Preparando evaluación..."):
                    try:
                        # Adaptación estricta al nuevo formato de historial y roles
                        formatted_history = [
                            types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])])
                            for m in st.session_state.messages[:-1]
                        ]
                        
                        chat = client.chats.create(
                            model="gemini-2.5-flash",
                            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                            history=formatted_history
                        )
                        response = chat.send_message(prompt_rapido)
                        
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                        st.rerun() 
                    except Exception as e:
                        print(f"ERROR TÉCNICO DE API: {e}") 
                        st.error("⚠️ El servidor está un poco saturado. Por favor, espera unos segundos y vuelve a pulsar el botón.")
                        st.session_state.messages.pop() 

# 4. ENTRADA PRINCIPAL DE CHAT
if prompt := st.chat_input("Escribe tu explicación aquí..."):
    # Al escribir, la interfaz se limpia automáticamente de los botones iniciales
    st.session_state.messages.append({"role": "user", "content": prompt, "show": True})
    with st.chat_message("user", avatar="🧑‍🏫"):
        st.markdown(prompt)

    with st.chat_message("model", avatar="🧑‍🎓"):
        with st.spinner("Pensando..."):
            try:
                # Adaptación estricta al nuevo formato de historial y roles
                formatted_history = [
                    types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])])
                    for m in st.session_state.messages[:-1]
                ]
                
                chat = client.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                    history=formatted_history
                )
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text, "show": True})
                st.rerun() 
            except Exception as e:
                print(f"ERROR TÉCNICO DE API: {e}") 
                st.error("⚠️ Ha habido un microcorte de conexión con el servidor. Por favor, vuelve a enviar tu explicación.")
                st.session_state.messages.pop()
