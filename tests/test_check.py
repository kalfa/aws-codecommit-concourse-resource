import git
from unittest.mock import patch, Mock, call

from sqs_resource.check import git_check


data = {
    'source': {
        'uri': 'http://fake.it',
    },
}


class Commit(Mock):
    def __init__(self, cid):
        super(Commit, self).__init__(spec=git.Commit)
        self.hexsha = str(cid)
        self.parents = []

    def diff(self):
        return (Mock(), Mock())

    def __repr__(self):
        return '<Commit %s>' % self.hexsha


def generate_commit_log(first, lenght=10):
    """
    >>> generate_commit_log(Commit('HEAD'))
    [<Commit HEAD>, <Commit 0>, <Commit 1>, <Commit 2>, <Commit 3>, <Commit 4>, <Commit 5>, <Commit 6>, <Commit 7>, <Commit 8>]

    >>> generate_commit_log(Commit('FOO'), lenght=1)
    [<Commit FOO>]

    >>> generate_commit_log(Commit('BAR'), lenght=2)
    [<Commit BAR>, <Commit 0>]
    """  # noqa
    current = first
    retval = []
    for i in range(lenght):
        new = Commit(str(i))
        current.parents = [new]
        retval.append(current)
        current = new
    return retval


# A generated history or a fake repository
LOG = generate_commit_log(Commit('HEAD'))
LOG_REVERSE = LOG[:]
LOG_REVERSE.reverse()


def Repo_commit(cid: str, log=None) -> Commit:
    """Returns a Commit instance if the commitid exists in the logs

    Raises git.BadName if the commitid does not exist in the log.

    The log can be passed as a list of Commit instances, if it's not passed
    If no log is passed, the global symbol LOG is used instead

    >>> LOG = generate_commit_log(Commit('HEAD'), lenght=2)
    >>> LOG2 = generate_commit_log(Commit('HEAD2'), lenght=1)

    >>> Repo_commit('HEAD2', log=LOG2)
    <Commit HEAD2>
    >>> Repo_commit('1', log=LOG2)
    Traceback (most recent call last):
      ...
    gitdb.exc.BadName: Ref '1' did not resolve to an object

    >>> Repo_commit('HEAD')
    <Commit HEAD>
    >>> Repo_commit('1')
    <Commit 1>
    >>> Repo_commit('I do not exit in LOG')
    Traceback (most recent call last):
      ...
    gitdb.exc.BadName: Ref 'I do not exit in LOG' did not resolve to an object

    """
    if log is None:
        log = LOG

    if cid is None:
        return log[0]

    log_dict = {obj.hexsha: obj for obj in log}

    if cid in log_dict:
        return log_dict[cid]
    else:
        raise git.BadName(cid)


@patch('sqs_resource.check.os.environ')
@patch('sqs_resource.check.git.Repo', autospec=True,
       return_value=Mock(
           commit=Mock(side_effect=Repo_commit)))
def test_git_check_with_repo_dir_existing(Repo, os, fs):
    git_check(data, [], repo_dir='/')
    Repo.assert_called_once_with('/')
    assert Repo.return_value.create_remote.call_count == 0

    # the repository is fetched
    Repo.return_value.remotes.origin.fetch.assert_called_once_with()
    # and the current HEAD is reset to the just fetched one
    Repo.return_value.head.reset.assert_called_once_with('FETCH_HEAD')


@patch('sqs_resource.check.os.environ')
@patch('sqs_resource.check.git.Repo', autospec=True)
def test_git_check_with_repo_dir_not_existing(Repo, os, fs):
    # have the cycle through the log history end immediately
    Repo.init.return_value.commit.return_value.parents = []
    git_check(data, [], repo_dir='/foo')

    Repo.init.assert_called_once_with('/foo')
    Repo.init.return_value.create_remote.assert_called_once_with(
        'origin',
        data['source']['uri'])

    # the repository is fetched
    Repo.init.return_value.remotes.origin.fetch.assert_called_once_with()
    # and the current HEAD is reset to the just fetched one
    Repo.init.return_value.head.reset.assert_called_once_with('FETCH_HEAD')


@patch('sqs_resource.check.os.environ')
@patch('sqs_resource.check.git.Repo', autospec=True,
       return_value=Mock(
           commit=Mock(side_effect=Repo_commit)))
def test_git_check_commit_history_is_retuned_with_data_having_version(Repo,
                                                                      os,
                                                                      fs):
    data_with_version = data.copy()
    data_with_version['version'] = {'ref': '2'}
    result = git_check(data_with_version, [], repo_dir='/')

    commit = Repo.return_value.commit
    assert commit.call_args_list.count(call('HEAD')) == 1
    assert commit.call_args_list.count(call('2')) == 1

    # version.ref = '2', so the result will include only HEAD and first and
    # second child, since the third child '2' is already known and won't be
    # included
    expected_result = [c.hexsha for c in LOG][:4]
    expected_result.reverse()
    assert result == expected_result
    # The version passed by version.ref should be included
    assert Repo_commit('2').hexsha in result


@patch('sqs_resource.check.os.environ')
@patch('sqs_resource.check.git.Repo', autospec=True,
       return_value=Mock(
           commit=Mock(side_effect=Repo_commit)))
def test_git_check_commit_history_is_retuned_with_data_no_version(Repo,
                                                                  os,
                                                                  fs):
    commit = Repo.return_value.commit
    result = git_check(data, [], repo_dir='/')

    # since version does not exist, the last known version becomes HEAD, hence
    # two calls to repo.commit(None)
    assert commit.call_args_list.count(call('HEAD')) == 1

    # version.ref = '2', so the result will include only HEAD and first and
    # second child, since the third child '2' is already known and won't be
    # included
    assert result == [LOG[0].hexsha]


@patch('sqs_resource.check.os.environ')
@patch('sqs_resource.check.git.Repo', autospec=True,
       return_value=Mock(
           commit=Mock(side_effect=Repo_commit)))
def test_git_check_commit_history_is_retuned_with_invalid_version(Repo,
                                                                  os,
                                                                  fs):
    data_with_version = data.copy()
    data_with_version['version'] = {'ref': 'invalid'}
    result = git_check(data_with_version, [], repo_dir='/')

    commit = Repo.return_value.commit
    assert commit.call_args_list.count(call('HEAD')) == 1
    assert commit.call_args_list.count(call('invalid')) == 1

    # version.ref = '2', so the result will include only HEAD and first and
    # second child, since the third child '2' is already known and won't be
    # included
    assert result == [Repo_commit('HEAD').hexsha]
