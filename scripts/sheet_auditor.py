"""Run sheet audits on all operational sheets.

Usage:
    python scripts/sheet_auditor.py --creds /path/to/credentials.json
    python scripts/sheet_auditor.py --creds /path/to/credentials.json --quiet  # errors only

Sheets are defined at the bottom of this file. Edit to add/remove.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure pp_shared is importable
_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir.parent))

from pp_shared.sheets import SheetDef, audit_sheet, format_report


_DEFAULT_CREDS = ""


def _sheet_op(label, sheet_id, tab, headers, *, required=None, unique=None, dates=None, skip=0, min_rows=0, creds=""):
    return SheetDef(
        label=label,
        sheet_id=sheet_id,
        tab_name=tab,
        expected_headers=headers,
        required_cols=set(required or []),
        unique_cols=set(unique or []),
        date_cols=set(dates or []),
        skip_rows=skip,
        min_rows=min_rows,
    ), creds or _DEFAULT_CREDS


# ── Sheet definitions ──────────────────────────────────────────────────────
# Column indices are 0-based. Edit expected_headers + indices when columns change.
#
# To find sheet_id: open sheet in browser, grab from URL:
#   https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit

# Column indices are 0-based.
# Display aliases differ from canonical names in some sheets — we match what
# the sheet actually shows:
#   Comprobantes: HEADER_DISPLAY_ALIASES maps "Conciliado"→"", "Estado pago"→"Estado", etc.

_USD_CREDS = os.environ.get("CREDS_USD", "")

SHEETS = [
    _sheet_op(
        label="Operaciones (ARS)",
        sheet_id=os.environ.get("SHEET_ID_OPERACIONES", ""),
        tab="Operaciones",
        headers=[
            "#", "Caja", "Rendido", "Recibido", "Hora",
            "Tipo", "Cliente", "Banco", "Remitente", "Banco Origen",
            "ID Op", "TxID Comprobante", "Monto Bruto", "Comision%", "Monto Neto",
            "Cotizacion", "USDT", "Estado", "Verifico", "Notas",
        ],
        required={3, 5, 6, 7, 8, 10, 12, 17},
        unique={10},
        dates={3, 4},
        min_rows=50,
    ),
    _sheet_op(
        label="Comprobantes (WA)",
        sheet_id=os.environ.get("SHEET_ID_COMPROBANTES", ""),
        tab="comprobantes",
        headers=[
            "", "Nº", "ID", "Acción", "Motivo",
            "Recibido", "Cliente", "Tipo", "Monto", "Moneda",
            "Estado", "Destino", "Remitente", "Canal", "Fee",
            "Neto CC", "Saldo", "Grupo", "Sender", "Fecha",
            "ID transacción", "Referencia", "Confianza", "Calidad", "Motivos calidad",
            "Dup?", "Notas", "Imagen", "WA msg id", "Notas cliente",
        ],
        required={2, 5, 6, 7, 8, 9, 17, 28},
        unique={2, 28},
        dates={5, 19},
        min_rows=100,
    ),
    _sheet_op(
        label="Matches (live)",
        sheet_id=os.environ.get("SHEET_ID_COMPROBANTES", ""),
        tab="matches_live",
        headers=[
            "Receipt ID", "Status", "Pending Reason", "Updated At (ART)", "Currency",
            "Receipt Amount", "Sender Name", "Receipt Account", "Receipt Created At (ART)",
            "Group Client", "WA Message ID", "Best Movement ID", "Best Score",
            "Second Score", "Movement Amount", "Movement Counterparty",
            "Movement Account", "Movement Occurred At (ART)", "Movement Bank",
        ],
        required={0, 1, 3},
        unique={0},
        dates={3, 8, 17},
        min_rows=50,
    ),
    _sheet_op(
        label="Manual Review",
        sheet_id=os.environ.get("SHEET_ID_COMPROBANTES", ""),
        tab="manual_review",
        headers=[
            "Receipt ID", "Status", "Pending Reason", "Updated At (ART)", "Currency",
            "Receipt Amount", "Sender Name", "Receipt Account", "Receipt Created At (ART)",
            "Group Client", "WA Message ID", "Best Movement ID", "Best Score",
            "Second Score", "Movement Amount", "Movement Counterparty",
            "Movement Account", "Movement Occurred At (ART)", "Movement Bank",
            "Acción operador",
        ],
        required={0, 1, 3},
        unique={0},
        dates={3, 8, 17},
    ),
    _sheet_op(
        label="Matches Events",
        sheet_id=os.environ.get("SHEET_ID_COMPROBANTES", ""),
        tab="events_log",
        headers=[
            "Event ID", "Created At (ART)", "Receipt ID", "Event Type",
            "Best Movement ID", "Best Score", "Second Score",
            "Candidate Count", "Candidate Evidence",
        ],
        required={0, 1, 2, 3},
        unique={0},
        dates={1},
    ),
    _sheet_op(
        label="USD Movements",
        sheet_id=os.environ.get("SHEET_ID_USD", ""),
        tab="movimientos_usd",
        headers=[
            "Nº", "ID", "Recibido", "Grupo", "Cuenta",
            "Tipo", "Banco", "Monto", "Moneda", "Fecha",
            "Estado pago", "Cuenta destino", "Contraparte", "Comisión %",
            "Neto CC", "Saldo post", "Canal", "Dedup key", "Occurred at", "Event ID",
        ],
        required={1, 2, 4, 5, 6, 7, 8, 17, 18},
        unique={1, 17},
        dates={2, 9, 18},
        min_rows=50,
        creds=_USD_CREDS,
    ),
]


def main():
    parser = argparse.ArgumentParser(description="Audit operational Google Sheets")
    parser.add_argument("--creds", default="", help="Path to credentials.json")
    parser.add_argument("--quiet", action="store_true", help="Only show failures")
    args = parser.parse_args()

    creds_path = args.creds or os.environ.get("GOOGLE_CREDS_FILE", "")
    if not creds_path or not Path(creds_path).exists():
        print("ERROR: credentials.json not found. Set GOOGLE_CREDS_FILE or pass --creds")
        sys.exit(1)

    # Sheets that may not exist yet (matcher tabs, separate-owner sheets)
    OPTIONAL_LABELS = frozenset({"Matches (live)", "Manual Review", "Matches Events", "USD Movements"})

    all_passed = True
    for sheet_def, sheet_creds in SHEETS:
        if not sheet_def.sheet_id:
            continue
        path = sheet_creds or creds_path
        if not path or not Path(path).exists():
            print(f"⚠️ {sheet_def.label}: creds not found ({path}), skipped")
            continue
        optional = sheet_def.label in OPTIONAL_LABELS
        report = audit_sheet(sheet_def, path, optional=optional)
        if args.quiet and report.passed and not report.error:
            continue
        print(format_report(report))
        print()
        if not report.passed:
            all_passed = False

    if not all_passed:
        print("❌ Some sheets need attention")
        sys.exit(1)
    print("✅ All sheets OK")


if __name__ == "__main__":
    main()
