import pandas as pd
from sqlalchemy import text
from scripts.db import engine

def load_dimensions(df: pd.DataFrame) -> tuple[dict, dict, dict]:

    print("Loading Dimensions...")
    
    with engine.begin() as conn:
        # 1. dim_problem_type
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
            
        # 2. dim_location
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
            
        # 3. dim_organizations
        all_orgs = set(df['primary_org'].dropna().unique()) | set(df['latest_action_org'].dropna().unique())
        for org in all_orgs:
            if org and org != "Not specified":
                conn.execute(
                    text("INSERT INTO dim_organizations (org_name) VALUES (:org) ON CONFLICT (org_name) DO NOTHING;"),
                    {"org": org}
                )
                
    # ID Mapping
    type_map = pd.read_sql("SELECT full_type, type_id FROM dim_problem_type", engine).set_index('full_type')['type_id'].to_dict()
    loc_map = pd.read_sql("SELECT subdistrict, district, province, location_id FROM dim_location", engine).set_index(['subdistrict', 'district', 'province'])['location_id'].to_dict()
    org_map = pd.read_sql("SELECT org_name, org_id FROM dim_organizations", engine).set_index('org_name')['org_id'].to_dict()
    
    print("Dimensions loaded and mapped successfully!")
    return type_map, loc_map, org_map

def load_fact_tickets(df: pd.DataFrame, type_map: dict, loc_map: dict, org_map: dict):
    print("Loading Fact Tickets...")
    fact_df = df.copy()
    
    # 1. Map Foreign Keys
    fact_df['type_id'] = fact_df['type'].map(type_map)
    fact_df['location_id'] = fact_df.apply(lambda r: loc_map.get((r['subdistrict'], r['district'], r['province'])), axis=1)
    fact_df['primary_org_id'] = fact_df['primary_org'].map(org_map)
    fact_df['latest_action_org_id'] = fact_df['latest_action_org'].map(org_map)
    
    # 2. Adjust the column names to match the database
    fact_df = fact_df.rename(columns={
        'photo': 'photo_url',
        'photo_after': 'photo_after_url'
    })
    
    # 3. Select only the columns that exist in the table fact_tickets
    cols_to_load = [
        'ticket_id', 'message_id', 'type_id', 'location_id', 'state', 'tags',
        'star', 'count_reopen', 'is_internal_rework', 'comment', 'address',
        'longitude', 'latitude', 'photo_url', 'photo_after_url',
        'timestamp', 'timestamp_inprogress', 'timestamp_finished', 'last_activity',
        'duration_minutes_total', 'calculated_from_start', 'calculated_from_inprogress',
        'primary_org_id', 'latest_action_org_id', 'org_count'
    ]
    
    # If tags is not exist -> fill None
    if 'tags' not in fact_df.columns:
        fact_df['tags'] = None
        
    final_df = fact_df[cols_to_load]
    
    # 4. Load to temporary staging table
    final_df.to_sql(
        name='staging_tickets',
        con=engine,
        if_exists='replace',
        index=False,
        chunksize=2000,
        method='multi'
    )
    
    # 5. Execute SQL UPSERT from staging into fact_tickets
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
            photo_after_url = EXCLUDED.photo_after_url,
            timestamp_inprogress = EXCLUDED.timestamp_inprogress,
            timestamp_finished = EXCLUDED.timestamp_finished,
            last_activity = EXCLUDED.last_activity,
            duration_minutes_total = EXCLUDED.duration_minutes_total,
            calculated_from_start = EXCLUDED.calculated_from_start,
            calculated_from_inprogress = EXCLUDED.calculated_from_inprogress,
            latest_action_org_id = EXCLUDED.latest_action_org_id,
            org_count = EXCLUDED.org_count;

        -- Clean up staging table
        DROP TABLE IF EXISTS staging_tickets;
    """

    with engine.begin() as conn:
        conn.execute(text(upsert_sql))

    print(f"Upserted {len(final_df):,} records into 'fact_tickets' successfully!")

def load_ticket_organizations(df: pd.DataFrame, org_map: dict):
    print("Loading Ticket Organizations (Bridge Table)...")
    
    records = []
    for _, row in df[['ticket_id', 'organization', 'latest_action_org']].iterrows():
        org_str = row['organization']
        if pd.isna(org_str) or not str(org_str).strip():
            continue
            
        org_names = [o.strip() for o in str(org_str).split(',') if o.strip()]
        
        seen_orgs = set()
        for seq, org_name in enumerate(org_names, start=1):
            org_id = org_map.get(org_name)
            if org_id and (org_id not in seen_orgs):
                seen_orgs.add(org_id)
                records.append({
                    'ticket_id': row['ticket_id'],
                    'org_id': org_id,
                    'sequence_order': seq,
                    'is_primary': (seq == 1),
                    'is_latest_actor': (org_name == row['latest_action_org'])
                })
                
    if not records:
        print("No ticket organizations to load.")
        return
    bridge_df = pd.DataFrame(records)
    
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
    type_map, loc_map, org_map = load_dimensions(df)
    load_fact_tickets(df, type_map, loc_map, org_map)
    load_ticket_organizations(df, org_map)

if __name__ == "__main__":
    from scripts.extract import extract_traffy_data
    from scripts.transform import transform_traffy_data
    from scripts.db import init_db_schema
    
    init_db_schema()
    
    raw_df = extract_traffy_data("bangkok_2026-07")
    clean_df = transform_traffy_data(raw_df)
    
    load_traffy_data(clean_df)