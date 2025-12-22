# RiskSafeAI - Quick Start Guide

## 🎯 Prerequisites

Before you start, ensure you have:

1. **Python 3.9+** installed
2. **Pinecone vector database** with ASIC documents (already populated, 3072D embeddings)
3. **API Keys:**
   - OpenAI API Key → https://platform.openai.com/api-keys
   - Pinecone API Key → https://app.pinecone.io/
   - Tavily API Key → https://tavily.com/

---

## 🚀 Local Setup (5 Minutes)

### Step 1: Configure API Keys

```bash
# Copy template
copy .env.example .env

# Edit .env file and add your API keys
notepad .env
```

**Add to `.env`:**
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
PINECONE_API_KEY=pcsk_xxxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxx
```

### Step 2: Run Quick Start Script

**Windows:**
```bash
quick_start.bat
```

**Mac/Linux:**
```bash
chmod +x quick_start.sh
./quick_start.sh
```

This will:
- ✅ Create virtual environment
- ✅ Install dependencies
- ✅ Test Pinecone connection
- ✅ Start server at http://localhost:8000

### Step 3: Test the API

**Open new terminal and run:**

```bash
# Test health
curl http://localhost:8000/health

# Test ReAct agent
curl -X POST http://localhost:8000/react/obligation_register \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Generate obligation register for fintech personal loans\"}"
```

---

## 🧪 Automated Testing

**Run test suite:**

```bash
# Test local deployment
python test_deployment.py

# Test AWS deployment
python test_deployment.py http://your-alb-url.elb.amazonaws.com
```

**Expected output:**
```
✅ PASS | Pinecone Connection
✅ PASS | OpenAI API Key
✅ PASS | Tavily API Key
✅ PASS | Health Endpoint (Local)
✅ PASS | ReAct Agent (Local)

Results: 5/5 tests passed
🎉 All tests passed! RiskSafeAI is ready to use.
```

---

## 📡 API Endpoints

### 1. Health Check
```http
GET /health
```

**Response:**
```json
{"status": "ok"}
```

### 2. Generate Obligation Register (ReAct Agent)
```http
POST /react/obligation_register
Content-Type: application/json

{
  "query": "Generate obligation register for fintech personal loans business"
}
```

**Response:**
```json
{
  "answer": "# Compliance Obligation Register\n\n## Executive Summary\n...",
  "metadata": {
    "iterations": 6,
    "chunks_retrieved": 85,
    "regulators_covered": ["ASIC"],
    "grounding_score": 0.92,
    "confidence": 0.88,
    "completeness_checked": true,
    "citations_validated": true,
    "warnings": [],
    "errors": []
  }
}
```

---

## 🐳 AWS Deployment

**For detailed AWS deployment guide, see:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

**Quick AWS Deploy:**

```bash
# 1. Build Docker image
docker build -t risksafeai:latest .

# 2. Push to AWS ECR
# (See DEPLOYMENT_GUIDE.md for detailed steps)

# 3. Deploy to ECS Fargate
aws ecs create-service ...

# 4. Test AWS endpoint
python test_deployment.py http://your-alb-url.elb.amazonaws.com
```

---

## 🔍 How It Works

### ReAct Agent Workflow

```
User Query: "Generate obligation register for fintech lending"
    │
    ├─> ITERATION 1
    │   ├─> 💭 THINK: "Need ASIC licensing requirements"
    │   ├─> ⚡ ACT: rag_search("Australian credit license")
    │   └─> 👁️ OBSERVE: Retrieved 20 chunks
    │
    ├─> ITERATION 2
    │   ├─> 💭 THINK: "Need disclosure obligations"
    │   ├─> ⚡ ACT: rag_search("ASIC disclosure obligations")
    │   └─> 👁️ OBSERVE: Retrieved 18 chunks
    │
    ├─> ITERATION 3
    │   ├─> 💭 THINK: "Need conduct obligations"
    │   ├─> ⚡ ACT: rag_search("responsible lending conduct")
    │   └─> ��️ OBSERVE: Retrieved 15 chunks
    │
    ├─> ITERATION 4
    │   ├─> 💭 THINK: "Have enough data, check completeness"
    │   ├─> ⚡ ACT: completeness_check("fintech lending")
    │   └─> 👁️ OBSERVE: All ASIC areas covered ✓
    │
    ├─> ITERATION 5
    │   ├─> 💭 THINK: "Validate citations"
    │   ├─> ⚡ ACT: validate_citations()
    │   └─> 👁️ OBSERVE: Grounding score 0.92 ✓
    │
    └─> ITERATION 6
        ├─> 💭 THINK: "Ready to finalize"
        ├─> ⚡ ACT: finalize_answer()
        └─> 👁️ OBSERVE: Generated comprehensive obligation register ✓
```

### Available Tools

1. **RAG Search** - Query Pinecone for ASIC documents
2. **Completeness Check** - Verify all regulators covered
3. **Web Search** - Verify info from asic.gov.au (Tavily)
4. **Citation Validation** - Check grounding & citations
5. **Answer Generation** - Create comprehensive register

---

## 📊 Example Output

**Query:**
```
"Generate obligation register for fintech personal loans"
```

**Answer (Markdown):**
```markdown
# Compliance Obligation Register

## Executive Summary
- Total Obligations: 28
- Critical Priority: 8
- High Priority: 12
- Medium Priority: 6
- Low Priority: 2
- Estimated Total Cost: AUD $150,000 - $250,000
- Estimated Total Time: 6-12 months

## ASIC (Australian Securities and Investments Commission)

### 1. Obtain Australian Credit License (ACL)
**Priority:** Critical
**Deadline:** Before commencing credit activities
**Cost Estimate:** AUD $50,000 - $100,000
**Time Estimate:** 3-6 months
**Penalty:** Maximum penalty of AUD $2.22 million or imprisonment

**Description:**
All businesses engaging in credit activities must hold an Australian Credit License...

**Citation:**
[Source: National Consumer Credit Protection Act 2009, Section 29]

**Detailed Explanation:**
The National Consumer Credit Protection Act 2009 (NCCP Act) requires...

**Dependencies:**
- Company registration
- Compliance framework
- Internal dispute resolution system

---

### 2. Responsible Lending Obligations
**Priority:** Critical
**Deadline:** Ongoing
...
```

---

## ⚙️ Configuration

**Main config file:** `compliance_chat/config/config.yaml`

```yaml
embedding_model:
  provider: "openai"
  model_name: "text-embedding-3-large"

pinecone:
  index_name: "asic-compliance-rag"  # ← Your index name
  dimension: 3072
  metric: "dotproduct"

react_agent:
  max_iterations: 10
  temperature: 0
  llm_model: "gpt-4o"
```

**Customize:**
- `max_iterations`: Max ReAct loops (default: 10)
- `index_name`: Your Pinecone index name
- `llm_model`: OpenAI model (gpt-4o, gpt-4-turbo, etc.)

---

## 🐛 Troubleshooting

### Issue: "Pinecone connection failed"

**Check:**
```bash
python -c "from pinecone import Pinecone; import os; from dotenv import load_dotenv; load_dotenv(); print(Pinecone(api_key=os.getenv('PINECONE_API_KEY')).Index('asic-compliance-rag').describe_index_stats())"
```

**Fix:**
- Verify `PINECONE_API_KEY` in `.env`
- Check index name matches `config.yaml`

### Issue: "0 chunks retrieved"

**Causes:**
- Pinecone index is empty
- Wrong index name
- Regulator metadata doesn't match "ASIC"

**Fix:**
```python
# Check Pinecone index
from pinecone import Pinecone
pc = Pinecone(api_key="your-key")
index = pc.Index("asic-compliance-rag")
stats = index.describe_index_stats()
print(f"Vectors: {stats.total_vector_count}")  # Should be > 0

# Test query
results = index.query(
    vector=[0.1]*3072,
    top_k=5,
    include_metadata=True
)
for match in results.matches:
    print(f"Regulator: {match.metadata.get('regulator')}")  # Should be "ASIC"
```

### Issue: "Health check fails"

**Check server is running:**
```bash
curl http://localhost:8000/health
```

**Check logs:**
```bash
# Look for errors in terminal where server is running
```

---

## 💰 Costs (Approximate)

### Per 1 Request (Typical fintech query)

| Service | Usage | Cost |
|---------|-------|------|
| OpenAI Embeddings | ~50 queries × 512 tokens | $0.003 |
| OpenAI LLM | ~6 iterations × 2K tokens | $0.015 |
| Tavily Search | 0-1 searches | $0.001 |
| Pinecone | Queries (free tier) | $0 |
| **Total per request** | | **~$0.02** |

### Monthly (100 requests/day)

| Component | Cost |
|-----------|------|
| API Costs (100 req/day × 30 days) | ~$60 |
| AWS Infrastructure (ECS + ALB) | ~$55 |
| **Total per month** | **~$115** |

---

## 📚 Additional Resources

- **Full Deployment Guide:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Alignment Documentation:** [README_ALIGNMENT.md](README_ALIGNMENT.md)
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/
- **ReAct Paper:** https://arxiv.org/abs/2210.03629

---

## ✅ Next Steps

1. ✅ Run local server (`quick_start.bat`)
2. ✅ Test with example queries
3. ✅ Review generated obligation registers
4. ✅ Deploy to AWS (see DEPLOYMENT_GUIDE.md)
5. ✅ Monitor costs and performance
6. ✅ Scale as needed

---

## 🎉 You're Ready!

RiskSafeAI is now fully aligned with compliance_project and ready to generate comprehensive Australian compliance obligation registers using the ReAct agent architecture.

**Start the server and try it out!**

```bash
quick_start.bat
```

Then in another terminal:

```bash
curl -X POST http://localhost:8000/react/obligation_register \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Generate obligation register for fintech personal loans\"}"
```

**Last Updated:** December 2025
