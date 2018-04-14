This uses the _in_ and _out_ scripts from the official Concourse
git-resource, but reimplements (by replacing!) the _check_ script.

Use this resource at your own risk, it's not in production state yet.
At the moment just a limited set of functionalities is implemented, and probably they won't work anyway ;-)

 - Git access only via HTTP[S].
 - no paths/ignore_paths support
 - no ci_skip_disabled support
 - no tag_filter

Substantially what's (partially) implemented is what's in the YAML example below.

It wasn't meant to be, but it's becoming a python re-implementation of the original git-resource.

Changes from the official git-resource:
the 'branch' configuration key works (i.e. will work) in a different way, it's not yet decided how, but probably will check all the branches, unless one is specified explicitely.

It also requires both HTTP user/password and AWS credentials since it needs to access CodeCommit repository and authenticate to SQS.

If at least a SQS Message from CodeCommit is found, then if will return the
references between the last reference and such commit(s).
Since SQS payload doesn't specifies the reference of the branch which has been committed, but instead returns a list of refecences for all heads/tags present, there is no real way to understand only from SQS what has been done.
So a strategy will be implemented (it's in the TODO list) to merge the semantic of the 'branch' configuration key and the SQS payload


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

