"""
Three-agent logic for AI Case Review Method + a gatekeeper Evaluator.
Calls the Anthropic API (Claude) with specialized prompts.
The output language is dynamic: it depends on what the student selects in the GUI.
"""
import json
import os
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
# Language instruction (dynamic)
# ---------------------------------------------------------------------------
def _instruccion_idioma(idioma: str) -> str:
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


# ===========================================================================
# AGENT 0 — EVALUATOR (gatekeeper)
# ===========================================================================
# Returns a structured JSON: scores 0-2 on 5 criteria, plus a natural-language
# message in the chosen language with which criteria failed.

CRITERIOS = ["context", "evidencia", "kpis", "realismo", "horizonte_temporal"]

CRITERIOS_LABEL = {
    "English": {
        "context": "Context (market, competition, regulation, trends)",
        "evidencia": "Evidence (data, facts or fragments from the case/notes)",
        "kpis": "KPIs (sales, margin, market share, retention, efficiency…)",
        "realismo": "Realism (resources, time, capabilities, constraints)",
        "horizonte_temporal": "Time horizon (short / medium / long term)",
    },
    "Castellano": {
        "context": "Contexto (mercado, competencia, regulación, tendencias)",
        "evidencia": "Evidencia (datos, hechos o fragmentos del caso/apuntes)",
        "kpis": "KPIs (ventas, margen, cuota, retención, eficiencia…)",
        "realismo": "Realismo (recursos, tiempo, capacidades, restricciones)",
        "horizonte_temporal": "Horizonte temporal (corto / medio / largo plazo)",
    },
    "Català": {
        "context": "Context (mercat, competència, regulació, tendències)",
        "evidencia": "Evidència (dades, fets o fragments del cas/apunts)",
        "kpis": "KPIs (vendes, marge, quota, retenció, eficiència…)",
        "realismo": "Realisme (recursos, temps, capacitats, restriccions)",
        "horizonte_temporal": "Horitzó temporal (curt / mitjà / llarg termini)",
    },
}


def prompt_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

STUDENT DATA
============
- Question: {pregunta}
- Initial answer to evaluate: {respuesta_ini}

ROLE INSTRUCTIONS
=================
You are a strict pedagogical gatekeeper. Your only job is to decide whether the student's INITIAL answer meets the MINIMUM requirements to be evaluable. You do NOT correct the answer; you only check whether it has enough substance to be analyzed by the next agents.

Score each of these 5 criteria with EXACTLY one integer: 0, 1 or 2.
- 0 = absent (the criterion is not present at all)
- 1 = partial (the criterion is touched on but superficially or incompletely)
- 2 = present (the criterion is clearly and substantively addressed)

CRITERIA
========
1. context: The answer relates to the business environment (market, competition, economic situation, regulation or trends).
2. evidencia: The answer uses data, facts, figures or fragments from the case and/or the professor's notes to justify the recommendation.
3. kpis: The answer includes success indicators (sales, margin, customer satisfaction, market share, retention, efficiency, etc.).
4. realismo: The recommendation is realistic regarding the firm's resources, time, capabilities and constraints.
5. horizonte_temporal: The answer differentiates short-, medium- and long-term impacts of the proposed decision.

ANTI-CHEATING RULES
===================
- If the answer is empty, gibberish, off-topic, or just a copy/paste of the case, score everything 0.
- If the answer is extremely vague ("I think it's a good idea") with no specifics, max 1 in any criterion.
- The criteria are independent: an answer can score high in one and 0 in another.

OUTPUT FORMAT — STRICT JSON
===========================
You MUST return ONLY a valid JSON object, with NO surrounding text, NO markdown fences, NO explanation outside the JSON. The JSON must follow EXACTLY this schema:

{{
  "scores": {{
    "context": 0,
    "evidencia": 0,
    "kpis": 0,
    "realismo": 0,
    "horizonte_temporal": 0
  }},
  "total": 0,
  "passed": false,
  "failed_criteria": ["context", "kpis"],
  "message": "<natural-language message addressed to the student, in the language indicated below>"
}}

Where:
- "total" = sum of the 5 scores (0-10).
- "passed" = true if total >= 6, else false.
- "failed_criteria" = array with the keys of every criterion that scored 0 or 1 (only fill it when "passed" is false; when "passed" is true, return an empty array []).
- "message" = a short, encouraging but firm message (3-6 lines) in the chosen language, telling the student what is missing or weak. If passed=true, write a short congratulatory message and announce the next step. Do NOT reveal the numeric scores in this message.

{_instruccion_idioma(idioma)}
"""


# ---------------------------------------------------------------------------
# Prompts of the 3 main agents
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
- STRICT LIMIT: maximum 500 words.

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
- STRICT LIMIT: maximum 500 words.

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


def _extraer_json(raw: str) -> dict:
    """Robust JSON extraction. Accepts JSON with or without ```json fences."""
    raw = raw.strip()
    # Strip code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Fallback: extract the largest {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Could not parse evaluator JSON response.")


def ejecutar_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> dict:
    """Runs the gatekeeper agent. Returns a dict with keys:
       scores (dict), total (int), passed (bool), failed_criteria (list[str]), message (str)."""
    raw = _llamar(
        prompt_avaluador(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma),
        max_tokens=900,
    )
    data = _extraer_json(raw)

    # Sanity defaults if the model omits something
    scores = data.get("scores", {})
    safe_scores = {c: int(scores.get(c, 0)) for c in CRITERIOS}
    total = data.get("total")
    if not isinstance(total, int):
        total = sum(safe_scores.values())
    passed = bool(data.get("passed", total >= 6))
    failed_criteria = data.get("failed_criteria", [])
    if not isinstance(failed_criteria, list):
        failed_criteria = []
    # If passed, force empty failed_criteria
    if passed:
        failed_criteria = []
    message = str(data.get("message", "")).strip()

    return {
        "scores": safe_scores,
        "total": total,
        "passed": passed,
        "failed_criteria": failed_criteria,
        "message": message,
    }


def ejecutar_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


def ejecutar_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma="English") -> str:
    return _llamar(prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini, idioma))


def ejecutar_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma="English") -> str:
    return _llamar(
        prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final, idioma),
        max_tokens=3500,
    )
