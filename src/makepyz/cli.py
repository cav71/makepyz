"""cli utilities
"""

from __future__ import annotations

import os
import sys
import contextlib
import inspect
import logging
import time
from pathlib import Path
import functools
import argparse
from typing import Callable, Any


# SPECIAL MODULE LEVEL VARIABLES
MODULE_VARIABLES : dict[str, Any] = {
    "LOGGING_CONFIG": None,
    "CONFIGPATH": Path("make.py"),
}


log = logging.getLogger(__name__)


class CliBaseError(Exception):
    pass


class AbortCliError(CliBaseError):
    pass


class AbortWrongArgumentError(CliBaseError):
    pass


class AbortExitNoTimingError(CliBaseError):
    pass


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


class LuxosParser(argparse.ArgumentParser):
    def __init__(self, module_variables, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.module_variables = module_variables or {}

        # we're adding the -v|-q flags, to control the logging level
        self.add_argument(
            "-v", "--verbose", action="count", help="report verbose logging"
        )
        self.add_argument("-q", "--quiet", action="count", help="report quiet logging")

        # we add the -c|--config flag to point to a config file
        configpath = Path(
            self.module_variables.get("CONFIGPATH") or MODULE_VARIABLES["CONFIGPATH"]
        )
        configpath = Path(configpath).expanduser().absolute()
        if configpath.is_relative_to(Path.cwd()):
            configpath = configpath.relative_to(Path.cwd())

        self.add_argument(
            "-c",
            "--config",
            default=configpath,
            type=Path,
            help="path to a config file",
        )

    def parse_args(self, args=None, namespace=None):
        options = super().parse_args(args, namespace)

        # we provide an error function to nicely bail out the script
        def error(msg):
            raise AbortWrongArgumentError(msg)

        self.error = error
        options.error = self.error

        # setup the logging
        config = {}
        if value := self.module_variables.get("LOGGING_CONFIG"):
            config = value.copy()

        count = (options.verbose or 0) - (options.quiet or 0)
        setup_logging(config, count)

        return options

    @classmethod
    def get_parser(cls, module_variables, **kwargs):
        class Formatter(
            argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter
        ):
            pass

        return cls(
            module_variables=module_variables, formatter_class=Formatter, **kwargs
        )


def cli(
    add_arguments: Callable[[argparse.ArgumentParser], None] | None = None,
    process_args: (
        Callable[[argparse.Namespace], argparse.Namespace | None] | None
    ) = None,
):
    def _cli1(function):
        module = inspect.getmodule(function)

        @contextlib.contextmanager
        def setup():
            sig = inspect.signature(function)

            module_variables = MODULE_VARIABLES.copy()
            for name in list(module_variables):
                module_variables[name] = getattr(module, name, None)

            if "args" in sig.parameters and "parser" in sig.parameters:
                raise RuntimeError("cannot use args and parser at the same time")

            description, _, epilog = (
                (function.__doc__ or module.__doc__ or "").strip().partition("\n")
            )
            kwargs = {}
            parser = LuxosParser.get_parser(
                module_variables, description=description, epilog=epilog
            )
            if add_arguments:
                add_arguments(parser)

            if "parser" in sig.parameters:
                kwargs["parser"] = parser

            t0 = time.monotonic()
            success = "completed"
            errormsg = ""
            show_timing = True
            try:
                if "parser" not in sig.parameters:
                    args = parser.parse_args()
                    if process_args:
                        args = process_args(args) or args
                    if "args" in sig.parameters:
                        kwargs["args"] = args
                yield sig.bind(**kwargs)
            except AbortCliError as exc:
                errormsg = str(exc)
                success = "failed"
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
                success = "failed"
            finally:
                if show_timing:
                    delta = round(time.monotonic() - t0, 2)
                    log.info("task %s in %.2fs", success, delta)
            if errormsg:
                parser.error(errormsg)

        def log_sys_info():
            log.info("system: %s, %s", sys.executable, sys.version)

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def _cli2(*args, **kwargs):
                with setup() as ba:
                    log_sys_info()
                    return await function(*ba.args, **ba.kwargs)

        else:

            @functools.wraps(function)
            def _cli2(*args, **kwargs):
                with setup() as ba:
                    log_sys_info()
                    return function(*ba.args, **ba.kwargs)

        _cli2.attributes = {
            "doc": function.__doc__ or module.__doc__ or "",
        }
        return _cli2

    return _cli1