#!/usr/bin/env python

# Copyright (c) 2018 Cosimo Alfarano All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import json
import tempfile
import sys

from . import sqs


def git_check(data):
    filename = tempfile.mktemp()

    with open(filename, 'w') as f:
        f.write(json.dumps(data))
    with open(filename, 'r') as f:
        return subprocess.check_call(['/opt/original_git/check'],
                                     stdin=f,
                                     shell=True)


def check(instream):
    data = json.load(instream)
    source = data['source']
    print(data, file=sys.stderr)
    creds = {
        'aws_access_key_id': source['aws_access_key_id'],
        'aws_secret_access_key': source['aws_secret_access_key'],
        'region_name': source['aws_region'],
    }
    versions = sqs.poll_queue(source['queue'], creds, debug=True)
    if not versions:
        current_version = data.get('version')
        if current_version:
            return [current_version]
        else:
            print("No previous version found, runing original git/check",
                  file=sys.stderr)
            return git_check(data)

    return versions


def main():
    response = check(sys.stdin)
    if response:
        print(json.dumps(response))


if __name__ == '__main__':
    main()
