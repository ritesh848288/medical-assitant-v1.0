# backend/knowledge_base.py
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class MedicalKnowledgeBase:
    def __init__(self):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatL2(384)  # 384-dim embeddings
        self.documents = []
        
    def add_document(self, text, metadata):
        embedding = self.encoder.encode([text])
        self.index.add(embedding)
        self.documents.append({'text': text, 'metadata': metadata})
    
    def search(self, query, k=5):
        query_embedding = self.encoder.encode([query])
        distances, indices = self.index.search(query_embedding, k)
        return [self.documents[i] for i in indices[0]]