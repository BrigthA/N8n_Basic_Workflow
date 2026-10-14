# Student Enrollment ETL

This project cleans student enrollment data and saves the results as a CSV,
an Excel workbook, and a SQLite database.

## Input

The Python pipeline reads `student_enrollment_raw.csv` from the project root.
The expected columns include `Name`, `Email`, and `Enrolled_Date`.

## Run the pipeline

From the project root, install the dependencies and run:

```powershell
pip install -r requirements.txt
python Src\AutomationWorkflow.py
```

The script uses the OpenAI client. Set `OPENAI_API_KEY` in the environment or
in `Src\.env` before running it. The API is used to clean a `notes` column if
one is present in the input.

## Transformations

- Names are converted to title case.
- Non-empty invalid email addresses are replaced with `INVALID_EMAIL`; blank
  email values remain blank.
- `Date` or `Enrolled_Date` values are parsed day-first and formatted as
  `YYYY-MM-DD`. Unparseable dates become blank.

## Outputs

The pipeline writes these files to the project root:

- `cleaned_output.csv` — cleaned data in CSV format.
- `cleaned_output.xlsx` — cleaned data with Excel filter dropdowns. Enrollment
  dates are stored as dates and displayed using `yyyy-mm-dd`.

It also writes a `cleaned_customers` table to `warehouse.db` in the current
working directory. Close the output files in Excel before rerunning the
pipeline so Windows can overwrite them.

## n8n workflow

`Src\N8nBasicWorkflow.json` is a separate n8n workflow. It accepts an uploaded
file, processes rows with an OpenAI model, and routes them to CSV outputs based
on its configured conditions. It is not launched by the Python ETL script.