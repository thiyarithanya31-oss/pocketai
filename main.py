import os
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from passlib.context import CryptContext
from jose import jwt, JWTError
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. App Initialization & Global AI Client
# ---------------------------------------------------------
app = FastAPI()

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# THE FIX: Initialize the client once globally to prevent SSL connection drops
client = genai.Client(api_key="AQ.Ab8RN6L53WqFfB0u3iMdZrT2eG6XUpMTa36FAtXy54x054A4vg")

# In-Memory Databases (Resets on server restart)
users_db = {}
history_db = {}

# Security Settings
SECRET_KEY = "your-super-secret-pocketsmart-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------
# 2. Authentication Helper Functions
# ---------------------------------------------------------
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in users_db:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or session invalid")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# ---------------------------------------------------------
# 3. Page Routes (HTML)
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"username": current_user})

@app.get("/generate-home", response_class=HTMLResponse)
async def home_planner_page(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="home.html")

@app.get("/generate-party", response_class=HTMLResponse)
async def party_planner_page(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="party.html")

@app.get("/generate-jewelry", response_class=HTMLResponse)
async def jewelry_planner_page(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="jewelry_plan.html")

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, current_user: str = Depends(get_current_user)):
    user_history = history_db.get(current_user, [])
    return templates.TemplateResponse(request=request, name="history.html", context={"history": user_history})

# ---------------------------------------------------------
# 4. Authentication Action Routes
# ---------------------------------------------------------
@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...)):
    if username in users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    users_db[username] = get_password_hash(password)
    history_db[username] = []
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.post("/login")
async def login_user(username: str = Form(...), password: str = Form(...)):
    if username not in users_db or not verify_password(password, users_db[username]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": username})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, samesite="lax")
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response

# ---------------------------------------------------------
# 5. AI Generation Routes (Gemini Integration)
# ---------------------------------------------------------
@app.post("/generate-home")
async def generate_home_ai(budget: str = Form(...), room: str = Form(...), style: str = Form(...), current_user: str = Depends(get_current_user)):
    try:
        prompt = f"""
        You are an expert interior designer. Create a budget plan for a {room} in a {style} style with a total budget of {budget} INR.
        Return ONLY valid JSON in this exact structure. Do not use markdown blocks:
        {{
            "summary": "Short encouraging text about this design",
            "total_budget": "{budget} INR",
            "categories": [
                {{"name": "Furniture", "allocated": "amount", "items": ["Item 1 - Price", "Item 2 - Price"]}},
                {{"name": "Decor", "allocated": "amount", "items": ["Item 1 - Price"]}}
            ],
            "shopping_links": ["Amazon link idea", "IKEA link idea"]
        }}
        """
        response = client.models.generate_content(
            model='gemini-1.5-flash', # THE FIX: Corrected model name for Home Route
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(raw_text)
        history_db[current_user].append({"type": "Home Planner", "room": room, "style": style, "budget": budget, "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "result": result_data})
        return JSONResponse(content=result_data)
    except Exception as e:
        print(f"CRITICAL AI ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"AI Generation Failed: {str(e)}")

@app.post("/generate-party")
async def generate_party_ai(budget: str = Form(...), theme: str = Form(...), current_user: str = Depends(get_current_user)):
    try:
        prompt = f"""
        You are an expert event planner. Create a budget plan for a {theme} themed party with a total budget of {budget} INR.
        Return ONLY valid JSON in this exact structure. Do not use markdown blocks:
        {{
            "summary": "Short encouraging text about this party plan",
            "total_budget": "{budget} INR",
            "categories": [
                {{"name": "Venue & Decor", "allocated": "amount", "items": ["Item 1 - Price"]}},
                {{"name": "Food & Drinks", "allocated": "amount", "items": ["Item 1 - Price"]}}
            ],
            "shopping_links": ["Amazon link idea", "Party store link idea"]
        }}
        """
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(raw_text)
        history_db[current_user].append({"type": "Party Planner", "theme": theme, "budget": budget, "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "result": result_data})
        return JSONResponse(content=result_data)
    except Exception as e:
        print(f"CRITICAL AI ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"AI Generation Failed: {str(e)}")

@app.post("/generate-jewelry")
async def generate_jewelry_ai(budget: str = Form(...), style: str = Form(...), current_user: str = Depends(get_current_user)):
    try:
        prompt = f"""
        You are an expert jewelry consultant. Create a purchase plan for {style} style jewelry with a total budget of {budget} INR.
        Return ONLY valid JSON in this exact structure. Do not use markdown blocks:
        {{
            "summary": "Short encouraging text about this jewelry plan",
            "total_budget": "{budget} INR",
            "categories": [
                {{"name": "Gold/Silver Allocation", "allocated": "amount", "items": ["Item 1 - Price"]}},
                {{"name": "Making Charges & Taxes", "allocated": "amount", "items": ["Item 1 - Price"]}}
            ],
            "shopping_links": ["Tanishq link idea", "Malabar link idea"]
        }}
        """
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(raw_text)
        history_db[current_user].append({"type": "Jewelry Planner", "style": style, "budget": budget, "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "result": result_data})
        return JSONResponse(content=result_data)
    except Exception as e:
        print(f"CRITICAL AI ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"AI Generation Failed: {str(e)}")