from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import time
import os

# Import your routers
from app.routes.MessageRoute import router as message_router
from app.routes.FileProcessRoute import router as file_process_router

load_dotenv()

app = FastAPI()

# Get the shared secret from .env
FASTAPI_SECRET_KEY = os.getenv("FASTAPI_SECRET_KEY")

@app.middleware("http")
async def verify_nextjs_authorization(request: Request, call_next):
    # Skip authorization for root endpoint or health checks
    if request.url.path == "/" or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
        return await call_next(request)
        
    # Get the authorization header that Next.js sends
    api_key = request.headers.get("X-API-Key")
    
    # Check if the header exists and matches our secret
    if not api_key or api_key != FASTAPI_SECRET_KEY:
        return JSONResponse(
            status_code=401,
            content={"message": "Unauthorized. Invalid or missing API key.", "success": False}
        )
        
    # If authorized, proceed to the actual route
    response = await call_next(request)
    return response

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    print(f"[{request.method}] {request.url.path} - Completed in {process_time:.3f}s")
    
    return response

# Include the routers
app.include_router(message_router)
app.include_router(file_process_router)

@app.get("/")
def home():
    return {
        "message": "API running"
    }