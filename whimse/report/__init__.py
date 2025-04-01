from whimse.config import Config
from whimse.report.common import ReportFormatter
from whimse.report.html import HTMLReportFormatter
from whimse.report.json import JSONReportFormattter
from whimse.report.plain import PlainReportFormatter
from whimse.types.reports import Report, ReportFormat


def report_formatter_factory(config: Config, report: Report) -> ReportFormatter:
    match config.report_format:
        case ReportFormat.PLAIN:
            return PlainReportFormatter(config, report)
        case ReportFormat.HTML:
            return HTMLReportFormatter(config, report)
        case ReportFormat.JSON:
            return JSONReportFormattter(config, report)
        case _:
            raise ValueError("Invalid report format %r", format)
