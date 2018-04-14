#!/usr/bin/env python3

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
from pprint import pprint

from typing import List  # noqa, just for typing
from typing import Dict # noqa, just for typing

from . import sqs


class MyProgressPrinter(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print(op_code, cur_count, max_count, cur_count / (max_count or 100.0),
              message, file=sys.stderr)


def git_check(data: dict, references: List[Dict[str, str]] = None,
              repo_dir: str = None):
    debug = data['source'].get('debug', False)
    version = data['source'].get('version')
    if not version:
        # version is passed as None if there are no previous version, but an
        # empty dictionary playes better with how the symbol is used later
        version = {}
    repo_uri = data['source']['uri']
    if repo_dir is None:
        tmpdir = os.environ.get('TMPDIR', '/tmp')
        repo_dir = '{tmpdir}/codecommit-resource-repo-cache'.format(
            tmpdir=tmpdir)
    # TODO: resolve refs/remotes/origin/HEAD instead of hardcoding master
    branch = data['source'].get('branch', 'master')
    if debug:
        print("Branch is", branch, file=sys.stderr)

    if references is None:
        # use the head head of the branch as commit for it,
        # so repo.commit() can resolve it
        references = [{'ref': 'refs/heads/{branch}'.format(branch=branch),
                      'commit': 'refs/remotes/origin/{branch}'.format(
                          branch=branch)}]

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
        print("Repository %s already exists in %s" % (repo_uri, repo_dir),
              file=sys.stderr)
        repo = git.Repo(repo_dir)
    else:
        print("Cloning repository %s in %s" % (repo_uri, repo_dir),
              file=sys.stderr)
        repo = git.Repo.init(repo_dir)
        repo.create_remote('origin', repo_uri)

    repo.remotes.origin.fetch(progress=MyProgressPrinter())

    head = None
    for reference in references:
        ref = reference['ref']
        if ref == "refs/heads/{branch}".format(branch=branch) or \
                ref == "refs/tags/{branch}".format(branch=branch):
            head = repo.commit(reference['commit'])
            break
    if head is None:
        print("SQS passed a commit id which seems to not be valid anymore. "
              "Unless a rebase/forced push/repo manipulation happened, this "
              "seems a bug of the resource and should be investigated.",
              file=sys.stderr)
        raise RuntimeError("couldn't find commit %s" % reference['commit'])

    if debug:
        print("Checked out commit for branch is %s", head.hexsha,
              file=sys.stderr)

    repo.head.reset(head)
    # initialised to branch's HEAD, and updated by a valid 'ref' later
    last_version = head  # type: git.Commit

    # ref can be either the commit-id string or None
    ref = head
    try:
        last_version = repo.commit(ref)
    except git.BadName:
        # ref version is not/anymore a valid commit-id, this means
        # last_version is HEAD, as the resource specs say
        print("version.ref %s is not valid anymore, using branch HEAD instead "
              "(%s)" % last_version.hexsha, file=sys.stderr)

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
    debug = source.get('debug', False)
    delete_message = source.get('delete_message', True)

    if debug:
        pprint(data, stream=sys.stderr)
    creds = {
        'aws_access_key_id': source['aws_access_key_id'],
        'aws_secret_access_key': source['aws_secret_access_key'],
        'region_name': source['aws_region'],
    }

    setup_credentials(data)

    conf = {}
    if 'branch' in source:
        conf['branch'] = source['branch']

    references = sqs.poll_queue(source['queue'], creds, conf,
                                debug=debug, delete_message=delete_message)
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
