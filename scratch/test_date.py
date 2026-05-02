import pandas as pd
from datetime import datetime

try:
    d = "2026/04/30"
    dt = pd.to_datetime(d)
    print(f"Pandas success: {dt}")
except Exception as e:
    print(f"Pandas fail: {e}")

try:
    dt2 = datetime.strptime(d, "%Y-%m-%d")
    print(f"Datetime success: {dt2}")
except Exception as e:
    print(f"Datetime fail: {e}")
