"""
One-off script to create initial admin user.
"""
from user_service import create_user, get_user_by_email
import sys
import os

# Add parent dir to path to find auth and user_service if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    email = "admin@dscquant.com"
    password = "admin123"
    phone = "0000000000"
    full_name = "System Admin"
    
    # Check if exists
    existing = get_user_by_email(email)
    if existing:
        print(f"User {email} already exists. Updating role to admin.")
        # We can update the role directly in user_service or via SQL
        from utils.bigquery_helper import BigQueryHelper
        bq = BigQueryHelper()
        table = bq._get_full_table_id("users")
        sql = f"UPDATE `{table}` SET role = 'admin' WHERE email = '{email}'"
        bq.client.query(sql).result()
        print("Role updated.")
        return

    try:
        user = create_user(
            email=email,
            phone=phone,
            password=password,
            full_name=full_name,
            role="admin"
        )
        print(f"Admin user created: {email} / {password}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
