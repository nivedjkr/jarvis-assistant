import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np


class SemanticMemory:
    """
    Mark 5.4 Hierarchical Contextual Memory Layer.
    Combines local FAISS vector indexing with metadata filtering across
    projects, entities, topics, and Obsidian vault notes.
    """

    def __init__(self, index_path: Optional[str] = None, facts_path: Optional[str] = None):
        self.model = None  # lazy loaded
        self.index = None
        self.facts: List[Dict[str, Any]] = []
        
        self.index_path = Path(index_path) if index_path else Path('jarvis/data/semantic_index.faiss')
        self.facts_path = Path(facts_path) if facts_path else Path('jarvis/data/semantic_facts.json')
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
            try:
                with open(self.facts_path, 'r', encoding='utf-8') as f:
                    self.facts = json.load(f)
            except Exception as e:
                print(f"[SEMANTIC] Error reading facts: {e}")
                self.facts = []
        if self.index_path.exists() and self.facts:
            try:
                import faiss
                self.index = faiss.read_index(str(self.index_path))
            except Exception as e:
                print(f"[SEMANTIC] Error reading FAISS index: {e}")
                self.index = None
    
    def add_fact(
        self,
        fact: str,
        category: str = "general",
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "manual",
        source_path: Optional[str] = None
    ) -> str:
        """
        Stores a fact with hierarchical metadata into the FAISS vector store.
        """
        import faiss
        
        clean_text = fact.strip()
        if not clean_text:
            return "Error: Empty fact text."

        embedding = self._encode([clean_text])
        
        if self.index is None:
            dim = embedding.shape[1]
            self.index = faiss.IndexFlatL2(dim)
        
        self.index.add(embedding.astype('float32'))
        fact_meta = {
            "text": clean_text,
            "category": category.strip().lower() if category else "general",
            "project_id": project_id.strip().lower() if project_id else "",
            "tags": [t.strip().lower() for t in tags] if tags else [],
            "source": source,
            "source_path": str(source_path) if source_path else "",
            "timestamp": datetime.now().isoformat(),
            "index": len(self.facts)
        }
        self.facts.append(fact_meta)
        
        # Persist index and facts
        faiss.write_index(self.index, str(self.index_path))
        with open(self.facts_path, 'w', encoding='utf-8') as f:
            json.dump(self.facts, f, indent=2)
        
        return f"Hierarchical fact stored [{fact_meta['category']}]: {clean_text[:80]}"
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        max_distance: float = 1.3,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs vector search with optional hierarchical metadata filtering.
        """
        if not self.index or not self.facts or not query or not query.strip():
            return []
        
        query_embedding = self._encode([query.strip()])
        
        # Over-sample to allow metadata filtering
        search_k = min(max(top_k * 4, 10), len(self.facts))
        distances, indices = self.index.search(
            query_embedding.astype('float32'), 
            search_k
        )
        
        target_cat = category.strip().lower() if category else None
        target_proj = project_id.strip().lower() if project_id else None
        target_tag = tag.strip().lower() if tag else None

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.facts) and idx >= 0:
                dist = float(distances[0][i])
                if dist <= max_distance:
                    fact = self.facts[idx].copy()
                    
                    # Metadata filtering
                    if target_cat and fact.get("category") != target_cat:
                        continue
                    if target_proj and fact.get("project_id") != target_proj:
                        continue
                    if target_tag and target_tag not in fact.get("tags", []):
                        continue
                        
                    fact['score'] = dist
                    results.append(fact)
                    if len(results) >= top_k:
                        break
        
        # Sort by relevance (lower distance = better match)
        results.sort(key=lambda x: x['score'])
        return results
    
    def get_relevant_context(
        self,
        query: str,
        top_k: int = 5,
        max_distance: float = 1.3,
        category: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> str:
        """
        Returns a formatted context string for prompt injection.
        """
        if not query or len(query.strip()) < 4 or query.strip().lower() in {
            "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye"
        }:
            return ""
            
        results = self.search(
            query,
            top_k=top_k,
            max_distance=max_distance,
            category=category,
            project_id=project_id
        )
        if not results:
            return ""
            
        lines = []
        for r in results:
            cat_label = f"[{r.get('category', 'general').upper()}]"
            proj_label = f" ({r['project_id']})" if r.get('project_id') else ""
            lines.append(f"• {cat_label}{proj_label} {r['text']}")
            
        return "Hierarchical Memory Context:\n" + "\n".join(lines)

    def index_obsidian_vault(self, vault_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Recursively indexes notes in the Obsidian vault into the hierarchical vector store.
        Parses headers, categorizes folders, and persists embeddings.
        """
        from jarvis.tools import _resolve_obsidian_vault_path
        
        resolved_path = vault_path or _resolve_obsidian_vault_path()
        if not resolved_path or not os.path.isdir(resolved_path):
            return {
                "status": "error",
                "error": f"Obsidian vault directory not found: {resolved_path}"
            }

        vault = Path(resolved_path)
        notes_scanned = 0
        chunks_indexed = 0

        # Walk markdown files
        for md_path in vault.rglob("*.md"):
            # Skip hidden / system directories
            parts = [p.lower() for p in md_path.parts]
            if any(p.startswith(".") or p in {"node_modules", "venv", "__pycache__"} for p in parts):
                continue

            try:
                text = md_path.read_text(encoding="utf-8", errors="replace").strip()
                if not text:
                    continue
                notes_scanned += 1

                # Classify category and project from path hierarchy
                category = "general"
                project_id = ""
                rel_path = md_path.relative_to(vault).as_posix()

                if "profile" in rel_path.lower():
                    category = "profile"
                elif "topics" in rel_path.lower():
                    category = "topic"
                elif "people" in rel_path.lower():
                    category = "person"
                elif "areas" in rel_path.lower() or "projects" in rel_path.lower():
                    category = "project"
                    project_id = md_path.stem.lower()
                elif re.match(r"\d{4}-\d{2}-\d{2}", md_path.stem):
                    category = "daily_log"

                # Chunk note by headers or paragraphs
                chunks = self._chunk_markdown(text, title=md_path.stem)
                for chunk in chunks:
                    self.add_fact(
                        fact=chunk,
                        category=category,
                        project_id=project_id,
                        tags=[md_path.stem.lower()],
                        source="obsidian",
                        source_path=rel_path
                    )
                    chunks_indexed += 1

            except Exception as e:
                print(f"[SEMANTIC] Failed to index note '{md_path}': {e}")

        return {
            "status": "success",
            "vault_path": str(vault),
            "notes_scanned": notes_scanned,
            "chunks_indexed": chunks_indexed
        }

    def _chunk_markdown(self, text: str, title: str, max_chunk_chars: int = 500) -> List[str]:
        """Splits markdown text into cohesive sections with context headers."""
        chunks = []
        # Split on headers (# Header)
        sections = re.split(r"(?m)^(#{1,4}\s+.+)$", text)
        current_header = title

        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue
            if re.match(r"^#{1,4}\s+", sec_clean):
                current_header = sec_clean.lstrip("#").strip()
            else:
                # Add chunk with title and header prefix
                prefix = f"[{title} > {current_header}] "
                # If section is very long, split into paragraphs
                paragraphs = sec_clean.split("\n\n")
                for p in paragraphs:
                    p_clean = p.strip()
                    if len(p_clean) > 20:
                        chunks.append(f"{prefix}{p_clean[:max_chunk_chars]}")

        if not chunks and len(text) > 20:
            chunks.append(f"[{title}] {text[:max_chunk_chars]}")

        return chunks


_SEMANTIC_MEMORY_INSTANCE: Optional[SemanticMemory] = None

def get_semantic_memory(index_path: Optional[str] = None, facts_path: Optional[str] = None) -> SemanticMemory:
    global _SEMANTIC_MEMORY_INSTANCE
    if _SEMANTIC_MEMORY_INSTANCE is None or index_path is not None:
        inst = SemanticMemory(index_path=index_path, facts_path=facts_path)
        if index_path is None:
            _SEMANTIC_MEMORY_INSTANCE = inst
        return inst
    return _SEMANTIC_MEMORY_INSTANCE
