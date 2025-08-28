# Lambda GitHub Actions Deployment with Auto-Rollback

This demo shows how to deploy AWS Lambda functions using GitHub Actions with OIDC authentication, CloudWatch monitoring, and automatic rollback on failures.

## Quick Setup

### 1. Replace Placeholders

Update these files with your values:
- `.github/workflows/deploy.yml`: Replace `<YOUR_*>` placeholders
- `template.yaml`: Replace `<YOUR_*>` placeholders  
- `lambda_function.py`: Update environment-specific values

### 2. GitHub Repository Secrets

Add this secret to your GitHub repository:
- `AWS_ROLE_TO_ASSUME`: `arn:aws:iam::<YOUR_ACCOUNT_ID>:role/<YOUR_GITHUB_ROLE>`

Go to: Repository Settings → Secrets and variables → Actions → New repository secret

### 3. IAM Role Trust Policy

Create an IAM role with this trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<YOUR_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### 4. IAM Role Permissions

Attach this policy to your role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:UpdateAlias",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DeleteAlarms",
        "codedeploy:CreateDeployment",
        "codedeploy:GetDeployment"
      ],
      "Resource": "*"
    }
  ]
}
```

## Local Testing with SAM

### 1. Install SAM CLI
```bash
pip install aws-sam-cli
```

### 2. Modify template.yaml for Local Testing

Uncomment the deployment preference section in `template.yaml`:
```yaml
AutoPublishAlias: live
DeploymentPreference:
  Type: Linear10PercentEvery1Minute
  Alarms:
    - AliasErrorMetricGreaterThanZeroAlarm
```

### 3. Local Testing Commands

```bash
# Build the application
sam build

# Test locally
sam local invoke MyLambdaFunction --event event.json

# Start local API
sam local start-api

# Deploy to AWS for testing
sam deploy --guided
```

## CodeDeploy Integration with Automatic Testing

### 1. Setup CodeDeploy Application

```bash
# Create CodeDeploy application
aws deploy create-application \
  --application-name <YOUR_CODEDEPLOY_APPLICATION> \
  --compute-platform Lambda

# Create deployment group
aws deploy create-deployment-group \
  --application-name <YOUR_CODEDEPLOY_APPLICATION> \
  --deployment-group-name <YOUR_CODEDEPLOY_DEPLOYMENT_GROUP> \
  --service-role-arn arn:aws:iam::<YOUR_ACCOUNT_ID>:role/CodeDeployServiceRole \
  --auto-rollback-configuration enabled=true,events=DEPLOYMENT_FAILURE,DEPLOYMENT_STOP_ON_ALARM \
  --alarm-configuration enabled=true,alarms=[{name=<YOUR_LAMBDA_FUNCTION_NAME>-ErrorRate-Alarm}]
```

### 2. Integration Test Function (Optional)

Create a separate Lambda function for integration testing that CodeDeploy will call automatically:

```python
import boto3
import json

def lambda_handler(event, context):
    # CodeDeploy passes deployment info in event
    deployment_id = event.get('DeploymentId')
    lifecycle_event_hook_execution_id = event.get('LifecycleEventHookExecutionId')
    
    # Test your main Lambda function
    lambda_client = boto3.client('lambda')
    codedeploy_client = boto3.client('codedeploy')
    
    try:
        # Test the new version
        response = lambda_client.invoke(
            FunctionName='<YOUR_LAMBDA_FUNCTION_NAME>:live',
            Payload=json.dumps({})
        )
        
        if response['StatusCode'] != 200:
            raise Exception("Lambda invocation failed")
        
        # Signal success to CodeDeploy
        codedeploy_client.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Succeeded'
        )
        
        return {'status': 'Succeeded'}
        
    except Exception as e:
        # Signal failure to CodeDeploy
        codedeploy_client.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Failed'
        )
        
        return {'status': 'Failed', 'error': str(e)}
```

**To Enable Integration Testing:**
1. Create the integration test Lambda function above
2. Uncomment the `Hooks` section in `.github/workflows/deploy.yml`
3. Replace `<YOUR_INTEGRATION_TEST_FUNCTION>` with your test function name

**How CodeDeploy Calls Integration Lambda:**
- CodeDeploy deploys new version but doesn't shift traffic
- Calls integration lambda via `BeforeAllowTraffic` hook
- Integration lambda tests new version and reports back to CodeDeploy
- If test passes: CodeDeploy shifts traffic to new version
- If test fails: CodeDeploy stops deployment and triggers rollback

### 3. How Auto-Rollback Works

**With Integration Testing:**
1. **Deployment**: CodeDeploy deploys new version (no traffic shift yet)
2. **Integration Test**: Calls integration lambda via `BeforeAllowTraffic` hook
3. **Traffic Shift**: If test passes, gradually shifts traffic to new version
4. **Monitoring**: CloudWatch alarm monitors error rates for 5 minutes
5. **Detection**: If ≥1 error occurs in 2 consecutive minutes, alarm triggers
6. **Rollback**: Automatically reverts alias to previous version
7. **Cleanup**: Removes temporary monitoring alarm

**Without Integration Testing:**
1. **Deployment**: CodeDeploy immediately starts traffic shift to new version
2. **Monitoring**: CloudWatch alarm monitors error rates for 5 minutes
3. **Detection**: If ≥1 error occurs in 2 consecutive minutes, alarm triggers
4. **Rollback**: Automatically reverts alias to previous version
5. **Cleanup**: Removes temporary monitoring alarm

## Files

- `lambda_function.py` - Main Lambda function code
- `template.yaml` - SAM template for local testing and deployment
- `.github/workflows/deploy.yml` - GitHub Actions workflow with auto-rollback
- `requirements.txt` - Python dependencies
- `event.json` - Sample event for local testing

## Deployment Flow

1. Push code to `main` branch
2. GitHub Actions authenticates with AWS using OIDC
3. Creates deployment package
4. Deploys using CodeDeploy with blue/green strategy
5. Creates CloudWatch alarm to monitor errors
6. Monitors for 5 minutes post-deployment
7. Auto-rolls back if errors detected
8. Cleans up monitoring resources