from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class SheetDef:
    sheet_id: str
    tab_name: str
    label: str
    expected_headers: list[str]
    required_cols: set[int]
    unique_cols: set[int]
    date_cols: set[int]
    skip_rows: int = 0
    min_rows: int = 0


@dataclass
class AuditIssue:
    severity: str
    category: str
    message: str
    row: int | None = None
    col: int | None = None


@dataclass
class AuditReport:
    label: str
    passed: bool
    issues: list[AuditIssue] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None


def _open_sheet(sheet_def: SheetDef, creds_path: str):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sheet_def.sheet_id)
    ws = sh.worksheet(sheet_def.tab_name)
    return ws


def _check_headers(ws, sheet_def: SheetDef, issues: list[AuditIssue]):
    """Verify header row matches expected headers."""
    try:
        actual = ws.row_values(1)
    except Exception as e:
        issues.append(AuditIssue(
            severity="error", category="header",
            message=f"Failed to read header row: {type(e).__name__}",
        ))
        return

    expected = sheet_def.expected_headers
    for i, (exp, act) in enumerate(zip(expected, actual)):
        if exp != act:
            issues.append(AuditIssue(
                severity="error", category="header",
                message=f"Col {i+1}: expected {exp!r}, got {act!r}",
            ))

    if len(actual) < len(expected):
        issues.append(AuditIssue(
            severity="error", category="header",
            message=f"Sheet has {len(actual)} cols, expected {len(expected)}",
        ))
    elif len(actual) > len(expected):
        issues.append(AuditIssue(
            severity="warning", category="header",
            message=f"Sheet has {len(actual)} cols ({len(expected)} expected) — extra cols may be OK",
        ))


def _check_rows(ws, sheet_def: SheetDef, issues: list[AuditIssue]):
    """Scan data rows for missing required fields, duplicates, date issues."""
    try:
        all_data = ws.get_all_values(value_render_option="FORMATTED_VALUE")
    except Exception as e:
        issues.append(AuditIssue(
            severity="error", category="read",
            message=f"Failed to read sheet data: {type(e).__name__}",
        ))
        return 0

    # Skip header + skip_rows
    data_start = 1 + sheet_def.skip_rows
    data_rows = all_data[data_start:] if len(all_data) > data_start else []
    row_count = len(data_rows)

    if row_count < sheet_def.min_rows:
        issues.append(AuditIssue(
            severity="warning" if row_count > 0 else "error",
            category="row_count",
            message=f"Only {row_count} rows (min expected: {sheet_def.min_rows})",
        ))

    unique_tracker: dict[int, dict] = {}  # col_idx -> {value: first_row}

    for i, row in enumerate(data_rows):
        row_num = data_start + i + 1  # 1-based for humans

        # Check required cols
        for col_idx in sheet_def.required_cols:
            val = (row[col_idx] or "").strip() if col_idx < len(row) else ""
            if not val:
                issues.append(AuditIssue(
                    severity="error", category="missing_data",
                    message=f"Row {row_num}: empty required col {col_idx+1} ({sheet_def.expected_headers[col_idx]})",
                    row=row_num, col=col_idx,
                ))

        # Check unique cols
        for col_idx in sheet_def.unique_cols:
            if col_idx >= len(row):
                continue
            val = (row[col_idx] or "").strip()
            if not val:
                continue
            if col_idx not in unique_tracker:
                unique_tracker[col_idx] = {}
            if val in unique_tracker[col_idx]:
                first_row = unique_tracker[col_idx][val]
                issues.append(AuditIssue(
                    severity="error", category="duplicate",
                    message=f"Row {row_num}: dup {sheet_def.expected_headers[col_idx]}={val!r} (first at row {first_row})",
                    row=row_num, col=col_idx,
                ))
            else:
                unique_tracker[col_idx][val] = row_num

        # Check date cols format
        for col_idx in sheet_def.date_cols:
            if col_idx >= len(row):
                continue
            val = (row[col_idx] or "").strip()
            if not val:
                continue
            # Accept common date formats
            if not _looks_like_a_date(val):
                issues.append(AuditIssue(
                    severity="warning", category="date_format",
                    message=f"Row {row_num}: col {col_idx+1} ({sheet_def.expected_headers[col_idx]}) doesn't look like a date: {val!r}",
                    row=row_num, col=col_idx,
                ))

    return row_count


def _looks_like_a_date(val: str) -> bool:
    """Check if a string looks like a date. Accepts common Google Sheets formats."""
    val = val.strip()
    if not val:
        return True
    # Numeric (Excel serial date)
    try:
        float(val)
        return True
    except ValueError:
        pass
    # ISO-ish: 2026-05-26, 2026-05-26T14:30, 2026-05-26 14:30:00
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            datetime.strptime(val[:19], fmt)
            return True
        except ValueError:
            pass
    # Short AR style: 26/May, 5/May 13:22, 12/May 14:07
    for fmt in ("%d/%b", "%d/%b %H:%M", "%d/%b/%Y", "%d/%m", "%d/%m/%Y"):
        try:
            datetime.strptime(val.strip()[:20], fmt)
            return True
        except ValueError:
            pass
    # d/mmm pattern: 9/Mar, 26/May
    import re
    if re.match(r"^\d{1,2}/[A-Za-z]{3,9}( \d{1,2}:\d{2})?$", val):
        return True
    # Checkbox-like or formula output
    if val in ("TRUE", "FALSE", "sí", "no", "—", "-", ""):
        return True
    return False


def audit_sheet(sheet_def: SheetDef, creds_path: str, *, optional: bool = False) -> AuditReport:
    """Run all audit checks on a sheet. Never raises — returns report on error.
    If `optional=True` and sheet/tab doesn't exist, returns passed=True silently.
    """
    try:
        ws = _open_sheet(sheet_def, creds_path)
    except Exception as e:
        if optional:
            return AuditReport(label=sheet_def.label, passed=True)
        return AuditReport(
            label=sheet_def.label,
            passed=False,
            error=f"Failed to open sheet: {type(e).__name__}",
        )

    issues: list[AuditIssue] = []
    _check_headers(ws, sheet_def, issues)
    row_count = _check_rows(ws, sheet_def, issues)

    return AuditReport(
        label=sheet_def.label,
        passed=len([i for i in issues if i.severity == "error"]) == 0,
        issues=issues,
        row_count=row_count,
    )


def format_report(report: AuditReport) -> str:
    """Format an AuditReport for Telegram / console output."""
    if report.error:
        return f"❌ {report.label}: {report.error}"

    icon = "✅" if report.passed else "⚠️"
    lines = [f"{icon} {report.label} — {report.row_count} rows"]

    errors = [i for i in report.issues if i.severity == "error"]
    warnings = [i for i in report.issues if i.severity == "warning"]

    if errors:
        lines.append(f"   Errors ({len(errors)}):")
        for e in errors[:5]:
            lines.append(f"     • {e.message}")
        if len(errors) > 5:
            lines.append(f"     … and {len(errors) - 5} more")

    if warnings:
        lines.append(f"   Warnings ({len(warnings)}):")
        for w in warnings[:3]:
            lines.append(f"     • {w.message}")
        if len(warnings) > 3:
            lines.append(f"     … and {len(warnings) - 3} more")

    return "\n".join(lines)
