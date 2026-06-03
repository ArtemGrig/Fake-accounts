import sqlite3
import os
from datetime import datetime

DB_PATH = 'social_network.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        is_bot      INTEGER DEFAULT 0,
        is_admin    INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS follows (
        follower_id INTEGER,
        target_id   INTEGER,
        created_at  TEXT NOT NULL,
        PRIMARY KEY (follower_id, target_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        content     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        user_id     INTEGER,
        post_id     INTEGER,
        created_at  TEXT NOT NULL,
        PRIMARY KEY (user_id, post_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        post_id     INTEGER NOT NULL,
        content     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_bots (
        owner_id  INTEGER NOT NULL,
        bot_id    INTEGER NOT NULL,
        PRIMARY KEY (owner_id, bot_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS vk_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id     INTEGER NOT NULL,
        vk_user_id   INTEGER NOT NULL,
        full_name    TEXT,
        screen_name  TEXT,
        photo        TEXT,
        vk_url       TEXT,
        score        INTEGER,
        status       TEXT,
        label        TEXT,
        color        TEXT,
        stats        TEXT,
        reasons      TEXT,
        goods        TEXT,
        checked_at   TEXT NOT NULL
    )''')

    conn.commit()
    conn.close()

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def create_user(username, password, is_bot=0):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, password, created_at, is_bot) VALUES (?,?,?,?)',
            (username, password, now(), is_bot)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return users

def follow_user(follower_id, target_id):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO follows (follower_id, target_id, created_at) VALUES (?,?,?)',
            (follower_id, target_id, now())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def unfollow_user(follower_id, target_id):
    conn = get_db()
    conn.execute(
        'DELETE FROM follows WHERE follower_id=? AND target_id=?',
        (follower_id, target_id)
    )
    conn.commit()
    conn.close()

def is_following(follower_id, target_id):
    conn = get_db()
    r = conn.execute(
        'SELECT 1 FROM follows WHERE follower_id=? AND target_id=?',
        (follower_id, target_id)
    ).fetchone()
    conn.close()
    return r is not None

def get_follows():
    conn = get_db()
    rows = conn.execute('SELECT follower_id, target_id FROM follows').fetchall()
    conn.close()
    return rows

def create_post(user_id, content):
    conn = get_db()
    conn.execute(
        'INSERT INTO posts (user_id, content, created_at) VALUES (?,?,?)',
        (user_id, content, now())
    )
    conn.commit()
    conn.close()

def get_all_posts():
    conn = get_db()
    posts = conn.execute('''
        SELECT p.*, u.username
        FROM posts p JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    ''').fetchall()
    conn.close()
    return posts

def get_post(post_id):
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
    conn.close()
    return post

def like_post(user_id, post_id):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO likes (user_id, post_id, created_at) VALUES (?,?,?)',
            (user_id, post_id, now())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_likes_count(post_id):
    conn = get_db()
    r = conn.execute('SELECT COUNT(*) FROM likes WHERE post_id=?', (post_id,)).fetchone()
    conn.close()
    return r[0]

def add_comment(user_id, post_id, content):
    conn = get_db()
    conn.execute(
        'INSERT INTO comments (user_id, post_id, content, created_at) VALUES (?,?,?,?)',
        (user_id, post_id, content, now())
    )
    conn.commit()
    conn.close()

def get_comments(post_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*, u.username
        FROM comments c JOIN users u ON c.user_id = u.id
        WHERE c.post_id=?
        ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()
    conn.close()
    return rows

def get_activity_log():
    conn = get_db()
    rows = []
    for r in conn.execute('SELECT user_id, created_at, "post" as action FROM posts').fetchall():
        rows.append(dict(r))
    for r in conn.execute('SELECT user_id, created_at, "like" as action FROM likes').fetchall():
        rows.append(dict(r))
    for r in conn.execute('SELECT user_id, created_at, "comment" as action FROM comments').fetchall():
        rows.append(dict(r))
    conn.close()
    return rows

def link_bot_to_user(owner_id, bot_id):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO user_bots (owner_id, bot_id) VALUES (?,?)',
            (owner_id, bot_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_my_bots(owner_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT u.id, u.username, u.is_bot
        FROM users u
        JOIN user_bots ub ON u.id = ub.bot_id
        WHERE ub.owner_id = ?
    ''', (owner_id,)).fetchall()
    conn.close()
    return rows

def create_bots_for_owner(owner_id, count):
    """Создать count ботов и привязать к owner_id."""
    created = []
    # Уникальное имя чтобы не пересекалось с другими
    existing = db_get_all_usernames()
    for i in range(1, count + 1):
        name = f"bot_{owner_id}_{i}"
        # Если имя занято — добавляем суффикс
        candidate = name
        suffix = 1
        while candidate in existing:
            candidate = f"{name}_{suffix}"
            suffix += 1
        ok = create_user(candidate, 'botpass_auto', is_bot=1)
        if ok:
            user = get_user(candidate)
            if user:
                link_bot_to_user(owner_id, user['id'])
                created.append({'id': user['id'], 'username': candidate})
                existing.add(candidate)
    return created

def db_get_all_usernames():
    conn = get_db()
    rows = conn.execute('SELECT username FROM users').fetchall()
    conn.close()
    return set(r['username'] for r in rows)

def get_all_bots_with_owners():
    """Все боты с информацией о владельце."""
    conn = get_db()
    rows = conn.execute('''
        SELECT
            u.id        as bot_id,
            u.username  as bot_username,
            u.is_bot,
            ub.owner_id,
            o.username  as owner_username
        FROM users u
        LEFT JOIN user_bots ub ON u.id = ub.bot_id
        LEFT JOIN users o ON ub.owner_id = o.id
        WHERE u.is_bot = 1
        ORDER BY ub.owner_id, u.id
    ''').fetchall()
    conn.close()
    return rows

def set_admin(user_id, value=1):
    conn = get_db()
    conn.execute('UPDATE users SET is_admin=? WHERE id=?', (value, user_id))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = get_db()
    row = conn.execute(
        'SELECT is_admin FROM users WHERE id=?', (user_id,)
    ).fetchone()
    conn.close()
    return bool(row and row['is_admin'])

def get_all_users_stats():
    """Статистика по всем пользователям для админки."""
    conn = get_db()
    users = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    result = []
    for u in users:
        post_count = conn.execute(
            'SELECT COUNT(*) FROM posts WHERE user_id=?', (u['id'],)
        ).fetchone()[0]
        like_count = conn.execute(
            'SELECT COUNT(*) FROM likes WHERE user_id=?', (u['id'],)
        ).fetchone()[0]
        follower_count = conn.execute(
            'SELECT COUNT(*) FROM follows WHERE target_id=?', (u['id'],)
        ).fetchone()[0]
        following_count = conn.execute(
            'SELECT COUNT(*) FROM follows WHERE follower_id=?', (u['id'],)
        ).fetchone()[0]
        result.append({
            'id':             u['id'],
            'username':       u['username'],
            'is_bot':         u['is_bot'],
            'is_admin':       u['is_admin'],
            'created_at':     u['created_at'],
            'post_count':     post_count,
            'like_count':     like_count,
            'follower_count': follower_count,
            'following_count':following_count,
        })
    conn.close()
    return result

def seed_initial_users():
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    if count > 0:
        return

    import random

    legit_users = [
        ('alice_smith',    'pass123'),
        ('bob_johnson',    'pass123'),
        ('carol_white',    'pass123'),
        ('david_brown',    'pass123'),
        ('elena_green',    'pass123'),
        ('frank_miller',   'pass123'),
        ('grace_wilson',   'pass123'),
        ('henry_moore',    'pass123'),
        ('ivan_taylor',    'pass123'),
        ('julia_anderson', 'pass123'),
        ('kevin_thomas',   'pass123'),
        ('laura_jackson',  'pass123'),
        ('mike_harris',    'pass123'),
        ('nina_martin',    'pass123'),
        ('oscar_garcia',   'pass123'),
        ('paula_martinez', 'pass123'),
        ('quinn_robinson', 'pass123'),
        ('rosa_clark',     'pass123'),
        ('steve_rodriguez','pass123'),
        ('tina_lewis',     'pass123'),
        ('uma_lee',        'pass123'),
        ('victor_walker',  'pass123'),
        ('wendy_hall',     'pass123'),
        ('xena_allen',     'pass123'),
        ('yuri_young',     'pass123'),
    ]
    for username, password in legit_users:
        create_user(username, password, is_bot=0)

    static_bots = [
        ('spam_bot_001', 'botpass'),
        ('spam_bot_002', 'botpass'),
        ('spam_bot_003', 'botpass'),
        ('spam_bot_004', 'botpass'),
        ('spam_bot_005', 'botpass'),
        ('fake_acc_x1',  'botpass'),
        ('fake_acc_x2',  'botpass'),
        ('fake_acc_x3',  'botpass'),
        ('fake_acc_x4',  'botpass'),
        ('fake_acc_x5',  'botpass'),
        ('bot_alpha_01', 'botpass'),
        ('bot_alpha_02', 'botpass'),
        ('bot_alpha_03', 'botpass'),
        ('bot_beta_01',  'botpass'),
        ('bot_beta_02',  'botpass'),
        ('bot_beta_03',  'botpass'),
        ('bot_gamma_01', 'botpass'),
        ('bot_gamma_02', 'botpass'),
        ('bot_delta_01', 'botpass'),
        ('bot_delta_02', 'botpass'),
    ]
    for username, password in static_bots:
        create_user(username, password, is_bot=1)

    conn   = get_db()
    humans = conn.execute('SELECT id FROM users WHERE is_bot=0 AND is_admin=0').fetchall()
    bots_  = conn.execute('SELECT id FROM users WHERE is_bot=1').fetchall()
    conn.close()

    human_ids = [u['id'] for u in humans]
    bot_ids   = [u['id'] for u in bots_]

    for i, uid in enumerate(human_ids):
        # Каждый подписывается на 4–8 случайных людей
        others  = [x for x in human_ids if x != uid]
        targets = random.sample(others, min(random.randint(4, 8), len(others)))
        for tid in targets:
            follow_user(uid, tid)

    for bid in bot_ids:
        for uid in human_ids:
            follow_user(bid, uid)

    human_posts = [
        'Всем привет! Рад быть здесь.',
        'Интересный проект, слежу за развитием.',
        'Сегодня хорошая погода, настроение отличное!',
        'Кто знает хорошие книги по ML?',
        'Только что посмотрел отличный фильм.',
        'Работаю над новым проектом, есть интересные идеи.',
        'Как дела у всех? Надеюсь всё хорошо.',
        'Делюсь интересной статьёй которую прочитал.',
        'Сегодня продуктивный день!',
        'Рекомендую новый ресторан в городе.',
        'Занимаюсь спортом каждое утро — советую!',
        'Изучаю Python, очень интересный язык.',
        'Поздравляю всех с хорошим настроением!',
        'Нашёл отличный подкаст о технологиях.',
        'Планирую поездку на следующей неделе.',
    ]
    for i, uid in enumerate(human_ids):
        content = human_posts[i % len(human_posts)]
        create_post(uid, content)

    conn   = get_db()
    posts_ = conn.execute('SELECT id FROM posts').fetchall()
    conn.close()
    post_ids = [p['id'] for p in posts_]

    for uid in human_ids:
        liked = random.sample(post_ids, min(random.randint(3, 8), len(post_ids)))
        for pid in liked:
            like_post(uid, pid)

    for bid in bot_ids:
        for pid in post_ids:
            like_post(bid, pid)

    create_user('admin', 'admin123', is_bot=0)
    admin = get_user('admin')
    if admin:
        set_admin(admin['id'], 1)

    print("[DB] Создано начальных пользователей: "
          f"{len(legit_users)} людей + {len(static_bots)} ботов + 1 админ")

def save_vk_check(owner_id, result):
    import json
    conn = get_db()
    conn.execute('''
        INSERT INTO vk_history
        (owner_id, vk_user_id, full_name, screen_name, photo, vk_url,
         score, status, label, color, stats, reasons, goods, checked_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        owner_id,
        result.get('user_id'),
        result.get('full_name'),
        result.get('screen_name'),
        result.get('photo'),
        result.get('vk_url'),
        result.get('score'),
        result.get('status'),
        result.get('label'),
        result.get('color'),
        json.dumps(result.get('stats', {})),
        json.dumps(result.get('reasons', [])),
        json.dumps(result.get('goods',   [])),
        now(),
    ))
    conn.commit()
    conn.close()

def get_vk_history(owner_id, limit=50):
    import json
    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM vk_history
        WHERE owner_id = ?
        ORDER BY checked_at DESC
        LIMIT ?
    ''', (owner_id, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        item['stats']   = json.loads(item['stats']   or '{}')
        item['reasons'] = json.loads(item['reasons'] or '[]')
        item['goods']   = json.loads(item['goods']   or '[]')
        result.append(item)
    return result

def delete_vk_check(check_id, owner_id):
    conn = get_db()
    conn.execute(
        'DELETE FROM vk_history WHERE id=? AND owner_id=?',
        (check_id, owner_id)
    )
    conn.commit()
    conn.close()

def reset_all_activity():
    """Удаляет всю активность — лайки, посты, комментарии, подписки ботов."""
    conn = get_db()

    conn.execute('DELETE FROM likes')

    conn.execute('DELETE FROM comments')

    conn.execute('''
        DELETE FROM posts WHERE user_id IN (
            SELECT id FROM users WHERE is_bot = 1
        )
    ''')

    conn.execute('''
        DELETE FROM follows WHERE follower_id IN (
            SELECT id FROM users WHERE is_bot = 1
        )
    ''')

    conn.commit()
    conn.close()
    print("[DB] Активность сброшена")