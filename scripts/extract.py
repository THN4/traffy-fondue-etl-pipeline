from io import StringIO
import pandas as pd
import requests
from scripts.config import TRAFFY_API_BASE_URL, DEFAULT_API_PARAMS

def extract_traffy_data(file_name: str = "bangkok_2026-07") -> pd.DataFrame:
    """
    Extract municipal issue dataset from Traffy Fondue Public API.
    
    Args:
        file_name (str): Identifier for target dataset file (e.g., 'bangkok_2026-07').
        
    Returns:
        pd.DataFrame: Extracted raw municipal issue dataset.
    """
    params = DEFAULT_API_PARAMS.copy()
    params["file_name"] = file_name
    
    print(f"Extracting data for: {file_name}...")
    response = requests.get(TRAFFY_API_BASE_URL, params=params)
    
    if response.status_code == 200:
        df = pd.read_csv(StringIO(response.text))
        print(f"Data extracted successfully! Total records: {len(df):,} rows")
        return df
    else:
        raise Exception(f"Failed to extract data. HTTP Status Code: {response.status_code}")

# Local module testing block
if __name__ == "__main__":
    df_sample = extract_traffy_data("bangkok_2026-07")
    print(df_sample.head(3))