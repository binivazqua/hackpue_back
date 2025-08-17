import google.generativeai as genai
import json


GEMINI_PROMPT_TO_JSON = """
Eres un curador de seguridad digital para familias. ¡Lees un artículo sobre seguridad digital con los datos proporcionados, entre ellos el link completo, el cual puedes consultar!
Primero, deberás traducir el artículo al español. Después de leerlo de manera atenta, pero no muy profunda, por favor:
Devuelve SOLO JSON válido con este shape:
{
  "digest_es": string,              // resumen claro y no alarmista para padres (3-5 líneas)
  "kickstarters_es": [string,...],  // 3-5 preguntas breves para adolescentes
  "activity_es": {                  // mini actividad lúdica para niños 7-11
    "titulo": string,
    "pasos": [string,...]
  },
  "risk_level": "bajo"|"medio"|"alto"
}
Criterios:
- Si el artículo parece fraude/estafa → "phishing" ↔ tendencia a "medio/alto" según urgencia y alcance.
- Lenguaje empático, no técnico.
- No inventes datos: si faltan detalles, di "según la nota".

"""


# gemini digest method -> le provee a front las recs basadas en los métodos de run en app.py

async def gemini_process_articles(item: dict, model_name: str) -> dict:
    """ 
     item: app.py /queue
     model_name: desired model
     output: dict compatible con ItemOut model in models.py
    """

    # we get the ingredients for gemini cook
    title = item.get("title", "")
    url = item.get("url", "")
    source = item.get("source", "")
    summary = item.get("summary", "")
    category = item.get("category", "")
    published = item.get("published", "")

    content = f"""
        Title: {title}
        URL: {url}
        Source: {source}
        Summary: {summary}
        Category: {category}
        Published: {published}
    """

    model = genai.GeminiModel(model_name, temperature=0.5, max_output_tokens=256)

    # keep it simple
    response = await model.generate_content(content)

    try:
        output = json.loads(response.text)
        output["digest_es"] = (output.get("digest_es", "")).strip()
        output["kickstarter_es"] = (output.get("kickstarter_es")).strip()
        output["activity_es"] = (output.get("activity_es")).strip()

        # asignar un risk level
        if output["risk_level"] not in ("bajo", "medio", "alto"):
            output["risk_level"] = "medio"
        
        return output
    except Exception: 
        #fallback si no es un JSON DIGNO (lol)
        return {
            "digest_es": f"Resumen: {title}. (Ver fuente: {url})",
            "kickstarters_es": ["¿Qué señales te harían dudar?", "¿Con quién pedirías ayuda?"],
            "activity_es": {"titulo":"Detectives anti-phishing","pasos":["Ver remitente","Revisar enlace","No compartir claves"]},
            "risk_level":"medio"
        }

        








