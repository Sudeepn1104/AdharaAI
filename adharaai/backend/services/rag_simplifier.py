"""
rag_simplifier.py — RAG + local LLM pipeline for plain-English clause rewriting.

Owner: P2 (NLP Engineer)

Setup checklist (see AdharaAI_P2_Requirements.pdf for full detail):
  1. Install Ollama, run: ollama pull mistral
  2. pip install faiss-cpu sentence-transformers langchain langchain-community
  3. Build the FAISS index from P3's labeled clauses (Month 2 script) and
     save it to models/clause_index.faiss + models/clause_meta.json
     (models/ is gitignored — share large files via Drive, not GitHub)
  4. Fill in simplify_with_rag() below

simplifier.py already imports simplify_with_rag from this file and falls
back to keyword substitution automatically if this raises an exception —
so it's safe to leave this unfinished/broken while you build it; the app
keeps working on the keyword path in the meantime.
"""

# import faiss
# import json
# import numpy as np
# from sentence_transformers import SentenceTransformer
# import requests

# TODO: load these once at module level, not per-call
# embedder = SentenceTransformer('all-MiniLM-L6-v2')
# index = faiss.read_index('models/clause_index.faiss')
# meta = json.load(open('models/clause_meta.json'))


def simplify_with_rag(clause_text: str) -> str:
    """
    Retrieve similar labeled examples via FAISS, then use them to guide
    Mistral (via Ollama) in rewriting the clause into plain English.

    Must raise an exception (not return a fallback string) if RAG/Ollama
    isn't available — simplifier.py's try/except handles the fallback to
    keyword substitution automatically.
    """
    raise NotImplementedError("RAG pipeline not yet built — see Month 3 of the requirements doc")

    # Reference implementation (from requirements doc):
    #
    # vec = embedder.encode([clause_text])
    # vec = np.array(vec, dtype='float32')
    # D, I = index.search(vec, k=3)
    #
    # examples = ''
    # for i in I[0]:
    #     examples += f'Original: {meta["texts"][i]}\n'
    #     examples += f'Simple: {meta["simplified"][i]}\n'
    #
    # prompt = f'''You simplify Indian legal clauses into plain English.
    # Keep it under 2 sentences. Never add legal advice.
    #
    # Examples of good simplifications:
    # {examples}
    #
    # Now simplify this clause:
    # {clause_text}
    #
    # Simple version:'''
    #
    # res = requests.post('http://localhost:11434/api/generate',
    #     json={'model': 'mistral', 'prompt': prompt, 'stream': False})
    # return res.json()['response'].strip()
