import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import cv2
import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify, Response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import base64
import mediapipe as mp
import requests
import json
import csv
import io
import secrets
import string
import bcrypt
from datetime import datetime, timedelta
from database import get_db, init_db, adapt_query, fetchone_dict, fetchall_dict

tf.config.set_visible_devices([], 'GPU')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'signtranslate2024'
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

init_db()

print("Loading model...")
model = tf.keras.models.load_model('model/action.keras')
# Warm up model to prevent retracing
@tf.function(reduce_retracing=True)
def predict(x):
    return model(x, training=False)
print("Model loaded successfully!")

actions = np.array(['thanks', 'i love you'])

mp_holistic = mp.solutions.holistic
holistic = mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0
)
print("MediaPipe loaded!")

TRANSLATIONS = {
    'thanks': {
        'en': 'Thanks', 'es': 'Gracias', 'fr': 'Merci',
        'ar': 'شكرًا', 'hi': 'धन्यवाद', 'ja': 'ありがとう'
    },
    'i love you': {
        'en': 'I love you', 'es': 'Te amo', 'fr': 'Je t\'aime',
        'ar': 'أحبك', 'hi': 'मैं तुमसे प्यार करता हूँ', 'ja': '愛してる'
    }
}

SUPER_ADMIN_PASSWORD = 'signbridge2024'
ANALYTICS_FILE = 'analytics.json'
MODELS_META_FILE = 'models_meta.json'

def load_models_meta():
    if os.path.exists(MODELS_META_FILE):
        with open(MODELS_META_FILE, 'r') as f:
            return json.load(f)
    # Default original model
    return [{
        'id': 'model_original',
        'name': 'SB-LSTM-v1.0-base',
        'accuracy': 98.3,
        'training_sequences': 300,
        'contributions_used': 0,
        'epochs': 2000,
        'created_at': '2026-05-10T00:00:00',
        'status': 'active',
        'file': 'action.keras'
    }]

def save_models_meta(data):
    with open(MODELS_META_FILE, 'w') as f:
        json.dump(data, f)

def load_analytics():
    if os.path.exists(ANALYTICS_FILE):
        with open(ANALYTICS_FILE, 'r') as f:
            return json.load(f)
    return {
        'total_sessions': 0,
        'total_gestures': 0,
        'gesture_counts': {'thanks': 0, 'i love you': 0},
        'hourly_detections': {str(i): 0 for i in range(24)},
        'confidence_sum': 0,
        'confidence_count': 0,
        'daily_sessions': {}
    }

def save_analytics(data):
    with open(ANALYTICS_FILE, 'w') as f:
        json.dump(data, f)

analytics = load_analytics()

def generate_api_key():
    prefix = 'sb_live_'
    chars = string.ascii_lowercase + string.digits
    unique = ''.join(secrets.choice(chars) for _ in range(24))
    return prefix + unique

def generate_token(length=32):
    return secrets.token_hex(length)

def get_session_user(token):
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(adapt_query('''
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.session_token = ? AND s.expires_at > ?
    '''), (token, datetime.now().isoformat()))
    user = fetchone_dict(cursor)
    conn.close()
    return user

def get_admin_session(token):
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(adapt_query('''
        SELECT a.* FROM admins a
        JOIN admin_sessions s ON a.id = s.admin_id
        WHERE s.session_token = ? AND s.expires_at > ?
    '''), (token, datetime.now().isoformat()))
    admin = fetchone_dict(cursor)
    conn.close()
    return admin

client_sequences = {}
client_predictions = {}
client_last_prediction = {}
client_hand_frames = {}
client_gesture_counts = {}

def extract_keypoints(results):
    pose = np.array([[res.x, res.y, res.z, res.visibility]
                     for res in results.pose_landmarks.landmark]).flatten() \
                     if results.pose_landmarks else np.zeros(33*4)
    face = np.array([[res.x, res.y, res.z]
                     for res in results.face_landmarks.landmark]).flatten() \
                     if results.face_landmarks else np.zeros(468*3)
    lh = np.array([[res.x, res.y, res.z]
                   for res in results.left_hand_landmarks.landmark]).flatten() \
                   if results.left_hand_landmarks else np.zeros(21*3)
    rh = np.array([[res.x, res.y, res.z]
                   for res in results.right_hand_landmarks.landmark]).flatten() \
                   if results.right_hand_landmarks else np.zeros(21*3)
    return np.concatenate([pose, face, lh, rh])

def get_landmarks_for_drawing(results):
    landmarks = {}
    if results.left_hand_landmarks:
        landmarks['left_hand'] = [{'x': lm.x, 'y': lm.y} for lm in results.left_hand_landmarks.landmark]
    if results.right_hand_landmarks:
        landmarks['right_hand'] = [{'x': lm.x, 'y': lm.y} for lm in results.right_hand_landmarks.landmark]
    if results.pose_landmarks:
        landmarks['pose'] = [{'x': lm.x, 'y': lm.y} for lm in results.pose_landmarks.landmark]
    return landmarks

def process_frame(frame):
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image_rgb.flags.writeable = False
    results = holistic.process(image_rgb)
    return results

def translate_text(text, target_language):
    try:
        text_lower = text.lower().strip()
        if text_lower in TRANSLATIONS:
            if target_language in TRANSLATIONS[text_lower]:
                return TRANSLATIONS[text_lower][target_language]
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_language}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data['responseData']['translatedText']
    except Exception as e:
        print("Translation error:", str(e))
        return text

@app.route('/api/superadmin/login', methods=['POST'])
def superadmin_login():
    try:
        data = request.get_json()
        password = data.get('password', '')
        if password == SUPER_ADMIN_PASSWORD:
            return jsonify({'success': True, 'role': 'superadmin', 'name': 'Super Admin', 'permissions': 'all'})
        return jsonify({'error': 'Invalid password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/superadmin/admins', methods=['GET'])
def get_admins():
    try:
        admin_key = request.headers.get('X-Admin-Key', '')
        if admin_key != SUPER_ADMIN_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, role, permissions, created_at, last_login, is_active, created_by FROM admins ORDER BY created_at DESC')
        admins = fetchall_dict(cursor)
        conn.close()
        return jsonify(admins)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/superadmin/admins', methods=['POST'])
def create_admin():
    try:
        admin_key = request.headers.get('X-Admin-Key', '')
        if admin_key != SUPER_ADMIN_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        permissions = data.get('permissions', 'overview,model,analytics,environment,contributions,users')
        if not name or not email or not password:
            return jsonify({'error': 'Name, email and password required'}), 400
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('SELECT id FROM admins WHERE email = ?'), (email,))
        if fetchone_dict(cursor):
            conn.close()
            return jsonify({'error': 'Email already registered'}), 400
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(adapt_query('''
            INSERT INTO admins (name, email, password_hash, role, permissions, created_at, created_by)
            VALUES (?, ?, ?, 'admin', ?, ?, 'superadmin')
        '''), (name, email, password_hash, permissions, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Admin {name} created successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/superadmin/admins/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    try:
        admin_key = request.headers.get('X-Admin-Key', '')
        if admin_key != SUPER_ADMIN_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json()
        permissions = data.get('permissions', '')
        is_active = data.get('is_active', 1)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('UPDATE admins SET permissions = ?, is_active = ? WHERE id = ?'),
                      (permissions, is_active, admin_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/superadmin/admins/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    try:
        admin_key = request.headers.get('X-Admin-Key', '')
        if admin_key != SUPER_ADMIN_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('DELETE FROM admins WHERE id = ?'), (admin_id,))
        cursor.execute(adapt_query('DELETE FROM admin_sessions WHERE admin_id = ?'), (admin_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('SELECT * FROM admins WHERE email = ? AND is_active = 1'), (email,))
        admin = fetchone_dict(cursor)
        if not admin or not bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        cursor.execute(adapt_query('UPDATE admins SET last_login = ? WHERE id = ?'),
                      (datetime.now().isoformat(), admin['id']))
        session_token = generate_token()
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()
        cursor.execute(adapt_query('''
            INSERT INTO admin_sessions (admin_id, session_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        '''), (admin['id'], session_token, datetime.now().isoformat(), expires_at))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'session_token': session_token,
            'name': admin['name'],
            'email': admin['email'],
            'role': admin['role'],
            'permissions': admin['permissions']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/me')
def admin_me():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        admin = get_admin_session(token)
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 401
        return jsonify({
            'id': admin['id'],
            'name': admin['name'],
            'email': admin['email'],
            'role': admin['role'],
            'permissions': admin['permissions']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(adapt_query('DELETE FROM admin_sessions WHERE session_token = ?'), (token,))
            conn.commit()
            conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        purpose = data.get('purpose', '').strip()
        if not name or not email or not password:
            return jsonify({'error': 'Name, email and password are required'}), 400
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Invalid email address'}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('SELECT id FROM users WHERE email = ?'), (email,))
        if fetchone_dict(cursor):
            conn.close()
            return jsonify({'error': 'Email already registered. Please login instead.'}), 400
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(adapt_query('''
            INSERT INTO users (name, email, password_hash, is_verified, created_at)
            VALUES (?, ?, ?, 1, ?)
        '''), (name, email, password_hash, datetime.now().isoformat()))
        conn.commit()
        cursor.execute(adapt_query('SELECT id FROM users WHERE email = ?'), (email,))
        user_record = fetchone_dict(cursor)
        user_id = user_record['id']
        api_key = generate_api_key()
        cursor.execute(adapt_query('''
            INSERT INTO api_keys (user_id, api_key, purpose, created_at)
            VALUES (?, ?, ?, ?)
        '''), (user_id, api_key, purpose, datetime.now().isoformat()))
        session_token = generate_token()
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        cursor.execute(adapt_query('''
            INSERT INTO sessions (user_id, session_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        '''), (user_id, session_token, datetime.now().isoformat(), expires_at))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'session_token': session_token,
            'api_key': api_key,
            'name': name,
            'email': email
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('SELECT * FROM users WHERE email = ?'), (email,))
        user = fetchone_dict(cursor)
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            conn.close()
            return jsonify({'error': 'Invalid email or password'}), 401
        cursor.execute(adapt_query('UPDATE users SET last_login = ? WHERE id = ?'),
                      (datetime.now().isoformat(), user['id']))
        session_token = generate_token()
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        cursor.execute(adapt_query('''
            INSERT INTO sessions (user_id, session_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        '''), (user['id'], session_token, datetime.now().isoformat(), expires_at))
        cursor.execute(adapt_query('SELECT api_key FROM api_keys WHERE user_id = ? AND is_active = 1 LIMIT 1'),
                      (user['id'],))
        key_record = fetchone_dict(cursor)
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'session_token': session_token,
            'api_key': key_record['api_key'] if key_record else None,
            'name': user['name'],
            'email': user['email']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(adapt_query('DELETE FROM sessions WHERE session_token = ?'), (token,))
            conn.commit()
            conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me')
def get_me():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_session_user(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('''
            SELECT api_key, usage_count, last_used, created_at, purpose
            FROM api_keys WHERE user_id = ? AND is_active = 1 LIMIT 1
        '''), (user['id'],))
        key_record = fetchone_dict(cursor)
        conn.close()
        return jsonify({
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'created_at': user['created_at'],
            'last_login': user['last_login'],
            'api_key': key_record if key_record else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/regenerate-key', methods=['POST'])
def regenerate_key():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_session_user(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('UPDATE api_keys SET is_active = 0 WHERE user_id = ?'), (user['id'],))
        new_key = generate_api_key()
        cursor.execute(adapt_query('''
            INSERT INTO api_keys (user_id, api_key, purpose, created_at)
            VALUES (?, ?, ?, ?)
        '''), (user['id'], new_key, '', datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'api_key': new_key})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users')
def admin_get_users():
    try:
        admin_key = request.headers.get('X-Admin-Key', '')
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        admin = get_admin_session(token) if token else None
        if admin_key != SUPER_ADMIN_PASSWORD and not admin:
            return jsonify({'error': 'Unauthorized'}), 401
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(adapt_query('''
            SELECT u.id, u.name, u.email, u.created_at, u.last_login,
                   k.api_key, k.usage_count, k.last_used
            FROM users u
            LEFT JOIN api_keys k ON u.id = k.user_id AND k.is_active = 1
            ORDER BY u.created_at DESC
        '''))
        users = fetchall_dict(cursor)
        conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return jsonify({'status': 'running', 'message': 'Sign Language Translation API', 'version': '1.0'})

@app.route('/api/gestures')
def get_gestures():
    return jsonify({'gestures': actions.tolist(), 'count': len(actions)})

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/translate', methods=['POST'])
def translate():
    data = request.get_json()
    text = data.get('text', '')
    target_language = data.get('target_language', 'en')
    if not text:
        return jsonify({'translated': ''})
    translated = translate_text(text, target_language)
    return jsonify({'translated': translated})

@app.route('/api/contribute', methods=['POST'])
def contribute():
    try:
        data = request.get_json()
        gesture = data.get('gesture', '').lower().strip()
        contribution = {
            'gesture': gesture,
            'confidence': data.get('confidence', 0),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'keypoints': data.get('keypoints', [])
        }
        filename = f"contributions_{gesture.replace(' ', '_')}.json"
        contributions = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                contributions = json.load(f)
        contributions.append(contribution)
        with open(filename, 'w') as f:
            json.dump(contributions, f)
        return jsonify({'status': 'saved', 'total': len(contributions)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contributions/stats')
def contribution_stats():
    try:
        stats = {}
        for action in ['thanks', 'i love you']:
            filename = f"contributions_{action.replace(' ', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                stats[action] = len(data)
            else:
                stats[action] = 0
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contributions/recent')
def contributions_recent():
    try:
        all_contributions = []
        for action in ['thanks', 'i love you']:
            filename = f"contributions_{action.replace(' ', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                all_contributions.extend(data)
        all_contributions.sort(key=lambda x: x.get('timestamp', ''))
        return jsonify(all_contributions[-50:])
    except Exception as e:
        return jsonify([])

@app.route('/api/contributions/export')
def contributions_export():
    try:
        all_contributions = []
        for action in ['thanks', 'i love you']:
            filename = f"contributions_{action.replace(' ', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                all_contributions.extend(data)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['timestamp', 'gesture', 'confidence'])
        for c in all_contributions:
            writer.writerow([c.get('timestamp', ''), c.get('gesture', ''), c.get('confidence', '')])
        return Response(output.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': 'attachment;filename=contributions.csv'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    try:
        avg_confidence = 0
        if analytics['confidence_count'] > 0:
            avg_confidence = analytics['confidence_sum'] / analytics['confidence_count']
        most_popular = max(analytics['gesture_counts'], key=analytics['gesture_counts'].get)
        return jsonify({
            'total_sessions': analytics['total_sessions'],
            'total_gestures': analytics['total_gestures'],
            'gesture_counts': analytics['gesture_counts'],
            'hourly_detections': analytics['hourly_detections'],
            'avg_confidence': round(avg_confidence * 100, 1),
            'most_popular_gesture': most_popular,
            'daily_sessions': analytics['daily_sessions']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    client_sequences[client_id] = []
    client_predictions[client_id] = []
    client_last_prediction[client_id] = -1
    client_hand_frames[client_id] = 0
    client_gesture_counts[client_id] = 0
    analytics['total_sessions'] += 1
    today = datetime.now().strftime('%Y-%m-%d')
    if today not in analytics['daily_sessions']:
        analytics['daily_sessions'][today] = 0
    analytics['daily_sessions'][today] += 1
    save_analytics(analytics)
    print("Client connected:", client_id)
    emit('connected', {'message': 'Connected to Sign Language API'})

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    client_sequences.pop(client_id, None)
    client_predictions.pop(client_id, None)
    client_last_prediction.pop(client_id, None)
    client_hand_frames.pop(client_id, None)
    client_gesture_counts.pop(client_id, None)
    print("Client disconnected:", client_id)

@socketio.on('frame')
def handle_frame(data):
    client_id = request.sid
    try:
        frame_data = data['frame'].split(',')[1]
        frame_bytes = base64.b64decode(frame_data)
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        if frame is None:
            emit('error', {'message': 'Invalid frame'})
            return
        results = process_frame(frame)
        hand_detected = (results.left_hand_landmarks is not None or
                        results.right_hand_landmarks is not None)
        if hand_detected:
            client_hand_frames[client_id] += 1
        else:
            client_hand_frames[client_id] = 0
            client_predictions[client_id] = []
            client_last_prediction[client_id] = -1
        keypoints = extract_keypoints(results)
        client_sequences[client_id].append(keypoints)
        client_sequences[client_id] = client_sequences[client_id][-30:]
        landmarks = get_landmarks_for_drawing(results)
        prediction_result = {
            'gesture': '',
            'confidence': 0.0,
            'hand_detected': hand_detected,
            'sequence_length': len(client_sequences[client_id]),
            'landmarks': landmarks
        }
        if len(client_sequences[client_id]) == 30:
            sequence = np.expand_dims(client_sequences[client_id], axis=0)
            res = predict(tf.constant(sequence, dtype=tf.float32)).numpy()[0]
            current_pred = np.argmax(res)
            confidence = float(res[current_pred])
            if current_pred != client_last_prediction[client_id]:
                client_predictions[client_id] = []
                client_last_prediction[client_id] = current_pred
            client_predictions[client_id].append(current_pred)
            client_predictions[client_id] = client_predictions[client_id][-10:]
            predicted_action = actions[current_pred]
            prediction_result['probabilities'] = res.tolist()
            if len(client_predictions[client_id]) >= 10:
                last_preds = client_predictions[client_id][-10:]
                if len(set(last_preds)) == 1:
                    if confidence > 0.999 and hand_detected and client_hand_frames[client_id] >= 10:
                        prediction_result['gesture'] = predicted_action
                        prediction_result['confidence'] = confidence
                        analytics['total_gestures'] += 1
                        analytics['gesture_counts'][predicted_action] = \
                            analytics['gesture_counts'].get(predicted_action, 0) + 1
                        hour = str(datetime.now().hour)
                        analytics['hourly_detections'][hour] = \
                            analytics['hourly_detections'].get(hour, 0) + 1
                        analytics['confidence_sum'] += confidence
                        analytics['confidence_count'] += 1
                        save_analytics(analytics)
            prediction_result['confidence'] = confidence
        emit('prediction', prediction_result)
    except Exception as e:
        print("Error processing frame:", str(e))
        emit('error', {'message': str(e)})


# ─── Model Retraining Routes ───────────────────────────────────────

import threading
retraining_status = {'status': 'idle', 'progress': 0, 'message': '', 'accuracy': 0}

@app.route('/api/admin/retrain/status')
def retrain_status():
    return jsonify(retraining_status)

@app.route('/api/admin/retrain/start', methods=['POST'])
def start_retrain():
    admin_key = request.headers.get('X-Admin-Key', '')
    if admin_key != SUPER_ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    # Check minimum contributions
    thanks_file = 'contributions_thanks.json'
    ily_file = 'contributions_i_love_you.json'

    thanks_count = 0
    ily_count = 0

    if os.path.exists(thanks_file):
        with open(thanks_file, 'r') as f:
            thanks_count = len(json.load(f))
    if os.path.exists(ily_file):
        with open(ily_file, 'r') as f:
            ily_count = len(json.load(f))

    if thanks_count < 20 or ily_count < 20:
        return jsonify({
            'error': f'Not enough contributions. Need at least 20 per gesture. Have: thanks={thanks_count}, i love you={ily_count}'
        }), 400

    if retraining_status['status'] == 'running':
        return jsonify({'error': 'Retraining already in progress'}), 400

    thread = threading.Thread(target=run_retraining, args=(thanks_count, ily_count))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'message': 'Retraining started'})

@app.route('/api/admin/retrain/rollback', methods=['POST'])
def rollback_model():
    admin_key = request.headers.get('X-Admin-Key', '')
    if admin_key != SUPER_ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        backup_path = 'model/action_backup.keras'
        model_path = 'model/action.keras'
        if os.path.exists(backup_path):
            import shutil
            shutil.copy(backup_path, model_path)
            global model, predict
            model = tf.keras.models.load_model(model_path)
            predict = tf.function(reduce_retracing=True)(lambda x: model(x, training=False))
            print("Model rolled back and predict function rebuilt!")
            return jsonify({'success': True, 'message': 'Model rolled back to previous version'})
        return jsonify({'error': 'No backup found'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_retraining(thanks_count, ily_count):
    global model, retraining_status
    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        from tensorflow.keras.utils import to_categorical
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense
        from tensorflow.keras.optimizers import Adam
        import shutil

        retraining_status = {'status': 'running', 'progress': 5, 'message': 'Loading original training data...', 'accuracy': 0}

        # Load original MP_Data
        DATA_PATH = '/Users/sasmitha/Desktop/venv/MP_Data'
        actions_list = ['thanks', 'i love you']
        sequence_length = 30
        no_sequences = 150

        sequences = []
        labels = []
        label_map = {'thanks': 0, 'i love you': 1}

        # Load original data
        for action in actions_list:
            for sequence in range(no_sequences):
                window = []
                seq_path = os.path.join(DATA_PATH, action, str(sequence))
                if not os.path.exists(seq_path):
                    continue
                for frame_num in range(sequence_length):
                    frame_path = os.path.join(seq_path, f"{frame_num}.npy")
                    if os.path.exists(frame_path):
                        res = np.load(frame_path)
                        window.append(res)
                if len(window) == sequence_length:
                    sequences.append(window)
                    labels.append(label_map[action])

        retraining_status['progress'] = 20
        retraining_status['message'] = 'Loading crowdsourced contributions...'

        # Load contributions
        for action in actions_list:
            filename = f"contributions_{action.replace(' ', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    contributions = json.load(f)
                for contrib in contributions:
                    keypoints = contrib.get('keypoints', [])
                    if keypoints and len(keypoints) == sequence_length:
                        sequences.append(keypoints)
                        labels.append(label_map[action])

        retraining_status['progress'] = 35
        retraining_status['message'] = f'Preparing {len(sequences)} sequences for training...'

        X = np.array(sequences)
        y = to_categorical(labels).astype(int)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.05, random_state=42)

        retraining_status['progress'] = 40
        retraining_status['message'] = 'Building new model...'

        new_model = Sequential([
            LSTM(64, return_sequences=True, activation='relu', input_shape=(30, 1662)),
            LSTM(128, return_sequences=True, activation='relu'),
            LSTM(64, return_sequences=False, activation='relu'),
            Dense(64, activation='relu'),
            Dense(32, activation='relu'),
            Dense(2, activation='softmax')
        ])
        new_model.compile(
            optimizer=Adam(learning_rate=0.0001),
            loss='categorical_crossentropy',
            metrics=['categorical_accuracy']
        )

        retraining_status['progress'] = 45
        retraining_status['message'] = 'Training new model (this takes a few minutes)...'

        new_model.fit(X_train, y_train, epochs=500, verbose=0)

        retraining_status['progress'] = 85
        retraining_status['message'] = 'Evaluating new model accuracy...'

        yhat = new_model.predict(X_test, verbose=0)
        ytrue = np.argmax(y_test, axis=1)
        ypred = np.argmax(yhat, axis=1)
        accuracy = float(np.mean(ytrue == ypred))

        retraining_status['progress'] = 90
        retraining_status['message'] = f'New model accuracy: {accuracy*100:.1f}%'
        retraining_status['accuracy'] = round(accuracy * 100, 1)

        if accuracy >= 0.95:
            retraining_status['message'] = f'Accuracy {accuracy*100:.1f}% passed threshold! Deploying new model...'

            # Backup current model
            shutil.copy('model/action.keras', 'model/action_backup.keras')

            # Save and deploy new model
            new_model.save('model/action_new.keras')
            shutil.copy('model/action_new.keras', 'model/action.keras')

            # Reload model in server
            global predict
            model = tf.keras.models.load_model('model/action.keras')
            predict = tf.function(reduce_retracing=True)(lambda x: model(x, training=False))
            print("New model deployed and predict function rebuilt!")

            # Save model metadata
            models_meta = load_models_meta()
            new_meta = {
                'id': f'model_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'name': f'SB-LSTM-v2.{len(models_meta)}-community-{datetime.now().strftime("%Y%m%d")}',
                'accuracy': round(accuracy * 100, 1),
                'training_sequences': len(sequences),
                'contributions_used': thanks_count + ily_count,
                'epochs': 500,
                'created_at': datetime.now().isoformat(),
                'status': 'active',
                'file': 'action.keras'
            }
            # Mark previous as inactive
            for m in models_meta:
                m['status'] = 'backup'
            models_meta.append(new_meta)
            save_models_meta(models_meta)

            retraining_status = {
                'status': 'completed',
                'progress': 100,
                'message': f'Model successfully updated! New accuracy: {accuracy*100:.1f}%',
                'accuracy': round(accuracy * 100, 1),
                'model_id': new_meta['id']
            }
        else:
            retraining_status = {
                'status': 'rejected',
                'progress': 100,
                'message': f'New model accuracy {accuracy*100:.1f}% below 95% threshold. Keeping original model.',
                'accuracy': round(accuracy * 100, 1)
            }

    except Exception as e:
        retraining_status = {
            'status': 'error',
            'progress': 0,
            'message': f'Retraining failed: {str(e)}',
            'accuracy': 0
        }
        print("Retraining error:", str(e))

@app.route('/api/admin/models')
def get_models():
    admin_key = request.headers.get('X-Admin-Key', '')
    if admin_key != SUPER_ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    models = load_models_meta()
    return jsonify(models)

@app.route('/api/admin/models/activate/<model_id>', methods=['POST'])
def activate_model(model_id):
    admin_key = request.headers.get('X-Admin-Key', '')
    if admin_key != SUPER_ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        models = load_models_meta()
        target = None
        for m in models:
            if m['id'] == model_id:
                target = m
                break
        if not target:
            return jsonify({'error': 'Model not found'}), 404

        # Check which file to load
        file_map = {
            'model_original': 'model/action.keras',
            'active': 'model/action.keras',
            'backup': 'model/action_backup.keras'
        }

        model_file = 'model/action_backup.keras' if target.get('status') == 'backup' else 'model/action.keras'

        if not os.path.exists(model_file):
            return jsonify({'error': f'Model file not found: {model_file}'}), 404

        import shutil
        global model, predict

        # Backup current if activating backup
        if target.get('status') == 'backup':
            shutil.copy('model/action.keras', 'model/action_temp.keras')
            shutil.copy(model_file, 'model/action.keras')

        model = tf.keras.models.load_model('model/action.keras')
        predict = tf.function(reduce_retracing=True)(lambda x: model(x, training=False))

        # Update metadata
        for m in models:
            m['status'] = 'backup'
        target['status'] = 'active'
        save_models_meta(models)

        return jsonify({'success': True, 'message': f'Model {target["name"]} activated!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Sign Language Translation Server...")
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
