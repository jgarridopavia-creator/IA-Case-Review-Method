"""
AI Case Review Method
Aplicación Streamlit con tres agentes (Crítico / Optimista / Asertivo).
GUI ÍNTEGRAMENTE EN CASTELLANO.

Ejecutar localmente:
    streamlit run app.py
"""
import streamlit as st
from dotenv import load_dotenv

from utils import (
    extraer_texto_pdf,
    extraer_texto_pdfs,
    contar_palabras,
    construir_docx,
)
from agents import (
    ejecutar_critico,
    ejecutar_optimista,
    ejecutar_asertivo,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Case Review Method",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
DEFAULTS = {
    "fase": 1,
    "texto_caso": "",
    "texto_apuntes": "",
    "nombre_caso": "",
    "pregunta": "",
    "respuesta_inicial": "",
    "respuesta_critico": "",
    "respuesta_optimista": "",
    "respuesta_final": "",
    "respuesta_asertivo": "",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset_app():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
col_t1, col_t2 = st.columns([5, 1])
with col_t1:
    st.markdown("## AI Case Review Method")
    st.caption(
        "Sube el caso práctico y los apuntes correspondientes del profesor. Plantea preguntas sobre el caso, introduce tus respuestas iniciales y recibe un feedback crítico y un feedback optimista."
        "Una vez analizado todo, introduce tu respuesta final y obtén la "
        "corrección definitiva."
    )
with col_t2:
    if st.button("🔄 Reiniciar", use_container_width=True):
        reset_app()
        st.rerun()

st.divider()

# ===========================================================================
# FASE 1 — Entrada del alumno
# ===========================================================================
if st.session_state.fase >= 1:
    st.markdown("### 1️⃣ Sube el caso práctico y los apuntes relacionados del profesor")

    col1, col2 = st.columns(2)
    with col1:
        caso_pdf = st.file_uploader(
            "📄 **Arrastra el caso práctico en PDF (obligatorio)** — admite varios archivos",
            type=["pdf"],
            accept_multiple_files=True,
            key="upl_caso",
        )
    with col2:
        apuntes_pdf = st.file_uploader(
            "📚 **Arrastra los apuntes del profesor en PDF (opcional)** — admite varios archivos",
            type=["pdf"],
            accept_multiple_files=True,
            key="upl_apuntes",
        )

    st.markdown("### 2️⃣ Plantea una pregunta o cuestión sobre el caso")
    pregunta = st.text_area(
        "Sin límite de palabras",
        value=st.session_state.pregunta,
        height=110,
        key="in_pregunta",
        placeholder="Ej.: ¿Cuál sería la mejor estrategia de internacionalización para esta empresa?",
    )

    st.markdown("### 3️⃣ Escribe tu respuesta inicial")
    respuesta_ini = st.text_area(
        "Sin límite de palabras",
        value=st.session_state.respuesta_inicial,
        height=220,
        key="in_resp_ini",
        placeholder="Desarrolla aquí tu respuesta con la máxima profundidad",
    )
    st.caption(f"Palabras: {contar_palabras(respuesta_ini)}")

    st.markdown("")
    procesar = st.button(
        "▶️ Procesar (lanzar feedback crítico y feedback optimista)",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.fase >= 2),
    )

    if procesar:
        if not caso_pdf:
            st.error("Debes subir el caso práctico en PDF.")
            st.stop()
        if not pregunta.strip():
            st.error("Debes escribir una pregunta.")
            st.stop()
        if not respuesta_ini.strip():
            st.error("Debes escribir tu respuesta inicial.")
            st.stop()

        with st.spinner("Extrayendo texto del caso y los apuntes…"):
            st.session_state.nombre_caso = ", ".join([f.name for f in caso_pdf])
            st.session_state.texto_caso = extraer_texto_pdfs(caso_pdf)
            st.session_state.texto_apuntes = extraer_texto_pdfs(apuntes_pdf or [])
            st.session_state.pregunta = pregunta
            st.session_state.respuesta_inicial = respuesta_ini

        try:
            with st.spinner("🗡️ El Agente Crítico está analizando…"):
                st.session_state.respuesta_critico = ejecutar_critico(
                    st.session_state.texto_caso,
                    st.session_state.texto_apuntes,
                    st.session_state.pregunta,
                    st.session_state.respuesta_inicial,
                )
            with st.spinner("🌟 El Agente Optimista está analizando…"):
                st.session_state.respuesta_optimista = ejecutar_optimista(
                    st.session_state.texto_caso,
                    st.session_state.texto_apuntes,
                    st.session_state.pregunta,
                    st.session_state.respuesta_inicial,
                )
            st.session_state.fase = 2
            st.rerun()
        except Exception as e:
            st.error(f"Error al llamar a los agentes: {e}")

# ===========================================================================
# FASE 2 — Debate de los agentes
# ===========================================================================
if st.session_state.fase >= 2:
    st.divider()
    st.markdown("### 4️⃣ Debate de los agentes")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### 🗡️ Agente Crítico")
        st.text_area(
            "Feedback contrario a tu respuesta inicial:",
            value=st.session_state.respuesta_critico,
            height=420,
            key="out_critico",
        )
    with colB:
        st.markdown("#### 🌟 Agente Optimista")
        st.text_area(
            "Feedback a favor de tu respuesta inicial:",
            value=st.session_state.respuesta_optimista,
            height=420,
            key="out_optimista",
        )

    st.markdown("### 5️⃣ Tu respuesta final")
    respuesta_final = st.text_area(
        "Después de analizar los feedbacks, escribe ahora tu respuesta definitiva (máx. 700 palabras):",
        value=st.session_state.respuesta_final,
        height=260,
        key="in_resp_final",
        placeholder="Refina tu respuesta integrando los argumentos que consideres válidos",
    )
    palabras_final = contar_palabras(respuesta_final)
    if palabras_final > 700:
        st.warning(f"⚠️ Llevas {palabras_final} palabras. El límite son 700.")
    else:
        st.caption(f"Palabras: {palabras_final} / 700")

    procesar_final = st.button(
        "▶️ Solicitar corrección del Agente Asertivo",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.fase >= 3),
    )

    if procesar_final:
        if not respuesta_final.strip():
            st.error("Debes escribir tu respuesta final.")
            st.stop()
        if palabras_final > 700:
            st.error("Tu respuesta final supera las 700 palabras. Recórtala antes de continuar.")
            st.stop()

        st.session_state.respuesta_final = respuesta_final

        try:
            with st.spinner("⚖️ El Agente Asertivo está corrigiendo…"):
                st.session_state.respuesta_asertivo = ejecutar_asertivo(
                    st.session_state.texto_caso,
                    st.session_state.texto_apuntes,
                    st.session_state.pregunta,
                    st.session_state.respuesta_final,
                )
            st.session_state.fase = 3
            st.rerun()
        except Exception as e:
            st.error(f"Error al llamar al agente asertivo: {e}")

# ===========================================================================
# FASE 3 — Corrección final + exportación
# ===========================================================================
if st.session_state.fase >= 3:
    st.divider()
    st.markdown("### 6️⃣ Corrección del Agente Asertivo")
    st.text_area(
        "Feedback, respuesta correcta de referencia y diferencias:",
        value=st.session_state.respuesta_asertivo,
        height=520,
        key="out_asertivo",
    )

    st.divider()
    st.markdown("### 7️⃣ Exportar la sesión completa")

    docx_buffer = construir_docx(
        nombre_caso=st.session_state.nombre_caso,
        pregunta=st.session_state.pregunta,
        respuesta_inicial=st.session_state.respuesta_inicial,
        respuesta_critico=st.session_state.respuesta_critico,
        respuesta_optimista=st.session_state.respuesta_optimista,
        respuesta_final=st.session_state.respuesta_final,
        respuesta_asertivo=st.session_state.respuesta_asertivo,
    )

    nombre_descarga = (
        st.session_state.nombre_caso.split(",")[0].replace(".pdf", "").strip()
        if st.session_state.nombre_caso else "agora"
    )
    st.download_button(
        label="📥 Descargar análisis en Word (.docx)",
        data=docx_buffer,
        file_name=f"agora_{nombre_descarga}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Pie
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "AI Case Review Method · Prof. Dr. Jordi Garrido · La Salle Campus Barcelona-URL · "
    "Powered by Claude (Anthropic)"
)
