#!/usr/bin/env python3

import sys
import boto3
import json
from pprint import pprint


def poll_queue(queue_name, creds, conf, debug=False, delete_message=True):
    """Return a version for each refs in the tree

    The return object is [{'ref': '<commitid>'}]
    """
    sqs = boto3.client('sqs', **creds)

    q = sqs.create_queue(
        QueueName=queue_name,
    )
    m = sqs.receive_message(
        QueueUrl=q['QueueUrl'],
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=0,
        WaitTimeSeconds=0,
    )

    print("Receive from", q['QueueUrl'], file=sys.stderr)
    if debug:
        print("DEBUG: Payload:", file=sys.stderr)
        pprint(m, stream=sys.stderr)

    if 'Messages' not in m:
        return

    commitids = []
    for msg in m['Messages']:
        body = json.loads(msg['Body'])

        # The message can be passed as json code in a Message key or directly
        # within body
        # A normal CodeCommit trigger will not use Message, but a manually
        # generated message might.
        # <https://docs.aws.amazon.com/codecommit/latest/userguide/how-to-notify-sns.html>
        # point 5 for an example of a CC trigger payload by SNS (then pass
        # passed to SQS)
        try:
            message = json.loads(body['Message'])
        except KeyError:
            message = body

        if 'Records' not in message:
            print("Records key not in message, "
                  "it's not probably a SQS message", file=sys.stderr)
            if debug:
                pprint(msg, stream=sys.stderr)
            continue

        for record in message['Records']:
            # [{'commit': '<id>', 'ref': "<ref>"},...]
            # where <ref> can be e.g. 'refs/heads/<branchName>',
            # 'refs/tags/<tagName'
            customData = record.get('customData')
            wanted_customData = conf.get('customData')
            if wanted_customData and customData != wanted_customData:
                print("received customData='%s' not matching with "
                      "configured '%s': message not considered." % (
                          customData, wanted_customData),
                      file=sys.stderr)
                continue

            if record.get('eventSource') == "aws:codecommit":
                repository_arn = record.get('eventSourceARN')
                wanted_repository_arn = conf.get('repository_arn', None)
                if wanted_repository_arn and \
                        repository_arn != wanted_repository_arn:
                    print("received repository_arn='%s' not matching with "
                          "configured '%s': message not considered." % (
                              repository_arn, wanted_repository_arn),
                          file=sys.stderr)
                    continue

            if 'codecommit' not in record:
                print("Not a CodeCommit message", file=sys.stderr)
                if debug:
                    pprint(msg, stream=sys.stderr)
                continue
            references = record['codecommit']['references']
            for reference in references:
                if conf.get('branch'):
                    print("Considering only refs for "
                          "{branch}".format(**conf),
                          file=sys.stderr)
                    branch_ref = 'refs/heads/{branch}'.format(**conf)
                    tag_ref = 'refs/tags/{branch}'.format(**conf)
                    if reference['ref'].startswith((branch_ref, tag_ref)):
                        commitids.append(reference)
                else:
                    print("Considering all branches", file=sys.stderr)
                    # if not branch has been specified, then all branches!
                    commitids.append(reference)

    pprint(commitids, stream=sys.stderr)
    if delete_message:
        print("Deleting SQS message", file=sys.stderr)
        sqs.delete_message(
            QueueUrl=q['QueueUrl'],
            ReceiptHandle=msg['ReceiptHandle'])
    else:
        print("Not deleting SQS message", file=sys.stderr)

    return commitids
