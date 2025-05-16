# Rhesis Infrastructure

This directory contains the Terraform code for deploying the Rhesis application infrastructure on Google Cloud Platform.

## Optimizations and Best Practices

The infrastructure code has been optimized to follow Terraform best practices:

1. **DRY (Don't Repeat Yourself)** - Common configurations are extracted to:
   - `common/defaults.tfvars`: Environment-specific defaults for services
   - `common/providers.tf`: Common provider configurations
   - `modules/service`: A unified service deployment module

2. **Parameterization** - Environment-specific configurations are parameterized:
   - Database settings (machine type, high availability, disk size)
   - Service settings (CPU, memory, instance counts)
   - IAM roles

3. **Modularity** - The code is organized into reusable modules:
   - `environment`: Orchestrates the deployment of a complete environment
   - `service`: Standardizes service deployment (Cloud Run + IAM)
   - Other resource-specific modules (cloud-sql, network, storage, etc.)

4. **Consistency** - Common patterns are used across all resources:
   - Consistent naming conventions
   - Standardized labels
   - Unified approach to environment variables

## Fixed IPs and SSL with Load Balancers

Cloud Run services by default don't have fixed IP addresses. To provide fixed IPs and proper SSL certificates, this infrastructure includes load balancers for each service:

1. **Static IP** - Each service can have a reserved static IP address
2. **SSL Certificates** - Managed SSL certificates are automatically provisioned
3. **Domain Mapping** - Custom domains are mapped to each service
4. **Environment-specific** - Different domains for dev/stg/prd environments

To enable a load balancer for a service, set the corresponding domain variable:
```hcl
# For example, in terraform.tfvars
backend_domain = "api.example.com"
frontend_domain = "app.example.com"
```

If a domain is not specified (empty string), no load balancer will be created for that service.

## Directory Structure

- `common/`: Common configurations and defaults
- `environments/`: Environment-specific configurations
  - `dev/`: Development environment
  - `stg/`: Staging environment
  - `prd/`: Production environment
- `modules/`: Reusable Terraform modules
  - `environment/`: Environment orchestration module
  - `service/`: Service deployment module
  - `container-registry/`: Container registry module
  - Other resource-specific modules
- `scripts/`: Deployment and utility scripts
  - `deploy-terraform.sh`: Script for deploying to different environments
  - `bootstrap-terraform-deployer.sh`: Script for setting up a Terraform deployer service account

## Deployment

### Quick Start

1. Create a bootstrap admin project in GCP for Terraform state management:
   ```
   # Create a new project in GCP called "rhesis-platform-admin" (or your preferred name)
   # Enable billing for the project
   ```

2. Set up your GCP service account and Terraform state bucket:
   ```
   # Update the bootstrap script with your project and billing account IDs
   cd scripts
   ./bootstrap-terraform-deployer.sh
   ```
   This script will:
   - Create a service account with necessary permissions
   - Enable required APIs
   - Create a GCS bucket for Terraform state storage
   - Configure bucket versioning and permissions
   - Generate a service account key file

3. Deploy to an environment using the deployment script:
   ```
   cd scripts
   ./deploy-terraform.sh --environment dev --key /path/to/service-account-key.json
   ```

4. For more deployment options:
   ```
   ./deploy-terraform.sh --help
   ```

### Automated Deployment

This repository includes a GitHub Actions workflow for automated deployments. See `scripts/DEPLOYMENT.md` for detailed instructions.

### Variable Management

The deployment process uses a standardized approach to map GitHub secrets to Terraform variables:
1. GitHub secrets follow the naming convention `TF_VAR_VARIABLE_NAME` (uppercase)
2. Terraform variables use snake_case in the .tf files
3. The deployment script automatically converts between these formats
4. Variables are organized by environment using GitHub Environments feature
5. For detailed information about the variable mapping process, see `scripts/DEPLOYMENT.md`

## Usage

1. Navigate to the desired environment directory:
   ```
   cd environments/dev
   ```

2. Initialize Terraform:
   ```
   terraform init
   ```

3. Apply the common defaults:
   ```
   terraform apply -var-file=../../common/defaults.tfvars
   ```

4. Create a `terraform.tfvars` file based on the example:
   ```
   cp terraform.tfvars.example terraform.tfvars
   ```

5. Edit the `terraform.tfvars` file with your specific values.

6. Apply the Terraform configuration:
   ```
   terraform apply
   ```

## Structure

- `modules/`: Reusable Terraform modules
  - `environment/`: Main environment module that creates all resources
  - `gcp-project/`: GCP project creation and API enablement
  - `cloud-run/`: Cloud Run services
  - `cloud-sql/`: Cloud SQL databases
  - `storage/`: GCS buckets
  - `network/`: VPC networks, subnets, and related resources
  - `iam/`: Service accounts and IAM permissions
  - `pubsub/`: Pub/Sub topics and subscriptions
  - `container-registry/`: Artifact Registry repositories for container images
  - `load-balancer/`: Load balancer with SSL certificates for Cloud Run services
- `environments/`: Environment-specific configurations
  - `dev/`: Development environment
  - `stg/`: Staging environment
  - `prd/`: Production environment
- `common/`: Shared resources and configurations

## Naming Convention

Resources follow the naming convention: `{service}-{env}[-{region}]`

- `service`: backend, frontend, worker, polyphemus, db
- `env`: dev, prd, stg
- `region`: included for region-specific resources

## Default Region

The default region is `europe-west4`.

## Environment Separation

Each environment (dev, stg, prd) has its own:
- GCP project
- Network infrastructure
- Service accounts
- Cloud SQL database
- Storage buckets
- Pub/Sub topics
- Cloud Run services 