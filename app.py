"""
AI Case Review Method
Streamlit application with four agents:
  0. Evaluator (gatekeeper): scores the initial answer 0-3 (3 criteria, 0-1 each).
     Threshold = 2/3.
  1. Critic
  2. Optimist
  3. Assertive

GUI fixed in English. Agents respond in the language chosen by the user.

Run locally:
    streamlit run app.py
"""
import os
import streamlit as st
from dotenv import load_dotenv

from utils import (
    extraer_texto_pdf,
    extraer_texto_pdfs,
    contar_palabras,
    construir_docx,
)
from agents import (
    ejecutar_avaluador,
    ejecutar_critico,
    ejecutar_optimista,
    ejecutar_asertivo,
    ETIQUETAS_CRITERIOS,
    CRITERIOS,
    MENSAJE_BLOQUEO_EN,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Case Review Method",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
DEFAULTS = {
    "fase": 1,
    "texto_caso": "",
    "texto_apuntes": "",
    "nombre_caso": "",
    "pregunta": "",
    "respuesta_inicial": "",
    "evaluacion": None,            # dict returned by ejecutar_avaluador
    "intentos_evaluador": 0,
    "respuesta_critico": "",
    "respuesta_optimista": "",
    "respuesta_final": "",
    "respuesta_asertivo": "",
    "idioma_agentes": "English",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset_app():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def _buscar_logo() -> str | None:
    base = os.path.dirname(os.path.abspath(__file__))
    for ext in ("png", "jpg", "jpeg", "PNG", "JPG", "JPEG"):
        ruta = os.path.join(base, f"logosalle.{ext}")
        if os.path.exists(ruta):
            return ruta
    return None


# ---------------------------------------------------------------------------
# Header (logo + title + reset)
# ---------------------------------------------------------------------------
col_logo, col_title, col_reset = st.columns([1, 4, 1])

with col_logo:
    logo = _buscar_logo()
    if logo:
        st.image(logo, use_container_width=True)
    else:
        st.markdown(
            "<div style='border:1px dashed #b5b5b5;border-radius:8px;"
            "padding:24px 8px;text-align:center;color:#888;font-size:12px;'>"
            "Upload <b>logosalle.png</b><br/>to project folder"
            "</div>",
            unsafe_allow_html=True,
        )

with col_title:
    st.markdown("## AI Case Review Method")
    st.caption(
        "Tool that strengthens the student's critical thinking when working "
        "on business cases. Three AI consultants debate with the student: one "
        "challenges the answer, another defends it, and a third corrects it "
        "with the reference solution."
    )

with col_reset:
    if st.button("🔄 Reset", use_container_width=True):
        reset_app()
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Language selector (only affects the agents' responses)
# ---------------------------------------------------------------------------
st.markdown("### 🌐 Agents response language")
st.caption(
    "Choose the language in which the agents will write their answers. "
    "The interface will remain in English."
)
st.session_state.idioma_agentes = st.selectbox(
    "Language",
    options=["English", "Castellano", "Català"],
    index=["English", "Castellano", "Català"].index(st.session_state.idioma_agentes),
    key="sel_idioma",
    label_visibility="collapsed",
)

st.divider()

# ===========================================================================
# PHASE 1 — Student input + Evaluator gatekeeper
# ===========================================================================
if st.session_state.fase >= 1:
    st.markdown("### 1️⃣ Upload the business case and related professor's notes")

    col1, col2 = st.columns(2)
    with col1:
        caso_pdf = st.file_uploader(
            "📄 **Drag the business case PDF (mandatory)** — multiple files allowed",
            type=["pdf"],
            accept_multiple_files=True,
            key="upl_caso",
        )
    with col2:
        apuntes_pdf = st.file_uploader(
            "📚 **Drag the professor's notes PDF (optional)** — multiple files allowed",
            type=["pdf"],
            accept_multiple_files=True,
            key="upl_apuntes",
        )

    st.markdown("### 2️⃣ Ask a question about the case")
    pregunta = st.text_area(
        "No word limit",
        value=st.session_state.pregunta,
        height=110,
        key="in_pregunta",
        placeholder="e.g. What would be the best internationalization strategy for this company?",
    )

    st.markdown("### 3️⃣ Write your initial answer")
    respuesta_ini = st.text_area(
        "No word limit",
        value=st.session_state.respuesta_inicial,
        height=220,
        key="in_resp_ini",
        placeholder="Develop your answer here with the maximum depth",
    )
    st.caption(f"Words: {contar_palabras(respuesta_ini)}")

    st.markdown("")
    procesar = st.button(
        "▶️ Evaluate my initial answer",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.fase >= 3),
    )

    if procesar:
        if not caso_pdf:
            st.error("You must upload the business case in PDF.")
            st.stop()
        if not pregunta.strip():
            st.error("You must write a question.")
            st.stop()
        if not respuesta_ini.strip():
            st.error("You must write your initial answer.")
            st.stop()

        with st.spinner("Extracting text from the case and the notes…"):
            st.session_state.nombre_caso = ", ".join([f.name for f in caso_pdf])
            st.session_state.texto_caso = extraer_texto_pdfs(caso_pdf)
            st.session_state.texto_apuntes = extraer_texto_pdfs(apuntes_pdf or [])
            st.session_state.pregunta = pregunta
            st.session_state.respuesta_inicial = respuesta_ini

        idioma = st.session_state.idioma_agentes

        try:
            with st.spinner("📊 The Evaluator is checking minimum quality…"):
                evaluacion = ejecutar_avaluador(
                    st.session_state.texto_caso,
                    st.session_state.texto_apuntes,
                    st.session_state.pregunta,
                    st.session_state.respuesta_inicial,
                    idioma,
                )
            st.session_state.evaluacion = evaluacion
            st.session_state.intentos_evaluador += 1

            if evaluacion.get("passes"):
                st.session_state.fase = 2
                st.rerun()
            else:
                st.session_state.fase = 1
                st.rerun()
        except Exception as e:
            st.error(f"Error calling the evaluator: {e}")

# ---------------------------------------------------------------------------
# Show evaluator result (if any)
# ---------------------------------------------------------------------------
if st.session_state.evaluacion is not None:
    ev = st.session_state.evaluacion
    total = ev.get("total", 0)
    passes = ev.get("passes", False)
    scores = ev.get("scores", {})
    feedback = ev.get("feedback_per_criterion", {})
    mensaje_global = ev.get("global_message", "")

    idioma = st.session_state.idioma_agentes
    etiquetas = ETIQUETAS_CRITERIOS.get(idioma, ETIQUETAS_CRITERIOS["English"])

    st.divider()
    if passes:
        st.success(
            f"✅ **Evaluator score: {total}/3** — Your answer meets the minimum quality "
            f"to proceed (attempt #{st.session_state.intentos_evaluador})."
        )
    else:
        # Fixed English message + indication of which criteria fail
        criterios_fallats = [etiquetas.get(k, k) for k, _ in CRITERIOS if int(scores.get(k, 0)) == 0]
        lista_fallos = ", ".join(criterios_fallats) if criterios_fallats else "—"
        st.error(
            f"❌ **Evaluator score: {total}/3** — {MENSAJE_BLOQUEO_EN} "
            f"(attempt #{st.session_state.intentos_evaluador}). "
            f"Failing criteria: **{lista_fallos}**. "
            f"Review the table below, rewrite your initial answer above and "
            f"click **Evaluate my initial answer** again."
        )

    with st.expander("📋 Detailed evaluation by criterion", expanded=not passes):
        filas = ["| Criterion | Score | Comment |", "|---|---|---|"]
        for clave, _ in CRITERIOS:
            puntos = int(scores.get(clave, 0))
            etiqueta = etiquetas.get(clave, clave)
            comentari = feedback.get(clave, "—").replace("|", "/")
            simbol = "✅" if puntos == 1 else "❌"
            filas.append(f"| {etiqueta} | {simbol} **{puntos}/1** | {comentari} |")
        st.markdown("\n".join(filas))

        if mensaje_global:
            st.markdown(f"**Overall message from the Evaluator:** {mensaje_global}")

# ===========================================================================
# PHASE 2 — Debate (Critic + Optimist)
# ===========================================================================
if st.session_state.fase == 2 and not st.session_state.respuesta_critico:
    idioma = st.session_state.idioma_agentes
    try:
        with st.spinner("🗡️ The Critical Agent is analyzing…"):
            st.session_state.respuesta_critico = ejecutar_critico(
                st.session_state.texto_caso,
                st.session_state.texto_apuntes,
                st.session_state.pregunta,
                st.session_state.respuesta_inicial,
                idioma,
            )
        with st.spinner("🌟 The Optimistic Agent is analyzing…"):
            st.session_state.respuesta_optimista = ejecutar_optimista(
                st.session_state.texto_caso,
                st.session_state.texto_apuntes,
                st.session_state.pregunta,
                st.session_state.respuesta_inicial,
                idioma,
            )
        st.rerun()
    except Exception as e:
        st.error(f"Error calling the agents: {e}")

if st.session_state.fase >= 2 and st.session_state.respuesta_critico:
    st.divider()
    st.markdown("### 4️⃣ Agents' debate")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### 🗡️ Critical Agent")
        st.text_area(
            "Feedback against your initial answer:",
            value=st.session_state.respuesta_critico,
            height=420,
            key="out_critico",
        )
    with colB:
        st.markdown("#### 🌟 Optimistic Agent")
        st.text_area(
            "Feedback in favor of your initial answer:",
            value=st.session_state.respuesta_optimista,
            height=420,
            key="out_optimista",
        )

    st.markdown("### 5️⃣ Your final answer")
    respuesta_final = st.text_area(
        "After analyzing the feedback, write your definitive answer (max. 700 words):",
        value=st.session_state.respuesta_final,
        height=260,
        key="in_resp_final",
        placeholder="Refine your answer integrating the arguments you consider valid",
    )
    palabras_final = contar_palabras(respuesta_final)
    if palabras_final > 700:
        st.warning(f"⚠️ You have written {palabras_final} words. Limit is 700.")
    else:
        st.caption(f"Words: {palabras_final} / 700")

    procesar_final = st.button(
        "▶️ Request the Assertive Agent's correction",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.fase >= 3),
    )

    if procesar_final:
        if not respuesta_final.strip():
            st.error("You must write your final answer.")
            st.stop()
        if palabras_final > 700:
            st.error("Your final answer exceeds 700 words. Trim it before continuing.")
            st.stop()

        st.session_state.respuesta_final = respuesta_final
        idioma = st.session_state.idioma_agentes

        try:
            with st.spinner("⚖️ The Assertive Agent is correcting…"):
                st.session_state.respuesta_asertivo = ejecutar_asertivo(
                    st.session_state.texto_caso,
                    st.session_state.texto_apuntes,
                    st.session_state.pregunta,
                    st.session_state.respuesta_final,
                    idioma,
                )
            st.session_state.fase = 3
            st.rerun()
        except Exception as e:
            st.error(f"Error calling the assertive agent: {e}")

# ===========================================================================
# PHASE 3 — Final correction + export
# ===========================================================================
if st.session_state.fase >= 3:
    st.divider()
    st.markdown("### 6️⃣ Assertive Agent's correction")
    st.text_area(
        "Feedback, reference correct answer and differences:",
        value=st.session_state.respuesta_asertivo,
        height=520,
        key="out_asertivo",
    )

    st.divider()
    st.markdown("### 7️⃣ Export the full session")

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
        if st.session_state.nombre_caso else "case_review"
    )
    st.download_button(
        label="📥 Download analysis as Word (.docx)",
        data=docx_buffer,
        file_name=f"case_review_{nombre_descarga}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "AI Case Review Method · Prof. Dr. Jordi Garrido · La Salle Campus Barcelona-URL · "
    "Powered by Claude (Anthropic)"
)
