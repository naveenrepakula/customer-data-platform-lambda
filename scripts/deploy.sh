#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-ap-south-1}"
STACK_NAME="${STACK_NAME:-customer-data-platform-${ENVIRONMENT}}"
sam build --template-file infrastructure/template.yaml
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "Environment=${ENVIRONMENT}" \
  --no-confirm-changeset
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" --query 'Stacks[0].Outputs'
