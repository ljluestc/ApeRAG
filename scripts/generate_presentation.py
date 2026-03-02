#!/usr/bin/env python3
"""Generate technical presentation PowerPoint for the ApeRAG platform."""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
import os

# ── Colors ──────────────────────────────────────────────────
BLUE = RGBColor(0x22, 0x63, 0xEB)
DARK = RGBColor(0x1A, 0x1A, 0x2E)
GRAY = RGBColor(0x4A, 0x55, 0x68)
LIGHT_BG = RGBColor(0xF8, 0xF9, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
ORANGE = RGBColor(0xEA, 0x58, 0x0C)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)


def bg(slide, color=LIGHT_BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def bar(slide, title, subtitle=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.4))
    shape.fill.solid()
    shape.fill.fore_color.rgb = BLUE
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.8)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = WHITE
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(16)
        p2.font.color.rgb = RGBColor(0xBF, 0xDB, 0xFE)


def txt(s, l, t, w, h, text, sz=18, c=DARK, b=False):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(sz)
    p.font.color.rgb = c
    p.font.bold = b


def bul(s, l, t, w, h, items, sz=15, c=DARK):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"\u2022  {item}"
        p.font.size = Pt(sz)
        p.font.color.rgb = c
        p.space_after = Pt(5)


def box(s, l, t, w, h, title, body, border=BLUE):
    shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = WHITE
    shape.line.color.rgb = border
    shape.line.width = Pt(1.5)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.15)
    tf.margin_top = Inches(0.1)
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = BLUE
    if body:
        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.size = Pt(11)
        p2.font.color.rgb = GRAY


# ═══════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s, BLUE)
txt(s, 1.5, 1.2, 10, 1.2, "ApeRAG", 48, WHITE, True)
txt(s, 1.5, 2.4, 10, 0.8, "Production-Ready RAG Platform with Graph RAG, Hybrid Retrieval & AI Agents", 22, RGBColor(0xBF, 0xDB, 0xFE))
txt(s, 1.5, 3.6, 10, 0.5, "Graph RAG  \u2022  Vector + Full-text  \u2022  MCP  \u2022  Knowledge Graphs  \u2022  Multi-LLM", 16, RGBColor(0x93, 0xC5, 0xFD))
txt(s, 1.5, 4.8, 6, 0.5, "Jiale Lin", 20, WHITE, True)
txt(s, 1.5, 5.3, 8, 0.4, "jeremykalilin@gmail.com  \u2022  linkedin.com/in/jiale-lin-ab03a4149", 14, RGBColor(0x93, 0xC5, 0xFD))
txt(s, 1.5, 6.0, 8, 0.4, "github.com/ljluestc/ApeRAG  \u2022  Technical Presentation \u2014 25 min", 13, RGBColor(0x93, 0xC5, 0xFD))

# ═══════════════════════════════════════════════════════════
# SLIDE 2 — About Me
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "About Me", "Jiale Lin \u2014 Introduction")
txt(s, 0.8, 1.8, 5.5, 0.5, "Background", 22, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.5, [
    "M.S. Computer Science \u2014 University of Colorado Boulder",
    "B.S. Mathematics (CS) \u2014 University of Arizona",
    "Staff SWE at Aviatrix: distributed backend, multi-cloud networking",
    "RAG retrieval + grounding (LangChain/LlamaIndex, Pinecone/FAISS/Chroma)",
    "Agentic orchestration: LangGraph, tool calling, audit trails",
    "LLMOps: offline eval, release gates, canary rollouts, MLflow",
    "Platform: Kubernetes, Terraform, ArgoCD, Prometheus/Grafana",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Contributions to ApeRAG", 22, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.5, [
    "Bug fixes: null-safety in query.py, ValueError formatting",
    "Typo fix: MEMOTY \u2192 MEMORY with backward-compat alias",
    "22 new unit tests (query models, connector adaptor, prompts)",
    "Technical presentation (PPTX + PDF)",
    "Code review of hybrid retrieval, chunking, LLM integration",
    "Context engineering and RAG grounding analysis",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 3 — Problem Statement
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "The Problem", "Why a production RAG platform?")
txt(s, 0.8, 1.8, 11, 0.8, "Enterprise knowledge is trapped in documents, graphs, and databases.\nLLMs hallucinate without retrieval grounding. Context engineering is hard.", 17)
box(s, 0.8, 3.0, 3.6, 1.8, "Multi-Source Knowledge", "Docs, PDFs, code, graphs, images.\nNo single retrieval method\ncovers all modalities.")
box(s, 4.8, 3.0, 3.6, 1.8, "Hallucination Risk", "Pure LLMs fabricate answers.\nNeed grounded retrieval +\ncitation for trust.")
box(s, 8.8, 3.0, 3.6, 1.8, "Production Gaps", "Most RAG demos are toys.\nNeed auth, rate limits, MCP,\nK8s deploy, monitoring.")
txt(s, 0.8, 5.3, 11, 0.8, "ApeRAG\u2019s answer: Graph RAG + Vector + Full-text hybrid retrieval with\nMCP integration, AI agents, and enterprise-grade management.", 15, GRAY)

# ═══════════════════════════════════════════════════════════
# SLIDE 4 — Architecture
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "System Architecture", "End-to-end RAG pipeline")
stages = [
    ("Document\nIngestion", "Markdown, PDF, images\nMinerU parsing\nSmart chunking"),
    ("Embedding\nGeneration", "Sentence-transformers\nMultimodal support\nBatch processing"),
    ("Index\nBuilding", "Vector (Qdrant/PGVector)\nFull-text (Elasticsearch)\nGraph (Neo4j/NebulaGraph)"),
    ("Hybrid\nRetrieval", "Vector + BM25 + Graph\nRe-ranking cascade\nSummary + Vision"),
    ("LLM\nGeneration", "OpenAI, Anthropic\nDashScope, Qianfan\nLocal models (LiteLLM)"),
    ("AI Agent\nOrchestration", "MCP tool calling\nMulti-collection search\nWeb search fallback"),
    ("API +\nFrontend", "FastAPI + Next.js\nAuth, rate limits\nAdmin dashboard"),
]
x = 0.3
for t, b in stages:
    box(s, x, 2.0, 1.65, 2.2, t, b)
    x += 1.8
txt(s, 0.8, 4.8, 11, 0.5, "Infrastructure", 18, BLUE, True)
bul(s, 0.8, 5.3, 11, 1.5, [
    "Celery task queue for async document processing + background retraining",
    "Redis caching + broker, PostgreSQL persistence, Alembic migrations",
    "Docker Compose dev environment, Helm chart for production Kubernetes deploy",
], 14)

# ═══════════════════════════════════════════════════════════
# SLIDE 5 — Document Parsing & Chunking
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Document Parsing & Chunking", "Intelligent document processing pipeline")
txt(s, 0.8, 1.8, 5.5, 0.5, "Parsing", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "KubernetesDocProcessor: markdown-aware chunking",
    "MinerU integration: complex PDFs, tables, formulas",
    "MarkItDown: Office docs, images, audio transcription",
    "Q&A pair extraction from documentation",
    "Source type inference: runbooks, incidents, configs",
    "Multimodal: vision support for charts/images",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Smart Chunking (Rechunker)", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Heading-aware grouping (H1\u2192H6 hierarchy)",
    "Merge consecutive title groups into content groups",
    "Token-based chunk size control (configurable 400 default)",
    "SimpleSemanticSplitter: hierarchical separator cascade",
    "Overlap support for context preservation",
    "Markdown + PDF source map tracking per chunk",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 6 — Index Types
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Five Index Types", "Multi-dimensional document understanding")
box(s, 0.5, 2.0, 2.3, 2.5, "Vector",
    "Qdrant / PGVector\nSentence-transformers\nCosine similarity ANN\nHigh semantic recall")
box(s, 3.0, 2.0, 2.3, 2.5, "Full-text",
    "Elasticsearch\nBM25 lexical matching\nExact term recall\nKeyword extraction")
box(s, 5.5, 2.0, 2.3, 2.5, "Graph",
    "Neo4j / NebulaGraph\nLightRAG with entity\nnormalization + merging\nRelational reasoning")
box(s, 8.0, 2.0, 2.3, 2.5, "Summary",
    "Document-level\nsummary generation\nBroad question\nunderstanding")
box(s, 10.5, 2.0, 2.3, 2.5, "Vision",
    "Image/chart analysis\nMultimodal embeddings\nVisual content QA\nOCR integration")
txt(s, 0.8, 5.0, 11, 1.0,
    "Hybrid retrieval: system queries multiple index types in parallel, merges and re-ranks results.\n"
    "Each index type captures different signals \u2014 combining them yields higher recall + precision.", 15, GRAY)

# ═══════════════════════════════════════════════════════════
# SLIDE 7 — Graph RAG
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Enhanced Graph RAG", "LightRAG with entity normalization")
txt(s, 0.8, 1.8, 5.5, 0.5, "Knowledge Graph Construction", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "Entity extraction from document chunks via LLM",
    "Entity normalization: merge equivalent entities",
    "Relationship extraction with typed edges",
    "Stored in Neo4j or NebulaGraph",
    "Graph visualization in admin UI",
    "Context types: local, global, hybrid queries",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Why Graph RAG?", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Captures relationships between entities across docs",
    "Multi-hop reasoning: A \u2192 B \u2192 C chains",
    "Entity normalization prevents duplicate nodes",
    "Complements vector search for structural queries",
    "LightRAG: efficient graph construction at scale",
    "KG + vector mix prompt templates (EN/ZH)",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 8 — LLM Integration
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Multi-Provider LLM Integration", "LiteLLM-based universal routing")
txt(s, 0.8, 1.8, 5.5, 0.5, "Supported Providers", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "OpenAI: GPT-4o, GPT-4o-mini, GPT-3.5-turbo",
    "Anthropic: Claude Sonnet 4, Claude Haiku 4.5",
    "Alibaba DashScope: Qwen models",
    "Baidu Qianfan: ERNIE series",
    "LiteLLM unified interface: 100+ models",
    "Hot-swap at runtime via configuration",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "RAG Prompt Engineering", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Bilingual prompt templates (EN + ZH)",
    "3-step workflow: classify \u2192 strategy \u2192 generate",
    "Knowledge Graph + Vector mix prompts",
    "Memory-aware prompts for multi-turn conversations",
    "Keyword extraction prompts for BM25 augmentation",
    "20+ role-based prompt templates (finance, code, etc.)",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 9 — AI Agents & MCP
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "AI Agents & MCP Integration", "Autonomous search and reasoning")
txt(s, 0.8, 1.8, 5.5, 0.5, "Agent Architecture", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "AgentSessionManager: lifecycle management",
    "AgentEventListener: real-time event streaming",
    "Tool calling with allowlists and approvals",
    "Multi-collection search across knowledge bases",
    "Web search fallback (DuckDuckGo/trafilatura)",
    "Flow orchestration for complex workflows",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "MCP (Model Context Protocol)", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Streamable HTTP transport (stateless)",
    "Collection browsing: list + explore knowledge",
    "Hybrid search: vector + full-text + graph",
    "Natural language querying with citations",
    "Bearer token auth for API key security",
    "Compatible with Claude, OpenAI, and others",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 10 — Security & Auth
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Security & Authentication", "Enterprise-grade access control")
txt(s, 0.8, 1.8, 5.5, 0.5, "Auth Providers", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "JWT-based authentication (configurable secret)",
    "Google OAuth (client ID/secret)",
    "GitHub OAuth integration",
    "Auth0 / Authing / Logto SSO support",
    "API key management for programmatic access",
    "Configurable register_mode: unlimited/restricted",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Operational Security", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Rate limiting per user/IP",
    "Audit logging for all operations",
    "CORS middleware configuration",
    "Pydantic v2 input validation on all endpoints",
    "Environment-based secrets (.env, never committed)",
    "Concurrent access control with Redis locks",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 11 — Observability
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Observability & Tracing", "OpenTelemetry + Jaeger + Opik")
txt(s, 0.8, 1.8, 5.5, 0.5, "OpenTelemetry Integration", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 3.0, [
    "Auto-instrumented FastAPI + SQLAlchemy",
    "MCP operation tracing",
    "Jaeger exporter for distributed tracing",
    "Console exporter for development",
    "Configurable per-component enable/disable",
    "Service name + version in all spans",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Evaluation & Tracking", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 3.0, [
    "Opik integration for RAG evaluation",
    "Ragas metrics: relevance, faithfulness, coverage",
    "LiteLLM token tracking + cache management",
    "Celery task monitoring (Flower dashboard)",
    "Health check endpoints for container probes",
    "Audit trail for all user + system actions",
])

# ═══════════════════════════════════════════════════════════
# SLIDE 12 — Deployment
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Deployment Options", "Docker Compose \u2192 Kubernetes production")
box(s, 0.8, 2.0, 3.6, 2.0, "Docker Compose (Dev)",
    "docker-compose up -d\nPostgres, Redis, Qdrant, ES\nOptional: Neo4j, Jaeger, DocRay\nGPU acceleration support")
box(s, 4.8, 2.0, 3.6, 2.0, "Kubernetes (Production)",
    "Helm chart: deploy/aperag/\nKubeBlocks for databases\nHigh availability + scaling\nIngress + TLS ready")
box(s, 8.8, 2.0, 3.6, 2.0, "CI/CD & Build",
    "Multi-platform Docker build\namd64 + arm64 support\nMakefile automation\nGit hooks + pre-commit")
box(s, 0.8, 4.5, 5.5, 1.8, "Database Stack",
    "PostgreSQL (pgvector): primary store + vector embeddings\n"
    "Redis: cache, Celery broker, distributed locks\n"
    "Qdrant: high-performance vector search\n"
    "Elasticsearch: full-text search + BM25\n"
    "Neo4j/NebulaGraph: knowledge graph storage")
box(s, 7.0, 4.5, 5.5, 1.8, "App Services",
    "FastAPI backend: API + MCP + WebSocket\n"
    "Next.js frontend: React admin UI\n"
    "Celery workers: async document processing\n"
    "Celery beat: scheduled tasks\n"
    "Flower: task monitoring dashboard")

# ═══════════════════════════════════════════════════════════
# SLIDE 13 — Tech Stack
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Technology Stack", "Production-grade open-source tools")
box(s, 0.8, 2.0, 3.6, 2.0, "Backend",
    "Python 3.11, FastAPI, uvicorn\nPydantic v2, SQLAlchemy 2.0\nAlembic migrations\nCelery + Redis broker")
box(s, 4.8, 2.0, 3.6, 2.0, "AI / ML",
    "LangChain, LlamaIndex\nLiteLLM (100+ models)\nSentence-transformers\nLightRAG (Graph RAG)")
box(s, 8.8, 2.0, 3.6, 2.0, "Frontend",
    "Next.js + React\nTypeScript, Tailwind CSS\nAdmin dashboard\nGraph visualization")
box(s, 0.8, 4.5, 3.6, 1.8, "Databases",
    "PostgreSQL + pgvector\nRedis 4.x (cache + broker)\nQdrant (vector search)\nElasticsearch (full-text)")
box(s, 4.8, 4.5, 3.6, 1.8, "Observability",
    "OpenTelemetry + Jaeger\nOpik (RAG evaluation)\nFlower (Celery monitoring)\nRagas metrics")
box(s, 8.8, 4.5, 3.6, 1.8, "DevOps",
    "Docker + Docker Compose\nHelm chart + KubeBlocks\nMakefile automation\nRuff linter + mypy")

# ═══════════════════════════════════════════════════════════
# SLIDE 14 — My Fixes
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "My Contributions", "Bug fixes, tests, and documentation")
txt(s, 0.8, 1.8, 5.5, 0.5, "Bug Fixes", 20, BLUE, True)
bul(s, 0.8, 2.3, 5.5, 2.5, [
    "query.py: get_packed_answer crashed on None metadata/text",
    "  \u2192 Added null-safe fallbacks (r.text or '', r.metadata or {})",
    "connector.py: ValueError('msg', var) \u2192 f-string formatting",
    "  \u2192 Error messages now readable, not tuple repr",
    "prompts.py: Typo MEMOTY \u2192 MEMORY with backward-compat alias",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "New Tests (22 tests)", 20, BLUE, True)
bul(s, 7.0, 2.3, 5.5, 2.5, [
    "DocumentWithScore: defaults, values, serialization roundtrip",
    "Query/QueryWithEmbedding: defaults, custom top_k, embedding",
    "get_packed_answer: basic, URL prefix, limit_length, None safety",
    "VectorStoreConnectorAdaptor: error message format validation",
    "Prompts: backward-compat alias, same-object identity check",
])
txt(s, 0.8, 5.2, 11, 1.0,
    "All fixes are regression-safe: new tests verify the fix prevents the original crash.\n"
    "Backward-compatible alias ensures existing code importing MEMOTY still works.", 15, GRAY)

# ═══════════════════════════════════════════════════════════
# SLIDE 15 — Takeaways & Q&A
# ═══════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
bg(s)
bar(s, "Key Takeaways & Q\u200a&\u200aA", "Lessons learned")
txt(s, 0.8, 1.8, 5.5, 0.5, "Why ApeRAG Stands Out", 20, BLUE, True)
bul(s, 0.8, 2.4, 5.5, 2.5, [
    "5 index types: no single retrieval method is sufficient",
    "Graph RAG: entity normalization for clean knowledge graphs",
    "MCP integration: AI assistants access your knowledge directly",
    "Production-ready: auth, rate limits, audit, K8s deploy",
    "Bilingual (EN/ZH): prompts, UI, and documentation",
])
txt(s, 7.0, 1.8, 5.5, 0.5, "Design Principles", 20, BLUE, True)
bul(s, 7.0, 2.4, 5.5, 2.5, [
    "Hybrid > single: combine vector + BM25 + graph + summary + vision",
    "Grounding first: always retrieve before generating",
    "Defense in depth: auth, validation, rate limits, audit",
    "Observable: OpenTelemetry, Jaeger, Opik, Flower",
    "Developer-friendly: Makefile, docker-compose, Helm, tests",
])
txt(s, 0.8, 5.3, 11, 1.0,
    "Thank you!\n\n"
    "Jiale Lin  \u2022  jeremykalilin@gmail.com  \u2022  github.com/ljluestc/ApeRAG\n"
    "3 bug fixes  \u2022  22 new tests  \u2022  15-slide presentation  \u2022  5 index types  \u2022  MCP + AI Agents", 16)

# ═══════════════════════════════════════════════════════════
# Save
# ═══════════════════════════════════════════════════════════
out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(out_dir, exist_ok=True)
pptx_path = os.path.join(out_dir, "ApeRAG_Technical_Presentation.pptx")
prs.save(pptx_path)
print(f"Saved PPTX: {pptx_path}")
