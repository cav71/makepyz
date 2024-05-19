import argparse
import inspect
import sys
from pathlib import Path
import logging
import traceback

from makepyz import fileos, tasks, exceptions, text


def makepy():
    path = (Path.cwd() / "make.py").absolute()
    tasks.BASEDIR = path.parent
    return fileos.loadmod(path)


def get_parser():
    class F(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
        pass

    class MyParser(argparse.ArgumentParser):
        def parse_args(self, *args, **kwargs):
            process = kwargs.pop("process") if "process" in kwargs else None
            options = super().parse_args(*args, **kwargs)
            level = ((options.verbose or 0) - (options.quiet or 0))
            level = min(max(level, -1), 1)
            logging.basicConfig(level={
                1: logging.DEBUG,
                0: logging.INFO,
                -1: logging.WARNING,
            }[level])
            return (process(options) or options) if process else options


    parser = MyParser(formatter_class=F)
    parser.add_argument("-v", "--verbose", action="count", help="verbose messaging")
    parser.add_argument("-q", "--quiet", action="count", help="verbose messaging")
    return parser


def main():
    mod = makepy()

    def getdoc(fn):
        return (fn.__doc__.strip().partition("\n")[
            0] if fn.__doc__ else "no help available")

    commands = {getattr(mod, k).task: getattr(mod, k) for k in dir(mod) if
        getattr(getattr(mod, k), "task", None)}

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        txt = "\n".join(f"  {cmd} - {getdoc(fn)}" for cmd, fn in commands.items())
        print(  # noqa: T201
            f"""\
make.py <command> {{arguments}}

Commands:
{txt}
""", file=sys.stderr)
        sys.exit()

    #workdir = Path(__file__).parent
    try:
        command = commands[sys.argv[1]]
        sig = inspect.signature(command)
        kwargs = {}
        if "parser" in sig.parameters:
            kwargs["parser"] = get_parser()
        if "argv" in sig.parameters:
            kwargs["argv"] = sys.argv[2:]
        ba = sig.bind(**kwargs)
        command(*ba.args, **ba.kwargs)

    except exceptions.AbortExecutionError as e:
        print(f"error: {e}", file=sys.stderr)  # noqa: T201
    except Exception as e:
        message, _, explain = str(e).strip().partition("\n")
        message = message.strip()
        explain = text.indent(explain, "  ")
        tbtext = text.indent(traceback.format_exc(), "| ")

        print(tbtext, file=sys.stderr)
        print(message, file=sys.stderr)
        if explain:
            print(explain, file=sys.stderr)


if __name__ == "__main__":
    main()
