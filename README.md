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
    aws\_access\_key\_id: {{AWS\_ACCESS\_KEY\_ID}}
    aws\_secret\_access\_key: {{AWS\_SECRET\_KEY}}
    aws\_region: {{AWS\_REGION}}

    queue: {{AWS\_QUEUE\_NAME}}
    uri: {{AWS\_CODECOMMIT\_REPO\_URL}}
    branch: master
    username: {{AWS\_HTTP\_TOKEN}}
    password: {{AWS\_HTTP\_TOKEN\_SECRET}}
```

Where:
- *queue*, *aws\_access\_key\_id*, *aws\_secret\_access\_key* and *aws\_region* are specific for this resource
- *queue* containes the AWS SQS queue name (not the URL or the ARN!), e.g., "concourse"
- any other key are the same used by the "in" or "out" script of git-resource
