# AWS Terraform

This configuration creates billable resources. Do not run `terraform apply` until a reviewed plan,
current regional price estimate, explicit owner approval, and teardown time are recorded.

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check -recursive
terraform validate
checkov --directory . --framework terraform
terraform plan -out expenseguard.tfplan
terraform show -no-color expenseguard.tfplan > plan.txt
```

The image input must be an ECR URI pinned by digest. Build and push the image before planning, then
run migrations as a one-off ECS task using the deployed task definition with an `alembic upgrade
head` command override. Administrator bootstrap remains interactive and should be performed through
a controlled, audited procedure rather than a public endpoint.

After smoke tests and CloudWatch/CloudTrail evidence collection:

```bash
terraform destroy
```

Confirm ECS, ALB, NAT gateway, RDS, EIP, S3 objects/buckets, and retained snapshots are absent. The
lab uses one NAT gateway and single-AZ RDS; this is a cost decision, not the production reference.

