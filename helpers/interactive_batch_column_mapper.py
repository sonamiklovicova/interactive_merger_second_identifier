#!/usr/bin/env python3
"""
Interactive Batch Column Mapper

Appends a new "raw" batch of annotation rows onto an existing master
annotation table. For each column in the raw batch, asks which master
column it corresponds to (or whether it's a new column, or should be
skipped). Mappings are remembered in a small JSON file next to your data,
so re-running on a later batch with the same source column names offers
the previous answer as a default (press Enter to accept, or type to
override) instead of asking from scratch.
"""

import json
import sys
from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".xlsm", ".ods"}
MAPPING_STORE_NAME = "column_mapping_memory.json"

NEW_COLUMN = "__NEW__"
SKIP_COLUMN = "__SKIP__"


def banner(title):
    line = "=" * 74
    print(f"\n{line}\n  {title}\n{line}\n")


def list_supported_files(directory):
    return sorted(
        p for p in Path(directory).iterdir()
        if p.suffix.lower() in SUPPORTED_EXTENSIONS and p.name != MAPPING_STORE_NAME
    )


def choose_file(files, prompt):
    for i, f in enumerate(files, 1):
        print(f"  [{i}] {f.name}")
    while True:
        choice = input(f"\n{prompt}: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice) - 1]
        print("  Please enter a valid number.")


def read_table(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str)
    return pd.read_excel(path, dtype=str)


def write_table(df, path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
    elif suffix == ".tsv":
        df.to_csv(path, sep="\t", index=False)
    else:
        df.to_excel(path, index=False)


def load_mapping_store(directory):
    store_path = Path(directory) / MAPPING_STORE_NAME
    if store_path.exists():
        with open(store_path) as f:
            return json.load(f)
    return {}


def save_mapping_store(directory, store):
    store_path = Path(directory) / MAPPING_STORE_NAME
    with open(store_path, "w") as f:
        json.dump(store, f, indent=2, sort_keys=True)


def normalize(name):
    return str(name).strip().lower()


def sample_values(series, n=3):
    values = [str(v) for v in series.dropna().unique()[:n]]
    return ", ".join(values) if values else "(all blank)"


def resolve_column(source_col, series, master_columns, remembered):
    key = normalize(source_col)
    saved = remembered.get(key)

    print(f"\n  Source column: '{source_col}'")
    print(f"  Sample values: {sample_values(series)}")

    default_label = None
    if saved == SKIP_COLUMN:
        default_label = "skip this column"
    elif saved == NEW_COLUMN:
        default_label = "add as a new column"
    elif saved in master_columns:
        default_label = f"master column '{saved}'"
    else:
        saved = None

    for i, col in enumerate(master_columns, 1):
        print(f"    [{i}] {col}")
    print("    [N] add as a new column")
    print("    [S] skip this column")

    if default_label:
        prompt = f"\n  Map to which master column? (Enter = {default_label}): "
    else:
        prompt = "\n  Map to which master column?: "

    while True:
        choice = input(prompt).strip()
        if not choice and saved:
            return saved
        if choice.lower() == "n":
            remembered[key] = NEW_COLUMN
            return NEW_COLUMN
        if choice.lower() == "s":
            remembered[key] = SKIP_COLUMN
            return SKIP_COLUMN
        if choice.isdigit() and 1 <= int(choice) <= len(master_columns):
            target = master_columns[int(choice) - 1]
            remembered[key] = target
            return target
        print("  Please enter a number, N, or S.")


def output_path_for(master_path):
    stem = master_path.stem + "_updated"
    return master_path.parent / f"{stem}{master_path.suffix}"


def main():
    banner("Batch Annotation Appender  —  Interactive Mode")
    directory = Path.cwd()
    files = list_supported_files(directory)
    if len(files) < 2:
        print("  Need at least two files in the current directory:")
        print("  one master (already annotated) table and one raw batch to append.")
        print(f"  Found: {[f.name for f in files]}")
        sys.exit(1)

    banner("STEP 1  —  Select files")
    print("Which file is the MASTER (already annotated) table?\n")
    master_path = choose_file(files, "Master file number")
    remaining = [f for f in files if f != master_path]
    print("\nWhich file is the new RAW batch to append?\n")
    batch_path = choose_file(remaining, "Batch file number")

    master_df = read_table(master_path)
    batch_df = read_table(batch_path)
    master_columns = list(master_df.columns)

    banner("STEP 2  —  Map columns")
    print(f"Master columns ({len(master_columns)}): {', '.join(master_columns)}")

    remembered = load_mapping_store(directory)
    append_data = {col: [None] * len(batch_df) for col in master_columns}

    for source_col in batch_df.columns:
        target = resolve_column(source_col, batch_df[source_col], master_columns, remembered)
        if target == SKIP_COLUMN:
            continue
        if target == NEW_COLUMN:
            if source_col not in master_columns:
                master_columns.append(source_col)
                master_df[source_col] = None
                append_data[source_col] = [None] * len(batch_df)
            append_data[source_col] = batch_df[source_col].tolist()
            continue
        append_data[target] = batch_df[source_col].tolist()

    save_mapping_store(directory, remembered)

    banner("STEP 3  —  Append and save")
    appended_df = pd.DataFrame(append_data)[master_columns]
    result_df = pd.concat([master_df[master_columns], appended_df], ignore_index=True)

    output_path = output_path_for(master_path)
    write_table(result_df, output_path)

    print(f"  Appended {len(batch_df)} rows from '{batch_path.name}' onto '{master_path.name}'.")
    print(f"  Saved result to: {output_path.name}")
    print(f"  Column mappings remembered in: {MAPPING_STORE_NAME} (offered as defaults next batch)")


if __name__ == "__main__":
    main()
