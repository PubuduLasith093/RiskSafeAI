# RiskSafeAI - Local & AWS Deployment Guide

## 🎯 Overview

This guide covers:
1. **Local Development** - Run RiskSafeAI on your machine
2. **AWS Deployment** - Deploy to AWS ECS/Fargate with ALB
3. **Testing** - Verify the ReAct agent works correctly

**Note:** This setup assumes your Pinecone vector database is already populated with ASIC compliance documents (no document upload needed).

---

## 📋 Prerequisites

### Required
- ✅ Python 3.9+ installed
- ✅ Pinecone vector database with ASIC documents (3072D embeddings)
- ✅ API Keys:
  - OpenAI API Key
  - Pinecone API Key
  - Tavily API Key
- ✅ AWS Account (for deployment)
- ✅ Docker installed (for AWS deployment)

---

## 🚀 Part 1: Local Development

### Step 1: Clone/Navigate to Project

```bash
cd "D:\Deltone Solutions\scraping\RiskSafeAI"
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
# source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed langgraph-0.2.x langchain-openai-0.2.10 tavily-python-0.3.x ...
```

### Step 4: Configure Environment Variables

```bash
# Copy template
copy .env.example .env

# Edit .env file
notepad .env
```

**Add your API keys to `.env`:**
```env
# API Keys
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
PINECONE_API_KEY=pcsk_xxxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxx

# Configuration
ENV=local
LLM_PROVIDER=openai
PORT=8000
```

### Step 5: Verify Pinecone Index

**Check your Pinecone index name in `config.yaml`:**
```yaml
pinecone:
  index_name: "asic-compliance-rag"  # ← Must match your existing index
  dimension: 3072
  metric: "dotproduct"
```

**Test Pinecone connection:**
```python
# test_pinecone.py
import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index("asic-compliance-rag")

stats = index.describe_index_stats()
print(f"✅ Index connected!")
print(f"   Total vectors: {stats.total_vector_count:,}")
print(f"   Dimension: {stats.dimension}")
```

Run test:
```bash
python test_pinecone.py
```

**Expected output:**
```
✅ Index connected!
   Total vectors: 17,105
   Dimension: 3072
```

### Step 6: Run Local Server

```bash
python main.py
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 7: Test the API

**Open browser:** http://localhost:8000

**Test health endpoint:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{"status": "ok"}
```

**Test ReAct Agent:**
```bash
curl -X POST http://localhost:8000/react/obligation_register \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Generate obligation register for fintech personal loans business\"}"
```

**Expected response:**
```json
{
  "answer": "# Compliance Obligation Register\n\n## Executive Summary\n...",
  "metadata": {
    "iterations": 6,
    "chunks_retrieved": 85,
    "regulators_covered": ["ASIC"],
    "grounding_score": 0.92,
    "confidence": 0.88
  }
}
```

---

## 🐳 Part 2: AWS Deployment

### Architecture Overview

```
Internet
    │
    ├─> ALB (Load Balancer)
    │      │
    │      ├─> ECS Service (Fargate)
    │      │      │
    │      │      └─> Task (RiskSafeAI Container)
    │      │             │
    │      │             ├─> OpenAI API
    │      │             ├─> Pinecone
    │      │             └─> Tavily
    │
    └─> CloudWatch Logs
```

### Step 1: Create Dockerfile

**Create `Dockerfile` in project root:**

```dockerfile
# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run application
CMD ["python", "main.py"]
```

### Step 2: Create .dockerignore

**Create `.dockerignore`:**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
logs/

# Environment
.env
.env.local

# Git
.git/
.gitignore

# Documentation
*.md
docs/

# Tests
tests/
pytest_cache/

# Jupyter
*.ipynb
.ipynb_checkpoints/
```

### Step 3: Build & Test Docker Image Locally

```bash
# Build image
docker build -t risksafeai:latest .

# Run container locally
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="sk-proj-xxxxx" \
  -e PINECONE_API_KEY="pcsk-xxxxx" \
  -e TAVILY_API_KEY="tvly-xxxxx" \
  -e ENV="local" \
  risksafeai:latest

# Test
curl http://localhost:8000/health
```

### Step 4: Push to AWS ECR

```bash
# Install AWS CLI
# Download from: https://aws.amazon.com/cli/

# Configure AWS credentials
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1
# - Default output format: json

# Create ECR repository
aws ecr create-repository --repository-name risksafeai --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Tag image
docker tag risksafeai:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/risksafeai:latest

# Push image
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/risksafeai:latest
```

**Replace `YOUR_ACCOUNT_ID` with your AWS account ID (find it in AWS Console top-right)**

### Step 5: Store API Keys in AWS Secrets Manager

```bash
# Create secret for API keys
aws secretsmanager create-secret \
  --name risksafeai-api-keys \
  --description "API keys for RiskSafeAI" \
  --secret-string '{
    "OPENAI_API_KEY": "sk-proj-xxxxx",
    "PINECONE_API_KEY": "pcsk-xxxxx",
    "TAVILY_API_KEY": "tvly-xxxxx"
  }' \
  --region us-east-1
```

**Note the ARN from output - you'll need it later**

### Step 6: Create ECS Cluster

```bash
# Create ECS cluster
aws ecs create-cluster \
  --cluster-name risksafeai-cluster \
  --region us-east-1
```

### Step 7: Create Task Definition

**Create `ecs-task-definition.json`:**

```json
{
  "family": "risksafeai-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "risksafeai-container",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/risksafeai:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "ENV",
          "value": "production"
        },
        {
          "name": "PORT",
          "value": "8000"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:risksafeai-api-keys:OPENAI_API_KEY::"
        },
        {
          "name": "PINECONE_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:risksafeai-api-keys:PINECONE_API_KEY::"
        },
        {
          "name": "TAVILY_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:risksafeai-api-keys:TAVILY_API_KEY::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/risksafeai",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**Register task definition:**

```bash
# Create CloudWatch log group first
aws logs create-log-group --log-group-name /ecs/risksafeai --region us-east-1

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --region us-east-1
```

### Step 8: Create Application Load Balancer

```bash
# Create security group for ALB
aws ec2 create-security-group \
  --group-name risksafeai-alb-sg \
  --description "Security group for RiskSafeAI ALB" \
  --vpc-id vpc-xxxxx \
  --region us-east-1

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region us-east-1

# Create ALB
aws elbv2 create-load-balancer \
  --name risksafeai-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx \
  --scheme internet-facing \
  --type application \
  --region us-east-1

# Create target group
aws elbv2 create-target-group \
  --name risksafeai-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region us-east-1

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:xxxxx:loadbalancer/app/risksafeai-alb/xxxxx \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:xxxxx:targetgroup/risksafeai-tg/xxxxx \
  --region us-east-1
```

### Step 9: Create ECS Service

```bash
# Create security group for ECS tasks
aws ec2 create-security-group \
  --group-name risksafeai-ecs-sg \
  --description "Security group for RiskSafeAI ECS tasks" \
  --vpc-id vpc-xxxxx \
  --region us-east-1

# Allow traffic from ALB
aws ec2 authorize-security-group-ingress \
  --group-id sg-yyyyy \
  --protocol tcp \
  --port 8000 \
  --source-group sg-xxxxx \
  --region us-east-1

# Create ECS service
aws ecs create-service \
  --cluster risksafeai-cluster \
  --service-name risksafeai-service \
  --task-definition risksafeai-task:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx,subnet-yyyyy],securityGroups=[sg-yyyyy],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:xxxxx:targetgroup/risksafeai-tg/xxxxx,containerName=risksafeai-container,containerPort=8000" \
  --region us-east-1
```

### Step 10: Get ALB DNS Name

```bash
aws elbv2 describe-load-balancers \
  --names risksafeai-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region us-east-1
```

**Output:** `risksafeai-alb-123456789.us-east-1.elb.amazonaws.com`

---

## ✅ Part 3: Testing Deployment

### Test 1: Health Check

```bash
# Local
curl http://localhost:8000/health

# AWS
curl http://risksafeai-alb-123456789.us-east-1.elb.amazonaws.com/health
```

**Expected:**
```json
{"status": "ok"}
```

### Test 2: ReAct Agent Endpoint

```bash
# AWS
curl -X POST http://risksafeai-alb-123456789.us-east-1.elb.amazonaws.com/react/obligation_register \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Generate obligation register for fintech personal loans business"
  }'
```

**Expected response:**
```json
{
  "answer": "# Compliance Obligation Register\n\n## Executive Summary\n\nTotal Obligations: 28\n...",
  "metadata": {
    "iterations": 6,
    "chunks_retrieved": 85,
    "regulators_covered": ["ASIC"],
    "grounding_score": 0.92,
    "confidence": 0.88,
    "completeness_checked": true,
    "citations_validated": true
  }
}
```

### Test 3: Check Logs

```bash
# View CloudWatch logs
aws logs tail /ecs/risksafeai --follow --region us-east-1
```

### Test 4: Python Client

```python
import requests

# AWS endpoint
url = "http://risksafeai-alb-123456789.us-east-1.elb.amazonaws.com/react/obligation_register"

response = requests.post(url, json={
    "query": "Generate obligation register for Australian fintech lending business"
})

result = response.json()
print(f"Iterations: {result['metadata']['iterations']}")
print(f"Chunks: {result['metadata']['chunks_retrieved']}")
print(f"Score: {result['metadata']['grounding_score']}")
print(f"\nAnswer:\n{result['answer'][:500]}...")
```

---

## 📊 Monitoring & Logs

### View ECS Service Status

```bash
aws ecs describe-services \
  --cluster risksafeai-cluster \
  --services risksafeai-service \
  --region us-east-1
```

### View Task Status

```bash
aws ecs list-tasks \
  --cluster risksafeai-cluster \
  --service-name risksafeai-service \
  --region us-east-1
```

### View Logs in Real-time

```bash
aws logs tail /ecs/risksafeai --follow --region us-east-1
```

### CloudWatch Metrics

Navigate to: AWS Console → CloudWatch → Metrics → ECS

Monitor:
- CPU Utilization
- Memory Utilization
- Request Count
- Response Time

---

## 🔧 Troubleshooting

### Issue 1: Task Fails to Start

**Check logs:**
```bash
aws logs tail /ecs/risksafeai --since 10m --region us-east-1
```

**Common causes:**
- Missing API keys in Secrets Manager
- Wrong Pinecone index name
- Insufficient memory/CPU

### Issue 2: Health Check Failing

**Test manually:**
```bash
# Get task IP
aws ecs list-tasks --cluster risksafeai-cluster --service risksafeai-service --region us-east-1

# Get task details
aws ecs describe-tasks --cluster risksafeai-cluster --tasks arn:aws:ecs:us-east-1:xxxxx:task/xxxxx --region us-east-1

# SSH to bastion or use Session Manager
curl http://TASK_PRIVATE_IP:8000/health
```

### Issue 3: 0 Chunks Retrieved

**Check Pinecone connection:**
```python
# Add to logs in tools.py
print(f"Pinecone index stats: {self.pinecone_index.describe_index_stats()}")
```

**Verify:**
- Index name matches config
- API key is correct
- Vectors exist for regulator="ASIC"

### Issue 4: High Response Time

**Optimize:**
- Increase ECS task CPU/memory
- Enable auto-scaling
- Add CloudFront CDN

---

## 💰 Cost Estimation

### AWS Costs (Monthly)

| Service | Cost |
|---------|------|
| ECS Fargate (1 task, 1vCPU, 2GB RAM) | ~$30 |
| ALB | ~$20 |
| CloudWatch Logs (10GB/month) | ~$5 |
| ECR Storage (1GB) | ~$0.10 |
| **Total AWS** | **~$55/month** |

### API Costs (Per 1000 Requests)

| Service | Cost |
|---------|------|
| OpenAI Embeddings (text-embedding-3-large) | ~$0.13 |
| OpenAI LLM (gpt-4o, avg 6 iterations) | ~$15 |
| Tavily Search | ~$1 |
| Pinecone Queries | ~$0 (free tier) |
| **Total per 1000 requests** | **~$16** |

---

## 🚀 Auto-Scaling Configuration

**Update service for auto-scaling:**

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/risksafeai-cluster/risksafeai-service \
  --min-capacity 1 \
  --max-capacity 5 \
  --region us-east-1

# Create scaling policy (CPU-based)
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/risksafeai-cluster/risksafeai-service \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }' \
  --region us-east-1
```

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] Pinecone index populated with ASIC documents (3072D)
- [ ] API keys obtained (OpenAI, Pinecone, Tavily)
- [ ] Local testing completed successfully
- [ ] Docker image builds successfully
- [ ] `.env` file configured (not committed to Git)

### AWS Setup
- [ ] AWS account created and configured
- [ ] ECR repository created
- [ ] Docker image pushed to ECR
- [ ] Secrets Manager configured with API keys
- [ ] ECS cluster created
- [ ] Task definition registered
- [ ] ALB created with target group
- [ ] Security groups configured
- [ ] ECS service created

### Post-Deployment
- [ ] Health check passes
- [ ] ReAct agent endpoint tested
- [ ] CloudWatch logs verified
- [ ] Monitoring metrics configured
- [ ] Auto-scaling enabled (optional)
- [ ] DNS/Custom domain configured (optional)

---

## 📞 Support

For issues:
1. Check CloudWatch logs
2. Verify API keys in Secrets Manager
3. Test Pinecone connection
4. Review ECS task health status

---

**Last Updated:** December 2025
