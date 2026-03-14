# backend/main.py
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from me_worker import Me

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend.cors")

app = FastAPI()
me = None


def get_me():
    global me
    if me is None:
        me = Me()
    return me

# allow only explicitly configured front-end origins
origins = [
    # os.getenv("CLIENT_ORIGIN_DEVELOPMENT"),
    os.getenv("CLIENT_ORIGIN_PRODUCTION"),
]
origins = [origin.strip() for origin in origins if origin and origin.strip()]

logger.info("Allowed origins: %s", origins)


# Middleware to enforce origin restriction on API routes
@app.middleware("http")
async def enforce_origin_restriction(request: Request, call_next):
    origin = request.headers.get("origin")
    client_ip = request.client.host if request.client else "unknown"

    if request.url.path.startswith("/api/"):
        logger.info(
            "Incoming request path=%s method=%s origin=%s client_ip=%s",
            request.url.path,
            request.method,
            origin,
            client_ip,
        )

    if request.url.path.startswith("/api/"):
        if origin and origin not in origins:
            logger.warning(
                "Blocked request path=%s method=%s origin=%s client_ip=%s allowed_origins=%s",
                request.url.path,
                request.method,
                origin,
                client_ip,
                origins,
            )
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    return await call_next(request)


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
        reply = get_me().chat(req.message, req.history)
        return {"reply": reply}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True
    )
