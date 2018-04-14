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

import git
import os
import sys
import json

from typing import List  # noqa, just for typing

from . import sqs


def git_check(data: dict, references: List[str] = None, repo_dir: str = None):
    repo_uri = data['source']['uri']
    if repo_dir is None:
        tmpdir = os.environ.get('TMPDIR', '/tmp')
        repo_dir = '{tmpdir}/codecommit-resource-repo-cache'.format(
            tmpdir=tmpdir)

    # full paths for included and ignored repository locations.
    # it doesn't matter if they don't exist: the comparison will harmlessly
    # fail
    paths = [os.path.abspath('%s/%s' % (repo_dir, path))
             for path in data['source'].get('paths', [])]
    ignored_paths = [os.path.abspath('%s/%s' % (repo_dir, path))
                     for path in data['source'].get('ignored_paths', [])]
    # TODO implement tag_filter and skip_ci_disabled

    repo = None  # type: git.Repo
    if os.path.exists(repo_dir) and os.path.isdir(repo_dir):
        print("Repository %s already exists in %s" % (repo_uri, repo_dir))
        repo = git.Repo(repo_dir)
    else:
        print("Cloning repository %s in %s" % (repo_uri, repo_dir))
        repo = git.Repo.init(repo_dir)
        repo.create_remote('origin', repo_uri)

    repo.remotes.origin.fetch()
    repo.head.reset('FETCH_HEAD')

    head = repo.commit('HEAD')  # type: git.Commit
    # initialised to HEAD, and updated by a valid 'ref' later
    last_version = head  # type: git.Commit

    # ref can be either the commit-id string or None
    ref = data.get('version', {}).get('ref', None)
    try:
        last_version = repo.commit(ref)
    except git.BadName:
        # ref version is not/anymore a valid commit-id, this means
        # last_version is HEAD, as the resource specs say
        pass

    # Obtain the commit ids between the current head and the last known version
    # (commit)
    c = head  # type: git.Commit
    parents = []  # type: List[git.Commit]

    while c.parents:
        def absolute(p):
            """Just a shortcut"""
            return os.path.abspath('%s/%s' % (repo_dir, p))

        is_included = True
        is_ignored = False
        if paths:
            is_included = any([absolute(path).startswith(tuple(paths))
                               for path in c.diff()])
        if ignored_paths:
            is_ignored = any([absolute(path).startswith(tuple(ignored_paths))
                              for path in c.diff()])

        if is_ignored or not is_included:
            # in a multi-parent commit, the first one is always the 'current
            # branch' one, and the others are the merged branches'
            c = c.parents[0]
        else:
            parents.append(c)
            c = c.parents[0]

        if parents[-1] == last_version:
            break

    parents.reverse()

    return [commit.hexsha for commit in parents]


def setup_credentials(data):
    credential_file = "~/.netrc"
    credential_content = "default login {username} password {password}"

    with open(os.path.expanduser(credential_file), 'w') as f:
        f.write(credential_content.format(**data['source']))


def check(instream):
    data = json.load(instream)
    source = data['source']
    print('check: requested data:', data, file=sys.stderr)
    creds = {
        'aws_access_key_id': source['aws_access_key_id'],
        'aws_secret_access_key': source['aws_secret_access_key'],
        'region_name': source['aws_region'],
    }

    setup_credentials(data)

    conf = {}
    if 'branch' in source:
        conf['branch'] = source['branch']

    references = sqs.poll_queue(source['queue'], creds, conf, debug=True)
    if references:
        references = git_check(data, references=references)
    else:
        print("No messages found in SQS", file=sys.stderr)
        references = git_check(data)

    return [{'ref': ver} for ver in references]


def main():
    response = check(sys.stdin)
    if not response:
        response = []
    print(json.dumps(response))


if __name__ == '__main__':
    main()
