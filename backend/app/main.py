from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import create_db_and_tables

settings = get_settings()
PROJECT_ROOT = settings.project_root
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="ContractMind AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import routes  # noqa: E402

# Mount API router
app.include_router(routes.router)

# Mount frontend static assets if available
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    fav = FRONTEND_DIST / "favicon.svg"
    if fav.is_file():
        return FileResponse(fav, media_type="image/svg+xml")
    return FileResponse(FRONTEND_DIST / "index.html")


@app.get("/")
async def root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "ContractMind AI API is running. Build frontend with 'npm run build'."}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Catch-all route for SPA client-side routing and root-level static files."""
    # Never intercept /api or /docs
    if full_path.startswith("api") or full_path in {"docs", "redoc", "openapi.json"}:
        return {"error": "Not found"}

    target = FRONTEND_DIST / full_path
    if full_path and target.is_file():
        return FileResponse(target)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    return {"message": "Frontend build not found. Run 'npm run build' inside frontend directory."}
