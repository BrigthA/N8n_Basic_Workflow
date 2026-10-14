import os
import re
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI()


# ==========================================
# 1. EXTRACT
# ==========================================
def extract_data(file_path):
  """Extracts raw data from a local CSV file."""
  try:
    df = pd.read_csv(file_path)
    print(f"[EXTRACT] Successfully read {len(df)} rows from {file_path}")
    return df
  except Exception as e:
    print(f"[EXTRACT ERROR] {e}")
    return None


# ==========================================
# 2. TRANSFORM
# ==========================================
def clean_text_with_openai(text_content):
  """Uses OpenAI to clean and normalize unstructured text rows."""
  try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise data cleaning assistant. Clean,"
                    " correct spelling, and normalize the provided text"
                    " data while keeping the original meaning intact."
                    " Clean this student enrollment row "
                    "Rules: Name: Title Case"
                    " Email: if invalid set INVALID_EMAIL"
                    " Phone: if less than 10 digits set MISSING"
                    " Course: only Python or Machine Learning or Data Science"
                    " Fee_Paid: yes/YES = true, no/NO = false"
                    " City: Title Case, empty = UNKNOWN"
                    " Enrolled_Date: convert to YYYY-MM-DD"
                ),
            },
            {"role": "user", "content": str(text_content)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()
  except Exception as e:
    print(f"[OPENAI API ERROR] {e}")
    return text_content


def transform_data(df):
  """Applies transformations, data validation, and AI cleaning."""
  if df is None:
    return None

  print("[TRANSFORM] Starting data cleaning process...")

  # Email validation via Regex
  email_regex = (
      r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
      r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
      r"[A-Za-z]{2,}"
  )
  email_col = next(
      (column for column in df.columns if str(column).casefold() == "email"),
      None,
  )
  if email_col is not None:
    df[email_col] = df[email_col].astype("string").str.strip()
    email_valid = df[email_col].str.fullmatch(email_regex, na=False)
    email_present = df[email_col].notna() & df[email_col].ne("")
    df.loc[
        email_present & ~email_valid, email_col
    ] = "INVALID_EMAIL"

  # Mobile number cleanup (10-digit standard)
  if "mobile" in df.columns:
    df["mobile"] = df["mobile"].astype(str).str.replace(r"\D", "", regex=True)
    df.loc[~df["mobile"].str.match(r"^\d{10}$", na=False), "mobile"] = pd.NA

  # Date format conversion (YYYY-MM-DD)
  date_col = next(
      (
          column
          for column in df.columns
          if str(column).casefold() in {"date", "enrolled_date"}
      ),
      None,
  )
  if date_col is not None:
    parsed_dates = pd.to_datetime(
        df[date_col], errors="coerce", dayfirst=True
    )
    df[date_col] = parsed_dates.dt.strftime("%Y-%m-%d").astype("string")

  # Name standardisation (Title Case)
  name_col = next(
      (column for column in df.columns if str(column).casefold() == "name"),
      None,
  )
  if name_col is not None:
    df[name_col] = df[name_col].astype("string").str.title()

  # OpenAI integration for unstructured columns (e.g., 'notes')
  unstructured_col = "notes"
  if unstructured_col in df.columns:
    print(
        f"[TRANSFORM] Processing '{unstructured_col}' column with OpenAI"
        " model..."
    )
    df[f"cleaned_{unstructured_col}"] = df[unstructured_col].apply(
        lambda x: clean_text_with_openai(x) if pd.notnull(x) else pd.NA
    )

  print("[TRANSFORM] Data transformation completed successfully.")
  return df


# ==========================================
# 3. LOAD
# ==========================================
def load_data(
    df,
    output_csv=os.path.join(PROJECT_ROOT, "cleaned_output.csv"),
    output_xlsx=os.path.join(PROJECT_ROOT, "cleaned_output.xlsx"),
    db_name="warehouse.db",
):
  """Loads cleaned data into CSV, Excel, and SQLite outputs."""
  if df is None:
    print("[LOAD ERROR] No data to load.")
    return

  # Load target 1: Save to CSV
  df.to_csv(output_csv, index=False)
  print(f"[LOAD] Cleaned data successfully saved to CSV: {output_csv}")

  # Load target 2: Save an Excel workbook with an explicit date display format
  excel_df = df.copy()
  date_col = next(
      (
          column
          for column in excel_df.columns
          if str(column).casefold() in {"date", "enrolled_date"}
      ),
      None,
  )
  if date_col is not None:
    excel_df[date_col] = pd.to_datetime(
        excel_df[date_col], format="%Y-%m-%d", errors="coerce"
    )
  with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
    excel_df.to_excel(writer, index=False, sheet_name="Cleaned Data")
    worksheet = writer.sheets["Cleaned Data"]
    worksheet.auto_filter.ref = worksheet.dimensions
    if date_col is not None:
      date_column_index = excel_df.columns.get_loc(date_col) + 1
      for row in worksheet.iter_rows(
          min_row=2, min_col=date_column_index, max_col=date_column_index
      ):
        row[0].number_format = "yyyy-mm-dd"
  print(f"[LOAD] Cleaned data successfully saved to Excel: {output_xlsx}")

  # Load target 3: Save to SQLite Database
  try:
    conn = sqlite3.connect(db_name)
    df.to_sql("cleaned_customers", conn, if_exists="replace", index=False)
    conn.close()
    print(
        f"[LOAD] Cleaned data successfully loaded into SQLite table"
        f" 'cleaned_customers' in {db_name}"
    )
  except Exception as e:
    print(f"[LOAD ERROR] Database loading failed: {e}")


# ==========================================
# RUN ETL PIPELINE
# ==========================================
def run_etl_pipeline(file_path):
  print("--- ETL Pipeline Execution Started ---")
  raw_df = extract_data(file_path)
  transformed_df = transform_data(raw_df)
  load_data(transformed_df)
  print("--- ETL Pipeline Execution Finished ---")


if __name__ == "__main__":
  input_file = os.path.join(PROJECT_ROOT, "student_enrollment_raw.csv")
  run_etl_pipeline(input_file)