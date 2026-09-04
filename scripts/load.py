import pandas as pd
from sqlalchemy import text
from scripts.db import engine

def load_dimensions(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """
    Perform idempotent upsert loading into Dimension tables and return ID lookup maps.
    
    Args:
        df (pd.DataFrame): Cleaned dataset containing dimension attributes.
        
    Returns:
        tuple[dict, dict, dict]: Lookup dictionaries for type_map, loc_map, and org_map.
    """
    print("Loading Dimensions...")
    
    with engine.begin() as conn:
        # 1. Populate dim_problem_type
        types_df = df[['type', 'main_category', 'sub_category', 'detail_category']].drop_duplicates(subset=['type'])
        for _, row in types_df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO dim_problem_type (full_type, main_category, sub_category, detail_category)
                    VALUES (:full_type, :main_cat, :sub_cat, :detail_cat)
                    ON CONFLICT (full_type) DO NOTHING;
                """),
                {
                    "full_type": row['type'],
                    "main_cat": row['main_category'],
                    "sub_cat": row['sub_category'],
                    "detail_cat": row['detail_category']
                }
            )
            
        # 2. Populate dim_location
        loc_df = df[['subdistrict', 'district', 'province']].drop_duplicates()
        for _, row in loc_df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO dim_location (subdistrict, district, province)
                    VALUES (:subdistrict, :district, :province)
                    ON CONFLICT (subdistrict, district, province) DO NOTHING;
                """),
                {
                    "subdistrict": row['subdistrict'],
                    "district": row['district'],
                    "province": row['province']
                }
            )
            
        # 3. Populate dim_organizations
        all_orgs = set(df['primary_org'].dropna().unique()) | set(df['latest_action_org'].dropna().unique())
        for org in all_orgs:
            if org and org != "Not specified":
                conn.execute(
                    text("INSERT INTO dim_organizations (org_name) VALUES (:org) ON CONFLICT (org_name) DO NOTHING;"),
                    {"org": org}
                )
                
    # Build In-Memory ID Mapping Dictionaries
    type_map = pd.read_sql("SELECT full_type, type_id FROM dim_problem_type", engine).set_index('full_type')['type_id'].to_dict()
    loc_map = pd.read_sql("SELECT subdistrict, district, province, location_id FROM dim_location", engine).set_index(['subdistrict', 'district', 'province'])['location_id'].to_dict()
    org_map = pd.read_sql("SELECT org_name, org_id FROM dim_organizations", engine).set_index('org_name')['org_id'].to_dict()
    
    print("Dimensions loaded and mapped successfully!")
    return type_map, loc_map, org_map

def load_fact_tickets(df: pd.DataFrame, type_map: dict, loc_map: dict, org_map: dict):
    """
    Load ticket records into fact_tickets using Staging Table + SQL UPSERT pattern.
    
    Args:
        df (pd.DataFrame): Cleaned dataset.
        type_map (dict): full_type -> type_id lookup map.
        loc_map (dict): (subdistrict, district, province) -> location_id lookup map.
        org_map (dict): org_name -> org_id lookup map.
    """
    print("Loading Fact Tickets...")
    fact_df = df.copy()
    
    # 1. Map Foreign Key Surrogate Keys
    fact_df['type_id'] = fact_df['type'].map(type_map)
    fact_df['location_id'] = fact_df.apply(lambda r: loc_map.get((r['subdistrict'], r['district'], r['province'])), axis=1)
    fact_df['primary_org_id'] = fact_df['primary_org'].map(org_map)
    fact_df['latest_action_org_id'] = fact_df['latest_action_org'].map(org_map)
    
    # 2. Rename columns to match PostgreSQL target schema
    fact_df = fact_df.rename(columns={
        'photo': 'photo_url',
        'photo_after': 'photo_after_url'
    })
    
    # 3. Select target schema columns
    cols_to_load = [
        'ticket_id', 'message_id', 'type_id', 'location_id', 'state', 'tags',
        'star', 'count_reopen', 'is_internal_rework', 'comment', 'address',
        'longitude', 'latitude', 'photo_url', 'photo_after_url',
        'timestamp', 'timestamp_inprogress', 'timestamp_finished', 'last_activity',
        'duration_minutes_total', 'calculated_from_start', 'calculated_from_inprogress',
        'primary_org_id', 'latest_action_org_id', 'org_count'
    ]
    
    # Ensure tags column presence
    if 'tags' not in fact_df.columns:
        fact_df['tags'] = None
        
    final_df = fact_df[cols_to_load]
    
    # 4. Load records into temporary staging table
    final_df.to_sql(
        name='staging_tickets',
        con=engine,
        if_exists='replace',
        index=False,
        chunksize=2000,
        method='multi'
    )
    
    # 5. Execute SQL UPSERT from staging table to fact_tickets
    upsert_sql = """
        INSERT INTO fact_tickets (
            ticket_id, message_id, type_id, location_id, state, tags,
            star, count_reopen, is_internal_rework, comment, address,
            longitude, latitude, photo_url, photo_after_url,
            timestamp, timestamp_inprogress, timestamp_finished, last_activity,
            duration_minutes_total, calculated_from_start, calculated_from_inprogress,
            primary_org_id, latest_action_org_id, org_count
        )
        SELECT 
            ticket_id, message_id, type_id, location_id, state, tags,
            star, count_reopen, is_internal_rework, comment, address,
            longitude, latitude, photo_url, photo_after_url,
            timestamp, timestamp_inprogress, timestamp_finished, last_activity,
            duration_minutes_total, calculated_from_start, calculated_from_inprogress,
            primary_org_id, latest_action_org_id, org_count
        FROM staging_tickets
        ON CONFLICT (ticket_id) DO UPDATE SET
            state = EXCLUDED.state,
            tags = EXCLUDED.tags,
            star = EXCLUDED.star,
            count_reopen = EXCLUDED.count_reopen,
            is_internal_rework = EXCLUDED.is_internal_rework,
            comment = EXCLUDED.comment,
            address = EXCLUDED.address,
            longitude = EXCLUDED.longitude,
            latitude = EXCLUDED.latitude,
            photo_url = EXCLUDED.photo_url,
            photo_after_url = EXCLUDED.photo_after_url,
            timestamp = EXCLUDED.timestamp,
            timestamp_inprogress = EXCLUDED.timestamp_inprogress,
            timestamp_finished = EXCLUDED.timestamp_finished,
            last_activity = EXCLUDED.last_activity,
            duration_minutes_total = EXCLUDED.duration_minutes_total,
            calculated_from_start = EXCLUDED.calculated_from_start,
            calculated_from_inprogress = EXCLUDED.calculated_from_inprogress,
            primary_org_id = EXCLUDED.primary_org_id,
            latest_action_org_id = EXCLUDED.latest_action_org_id,
            org_count = EXCLUDED.org_count;

        DROP TABLE IF EXISTS staging_tickets;
    """
    
    with engine.begin() as conn:
        conn.execute(text(upsert_sql))
        
    print(f"Upserted {len(final_df):,} records into 'fact_tickets' successfully!")

def load_ticket_organizations(df: pd.DataFrame, org_map: dict):
    """
    Parse multi-organization assignments and load into ticket_organizations Bridge Table.
    
    Args:
        df (pd.DataFrame): Cleaned dataset.
        org_map (dict): org_name -> org_id lookup map.
    """
    print("Loading Bridge Table: ticket_organizations...")
    records = []
    
    for _, row in df.iterrows():
        ticket_id = row['ticket_id']
        org_str = row['organization']
        latest_org = row['latest_action_org']
        
        if pd.notna(org_str) and org_str:
            org_list = [o.strip() for o in org_str.split(',') if o.strip() and o.strip() != "Not specified"]
            
            for idx, org_name in enumerate(org_list):
                org_id = org_map.get(org_name)
                if org_id:
                    records.append({
                        'ticket_id': ticket_id,
                        'org_id': org_id,
                        'sequence_order': idx + 1,
                        'is_primary': (idx == 0),
                        'is_latest_actor': (org_name == latest_org)
                    })
                    
    if not records:
        print("No ticket organizations to load.")
        return
        
    bridge_df = pd.DataFrame(records)
    
    # Load into staging table and execute UPSERT
    bridge_df.to_sql(
        name='staging_ticket_orgs',
        con=engine,
        if_exists='replace',
        index=False,
        chunksize=5000,
        method='multi'
    )
    
    upsert_bridge_sql = """
        INSERT INTO ticket_organizations (ticket_id, org_id, sequence_order, is_primary, is_latest_actor)
        SELECT ticket_id, org_id, sequence_order, is_primary, is_latest_actor
        FROM staging_ticket_orgs
        ON CONFLICT (ticket_id, org_id) DO UPDATE SET
            sequence_order = EXCLUDED.sequence_order,
            is_primary = EXCLUDED.is_primary,
            is_latest_actor = EXCLUDED.is_latest_actor;
            
        DROP TABLE IF EXISTS staging_ticket_orgs;
    """
    
    with engine.begin() as conn:
        conn.execute(text(upsert_bridge_sql))
        
    print(f"Loaded {len(bridge_df):,} records into 'ticket_organizations' successfully!")

def load_traffy_data(df: pd.DataFrame):
    """Orchestrate loading sequence for dimensions, fact table, and bridge table."""
    type_map, loc_map, org_map = load_dimensions(df)
    load_fact_tickets(df, type_map, loc_map, org_map)
    load_ticket_organizations(df, org_map)

# Local module testing block
if __name__ == "__main__":
    from scripts.extract import extract_traffy_data
    from scripts.transform import transform_traffy_data
    from scripts.db import init_db_schema
    
    init_db_schema()
    
    raw_df = extract_traffy_data("bangkok_2026-07")
    clean_df = transform_traffy_data(raw_df)
    
    load_traffy_data(clean_df)