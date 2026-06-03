import time
import random
import threading
import database as db

BOT_POSTS = [
    'Купи подписку! Скидка 99%!',
    'Лучший заработок в интернете!',
    'Переходи по ссылке!',
    'Успей купить до конца дня!',
    'Розыгрыш призов! Подпишись!',
    'Зарабатывай не выходя из дома!',
]

_simulations = {}


def _key_user(user_id): return f"user_{user_id}"
def _key_bot(bot_id):   return f"bot_{bot_id}"



def is_running(owner_id):
    return _simulations.get(_key_user(owner_id), {}).get('active', False)

def is_bot_running(bot_id):
    return _simulations.get(_key_bot(bot_id), {}).get('active', False)

def is_anomaly_running(bot_id):
    key = f"anomaly_{bot_id}"
    return _simulations.get(key, {}).get('active', False)

def get_all_active():
    return {k: v for k, v in _simulations.items() if v.get('active')}



def start_human_simulation(user_id):
    key = _key_user(user_id)
    if _simulations.get(key, {}).get('active'):
        return False
    _simulations[key] = {'active': True}
    t = threading.Thread(target=_human_bot_loop, args=(user_id, key), daemon=True)
    _simulations[key]['thread'] = t
    t.start()
    return True

def stop_simulation(user_id):
    key = _key_user(user_id)
    if key in _simulations:
        _simulations[key]['active'] = False
    return True

def start_simulation(owner_id):
    return start_human_simulation(owner_id)

def _human_bot_loop(user_id, key):
    while _simulations.get(key, {}).get('active'):
        all_posts = db.get_all_posts()
        all_users = db.get_all_users()

        others  = [u for u in all_users if u['id'] != user_id]
        count   = max(1, int(len(others) * random.uniform(0.2, 0.6)))
        targets = random.sample(others, min(count, len(others)))
        for u in targets:
            db.follow_user(user_id, u['id'])

        if all_posts:
            count = max(1, int(len(all_posts) * random.uniform(0.3, 0.7)))
            liked = random.sample(all_posts, min(count, len(all_posts)))
            for post in liked:
                db.like_post(user_id, post['id'])
                time.sleep(random.uniform(0.3, 1.2))

        db.create_post(user_id, random.choice(BOT_POSTS))
        time.sleep(random.uniform(4, 10))



def start_single_bot(bot_id):
    key = _key_bot(bot_id)
    if _simulations.get(key, {}).get('active'):
        return False
    _simulations[key] = {'active': True}
    t = threading.Thread(target=_single_bot_loop, args=(bot_id, key), daemon=True)
    _simulations[key]['thread'] = t
    t.start()
    return True

def stop_single_bot(bot_id):
    key = _key_bot(bot_id)
    if key in _simulations:
        _simulations[key]['active'] = False
        print(f"[BOT] Остановлен бот {bot_id}, ключ={key}")
    else:
        print(f"[BOT] Бот {bot_id} не найден. Активные: {list(_simulations.keys())}")
    return True

def _single_bot_loop(bot_id, key):
    while _simulations.get(key, {}).get('active'):
        all_posts = db.get_all_posts()
        all_users = db.get_all_users()

        others  = [u for u in all_users if u['id'] != bot_id]
        count   = max(1, int(len(others) * random.uniform(0.1, 0.5)))
        targets = random.sample(others, min(count, len(others)))
        for u in targets:
            db.follow_user(bot_id, u['id'])

        if all_posts:
            count = max(1, int(len(all_posts) * random.uniform(0.2, 0.6)))
            liked = random.sample(all_posts, min(count, len(all_posts)))
            for post in liked:
                db.like_post(bot_id, post['id'])
                time.sleep(random.uniform(0.2, 0.8))

        db.create_post(bot_id, random.choice(BOT_POSTS))
        time.sleep(random.uniform(3, 8))


# ─── Создание ботов

def create_bots_for_user(owner_id, count=5):
    created  = []
    existing = db.db_get_all_usernames()
    for i in range(1, count + 1):
        name      = f"bot_{owner_id}_{i}"
        candidate = name
        suffix    = 1
        while candidate in existing:
            candidate = f"{name}_{suffix}"
            suffix   += 1
        ok = db.create_user(candidate, 'botpass_auto', is_bot=1)
        if ok:
            user = db.get_user(candidate)
            if user:
                db.link_bot_to_user(owner_id, user['id'])
                created.append({'id': user['id'], 'username': candidate})
                existing.add(candidate)
    return created


# ─── Аномальный режим 

def start_anomaly_mode(bot_id):
    print(f"[ANOMALY] start called, _simulations before: {list(_simulations.keys())}")
    key = f"anomaly_{bot_id}"
    if _simulations.get(key, {}).get('active'):
        return False
    _simulations[key] = {'active': True}
    t = threading.Thread(target=_anomaly_loop, args=(bot_id, key), daemon=True)
    _simulations[key]['thread'] = t
    t.start()
    return True

def stop_anomaly_mode(bot_id):
    key = f"anomaly_{bot_id}"
    if key in _simulations:
        _simulations[key]['active'] = False
    return True

def _anomaly_loop(bot_id, key):
    """
    Аномальный режим с ночными метками времени.
    Гарантированно создаёт:
    - night_activity_ratio > 0.95  (все действия в 2–4 ночи)
    - burst_score > 0.9            (все лайки в одну минуту)
    - ff_ratio >> 50               (подписка на всех)
    - action_entropy → 0           (только лайки)
    - avg_actions_per_hour > 500
    """
    from datetime import datetime, timedelta

    iteration = 0

    while _simulations.get(key, {}).get('active'):
        all_posts = db.get_all_posts()
        all_users = db.get_all_users()

        now        = datetime.now()
        night_base = now.replace(
            hour   = random.randint(2, 4),
            minute = random.randint(0, 30),
            second = 0,
            microsecond=0
        )

        conn = db.get_db()
        tick = night_base
        for post in all_posts:
            if not _simulations.get(key, {}).get('active'):
                break
            try:
                conn.execute(
                    'INSERT OR IGNORE INTO likes (user_id, post_id, created_at) VALUES (?,?,?)',
                    (bot_id, post['id'], tick.strftime('%Y-%m-%d %H:%M:%S'))
                )
            except Exception:
                pass
            tick += timedelta(seconds=random.uniform(0.5, 2.5))

        for _ in range(3):
            spam = random.choice([
                'КУПИ СЕЙЧАС! АКЦИЯ! СКИДКА 99%!',
                'Заработок от 100000 в день! Пиши в ЛС!',
                'БЕСПЛАТНО! ЖМИТЕ! УСПЕЙТЕ!',
                'ВЫ ВЫИГРАЛИ! ПЕРЕЙДИТЕ ПО ССЫЛКЕ!',
            ])
            night_post = night_base + timedelta(seconds=random.randint(60, 300))
            conn.execute(
                'INSERT INTO posts (user_id, content, created_at) VALUES (?,?,?)',
                (bot_id, spam, night_post.strftime('%Y-%m-%d %H:%M:%S'))
            )

        conn.commit()
        conn.close()

        for u in all_users:
            if u['id'] != bot_id:
                db.follow_user(bot_id, u['id'])

        iteration += 1
        print(f"[ANOMALY] bot_{bot_id} итерация {iteration}: "
              f"лайков={len(all_posts)}, подписок={len(all_users)-1}, "
              f"ночное время={night_base.strftime('%H:%M')}")

        time.sleep(random.uniform(1.0, 2.5))



def start_all_anomaly():
    users   = db.get_all_users()
    started = []
    for u in users:
        if u['is_bot']:
            start_anomaly_mode(u['id'])
            started.append(u['username'])
    return started

def stop_all_anomaly():
    keys = [k for k in list(_simulations.keys()) if k.startswith('anomaly_')]
    for key in keys:
        _simulations[key]['active'] = False

def start_random_anomaly(count=2):
    """
    Запускает аномальный режим для N случайных участников.
    50% шанс что выберет человека вместо бота.
    """
    all_bots   = [u for u in db.get_all_users()
                  if u['is_bot'] == 1]
    all_humans = [u for u in db.get_all_users()
                  if u['is_bot'] == 0 and not u['is_admin']]

    if not all_bots and not all_humans:
        return []

    human_sample = random.sample(
        all_humans,
        min(max(1, len(all_humans) // 3), len(all_humans))
    )
    pool     = all_bots + human_sample
    selected = random.sample(pool, min(count, len(pool)))

    started = []
    for acc in selected:
        start_anomaly_mode(acc['id'])
        started.append({
            'id':       acc['id'],
            'username': acc['username'],
            'is_bot':   acc['is_bot'],
        })
    return started

def stop_random_anomaly():
    """Останавливает все аномальные симуляции."""
    keys = [k for k in list(_simulations.keys()) if k.startswith('anomaly_')]
    for key in keys:
        _simulations[key]['active'] = False
    return len(keys)