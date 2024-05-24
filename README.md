# makepyz - the makefile alternative

## Intro

`makepyz` is a simple tool to collect task in a `make.py` file, in the same
spirit of a `Makefile`: it allows you to write portable tasks in python
leveraging an extensive internal library.

## Install

There are two ways to install it, in standalone mode (eg. no dependencies)
good for project that want to not rely on the [makepyz](https://github.com/cav71/makepyz)
project (or they want to keep a tight control on third parties code),
and the usual `pip` installed [package](https://pypi.org/project/makepyz).


### Using pip

You can use pip to install [makepyz](https://github.com/cav71/makepyz):

```shell
pip install makepyz
```

### Stand alone

In standalone mod you can just get the latest `makepyz`:

```shell
curl -LO https://github.com/cav71/makepyz/raw/master/makepyz
```

```shell
echo hello
```

## Using

First you need to create a `make.py` file:

```python
from makepyz import api

@api.task()
def info(arguments: list[str]):
    """this is the hello world"""
    print(  # noqa: T201
        f"""
    Hi!
    python: {sys.executable}
    version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
    cwd: {Path.cwd()}
    arguments: {arguments}
    """)
```

Then:
```shell
makepyz
```


## API

**api.task** - decorates a new makepyz task.

Example:
```python
from make import api

@api.task()
def hello():
    print("Hello world")
```


**api.which** - finds an executablek.
Example:
```python
from make import api

print(api.which("dir"))
```
