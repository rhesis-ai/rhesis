# Terraform Deployment Workflow

This document explains how to deploy the Rhesis infrastructure using the provided deployment scripts.

## Prerequisites

1. Bootstrap admin project in GCP for Terraform state management
   - Create a project (e.g., "rhesis-platform-admin") to store Terraform state
   - Enable billing for the project
   - Run the `bootstrap-terraform-deployer.sh` script to:
     - Create a service account with necessary permissions
     - Enable required APIs
     - Create a GCS bucket for Terraform state
     - Configure bucket versioning and permissions

2. Google Cloud Platform service account with appropriate permissions
3. Service account key JSON file
4. Terraform installed locally (for manual deployments)

## Deployment Options

You can deploy the infrastructure in three ways:

1. **Manual deployment** using the provided shell script
2. **Automated deployment** using GitHub Actions via the web interface
3. **Automated deployment** using GitHub Actions via the command line

## Manual Deployment

The `deploy-terraform.sh` script provides a flexible way to deploy to different environments.

### Usage

```bash
./deploy-terraform.sh [OPTIONS]
```

### Options

- `-e, --environment ENV`: Environment to deploy (dev, stg, prd) [default: dev]
- `-k, --key FILE`: Path to GCP service account key JSON file [required]
- `-y, --auto-approve`: Auto-approve Terraform apply
- `-p, --plan`: Generate plan only, don't apply
- `-i, --init`: Initialize Terraform only
- `-s, --stage STAGE`: Deployment stage (project, services, all) [default: all]
- `-u, --force-unlock ID`: Force unlock the state with the given lock ID
- `-h, --help`: Show help message

### Examples

Initialize Terraform for development environment:
```bash
./deploy-terraform.sh --environment dev --key ./terraform-deployer-key.json --init
```

Generate plan for staging environment:
```bash
./deploy-terraform.sh --environment stg --key ./terraform-deployer-key.json --plan
```

Deploy to production with auto-approve:
```bash
./deploy-terraform.sh --environment prd --key ./terraform-deployer-key.json --auto-approve
```

### Staged Deployment

To avoid issues with resource dependencies (particularly Cloud SQL users requiring a running SQL instance), the script supports staged deployment:

#### Step 1: Deploy Project Infrastructure Only

```bash
./deploy-terraform.sh --environment dev --key $(pwd)/terraform-deployer-key.json --stage project
```

This will:
- Create/update the GCP project
- Enable required APIs
- Set up IAM permissions
- Create the Cloud SQL instance (but not users)

Wait for the Cloud SQL instance to be fully running. You can check its status with:

```bash
gcloud sql instances describe db-development-europe-west4 --project=rhesis-dev --format="value(state)"
```

Wait until it shows `RUNNABLE` before proceeding to the next step.

#### Step 2: Deploy Services (Including SQL Users)

```bash
./deploy-terraform.sh --environment dev --key $(pwd)/terraform-deployer-key.json --stage services
```

This will:
- Create SQL users and databases
- Deploy Cloud Run services
- Set up other dependent resources

#### Why Staged Deployment?

Staged deployment solves a common issue where Terraform attempts to create SQL users before the SQL instance is fully operational. This can cause errors like:

```
Error: Error when reading or editing SQL User "rhesis" in instance "db-development-europe-west4": googleapi: Error 400: Invalid request: Invalid request since instance is not running., invalid
```

By splitting the deployment into stages, we ensure the SQL instance is fully running before attempting to create users.

## GitHub Actions Deployment

The repository includes a GitHub Actions workflow file (`infrastructure.yml`) in the `.github/workflows/` directory that can be used to automate deployments.

### Setup

1. Add your GCP service account key as a GitHub secret named `GCP_SA_KEY`

2. Add Terraform variables as GitHub secrets with the following naming convention:
   - Common variables for all environments:
     - `TF_VAR_REGION`: The GCP region (e.g., "europe-west4")
     - `TF_VAR_BILLING_ACCOUNT`: Your GCP billing account ID

   - Environment-specific variables (replace ENV with DEV, STG, or PRD):
     - `TF_VAR_ENV_DATABASE_PASSWORD`: Database password
     - `TF_VAR_ENV_BACKEND_IMAGE`: Backend container image URL
     - `TF_VAR_ENV_FRONTEND_IMAGE`: Frontend container image URL
     - `TF_VAR_ENV_WORKER_IMAGE`: Worker container image URL
     - `TF_VAR_ENV_POLYPHEMUS_IMAGE`: Polyphemus container image URL
     - `TF_VAR_ENV_CHATBOT_IMAGE`: Chatbot container image URL
     - `TF_VAR_ENV_ENABLE_LOAD_BALANCERS`: Whether to enable load balancers (true/false)
     
   - Domain naming follows these conventions:
     - For development and staging: `env-service.rhesis.ai` (e.g., dev-api.rhesis.ai)
     - For production: `service.rhesis.ai` (e.g., api.rhesis.ai)
     
   - Domain variables:
     - For dev/stg: `TF_VAR_ENV_SERVICE_DOMAIN` (e.g., TF_VAR_DEV_BACKEND_DOMAIN = "dev-api.rhesis.ai")
     - For production: `TF_VAR_PRD_SERVICE_DOMAIN` (e.g., TF_VAR_PRD_BACKEND_DOMAIN = "api.rhesis.ai")

   Example:
   - `TF_VAR_DEV_DATABASE_PASSWORD`: Password for the development database
   - `TF_VAR_DEV_FRONTEND_DOMAIN`: "dev-app.rhesis.ai"
   - `TF_VAR_PRD_FRONTEND_DOMAIN`: "app.rhesis.ai"

### Container Image Validation

The workflow includes an image validation step using the `check-images.sh` script. This script performs the following important functions:

1. **Validation**: Checks if specified container images actually exist in the artifact registry
2. **Fallback Mechanism**: For images that don't exist, it sets empty values which cause Terraform to use default images
3. **Infrastructure-First Deployment**: Enables infrastructure deployment before container images exist

#### How Image Checking Works

When the workflow runs, before the Terraform plan is generated:

1. The script checks if the artifact registry for the environment exists in the GCP project
   - If the registry doesn't exist yet (common during initial deployment), all image variables are set to empty, allowing Terraform to use default public images
   - This solves the "chicken and egg" problem of needing infrastructure to store images, but needing images to deploy infrastructure

2. For each service (backend, frontend, worker, polyphemus, chatbot):
   - If an image is specified in GitHub secrets, the script checks if it exists in the GCP Artifact Registry
   - If the image exists, it is used in the deployment
   - If the image doesn't exist, an empty value is set, causing Terraform to use default public images
   - For external images (e.g., Docker Hub), the script assumes they exist and uses them as provided

3. Environment variables are set for Terraform using GitHub's `GITHUB_ENV` mechanism

This approach ensures that the infrastructure deployment is resilient to missing images and can proceed even during initial setup when no images have been built yet. It also prevents deployment failures due to referencing non-existent images.

#### Configuration Options

The script accepts the following parameters:
- `--project`: The GCP project ID (required)
- `--environment`: The deployment environment (dev, stg, prd)
- `--region`: The GCP region for the artifact registry

#### Default Images

When image variables are empty, the Terraform modules use the `coalesce()` function to select default public images:
```hcl
container_image = coalesce(var.backend_image, "gcr.io/cloudrun/hello:latest")
```

This approach ensures that Cloud Run services can be deployed even without custom images, facilitating the initial infrastructure setup.

### Terraform Variables and GitHub Secrets Mapping

The deployment process automatically maps GitHub secrets to Terraform variables using a standardized approach:

1. **Naming Convention Alignment**:
   - GitHub secrets use the `TF_VAR_` prefix followed by the variable name in uppercase
   - Terraform variables use lowercase/snake_case in the .tf files
   - The deployment script automatically converts between these formats

2. **Variable Mapping Process**:
   - The `deploy-terraform.sh` script reads the `terraform.tfvars.example` file to identify required variables
   - For each variable, it looks for a corresponding GitHub secret with the `TF_VAR_` prefix
   - The script converts Terraform's snake_case to GitHub's uppercase format (e.g., `database_password` → `TF_VAR_DATABASE_PASSWORD`)
   - When a matching secret is found, its value is written to the generated `terraform.tfvars` file

3. **Example Mapping**:
   ```
   # Terraform variable in .tf file
   variable "database_password" {
     description = "Password for the database"
     type        = string
   }
   
   # Corresponding GitHub secret
   TF_VAR_DATABASE_PASSWORD = "secure-password-value"
   
   # Generated entry in terraform.tfvars
   database_password = "secure-password-value"
   ```

4. **Environment-Specific Variables**:
   - With GitHub environments, variables are stored directly in each environment without prefixes
   - The workflow references the correct environment based on the deployment target
   - This ensures proper variable isolation between environments

5. **Validation and Fallbacks**:
   - If a required variable has no corresponding GitHub secret, the script will use example values with a warning
   - This ensures the deployment process doesn't fail due to missing variables
   - For production deployments, all required variables should be properly set as secrets

This systematic approach ensures that:
- Every Terraform variable has a corresponding GitHub secret with the correct naming convention
- The mapping is consistent across environments
- Variables are properly isolated between environments
- The deployment process is transparent and debuggable

### Automated GitHub Secrets Setup

The repository includes a script (`setup-github-secrets.sh`) to automate the creation of GitHub secrets for all environments.

#### Usage

```bash
./setup-github-secrets.sh [OPTIONS]
```

#### Options

- `-r, --repo REPO`: GitHub repository in format 'owner/repo' [required]
- `-k, --key FILE`: Path to GCP service account key JSON file [default: terraform-deployer-key.json]
- `-e, --environments`: Comma-separated list of environments to set up [default: dev,stg,prd]
- `-h, --help`: Show help message

#### Required Environment Variables

Before running the script, set the following environment variables:

```bash
# Common variables
export REGION="europe-west4"
export BILLING_ACCOUNT="your-billing-account-id"

# Environment-specific variables (example for dev)
export DEV_DATABASE_PASSWORD="your-secure-password"
export DEV_BACKEND_IMAGE="your-backend-image-url"
export DEV_FRONTEND_IMAGE="your-frontend-image-url"
export DEV_WORKER_IMAGE="your-worker-image-url"
export DEV_POLYPHEMUS_IMAGE="your-polyphemus-image-url"
export DEV_CHATBOT_IMAGE="your-chatbot-image-url"
export DEV_ENABLE_LOAD_BALANCERS="true"

# Optional: Custom domain overrides
export DEV_BACKEND_DOMAIN="custom-dev-api.rhesis.ai"
```

Repeat for STG and PRD environments as needed.

#### Example

```bash
# Set up environment variables (see above)
# ...

# Run the script
./setup-github-secrets.sh --repo "your-org/your-repo"
```

The script will:
1. Create GitHub environments for each environment (dev, stg, prd) if they don't exist
2. Set up repository-level secrets for common values
3. Set up environment-specific secrets for each environment
4. Apply the correct domain naming convention for each environment

### Triggering Workflow from Command Line

The repository includes a script (`trigger-infrastructure.sh`) to trigger the GitHub Actions workflow from the command line.

#### Usage

```bash
./trigger-infrastructure.sh [OPTIONS]
```

#### Options

- `-e, --environment ENV`: Environment to deploy (dev, stg, prd) [default: dev]
- `-y, --auto-approve`: Auto-approve Terraform apply
- `-p, --plan`: Generate plan only, don't apply
- `-b, --branch BRANCH`: Specify the branch containing the workflow [default: current branch]
- `-f, --fresh-start`: Create a new Terraform workspace for a fresh start
- `-s, --stage STAGE`: Deployment stage (project, services, all) [default: all]
- `-h, --help`: Show help message

#### Examples

Deploy to development environment:
```bash
./trigger-infrastructure.sh --environment dev
```

Generate plan for staging environment:
```bash
./trigger-infrastructure.sh --environment stg --plan
```

Deploy to production with auto-approve:
```bash
./trigger-infrastructure.sh --environment prd --auto-approve
```

Specify a different branch containing the workflow:
```bash
./trigger-infrastructure.sh --environment dev --branch main
```

Start fresh with a new Terraform workspace (useful after project deletion):
```bash
./trigger-infrastructure.sh --environment dev --fresh-start --plan
```

Use staged deployment to avoid SQL instance state issues:
```bash
# First deploy project infrastructure
./trigger-infrastructure.sh --environment dev --stage project

# Then deploy services after the SQL instance is running
./trigger-infrastructure.sh --environment dev --stage services
```

The script will:
1. Automatically detect the current repository
2. Trigger the workflow with the specified parameters
3. Watch the workflow execution and show its progress

### Using the Workflow via Web Interface

1. Go to the "Actions" tab in your GitHub repository
2. Select the "Infrastructure" workflow
3. Click "Run workflow"
4. Choose the environment (dev, stg, prd)
5. Set additional options (auto-approve, plan only, fresh start)
6. Select deployment stage (project, services, all)
7. Click "Run workflow" to start the deployment

The workflow will:
- Generate terraform.tfvars from GitHub secrets
- Initialize Terraform
- Validate the configuration
- Create a plan
- Apply the changes (if plan_only is false)
- For staged deployments, it will wait for the SQL instance to be running before proceeding to services

## Environment-Specific Configuration

Each environment has its own configuration in the `environments/` directory:

- `dev/`: Development environment
- `stg/`: Staging environment
- `prd/`: Production environment

Before deploying, make sure to:

1. Set up the required GitHub secrets for the environment you want to deploy
2. For manual deployments, create a `terraform.tfvars` file in the appropriate environment directory
   (You can copy from `terraform.tfvars.example` and modify as needed)

## Common Defaults

Common configuration defaults are stored in `common/defaults.tfvars` and are automatically applied during deployment. These include:

- Service resource configurations (CPU, memory, instances)
- Database configurations
- IAM roles
- Common labels

## Troubleshooting

If you encounter issues during deployment:

1. Check that your service account has the necessary permissions
2. Verify that the required GitHub secrets are set correctly
3. Check the Terraform logs for specific error messages
4. Ensure that the required APIs are enabled in your GCP project

### SQL User Creation Issues

If you encounter errors like this during deployment:

```
Error: Error when reading or editing SQL User "rhesis" in instance "db-development-europe-west4": googleapi: Error 400: Invalid request: Invalid request since instance is not running., invalid
```

This happens because Terraform is trying to create SQL users before the SQL instance is fully operational. To resolve this:

1. **Use Staged Deployment**: 
   - First deploy just the project infrastructure: `--stage project`
   - Wait for the SQL instance to be fully running (state: RUNNABLE)
   - Then deploy the services: `--stage services`

2. **Check SQL Instance State**:
   ```bash
   gcloud sql instances describe db-development-europe-west4 --project=rhesis-dev --format="value(state)"
   ```
   The instance should be in `RUNNABLE` state before proceeding with service deployment.

3. **Why This Happens During Plan**:
   - Even during `terraform plan`, Terraform needs to read the current state of resources
   - For SQL users, it needs to check if they exist on the SQL instance
   - If the instance isn't running, this API call fails
   - This is why staged deployment is necessary even for plan operations

4. **Automated Solution**:
   - The GitHub Actions workflow handles this automatically when using `--stage all`
   - It deploys the project first, waits for the SQL instance to be ready, then deploys services
   - For manual deployments, you need to perform these steps yourself

### Container Image Issues

If you see errors like this during deployment:

```
Error: Error waiting to create Service: resource is in failed state "Ready:False", message: Revision 'service-name-00001-wsl' is not ready and cannot serve traffic. Image 'region-docker.pkg.dev/project/registry/image:latest' not found.
```

This indicates that Terraform is trying to use a container image that doesn't exist. To resolve this:

1. **Ensure Image Checking Is Working**: The workflow includes a step to check if images exist and set environment variables accordingly. Make sure this step is running without errors.

2. **Plan Regeneration**: If you've made changes to the image variables or the image checking script, you'll need to regenerate the Terraform plan to pick up these changes. Run the workflow with the `--plan` option first, then run it again to apply.

3. **Check GitHub Environment Variables**: Verify that the image variables in GitHub secrets are set correctly for the environment you're deploying to.

4. **Debug Image Values**: The deployment script logs the image variables being used. Check the workflow logs to see what values are being passed to Terraform.

5. **Force Empty Image Value**: In some cases, you may need to explicitly set an image variable to an empty string to trigger the use of the default image. You can do this by setting the corresponding GitHub secret to an empty value.

For more detailed information about the infrastructure, refer to the main `README.md` file in the infrastructure directory.

### Fresh Start and State Management

If you need to start with a fresh Terraform state (useful after deleting a project or after encountering conflicts):

1. **Using the fresh start option**:
   - Run the workflow with the `--fresh-start` flag
   - This deletes the local state files and forces a re-initialization
   - Example: `./trigger-infrastructure.sh --environment dev --fresh-start --plan`

2. **When to use fresh start**:
   - After manually deleting a GCP project that was managed by Terraform
   - When encountering state conflicts with existing or deleted resources
   - When you want to rebuild the infrastructure from scratch
   - During development and testing phases

3. **How fresh start works**:
   - Removes local Terraform state files
   - Forces Terraform to re-initialize with `-reconfigure` flag
   - Starts with a clean state while preserving backend configuration
   - This effectively clears Terraform's memory of what resources it created
   - Subsequent operations will treat all resources as new

4. **Best practices**:
   - Always run with `--plan` first to see what would be created
   - Review the plan carefully before applying
   - Consider backing up any important data before starting fresh
   - For production environments, coordinate with the team before using fresh start
   - Be aware that this may result in recreation of all resources

For more detailed information about the infrastructure, refer to the main `README.md` file in the infrastructure directory. 