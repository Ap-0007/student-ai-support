import os
import json
import re
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# --- 1. Setup & Initialize ---
load_dotenv()
pc_api_key = os.getenv("PINECONE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

app = FastAPI()

print("Initializing AI, Database, and LLM connections...")
# Connect to Pinecone Cloud
pc = Pinecone(api_key=pc_api_key)
index = pc.Index("mental-health-rag")

# Load Local Embedding Model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Configure Google Gemini Brain
genai.configure(api_key=gemini_api_key)
llm = genai.GenerativeModel('gemini-1.5-flash') 
print("Server Ready!")

# --- 2. Data Structures ---
class ChatRequest(BaseModel):
    user_message: str

class ChatResponse(BaseModel):
    mental_state: str
    reply: str
    is_escalated: bool
    coping_strategy: Optional[str] = None

# --- 3. Safety Guardrails ---
CRITICAL_REGEX = re.compile(r"\b(kill myself|suicide|end it all|give up on life|mar jana)\b", re.IGNORECASE)

def is_critical_danger(message: str) -> bool:
    return bool(CRITICAL_REGEX.search(message))

# --- 4. Database Search (RAG) ---
def retrieve_coping_strategy(message: str) -> str:
    query_embedding = model.encode(message).tolist()
    results = index.query(vector=query_embedding, top_k=1, include_metadata=True)
    if results['matches']:
        return results['matches'][0]['metadata']['text']
    return "Take a deep breath. We will get through this together."

# --- 5. Brain Logic (Gemini) ---
def analyze_and_respond(user_message: str, strategy: str, is_crisis: bool) -> dict:
    crisis_instruction = ""
    if is_crisis:
        crisis_instruction = """
        CRITICAL ALERT: The user is expressing thoughts of self-harm. 
        Your response must be incredibly gentle and empathetic. 
        You MUST naturally include this text in your reply: 'Please, if you are feeling overwhelmed, reach out to AASRA (9820466726) or Vandrevala Foundation (9999 666 555).'
        """

    prompt = f"""
    You are a supportive mental health AI for students.
    Student message: "{user_message}"
    Clinical strategy to mention: "{strategy}"
    {crisis_instruction}
    
    Task 1: Assess mental state (1-3 words).
    Task 2: Write a conversational, comforting response.
    
    Respond ONLY with a raw JSON object:
    {{
        "mental_state": "...",
        "reply": "..."
    }}
    """
    
    try:
        response = llm.generate_content(prompt)
        # Clean potential markdown formatting from AI output
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {"mental_state": "Distressed", "reply": "I'm listening. Please tell me more."}

# --- 6. Endpoints ---
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    user_msg = request.user_message
    
    # Check for crisis keywords
    crisis_flag = is_critical_danger(user_msg)
    
    # Get strategy from Pinecone
    strategy = retrieve_coping_strategy(user_msg)
    
    # Get empathetic response from Gemini
    ai_output = analyze_and_respond(user_msg, strategy, crisis_flag)
    
    return ChatResponse(
        mental_state=ai_output.get("mental_state", "Analyzing..."),
        reply=ai_output.get("reply", "I'm here."),
        is_escalated=crisis_flag,
        coping_strategy=strategy if not crisis_flag else None
    )