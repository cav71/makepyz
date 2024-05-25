import argparse
import inspect
import logging
import sys
from pathlib import Path

from makepyz import cli, fileops, tasks

log = logging.getLogger(__name__)


def process_args(args: argparse.Namespace):
    if not args.config.exists():
        raise cli.AbortWrongArgumentError(f"missing config file {args.config}")


def makepy():
    path = (Path.cwd() / "make.py").absolute()
    tasks.BASEDIR = path.parent
    return fileops.loadmod(path)


@cli.cli(process_args=process_args)
def main(args: argparse.Namespace):
    log.info("loading make.py file %s", args.config)
    mod = makepy()

    def getdoc(fn):
        return (
            fn.__doc__.strip().partition("\n")[0] if fn.__doc__ else "no help available"
        )

    commands = {
        getattr(mod, k).task: getattr(mod, k)
        for k in dir(mod)
        if isinstance(getattr(getattr(mod, k), "task", None), str)
    }

    if not args.arguments or args.arguments[0] not in commands:
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

    # try:
    command = commands[args.arguments[0]]
    sig = inspect.signature(command)
    kwargs = {}
    if "arguments" in sig.parameters:
        kwargs["arguments"] = args.arguments[1:]
    ba = sig.bind(**kwargs)
    command(*ba.args, **ba.kwargs)
    # except cli.AbortCliError:
    #     raise
    # except exceptions.AbortExecutionError as e:
    #     print(f"error: {e}", file=sys.stderr)  # noqa: T201
    # except Exception as e:
    #     message, _, explain = str(e).strip().partition("\n")
    #     message = message.strip()
    #     explain = text.indent(explain, "  ")
    #     tbtext = text.indent(traceback.format_exc(), "| ")
    #
    #     print(tbtext, file=sys.stderr)
    #     print(message, file=sys.stderr)
    #     if explain:
    #         print(explain, file=sys.stderr)


if __name__ == "__main__":
    main()
