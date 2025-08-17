import google.generativeai as genai
import json
import os


# Configure API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


GEMINI_PROMPT_TO_JSON = """
Eres un curador de seguridad digital para familias. Lee los datos de un artículo de seguridad digital (incluyen link y summary). 
Tu tarea: generar SOLO un JSON válido (sin explicaciones, sin texto extra) con este shape EXACTO:

{
  "digest_es": string,              
  "kickstarter_es": [string,...],   
  "activity_es": {                  
    "titulo": string,
    "pasos": [string,...]
  },
  "risk_level": "bajo"|"medio"|"alto"
}

Instrucciones:
- "digest_es": traducción al español del campo "Summary".
- "kickstarter_es": 3–5 preguntas breves para adolescentes.
- "activity_es": una mini actividad creativa para familia (titulo + 2–4 pasos) EN ESPAÑOL!!!
- "risk_level": evalúa el nivel de riesgo del artículo (fraude/estafa → "medio" o "alto").
- Lenguaje empático, no técnico.
- No inventes datos: si faltan, usa "según la nota".
- TODO debe estar en ESPAÑOL.
- Devuelve SOLO JSON. No agregues prosa, comentarios, markdown ni texto antes o después.

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
{GEMINI_PROMPT_TO_JSON}

Artículo a procesar:
Title: {title}
URL: {url}
Source: {source}
Summary: {summary}
Category: {category}
Published: {published}
    """

    model = genai.GenerativeModel(model_name=model_name, generation_config=genai.GenerationConfig(
        temperature=0.7,
        max_output_tokens=1000,  # Increased for complex JSON
        top_p=0.95,
        top_k=40
    ))
    # keep it simple
    response = model.generate_content(content)

    try:
        # Clean response text (remove markdown if present)
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        output = json.loads(response_text)
        
        # Clean strings properly
        if "digest_es" in output:
            output["digest_es"] = str(output["digest_es"]).strip()
        if "kickstarter_es" in output and isinstance(output["kickstarter_es"], list):
            output["kickstarter_es"] = [str(item).strip() for item in output["kickstarter_es"]]
        if "activity_es" in output and isinstance(output["activity_es"], dict):
            # Don't strip dict, just validate it has the right structure
            if "titulo" not in output["activity_es"] or "pasos" not in output["activity_es"]:
                raise ValueError("Invalid activity_es structure")

        # Validate risk level
        if output.get("risk_level") not in ("bajo", "medio", "alto"):
            output["risk_level"] = "medio"
        
        return output
    except Exception as e: 
        print(f"Error processing Gemini response: {e}")
        print(f"Raw response: {response.text}")
        #fallback si no es un JSON DIGNO (lol)
        return {
            "digest_es": f"Resumen: {title}. (Ver fuente: {url})",
            "kickstarter_es": ["¿Qué señales te harían dudar?", "¿Con quién pedirías ayuda?"],
            "activity_es": {"titulo":"Detectives anti-phishing","pasos":["Ver remitente","Revisar enlace","No compartir claves"]},
            "risk_level":"medio"
        }

        








