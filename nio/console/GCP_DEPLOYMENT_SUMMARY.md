# Nexus Console — Google Cloud Port Summary

##  Overview

The Nexus Console has been prepared for deployment to Google Cloud Platform using a **Google-Cloud-native architecture**. All components are designed to use only Google Cloud Console services.

## 📁 Created Files

### Infrastructure as Code (Terraform)
```
gcp/terraform/
├── main.tf                 # Main infrastructure configuration
├── variables.tf            # Terraform input variables
├── backend.tf              # Remote state configuration
└── deploy-infra.sh         # Infrastructure deployment script
```

### CI/CD Pipeline
```
gcp/
├── cloudbuild.yaml         # Cloud Build pipeline definition
├── deploy.sh               # Application deployment script
├── .env.example            # Environment variables template
├── README.md               # Deployment documentation
└── DEPLOYMENT_CHECKLIST.md # Pre/post deployment checklist
```

### Container Configuration
```
├── Dockerfile              # Multi-stage Docker build
├── .dockerignore           # Docker build context exclusions
└── .gcloudignore           # Cloud Build context exclusions
```

### Vertex AI Configuration
```
gcp/vertex-ai/
── agent-registry.json     # Agent Engine manifest (Option A)
```

### Application Configuration
```
├── next.config.ts          # Next.js config (standalone output)
└── package.json            # Dependencies (already exists)
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Cloud Run (Managed)                    │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │           Nexus Console (Next.js)                  │   │   │
│  │  │  - Containerized Next.js application               │   │   │
│  │  │  - Auto-scaling 0-10 instances                     │   │   │
│  │  │  - Health checks on /api/health                    │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Vertex AI Agent Engine                       │   │
│  │  - 10 specialized AI agents                               │   │
│  │  - Gemini 2.5 Pro / Flash models                          │   │
│  │  - Managed runtime with IAM identity                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              ┌───────────────┴───────────────┐                  │
│              ▼                               ▼                  │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │   Cloud SQL         │         │  Secret Manager     │       │
│  │   PostgreSQL 15     │         │  - DB passwords     │       │
│  │   - Database        │         │  - API keys         │       │
│  │   - Auto backups    │         │  - Auto rotation    │       │
│  └─────────────────────┘         └─────────────────────┘       │
│              │                               │                  │
│              ▼                               ▼                  │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │  Artifact Registry  │         │  Cloud Build        │       │
│  │  - Docker images    │         │  - CI/CD pipeline   │       │
│  │  - Versioned tags   │         │  - Auto triggers    │       │
│  └─────────────────────┘         └─────────────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Observability Stack                          │   │
│  │  - Cloud Monitoring (metrics & dashboards)               │   │
│  │  - Cloud Logging (structured logs)                       │   │
│  │  - Cloud Trace (distributed tracing)                     │   │
│  │  - Alert Policy (error rate, latency)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Deploy

### 1. Set Environment
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west3"
export ENVIRONMENT="dev"
```

### 2. Deploy Infrastructure
```bash
cd gcp/terraform
./deploy-infra.sh
```

### 3. Deploy Application
```bash
cd ../
./deploy.sh
```

### 4. Verify
```bash
gcloud run services browse nexus-console-dev --region=$REGION
```

##  Key Configurations

### Cloud Run
| Setting | Value |
|---------|-------|
| Region | europe-west3 |
| Memory | 512Mi |
| CPU | 1 |
| Min Instances | 0 |
| Max Instances | 10 |
| Timeout | 300s |
| Concurrency | 80 |

### Cloud SQL
| Setting | Value |
|---------|-------|
| Engine | PostgreSQL 15 |
| Tier | db-f1-micro (dev) |
| Disk | 10GB SSD |
| Backups | Daily + PITR |
| SSL | Required |

### Vertex AI
| Setting | Value |
|---------|-------|
| Models | Gemini 2.5 Pro/Flash |
| Context | 256K - 1M tokens |
| Runtime | Agent Engine |
| Location | europe-west3 |

## 🔐 Security

- **Service Accounts**: Dedicated per component
- **Secrets**: All credentials in Secret Manager
- **Network**: VPC Service Controls ready
- **IAM**: Least privilege principle
- **SSL**: Enforced for database connections

## 📊 Monitoring

### Metrics Tracked
- Request count and latency
- Error rate (4xx, 5xx)
- Cloud SQL CPU and connections
- Vertex AI API calls
- Memory and CPU utilization

### Alerts Configured
- Error rate > 5%
- p99 latency > 2s
- Cloud SQL CPU > 80%
- Deployment failures

## 💰 Cost Estimates (Monthly)

| Service | Dev | Staging | Production |
|---------|-----|---------|------------|
| Cloud Run | ~$5 | ~$20 | ~$100 |
| Cloud SQL | ~$10 | ~$30 | ~$150 |
| Vertex AI | ~$20 | ~$50 | ~$300 |
| Cloud Build | ~$5 | ~$10 | ~$30 |
| Storage/Registry | ~$2 | ~$5 | ~$20 |
| **Total** | **~$42** | **~$115** | **~$600** |

*Estimates based on typical usage patterns*

## 📋 Next Steps

1. **Review** `gcp/terraform/variables.tf` and customize
2. **Create** `terraform.tfvars` with your settings
3. **Run** infrastructure deployment script
4. **Configure** GitHub connection for Cloud Build
5. **Deploy** application using deploy.sh
6. **Verify** health checks and monitoring
7. **Complete** DEPLOYMENT_CHECKLIST.md

## 📚 Documentation

- `gcp/README.md` — Detailed deployment guide
- `gcp/DEPLOYMENT_CHECKLIST.md` — Pre/post deployment checklist
- `gcp/vertex-ai/agent-registry.json` — Agent Engine manifest
- `gcp/.env.example` — Environment variables reference

## 🆘 Support

### Common Issues

**Build fails:**
```bash
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

**Deployment fails:**
```bash
gcloud run services describe nexus-console-dev --region=$REGION
gcloud run services logs read nexus-console-dev --region=$REGION
```

**Database connection:**
```bash
gcloud sql instances describe nexus-db
gcloud secrets describe nexus-console-dev-db-password
```

### Resources

- [Cloud Run Docs](https://cloud.google.com/run/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/agent-engine)
- [Next.js Deployment](https://nextjs.org/docs/deployment)

---

**Status**: ✅ Ready for Google Cloud Deployment
**Last Updated**: 2026
**Version**: 1.0.0
