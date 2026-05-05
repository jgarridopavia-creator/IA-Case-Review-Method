"""
Lógica de los tres agentes del Ágora.
Llama a la API de Anthropic (Claude) con prompts especializados.
TODOS los agentes responden SIEMPRE en castellano.
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
                "Falta ANTHROPIC_API_KEY. Configúrala en el archivo .env "
                "o en los Secrets de Streamlit Cloud."
            )
        _client = Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# IDIOMA OBLIGATORIO
# ---------------------------------------------------------------------------
INSTRUCCION_IDIOMA = (
    "IDIOMA DE SALIDA OBLIGATORIO: Debes responder ÍNTEGRAMENTE EN CASTELLANO "
    "(español de España), incluso si el caso práctico o los apuntes del "
    "profesor están escritos en catalán, inglés o cualquier otro idioma. "
    "Todos los títulos, epígrafes, conectores y argumentos deben estar en "
    "castellano. No mezcles idiomas."
)


def _bloque_contexto(texto_caso: str, texto_apuntes: str) -> str:
    apuntes = texto_apuntes.strip() if texto_apuntes else "(El alumno no ha aportado apuntes del profesor.)"
    return f"""CONTEXTO DE REFERENCIA
======================
[CASO PRÁCTICO]
{texto_caso}

[APUNTES DEL PROFESOR]
{apuntes}
"""


def prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

DATOS DEL ALUMNO
================
- Pregunta: {pregunta}
- Respuesta a evaluar: {respuesta_ini}

INSTRUCCIONES DE ROL
====================
Eres un consultor experto en management y muy crítico. Tu misión es demostrar que la respuesta del alumno es incorrecta a través de argumentos sólidos.

Sigue este orden estrictamente:
1. Busca fallos operativos, tácticos, estratégicos y contradicciones con respecto al contenido del propio caso práctico.
2. Busca fallos operativos, tácticos, estratégicos y contradicciones con respecto a los apuntes del profesor (si se han proporcionado).
3. Busca fallos operativos, tácticos, estratégicos y contradicciones basándote en tu conocimiento avanzado de management y mejores prácticas del sector (Porter, Mintzberg, Kotler, Prahalad, Kim & Mauborgne, McKinsey, BCG, HBR…).

PAUTAS DE ESTILO
================
- Razona profesionalmente tus opiniones.
- Sé crítico pero profesional.
- No seas genérico: cita literalmente qué partes de la respuesta del alumno están mal y por qué.
- Estructura tu salida con epígrafes claros.
- LÍMITE ESTRICTO: máximo 700 palabras.

{INSTRUCCION_IDIOMA}
"""


def prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

DATOS DEL ALUMNO
================
- Pregunta: {pregunta}
- Respuesta a evaluar: {respuesta_ini}

INSTRUCCIONES DE ROL
====================
Eres un consultor experto en management y muy optimista. Tu misión es demostrar que la respuesta del alumno es correcta a través de argumentos sólidos.

Sigue este orden estrictamente:
1. Busca razones operativas, tácticas, estratégicas y datos con respecto al contenido del propio caso práctico.
2. Busca razones operativas, tácticas, estratégicas y datos con respecto a los apuntes del profesor (si se han proporcionado).
3. Busca razones operativas, tácticas, estratégicas y datos basándote en tu conocimiento avanzado de management y mejores prácticas del sector (Porter, Mintzberg, Kotler, Prahalad, Kim & Mauborgne, McKinsey, BCG, HBR…).

PAUTAS DE ESTILO
================
- Razona profesionalmente tus opiniones.
- Sé optimista pero profesional.
- No seas genérico: cita literalmente qué partes de la respuesta del alumno están bien y por qué.
- Estructura tu salida con epígrafes claros.
- LÍMITE ESTRICTO: máximo 700 palabras.

{INSTRUCCION_IDIOMA}
"""


def prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final) -> str:
    return f"""{_bloque_contexto(texto_caso, texto_apuntes)}

DATOS DEL ALUMNO
================
- Pregunta: {pregunta}
- Respuesta final del alumno: {respuesta_final}

INSTRUCCIONES DE ROL
====================
Eres un consultor experto en management y muy asertivo. Tu misión es corregir la respuesta final del alumno y darle feedback a través de argumentos sólidos.

Sigue este orden estrictamente:
1. Analiza datos operativos, tácticos, estratégicos con respecto al contenido del propio caso práctico.
2. Analiza datos operativos, tácticos, estratégicos con respecto a los apuntes del profesor (si se han proporcionado).
3. Analiza datos operativos, tácticos, estratégicos basándote en tu conocimiento avanzado de management y mejores prácticas del sector.

ESTRUCTURA OBLIGATORIA DE LA SALIDA
====================================
Devuelve EXACTAMENTE las siguientes secciones, con estos títulos en mayúsculas:

1) FEEDBACK SOBRE LA RESPUESTA FINAL DEL ALUMNO
   - Aciertos concretos (con citas literales).
   - Errores concretos (con citas literales).
   - Justificación de cada juicio basada en caso, apuntes o teoría.

2) RESPUESTA CORRECTA DE REFERENCIA
   - Tu propia respuesta razonada a la pregunta planteada, ejemplar y completa.

3) DIFERENCIAS ENTRE LA RESPUESTA DEL ALUMNO Y LA RESPUESTA CORRECTA
   - Lista comparativa punto por punto: qué le falta, qué le sobra, qué interpreta mal.

4) NOTA SUGERIDA (sobre 10) Y JUSTIFICACIÓN BREVE.

PAUTAS DE ESTILO
================
- Razona profesionalmente y sé asertivo (firme y respetuoso, ni complaciente ni destructivo).
- No seas genérico: cita literalmente las partes que comentas.

{INSTRUCCION_IDIOMA}
"""


# ---------------------------------------------------------------------------
# LLAMADAS AL MODELO
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


def ejecutar_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini) -> str:
    return _llamar(prompt_critico(texto_caso, texto_apuntes, pregunta, respuesta_ini))


def ejecutar_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini) -> str:
    return _llamar(prompt_optimista(texto_caso, texto_apuntes, pregunta, respuesta_ini))


def ejecutar_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final) -> str:
    return _llamar(
        prompt_asertivo(texto_caso, texto_apuntes, pregunta, respuesta_final),
        max_tokens=3500,
    )
