import os
import time
import random
import smtplib
import hmac
import hashlib
import traceback
from email.message import EmailMessage
from functools import wraps
# pyrefly: ignore [missing-import]
from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, url_for, session, abort
from backend.database import get_db_connection, execute_query
from backend.youtube_api import YouTubeStats
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import razorpay

load_dotenv()

# Initialize Razorpay Client
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except Exception as e:
        print(f"Error initializing Razorpay client: {e}")

# Run database migrations for new columns (consolidated to minimize connection overhead on cold starts)

try:
    migration_query = """
    ALTER TABLE store_products 
      ADD COLUMN IF NOT EXISTS source_code_link TEXT,
      ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT TRUE,
      ADD COLUMN IF NOT EXISTS guide_link TEXT;
    ALTER TABLE user_reels 
      ADD COLUMN IF NOT EXISTS guide_link TEXT;
    """
    execute_query(migration_query)
except Exception as e:
    print(f"Database Migration Error: {e}")

class SimpleCache:
    def __init__(self):
        self._cache = {}
    
    def get(self, key, timeout=60):
        if key in self._cache:
            val, timestamp = self._cache[key]
            if time.time() - timestamp < timeout:
                return val
        return None
        
    def set(self, key, val):
        self._cache[key] = (val, time.time())
        
    def delete(self, key):
        self._cache.pop(key, None)
        
    def clear(self):
        self._cache.clear()

db_cache = SimpleCache()

# ── RATE LIMITING DECORATOR (DevSecOps - Brute Force Protection) ──
def rate_limit(limit=10, period=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if app.debug:
                return f(*args, **kwargs)
            
            # Extract client IP safely behind reverse proxies
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
                
            key = f"rate_limit:{f.__name__}:{ip}"
            requests_info = db_cache.get(key, timeout=period)
            
            now = time.time()
            if requests_info is None:
                requests_info = []
                
            # Filter expired timestamps
            requests_info = [t for t in requests_info if now - t < period]
            
            if len(requests_info) >= limit:
                abort(429, description="Too many requests. Please try again later.")
                
            requests_info.append(now)
            db_cache.set(key, requests_info)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

app = Flask(__name__, 
            static_folder='frontend', 
            template_folder='frontend')
app.secret_key = os.getenv('SECRET_KEY', 'vroyals_secret_123')

# ── SESSION AND COOKIE SECURITY (DevSecOps Hardening) ──
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Prevent caching of dynamic/sensitive data (DevSecOps)
    if request.path.startswith('/api/') or request.path.endswith('.html') or request.path == '/':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        
    # Strict Content Security Policy (CSP) (DevSecOps)
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://www.youtube.com https://s.ytimg.com https://www.gstatic.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https://lh3.googleusercontent.com https://yt3.googleusercontent.com https://yt3.ggpht.com https://i.ytimg.com https://images.unsplash.com https://www.gstatic.com",
        "frame-src 'self' https://www.youtube.com https://accounts.google.com",
        "connect-src 'self' https://www.googleapis.com"
    ]
    response.headers['Content-Security-Policy'] = "; ".join(csp_directives)
    
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ── GLOBAL EXCEPTION HANDLER (DevSecOps - Safe Error Handling) ──
@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled Exception: {e}", exc_info=True)
    
    from werkzeug.exceptions import HTTPException
    code = 500
    description = "An unexpected server error occurred."
    
    if isinstance(e, HTTPException):
        code = e.code
        description = e.description
        
    if request.path.startswith('/api/'):
        return jsonify({"error": description}), code
        
    return render_template('index.html'), code

# ── AUTHENTICATION SETUP ──
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    def __init__(self, id, email, full_name, avatar_url, is_admin=False):
        self.id = id
        self.email = email
        self.full_name = full_name
        self.avatar_url = avatar_url
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    row = execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetch=True)
    if row and len(row) > 0:
        u = row[0]
        return User(u['id'], u['email'], u['full_name'], u['avatar_url'], u['is_admin'])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ── STATIC FILE SERVING ──
@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('frontend/css', path)

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('frontend/js', path)

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('frontend/assets', path)

# ── PAGE ROUTES ──
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/my-reels')
@login_required
def my_reels():
    return render_template('my-reels.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/<path:page>')
def serve_any_page(page):
    # DevSecOps Hardening: Prevent directory traversal / path exploitation
    if '..' in page or page.startswith('/') or page.startswith('.'):
        abort(400)
    # If it ends with .html, serve as is
    if page.endswith('.html'):
        return render_template(page)
    # If it's a known static folder, let other routes handle it
    if page.startswith(('css/', 'js/', 'assets/', 'api/')):
        return None 
    # Try serving as .html
    try:
        return render_template(f'{page}.html')
    except:
        return render_template('index.html') # Fallback to home


# ── INPUT VALIDATION HELPERS (DevSecOps) ──
import re
import html
from itsdangerous import URLSafeSerializer

def get_id_serializer():
    return URLSafeSerializer(app.secret_key or 'default_id_serialization_key_12893')

def encrypt_id(integer_id):
    try:
        return get_id_serializer().dumps(int(integer_id))
    except Exception:
        return None

def decrypt_id(encrypted_id_str):
    if not encrypted_id_str:
        return None
    try:
        return int(get_id_serializer().loads(str(encrypted_id_str).strip()))
    except Exception:
        return None

def is_safe_for_headers(val):

    if not val or not isinstance(val, str):
        return False
    # No carriage returns or newlines allowed in headers (prevent header injection)
    return '\r' not in val and '\n' not in val

def is_valid_email(email_str):

    if not email_str or not isinstance(email_str, str):
        return False
    email_str = email_str.strip().lower()
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email_str))

def sanitize_string(val, max_len=1000):
    if val is None:
        return None
    val_str = str(val).strip()
    if len(val_str) > max_len:
        val_str = val_str[:max_len]
    return html.escape(val_str)

def validate_category(cat):
    if not cat or not isinstance(cat, str):
        return None
    cat_lower = cat.strip().lower()
    if cat_lower in ['web', 'cybersecurity', 'project']:
        return cat_lower
    return None

def validate_price(price_val):
    try:
        p = float(price_val)
        if p >= 0:
            return round(p, 2)
    except (ValueError, TypeError):
        pass
    return None

def contains_links(text):
    if not text or not isinstance(text, str):
        return False
    # Check for protocol or www prefix
    if re.search(r'https?://|www\.', text, re.IGNORECASE):
        return True
    # Check for domain-like patterns with common TLDs (e.g. site.com, site.net)
    common_tlds = r'\.(com|net|org|co|info|io|xyz|biz|in|edu|gov)\b'
    if re.search(common_tlds, text, re.IGNORECASE):
        return True
    return False

# ── API ROUTES ──
@app.route('/api/signup', methods=['POST'])
@rate_limit(limit=5, period=60)
def api_signup():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not full_name or not email or not password:
        return redirect(url_for('signup_page', error='All fields are required.'))
        
    full_name = str(full_name).strip()
    email = str(email).strip().lower()
    password = str(password)
    
    if len(full_name) < 2 or len(full_name) > 100:
        return redirect(url_for('signup_page', error='Full name must be between 2 and 100 characters.'))
        
    if not is_valid_email(email) or len(email) > 255:
        return redirect(url_for('signup_page', error='Invalid email address.'))
        
    if len(password) < 6 or len(password) > 128:
        return redirect(url_for('signup_page', error='Password must be between 6 and 128 characters.'))
        
    # Check if user exists
    existing = execute_query("SELECT * FROM users WHERE email = %s", (email,), fetch=True)
    if existing:
        return redirect(url_for('signup_page', error='Email already registered'))
        
    password_hash = generate_password_hash(password)
    is_admin = email == 'veeranpandian62@gmail.com'
    
    full_name_sanitized = sanitize_string(full_name, 100)
    
    execute_query(
        "INSERT INTO users (email, full_name, password_hash, is_admin) VALUES (%s, %s, %s, %s)",
        (email, full_name_sanitized, password_hash, is_admin)
    )
    
    # Auto login after signup
    row = execute_query("SELECT * FROM users WHERE email = %s", (email,), fetch=True)
    user_data = row[0]
    user_obj = User(user_data['id'], user_data['email'], user_data['full_name'], user_data['avatar_url'], user_data['is_admin'])
    login_user(user_obj)
    
    return redirect(url_for('index'))
 
@app.route('/api/login', methods=['POST'])
@rate_limit(limit=5, period=60)
def api_login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return redirect(url_for('login_page', error='Missing email or password'))
        
    email = str(email).strip().lower()
    password = str(password)
    
    if not is_valid_email(email) or len(password) > 128:
        return redirect(url_for('login_page', error='Invalid credentials'))
        
    row = execute_query("SELECT * FROM users WHERE email = %s", (email,), fetch=True)
    if row and len(row) > 0:
        user_data = row[0]
        if user_data['password_hash'] and check_password_hash(user_data['password_hash'], password):
            user_obj = User(user_data['id'], user_data['email'], user_data['full_name'], user_data['avatar_url'], user_data['is_admin'])
            login_user(user_obj)
            return redirect(url_for('index'))
            
    return redirect(url_for('login_page', error='Invalid credentials'))

@app.route('/api/logout')
@login_required
def api_logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/api/user/reels')
@login_required
def get_user_reels():
    cache_key = f"user_reels_{current_user.id}"
    cached = db_cache.get(cache_key, timeout=60)
    if cached is not None:
        return jsonify(cached)
    rows = execute_query("SELECT * FROM user_reels WHERE user_id = %s", (current_user.id,), fetch=True)
    result = rows if rows else []
    db_cache.set(cache_key, result)
    return jsonify(result)

# Google Auth Redirect
@app.route('/api/auth/google')
def google_auth():
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    redirect_uri = url_for('google_callback', _external=True)
    scope = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    
    # Retrieve next/redirect URL parameter
    next_url = request.args.get('next', '')
    state_param = next_url if next_url else ''
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={google_client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}"
    
    if state_param:
        import urllib.parse
        auth_url += f"&state={urllib.parse.quote(state_param)}"
        
    return redirect(auth_url)


@app.route('/api/auth/google/callback')
def google_callback():
    try:
        code = request.args.get('code')
        if not code:
            return redirect(url_for('login_page', error='No code provided from Google'))

        google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        redirect_uri = url_for('google_callback', _external=True)

        # 1. Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": google_client_id,
            "client_secret": google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        resp = requests.post(token_url, data=token_data)
        token_resp = resp.json()
        
        if resp.status_code != 200:
            print(f"ERROR: Google Token Exchange failed: {token_resp}")
            return redirect(url_for('login_page', error=f"Google Error: {token_resp.get('error_description', 'Token exchange failed')}"))

        access_token = token_resp.get("access_token")

        # 2. Get user info
        user_info_resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        email = user_info_resp.get("email")
        google_id = user_info_resp.get("id")
        full_name = user_info_resp.get("name")
        avatar_url = user_info_resp.get("picture")

        if not email:
            return redirect(url_for('login_page', error='Google account has no email'))

        # 3. Check if user exists, else create
        row = execute_query("SELECT * FROM users WHERE google_id = %s OR email = %s", (google_id, email), fetch=True)
        
        email_lower = email.lower()
        is_admin = 'admin' in email_lower or email_lower == 'veeranpandian62@gmail.com'
        
        user_data = None
        if row and len(row) > 0:
            user_data = row[0]
            # Ensure is_admin updates if user meets admin criteria
            execute_query("UPDATE users SET google_id = %s, avatar_url = %s, full_name = %s, is_admin = %s WHERE id = %s", 
                         (google_id, avatar_url, full_name, is_admin or user_data['is_admin'], user_data['id']))
            # Refresh user data
            row = execute_query("SELECT * FROM users WHERE id = %s", (user_data['id'],), fetch=True)
            user_data = row[0]
        else:
            execute_query(
                "INSERT INTO users (email, google_id, full_name, avatar_url, is_admin) VALUES (%s, %s, %s, %s, %s)",
                (email, google_id, full_name, avatar_url, is_admin)
            )
            new_row = execute_query("SELECT * FROM users WHERE google_id = %s", (google_id,), fetch=True)
            if new_row:
                user_data = new_row[0]

        if not user_data:
            return redirect(url_for('login_page', error='Database storage failed'))

        # 4. Login the user
        user_obj = User(user_data['id'], user_data['email'], user_data['full_name'], user_data['avatar_url'], user_data['is_admin'])
        login_user(user_obj)
        
        # Safe redirect to the requested page if state contains a next URL
        state = request.args.get('state')
        if state:
            import urllib.parse
            unquoted_state = urllib.parse.unquote(state).strip()
            # Only redirect if it is a relative path (prevent open redirect vulnerabilities)
            # Ensure it does not start with '//' and doesn't contain '://' to block absolute and protocol-relative URLs
            if not unquoted_state.startswith('//') and '://' not in unquoted_state:
                if unquoted_state.startswith('/') or unquoted_state.startswith('project-details.html') or unquoted_state.startswith('projects.html') or unquoted_state.startswith('contact.html'):
                    # Handle cases where it doesn't start with a slash
                    redirect_path = unquoted_state if unquoted_state.startswith('/') else '/' + unquoted_state
                    return redirect(redirect_path)
                
        return redirect(url_for('index'))

    except Exception as e:
        print(f"CRITICAL ERROR in google_callback: {e}")
        return redirect(url_for('login_page', error=f"System Error: {str(e)}"))


@app.route('/api/stats/youtube')
def get_youtube_stats():
    """Returns live YouTube statistics."""
    yt = YouTubeStats()
    data = yt.fetch_stats()
    
    # If successful, format the numbers for the frontend
    if "error" not in data:
        data['formatted_subs'] = yt.format_number(data['subscribers'])
        data['formatted_views'] = yt.format_number(data['views'])
        data['full_subs'] = data['subscribers']
        data['full_views'] = data['views']
    
    return jsonify(data)

@app.route('/api/youtube/videos')
def get_youtube_videos():
    """Returns a list of recent YouTube videos with pagination."""
    page_token = request.args.get('pageToken')
    yt = YouTubeStats()
    result = yt.fetch_recent_videos(count=6, page_token=page_token)
    return jsonify(result)



@app.route('/api/pricing')
def get_pricing():
    """Returns service pricing with automatically calculated discounts."""
    cached = db_cache.get('pricing', timeout=300)
    if cached is not None:
        return jsonify(cached)
    from backend.database import execute_query
    rows = execute_query("SELECT * FROM service_pricing", fetch=True)
    if rows is None:
        return jsonify({"error": "Failed to fetch pricing"}), 500
    
    pricing = []
    for row in rows:
        base = float(row['base_price'])
        sale = float(row['sale_price']) if row['sale_price'] else base
        
        # Calculate discount % automatically
        disc_percent = 0
        if base > sale:
            disc_percent = ((base - sale) / base) * 100
        
        pricing.append({
            "service": row['service_name'],
            "category": row['category'],
            "original_price": base,
            "discount_percent": round(disc_percent, 2),
            "discounted_price": sale
        })
    db_cache.set('pricing', pricing)
    return jsonify(pricing)

def clean_drive_url(url):
    if not url:
        return url
    url = url.strip()
    if 'drive.google.com' in url:
        import re
        match_d = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match_d:
            return f"https://lh3.googleusercontent.com/d/{match_d.group(1)}"
        match_id = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match_id:
            return f"https://lh3.googleusercontent.com/d/{match_id.group(1)}"
    return url

@app.route('/api/store')
def get_store_products():
    """Returns a list of digital products from the store."""
    show_all = request.args.get('all') == 'true'
    is_admin_user = current_user.is_authenticated and getattr(current_user, 'is_admin', False)
    
    # Cache only public store items to prevent cache collision for admin list vs public catalog
    if not show_all or not is_admin_user:
        cached = db_cache.get('store_products', timeout=120)
        if cached is not None:
            return jsonify(cached)
            
    from backend.database import execute_query
    if show_all and is_admin_user:
        rows = execute_query("SELECT * FROM store_products ORDER BY created_at DESC", fetch=True)
    else:
        rows = execute_query("SELECT * FROM store_products WHERE is_public = TRUE ORDER BY created_at DESC", fetch=True)
        
    if rows is None:
        return jsonify({"error": "Failed to fetch store products"}), 500
    
    products = []
    for row in rows:
        base = float(row['price'])
        sale = float(row['sale_price']) if row['sale_price'] else base
        disc_percent = 0
        if base > sale:
            disc_percent = ((base - sale) / base) * 100
            
        products.append({
            "id": encrypt_id(row['id']),
            "title": row['title'],
            "description": row['description'],
            "original_price": base,
            "sale_price": sale,
            "discount_percent": round(disc_percent, 1),
            "thumbnail": clean_drive_url(row['thumbnail_url']),
            "tech_stack": row['tech_stack'],
            "category": row['category'],
            "source_code_link": row.get('source_code_link'),
            "is_public": row.get('is_public', True),
            "guide_link": row.get('guide_link')
        })
        
    if not show_all or not is_admin_user:
        db_cache.set('store_products', products)
    return jsonify(products)

@app.route('/api/youtube/search')
def search_youtube_videos():
    """Searches for YouTube videos."""
    query = request.args.get('q', '')
    yt = YouTubeStats()
    videos = yt.search_videos(query=query, count=6)
    return jsonify(videos)

from backend.clientcount import StudioStats

@app.route('/api/stats/overall')
def get_overall_stats():
    cached = db_cache.get('overall_stats', timeout=60)
    if cached is not None:
        return jsonify(cached)
    stats = StudioStats.get_overall_stats()
    db_cache.set('overall_stats', stats)
    return jsonify(stats)

@app.route('/api/reviews')
def get_reviews():
    cached = db_cache.get('reviews', timeout=60)
    if cached is not None:
        return jsonify(cached)
    reviews = execute_query("SELECT * FROM reviews ORDER BY created_at DESC", fetch=True)
    db_cache.set('reviews', reviews)
    return jsonify(reviews)

@app.route('/api/user/status')
def user_status():
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "full_name": current_user.full_name,
            "avatar": current_user.avatar_url,
            "email": current_user.email,
            "is_admin": getattr(current_user, 'is_admin', False)
        })
    return jsonify({"logged_in": False})

@app.route('/admin')
@login_required
@admin_required
def admin_page():
    return render_template('admin.html')

@app.route('/api/store/<product_id>')
def get_single_product(product_id):
    """Returns details of a single product."""
    real_id = decrypt_id(product_id)
    if real_id is None:
        return jsonify({"error": "Invalid Product ID format"}), 400
        
    from backend.database import execute_query
    row = execute_query("SELECT * FROM store_products WHERE id = %s", (real_id,), fetch=True)
    if not row:
        return jsonify({"error": "Product not found"}), 404
    p = row[0]
    
    # DevSecOps - Access Control check for private products
    is_public = p.get('is_public', True)
    if not is_public:
        authorized = False
        if current_user.is_authenticated:
            if getattr(current_user, 'is_admin', False):
                authorized = True
            else:
                # Check if this user has access to this product (match by product title in user_reels)
                access_row = execute_query(
                    "SELECT 1 FROM user_reels WHERE user_id = %s AND LOWER(title) = LOWER(%s)",
                    (current_user.id, p['title']),
                    fetch=True
                )
                if access_row:
                    authorized = True
        
        if not authorized:
            return jsonify({"error": "Access denied. This is a private product."}), 403
 
    base = float(p['price'])
    sale = float(p['sale_price']) if p['sale_price'] else base
    disc_percent = 0
    if base > sale:
        disc_percent = ((base - sale) / base) * 100
        
    return jsonify({
        "id": encrypt_id(p['id']),
        "title": p['title'],
        "description": p['description'],
        "original_price": base,
        "sale_price": sale,
        "discount_percent": round(disc_percent, 1),
        "thumbnail": clean_drive_url(p['thumbnail_url']),
        "tech_stack": p['tech_stack'],
        "category": p['category'],
        "source_code_link": p.get('source_code_link'),
        "is_public": p.get('is_public', True),
        "guide_link": p.get('guide_link')
    })

@app.route('/api/admin/users')
@login_required
@admin_required
def admin_users():
    """Fetch all users for project access assignment."""
    rows = execute_query("SELECT id, email, full_name FROM users ORDER BY email ASC", fetch=True)
    return jsonify(rows if rows else [])

@app.route('/api/admin/pricing')
@login_required
@admin_required
def admin_pricing():
    """Fetch raw pricing details for service management."""
    rows = execute_query("SELECT * FROM service_pricing ORDER BY id ASC", fetch=True)
    return jsonify(rows if rows else [])

@app.route('/api/admin/pricing/update', methods=['POST'])
@login_required
@admin_required
def admin_pricing_update():
    """Update service name, category, base_price, and sale_price for a service."""
    try:
        data = request.get_json()
        pricing_id = data.get('id')
        base_price = data.get('base_price')
        sale_price = data.get('sale_price')
        service_name = data.get('service_name')
        category = data.get('category')
        
        if pricing_id is None or base_price is None:
            return jsonify({"error": "Missing service id or base price"}), 400
            
        try:
            pricing_id = int(pricing_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid service id"}), 400
            
        bp = validate_price(base_price)
        if bp is None:
            return jsonify({"error": "Invalid base price"}), 400
            
        sp = None
        if sale_price is not None and str(sale_price).strip() != '':
            sp = validate_price(sale_price)
            if sp is None:
                return jsonify({"error": "Invalid sale price"}), 400
            if sp > bp:
                return jsonify({"error": "Sale price cannot be greater than base price"}), 400
                
        fields = ["base_price = %s", "sale_price = %s"]
        params = [bp, sp]
        
        if service_name is not None:
            if not isinstance(service_name, str) or not service_name.strip():
                return jsonify({"error": "Invalid service name"}), 400
            fields.append("service_name = %s")
            params.append(sanitize_string(service_name, 255))
        if category is not None:
            cat_val = validate_category(category)
            if not cat_val:
                return jsonify({"error": "Invalid category. Must be web, cybersecurity, or project"}), 400
            fields.append("category = %s")
            params.append(cat_val)
            
        params.append(pricing_id)
        query = f"UPDATE service_pricing SET {', '.join(fields)} WHERE id = %s"
        
        execute_query(query, params)
        # Clear cache
        db_cache.delete('pricing')
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error in pricing update: {e}")
        return jsonify({"error": "Failed to update pricing option."}), 500

@app.route('/api/admin/pricing/batch-update', methods=['POST'])
@login_required
@admin_required
def admin_pricing_batch_update():
    """Update multiple service parameters in a single request."""
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"error": "Expected a list of updates"}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        try:
            with conn.cursor() as cur:
                for item in data:
                    pricing_id = item.get('id')
                    base_price = item.get('base_price')
                    sale_price = item.get('sale_price')
                    service_name = item.get('service_name')
                    category = item.get('category')
                    
                    if pricing_id is None or base_price is None:
                        continue
                        
                    try:
                        pricing_id = int(pricing_id)
                    except (ValueError, TypeError):
                        continue
                        
                    bp = validate_price(base_price)
                    if bp is None:
                        continue
                        
                    sp = None
                    if sale_price is not None and str(sale_price).strip() != '':
                        sp = validate_price(sale_price)
                        if sp is None or sp > bp:
                            continue
                            
                    fields = ["base_price = %s", "sale_price = %s"]
                    params = [bp, sp]
                    
                    if service_name is not None:
                        if not isinstance(service_name, str) or not service_name.strip():
                            continue
                        fields.append("service_name = %s")
                        params.append(sanitize_string(service_name, 255))
                    if category is not None:
                        cat_val = validate_category(category)
                        if not cat_val:
                            continue
                        fields.append("category = %s")
                        params.append(cat_val)
                        
                    params.append(pricing_id)
                    query = f"UPDATE service_pricing SET {', '.join(fields)} WHERE id = %s"
                    cur.execute(query, params)
            conn.commit()
        except Exception as db_err:
            conn.rollback()
            app.logger.error(f"Batch Update Query Error: {db_err}")
            return jsonify({"error": "Failed to update pricing catalog."}), 500
        finally:
            conn.close()
            
        # Clear cache
        db_cache.delete('pricing')
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error in batch pricing update: {e}")
        return jsonify({"error": "Failed to process batch update request."}), 500

@app.route('/api/admin/pricing/add', methods=['POST'])
@login_required
@admin_required
def admin_pricing_add():
    """Add a new service pricing option."""
    try:
        data = request.get_json()
        service_name = data.get('service_name')
        category = data.get('category', 'web')
        base_price = data.get('base_price', 0)
        sale_price = data.get('sale_price')
        
        if not service_name or not isinstance(service_name, str) or not service_name.strip():
            return jsonify({"error": "Service name is required"}), 400
            
        service_name_sanitized = sanitize_string(service_name, 255)
        cat_val = validate_category(category)
        if not cat_val:
            return jsonify({"error": "Invalid category. Must be web, cybersecurity, or project"}), 400
            
        bp = validate_price(base_price)
        if bp is None:
            return jsonify({"error": "Invalid base price. Must be a positive number."}), 400
            
        sp = None
        if sale_price is not None and str(sale_price).strip() != '':
            sp = validate_price(sale_price)
            if sp is None:
                return jsonify({"error": "Invalid sale price. Must be a positive number."}), 400
            if sp > bp:
                return jsonify({"error": "Sale price cannot be greater than base price."}), 400
                
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        new_id = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO service_pricing (service_name, category, base_price, sale_price) VALUES (%s, %s, %s, %s) RETURNING id",
                    (service_name_sanitized, cat_val, bp, sp)
                )
                new_id = cur.fetchone()[0]
            conn.commit()
        except Exception as db_err:
            conn.rollback()
            app.logger.error(f"Add Pricing Query Error: {db_err}")
            return jsonify({"error": "Failed to add pricing item to database."}), 500
        finally:
            conn.close()
            
        # Clear cache
        db_cache.delete('pricing')
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        app.logger.error(f"Error in admin_pricing_add: {e}")
        return jsonify({"error": "Failed to process add pricing request."}), 500

@app.route('/api/admin/pricing/delete/<int:pricing_id>', methods=['POST'])
@login_required
@admin_required
def admin_pricing_delete(pricing_id):
    """Delete a service pricing option."""
    try:
        execute_query("DELETE FROM service_pricing WHERE id = %s", (pricing_id,))
        # Clear cache
        db_cache.delete('pricing')
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/store/add', methods=['POST'])
@login_required
@admin_required
def admin_store_add():
    """Add a new product to the store."""
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        price = data.get('price')
        sale_price = data.get('sale_price')
        thumbnail_url = data.get('thumbnail_url')
        tech_stack = data.get('tech_stack')
        category = data.get('category')
        source_code_link = data.get('source_code_link')
        is_public = data.get('is_public', True)
        guide_link = data.get('guide_link')
        
        if not title or not isinstance(title, str) or not title.strip():
            return jsonify({"error": "Title is required"}), 400
            
        title_sanitized = sanitize_string(title, 255)
        description_sanitized = sanitize_string(description, 5000) if description else None
        
        bp = validate_price(price)
        if bp is None:
            return jsonify({"error": "Invalid price. Must be a positive number."}), 400
            
        sp = None
        if sale_price is not None and str(sale_price).strip() != '':
            sp = validate_price(sale_price)
            if sp is None:
                return jsonify({"error": "Invalid sale price. Must be a positive number."}), 400
            if sp > bp:
                return jsonify({"error": "Sale price cannot be greater than regular price."}), 400
                
        cat_val = validate_category(category)
        if not cat_val:
            return jsonify({"error": "Invalid category. Must be web, cybersecurity, or project"}), 400
            
        thumbnail_sanitized = sanitize_string(thumbnail_url, 1000) if thumbnail_url else None
        tech_stack_sanitized = sanitize_string(tech_stack, 1000) if tech_stack else None
        source_code_sanitized = sanitize_string(source_code_link, 1000) if source_code_link else None
        guide_sanitized = sanitize_string(guide_link, 1000) if guide_link else None
        is_public_bool = bool(is_public)
        
        execute_query(
            "INSERT INTO store_products (title, description, price, sale_price, thumbnail_url, tech_stack, category, source_code_link, is_public, guide_link) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (title_sanitized, description_sanitized, bp, sp, thumbnail_sanitized, tech_stack_sanitized, cat_val, source_code_sanitized, is_public_bool, guide_sanitized)
        )
        # Clear cache
        db_cache.delete('store_products')
        db_cache.delete('overall_stats')
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error in admin_store_add: {e}")
        return jsonify({"error": "Failed to add store product."}), 500

@app.route('/api/admin/store/update/<product_id>', methods=['POST'])
@login_required
@admin_required
def admin_store_update(product_id):
    """Modify a product in the store."""
    real_id = decrypt_id(product_id)
    if real_id is None:
        return jsonify({"error": "Invalid Product ID format"}), 400
        
    try:

        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        price = data.get('price')
        sale_price = data.get('sale_price')
        thumbnail_url = data.get('thumbnail_url')
        tech_stack = data.get('tech_stack')
        category = data.get('category')
        source_code_link = data.get('source_code_link')
        is_public = data.get('is_public', True)
        guide_link = data.get('guide_link')
        
        if not title or not isinstance(title, str) or not title.strip():
            return jsonify({"error": "Title is required"}), 400
            
        title_sanitized = sanitize_string(title, 255)
        description_sanitized = sanitize_string(description, 5000) if description else None
        
        bp = validate_price(price)
        if bp is None:
            return jsonify({"error": "Invalid price. Must be a positive number."}), 400
            
        sp = None
        if sale_price is not None and str(sale_price).strip() != '':
            sp = validate_price(sale_price)
            if sp is None:
                return jsonify({"error": "Invalid sale price. Must be a positive number."}), 400
            if sp > bp:
                return jsonify({"error": "Sale price cannot be greater than regular price."}), 400
                
        cat_val = validate_category(category)
        if not cat_val:
            return jsonify({"error": "Invalid category. Must be web, cybersecurity, or project"}), 400
            
        thumbnail_sanitized = sanitize_string(thumbnail_url, 1000) if thumbnail_url else None
        tech_stack_sanitized = sanitize_string(tech_stack, 1000) if tech_stack else None
        source_code_sanitized = sanitize_string(source_code_link, 1000) if source_code_link else None
        guide_sanitized = sanitize_string(guide_link, 1000) if guide_link else None
        is_public_bool = bool(is_public)
        
        execute_query(
            "UPDATE store_products SET title = %s, description = %s, price = %s, sale_price = %s, thumbnail_url = %s, tech_stack = %s, category = %s, source_code_link = %s, is_public = %s, guide_link = %s WHERE id = %s",
            (title_sanitized, description_sanitized, bp, sp, thumbnail_sanitized, tech_stack_sanitized, cat_val, source_code_sanitized, is_public_bool, guide_sanitized, real_id)
        )
        # Clear cache
        db_cache.delete('store_products')
        db_cache.delete('overall_stats')
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error in admin_store_update: {e}")
        return jsonify({"error": "Failed to update store product."}), 500

@app.route('/api/admin/store/delete/<product_id>', methods=['POST'])
@login_required
@admin_required
def admin_store_delete(product_id):
    """Delete a product from the store."""
    real_id = decrypt_id(product_id)
    if real_id is None:
        return jsonify({"error": "Invalid Product ID format"}), 400
        
    try:
        execute_query("DELETE FROM store_products WHERE id = %s", (real_id,))
        # Clear cache
        db_cache.delete('store_products')
        db_cache.delete('overall_stats')
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/access')
@login_required
@admin_required
def admin_access_list():
    """Fetch all user reels / project accesses with user email details."""
    query = """
        SELECT ur.id, ur.user_id, ur.title, ur.drive_link, ur.guide_link, ur.created_at, u.email, u.full_name
        FROM user_reels ur
        JOIN users u ON ur.user_id = u.id
        ORDER BY ur.created_at DESC
    """
    rows = execute_query(query, fetch=True)
    return jsonify(rows if rows else [])

@app.route('/api/admin/access/grant', methods=['POST'])
@login_required
@admin_required
def admin_access_grant():
    """Grant a user access to a product (creates a user_reels entry)."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        title = data.get('title')
        drive_link = data.get('drive_link')
        guide_link = data.get('guide_link')
        
        if not user_id or not title or not drive_link:
            return jsonify({"error": "Missing user_id, title, or drive_link"}), 400
            
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid user_id"}), 400
            
        title_sanitized = sanitize_string(title, 255)
        drive_sanitized = sanitize_string(drive_link, 1000)
        guide_sanitized = sanitize_string(guide_link, 1000) if guide_link else None
        
        execute_query(
            "INSERT INTO user_reels (user_id, title, drive_link, guide_link) VALUES (%s, %s, %s, %s)",
            (user_id, title_sanitized, drive_sanitized, guide_sanitized)
        )
        # Clear user's cache
        db_cache.delete(f"user_reels_{user_id}")
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error in admin_access_grant: {e}")
        return jsonify({"error": "Failed to grant user access."}), 500

@app.route('/api/admin/access/revoke/<int:access_id>', methods=['POST'])
@login_required
@admin_required
def admin_access_revoke(access_id):
    """Revoke a user's access (deletes a user_reels entry)."""
    try:
        # Find user_id first to clear cache
        row = execute_query("SELECT user_id FROM user_reels WHERE id = %s", (access_id,), fetch=True)
        if row:
            user_id = row[0]['user_id']
            execute_query("DELETE FROM user_reels WHERE id = %s", (access_id,))
            db_cache.delete(f"user_reels_{user_id}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/db-status')
def db_status():
    """Checks the PostgreSQL connection status."""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({"status": "connected", "message": "Successfully connected to Neon DB"})
    return jsonify({"status": "error", "message": "Database connection failed"}), 500

@app.route('/api/payment/create-order', methods=['POST'])
@login_required
@rate_limit(limit=10, period=60)
def payment_create_order():
    if not razorpay_client:
        return jsonify({"error": "Razorpay is not configured on the server. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env"}), 500
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
            
        product_id_raw = data.get('product_id')
        if product_id_raw is None:
            return jsonify({"error": "Product ID is required"}), 400
            
        product_id = decrypt_id(product_id_raw)
        if product_id is None:
            return jsonify({"error": "Invalid Product ID format"}), 400
            
        # Fetch product from database
        product_row = execute_query("SELECT * FROM store_products WHERE id = %s AND is_public = TRUE", (product_id,), fetch=True)
        if not product_row:
            return jsonify({"error": "Product not found"}), 404
            
        product = product_row[0]
        sale_price = float(product['sale_price']) if product['sale_price'] else float(product['price'])
        
        # Razorpay expects amount in paise (e.g. 100 paise = 1 INR)
        amount_paise = int(sale_price * 100)
        
        if amount_paise <= 0:
            return jsonify({"error": "Invalid product price"}), 400
            
        # Create Razorpay Order
        order_receipt = f"receipt_p{product_id}_u{current_user.id}_{int(time.time())}"
        
        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': order_receipt,
            'notes': {
                'product_id': str(product_id),
                'user_id': str(current_user.id),
                'product_title': product['title']
            }
        }
        
        razorpay_order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            "key_id": RAZORPAY_KEY_ID,
            "amount": razorpay_order['amount'],
            "currency": razorpay_order['currency'],
            "order_id": razorpay_order['id'],
            "product_title": product['title'],
            "user_name": current_user.full_name,
            "user_email": current_user.email
        })
        
    except Exception as e:
        app.logger.error(f"Error creating Razorpay order: {e}")
        return jsonify({"error": "Failed to initiate payment. Please try again."}), 500

@app.route('/api/payment/verify', methods=['POST'])
@login_required
@rate_limit(limit=10, period=60)
def payment_verify():
    if not razorpay_client:
        return jsonify({"error": "Razorpay is not configured"}), 500
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
            
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        product_id_raw = data.get('product_id')
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, product_id_raw]):
            return jsonify({"error": "Missing signature verification details"}), 400
            
        product_id = decrypt_id(product_id_raw)
        if product_id is None:
            return jsonify({"error": "Invalid Product ID format"}), 400

            
        # Verify the signature securely
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError:
            app.logger.warning(f"Razorpay Signature Verification Failed: order {razorpay_order_id}")
            return jsonify({"error": "Payment signature verification failed. Tampering detected."}), 400
            
        # Prevent payment replays/double processing by checking if this transaction was already logged
        existing_payment = execute_query(
            "SELECT 1 FROM payments WHERE razorpay_payment_id = %s OR razorpay_order_id = %s",
            (razorpay_payment_id, razorpay_order_id),
            fetch=True
        )
        if existing_payment:
            return jsonify({"error": "This transaction has already been processed."}), 400
            
        # Fetch the product from store_products
        product_row = execute_query("SELECT * FROM store_products WHERE id = %s", (product_id,), fetch=True)
        if not product_row:
            return jsonify({"error": "Product not found"}), 404
            
        product = product_row[0]
        
        # Grant user access to the product
        # First check if the user already has access to this product
        existing_reel = execute_query(
            "SELECT 1 FROM user_reels WHERE user_id = %s AND LOWER(title) = LOWER(%s)",
            (current_user.id, product['title']),
            fetch=True
        )
        if not existing_reel:
            execute_query(
                "INSERT INTO user_reels (user_id, title, drive_link, guide_link) VALUES (%s, %s, %s, %s)",
                (current_user.id, product['title'], product['source_code_link'], product.get('guide_link'))
            )
            # Clear user reels cache
            db_cache.delete(f"user_reels_{current_user.id}")
            
        # Log payment transaction
        sale_price = float(product['sale_price']) if product['sale_price'] else float(product['price'])
        execute_query(
            "INSERT INTO payments (user_id, product_id, razorpay_order_id, razorpay_payment_id, amount, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (current_user.id, product_id, razorpay_order_id, razorpay_payment_id, sale_price, 'captured')
        )
        
        return jsonify({"success": True, "message": "Payment verified and project access granted!"})
        
    except Exception as e:
        app.logger.error(f"Error in payment verification: {e}")
        return jsonify({"error": "An error occurred during payment verification. Please contact support."}), 500

@app.route('/api/reviews/submit', methods=['POST'])

@login_required
@rate_limit(limit=5, period=60)
def submit_review():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
        item_name = data.get('item_name')
        rating = data.get('rating', 5)
        comment = data.get('comment')
        
        try:
            rating = int(rating)
        except (ValueError, TypeError):
            return jsonify({"error": "Rating must be an integer"}), 400
            
        if rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be between 1 and 5"}), 400
            
        if not comment or not str(comment).strip():
            return jsonify({"error": "Comment is required"}), 400
            
        if len(str(comment)) > 1000:
            return jsonify({"error": "Comment must be 1000 characters or less"}), 400
            
        # ── Anti-spam link detector ──
        if contains_links(str(comment)):
            return jsonify({"error": "Links/URLs are not allowed in reviews."}), 400

        # ── Access verification: Only allow reviews on assigned products ──
        if not item_name or not str(item_name).strip():
            return jsonify({"error": "Item name is required"}), 400
            
        item_name_str = str(item_name).strip()
        access_check = execute_query(
            "SELECT 1 FROM user_reels WHERE user_id = %s AND LOWER(title) = LOWER(%s)",
            (current_user.id, item_name_str),
            fetch=True
        )
        if not access_check:
            return jsonify({"error": "You can only review projects assigned to your account."}), 403

        import html
        comment_sanitized = html.escape(str(comment).strip())
        item_name_sanitized = html.escape(item_name_str)
        
        execute_query(
            "INSERT INTO reviews (user_id, user_name, rating, comment, avatar_url, item_name) VALUES (%s, %s, %s, %s, %s, %s)",
            (current_user.id, current_user.full_name, rating, comment_sanitized, current_user.avatar_url, item_name_sanitized)
        )
        # Clear cache when reviews change
        db_cache.delete('reviews')
        db_cache.delete('overall_stats')
        return jsonify({"success": True, "message": "Review submitted successfully!"})
    except Exception as e:
        app.logger.error(f"Error submitting review: {e}")
        return jsonify({"error": "Failed to submit review."}), 500



def generate_otp_signature(email, otp, expiration):
    secret = app.secret_key.encode() if app.secret_key else b'default_secret'
    message = f"{email}:{otp}:{expiration}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()

@app.route('/api/contact/send-otp', methods=['POST'])
@rate_limit(limit=3, period=60)
def send_contact_otp():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
        email_addr = str(data.get('email', '')).strip().lower()
        name = str(data.get('name', '')).strip()

        # ── Input Validation ──
        if not email_addr or not name:
            return jsonify({"error": "Name and email are required"}), 400
        if not is_safe_for_headers(name) or not is_safe_for_headers(email_addr):
            return jsonify({"error": "Name and email cannot contain newline characters."}), 400
        if len(name) < 2 or len(name) > 100:
            return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
        if not is_valid_email(email_addr) or len(email_addr) > 255:
            return jsonify({"error": "Please enter a valid email address"}), 400

            
        otp = str(random.randint(100000, 999999))
        expiration = int(time.time()) + 600 # 10 minutes expiry
        signature = generate_otp_signature(email_addr, otp, expiration)
        
        # Send OTP email
        subject = "Your V Royals Studio Verification Code"
        body = f"Hello {name},\n\nYour contact form verification code is: {otp}\n\nThis code will expire in 10 minutes.\n\nBest regards,\nV Royals Studio"
        
        em = EmailMessage()
        em.set_content(body)
        em['Subject'] = subject
        em['From'] = os.getenv('SMTP_EMAIL')
        em['To'] = email_addr
        
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_email = os.getenv('SMTP_EMAIL')
        smtp_password = os.getenv('SMTP_PASSWORD')
        if smtp_password:
            smtp_password = smtp_password.replace(" ", "")
        
        if not smtp_email or not smtp_password:
            print("Warning: SMTP credentials not set. Returning OTP in response for dev purposes.")
            return jsonify({
                "success": True, 
                "signature": signature, 
                "expiration": expiration,
                "dev_otp": otp # Fallback for dev environments without SMTP
            })
            
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(em)
            
        return jsonify({"success": True, "signature": signature, "expiration": expiration})
    except Exception as e:
        app.logger.error(f"[OTP SMTP ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to send OTP email."}), 500

@app.route('/api/contact', methods=['POST'])
@rate_limit(limit=3, period=60)
def api_contact():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400

        name        = str(data.get('name', '')).strip()
        email_addr  = str(data.get('email', '')).strip().lower()
        service     = str(data.get('service', '')).strip()
        budget      = str(data.get('budget', '')).strip()
        msg         = str(data.get('message', '')).strip()
        otp         = str(data.get('otp', '')).strip()
        signature   = str(data.get('signature', '')).strip()
        expiration  = data.get('expiration')

        # ── Input Validation ──
        if not all([name, email_addr, msg, otp, signature, expiration]):
            return jsonify({"error": "Missing required fields or OTP"}), 400
        if not is_safe_for_headers(name) or not is_safe_for_headers(email_addr) or not is_safe_for_headers(service) or not is_safe_for_headers(budget):
            return jsonify({"error": "Fields cannot contain newline characters."}), 400
        if len(name) < 2 or len(name) > 100:
            return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
        if not is_valid_email(email_addr) or len(email_addr) > 255:
            return jsonify({"error": "Invalid email address"}), 400

        if len(msg) < 10:
            return jsonify({"error": "Message must be at least 10 characters"}), 400
        if len(msg) > 2000:
            return jsonify({"error": "Message must be 2000 characters or less"}), 400
        if len(otp) != 6 or not otp.isdigit():
            return jsonify({"error": "Invalid OTP format"}), 400
        # Validate service and budget against known safe values
        allowed_services = {'Web Development', 'Project Development', 'Cybersecurity Services', 'Other', ''}
        allowed_budgets  = {'Under ₹500', '₹500–₹2,000', '₹2,000–₹10,000', '₹10,000+', "Let's discuss", ''}
        if service not in allowed_services:
            return jsonify({"error": "Invalid service selection"}), 400
        if budget not in allowed_budgets:
            return jsonify({"error": "Invalid budget selection"}), 400

        # ── Anti-spam: no links in name or message ──
        if contains_links(name) or contains_links(msg):
            return jsonify({"error": "Links/URLs are not allowed in the name or message fields."}), 400
            
        # Verify expiration
        if int(time.time()) > int(expiration):
            return jsonify({"error": "OTP has expired. Please request a new one."}), 400
            
        # Verify signature
        expected_signature = generate_otp_signature(email_addr, otp, expiration)
        if not hmac.compare_digest(expected_signature, signature):
            return jsonify({"error": "Invalid OTP."}), 400

        # Create admin email
        subject = f"New Contact Form Submission from {name}"
        body = f"Name: {name}\nEmail: {email_addr}\nService: {service}\nBudget: {budget}\n\nMessage:\n{msg}"

        em = EmailMessage()
        em.set_content(body)
        em['Subject'] = subject
        em['From'] = os.getenv('SMTP_EMAIL')
        em['To'] = 'veeranpandian62@gmail.com'
        em['Reply-To'] = email_addr

        # Send email
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_email = os.getenv('SMTP_EMAIL')
        smtp_password = os.getenv('SMTP_PASSWORD')
        if smtp_password:
            smtp_password = smtp_password.replace(" ", "")
        
        if not smtp_email or not smtp_password:
            return jsonify({"error": "Email sending failed. Please contact me directly."}), 500

        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(em)

        return jsonify({"success": True, "message": "Message sent successfully!"})
    except Exception as e:
        app.logger.error(f"[CONTACT ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to send message."}), 500

if __name__ == '__main__':
    # Using dynamic port for deployment flexibility
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
