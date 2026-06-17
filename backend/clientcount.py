from backend.database import execute_query

class StudioStats:
    @staticmethod
    def get_overall_stats():
        try:
            # 1. Exact Client Count (From Users Table)
            count_row = execute_query("SELECT COUNT(*) as count FROM users", fetch=True)
            clients = int(count_row[0]['count']) if count_row and count_row[0]['count'] else 0
            
            # 2. Exact Project Count (Count of all Store Products, both public and private)
            store_row = execute_query("SELECT COUNT(*) as count FROM store_products", fetch=True)
            projects = int(store_row[0]['count']) if store_row and store_row[0]['count'] else 0
            
            # Category breakdown (For the small text below Projects)
            store_stats = execute_query("SELECT LOWER(category) as category, COUNT(*) as count FROM store_products GROUP BY LOWER(category)", fetch=True)
            cat_map = {row['category']: int(row['count']) for row in store_stats if row['category']} if store_stats else {}
            
            # 3. Consolidated Rating (Average of all Reviews)
            rating_row = execute_query("SELECT AVG(rating) as avg_rating FROM reviews", fetch=True)
            avg_rating = float(rating_row[0]['avg_rating']) if rating_row and rating_row[0]['avg_rating'] else 5.0
            
            return {
                "clients": clients,
                "projects": projects,
                "rating": round(avg_rating, 1),
                "years": 1, # Exactly 1 year as requested
                "details": {
                    "cybersecurity": cat_map.get('cybersecurity', 0),
                    "web": cat_map.get('web', 0),
                    "project": cat_map.get('project', 0)
                }
            }
        except Exception as e:
            print(f"Stats Error: {e}")
            return {
                "clients": 0, 
                "projects": 0, 
                "rating": 5.0, 
                "years": 1,
                "details": {
                    "cybersecurity": 0,
                    "web": 0,
                    "project": 0
                }
            }
