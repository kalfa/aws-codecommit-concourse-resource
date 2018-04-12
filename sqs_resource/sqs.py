#!/usr/bin/env python3

import sys
import boto3
import json


def poll_queue(queue_name, creds, debug=False):
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
        print("Received %s" % m, file=sys.stderr)

    if 'Messages' not in m:
        print("No Messages found", file=sys.stderr)
        return

    commitids = []
    for msg in m['Messages']:
        body = json.loads(msg['Body'])

        # The message can be passed as json code in a Message key or directly
        # within body
        # A normal CodeCommit trigger will not use Message, but a manually
        # generated message might.
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
            else:
                references = record['codecommit']['references']
                for reference in references:
                    commitid = reference['commit']
                    commitids.append(commitid)

        sqs.delete_message(
            QueueUrl=q['QueueUrl'],
            ReceiptHandle=msg['ReceiptHandle'])

        return [{'ref': ref} for ref in commitids]
