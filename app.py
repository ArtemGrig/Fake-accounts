from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO
import pandas as pd

import database as db
from graph_engine      import GraphEngine
from activity_analyzer import ActivityAnalyzer
from classifier        import FakeAccountClassifier
import bot_simulator   as bots
import vk_analyzer

app = Flask(__name__)
app.secret_key = 'coursework_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins='*')

@app.context_processor
def inject_globals():
    uid = session.get('real_user_id', session.get('user_id'))
    return dict(
        is_admin_user = bool(uid and db.is_admin(uid)),
        session       = session,
    )

@app.context_processor
def inject_admin():
    """Делает is_admin доступным во всех шаблонах."""
    uid = session.get('real_user_id', session.get('user_id'))
    return dict(is_admin_user=uid and db.is_admin(uid))

db.init_db()
db.seed_initial_users()

# Вспомогательная функция анализа

def run_analysis():
    users = db.get_all_users()
    if len(users) < 2:
        return None

    follows  = db.get_follows()
    activity = db.get_activity_log()

    if not follows:
        return None

    users_df = pd.DataFrame([{
        'user_id':  u['id'],
        'username': u['username'],
        'is_bot':   u['is_bot'],
    } for u in users])

    edges_df = pd.DataFrame([{
        'source_id': f['follower_id'],
        'target_id': f['target_id'],
    } for f in follows])

    engine = GraphEngine()
    engine.build_graph(edges_df)
    g_feat = engine.extract_features()

    if activity:
        act_df = pd.DataFrame([{
            'user_id':     a['user_id'],
            'timestamp':   a['created_at'],
            'action_type': a['action'],
        } for a in activity])
        analyzer = ActivityAnalyzer()
        b_feat   = analyzer.extract_features(act_df)
        all_feat = g_feat.merge(b_feat, on='user_id', how='left').fillna(0)
    else:
        all_feat = g_feat.fillna(0)

    clf     = FakeAccountClassifier(contamination=0.1)
    results = clf.fit_predict(all_feat)
    results = results.merge(users_df, on='user_id', how='left')

    return results, engine.G


# Страницы

@app.route('/')
def index():
    all_users = db.get_all_users()
    user_id   = session.get('user_id')

    posts_data = []
    for p in db.get_all_posts():
        comments_list = db.get_comments(p['id'])
        posts_data.append({
            'id':             p['id'],
            'username':       p['username'],
            'content':        p['content'],
            'created_at':     p['created_at'],
            'likes':          db.get_likes_count(p['id']),
            'comments':       comments_list,
            'comments_count': len(comments_list),
        })

    following_ids = []
    if user_id:
        following_ids = [
            f['target_id'] for f in db.get_follows()
            if f['follower_id'] == user_id
        ]

    return render_template('index.html',
        posts            = posts_data,
        users            = all_users,
        current_user_id  = user_id,
        current_username = session.get('username'),
        following_ids    = following_ids,
        bot_running      = bots.is_running(session.get('user_id', 0)),
        real_user_id     = session.get('real_user_id', user_id),
        real_users_count = sum(1 for u in all_users if u['is_bot'] == 0),
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username  = request.form['username'].strip()
        password  = request.form['password'].strip()
        bot_count = int(request.form.get('bot_count', 0))

        if not username or not password:
            error = 'Заполни все поля'
        elif db.create_user(username, password):
            user = db.get_user(username)
            session['user_id']  = user['id']
            session['username'] = username

            # Создаём ботов и привязываем к аккаунту
            if bot_count > 0:
                db.create_bots_for_owner(user['id'], bot_count)

            return redirect(url_for('index'))
        else:
            error = 'Такой пользователь уже существует'
    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        user = db.get_user(username)
        if user and user['password'] == password:
            session['user_id']  = user['id']
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Неверный логин или пароль'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/graph')
def graph():
    return render_template('graph.html',
        current_username = session.get('username'),
        bot_running      = bots.is_running(session.get('user_id', 0)),
        real_user_id     = session.get('real_user_id', session.get('user_id')),
    )


# Вход под ботом / возврат

@app.route('/login-as-bot/<int:bot_id>')
def login_as_bot(bot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.get_user_by_id(bot_id)
    if user and user['is_bot'] == 1:
        # Сохраняем реальный ID только если ещё не в режиме бота
        if not session.get('is_bot_session'):
            session['real_user_id'] = session['user_id']
        session['user_id']        = user['id']
        session['username']       = user['username']
        session['is_bot_session'] = True
    return redirect(url_for('index'))


@app.route('/login-back')
def login_back():
    real_id = session.get('real_user_id')
    if real_id:
        user = db.get_user_by_id(real_id)
        if user:
            session['user_id']  = user['id']
            session['username'] = user['username']
    session.pop('is_bot_session', None)
    session.pop('real_user_id', None)
    return redirect(url_for('index'))


@app.route('/post', methods=['POST'])
def post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form.get('content', '').strip()
    if content:
        db.create_post(session['user_id'], content)
    return redirect(url_for('index'))


@app.route('/like/<int:post_id>')
def like(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db.like_post(session['user_id'], post_id)
    return redirect(url_for('index'))


@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form.get('content', '').strip()
    if content:
        db.add_comment(session['user_id'], post_id, content)
    return redirect(url_for('index'))


@app.route('/follow/<int:target_id>')
def follow(target_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    if uid == target_id:
        return redirect(url_for('index'))
    if db.is_following(uid, target_id):
        db.unfollow_user(uid, target_id)
    else:
        db.follow_user(uid, target_id)
    return redirect(url_for('index'))


@app.route('/api/graph')
def api_graph():
    result = run_analysis()
    if result is None:
        return jsonify({'nodes': [], 'edges': [], 'stats': {}})

    results_df, G = result

    nodes = []
    for _, row in results_df.iterrows():
        nodes.append({
            'id':          int(row['user_id']),
            'username':    str(row.get('username', f"user_{row['user_id']}")),
            'is_fake':     int(row['is_fake']),
            'final_score': round(float(row['final_score']), 3),
            'in_degree':   int(row['in_degree']),
            'out_degree':  int(row['out_degree']),
            'ff_ratio':    round(float(row['ff_ratio']), 2),
            'burst_score': round(float(row['burst_score']), 3),
            'is_bot':      int(row.get('is_bot', 0)),
        })

    edges   = [{'from': int(u), 'to': int(v)} for u, v in G.edges()]
    n_fake  = int(results_df['is_fake'].sum())
    n_total = len(results_df)

    return jsonify({
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'total':       n_total,
            'fake':        n_fake,
            'legit':       n_total - n_fake,
            'percent':     round(n_fake / n_total * 100, 1) if n_total else 0,
            'bot_running': bots.is_running(session.get('user_id', 0)),
        }
    })


@app.route('/api/bots/start')
def api_bots_start():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'running': False})
    uid     = session['user_id']
    my_bots = db.get_my_bots(uid)
    if my_bots:
        bots.start_simulation(uid)
    else:
        bots.start_human_simulation(uid)
    return jsonify({'ok': True, 'running': True})


@app.route('/api/bots/stop')
def api_bots_stop():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'running': False})
    uid = session['user_id']
    bots.stop_simulation(uid)
    # Останавливаем и привязанных ботов
    my_bots = db.get_my_bots(uid)
    for b in my_bots:
        bots.stop_single_bot(b['id'])
    return jsonify({'ok': True, 'running': False})


@app.route('/api/post', methods=['POST'])
def api_post():
    if 'user_id' not in session:
        return jsonify({'ok': False})
    data = request.get_json()
    db.create_post(session['user_id'], data['content'])
    return jsonify({'ok': True})


@app.route('/api/like/<int:post_id>', methods=['POST'])
def api_like(post_id):
    if 'user_id' not in session:
        return jsonify({'ok': False})
    db.like_post(session['user_id'], post_id)
    return jsonify({'ok': True, 'likes': db.get_likes_count(post_id)})


@app.route('/api/comment/<int:post_id>', methods=['POST'])
def api_comment(post_id):
    if 'user_id' not in session:
        return jsonify({'ok': False})
    data    = request.get_json()
    content = data.get('content', '').strip()
    if content:
        db.add_comment(session['user_id'], post_id, content)
    return jsonify({
        'ok':       True,
        'username': session['username'],
        'content':  content,
        'time':     db.now()[11:16],
    })


@app.route('/api/follow/<int:target_id>', methods=['POST'])
def api_follow(target_id):
    if 'user_id' not in session:
        return jsonify({'ok': False})
    uid = session['user_id']
    if uid == target_id:
        return jsonify({'ok': False})
    if db.is_following(uid, target_id):
        db.unfollow_user(uid, target_id)
        return jsonify({'ok': True, 'following': False})
    else:
        db.follow_user(uid, target_id)
        return jsonify({'ok': True, 'following': True})


@app.route('/api/feed')
def api_feed():
    posts_data = []
    for p in db.get_all_posts():
        comments_list = db.get_comments(p['id'])
        posts_data.append({
            'id':             p['id'],
            'username':       p['username'],
            'content':        p['content'],
            'created_at':     p['created_at'],
            'likes':          db.get_likes_count(p['id']),
            'comments_count': len(comments_list),
        })
    return jsonify({'posts': posts_data})


@app.route('/api/bots/list')
def api_bots_list():
    """Только свои боты — привязанные к текущему аккаунту."""
    if 'user_id' not in session:
        return jsonify({'bots': []})
    # Берём реальный ID владельца (не бота)
    owner_id = session.get('real_user_id', session['user_id'])
    my_bots  = db.get_my_bots(owner_id)
    return jsonify({
        'bots': [{'id': b['id'], 'username': b['username']} for b in my_bots]
    })

# Админка

def admin_required(f):
    """Декоратор — только для админа."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        uid = session.get('real_user_id', session['user_id'])
        if not db.is_admin(uid):
            return jsonify({'error': 'Нет доступа'}), 403
        return f(*args, **kwargs)
    return decorated


@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session.get('real_user_id', session['user_id'])
    if not db.is_admin(uid):
        return redirect(url_for('index'))
    return render_template('admin.html',
        current_username = session.get('username'),
        real_user_id     = uid,
    )


@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    users      = db.get_all_users_stats()
    bots_raw   = db.get_all_bots_with_owners()
    all_posts  = db.get_all_posts()
    all_follows= db.get_follows()

    active_owners = []
    for u in users:
        if not u['is_bot']:
            if bots.is_running(u['id']):
                active_owners.append(u['id'])

    bots_info = []
    for b in bots_raw:
        bots_info.append({
            'bot_id':         b['bot_id'],
            'bot_username':   b['bot_username'],
            'owner_id':       b['owner_id'],
            'owner_username': b['owner_username'],
            'is_running':     bots.is_bot_running(b['bot_id']),
        })

    users_list = []
    for u in users:
        users_list.append({
            'id':             u['id'],
            'username':       u['username'],
            'is_bot':         u['is_bot'],
            'is_admin':       u['is_admin'],
            'created_at':     u['created_at'],
            'post_count':     u['post_count'],
            'like_count':     u['like_count'],
            'follower_count': u['follower_count'],
            'following_count':u['following_count'],
        })

    return jsonify({
        'users':         users_list,
        'bots_info':     bots_info,
        'total_posts':   len(all_posts),
        'total_follows': len(all_follows),
        'active_owners': active_owners,
        'total_users':   len([u for u in users if not u['is_bot']]),
        'total_bots':    len([u for u in users if u['is_bot']]),
    })


@app.route('/api/admin/bots/start-all')
@admin_required
def api_admin_bots_start_all():
    users   = db.get_all_users()
    started = []

    for u in users:
        if u['is_admin']:
            continue
        if u['is_bot']:
            # Запускаем каждого бота отдельно
            bots.start_single_bot(u['id'])
            started.append(u['username'])
        else:
            # Запускаем human simulation для людей
            bots.start_human_simulation(u['id'])
            started.append(u['username'])

    return jsonify({'ok': True, 'started': started})


@app.route('/api/admin/bots/stop-all')
@admin_required
def api_admin_bots_stop_all():
    users   = db.get_all_users()
    stopped = []

    for u in users:
        if u['is_admin']:
            continue
        if u['is_bot']:
            bots.stop_single_bot(u['id'])
        else:
            bots.stop_simulation(u['id'])
        stopped.append(u['username'])

    return jsonify({'ok': True, 'stopped': stopped})


@app.route('/api/admin/bots/start/<int:owner_id>')
@admin_required
def api_admin_bots_start_one(owner_id):
    """Запустить подозрительную активность от имени пользователя."""
    user = db.get_user_by_id(owner_id)
    if not user or user['is_bot']:
        return jsonify({'ok': False, 'error': 'Неверный пользователь'})
    bots.start_human_simulation(owner_id)
    return jsonify({'ok': True, 'running': True})


@app.route('/api/admin/bots/stop/<int:owner_id>')
@admin_required
def api_admin_bots_stop_one(owner_id):
    bots.stop_simulation(owner_id)
    # Останавливаем и привязанных ботов
    my_bots = db.get_my_bots(owner_id)
    for b in my_bots:
        bots.stop_single_bot(b['id'])
    return jsonify({'ok': True, 'running': False})


@app.route('/api/admin/user/delete/<int:user_id>')
@admin_required
def api_admin_delete_user(user_id):
    """Удалить пользователя и его ботов."""
    conn = db.get_db()
    # Удаляем привязанных ботов
    bot_rows = conn.execute(
        'SELECT bot_id FROM user_bots WHERE owner_id=?', (user_id,)
    ).fetchall()
    for b in bot_rows:
        conn.execute('DELETE FROM users WHERE id=?', (b['bot_id'],))
    conn.execute('DELETE FROM user_bots WHERE owner_id=?', (user_id,))
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.execute('DELETE FROM follows WHERE follower_id=? OR target_id=?',
                 (user_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/bot/start/<int:bot_id>')
@admin_required
def api_admin_single_bot_start(bot_id):
    user = db.get_user_by_id(bot_id)
    if not user or not user['is_bot']:
        return jsonify({'ok': False, 'error': 'Не бот'})
    result = bots.start_single_bot(bot_id)
    print(f"[ADMIN] start_single_bot({bot_id}) = {result}")
    print(f"[ADMIN] is_bot_running({bot_id}) = {bots.is_bot_running(bot_id)}")
    return jsonify({'ok': True, 'running': True})


@app.route('/api/admin/bot/stop/<int:bot_id>')
@admin_required
def api_admin_single_bot_stop(bot_id):
    bots.stop_single_bot(bot_id)
    print(f"[ADMIN] stop_single_bot({bot_id}), is_running={bots.is_bot_running(bot_id)}")
    return jsonify({'ok': True, 'running': False})

# VK Анализатор

@app.route('/vk')
def vk_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('vk.html',
        current_username = session.get('username'),
        real_user_id     = session.get('real_user_id', session.get('user_id')),
    )


@app.route('/api/vk/analyze', methods=['POST'])
def api_vk_analyze():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'Не авторизован'})
    data  = request.get_json()
    url   = data.get('url', '').strip()
    token = data.get('token', '').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'Укажи ссылку на профиль'})
    if not token:
        return jsonify({'ok': False, 'error': 'Укажи VK Access Token'})
    try:
        result   = vk_analyzer.analyze_profile(url, token)
        owner_id = session.get('real_user_id', session['user_id'])
        db.save_vk_check(owner_id, result)
        return jsonify({'ok': True, 'result': result})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)})
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Ошибка API: {str(e)}'})


@app.route('/api/vk/history')
def api_vk_history():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'history': []})
    owner_id = session.get('real_user_id', session['user_id'])
    history  = db.get_vk_history(owner_id)
    return jsonify({'ok': True, 'history': history})


@app.route('/api/vk/history/delete/<int:check_id>', methods=['DELETE'])
def api_vk_history_delete(check_id):
    if 'user_id' not in session:
        return jsonify({'ok': False})
    owner_id = session.get('real_user_id', session['user_id'])
    db.delete_vk_check(check_id, owner_id)
    return jsonify({'ok': True})

# Аномальный режим

@app.route('/api/admin/anomaly/start-all')
@admin_required
def api_anomaly_start_all():
    """Запустить аномальный режим для всех ботов."""
    started = bots.start_all_anomaly()
    return jsonify({'ok': True, 'started': started, 'count': len(started)})


@app.route('/api/admin/anomaly/stop-all')
@admin_required
def api_anomaly_stop_all():
    """Остановить аномальный режим."""
    bots.stop_all_anomaly()
    return jsonify({'ok': True})


@app.route('/api/admin/anomaly/start/<int:bot_id>')
@admin_required
def api_anomaly_start_one(bot_id):
    user = db.get_user_by_id(bot_id)
    if not user or not user['is_bot']:
        return jsonify({'ok': False, 'error': 'Не бот'})
    bots.start_anomaly_mode(bot_id)
    return jsonify({'ok': True, 'running': True})


@app.route('/api/admin/anomaly/stop/<int:bot_id>')
@admin_required
def api_anomaly_stop_one(bot_id):
    bots.stop_anomaly_mode(bot_id)
    return jsonify({'ok': True, 'running': False})


@app.route('/api/admin/anomaly/status')
@admin_required
def api_anomaly_status():
    """Статус аномального режима для всех ботов."""
    all_users = db.get_all_users()
    result = {}
    for u in all_users:
        if u['is_bot']:
            result[u['id']] = bots.is_anomaly_running(u['id'])
    any_active = any(result.values())
    return jsonify({'ok': True, 'statuses': result, 'any_active': any_active})

@app.route('/api/admin/anomaly/start-random')
@admin_required
def api_anomaly_start_random():
    started = bots.start_random_anomaly(count=2)
    if not started:
        return jsonify({'ok': False, 'error': 'Ботов нет в системе'})
    return jsonify({'ok': True, 'started': started, 'count': len(started)})


@app.route('/api/admin/anomaly/stop-random')
@admin_required
def api_anomaly_stop_random():
    count = bots.stop_random_anomaly()
    return jsonify({'ok': True, 'stopped': count})


@app.route('/api/graph/reset', methods=['POST'])
def api_graph_reset():
    if 'user_id' not in session:
        return jsonify({'ok': False})
    uid = session.get('real_user_id', session.get('user_id'))
    if not db.is_admin(uid):
        return jsonify({'ok': False, 'error': 'Только для администратора'})
    bots.stop_all_anomaly()
    all_users = db.get_all_users()
    for u in all_users:
        bots.stop_simulation(u['id'])
        if u['is_bot']:
            bots.stop_single_bot(u['id'])
    db.reset_all_activity()
    return jsonify({'ok': True})

@app.route('/api/report')
def api_report():
    if 'user_id' not in session:
        return jsonify({'ok': False})

    result = run_analysis()
    if result is None:
        return jsonify({'ok': True, 'suspicious': [], 'total': 0, 'fake_count': 0})

    results_df, G = result
    suspicious = results_df[results_df['is_fake'] == 1].copy()

    conn = db.get_db()
    report_users = []

    for _, row in suspicious.iterrows():
        uid      = int(row['user_id'])
        username = str(row.get('username', f'user_{uid}'))
        is_bot   = int(row.get('is_bot', 0))

        posts_count = conn.execute(
            'SELECT COUNT(*) FROM posts WHERE user_id=?', (uid,)
        ).fetchone()[0]

        likes_count = conn.execute(
            'SELECT COUNT(*) FROM likes WHERE user_id=?', (uid,)
        ).fetchone()[0]

        comments_count = conn.execute(
            'SELECT COUNT(*) FROM comments WHERE user_id=?', (uid,)
        ).fetchone()[0]

        follows_count = conn.execute(
            'SELECT COUNT(*) FROM follows WHERE follower_id=?', (uid,)
        ).fetchone()[0]

        followers_count = conn.execute(
            'SELECT COUNT(*) FROM follows WHERE target_id=?', (uid,)
        ).fetchone()[0]

        night_likes = conn.execute('''
            SELECT COUNT(*) FROM likes
            WHERE user_id=?
            AND CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 0 AND 5
        ''', (uid,)).fetchone()[0]

        burst_data = conn.execute('''
            SELECT strftime('%Y-%m-%d %H:%M', created_at) as minute,
                   COUNT(*) as cnt
            FROM likes WHERE user_id=?
            GROUP BY minute
            ORDER BY cnt DESC LIMIT 1
        ''', (uid,)).fetchone()

        max_per_minute = burst_data['cnt'] if burst_data else 0

        report_users.append({
            'user_id':        uid,
            'username':       username,
            'is_bot':         is_bot,
            'final_score':    round(float(row['final_score']), 3),
            'in_degree':      int(row['in_degree']),
            'out_degree':     int(row['out_degree']),
            'ff_ratio':       round(float(row['ff_ratio']), 2),
            'burst_score':    round(float(row['burst_score']), 3),
            'posts':          posts_count,
            'likes_given':    likes_count,
            'comments':       comments_count,
            'follows':        follows_count,
            'followers':      followers_count,
            'night_likes':    night_likes,
            'max_per_minute': max_per_minute,
        })

    conn.close()
    report_users.sort(key=lambda x: x['final_score'], reverse=True)

    return jsonify({
        'ok':         True,
        'suspicious': report_users,
        'total':      len(results_df),
        'fake_count': len(report_users),
    })

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)