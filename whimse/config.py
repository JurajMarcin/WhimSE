from argparse import Action, ArgumentParser, FileType, Namespace, RawTextHelpFormatter
from collections.abc import Sequence
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from logging import DEBUG, INFO
from pathlib import Path
from sys import stdout
from tempfile import mkdtemp
from typing import Any, TextIO

from selinux import selinux_getpolicytype

from whimse.types.reports import ReportFormat


class ExtendListAction(Action):
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        del parser
        del option_string
        if not values:
            return
        if not hasattr(namespace, self.dest):
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).extend(values)


class ModuleFetchMethod(StrEnum):
    EXACT_PACKAGE = "exact"
    NEWER_PACKAGE = "newer"
    LOCAL_MODULE = "local"


@dataclass(kw_only=True, frozen=True)
class Config:
    log_level: int
    log_levels: dict[str, int]
    work_dir: Path
    keep_work_dir: bool
    cildiff_path: Path

    policy_store_path: Path
    module_fetch_methods: tuple[ModuleFetchMethod, ...]

    avc_start_time: datetime | None

    input: TextIO | None
    report_format: ReportFormat
    output: TextIO
    full_report: bool
    show_lookalikes: bool

    @property
    def shadow_root_path(self) -> Path:
        return self.work_dir / "root"

    @property
    def shadow_policy_store_path(self) -> Path:
        return self.shadow_root_path / self.policy_store_path.relative_to("/")

    def cil_cache_path(self, path: str | Path, dist: bool = False) -> Path:
        return (
            self.work_dir
            / "cilcache"
            / ("actual" if not dist else "dist")
            / Path(path).relative_to("/")
        )

    @staticmethod
    def parse_args(version: str) -> "Config":
        semanage_conf = ConfigParser()
        root_path = Path("/var/lib/selinux")
        try:
            with open(
                "/etc/selinux/semanage.conf", "r", encoding="locale"
            ) as semanage_conf_file:
                semanage_conf.read_string("[DEFAULT]" + semanage_conf_file.read())
            root_path = Path(semanage_conf["DEFAULT"]["store-root"])
        except (FileNotFoundError, KeyError):
            pass

        rc, policy_type = selinux_getpolicytype()
        if rc:
            raise RuntimeError("Failed to get current policy type")

        parser = ArgumentParser(
            description="What Have I Modified in SELinux - "
            "detect and report differences between current and distribution policy",
            formatter_class=RawTextHelpFormatter,
        )
        parser.register("action", "extend", ExtendListAction)

        parser.add_argument(
            "-V", "--version", action="version", version=version, help="Show version"
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=False,
            help="Verbose program output",
        )
        parser.add_argument(
            "--verbose-filter",
            action="extend",
            type=lambda string: string.split(","),
            default=[],
        )
        parser.add_argument(
            "--workdir",
            action="store",
            type=Path,
            help="Directory to be used for distribution policy and other work files.\n"
            "This directory should be empty and will be deleted if not specified otherwise.\n"
            "Default: `mktemp -d`.",
        )
        parser.add_argument(
            "--keep-workdir",
            action="store_true",
            default=False,
            help="Do not clean working directory upon exit.",
        )
        parser.add_argument(
            "--cildiff",
            action="store",
            type=Path,
            default=Path("/usr/bin/cildiff"),
            help="Path to the cildiff binary.\nDefault: '/usr/bin/cildiff'.",
        )

        policy_explore_options = parser.add_argument_group("Policy explore options")
        policy_explore_options.add_argument(
            "--policy-store",
            action="store",
            default=policy_type,
            help="Name of the policy type to operate on.\n"
            "Default loaded from '/etc/selinux/config'.",
        )
        policy_explore_options.add_argument(
            "--policy-store-root",
            action="store",
            type=Path,
            default=root_path,
            help="Policy store root path.\nDefault loaded from '/etc/selinux/semanage.conf'.",
        )
        policy_explore_options.add_argument(
            "--module-fetch",
            action="extend",
            type=lambda string: (ModuleFetchMethod(arg) for arg in string.split(",")),
            default=[],
            help="Priority of module fetch methods, can be either comma-separated list "
            "or the option can be specified multiple times.\n"
            "Possible values:\n"
            "local - trust a second local copy of the policy module, source of 'semodule -i',\n"
            "exact - fetch policy module from a package with the same version as installed,\n"
            "newer - fetch policy module from a package with newer version.\n"
            "Default: local,exact,newer.",
        )
        policy_explore_options.add_argument(
            "--policy-updates",
            action="store_const",
            const=[ModuleFetchMethod.NEWER_PACKAGE],
            dest="module_fetch",
            help="Compare the current policy and hypothetical policy after system update. "
            "Equivalent to '--module-fetch newer'.",
        )

        analysis_options = parser.add_argument_group("Analysis options")
        analysis_options.add_argument(
            "--avc-start-time",
            action="store",
            type=datetime.fromisoformat,
            default=None,
            help="Start time for AVC analysis audit event search. Must be in ISO format.",
        )

        report_options = parser.add_argument_group("Report options")
        report_options.add_argument(
            "--input",
            action="store",
            type=FileType("r", encoding="locale"),
            default=None,
            help="Instead of analysing the current policy, "
            "load JSON formatted report from this file and output it in another format.",
        )
        report_options.add_argument(
            "--format",
            action="store",
            type=ReportFormat,
            default=ReportFormat.PLAIN,
            help="Report format, possible values: plain, json, html\nDefault: plain",
        )
        report_options.add_argument(
            "--output",
            action="store",
            type=FileType("w", encoding="locale"),
            default=stdout,
            help="Output the report to this file.\nDefault: stdout",
        )
        report_options.add_argument(
            "--full-report",
            action="store_true",
            default=False,
            help="Output full report including unchanged local modifications files and policy "
            "modules. Applicable to plain or html report format.",
        )
        report_options.add_argument(
            "--show-lookalikes",
            action="store_true",
            default=False,
            help="Show policy module lookalikes (package files that might be policy modules, but "
            "their installation has not been detected) in the report. Aplicable plain or html "
            "report format.",
        )
        parsed_args = parser.parse_args()

        return Config(
            log_level=DEBUG if parsed_args.verbose else INFO,
            log_levels=dict((f, DEBUG) for f in parsed_args.verbose_filter),
            work_dir=parsed_args.workdir if parsed_args.workdir else Path(mkdtemp()),
            keep_work_dir=parsed_args.keep_workdir,
            cildiff_path=parsed_args.cildiff,
            policy_store_path=parsed_args.policy_store_root / parsed_args.policy_store,
            module_fetch_methods=(
                tuple(parsed_args.module_fetch)
                if parsed_args.module_fetch
                else (
                    ModuleFetchMethod.LOCAL_MODULE,
                    ModuleFetchMethod.EXACT_PACKAGE,
                    ModuleFetchMethod.NEWER_PACKAGE,
                )
            ),
            avc_start_time=parsed_args.avc_start_time,
            input=parsed_args.input,
            report_format=parsed_args.format,
            output=parsed_args.output,
            full_report=parsed_args.full_report,
            show_lookalikes=parsed_args.show_lookalikes,
        )
