import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

# 1. Load your hidden API key from the .env file
load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")

# 2. Connect to Pinecone
print("Connecting to Pinecone...")
pc = Pinecone(api_key=api_key)

index_name = "mental-health-rag"

# 3. Create the database index (bucket) if it doesn't exist yet
if index_name not in pc.list_indexes().names():
    print(f"Creating new database index called '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=384, # This matches the size of the AI text reader we will use
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1" 
        )
    )
    print("Database created successfully!")
else:
    print("Database already exists and is connected perfectly!")