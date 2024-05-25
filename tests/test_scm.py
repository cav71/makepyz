import contextlib
import subprocess

import pytest

from makepyz import scm


def test_clone(tmp_path):
    from configparser import ConfigParser, ParsingError

    repo = scm.clone("https://github.com/cav71/makepyz.git", tmp_path / "master")
    assert repo.branch() == "master"
    assert (repo.workdir / "pyproject.toml").exists()
    config = ConfigParser(strict=False)
    with contextlib.suppress(ParsingError):
        config.read(repo.workdir / "pyproject.toml")
    assert "build-system" in config.sections()
    assert config.options("project")
    assert config.get("project", "name").strip('"') == "makepyz"


def test_lookup(git_project_factory, monkeypatch):
    repo = git_project_factory().create("0.0.0")
    dstdir = repo.workdir / "a" / "b" / "c"
    dstdir.mkdir(parents=True)
    (dstdir / "out.txt").touch()
    assert (dstdir / "out.txt").exists()
    repofound = scm.lookup(dstdir)
    assert repofound
    assert str(repofound.workdir) == f"{repo.workdir}"
    assert scm.lookup(dstdir.parent.parent.parent.parent) is None

    # verify we can lookup with a relative path
    monkeypatch.chdir(repo.workdir)
    repofound = scm.lookup(dstdir.relative_to(repo.workdir))
    assert repofound
    assert str(repofound.workdir) == f"{repo.workdir}"


def test_basic_scm_operations(git_project_factory):
    repo = git_project_factory("test_check_version-repo").create("0.0.0")
    assert not repo.status()

    path = repo.workdir / "new-file.txt"
    path2 = repo.workdir / "renamed-file.txt"

    # 1. add new untracked file
    path.write_text("Hello")
    assert repo.status() == {"new-file.txt": 128}

    # 2. track file
    repo(["add", path.name])
    assert repo.status() == {"new-file.txt": 1}

    # 3. commit file
    repo.commit(path.name, "added new file")
    assert not repo.status()

    # 4. delete file
    path.unlink()
    assert repo.status() == {"new-file.txt": 512}

    # 5. restore file
    path.write_text("Hello")
    assert not repo.status()

    # 6. rename file
    repo(["mv", path.name, path2.name])
    # path.unlink()
    # path2.write_text("Hello")
    assert repo.status() == {"new-file.txt -> renamed-file.txt": 5}

    # 7. modify renamed file
    path2.write_text("Hello World")
    assert repo.status() == {"new-file.txt -> renamed-file.txt": 261}

    # 8. restore (the wrong way)
    path.write_text("Hello")
    path2.unlink()
    assert repo.status() == {
        "new-file.txt -> renamed-file.txt": 261,
        "new-file.txt": 128,
    }

    # 9. restore (proper way)
    repo(["restore", "--staged", path.name, path2.name])
    assert not repo.status()


def test_handle_remote_and_local_repos(git_project_factory):
    "test branch handling across repos"

    def check_branches(repo):
        srepo = scm.GitRepo(repo.workdir)
        assert set(repo.branches.local) == set(srepo.branches.local)
        assert set(repo.branches.remote) == set(srepo.branches.remote)

    # Create a repository with two beta branches tagged
    repo = git_project_factory("test_check_version-repo").create("0.0.0")
    repo.branch("beta/0.0.3")
    repo(["tag", "-m", "release", "release/0.0.3"])

    repo.branch("beta/0.0.4")
    repo(["tag", "-m", "release", "release/0.0.4"])
    repo(["checkout", "master"])
    assert (
        repo.dumps(mask=True)
        == f"""\
REPO: {repo.workdir}
 [status]
  On branch master
  nothing to commit, working tree clean

 [branch]
    beta/0.0.3 ABCDEFG [master] initial commit
    beta/0.0.4 ABCDEFG [master] initial commit
  * master     ABCDEFG initial commit

 [tags]
  release/0.0.3
  release/0.0.4

 [remote]

"""
    )
    check_branches(repo)

    # Clone from repo and adds a new branch
    repo1 = git_project_factory("test_check_version-repo1").create(clone=repo)
    repo1.branch("beta/0.0.2")
    assert (
        repo1.dumps(mask=True)
        == f"""\
REPO: {repo1.workdir}
 [status]
  On branch beta/0.0.2
  Your branch is up to date with 'master'.

  nothing to commit, working tree clean

 [branch]
  * beta/0.0.2                ABCDEFG [master] initial commit
    master                    ABCDEFG [origin/master] initial commit
    remotes/origin/HEAD       -> origin/master
    remotes/origin/beta/0.0.3 ABCDEFG initial commit
    remotes/origin/beta/0.0.4 ABCDEFG initial commit
    remotes/origin/master     ABCDEFG initial commit

 [tags]
  release/0.0.3
  release/0.0.4

 [remote]
  origin	{repo.workdir} (fetch)
  origin	{repo.workdir} (push)

"""
    )
    check_branches(repo1)

    # Clone from repo, adds a new branch and adds repo1 as remote
    project = git_project_factory().create(clone=repo)
    project.branch("beta/0.0.1", "origin/master")
    # master branch is already present
    pytest.raises(
        subprocess.CalledProcessError, project.branch, "master", "origin/master"
    )

    project(["remote", "add", "repo1", repo1.workdir])
    project(["fetch", "--all"])

    assert (
        project.dumps(mask=True)
        == f"""\
REPO: {project.workdir}
 [status]
  On branch beta/0.0.1
  Your branch is up to date with 'origin/master'.

  nothing to commit, working tree clean

 [branch]
  * beta/0.0.1                ABCDEFG [origin/master] initial commit
    master                    ABCDEFG [origin/master] initial commit
    remotes/origin/HEAD       -> origin/master
    remotes/origin/beta/0.0.3 ABCDEFG initial commit
    remotes/origin/beta/0.0.4 ABCDEFG initial commit
    remotes/origin/master     ABCDEFG initial commit
    remotes/repo1/beta/0.0.2  ABCDEFG initial commit
    remotes/repo1/master      ABCDEFG initial commit

 [tags]
  release/0.0.3
  release/0.0.4

 [remote]
  origin	{repo.workdir} (fetch)
  origin	{repo.workdir} (push)
  repo1	{repo1.workdir} (fetch)
  repo1	{repo1.workdir} (push)

"""
    )
    check_branches(project)

    repox = scm.GitRepo(project.workdir)
    assert project.dumps() == repox.dumps()


def test_detached_head(git_project_factory):
    repo = git_project_factory("test_detached_head-repo").create("0.0.0")
    assert repo(["symbolic-ref", "HEAD"]).strip() == "refs/heads/master"
    assert not repo.detached

    repo1 = git_project_factory("test_check_version-repo1").create(clone=repo)
    assert repo1(["symbolic-ref", "HEAD"]).strip() == "refs/heads/master"
    assert not repo1.detached

    ref = repo1(["rev-parse", "refs/heads/master"]).strip()
    (repo1.workdir / ".git/HEAD").write_text(ref)
    pytest.raises(subprocess.CalledProcessError, repo1, ["symbolic-ref", "HEAD"])
    assert repo1.detached
