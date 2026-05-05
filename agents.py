"""
Three-agent logic for AI Case Review Method.
Calls the Anthropic API (Claude) with specialized prompts.
The output language is dynamic: it depends on what the student selects in the GUI.
"""
import os
from anthropic import Anthropic

MODELO = "claude-sonnet-4-5"

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is missing. Configure it in the .env file "
                "or in Streamlit Cloud Secrets."
            )
        _client = Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Language instruction (dynamic)
# ---------------------------------------------------------------------------
def _instruccion_idioma(idioma: str) -> str:
    """Returns a strict output-language instruction for the chosen language."""
    mapa = {
        "English": (
            "MANDATORY OUTPUT LANGUAGE: You MUST write your entire answer in ENGLISH, "
            "regardless of the language of the case or the professor's notes. "
            "All headings, connectors and arguments must be in English. Do NOT mix languages."
        ),
        "Castellano": (
            "IDIOMA DE SALIDA OBLIGATORIO: Debes responder ÍNTEGRAMENTE EN CASTELLANO "
            "(español de España), incluso si el caso o los apuntes del profesor están "
            "escritos en otro idioma. Todos los títulos, epígrafes, conectores y argumentos "
            "deben estar en castellano. No mezcles idiomas."
        ),
        "Català": (
            "IDIOMA DE SORTIDA OBLIGATORI: Has de respondre ÍNTEGRAMENT EN CATALÀ, "
            "encara que el cas pràctic o els apunts del professor estiguin escrits en "
            "un altre idioma. Tots els títols, epígrafs, connectors i arguments han "
            "de ser en català. No barregis idiomes."
        ),
    }
    return mapa.get(idioma, mapa["English"])


def _bloque_contexto(texto_caso: str, texto_apuntes: str) -> str:
    apuntes = texto_apuntes.strip() if texto_apuntes else "(The student has not provided professor's notes.)"
    return f"""REFERENCE CONTEXT
=================
[BUSINESS CASE]
{texto_caso}

[PROFESSOR'S NOTES]
{apuntes}
"""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

STUDENT DATA
============
- Question: {pregunta}
- Answer to evaluate: {respuesta_ini}

ROLE INSTRUCTIONS
=================
You are an expert management consultant and very critical. Your mission is to demonstrate, with solid arguments, that the student's answer is incorrect.

Follow this order strictly:
1. Look for operational, tactical, strategic flaws and contradictions with respect to the content of the business case itself.
2. Look for operational, tactical, strategic flaws and contradictions with respect to the professor's notes (if provided).
3. Look for operational, tactical, strategic flaws and contradictions based on your advanced management knowledge and best industry practices (Porter, Mintzberg, Kotler, Prahalad, Kim & Mauborgne, McKinsey, BCG, HBR…).

STYLE GUIDELINES
================
- Reason your opinions professionally.
- Be critical but professional.
- Do not be generic: literally cite which parts of the student's answer are wrong and why.
- Structure your output with clear headings.
- STRICT LIMIT: maximum 700 words.

{_instruccion_idioma(idioma)}
"""


def prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

STUDENT DATA
============
- Question: {pregunta}
- Answer to evaluate: {respuesta_ini}

ROLE INSTRUCTIONS
=================
You are an expert management consultant and very optimistic. Your mission is to demonstrate, with solid arguments, that the student's answer is correct.

Follow this order strictly:
1. Look for operational, tactical, strategic reasons and data with respect to the content of the business case itself.
2. Look for operational, tactical, strategic reasons and data with respect to the professor's notes (if provided).
3. Look for operational, tactical, strategic reasons and data based on your advanced management knowledge and best industry practices (Porter, Mintzberg, Kotler, Prahalad, Kim & Mauborgne, McKinsey, BCG, HBR…).

STYLE GUIDELINES
================
- Reason your opinions professionally.
- Be optimistic but professional.
- Do not be generic: literally cite which parts of the student's answer are good and why.
- Structure your output with clear headings.
- STRICT LIMIT: maximum 700 words.

{_instruccion_idioma(idioma)}
"""


def prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

STUDENT DATA
============
- Question: {pregunta}
- Student's final answer: {respuesta_final}

ROLE INSTRUCTIONS
=================
You are an expert management consultant and very assertive. Your mission is to correct the student's final answer and provide feedback through solid arguments.

Follow this order strictly:
1. Analyze operational, tactical, strategic data with respect to the content of the business case itself.
2. Analyze operational, tactical, strategic data with respect to the professor's notes (if provided).
3. Analyze operational, tactical, strategic data based on your advanced management knowledge and best industry practices.

MANDATORY OUTPUT STRUCTURE
==========================
Return EXACTLY the following sections, with these titles in capital letters (translated to the chosen output language):

1) FEEDBACK ON THE STUDENT'S FINAL ANSWER
   - Specific strengths (with literal quotes).
   - Specific errors (with literal quotes).
   - Justification of each judgment based on case, notes or theory.

2) REFERENCE CORRECT ANSWER
   - Your own reasoned answer to the question, exemplary and complete.

3) DIFFERENCES BETWEEN THE STUDENT'S ANSWER AND THE CORRECT ANSWER
   - Point-by-point comparative list: what is missing, what is unnecessary, what is misinterpreted.

4) SUGGESTED MARK (over 10) AND BRIEF JUSTIFICATION.

STYLE GUIDELINES
================
- Reason professionally and be assertive (firm and respectful, neither complacent nor destructive).
- Do not be generic: literally cite the parts you comment on.

{_instruccion_idioma(idioma)}
"""


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

def _llamar(prompt: str, max_tokens: int = 2500) -> str:
    client = _get_client()
    msg = client.messages.create(
        model=MODELO,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    partes = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(partes).strip()


def ejecutar_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


def ejecutar_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


def ejecutar_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma="English") -> str:
    return _llamar(
        prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma),
        max_tokens=3500,
    )
