import os
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# 1. Connect to Pinecone
load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=api_key)
index = pc.Index("mental-health-rag")

# 2. Load the AI Text Reader (Embedding Model)
print("Loading AI embedding model (this might take a few seconds)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# 3. Our Clinical Knowledge Base (MVP Version)
coping_strategies = [
    {"id": "cbt-1", "text": "Box Breathing: Breathe in for 4 seconds, hold for 4, exhale for 4, hold for 4. Repeat until your heart rate slows down.", "category": "Anxiety"},
    {"id": "cbt-2", "text": "5-4-3-2-1 Grounding: Name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste. This pulls your brain out of an anxiety spiral.", "category": "Panic"},
    {"id": "cbt-3", "text": "Cognitive Reframing: Ask yourself, 'Is this a fact or just a feeling? Will this exam define my entire life 5 years from now?'", "category": "Academic Overthinking"},
    {"id": "study-1", "text": "Pomodoro Technique: Study for 25 minutes, then take a 5-minute break to reduce academic burnout.", "category": "Academic Stress"}
]

# 4. Convert text to AI numbers and upload to Pinecone
print("Translating strategies and uploading to the database...")
vectors_to_upload = []

for strategy in coping_strategies:
    # Convert the text into a 384-dimension numerical vector
    embedding = model.encode(strategy["text"]).tolist() 
    
    # Package it up with the original text so the AI can read it later
    vectors_to_upload.append((
        strategy["id"], 
        embedding, 
        {"text": strategy["text"], "category": strategy["category"]}
    ))

# Push everything to the cloud
index.upsert(vectors=vectors_to_upload)
print("Upload complete! Your database now has clinical memory.")