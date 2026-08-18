# Nexus Console — Google Cloud Deployment Checklist

## Pre-Deployment

### Account & Project Setup
- [ ] Google Cloud account created
- [ ] Project created with unique ID
- [ ] Billing account linked to project
- [ ] Dedicated human/Terraform bootstrap principal selected
- [ ] Temporary `roles/serviceusage.serviceUsageAdmin` grant created with expiry
- [ ] Confirmed the role is not assigned to Cloud Run, Cloud Build, or Agent Engine runtime identities
- [ ] Required APIs enabled:
  - [ ] Cloud Run API
  - [ ] Cloud Build API
  - [ ] Cloud SQL API
  - [ ] Secret Manager API
  - [ ] Vertex AI API
  - [ ] Artifact Registry API
  - [ ] Cloud Monitoring API
  - [ ] Cloud Logging API
  - [ ] VPC Access API

### Local Environment
- [ ] gcloud CLI installed (`gcloud version`)
- [ ] Authenticated (`gcloud auth login`)
- [ ] Project set (`gcloud config set project PROJECT_ID`)
- [ ] Docker installed (`docker --version`)
- [ ] Node.js 20+ installed (`node --version`)
- [ ] Terraform 1.5+ installed (`terraform version`)

### Code Preparation
- [ ] All TypeScript errors resolved
- [ ] All tests passing
- [ ] `.env.example` reviewed and updated
- [ ] `package.json` dependencies up to date
- [ ] Dockerfile tested locally

## Infrastructure Deployment (Terraform)

### State Management
- [ ] GCS bucket created for Terraform state
- [ ] State bucket versioning enabled
- [ ] Backend configuration updated

### Terraform Variables
- [ ] `terraform.tfvars` created
- [ ] Project ID configured
- [ ] Region configured
- [ ] Environment name set
- [ ] Alert email configured (production)
- [ ] Database credentials reviewed

### Apply Infrastructure
- [ ] `terraform init` completed successfully
- [ ] `terraform plan` reviewed
- [ ] `terraform apply` completed
- [ ] Outputs recorded:
  - [ ] Cloud Run URL
  - [ ] Cloud SQL connection name
  - [ ] Service account email
  - [ ] Artifact Registry URL

### Post-Infrastructure Verification
- [ ] Temporary `roles/serviceusage.serviceUsageAdmin` binding explicitly revoked
- [ ] Grant, API-enable operations, and revocation visible in Cloud Audit Logs
- [ ] Cloud Run service exists
- [ ] Cloud SQL instance is running
- [ ] Secret Manager secrets created
- [ ] Service accounts have correct roles
- [ ] Artifact Registry repository exists

## Application Deployment

### Database Setup
- [ ] Database password stored in Secret Manager
- [ ] Database user created in Cloud SQL
- [ ] Database schema migrated (drizzle-kit push)
- [ ] Connection string tested

### Container Image
- [ ] Docker build successful locally
- [ ] Image pushed to Artifact Registry
- [ ] Image tagged with commit SHA
- [ ] Image tagged as latest

### Cloud Run Deployment
- [ ] Service deployed to Cloud Run
- [ ] Environment variables set
- [ ] Secrets mounted correctly
- [ ] Memory/CPU configured
- [ ] Min/max instances set
- [ ] Timeout configured
- [ ] Ingress settings verified

### Health Check
- [ ] `/api/health` endpoint responds
- [ ] Database connection successful
- [ ] No errors in Cloud Logging
- [ ] Response time acceptable (<2s)

## Post-Deployment Verification

### Functional Testing
- [ ] Home page loads
- [ ] All routes accessible
- [ ] API endpoints respond
- [ ] No console errors
- [ ] Mobile responsive

### Performance
- [ ] Cold start time measured
- [ ] Average response time < 500ms
- [ ] p95 latency < 2s
- [ ] Memory usage within limits

### Monitoring & Alerting
- [ ] Cloud Monitoring dashboard created
- [ ] Alerts configured
- [ ] Notification channels tested
- [ ] Log ingestion verified
- [ ] Custom metrics visible

### Security
- [ ] HTTPS enforced
- [ ] Security headers present
- [ ] Service account has minimal permissions
- [ ] Secrets not in logs
- [ ] Database requires SSL

## Production-Specific

### High Availability
- [ ] Multi-region deployment considered
- [ ] Cloud SQL high availability enabled
- [ ] Backup configuration verified
- [ ] Point-in-time recovery enabled

### Disaster Recovery
- [ ] Backup schedule configured
- [ ] Restore procedure documented
- [ ] Terraform state backed up
- [ ] Rollback procedure tested

### Compliance
- [ ] Data residency requirements met
- [ ] Audit logging enabled
- [ ] Access logs reviewed
- [ ] IAM policies documented

### Cost Optimization
- [ ] Min instances = 0 for non-prod
- [ ] Appropriate Cloud SQL tier selected
- [ ] Cloud Run concurrency optimized
- [ ] Budget alerts configured

## CI/CD Pipeline

### Cloud Build Configuration
- [ ] cloudbuild.yaml validated
- [ ] GitHub connection established
- [ ] Trigger configured for main branch
- [ ] Build notifications enabled

### Deployment Automation
- [ ] Automated builds on push
- [ ] Automated tests in pipeline
- [ ] Automated deployment on merge
- [ ] Rollback capability tested

## Documentation

### Runbooks
- [ ] Deployment procedure documented
- [ ] Rollback procedure documented
- [ ] Incident response plan created
- [ ] On-call rotation configured

### Knowledge Transfer
- [ ] Architecture diagram updated
- [ ] Service dependencies documented
- [ ] Contact information current
- [ ] Access procedures documented

## Cleanup (If Needed)

### Resource Deletion
- [ ] Cloud Run service deleted
- [ ] Cloud SQL instance deleted
- [ ] Secret Manager secrets deleted
- [ ] Artifact Registry cleaned
- [ ] Terraform resources destroyed
- [ ] GCS state bucket emptied

### Final Verification
- [ ] No orphaned resources
- [ ] Billing shows no unexpected charges
- [ ] DNS records removed (if applicable)
- [ ] GitHub triggers disabled

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| DevOps | | | |
| Security | | | |
| Product Owner | | | |

---

**Notes:**
