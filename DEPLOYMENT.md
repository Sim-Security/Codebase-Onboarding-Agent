# Deployment Guide

Production deployment infrastructure for the Codebase Onboarding Agent on Google Cloud Platform.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Local Development](#local-development)
4. [GCP Cloud Run Deployment](#gcp-cloud-run-deployment)
5. [GitHub Actions CI/CD](#github-actions-cicd)
6. [Environment Variables](#environment-variables)
7. [Monitoring & Observability](#monitoring--observability)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Repository                            │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ Source Code │───▶│ GitHub Actions│───▶│ Cloud Build/GCR   │  │
│  └─────────────┘    └──────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                        │
│  ┌───────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │ Container     │───▶│ Cloud Run    │◀───│ Load Balancer   │  │
│  │ Registry      │    │ (Serverless) │    │ (HTTPS)         │  │
│  └───────────────┘    └──────────────┘    └─────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│                    ┌──────────────────┐                         │
│                    │ Cloud Monitoring │                         │
│                    │ & Logging        │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Gradio Application**: Interactive web UI serving on port 8080
- **Multi-stage Docker Build**: Optimized image with minimal attack surface
- **Cloud Run**: Serverless container platform with auto-scaling
- **GitHub Actions**: CI/CD pipeline for automated deployments

---

## Prerequisites

### Required Tools

```bash
# Google Cloud SDK
curl https://sdk.cloud.google.com | bash
gcloud --version

# Docker
docker --version

# Git
git --version
```

### GCP Setup

1. **Create a GCP Project** (or use existing):
   ```bash
   gcloud projects create YOUR_PROJECT_ID --name="Codebase Onboarding Agent"
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Enable Required APIs**:
   ```bash
   gcloud services enable \
     cloudbuild.googleapis.com \
     run.googleapis.com \
     containerregistry.googleapis.com \
     secretmanager.googleapis.com
   ```

3. **Create Service Account for CI/CD**:
   ```bash
   # Create service account
   gcloud iam service-accounts create github-actions \
     --display-name="GitHub Actions Deployer"

   # Grant required roles
   PROJECT_ID=$(gcloud config get-value project)
   SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${SA_EMAIL}" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${SA_EMAIL}" \
     --role="roles/storage.admin"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${SA_EMAIL}" \
     --role="roles/iam.serviceAccountUser"

   # Generate key file
   gcloud iam service-accounts keys create ./gcp-sa-key.json \
     --iam-account=${SA_EMAIL}

   # Base64 encode for GitHub secrets
   cat gcp-sa-key.json | base64 -w 0
   ```

---

## Local Development

### Run with Docker

```bash
# Build the image
docker build -t codebase-agent:local .

# Run locally (mimics Cloud Run)
docker run -p 8080:8080 \
  -e PORT=8080 \
  codebase-agent:local

# Access at http://localhost:8080
```

### Run without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py

# Access at http://localhost:7860 (default) or PORT env var
```

### Test with Different Ports

```bash
# Simulate Cloud Run port
PORT=8080 python app.py
```

---

## GCP Cloud Run Deployment

### Option 1: Manual Deployment via gcloud

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/codebase-onboarding-agent

# Deploy to Cloud Run
gcloud run deploy codebase-onboarding-agent \
  --image gcr.io/YOUR_PROJECT_ID/codebase-onboarding-agent \
  --platform managed \
  --region us-central1 \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300s \
  --max-instances 10 \
  --min-instances 0 \
  --allow-unauthenticated
```

### Option 2: Cloud Build Configuration

```bash
# Deploy using cloudbuild.yaml
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_SERVICE_NAME=codebase-onboarding-agent,_REGION=us-central1
```

### Option 3: GitHub Actions (Recommended)

See [GitHub Actions CI/CD](#github-actions-cicd) section below.

---

## GitHub Actions CI/CD

### Required GitHub Secrets

Navigate to **Settings > Secrets and variables > Actions** and add:

| Secret Name       | Description                           | How to Get                          |
|-------------------|---------------------------------------|-------------------------------------|
| `GCP_PROJECT_ID`  | Your GCP project ID                   | `gcloud config get-value project`   |
| `GCP_SA_KEY`      | Base64-encoded service account key    | See Prerequisites section above     |
| `GCP_REGION`      | Deployment region (optional)          | Default: `us-central1`              |

### Workflow Triggers

The CI/CD pipeline triggers on:
- **Push to `main`**: Full build, test, and deploy
- **Pull Request to `main`**: Build and test only (no deploy)
- **Manual dispatch**: Via GitHub Actions UI

### Pipeline Stages

```
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────┐
│  Lint   │───▶│   Test   │───▶│  Build  │───▶│ Deploy │
└─────────┘    └──────────┘    └─────────┘    └────────┘
     │              │               │              │
     ▼              ▼               ▼              ▼
   Ruff          pytest         Docker        Cloud Run
   mypy          coverage       Buildx        Health Check
```

### Manual Deployment

Trigger deployment manually:
1. Go to **Actions** tab
2. Select **Build, Test & Deploy to Cloud Run**
3. Click **Run workflow**
4. Select branch and environment

---

## Environment Variables

### Application Variables

| Variable        | Description                    | Default     | Required |
|-----------------|--------------------------------|-------------|----------|
| `PORT`          | Server port (Cloud Run sets)   | `7860`      | No       |

### API Keys (User-provided at runtime)

The application requires users to provide their own API keys through the UI:
- **OpenRouter API Key**: `sk-or-...`
- **Groq API Key**: `gsk_...`

No API keys should be baked into the container image.

### Cloud Run Environment

Set via deployment flags or Cloud Console:
```bash
gcloud run services update codebase-onboarding-agent \
  --update-env-vars "PYTHONUNBUFFERED=1"
```

---

## Monitoring & Observability

### Cloud Run Metrics

View in GCP Console: **Cloud Run > Services > codebase-onboarding-agent > Metrics**

Key metrics:
- Request count and latency
- Container instance count
- Memory and CPU utilization
- Error rates (4xx, 5xx)

### Logging

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=codebase-onboarding-agent" \
  --limit=100 \
  --format="table(timestamp,textPayload)"

# Stream logs in real-time
gcloud beta run services logs read codebase-onboarding-agent --tail
```

### Health Checks

The Dockerfile includes a health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1
```

Cloud Run performs its own HTTP health checks on the root path `/`.

---

## Troubleshooting

### Common Issues

#### 1. Container fails to start

```bash
# Check logs
gcloud run services logs read codebase-onboarding-agent --limit=50

# Common causes:
# - PORT not set correctly (must be 8080)
# - Missing dependencies in requirements.txt
# - Memory limit too low
```

#### 2. Health check failures

```bash
# Verify the app responds on the correct port
docker run -p 8080:8080 -e PORT=8080 IMAGE_NAME
curl http://localhost:8080
```

#### 3. Deployment permission denied

```bash
# Verify service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:github-actions@"
```

#### 4. Build fails in GitHub Actions

- Verify all secrets are set correctly
- Check if GCP_SA_KEY is properly base64 encoded
- Ensure APIs are enabled in GCP project

### Debug Commands

```bash
# List Cloud Run services
gcloud run services list

# Describe service details
gcloud run services describe codebase-onboarding-agent --region=us-central1

# View revision details
gcloud run revisions list --service=codebase-onboarding-agent --region=us-central1

# Delete and redeploy
gcloud run services delete codebase-onboarding-agent --region=us-central1
```

---

## Security Considerations

### Container Security

- **Non-root user**: Container runs as `appuser` (UID 1000)
- **Minimal base image**: `python:3.11-slim` reduces attack surface
- **Multi-stage build**: Build dependencies not included in runtime image
- **No secrets in image**: API keys provided by users at runtime

### Cloud Run Security

- **HTTPS by default**: All traffic encrypted in transit
- **IAM integration**: Fine-grained access control
- **VPC connector**: Optional private networking (not configured by default)
- **Concurrency limits**: Prevents resource exhaustion

### CI/CD Security

- **Secrets management**: Credentials stored in GitHub Secrets
- **Minimal permissions**: Service account has only required roles
- **Branch protection**: Deploy only from `main` branch

### Recommendations

1. **Enable VPC Service Controls** for sensitive workloads
2. **Use Cloud Armor** for DDoS protection if publicly exposed
3. **Rotate service account keys** periodically
4. **Enable binary authorization** for supply chain security

---

## Quick Reference

### Useful Commands

```bash
# Deploy
gcloud builds submit --config=cloudbuild.yaml

# View service URL
gcloud run services describe codebase-onboarding-agent \
  --region=us-central1 --format='value(status.url)'

# Scale to zero (cost saving)
gcloud run services update codebase-onboarding-agent \
  --region=us-central1 --min-instances=0

# Update memory
gcloud run services update codebase-onboarding-agent \
  --region=us-central1 --memory=4Gi

# Rollback to previous revision
gcloud run services update-traffic codebase-onboarding-agent \
  --region=us-central1 --to-revisions=PREVIOUS_REVISION=100
```

### Cost Optimization

- Set `--min-instances=0` for scale-to-zero
- Use `--cpu-throttling` to reduce idle CPU costs
- Set appropriate `--max-instances` to cap spending
- Use Cloud Run pricing calculator for estimates

---

## Support

For issues with this deployment:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Cloud Run logs in GCP Console
3. Open an issue in this repository
