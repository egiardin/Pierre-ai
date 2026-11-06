from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

class RoomInfo(BaseModel):
    name: str = Field(description="Nom de la chambre")
    description: Optional[str] = Field(description="Description de la chambre")

class HotelExtractedInfo(BaseModel):
    name: Optional[str] = Field(description="Nom de l'hôtel")
    address: Optional[str] = Field(description="Adresse complète de l'hôtel")
    email: Optional[str] = Field(description="Email de contact")
    phone: Optional[str] = Field(description="Numéro de téléphone")
    amenities: List[str] = Field(description="Liste des équipements de l'hôtel (ex: piscine, spa, wifi)")
    rooms: List[RoomInfo] = Field(description="Liste des chambres détectées")

def extract_hotel_info(text_content: str, api_key: Optional[str] = None) -> HotelExtractedInfo:
    """
    Extrait les informations structurées d'un hôtel à partir du contenu textuel en utilisant le SDK google-genai.
    """
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Extrais les informations structurées de cet hôtel à partir du texte suivant :\n\n{text_content}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=HotelExtractedInfo,
            temperature=0.1
        ),
    )
    
    return response.parsed
