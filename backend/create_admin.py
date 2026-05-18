import os
import bcrypt
from database import get_db
from datetime import datetime

def create_admin():
    os.environ['DATABASE_URL'] = 'postgresql://postgres:hBvNDIVRNdKxqZnbqBpzozptvOHBYypC@yamanote.proxy.rlwy.net:46688/railway'
    
    conn = get_db()
    cursor = conn.cursor()
    
    name = "Admin User"
    email = "admin@signbridge.com"
    password = "HJdie2120933"
    created_at = datetime.now()
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    cursor.execute('''
        INSERT INTO admins (name, email, password_hash, permissions, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            permissions = EXCLUDED.permissions
    ''', (name, email, password_hash, 'user_management,analytics_view,model_retrain,system_config', created_at))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ Admin created!")
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Password: {password}")

if __name__ == '__main__':
    create_admin()
