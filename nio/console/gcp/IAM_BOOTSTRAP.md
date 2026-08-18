# Google Cloud Service Usage bootstrap

## Why this role is needed

The infrastructure enables Google Cloud APIs such as Cloud Run, Cloud Build, Cloud SQL, Secret Manager, Vertex AI, Workflows, Pub/Sub, and Eventarc. The principal executing that bootstrap needs:

- `serviceusage.services.enable`
- `serviceusage.services.get`
- `serviceusage.services.list`

Google's predefined **Service Usage Admin** role (`roles/serviceusage.serviceUsageAdmin`) includes those permissions. It also includes materially stronger permissions, including disabling services, updating service quotas, consuming project quota/billing, and managing consumer policies. It is therefore a bootstrap role—not an application runtime role.

Reference: https://docs.cloud.google.com/iam/docs/roles-permissions/serviceusage#serviceusage.serviceUsageAdmin

## Identity separation

| Identity | Service Usage role | Reason |
|---|---|---|
| Human or dedicated Terraform bootstrap principal | Temporary `roles/serviceusage.serviceUsageAdmin` | Enables required APIs during project bootstrap |
| Vertex AI Agent Engine runtime | `roles/serviceusage.serviceUsageConsumer` | Consumes already-enabled project APIs and quota |
| Cloud Run application runtime | No Service Usage Admin | Must never change project API state |
| Cloud Build deployer | No Service Usage Admin | Builds and deploys; API lifecycle stays outside CI |
| Read-only auditor | `roles/serviceusage.serviceUsageViewer` if needed | Inspects enabled service state only |

## Recommended temporary grant

Run this as a project IAM administrator:

```bash
export PROJECT_ID="your-project-id"
export BOOTSTRAP_PRINCIPAL="user:platform-admin@example.com"

./gcp/bootstrap-service-usage.sh grant
```

By default, the binding expires after two hours through an IAM Condition. The exact expiration is stored locally in `gcp/.bootstrap-role-expiry` so the same conditional binding can be removed explicitly.

Deploy infrastructure while the grant is active:

```bash
cd gcp/terraform
./deploy-infra.sh
```

Then revoke the binding:

```bash
cd ../..
./gcp/bootstrap-service-usage.sh revoke
```

The grant script refuses known Nexus runtime, build, security-agent, and orchestrator service-account names.

## Organization-policy considerations

A project-level role cannot override organization policies. API activation can still fail when:

- `constraints/serviceuser.services` restricts allowed services;
- the principal is blocked by IAM Deny policies;
- VPC Service Controls or Access Context Manager policies restrict the operation;
- required billing is not attached to the project;
- a service is unavailable in the selected organization or region.

Treat those failures as governance decisions. Do not work around them by granting Owner or Editor.

## Terraform behavior

`gcp/terraform/main.tf` declares all required APIs through `google_project_service`. It intentionally uses:

```hcl
disable_on_destroy         = false
disable_dependent_services = false
```

Destroying this stack therefore does **not** disable shared project APIs or cascade-delete dependent services. This guards against accidental project-wide outages.

## Audit requirements

Before and after bootstrap, retain:

1. IAM policy change from Cloud Audit Logs;
2. Service Usage API enable operations;
3. Terraform plan and apply logs;
4. explicit role revocation evidence.

Never place `roles/serviceusage.serviceUsageAdmin` in an agent manifest, Cloud Run runtime identity, or self-modifiable Limb manifest.
