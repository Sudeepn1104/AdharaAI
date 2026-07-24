<div align="center">

# ⚖️ AdharaAI — Indian Legal Document Simplifier

**Your foundation for understanding what you sign.**

Upload a rental agreement, court notice, or employment contract — AdharaAI flags risky clauses, explains every line in plain English, and gives you a personal action checklist.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Accuracy](https://img.shields.io/badge/Risk%20Detection-100%25%20F1-brightgreen?style=flat)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat)]()

<br/>

> *Adhara* (आधार) — Sanskrit for **foundation**. Your legal rights are your foundation. We protect them.

</div>

---

## 🎯 The Problem

Most legal AI tools are built for the US or UK. India has its own legal language, court structure, and document formats — rental agreements with stamp duty clauses, Section 138 negotiable instrument notices, consumer court orders, and government circulars.

When ordinary people receive legal notices, they either pay thousands of rupees to a lawyer just to understand what it says — or they sign without understanding.

**AdharaAI fills that gap.**

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 Multi-format upload | PDF, scanned images (OCR via Tesseract), and plain text |
| 🔍 Smart clause segmentation | 4-strategy waterfall handles numbered, lettered, WHEREAS, and paragraph-style documents |
| 🚨 Risk flagging | 30+ rules detecting unfair terms under Indian law — 100% precision, 100% recall on test suite |
| 💬 Plain English rewrite | 80+ substitution rules translate legal jargon into language anyone understands |
| ✅ Action checklist | Extracts deadlines and to-dos specific to your document |
| 🔒 Privacy-first | Raw document text auto-deleted within 5 minutes. Nothing sent to external APIs. |
| 🛡️ Production-hardened | Rate limiting, file validation by magic bytes, security headers, global error handling |

---

## 📊 Accuracy Test Results

```
Risk Flagging Precision  : 100.0%
Risk Flagging Recall     : 100.0%
Risk Flagging F1         : 100.0%
Clause Segmentation      : 100.0%
Simplification           : 100.0%

Deployment ready         : ✅ YES
```

Run it yourself:
```bash
python tests/test_accuracy.py
```

---

## 🏗️ System Architecture

```
User uploads PDF / image / text
         │
         ▼
┌─────────────────────┐
│   Text Extractor    │  ← pdfminer.six + Tesseract OCR
│   + File Validator  │  ← magic bytes, size, type checks
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Clause Segmenter   │  ← 4-strategy waterfall (numbered → lettered → WHEREAS → sentences)
└─────────┬───────────┘
          │
     ┌────┴────────────┐
     ▼                 ▼                  ▼
┌──────────┐   ┌──────────────┐   ┌──────────────┐
│Risk Flag │   │  Simplifier  │   │  (Phase 2)   │
│30+ rules │   │ 80+ patterns │   │ InLegalBERT  │
│3-layer   │   │ jargon→plain │   │ RAG + Ollama │
└────┬─────┘   └──────┬───────┘   └──────┬───────┘
     └────────────────┴───────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  FastAPI REST   │  ← Rate limited, security headers
              │  + SQLAlchemy   │  ← Auto privacy wipe after 5 min
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ HTML/CSS/JS UI  │  ← Drag-drop, clause cards, risk colours
              └─────────────────┘
```

---

## 🛠️ Tech Stack

**Backend**
- Python 3.10+, FastAPI, SQLAlchemy (SQLite dev / PostgreSQL prod)
- spaCy `en_core_web_sm` — clause segmentation
- pdfminer.six + Tesseract OCR — document ingestion
- Custom 3-layer risk engine — 30+ Indian legal rules with confidence scoring

**Security & Reliability**
- Rate limiting (10 req/min/IP) via custom middleware
- File validation by magic bytes — cannot be spoofed by renaming
- Auto document deletion — raw text wiped within 5 min (privacy-first)
- Global exception handlers — no stack traces exposed to users
- Security headers — X-Frame-Options, X-Content-Type-Options, HSTS

**AI/ML** *(Phase 2 — in progress)*
- `law-ai/InLegalBERT` — pre-trained on Indian legal corpora
- FAISS vector store for clause retrieval
- Mistral-7B via Ollama (local, no API key required)
- LangChain for RAG pipeline orchestration

**Frontend**
- Vanilla HTML/CSS/JS — no framework dependency, no build step
- Drag-and-drop upload with animated progress
- Clause cards with Plain English / Original tab toggle
- Risk colour bands (red / amber / green) and action checklist

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/adharaai.git
cd adharaai

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download spaCy model
python -m spacy download en_core_web_sm

# 5. Run accuracy tests (should show 100% across all metrics)
python tests/test_accuracy.py

# 6. Start the server
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the UI or `http://127.0.0.1:8000/docs` for the API explorer.

---

## 📁 Project Structure

```
adharaai/
├── main.py                          # App entry point
├── config.py                        # Centralised settings from .env
├── requirements.txt
├── render.yaml                      # One-click Render.com deployment
│
├── backend/
│   ├── middleware/
│   │   └── security.py              # Rate limiting + security headers
│   ├── routers/
│   │   ├── upload.py                # POST /api/upload
│   │   ├── analyze.py               # POST /api/analyze/{id}
│   │   ├── documents.py             # GET /api/documents
│   │   └── health.py                # GET /health
│   ├── services/
│   │   ├── text_extractor.py        # PDF + OCR + file validation
│   │   ├── clause_segmenter.py      # 4-strategy clause detection
│   │   ├── risk_flagger.py          # 30+ Indian legal rules, 3-layer engine
│   │   └── simplifier.py            # 80+ jargon substitutions
│   └── models/
│       └── database.py              # SQLAlchemy models + privacy wipe
│
├── frontend/
│   ├── index.html                   # Full UI (drag-drop, clause cards, risk panel)
│   └── privacy.html                 # Privacy policy page
│
├── tests/
│   └── test_accuracy.py             # Full accuracy test suite (run before deploy)
│
└── data/                            # Put legal document samples here
```

---

## 🗺️ Roadmap

- [x] Phase 1 — Core pipeline (OCR → segmentation → risk rules → API)
- [x] Phase 1 — Frontend with drag-and-drop, clause cards, action checklist
- [x] Phase 1 — Production hardening (rate limiting, privacy, security headers)
- [x] Phase 1 — 100% accuracy on test suite
- [ ] Phase 2 — Fine-tune InLegalBERT for clause classification
- [ ] Phase 2 — RAG pipeline with Mistral-7B via Ollama
- [ ] Phase 3 — Hindi / Kannada language support
- [ ] Phase 3 — PDF export with annotated highlights
- [ ] Phase 4 — Mobile app (React Native)

---

## 👥 Team

| Member | Role |
|---|---|
| **Sudeep Nayak** (Lead) | ML Lead — risk engine, InLegalBERT fine-tuning |
| P2 | NLP Engineer — RAG pipeline, Ollama integration |
| P3 | Data Engineer — OCR pipeline, dataset collection |
| P4 | Backend Developer — FastAPI, database, model serving |
| P5 | Frontend Developer — UI, clause viewer, action checklist |

*4th Semester — B.E. Artificial Intelligence & Machine Learning, Mangaluru*

---

## 📊 Dataset Sources

| Dataset | Description |
|---|---|
| [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) | 5.4M paragraphs from Indian SC/HC judgments |
| [ILDC](https://github.com/Exploration-Lab/ILDC) | Indian Legal Document Corpus with summaries |
| [OpenNyAI](https://github.com/OpenNyAI) | Indian legal NLP tasks — UNDP funded |
| Custom collected | 200+ Karnataka rental agreements and court notices |

---

## 🤝 Contributing

This is an active student research project. Contributions welcome — especially Indian legal document samples and additional risk rule patterns.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/hindi-support`
3. Commit: `git commit -m 'Add Hindi language detection'`
4. Push: `git push origin feature/hindi-support`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [OpenNyAI](https://opennyai.org) for Indian legal NLP datasets
- [law-ai](https://huggingface.co/law-ai) for InLegalBERT
- Anthropic Claude for development assistance

---

<div align="center">
Built with ❤️ in Mangaluru, Karnataka 🇮🇳<br/>
<em>Your foundation. Your rights.</em>
</div>
