import io

import pandas as pd
from openpyxl.utils import get_column_letter

OPERATOR_ROW_IDX = 2
FIRST_DATA_COL_IDX = 3

STRICT_MAPPING = {
    ("Cashout", ""): "Cashout",
    ("Deposit", ""): "Deposit",
    ("Тип_операции", "КорСчет"): "Currency",
}

C_ONLY_MAPPING = {
    "Pay In CoS": "Payin_commission",
    "Транзит_Пэй_ин": "Payin",
    "Pay Out CoS": "Payout_commission",
    "Транзит_Пэй_аут": "Payout",
    "Pt CoS": "Payin_commission",
    "Обмен": "Transfer",
    "Pay In Revenue": "Payin_commission",
    "Pay Out Revenue": "Payout_commission",
    "Pt Revenue": "Payin_commission",
}

RENAME_TYPOS = {
    "Payin_commision": "Payin_commission",
    "Payout_commision": "Payout_commission",
}

DESIRED_ORDER = [
    "Name",
    "Currency",
    "Start_balance",
    "Payin",
    "Payin_commission",
    "Payout",
    "Payout_commission",
    "Deposit",
    "Cashout",
    "Transfer",
    "End_balance",
]


def build_name_column(df: pd.DataFrame, col_a: str, col_b: str, col_c: str) -> pd.Series:
    a = df[col_a].fillna("").astype(str)
    b = df[col_b].fillna("").astype(str)
    c = df[col_c].fillna("").astype(str)

    name = pd.Series("", index=df.index)

    for (b_val, c_val), out_name in STRICT_MAPPING.items():
        mask = (b == b_val) & (c == c_val)
        if mask.any():
            name[mask] = out_name

    for c_val, out_name in C_ONLY_MAPPING.items():
        mask = c == c_val
        if mask.any():
            name[mask] = out_name

    mask_start = a == "Входящее"
    mask_end = a == "Итого"

    if mask_start.any():
        name[mask_start] = "Start_balance"
    if mask_end.any():
        name[mask_end] = "End_balance"

    return name


def auto_fit_worksheet(ws) -> None:
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_length = max(
            (len(str(cell.value)) if cell.value is not None else 0) for cell in col
        )
        ws.column_dimensions[col_letter].width = max_length + 2


def transform_excel_bytes(input_bytes: bytes) -> bytes:
    raw = pd.read_excel(io.BytesIO(input_bytes))
    raw.iloc[OPERATOR_ROW_IDX] = raw.iloc[OPERATOR_ROW_IDX].ffill(axis=0)

    provider_cols = raw.columns[FIRST_DATA_COL_IDX:]
    provider_names = raw.iloc[OPERATOR_ROW_IDX, FIRST_DATA_COL_IDX:].astype(str)
    provider_names.index = provider_cols

    df = raw.copy()
    col_a, col_b, col_c = df.columns[:3]
    df = df[df[col_a] != "Изменение"]
    df["Name"] = build_name_column(df, col_a, col_b, col_c)

    df = df.drop(columns=[col_a, col_b, col_c])
    cols_without_name = [c for c in df.columns if c != "Name"]
    df = df[["Name"] + cols_without_name]

    numeric_flags = df.iloc[:, 1:].apply(
        lambda col: pd.to_numeric(col, errors="coerce").notna().any()
    )
    cols_to_keep = ["Name"] + list(df.columns[1:][numeric_flags])
    df = df[cols_to_keep]

    empty_rows_mask = (
        (df["Name"].isna() | (df["Name"].astype(str).str.strip() == ""))
        & df.iloc[:, 1:].isna().all(axis=1)
    )
    df = df[~empty_rows_mask]
    df = df.dropna(how="all").reset_index(drop=True)

    metrics_matrix = df.set_index("Name")
    df_t = metrics_matrix.T
    df_t.index = provider_names.reindex(df_t.index).values
    df_t.index.name = "Name"
    df_t = df_t.reset_index()

    dup_name_cols = [
        c
        for c in df_t.columns
        if c != "Name" and df_t[c].astype(str).equals(df_t["Name"].astype(str))
    ]
    if dup_name_cols:
        df_t = df_t.drop(columns=dup_name_cols)

    df_t = df_t.rename(columns=RENAME_TYPOS)

    value_cols = [c for c in df_t.columns if c not in ("Name", "Currency")]
    values = df_t[value_cols].apply(pd.to_numeric, errors="coerce")

    merged = {}
    for col_name in dict.fromkeys(values.columns):
        same = values.loc[:, values.columns == col_name]
        if same.shape[1] == 1:
            merged[col_name] = same.iloc[:, 0]
        else:
            def merge_row(row: pd.Series):
                non_null = row.dropna()
                if non_null.empty:
                    return pd.NA
                if non_null.nunique() == 1:
                    return non_null.iloc[0]
                return non_null.sum()

            merged[col_name] = same.apply(merge_row, axis=1)

    keep_cols = [c for c in ["Name", "Currency"] if c in df_t.columns]
    values_merged = pd.DataFrame(merged, index=df_t.index)
    df_t = pd.concat([df_t[keep_cols], values_merged], axis=1)

    existing = [c for c in DESIRED_ORDER if c in df_t.columns]
    others = [c for c in df_t.columns if c not in existing]
    df_t = df_t[existing + others]
    df_t = df_t.sort_values(by="Name", ascending=True).reset_index(drop=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_t.to_excel(writer, index=False, sheet_name="Sheet1")
        auto_fit_worksheet(writer.sheets["Sheet1"])

    output.seek(0)
    return output.getvalue()
