# backend/main.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from me_worker import Me

app = FastAPI()
me = Me()  # loads files at startup

# allow your Next.js dev server / deployed front-end
origins = [
    os.getenv("CLIENT_ORIGIN_DEVELOPMENT"),
    os.getenv("CLIENT_ORIGIN_PRODUCTION"),  
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list = []  # list of {"role": "user"|"assistant", "content": "..."}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        reply = me.chat(req.message, req.history)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True
    )
