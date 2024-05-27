import argparse
import contextlib
import functools
import inspect
import logging
import sys
import types
from pathlib import Path

from makepyz import cli, fileops, tasks

log = logging.getLogger(__name__)


def makepy():
    path = (Path.cwd() / "make.py").absolute()
    tasks.BASEDIR = path.parent
    return fileops.loadmod(path)


@cli.cli(parser_variables={"add_config": {"is-a-module": True}})
def main(args: argparse.Namespace, mod: types.ModuleType):
    if not mod.__file__:
        raise RuntimeError(f"mo module path for {mod}")
    tasks.BASEDIR = Path(mod.__file__).parent

    names = [
        k for k in dir(mod) if isinstance(getattr(getattr(mod, k), "task", None), str)
    ]
    commands = {}
    if "info" not in names:
        commands["info"] = tasks.info

    for name in names:
        function = getattr(mod, name)
        if "mod" in inspect.signature(function).parameters:
            function = functools.partial(function, mod=mod)
        commands[getattr(mod, name).task] = function

    if not args.arguments or args.arguments[0] not in commands:

        def getdoc(fn):
            return (
                fn.__doc__.strip().partition("\n")[0]
                if fn.__doc__
                else "no help available"
            )

        txt = "\n".join(f"  {cmd} - {getdoc(fn)}" for cmd, fn in commands.items())
        print(  # noqa: T201
            f"""\
make.py <command> {{arguments}}

Commands:
{txt}
""",
            file=sys.stderr,
        )
        raise cli.AbortExitNoTimingError()

    # you can pass arguments to a command
    # passing a `--` to avoid the main parser
    # to catch them.
    with contextlib.suppress(ValueError):
        del args.arguments[args.arguments.index("--")]

    command = commands[args.arguments[0]]
    sig = inspect.signature(command)
    kwargs = {}
    if "arguments" in sig.parameters:
        kwargs["arguments"] = args.arguments[1:]
    ba = sig.bind(**kwargs)
    command(*ba.args, **ba.kwargs)


if __name__ == "__main__":
    main()
