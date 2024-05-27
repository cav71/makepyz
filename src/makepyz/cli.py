"""cli utilities"""

from __future__ import annotations

import argparse
import contextlib
import functools
import inspect
import logging
import sys
import time
import types
from pathlib import Path
from typing import Any, Callable

# SPECIAL MODULE LEVEL VARIABLES
MODULE_VARIABLES: dict[str, Any] = {
    "LOGGING_CONFIG": None,
    "CONFIGPATH": Path("make.py"),
    "BUILDDIR": Path("build"),
}


log = logging.getLogger(__name__)


Callback = Callable[[argparse.Namespace, list[str]], None]


class CliBaseError(Exception):
    pass


class AbortCliError(CliBaseError):
    pass


class AbortWrongArgumentError(CliBaseError):
    pass


class AbortExitNoTimingError(CliBaseError):
    pass


class Optional:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


def resolve(mod: types.ModuleType, var: str, options: argparse.Namespace) -> Any:
    # sources:
    # 1. cli
    if not isinstance(getattr(options, var), Optional):
        value = getattr(options, var)
    # 2. mod
    elif hasattr(mod, var):
        value = getattr(mod, var)
    # 3. fallback
    elif var in MODULE_VARIABLES:
        value = MODULE_VARIABLES[var]
    else:
        raise RuntimeError(f"cannot resolve {var}")
    return value


def setup_logging(config: dict[str, Any], count: int) -> None:
    levelmap = [
        logging.WARNING,
        logging.INFO,
        logging.DEBUG,
    ]
    n = len(levelmap)

    # awlays start from info level
    level = logging.INFO

    # we can set the default start log level in LOGGING_CONFIG
    if config.get("level", None) is not None:
        level = config["level"]

    # we control if we go verbose or quite here
    index = levelmap.index(level) + count
    config["level"] = levelmap[max(min(index, n - 1), 0)]
    logging.basicConfig(**config)


def add_config(parser: MakepyzParser, var: str = "CONFIGPATH") -> Callback:
    # we add the -c|--config flag to point to a config file
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        default=MODULE_VARIABLES[var],
        help="path to a config file",
    )

    def callback(
        options: argparse.Namespace,
        _: list[str],
    ):
        from makepyz.fileops import loadmod

        options.config = Path(options.config).expanduser().absolute()
        is_a_module = parser.parser_variables.get("add_config", {}).get(
            "is-a-module", False
        )

        if hasattr(options, "mod"):
            raise RuntimeError("mod is a reserved dest for options")
        options.mod = None
        if is_a_module:
            if not options.config.exists():
                raise AbortWrongArgumentError(f"missing config file {options.config}")
            options.mod = loadmod(options.config)
            if hasattr(options.mod, var):
                raise RuntimeError(f"cannot define {var} in {options.config}")

    return callback


def add_builddir(parser: MakepyzParser, var: str = "BUILDDIR") -> Callback:
    # we source the default:
    #  1. from module
    #  2. from this file in MODULE_VARIABLES
    # we evaluate the arguments on the cli and we set the module.BUILDDIR
    path = Path(MODULE_VARIABLES[var]).expanduser().absolute()

    parser.add_argument(
        "--build-dir",
        dest=var,
        default=Optional(path),
        type=Path,
        help="path to the output builddir",
    )

    def callback(
        options: argparse.Namespace,
        _: list[str],
    ):
        if options.mod:
            value = Path(resolve(options.mod, var, options)).expanduser().absolute()
            setattr(options.mod, var, value)
        delattr(options, var)

    return callback


def add_logging(parser: MakepyzParser, var: str = "LOGGING_CONFIG") -> Callback:
    # we're adding the -v|-q flags, to control the logging level
    parser.add_argument(
        "-v", "--verbose", action="count", help="report verbose logging"
    )
    parser.add_argument("-q", "--quiet", action="count", help="report quiet logging")

    def callback(
        options: argparse.Namespace,
        _: list[str],
    ):
        # setup the logging
        config = (MODULE_VARIABLES[var] or {}).copy()

        # updating with vars from the module
        if options.mod:
            config.update(getattr(options.mod, var, {}))

        count = (options.verbose or 0) - (options.quiet or 0)
        setup_logging(config, count)
        delattr(options, "verbose")
        delattr(options, "quiet")

    return callback


class MakepyzParser(argparse.ArgumentParser):
    def __init__(self, parser_variables: dict[str, Any] | None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.parser_variables = parser_variables or {}

        self.callbacks: list[Callback | None] = []

        # add the -c|--config flag
        self.callbacks.append(add_config(self))

        # adds the --verbose|--quiet flags
        self.callbacks.append(add_logging(self))

        # we add the "--build-dir" flag to point to a config file
        self.callbacks.append(add_builddir(self))

    def error(self, message):
        raise AbortWrongArgumentError(message)

    def parse_args(  # type: ignore
        self,
        args: list[str] | None = None,
        namespace: argparse.Namespace | None = None,
        module: types.ModuleType | None = None,
    ):
        # options = super().parse_args(args, namespace)
        options, arguments = super().parse_known_args(args, namespace)

        if hasattr(options, "mod"):
            raise RuntimeError("options has a .mod attribute (it's internal)")

        for callback in self.callbacks:
            if not callback:
                continue
            callback(options, arguments)

        if hasattr(options, "arguments"):
            raise RuntimeError("options has arguments attribute")
        options.arguments = arguments
        return options

    @classmethod
    def get_parser(cls, parser_variables: dict[str, Any] | None = None, **kwargs):
        class Formatter(
            argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter
        ):
            pass

        return cls(
            parser_variables=parser_variables, formatter_class=Formatter, **kwargs
        )


@contextlib.contextmanager
def setup(
    module: types.ModuleType | None,
    function: Callable,
    add_arguments: Callable[[argparse.ArgumentParser], None] | None = None,
    process_args: (
        Callable[[argparse.Namespace], argparse.Namespace | None] | None
    ) = None,
    parser_variables: dict[str, Any] | None = None,
):
    sig = inspect.signature(function)

    if "args" in sig.parameters and "parser" in sig.parameters:
        raise RuntimeError("cannot use args and parser at the same time")

    description, _, epilog = (
        (function.__doc__ or module.__doc__ or "").strip().partition("\n")
    )
    kwargs = {}
    parser = MakepyzParser.get_parser(
        parser_variables, description=description, epilog=epilog
    )
    if add_arguments:
        add_arguments(parser)

    if "parser" in sig.parameters:
        kwargs["parser"] = parser

    if "callbacks" in sig.parameters:
        kwargs["callbacks"] = parser.callbacks

    t0 = time.monotonic()
    status = "completed"
    errormsg = ""
    show_timing = True
    try:
        if "parser" not in sig.parameters:
            args = parser.parse_args(module=module)
            if process_args:
                args = process_args(args) or args
            if "args" in sig.parameters:
                kwargs["args"] = args
            if "mod" in sig.parameters:
                kwargs["mod"] = args.mod
        yield sig.bind(**kwargs)
    except AbortCliError as exc:
        errormsg = str(exc)
        status = "failed"
    except AbortWrongArgumentError as exc:
        show_timing = False
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: {exc.args[0]}", file=sys.stderr)
        sys.exit(2)
    except AbortExitNoTimingError:
        show_timing = False
        sys.exit(0)
    except Exception:
        log.exception("un-handled exception")
        status = "failed"
    finally:
        if show_timing:
            delta = round(time.monotonic() - t0, 2)
            log.info("task %s in %.2fs", status, delta)

    if errormsg:
        parser.error(errormsg)
    if status == "failed":
        sys.exit(2)


def cli(
    add_arguments: Callable[[argparse.ArgumentParser], None] | None = None,
    process_args: (
        Callable[[argparse.Namespace], argparse.Namespace | None] | None
    ) = None,
    parser_variables: dict[str, Any] | None = None,
):
    def _cli1(function):
        module = inspect.getmodule(function)

        def log_sys_info(ba):
            path = getattr(
                getattr(
                    (ba.args or [argparse.Namespace()])[0], "mod", argparse.Namespace()
                ),
                "__file__",
                "N/A",
            )
            log.info("system: %s, %s, %s", sys.executable, sys.version, path)

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def _cli2(*args, **kwargs):
                with setup(
                    module, function, add_arguments, process_args, parser_variables
                ) as ba:
                    log_sys_info(ba)
                    return await function(*ba.args, **ba.kwargs)

        else:

            @functools.wraps(function)
            def _cli2(*args, **kwargs):
                with setup(
                    module, function, add_arguments, process_args, parser_variables
                ) as ba:
                    log_sys_info(ba)
                    return function(*ba.args, **ba.kwargs)

        _cli2.attributes = {  # type: ignore
            "doc": function.__doc__ or module.__doc__ or "",
        }
        return _cli2

    return _cli1
