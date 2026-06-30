from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from app.routers import auth, accounts, transfers, kyc, admin

app = FastAPI(
    title="SmartBank API",
    version="1.0.0",
    description="Digital banking simulation platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(transfers.router)
app.include_router(kyc.router)
app.include_router(admin.router)

@app.get("/", tags=["Health"])
def root():
    return RedirectResponse(url="/app/")