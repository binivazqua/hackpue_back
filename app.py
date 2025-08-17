

from fastapi import FastAPI, Depends, HTTPException, Query # api key requirement for endpoints importantes como queuery
import uvicorn
import os
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from utils import ensure_indexes, parse_rss, normalize_many
from rss_resources import RSS_FEEDS
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from copy import deepcopy
import google.generativeai as genai
from pydantic import BaseModel
from gemini import gemini_process_articles
from fastapi import BackgroundTasks


##### KILL ######## pkill -f "uvicorn app:app"


# loads the dotenv data
load_dotenv()

#configure gemini 
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL")





# INITIALIZE DB VARIABLES (from dotenv)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "cyberguardian")  # Default to "cyberguardian"
COLLECTION = os.getenv("COLLECTION")

# client Mongo 
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
coll = db[COLLECTION]

#initialize fastapI

app = FastAPI(title="Jack in the Code's API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

@app.get("/")
async def root():
    return {"Back running !!!"}


# MONGO DB CALL
@app.get("/mongoDB")
async def get_mongo_data():
    data = await coll.count_documents({})
    return {"data": data}

# initialize all mongodb before caaalll
@app.on_event("startup")
async def startup_event():
    await ensure_indexes(coll)


# api key requirement for endpoints importantes como queue
def require_api_key(api_key: str = Query(..., description="API Key for authentication")):
    if not api_key or api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="No tienes acceso. Datos protegidos")
    return True

# CLEAR DATABASE (for testing)
@app.delete("/clear-db")
async def clear_database():
    """ Borra todos los documentos de la colección - SOLO PARA TESTING """
    result = await coll.delete_many({})
    return {"deleted_count": result.deleted_count}

# ingest process: implementar parsing, hashing, normalizing
@app.post("/ingest/run")
async def ingest_run(limit:  int = 15):
    """ Toma los RSS de nuestro rss_resources y los digierre """
    inserted = 0
    duplicates = 0
    errors = 0
    for name, url in RSS_FEEDS.items():
        raw_items = parse_rss(name, url)
        normalized_items = normalize_many(raw_items)
        for item in normalized_items[:limit]:
            try:
                to_insert = deepcopy(item)
                await coll.insert_one(to_insert)
                inserted += 1
            except DuplicateKeyError:
                duplicates +=1
                pass      
            except Exception as e:
                errors +=1
                print(f"Error inserting item {item}: {e}")
    return {"inserted": inserted}


# queue (GEMINI API USE)
@app.get("/queue")
async def get_queue(limit: int = 10, _auth=Depends(require_api_key)):
    
    """ 
    Retrieves data de Mongo (parseada y normalizada) para ofrecer a gemini 
    Este endpoint implementa el proceso de distribución round robin para obtener artículos de diferentes fuentes de manera equitativa. El proceso funciona así:

    1. Obtiene todas las fuentes únicas presentes en la base de datos.
    2. Calcula cuántos artículos debe tomar de cada fuente para cumplir con el límite solicitado (`limit`). Si el límite no se divide de forma exacta entre las fuentes, las primeras fuentes reciben un artículo extra.
    3. Para cada fuente, obtiene los artículos más recientes según el límite calculado.
    4. Junta todos los artículos obtenidos, los normaliza y los ordena por fecha de publicación (del más nuevo al más antiguo).
    5. Devuelve la lista final de artículos, asegurando que todas las fuentes estén representadas de forma justa y priorizando el contenido más reciente.

    Este método garantiza que el queue tenga diversidad de fuentes y que ninguna fuente domine el resultado, lo cual es útil para mostrar información balanceada a los jueces.
    """
    
    projection = {
        "title": 1,
        "summary": 1,
        "published": 1,
        "source": 1,
        "category": 1,
    }

    # Get all unique sources
    sources = await coll.distinct("source")
    
    # Calculate items per source (distribute evenly)
    items_per_source = max(1, limit // len(sources))
    extra_items = limit % len(sources)
    
    all_items = []
    
    for i, source in enumerate(sources):
        # Some sources get one extra item if limit doesn't divide evenly
        source_limit = items_per_source + (1 if i < extra_items else 0)
        
        source_items = await coll.find(
            {"source": source}, 
            projection
        ).sort("published", -1).limit(source_limit).to_list(source_limit)
        
        for item in source_items:
            all_items.append({
                "id": str(item["_id"]),
                "title": item["title"],
                "summary": item["summary"],
                "published": item["published"],
                "source": item["source"],
                "category": item["category"],
                "processed": False,
            })
    
    # Sort all items by published date (newest first)
    all_items.sort(key=lambda x: x["published"], reverse=True)
    
    # Return only the requested limit
    return {"queue": all_items[:limit]}


# Alternative endpoint for random mix
@app.get("/queue/random")
async def get_queue_random(limit: int = 10, _auth=Depends(require_api_key)):
    """ 
    Retrieves random mix of articles from all sources
    """
    projection = {
        "title": 1,
        "summary": 1,
        "published": 1,
        "source": 1,
        "category": 1,
    }

    # Use MongoDB's $sample to get random documents
    pipeline = [
        {"$sample": {"size": limit}},
        {"$project": projection}
    ]
    
    items = []
    async for item in coll.aggregate(pipeline):
        items.append({
            "id": str(item["_id"]),
            "title": item["title"],
            "summary": item["summary"],
            "published": item["published"],
            "source": item["source"],
            "category": item["category"],
            "processed": False,
        })

    return {"queue": items}



####### INTEGRATE GEMINII #######

# what is seen in the docs
class ProcessAutoOut(BaseModel):
    ok: bool
    id: str 


@app.post("/process/{item_id}/auto", response_model=ProcessAutoOut)
async def process_article_auto(item_id: str, _auth=Depends(require_api_key)):
    """
     item_id: id en la db de MongoDB
     usa nuestro gemini.py para generar el output deseado
    """

    o_id = ObjectId(item_id)        

    # que esperamos ver en mongo 
    item = await coll.find_one({"_id": o_id}, {"title":1,"url":1,"summary":1,"category":1, "processed":1})

    if not item:
        raise HTTPException(status_code=404, detail="ITEM NOT FOUND !!!")

    # Call GEMINI API
    gemini_response = await gemini_process_articles(item, model_name=GEMINI_MODEL)

    # update MONGO
    res = await coll.update_one(
        {"_id": o_id, "processed": False}, 
        {"$set": {
            "processed": True, 
            "digest_es": gemini_response["digest_es"] or "", 
            "kickstarter_es": gemini_response["kickstarter_es"] or "", 
            "activity_es": gemini_response["activity_es"] or "", 
            "risk_level": gemini_response["risk_level"] or ""
        }})

    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="COULD NOT MODIFY ITEM. IT HAS BEEN ALREADY PROCESSED!!!")

    return {"ok": True, "id": item_id}

@app.post("/sync")
async def sync_articles(background_tasks: BackgroundTasks, limit: int = 10, api_key: str = Query(...)):
    """
    Sincroniza los artículos: ingesta, obtiene el queue y procesa cada artículo automáticamente.
    """
    # 1. Ingesta los artículos
    await ingest_run(limit=limit)

    # 2. Obtiene el queue
    queue_response = await get_queue(limit=limit, _auth=True)
    queue = queue_response["queue"]

    # 3. Procesa cada artículo en segundo plano
    for item in queue:
        background_tasks.add_task(process_article_auto, item["id"], _auth=True)

    return {"status": "sync started", "queued": len(queue)}
