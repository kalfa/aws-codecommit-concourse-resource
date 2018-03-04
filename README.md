This implements (copy!) the in and out scripts from the official Concourse
git-resource, but reimplements the 'check' script by polling AWS SQS for
CodeCommit messages.

If at least SQS Message from CodeCommit is found, then if will return the
references for such commit(s), which will be passed by Concourse to the
git-resource 'in' script

```
resources:
- name: test-git
  type: aws-sqs
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
- queue, aws_access_key_id, aws_secret_access_key and aws_region are specific for this resource
- queue containes the queue name (not the URL or the ARN!), e.g., "concourse"
- any other key are the same required by the "in" or "out" script of git-resource
