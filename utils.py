from pymongo import MongoClient
from bson.objectid import ObjectId
from fastapi import HTTPException
from datetime import datetime
import hashlib
import feedparser
from typing import Dict, Any, List

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



############### HELPERS ################

def compute_hash(source: dict, url: str, title: str) -> str:
    """
    Computa un hash SHA-256 para un artículo dado.
    """
    # Convertir el dict a un string y luego a bytes
    return hashlib.sha256(f"{source}-{url}-{title}".encode("utf-8")).hexdigest()


# CHECK THIS ONE LATER
import time
from datetime import datetime

def to_datetime_utc(published_raw, published_str: str | None):
    if published_raw:
        # If it's a struct_time (from feedparser)
        if hasattr(published_raw, 'tm_year'):
            ts = time.mktime(published_raw)
            return datetime.fromtimestamp(ts).astimezone(datetime.utc)
        # If it's already a number
        if isinstance(published_raw, (int, float)):
            return datetime.fromtimestamp(published_raw).astimezone(datetime.utc)
        # If it's a string, try to parse
        if isinstance(published_raw, str):
            try:
                return datetime.strptime(published_raw, "%Y-%m-%d %H:%M:%S").astimezone(datetime.utc)
            except ValueError:
                return None
    elif published_str:
        try:
            return datetime.strptime(published_str, "%Y-%m-%d %H:%M:%S").astimezone(datetime.utc)
        except ValueError:
            return None
    return None
        


def guess_category(title: str, summary_text: str) -> str:
    """ 
    Adivina la categoría del art, basado en los contenidos de su título y su descripción, detectando si cae en alguna de las categorías de: phishing, grooming, control parental o privacidad.
    """
    # Convertir a minúsculas para facilitar la comparación
    title = title.lower()
    summary_text = summary_text.lower()

    # Definir palabras clave para cada categoría
    categories = {
        "phishing": ["phishing", "scam", "identity theft"],
        "grooming": ["grooming", "harassment", "minors"],
        "control parental": ["parental control", "supervision", "children"],
        "privacidad": ["privacy", "personal data", "security", "social media", "personal information"],
    }

    # Contar coincidencias de palabras clave
    category_counts = {category: 0 for category in categories}

    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in title or keyword in summary_text:
                category_counts[category] += 1

    # Devolver la categoría con más coincidencias, o "otros" si ninguna coincide
    max_category = max(category_counts, key=category_counts.get)
    if category_counts[max_category] == 0:
        return "otros"
    
    return max_category



def normalize_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza un artículo parseado para que se ajuste a nuestro modelo de datos.
    Matches con ItemforGemini.
    """

    # hash for dedup
    hash = compute_hash(raw.get("source", ""), raw.get("link", ""), raw.get("title", ""))


    normalized = {
        "id": hash,
        "source": raw.get("source", "").strip(),
        "url": raw.get("link", "").strip(),
        "title": raw.get("title", "").strip(),
        "summary": raw.get("summary", "").strip(),
        "published": to_datetime_utc(published_raw = raw.get("published"), published_str = raw.get("published_parsed")),
        "category": guess_category(raw.get("title", ""), raw.get("summary", "")),
        
    }
    return normalized

def normalize_many(raw_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normaliza múltiples artículos parseados.
    """

    out = []
    for entry in raw_entries:
        try:
            if not entry.get("link") or not entry.get("title"):
                continue
            normalized = normalize_entry(entry)
            out.append(normalized)
        except Exception as e:
            # Manejar excepciones de normalización
            print(f"Error normalizando entrada: {e}")
    return out