

from fastapi import FastAPI
import uvicorn
import os
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from utils import ensure_indexes, parse_rss, normalize_many
from rss_resources import RSS_FEEDS
from pymongo.errors import DuplicateKeyError
from copy import deepcopy


# loads the dotenv data
load_dotenv()

# INITIALIZE DB VARIABLES (from dotenv)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "cyberguardian")  # Default to "cyberguardian"
COLLECTION = os.getenv("COLLECTION")

# client Mongo 
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
coll = db[COLLECTION]

#initialize fastap

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
def require_api_key(api_key: str):
    if api_key != os.getenv("API_KEY"):
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
