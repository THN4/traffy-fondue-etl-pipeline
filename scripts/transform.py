import re
import numpy as np
import pandas as pd

def normalize_tag(text) -> str:
    if pd.isna(text):
        return ""
    cleaned = re.sub(r"[\{\}\[\]\'\"]", "", str(text))
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def check_problemtype_tag(df_clean: pd.DataFrame) -> pd.DataFrame:
    if "problemtype_tag" in df_clean.columns:
        norm_tag = df_clean["problemtype_tag"].apply(normalize_tag)
        norm_type = df_clean["type"].apply(normalize_tag)
        
        is_identical = (norm_tag == norm_type).all()
        if is_identical:
            df_clean.drop(columns=["problemtype_tag"], inplace=True)
            print("Step 1: 'problemtype_tag' matches 'type' 100% (after normalization) -> Dropped safely.")
        else:
            diff_count = (norm_tag != norm_type).sum()
            df_clean.rename(columns={"problemtype_tag": "tags"}, inplace=True)
            print(f"Step 1: 'problemtype_tag' has {diff_count:,} rows with distinct values -> Preserved as 'tags'.")
    return df_clean

def transform_traffy_data(df: pd.DataFrame) -> pd.DataFrame:
    # 0. Initial Copy
    df_clean = df.copy()
    
    # Step 1: Check and clean problemtype_tag
    df_clean = check_problemtype_tag(df_clean)

    # Step 2: Parse 'type' hierarchy
    type_split = df_clean["type"].fillna("").str.split("->", expand=True)
    level_names = ["main_category", "sub_category", "detail_category"]
    col_names = [
        level_names[i] if i < len(level_names) else f"sub_category_{i}"
        for i in range(type_split.shape[1])
    ]
    type_split.columns = col_names

    for col in type_split.columns:
        type_split[col] = type_split[col].str.strip().replace("", "None").fillna("None")

    df_clean = pd.concat([df_clean, type_split], axis=1)
    print(f"Step 2: Parsed 'type' hierarchy into {list(type_split.columns)}.")

    # Step 3: Fill Missing Values
    df_clean["comment"] = df_clean["comment"].fillna("Not specified")
    df_clean["address"] = df_clean["address"].fillna("Not specified")
    print("Step 3: Filled missing values in 'comment' and 'address'.")

    # Step 4: Convert Datetime
    date_columns = ["timestamp", "last_activity", "timestamp_inprogress", "timestamp_finished"]
    for col in date_columns:
        df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
    print("Step 4: Converted date columns to Datetime.")

    # Step 5: Split Coordinates
    df_clean[["longitude", "latitude"]] = df_clean["coords"].str.split(",", expand=True).astype(float)
    df_clean.drop(columns=["coords"], inplace=True)
    print("Step 5: Split 'coords' into 'longitude' and 'latitude'.")

    # Step 6: Extract Organization Summary Features
    df_clean["primary_org"] = df_clean["organization"].fillna("").apply(
        lambda x: x.split(",")[0].strip() if x else "Not specified"
    )
    df_clean["latest_action_org"] = df_clean["organization_action"].fillna("").apply(
        lambda x: x.split(",")[0].strip() if x else "Not specified"
    )
    df_clean["org_count"] = df_clean["organization"].fillna("").apply(
        lambda x: len(x.split(",")) if x else 0
    )
    print("Step 6: Extracted organization summary features (primary_org, latest_action_org, org_count).")

    # Step 7: Recalculate Duration
    df_clean["calculated_from_start"] = (
        (df_clean["timestamp_finished"] - df_clean["timestamp"]).dt.total_seconds() / 60
    )
    df_clean["calculated_from_inprogress"] = (
        (df_clean["timestamp_finished"] - df_clean["timestamp_inprogress"]).dt.total_seconds() / 60
    )

    # Update duration_minutes_total for finished cases
    df_clean["duration_minutes_total"] = np.where(
        df_clean["timestamp_finished"].notna(),
        df_clean["calculated_from_start"],
        df_clean["duration_minutes_total"]
    )
    print("Step 7: Recalculated duration columns.")

    # Step 8: Internal Rework Feature Flag
    df_clean["is_internal_rework"] = (
        df_clean["timestamp_finished"].notna() &
        (df_clean["state"] != "เสร็จสิ้น") &
        (df_clean["count_reopen"] == 0)
    )
    print(f"Step 8: Created 'is_internal_rework' flag ({df_clean['is_internal_rework'].sum():,} cases).")

    print("\n--- Final Cleaned Data Sample ---")
    preview_cols = ["ticket_id", "main_category", "sub_category", "primary_org", "latest_action_org", "org_count", "duration_minutes_total"]
    print(df_clean[preview_cols].head())
    print(f"\nFinal Shape: {df_clean.shape[0]:,} rows, {df_clean.shape[1]} columns\n")
    
    return df_clean

# For test only
if __name__ == "__main__":
    from scripts.extract import extract_traffy_data
    df_raw = extract_traffy_data("bangkok_2026-07")
    df_transformed = transform_traffy_data(df_raw)
    print(df_transformed.head(5))