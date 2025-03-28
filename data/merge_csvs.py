import pandas as pd
from pathlib import Path


def merge_csv_files(
    small_csv_filename, large_csv_filename, output_filename, data_dir=None
):
    """
    Merge two CSV files based on common columns.

    Parameters:
    - small_csv_filename: Filename of the smaller CSV file with target columns
    - large_csv_filename: Filename of the larger CSV file to merge into
    - output_filename: Filename to save the merged CSV file
    - data_dir: Optional directory where CSV files are located (uses script dir by default)
    """
    print("Starting merge process...")

    # Get the directory of the current script or use specified data directory
    if data_dir is None:
        script_dir = Path(__file__).parent
    else:
        script_dir = Path(data_dir)

    print(f"Using directory: {script_dir}")

    # Create full paths to the CSV files
    small_csv_path = script_dir / small_csv_filename
    large_csv_path = script_dir / large_csv_filename
    output_path = script_dir / output_filename

    print(f"Small CSV path: {small_csv_path}")
    print(f"Large CSV path: {large_csv_path}")

    # Check if files exist
    if not small_csv_path.exists():
        raise FileNotFoundError(f"Small CSV file not found: {small_csv_path}")
    if not large_csv_path.exists():
        raise FileNotFoundError(f"Large CSV file not found: {large_csv_path}")

    # Read the CSV files
    print("Reading first CSV file...")
    small_df = pd.read_csv(small_csv_path)
    print(
        f"First CSV loaded with {len(small_df)} rows and {len(small_df.columns)} columns"
    )
    print(f"Columns in first CSV: {small_df.columns.tolist()}")

    print("Reading second CSV file...")
    large_df = pd.read_csv(large_csv_path)
    print(
        f"Second CSV loaded with {len(large_df)} rows and {len(large_df.columns)} columns"
    )
    print(f"Columns in second CSV: {large_df.columns.tolist()}")

    # Create mapping between different column names
    column_mapping = {
        "id": "track_id",  # id in small_df maps to track_id in large_df
        "name": "track_name",  # name maps to track_name
        "album": "album_name",  # album maps to album_name
        # Other mappings can be added here
    }

    print("Finding common columns for merging...")

    # Determine which key to use for merging
    if "id" in small_df.columns and "track_id" in large_df.columns:
        print("Using 'id' from first file and 'track_id' from second file for merging")

        # Perform the merge using the mapped columns
        print("Performing merge operation...")
        merged_df = pd.merge(
            small_df, large_df, left_on="id", right_on="track_id", how="left"
        )
    else:
        print(
            "WARNING: Expected key columns 'id' or 'track_id' not found in both files"
        )
        # Try to find alternative columns
        print("Attempting to find alternative common columns...")
        common_cols = set(small_df.columns).intersection(set(large_df.columns))
        if common_cols:
            common_col = list(common_cols)[0]
            print(f"Using common column '{common_col}' for merging")
            merged_df = pd.merge(small_df, large_df, on=common_col, how="left")
        else:
            raise KeyError("No common columns found between the files for merging")

    # Handle duplicate columns (columns with same data but different names)
    print("Cleaning up duplicate columns...")
    print(f"Merged data shape before cleanup: {merged_df.shape}")

    # Keep only the columns from the small CSV plus any new columns from large CSV
    # that don't have equivalents in the small CSV
    columns_to_keep = small_df.columns.tolist()
    for col in large_df.columns:
        if col not in column_mapping.values() and col not in columns_to_keep:
            columns_to_keep.append(col)

    # Filter to relevant columns if possible
    if set(columns_to_keep).issubset(set(merged_df.columns)):
        merged_df = merged_df[columns_to_keep]

    print(f"Final data shape: {merged_df.shape}")
    print(f"Saving merged data to {output_path}")

    # Save the merged CSV
    merged_df.to_csv(output_path, index=False)

    print(f"Merge complete. Saved {len(merged_df)} rows to {output_filename}")


# Example usage
if __name__ == "__main__":
    try:
        merge_csv_files(
            small_csv_filename="tracks_features.csv",
            large_csv_filename="dataset_to_merge.csv",
            output_filename="tracks_features.csv",
        )
        print("Script completed successfully!")
    except Exception as e:
        print(f"Error: {e}")
