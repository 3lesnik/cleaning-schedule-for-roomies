from datetime import datetime
import json

data = """[
  {"date": "2026-09-01", "waste_type": "Organic Waste"},
  {"date": "2026-09-08", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-09-15", "waste_type": "Organic Waste"},
  {"date": "2026-09-18", "waste_type": "Paper & Cardboard"},
  {"date": "2026-09-22", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-09-24", "waste_type": "Chemical Waste"},
  {"date": "2026-09-29", "waste_type": "Organic Waste"},
  {"date": "2026-10-06", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-10-13", "waste_type": "Organic Waste"},
  {"date": "2026-10-16", "waste_type": "Paper & Cardboard"},
  {"date": "2026-10-20", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-10-27", "waste_type": "Organic Waste"},
  {"date": "2026-10-29", "waste_type": "Chemical Waste"},
  {"date": "2026-11-03", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-11-10", "waste_type": "Organic Waste"},
  {"date": "2026-11-17", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-11-20", "waste_type": "Paper & Cardboard"},
  {"date": "2026-11-24", "waste_type": "Organic Waste"},
  {"date": "2026-12-01", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-12-03", "waste_type": "Chemical Waste"},
  {"date": "2026-12-08", "waste_type": "Organic Waste"},
  {"date": "2026-12-15", "waste_type": "Residual Waste & Plastic"},
  {"date": "2026-12-18", "waste_type": "Paper & Cardboard"},
  {"date": "2026-12-22", "waste_type": "Organic Waste"},
  {"date": "2026-12-29", "waste_type": "Residual Waste & Plastic"}
]"""

schedule = json.loads(data)
for entry in schedule:
  entry["date"] = datetime.strptime(entry["date"], "%Y-%m-%d").date()