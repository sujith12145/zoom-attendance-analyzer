"""
Script: generate_sample_data.py
================================
Generates realistic sample datasets:
  • sample_master_list.csv   – 50 students
  • sample_zoom_class1.csv   – class on 2024-01-15
  • sample_zoom_class2.csv   – class on 2024-01-22 (some name variations)
  • sample_zoom_class3.csv   – class on 2024-01-29
  • sample_zoom_class4.csv   – class on 2024-02-05
  • sample_zoom_class5.csv   – class on 2024-02-12

Run: python generate_sample_data.py
"""

import pandas as pd
import numpy as np
import os
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── Student roster ───────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Aditya","Akash","Amit","Ananya","Anjali","Arjun","Aryan",
    "Deepa","Divya","Gaurav","Harshita","Ishaan","Karan","Kavya","Keerthi",
    "Lakshmi","Manisha","Meena","Mohit","Naresh","Neha","Nikhil","Nisha",
    "Pooja","Prachi","Pranav","Priya","Rahul","Raj","Rajan","Rakesh",
    "Ramya","Ravi","Ritika","Rohit","Sachin","Sandeep","Sanjay","Sara",
    "Shivani","Shreya","Siddharth","Sneha","Sonam","Suresh","Tanvi","Tushar",
    "Usha","Vikas",
]
LAST_NAMES = [
    "Kumar","Sharma","Singh","Patel","Reddy","Nair","Joshi","Verma",
    "Gupta","Yadav","Mehta","Shah","Iyer","Pillai","Bose","Chatterjee",
    "Das","Roy","Mishra","Chopra",
]

students = []
for i, fname in enumerate(FIRST_NAMES):
    lname = LAST_NAMES[i % len(LAST_NAMES)]
    roll  = f"CS-21-{i+1:03d}"
    students.append({"roll_number": roll, "name": f"{fname} {lname}"})

master_df = pd.DataFrame(students)
master_df.to_csv(os.path.join(OUT_DIR, "sample_master_list.csv"), index=False)
print(f"✅ sample_master_list.csv  ({len(master_df)} students)")


# ─── Helper: fake Zoom CSV for a class ────────────────────────────────────────

def make_zoom_csv(
    class_date: str,
    students_df: pd.DataFrame,
    attendance_rate: float = 0.80,
    name_variation: bool = False,
    multi_session_rate: float = 0.15,
    out_name: str = "zoom.csv",
):
    base_dt   = datetime.strptime(class_date, "%Y-%m-%d").replace(hour=10, minute=0)
    class_dur = 60   # 60-minute class

    rows = []
    present_indices = random.sample(
        range(len(students_df)), int(len(students_df) * attendance_rate)
    )

    for idx in present_indices:
        stu  = students_df.iloc[idx]
        roll = stu['roll_number']
        name = stu['name']

        # Optionally vary the display name
        if name_variation:
            choice = random.randint(0, 4)
            if choice == 0:
                display = name.upper()
            elif choice == 1:
                display = name.lower()
            elif choice == 2:
                # Roll number prepended
                display = f"{roll} {name}"
            elif choice == 3:
                # Only first name
                display = name.split()[0]
            else:
                display = name   # normal
        else:
            display = name

        # Multi-session (student leaves and rejoins)
        if random.random() < multi_session_rate:
            # Session 1
            join1  = base_dt + timedelta(minutes=random.randint(0, 5))
            leave1 = join1   + timedelta(minutes=random.randint(20, 35))
            # Session 2
            join2  = leave1  + timedelta(minutes=random.randint(2, 8))
            leave2 = join2   + timedelta(minutes=random.randint(15, 25))
            dur1   = int((leave1 - join1).total_seconds() / 60)
            dur2   = int((leave2 - join2).total_seconds() / 60)
            rows.append({
                "Name (Original Name)": display,
                "User Email":           f"{roll.lower()}@university.edu",
                "Join Time":            join1.strftime("%m/%d/%Y %H:%M:%S"),
                "Leave Time":           leave1.strftime("%m/%d/%Y %H:%M:%S"),
                "Duration (Minutes)":   dur1,
            })
            rows.append({
                "Name (Original Name)": display,
                "User Email":           f"{roll.lower()}@university.edu",
                "Join Time":            join2.strftime("%m/%d/%Y %H:%M:%S"),
                "Leave Time":           leave2.strftime("%m/%d/%Y %H:%M:%S"),
                "Duration (Minutes)":   dur2,
            })
        else:
            join  = base_dt + timedelta(minutes=random.randint(0, 10))
            dur   = random.randint(40, class_dur)
            leave = join + timedelta(minutes=dur)
            rows.append({
                "Name (Original Name)": display,
                "User Email":           f"{roll.lower()}@university.edu",
                "Join Time":            join.strftime("%m/%d/%Y %H:%M:%S"),
                "Leave Time":           leave.strftime("%m/%d/%Y %H:%M:%S"),
                "Duration (Minutes)":   dur,
            })

    # Add 2-3 unknown participants (guests)
    for g in range(random.randint(1, 3)):
        rows.append({
            "Name (Original Name)": f"Guest User {g+1}",
            "User Email":           "",
            "Join Time":            base_dt.strftime("%m/%d/%Y %H:%M:%S"),
            "Leave Time":           (base_dt + timedelta(minutes=5)).strftime("%m/%d/%Y %H:%M:%S"),
            "Duration (Minutes)":   5,
        })

    zoom_df = pd.DataFrame(rows)
    zoom_df.to_csv(os.path.join(OUT_DIR, out_name), index=False)
    print(f"✅ {out_name}  ({len(present_indices)} present, {len(rows)} rows)")


# ─── Generate 5 classes ───────────────────────────────────────────────────────
make_zoom_csv("2024-01-15", master_df, 0.88, False, 0.10, "sample_zoom_class1.csv")
make_zoom_csv("2024-01-22", master_df, 0.76, True,  0.20, "sample_zoom_class2.csv")
make_zoom_csv("2024-01-29", master_df, 0.82, False, 0.15, "sample_zoom_class3.csv")
make_zoom_csv("2024-02-05", master_df, 0.70, True,  0.25, "sample_zoom_class4.csv")
make_zoom_csv("2024-02-12", master_df, 0.80, False, 0.10, "sample_zoom_class5.csv")

print("\nAll sample data generated in:", OUT_DIR)
