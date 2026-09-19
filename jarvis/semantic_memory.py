import json
import os
import threading
import numpy as np
from pathlib import Path


class SemanticMemory:
    def __init__(self):
        self.model = None  # lazy loaded
        self.index = None
        self.facts = []
        self.index_path = Path('jarvis/data/semantic_index.faiss')
        self.facts_path = Path('jarvis/data/semantic_facts.json')
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._model_lock = threading.Lock()
        self._load_existing()
    
    def _get_model(self):
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    print("[SEMANTIC] Loading embedding model...")
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer('all-MiniLM-L6-v2')  # small, fast, local
        return self.model


    def _encode(self, texts: list):
        model = self._get_model()
        with self._model_lock:
            return model.encode(texts)

    def prewarm(self):
        """Pre-load embedding model during startup to eliminate first-query latency."""
        try:
            self._get_model()
            print("[SEMANTIC] Embedding model pre-warmed successfully.")
        except Exception as e:
            print(f"[SEMANTIC] Pre-warm notice: {e}")
    
    def _load_existing(self):
        if self.facts_path.exists():
            with open(self.facts_path, 'r', encoding='utf-8') as f:
                self.facts = json.load(f)
        if self.index_path.exists() and self.facts:
            import faiss
            self.index = faiss.read_index(str(self.index_path))
    
    def add_fact(self, fact: str, category: str = "") -> str:
        import faiss
        
        embedding = self._encode([fact])
        
        if self.index is None:
            dim = embedding.shape[1]
            self.index = faiss.IndexFlatL2(dim)
        
        self.index.add(embedding.astype('float32'))
        self.facts.append({
            "text": fact,
            "category": category,
            "index": len(self.facts)
        })
        
        # Save
        faiss.write_index(self.index, str(self.index_path))
        with open(self.facts_path, 'w', encoding='utf-8') as f:
            json.dump(self.facts, f, indent=2)
        
        return f"Fact stored: {fact[:80]}"
    
    def search(self, query: str, top_k: int = 5, max_distance: float = 1.3) -> list:
        if not self.index or not self.facts or not query or not query.strip():
            return []
        
        query_embedding = self._encode([query.strip()])
        
        distances, indices = self.index.search(
            query_embedding.astype('float32'), 
            min(top_k, len(self.facts))
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.facts) and idx >= 0:
                dist = float(distances[0][i])
                if dist <= max_distance:
                    fact = self.facts[idx].copy()
                    fact['score'] = dist
                    results.append(fact)
        
        # Sort by relevance (lower distance = better)
        results.sort(key=lambda x: x['score'])
        return results
    
    def get_relevant_context(self, query: str, top_k: int = 5, max_distance: float = 1.3) -> str:
        if not query or len(query.strip()) < 4 or query.strip().lower() in {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye"}:
            return ""
        results = self.search(query, top_k, max_distance=max_distance)
        if not results:
            return ""
        facts = [r['text'] for r in results]
        return "Relevant facts: " + "; ".join(facts)

