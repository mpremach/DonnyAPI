import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# IMPORT THE NEW MASTER BRAIN
from app.memory.donny_memory import process_with_memory

app = FastAPI(title="Donny Core API")
load_dotenv()

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def donny_prompt(request: ChatRequest):
    try:
        # Pass the user message to the Master Brain
        final_response = process_with_memory(request.message)

        # Mock the stream so your Voice Client TTS reads it fluidly
        def instant_stream():
            for char in final_response:
                yield char
        
        return StreamingResponse(instant_stream(), media_type="text/plain")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Donny Error: {str(e)}")

@app.get("/")
async def system_check():
    return {"status": "Donny Core API is online."}