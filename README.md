This implements (by copying!) the _in_ and _out_ scripts from the official Concourse
git-resource, but reimplements (by replacing!) the _check_ script.

If at least a SQS Message from CodeCommit is found, then if will return the
references for such commit(s), which will be passed by Concourse to the
git-resource 'in' script.

```
resource_types:
- name: aws-codecommit
  type: docker-image
  source:
    repository: kalfa/aws-codecommit-concourse-resource

resources:
- name: my-codecommit-repo
  type: aws-codecommit
  source:
    aws_access_key_id: {{AWS_ACCESS_KEY_ID}}
    aws_secret_access_key: {{AWS_SECRET_KEY}}
    aws_region: {{AWS_REGION}}

    queue: {{AWS_QUEUE_NAME}}
    uri: {{AWS_CODECOMMIT_REPO_URL}}
    branch: master
    username: {{AWS_HTTP_TOKEN}}
    password: {{AWS_HTTP_TOKEN_SECRET}}
```

Where:
- *queue*, *aws\_access\_key\_id*, *aws\_secret\_access\_key* and *aws\_region* are specific for this resource
- *queue* containes the AWS SQS queue name (not the URL or the ARN!), e.g., "concourse"
- any other key are the same used by the "in" or "out" script of git-resource
