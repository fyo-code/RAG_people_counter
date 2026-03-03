import duckdb
import os

def setup_database(csv_path: str, db_path: str = "retail_data.db"):
    """
    Loads the CSV into a DuckDB database file for fast SQL querying.
    DuckDB is optimized for analytical queries on tabular data and can query CSVs directly.
    We convert it to a native DuckDB file format for maximum speed.
    """
    print(f"Loading data from {csv_path} into {db_path}...")
    
    # Connect to a persistent file so we don't have to load the CSV on every user question
    con = duckdb.connect(db_path)
    
    # Drop table if it exists to allow re-running this script safely
    con.execute("DROP TABLE IF EXISTS retail_traffic")
    
    # DuckDB can read CSV directly and infer the schema beautifully.
    # We create a table directly from the CSV file.
    con.execute(f"CREATE TABLE retail_traffic AS SELECT * FROM read_csv_auto('{csv_path}', header=True)")
    
    # Get row count to verify
    count = con.execute("SELECT COUNT(*) FROM retail_traffic").fetchone()[0]
    print(f"Successfully loaded {count} rows into the 'retail_traffic' table safely.")
    
    # Let's also print the schema so we know exactly what column names DuckDB inferred
    print("\nDatabase Schema:")
    schema = con.execute("DESCRIBE retail_traffic").fetchall()
    for col in schema:
        print(f" - {col[0]} ({col[1]})")
        
    con.close()

if __name__ == "__main__":
    csv_file = "people_counter_v2.0 - _home_volteanu_PeopleCounter_ (1).csv"
    if os.path.exists(csv_file):
        setup_database(csv_file)
    else:
        print(f"Error: Could not find '{csv_file}' in the current directory.")
