"""
Four-agent logic for AI Case Review Method.
- Evaluator (gatekeeper): scores the student's initial answer against 3 criteria.
- Critic / Optimist / Assertive: same as before.

The output language is dynamic: it depends on the GUI selector.
"""
import os
import json
import re
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
# Language instruction
# ---------------------------------------------------------------------------
def _instruccion_idioma(idioma: str) -> str:
    mapa = {
        "English": (
            "MANDATORY OUTPUT LANGUAGE: Write your entire answer in ENGLISH, "
            "regardless of the language of the case or the notes. All headings "
            "and arguments must be in English. Do NOT mix languages."
        ),
        "Castellano": (
            "IDIOMA DE SALIDA OBLIGATORIO: Debes responder ÍNTEGRAMENTE EN CASTELLANO, "
            "incluso si el caso o los apuntes están escritos en otro idioma. "
            "Todos los títulos y argumentos deben estar en castellano."
        ),
        "Català": (
            "IDIOMA DE SORTIDA OBLIGATORI: Has de respondre ÍNTEGRAMENT EN CATALÀ, "
            "encara que el cas o els apunts estiguin escrits en un altre idioma. "
            "Tots els títols i arguments han de ser en català."
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


# ===========================================================================
# AGENT 0: EVALUATOR (gatekeeper)
# ===========================================================================

# 3 criteria, 0-1 each, threshold 2/3
CRITERIOS = [
    ("exogenas",  "Exogenous variables"),
    ("evidencia", "Evidence"),
    ("realismo",  "Realism"),
]

# Localized labels for the table shown to the student
ETIQUETAS_CRITERIOS = {
    "English": {
        "exogenas":  "Exogenous variables (market, competition, suppliers, trends, PESTEL...)",
        "evidencia": "Evidence (data, facts, fragments from the case/notes)",
        "realismo":  "Realism (no constructs contrary to business logic or management)",
    },
    "Castellano": {
        "exogenas":  "Variables exógenas (mercado, competencia, proveedores, tendencias, PESTEL...)",
        "evidencia": "Evidencia (datos, hechos, fragmentos del caso/apuntes)",
        "realismo":  "Realismo (sin constructos contrarios a la lógica empresarial o de management)",
    },
    "Català": {
        "exogenas":  "Variables exògenes (mercat, competència, proveïdors, tendències, PESTEL...)",
        "evidencia": "Evidència (dades, fets, fragments del cas/apunts)",
        "realismo":  "Realisme (sense constructes contraris a la lògica empresarial o de management)",
    },
}

# Fixed English message shown when the answer does not pass
MENSAJE_BLOQUEO_EN = "The answer is not yet assessable. Reformulate before continuing."


def prompt_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

STUDENT DATA
============
- Question: {pregunta}
- Initial answer to evaluate: {respuesta_ini}

ROLE INSTRUCTIONS
=================
You are a strict but fair MBA case-method evaluator. Your ONLY mission is to decide whether the student's initial answer meets the minimum quality required to deserve full critical/optimistic feedback.

Score the answer on 3 criteria. For each criterion, give an integer score:
  - 0 = absent (the answer does NOT address this criterion)
  - 1 = present (the answer addresses it clearly)

The 3 criteria are:
1. EXOGENOUS VARIABLES — The answer relates to exogenous information: market, competition, suppliers, trends, PESTEL framework, etc.
2. EVIDENCE — The answer is based on data, facts or fragments from the case and/or the professor's notes.
3. REALISM — The answer is realistic. It is NOT a construct contrary to all business or management logic.

ANTI-CHEAT RULES (apply strictly)
=================================
- If the answer is empty, gibberish, or only a few words without meaning: 0 in ALL criteria (total = 0/3).
- If the answer is the literal copy of fragments of the case practically verbatim without adding any analysis: 0 in ALL criteria (total = 0/3).
- If the answer is a generic management essay completely unrelated to the specific case: 0 in EXOGENOUS VARIABLES and 0 in EVIDENCE.

OUTPUT FORMAT (STRICT JSON, NOTHING ELSE)
=========================================
Return ONLY a JSON object with this exact structure (no markdown, no code fences, no explanations outside the JSON):

{{
  "scores": {{
    "exogenas":  <0|1>,
    "evidencia": <0|1>,
    "realismo":  <0|1>
  }},
  "total": <integer 0-3>,
  "passes": <true|false>,
  "feedback_per_criterion": {{
    "exogenas":  "<one short sentence explaining why this score>",
    "evidencia": "<one short sentence explaining why this score>",
    "realismo":  "<one short sentence explaining why this score>"
  }},
  "global_message": "<2-3 sentences. If passes=false: tell the student concretely what to add/improve to reach >=2/3. If passes=true: briefly highlight the strongest criterion>"
}}

Rules:
- "passes" MUST be true if total >= 2, false otherwise.
- "total" MUST equal the sum of the 3 scores.
- The strings inside "feedback_per_criterion" and "global_message" MUST be written in this language: {idioma}.
- The JSON keys (exogenas, evidencia, realismo, etc.) and structure MUST stay as-is in English.
"""


def _extraer_json(texto: str) -> dict:
    """Extracts the first JSON object found in the model's response."""
    try:
        return json.loads(texto)
    except Exception:
        pass
    limpio = re.sub(r"```(?:json)?", "", texto).strip("` \n")
    try:
        return json.loads(limpio)
    except Exception:
        pass
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No se ha podido extraer JSON de la respuesta del evaluador.")


def ejecutar_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> dict:
    """Returns dict with: scores, total, passes, feedback_per_criterion, global_message."""
    client = _get_client()
    prompt = prompt_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma)
    msg = client.messages.create(
        model=MODELO,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    partes = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    texto = "\n".join(partes).strip()
    data = _extraer_json(texto)

    # Defensive normalization (force consistency between scores and total)
    scores = data.get("scores", {})
    total = sum(int(scores.get(k, 0)) for k, _ in CRITERIOS)
    data["total"] = total
    data["passes"] = total >= 2
    return data


# ===========================================================================
# AGENT 1: CRITIC
# ===========================================================================

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
- STRICT LIMIT: maximum 500 words.

{_instruccion_idioma(idioma)}
"""


def ejecutar_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


# ===========================================================================
# AGENT 2: OPTIMIST
# ===========================================================================

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
- STRICT LIMIT: maximum 500 words.

{_instruccion_idioma(idioma)}
"""


def ejecutar_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


# ===========================================================================
# AGENT 3: ASSERTIVE
# ===========================================================================

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


def ejecutar_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma="English") -> str:
    return _llamar(
        prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma),
        max_tokens=3500,
    )


# ===========================================================================
# Shared call helper
# ===========================================================================

def _llamar(prompt: str, max_tokens: int = 2500) -> str:
    client = _get_client()
    msg = client.messages.create(
        model=MODELO,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    partes = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(partes).strip()
