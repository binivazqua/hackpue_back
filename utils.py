from pymongo import MongoClient
from pymongo import ASCENDING
from bson.objectid import ObjectId
from fastapi import HTTPException
from datetime import datetime, timezone
import hashlib
import feedparser
from typing import Dict, Any, List
# CHECK THIS ONE LATER
import time
import re


def to_object_id(id_str: str) -> ObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    return ObjectId(id_str)

# ensure not dedups:

async def ensure_indexes(coll):
    """
    Crea índices necesarios en la colección:
    - hash: único (para evitar duplicados)
    - processed: para búsquedas rápidas de cola/digest
    - published_at: para ordenar por fecha
    """
    await coll.create_index([("hash", ASCENDING)], unique=True)
    await coll.create_index([("processed", ASCENDING)])
    await coll.create_index([("published_at", ASCENDING)])



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
            #print(list(entry.keys()))
            source = name
            link = entry.get("link", "")
            title = entry.get("title", "")
            published_str = entry.get("published", "")  # String format
            published_parsed = entry.get("published_parsed")  # struct_time format

            summary = (
                entry.get("summary", "")
                or entry.get("summary_detail", "")
                
            )

            # fallbacks
            if not link or not title:
                continue

            items.append({
                "source": source,
                "url": link,
                "title": title,
                "published_raw": published_str,
                "published_parsed": published_parsed,
                "summary_raw": summary
            })

        return items

    except Exception as e:
        print(f"Error parsing RSS feed from {url}: {e}") # loggear error.
        return []


# hashing the article. DIFFERENT FROM MONGO'S ID (THAT'S LOCAL)
# asegura que no subamos artículos dobles a la db


# normalizing: toma lo parseado y corre funciones de predicting, etc para categorizar y asignar los values fatantes de nuestro ItemModel



############### HELPERS ################

def clean_text(text: str) -> str:
    """
    Limpia HTML tags, caracteres especiales y texto no deseado del contenido.
    """
    if not text:
        return ""
    
    # Remover HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remover "By BCP Staff" y variaciones
    text = re.sub(r'By\s+BCP\s+Staff', '', text, flags=re.IGNORECASE)
    
    # Remover múltiples espacios en blanco y saltos de línea
    text = re.sub(r'\s+', ' ', text)
    
    # Remover caracteres especiales al inicio y final
    text = text.strip()
    
    return text

def compute_hash(source: dict, url: str, title: str) -> str:
    """
    Computa un hash SHA-256 para un artículo dado.
    """
    base = f"{source}|{url}|{title}".encode()
    return hashlib.sha256(base).hexdigest()




def to_datetime_utc(published_raw, published_str):
    # Debug: agregar logging temporal
    # print(f"DEBUG - published_raw: {published_raw} (type: {type(published_raw)})")
    # print(f"DEBUG - published_str: {published_str} (type: {type(published_str)})")

    if published_raw:
        # If it's a struct_time (from feedparser)
        if hasattr(published_raw, 'tm_year'):
            ts = time.mktime(published_raw)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.isoformat()  # Return as ISO string for JSON serialization
        # If it's already a number
        if isinstance(published_raw, (int, float)):
            dt = datetime.fromtimestamp(published_raw, tz=timezone.utc)
            return dt.isoformat()  # Return as ISO string for JSON serialization
        # If it's a string, try multiple date formats
        if isinstance(published_raw, str) and published_raw.strip():
            # Common RSS date formats
            formats = [
                "%B %d, %Y | %I:%M%p",       # July 22, 2025 | 7:47AM (FTC format)
                "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822 format
                "%Y-%m-%dT%H:%M:%S%z",       # ISO format with timezone
                "%Y-%m-%d %H:%M:%S",         # Simple format
                "%a, %d %b %Y %H:%M:%S GMT", # GMT format
                "%a, %d %b %Y %H:%M:%S"      # Without timezone
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(published_raw, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    # Return as ISO string for JSON serialization
                    return dt.astimezone(timezone.utc).isoformat()
                except ValueError:
                    continue
            # Si no coincide con ningún formato, mostrar el string para debug
            print(f"DEBUG - No format matched for: '{published_raw}'")
    
    # Try published_str (which is actually published_parsed - struct_time)
    if published_str and hasattr(published_str, 'tm_year'):
        ts = time.mktime(published_str)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.isoformat()  # Return as ISO string for JSON serialization
    
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
    hash = compute_hash(raw.get("source", ""), raw.get("url", ""), raw.get("title", ""))

    summary_raw = clean_text(raw.get("summary_raw", ""))

    normalized = {
        "hash": hash,
        "source": raw.get("source", "").strip(),
        "url": raw.get("url", "").strip(),
        "title": raw.get("title", "").strip(),
        "summary": summary_raw,
        "published": to_datetime_utc(published_raw = raw.get("published_raw"), published_str = raw.get("published_parsed")),
        "category": guess_category(raw.get("title", ""), summary_raw),
        
    }
    return normalized

def normalize_many(raw_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normaliza múltiples artículos parseados.
    """

    out = []
    for entry in raw_entries:
        try:
            if not entry.get("url") or not entry.get("title"): # DO NOT ALTER THIS LINE
                continue
            normalized = normalize_entry(entry)
            out.append(normalized)
        except Exception as e:
            # Manejar excepciones de normalización
            print(f"Error normalizando entrada: {e}")
    return out