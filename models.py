# USES BASE MODEL , CREATES ITEM OBJECTS TO BE SENT TO MONGO DB
from pydantic import BaseModel, Field, AnyHttpUrl
from typing import Optional, List, Dict
from datetime import datetime

# define categories for newsletter digest
# literal for strict value
Category = Literal["phishing", "grooming", "control parental", "privacidad", "otros"]

# define category priority
Priority = Literal["high", "medium", "low"]

# definir el item model para los datos que obtenemos de RSS

class ItemBase(BaseModel):
    source: str
    url: AnyHttpUrl
    title: str
    summary: Optional[str] = None # muchos RSS lo incluyen -> facilita parsing
    link: str
    pub_date: Optional[datetime] = None # No todos la traen
    category: Category = "otros" # default init en "otros"
    priority: Priority = "low" # default init en "low"
    #implement ItemOut attributes USE OPTIONAL
    digest: Optional[str] = None 
    kickstarter: Optional[str] = None
    activity: Optional[str] = None
    # add descriptors de processing
    processed: bool = False


# definir un item model que sale, con un id (único add on)
class ItemOut(ItemBase):
    id: str = Field(..., alias="_id") # alias para que mongo lo reconozca como _id

# definir un item model para los modelos en queue -- item sin procesar aún 
class ItemForGemini(ItemBase):
    id: str = Field(..., alias="_id")
    source: str
    url: AnyHttpUrl
    title: str
    summary: Optional[str] = None # puede ayudarle a gemini, O NO
    category: Category = "otros" # default init en "otros"
    published: Optional[datetime] = None # No todos la traen


# es un item base refinado


# definir un modelo para lo que gemini procesa de vuelta
class ItemOut(BaseModel):
    digest : str
    kickstarter : str
    activity : str
