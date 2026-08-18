# Nexus Console — Google Cloud Deployment Guide

## Overview

This directory contains all configuration files needed to deploy the Nexus Console to Google Cloud Platform using:

- **Cloud Run** — Serverless container execution
- **Cloud SQL** — Managed PostgreSQL database
- **Vertex AI** — Agent Engine for AI agents
- **Secret Manager** — Secure credential storage
- **Cloud Build** — CI/CD pipeline
- **Artifact Registry** — Container image storage
- **Cloud Monitoring** — Observability and alerting
- **Terraform** — Infrastructure as Code

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed locally
4. **Node.js 20+** for local development
5. **Terraform 1.5+** for infrastructure deployment

## Quick Start

### 1. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Set Environment Variables

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west3"
export ENVIRONMENT="dev"
```

### 3. Bootstrap Service Usage permission

The human or dedicated Terraform principal needs a temporary `roles/serviceusage.serviceUsageAdmin` grant to enable the declared APIs. Never grant this role to Cloud Run, Cloud Build, or Agent Engine runtime identities.

```bash
export BOOTSTRAP_PRINCIPAL="user:platform-admin@example.com"
./gcp/bootstrap-service-usage.sh grant
```

See `gcp/IAM_BOOTSTRAP.md` for the permission boundary and IAM Condition behavior.

### 4. Deploy Infrastructure (Terraform)

```bash
cd gcp/terraform
chmod +x deploy-infra.sh
./deploy-infra.sh
```

After the APIs and infrastructure are provisioned, remove the bootstrap grant:

```bash
cd ../..
./gcp/bootstrap-service-usage.sh revoke
```

This will create:
- Cloud Run service
- Cloud SQL PostgreSQL instance
- Secret Manager secrets
- Artifact Registry repository
- Service accounts with appropriate IAM roles
- Cloud Monitoring dashboard and alerts

### 4. Deploy Application

```bash
cd gcp
chmod +x deploy.sh
./deploy.sh
```

This will:
- Build the Next.js application
- Create and push Docker image
- Deploy to Cloud Run
- Run health checks

## Manual Deployment Steps

### Enable Required APIs

Run this only as the temporary bootstrap principal described in `IAM_BOOTSTRAP.md`. It needs `roles/serviceusage.serviceUsageAdmin`; do not substitute Owner/Editor and do not grant this role to a runtime identity.

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com
```

### Create Artifact Registry

```bash
gcloud artifacts repositories create nexus-console-docker \
  --project=$PROJECT_ID \
  --location=$REGION \
  --repository-format=docker
```

### Create Database Password Secret

```bash
gcloud secrets create nexus-console-dev-db-password \
  --project=$PROJECT_ID \
  --replication-policy=auto

# Add secret version
echo "your-secure-password" | \
  gcloud secrets versions add nexus-console-dev-db-password \
  --data-file=-
```

### Build and Push Image

```bash
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/nexus-console-docker/nexus-console:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/nexus-console-docker/nexus-console:latest
```

### Deploy to Cloud Run

```bash
gcloud run deploy nexus-console-dev \
  --project=$PROJECT_ID \
  --region=$REGION \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/nexus-console-docker/nexus-console:latest \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="NODE_ENV=production,PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="DATABASE_PASSWORD=nexus-console-dev-db-password:latest"
```

## CI/CD with Cloud Build

### Trigger Deployment from GitHub

1. Create a Cloud Build connection to GitHub:
```bash
gcloud builds connections create github \
  --project=$PROJECT_ID \
  --region=$REGION \
  nexus-github-connection
```

2. Grant Cloud Build access to your repository

3. Push to `main` branch to trigger automatic deployment

### View Build Logs

```bash
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

## Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `PROJECT_ID` | GCP Project ID | Cloud Run env |
| `REGION` | GCP Region | Cloud Run env |
| `DATABASE_URL` | PostgreSQL connection | Cloud Run env + Secret |
| `DATABASE_PASSWORD` | Database password | Secret Manager |
| `VERTEX_AI_LOCATION` | Vertex AI region | Cloud Run env |
| `NODE_ENV` | Environment | Cloud Run env |

## Monitoring

### View Logs

```bash
gcloud run services logs tail nexus-console-dev --region=$REGION
```

### Access Dashboard

1. Open [Cloud Console](https://console.cloud.google.com)
2. Navigate to **Monitoring → Dashboards**
3. Select "Nexus Console Dashboard"

### Configure Alerts

Alerts are configured via Terraform for:
- High error rate (>5%)
- High latency (p99 > 2s)
- Cloud SQL CPU utilization

## Security Considerations

1. **Service Accounts**: Use dedicated service accounts with minimal permissions
2. **Secrets**: All credentials stored in Secret Manager
3. **VPC**: Enable VPC Service Controls for production
4. **IAM**: Follow principle of least privilege
5. **SSL**: Cloud SQL requires SSL connections

## Cost Optimization

- Set `min_instances=0` for development environments
- Use appropriate Cloud SQL tier (db-f1-micro for dev)
- Configure Cloud Run concurrency based on workload
- Enable Cloud SQL automatic backup only for production

## Troubleshooting

### Cloud Run Deployment Fails

```bash
# Check service status
gcloud run services describe nexus-console-dev --region=$REGION

# View recent logs
gcloud run services logs read nexus-console-dev --region=$REGION --limit=50
```

### Database Connection Issues

```bash
# Verify Cloud SQL instance
gcloud sql instances describe nexus-db

# Check secret exists
gcloud secrets describe nexus-console-dev-db-password
```

### Permission Errors

```bash
# Check service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --filter="serviceAccount:$(gcloud run services describe nexus-console-dev --region=$REGION --format='value(spec.template.serviceAccountName)')"
```

## Cleanup

To remove all resources:

```bash
# Delete Cloud Run service
gcloud run services delete nexus-console-dev --region=$REGION

# Delete Cloud SQL instance (enable deletion protection first)
gcloud sql instances delete nexus-db

# Delete Artifact Registry
gcloud artifacts repositories delete nexus-console-docker --location=$REGION

# Delete Terraform resources
cd gcp/terraform
terraform destroy
```

## Support

For issues or questions, refer to:
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Next.js Deployment Guide](https://nextjs.org/docs/deployment)
