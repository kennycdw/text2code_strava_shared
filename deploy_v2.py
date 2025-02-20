from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app_instance import port
import uvicorn
from routes.routes_telegram import telegram_router
from routes.routes_strava import strava_router
from app_instance import lifespan, environment


if environment == "local":
    worker_count = 1
else:
    worker_count = 3


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(telegram_router, prefix="")
app.include_router(strava_router, prefix="")


@app.get("/")
def hello():
    return "Hello World"


if __name__ == "__main__":
    uvicorn.run("deploy_v2:app", host="0.0.0.0", port=port, reload=False, reload_delay=1, workers=worker_count)
