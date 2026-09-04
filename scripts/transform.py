import re
import numpy as np
import pandas as pd

def normalize_tag(text) -> str:
    """Normalize string tags by stripping brackets, quotes, and formatting whitespace."""
    if pd.isna(text):
        return ""
    cleaned = re.sub(r"[\{\}\[\]\'\"]", "", str(text))
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def check_problemtype_tag(df_clean: pd.DataFrame) -> pd.DataFrame:
    """
    Compare 'problemtype_tag' against 'type' column.
    Safely drop 'problemtype_tag' if values are 100% duplicate, otherwise preserve as 'tags'.
    """
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
    """
    Clean, normalize, and engineer features for raw Traffy Fondue dataset.
    
    Args:
        df (pd.DataFrame): Raw dataset extracted from Traffy Fondue API.
        
    Returns:
        pd.DataFrame: Cleaned dataset ready for dimensional loading.
    """
    # Step 0: Create working copy
    df_clean = df.copy()
    
    # Step 1: Check and drop redundant problemtype_tag column
    df_clean = check_problemtype_tag(df_clean)

    # Step 2: Parse 'type' hierarchy into 3-level categories to prevent schema drift
    split_df = df_clean["type"].fillna("").str.split("->", n=2, expand=True)
    
    df_clean["main_category"] = split_df[0].str.strip().replace("", "None").fillna("None")
    df_clean["sub_category"] = split_df[1].str.strip().replace("", "None").fillna("None") if split_df.shape[1] > 1 else "None"
    df_clean["detail_category"] = split_df[2].str.strip().replace("", "None").fillna("None") if split_df.shape[1] > 2 else "None"
    print(f"Step 2: Parsed 'type' hierarchy into main, sub, and detail categories.")

    # Step 3: Impute missing text values with standardized defaults
    df_clean["comment"] = df_clean["comment"].fillna("Not specified")
    df_clean["address"] = df_clean["address"].fillna("Not specified")
    print("Step 3: Filled missing values in 'comment' and 'address'.")

    # Step 4: Convert date columns to standard Datetime objects
    date_columns = ["timestamp", "last_activity", "timestamp_inprogress", "timestamp_finished"]
    for col in date_columns:
        df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
    print("Step 4: Converted date columns to Datetime format.")

    # Step 5: Extract longitude and latitude floats from geographic coordinates string
    df_clean[["longitude", "latitude"]] = df_clean["coords"].str.split(",", expand=True).astype(float)
    df_clean.drop(columns=["coords"], inplace=True)
    print("Step 5: Split 'coords' into 'longitude' and 'latitude'.")

    # Step 6: Engineer summary features for primary and latest acting organizations
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

    # Step 7: Recalculate duration metrics to fix negative/anomalous raw API duration values
    df_clean["calculated_from_start"] = (
        (df_clean["timestamp_finished"] - df_clean["timestamp"]).dt.total_seconds() / 60
    )
    df_clean["calculated_from_inprogress"] = (
        (df_clean["timestamp_finished"] - df_clean["timestamp_inprogress"]).dt.total_seconds() / 60
    )

    # Correct total duration for finished tickets using recalculated start-to-finish duration
    df_clean["duration_minutes_total"] = np.where(
        df_clean["timestamp_finished"].notna(),
        df_clean["calculated_from_start"],
        df_clean["duration_minutes_total"]
    )
    print("Step 7: Recalculated duration columns for finished cases.")

    # Step 8: Flag internal rework tickets (cases transferred between agencies without user reopen)
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

# Local module testing block
if __name__ == "__main__":
    from scripts.extract import extract_traffy_data
    df_raw = extract_traffy_data("bangkok_2026-07")
    df_transformed = transform_traffy_data(df_raw)
    print(df_transformed.head(5))