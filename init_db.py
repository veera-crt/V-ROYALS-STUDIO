import os
import sys
from backend.database import get_db_connection

def init_db():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database")
        return
    
    try:
        with conn.cursor() as cur:
            # 1. CREATE TABLES
            
            # Drop existing seeded tables to force reconstruction with correct UNIQUE constraints
            cur.execute("DROP TABLE IF EXISTS reviews, user_reels, store_products, service_pricing, projects CASCADE;")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT,
                    google_id VARCHAR(255) UNIQUE,
                    full_name VARCHAR(255),
                    avatar_url TEXT,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Projects table removed
            cur.execute("""
                CREATE TABLE IF NOT EXISTS service_pricing (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(255) UNIQUE NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    base_price DECIMAL(10, 2) NOT NULL,
                    sale_price DECIMAL(10, 2)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS store_products (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    sale_price DECIMAL(10, 2),
                    thumbnail_url TEXT,
                    tech_stack TEXT,
                    category VARCHAR(50),
                    source_code_link TEXT,
                    is_public BOOLEAN DEFAULT TRUE,
                    guide_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_reels (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    title VARCHAR(255) NOT NULL,
                    drive_link TEXT NOT NULL,
                    guide_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    user_name VARCHAR(255),
                    user_role VARCHAR(255) DEFAULT 'Verified Client',
                    rating INTEGER DEFAULT 5,
                    comment TEXT,
                    avatar_url TEXT,
                    item_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. SEED DATA (CLEAN MIGRATION FOR DEVELOPMENT & CYBERSECURITY)
            
            # Truncate tables to remove old video-editing records
            cur.execute("TRUNCATE TABLE service_pricing, store_products, reviews CASCADE;")

            # Seed Pricing
            pricing_data = [
                ('Web Development', 'web', 9999, 8499),
                ('Project Development', 'project', 24999, 19999),
                ('Vulnerability Testing', 'cybersecurity', 1499, 1299),
                ('Bug Fixing & Reports', 'cybersecurity', 2999, 2499),
                ('Security Auditing', 'cybersecurity', 4999, 3999),
                ('Full Pentesting Report', 'cybersecurity', 9999, 7999)
            ]
            for p in pricing_data:
                cur.execute("INSERT INTO service_pricing (service_name, category, base_price, sale_price) VALUES (%s, %s, %s, %s) ON CONFLICT (service_name) DO NOTHING", p)

            # Seed Store
            store_items = [
                ('CipherKeep Pro', 'Secure vault with AES-256 encryption. Full source code.', 499, 399, '/assets/images/store/cipherkeep.png', 'python,html,css,js,cloud', 'cybersecurity', 'https://github.com/veera-crt/V-ROYALS-STUDIO', True, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md'),
                ('Secure Voting Platform', 'Tamper-proof digital voting system. Node.js backend.', 1499, 999, '/assets/images/store/voting.png', 'python,flask,postgresql,js,security', 'web', 'https://github.com/veera-crt/V-ROYALS-STUDIO', True, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md'),
                ('Phishing Detector AI', 'Advanced email forensic analyzer with AI detection.', 899, 699, '/assets/images/store/phishing.png', 'python,flask,postgresql,security', 'cybersecurity', 'https://github.com/veera-crt/V-ROYALS-STUDIO', True, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md'),
                ('Crop & Carry Platform', 'Full farm-to-table marketplace source.', 1999, 1499, '/assets/images/store/marketplace.png', 'python,flask,html,css,js,cloud', 'project', 'https://github.com/veera-crt/V-ROYALS-STUDIO', False, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md'),
                ('VG Messenger Source', 'Real-time chat app with Socket.io integration.', 999, 799, '/assets/images/store/messenger.png', 'html,css,js,nodejs,express', 'web', 'https://github.com/veera-crt/V-ROYALS-STUDIO', True, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md'),
                ('Face Attendance Pro', 'Facial recognition attendance system with PDF reports.', 1299, 899, '/assets/images/store/attendance.png', 'python,opencv,user,database,pdf', 'project', 'https://github.com/veera-crt/V-ROYALS-STUDIO', True, 'https://github.com/veera-crt/V-ROYALS-STUDIO/blob/main/README.md')
            ]
            for item in store_items:
                cur.execute("INSERT INTO store_products (title, description, price, sale_price, thumbnail_url, tech_stack, category, source_code_link, is_public, guide_link) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (title) DO NOTHING", item)

            # No static reviews seeded to ensure only real client reviews are displayed.
            
            conn.commit()
            print("✅ Database synchronization complete. Tables and seed data verified.")
    except Exception as e:
        print(f"Error during database synchronization: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
