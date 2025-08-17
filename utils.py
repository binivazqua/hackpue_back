from pymongo import MongoClient
from bson.objectid import ObjectId
from fastapi import HTTPException
import feedparser

def to_object_id(data: str) -> ObjectId:
    """
    Convert any other type of data (str) to ObjectId for MongoDB PROCESSINNNG
    """
    try:
        return ObjectId(data)
    except Exception: 
        raise HTTPException(status_code=400, detail="Invalid ObjectId")



# parsing RSS 
def parse_rss(name: str, url: str) -> list[dict]:
    """
    Parsea el RSS proveniente de [url], que devuelve un dict crudo para ser procesado en normalizing()
    """
    art = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"}) #provide request headers TO ACCESS AND NOT GET A #403 ERROR

    # checar si hubo error al detectara el xml primero:
    if getattr(art, "bozo", 0):
        # art.bozo_exception contiene el detalle si lo necesitas
        print(f"[WARN] Problema parseando {url}: {getattr(art, 'bozo_exception', '')}")
   
    # print(art)
    items = []
    try:
        for entry in art.entries:
            # Procesar cada entrada del feed RSS
            # Usamos .get() porque al final son objetos -> opcionales
            print(list(entry.keys()))
            source = name
            link = entry.get("link", "")
            title = entry.get("title", "")
            published_raw = entry.get("published") or entry.get("published_parsed")
            
            summary = (
                entry.get("summary", "")
                or entry.get("summary_detail", "")
                
            )

            # fallbacks
            if not link or not title:
                continue

            items.append({
                "source": source,
                "link": link,
                "title": title,
                "published": published_raw,
                "summary": summary
            })

        return items

    except Exception as e:
        print(f"Error parsing RSS feed from {url}: {e}") # loggear error.
        return []


# hashing the article. DIFFERENT FROM MONGO'S ID (THAT'S LOCAL)
# asegura que no subamos artículos dobles a la db


# normalizing: toma lo parseado y corre funciones de predicting, etc para categorizar y asignar los values fatantes de nuestro ItemModel
def normalize_item(raw: dict) -> dict:
    """
    Normaliza un artículo crudo para que se ajuste a nuestro modelo de datos.
    """
    # Aquí puedes agregar lógica de normalización, como predecir categorías, etc.
    normalized = {
        "title": raw.get("title", "").strip(),
        "link": raw.get("link", "").strip(),
        "published": raw.get("published", "").strip(),
        "summary": raw.get("summary", "").strip(),
    }
    return normalized
