# -*- coding: utf-8 -*-
# UNIÓN DE NUESTROS ARTÍCULOS PROCESADOS PARA MANDARLOS 

from fastapi import FastAPI
import uvicorn
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


# loads the dotenv data
load_dotenv()

# INITIALIZE DB VARIABLES (from dotenv)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION = os.getenv("COLLECTION")

# client Mongo 
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
coll = db[COLLECTION]

#initialize fastap

app = FastAPI(title="Jack in the Code's API")

@app.get("/")
async def root():
    return {"Back running !!!"}


# MONGO DB CALL
@app.get("/mongoDB")
async def get_mongo_data():
    data = await coll.count_documents({})
    return {"data": data}
