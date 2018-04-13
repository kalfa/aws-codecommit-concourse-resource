#!/usr/bin/env python3

import sys
import boto3
import json


def poll_queue(queue_name, creds, conf, debug=False):
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
        print("Payload: %s" % m, file=sys.stderr)

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
            print("Records not in message, not AWS", file=sys.stderr)
            print(m, file=sys.stderr)
            continue

        for record in message['Records']:
            if 'codecommit' not in record:
                print("Not a CodeCommit message", file=sys.stderr)
                continue

            # [{'commit': '<id>', 'ref': "<ref>"},...]
            # where <ref> can be e.g. 'refs/heads/<branchName>',
            # 'refs/tags/<tagName'
            references = record['codecommit']['references']
            for reference in references:
                if 'branch' in conf:
                    branch_ref = 'refs/heads/{branch}'.format(
                        branch=conf['branch'])
                    tag_ref = 'refs/tags/{branch}'.format(
                        branch=conf['branch'])
                    if references['ref'].startswith((branch_ref, tag_ref)):
                        commitid = reference['commit']
                        commitids.append(commitid)
                else:
                    # if not branch has been specified, then all branches!
                    commitid = reference['commit']
                    commitids.append(commitid)

        sqs.delete_message(
            QueueUrl=q['QueueUrl'],
            ReceiptHandle=msg['ReceiptHandle'])

        return [{'ref': ref} for ref in commitids]
