import re
import math
import requests
from datetime import datetime

VK_API_VERSION = '5.199'
VK_API_BASE    = 'https://api.vk.com/method/'


def extract_screen_name(url: str) -> str:
    """Извлекает screen_name из любого формата ссылки VK."""
    url = url.strip().rstrip('/')

    # Убираем протокол
    url = re.sub(r'^https?://', '', url)

    patterns = [
        r'^(?:www\.)?vk\.com/([a-zA-Z0-9_.]+)',
        r'^(?:www\.)?vk\.ru/([a-zA-Z0-9_.]+)',
        r'^(?:www\.)?m\.vk\.com/([a-zA-Z0-9_.]+)',
    ]
    for p in patterns:
        m = re.match(p, url)
        if m:
            name = m.group(1)
            # Убираем query параметры если есть
            name = name.split('?')[0]
            return name

    if re.match(r'^[a-zA-Z0-9_.]+$', url):
        return url

    return url


def get_user_info(screen_name: str, token: str) -> dict:
    fields = ','.join([
        'followers_count', 'counters', 'sex', 'bdate',
        'city', 'country', 'photo_max', 'online',
        'site', 'status', 'last_seen', 'verified',
        'relation', 'is_closed', 'can_access_closed',
        'activities', 'interests', 'music', 'movies',
        'tv', 'books', 'games', 'about', 'quotes',
    ])
    resp = requests.get(VK_API_BASE + 'users.get', params={
        'user_ids':     screen_name,
        'fields':       fields,
        'access_token': token,
        'v':            VK_API_VERSION,
    }, timeout=10)
    data = resp.json()

    if 'error' in data or not data.get('response'):
        resp2 = requests.get(VK_API_BASE + 'groups.getById', params={
            'group_id':     screen_name,
            'fields':       'members_count,description,status,verified,is_closed',
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data2 = resp2.json()
        if 'response' in data2 and data2['response']:
            raise ValueError(
                f"«{screen_name}» — это группа/сообщество, а не личная страница. "
                f"Введи ссылку на профиль конкретного человека."
            )
        raise ValueError("Пользователь не найден. Проверь ссылку.")

    user = data['response'][0]

    if user.get('deactivated'):
        raise ValueError(
            f"Аккаунт «{screen_name}» заблокирован или удалён "
            f"(статус: {user.get('deactivated')})"
        )

    print("\n[VK DEBUG] Поля профиля:")
    for key, val in user.items():
        print(f"  {key}: {val}")

    return user


def get_wall_count(user_id: int, token: str) -> int:
    """Получает количество постов на стене."""
    try:
        resp = requests.get(VK_API_BASE + 'wall.get', params={
            'owner_id':    user_id,
            'count':       1,
            'access_token': token,
            'v':           VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        return data.get('response', {}).get('count', 0)
    except Exception:
        return 0


def get_photos_count(user_id: int, token: str) -> int:
    """Получает общее количество фото из всех доступных альбомов."""
    total = 0

    albums = [
        ('profile', 'Фото профиля'),
        ('wall',    'Фото на стене'),
        ('saved',   'Сохранённые'),
        ('-9',      'Общие фото'),
        ('-15',     'Фото со страниц'),
    ]

    for album_id, album_name in albums:
        try:
            resp = requests.get(VK_API_BASE + 'photos.get', params={
                'owner_id':     user_id,
                'album_id':     album_id,
                'count':        1,
                'access_token': token,
                'v':            VK_API_VERSION,
            }, timeout=10)
            data = resp.json()
            if 'response' in data:
                count = data['response'].get('count', 0)
                print(f"[VK DEBUG] photos '{album_name}' (id={album_id}): {count}")
                total += count
            elif 'error' in data:
                print(f"[VK DEBUG] photos '{album_name}' error: {data['error']['error_msg']}")
        except Exception as e:
            print(f"[VK DEBUG] photos '{album_name}' exception: {e}")

    try:
        resp = requests.get(VK_API_BASE + 'photos.getAlbums', params={
            'owner_id':     user_id,
            'need_system':  0,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'response' in data:
            for album in data['response'].get('items', []):
                size = album.get('size', 0)
                print(f"[VK DEBUG] user album '{album.get('title')}': {size}")
                total += size
    except Exception as e:
        print(f"[VK DEBUG] getAlbums exception: {e}")

    print(f"[VK DEBUG] Итого фотографий: {total}")
    return total
    

def get_friends_count(user_id: int, token: str) -> int:
    """Получает количество друзей отдельным запросом."""
    try:
        resp = requests.get(VK_API_BASE + 'friends.get', params={
            'user_id':      user_id,
            'count':        1,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'error' in data:
            return 0
        return data.get('response', {}).get('count', 0)
    except Exception:
        return 0

def get_groups_count(user_id: int, token: str) -> int:
    """Получает количество групп отдельным запросом."""
    try:
        resp = requests.get(VK_API_BASE + 'groups.get', params={
            'user_id':      user_id,
            'count':        1,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'error' in data:
            return 0
        return data.get('response', {}).get('count', 0)
    except Exception:
        return 0

def get_subscriptions_count(user_id: int, token: str) -> int:
    """Получает количество подписок отдельным запросом."""
    try:
        resp = requests.get(VK_API_BASE + 'users.getSubscriptions', params={
            'user_id':      user_id,
            'extended':     0,
            'count':        1,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'error' in data:
            return 0
        resp_data = data.get('response', {})
        users  = resp_data.get('users',  {}).get('count', 0)
        groups = resp_data.get('groups', {}).get('count', 0)
        return users + groups
    except Exception:
        return 0


def calculate_score(info: dict, wall_count: int, photos_count: int,
                    friends_count: int = 0, groups_count: int = 0,
                    subs_count: int = 0) -> dict:
    score   = 0
    reasons = []
    goods   = []

    counters  = info.get('counters', {}) or {}
    followers = info.get('followers_count') or counters.get('followers') or 0
    friends   = friends_count or counters.get('friends', 0)
    groups    = groups_count  or counters.get('groups', 0)
    following = subs_count    or counters.get('subscriptions', 0)
    photos    = photos_count  or counters.get('photos', 0)

    if info.get('verified'):
        score -= 20
        goods.append('✅ Верифицированный аккаунт VK')

    if info.get('is_closed') and not info.get('can_access_closed'):
        score += 10
        reasons.append('🔒 Закрытый профиль')

    photo_url = info.get('photo_max', '') or ''
    has_real_photo = (
        'userapi.com' in photo_url or
        'vk.com' in photo_url or
        'vk.me' in photo_url
    )
    if not has_real_photo:
        score += 20
        reasons.append('📷 Нет аватара (стандартная заглушка)')
    else:
        goods.append('📷 Есть аватар')

    if photos == 0:
        score += 5
        reasons.append('🖼 Фотографии недоступны или отсутствуют')
    elif photos < 5:
        score += 7
        reasons.append(f'🖼 Мало фотографий ({photos})')
    else:
        goods.append(f'🖼 Достаточно фотографий ({photos})')

    filled = 0
    if info.get('status'):   filled += 1
    if info.get('about'):    filled += 1
    if info.get('interests'):filled += 1
    if info.get('activities'):filled += 1
    if info.get('bdate'):    filled += 1
    if info.get('city'):     filled += 1
    if info.get('relation'): filled += 1

    if filled <= 1:
        score += 15
        reasons.append(f'📝 Профиль почти пустой ({filled}/7 полей)')
    elif filled <= 3:
        score += 7
        reasons.append(f'📝 Профиль заполнен слабо ({filled}/7 полей)')
    else:
        goods.append(f'📝 Профиль хорошо заполнен ({filled}/7 полей)')

    if info.get('status'):
        goods.append(f'💬 Есть статус')

    if wall_count == 0:
        score += 15
        reasons.append('📰 Нет постов на стене')
    elif wall_count < 5:
        score += 7
        reasons.append(f'📰 Мало постов ({wall_count})')
    else:
        goods.append(f'📰 Есть посты ({wall_count})')

    if friends == 0:
        score += 15
        reasons.append('👥 Нет друзей или недоступно')
    elif friends < 10:
        score += 8
        reasons.append(f'👥 Очень мало друзей ({friends})')
    elif friends < 50:
        score += 3
        reasons.append(f'👥 Мало друзей ({friends})')
    else:
        goods.append(f'👥 Много друзей ({friends})')

    if following > 0 and friends >= 0:
        ratio = following / (friends + 1)
        if ratio > 20:
            score += 20
            reasons.append(f'📊 Аномально много подписок (×{ratio:.0f} vs друзей)')
        elif ratio > 5:
            score += 10
            reasons.append(f'📊 Много подписок относительно друзей (×{ratio:.1f})')

    if groups == 0:
        score += 5
        reasons.append('👥 Не состоит ни в одной группе')
    else:
        goods.append(f'👥 Состоит в {groups} группах')

    if info.get('bdate'):
        goods.append('🎂 Указана дата рождения')
    else:
        score += 5
        reasons.append('🎂 Не указана дата рождения')

    if info.get('relation') and info.get('relation') != 0:
        goods.append('💑 Указан семейный статус')

    if followers > 500:
        goods.append(f'👁 Много подписчиков ({followers})')
    elif followers > 50:
        goods.append(f'👁 Есть подписчики ({followers})')

    score = max(0, min(100, score))

    if score >= 60:
        status = 'fake'
        label  = '🚨 Подозрительный аккаунт'
        color  = '#ff4444'
    elif score >= 35:
        status = 'suspicious'
        label  = '⚠️ Требует проверки'
        color  = '#ff9900'
    else:
        status = 'legit'
        label  = '✅ Вероятно легитимный'
        color  = '#44bb44'

    return {
        'score':    score,
        'status':   status,
        'label':    label,
        'color':    color,
        'reasons':  reasons,
        'goods':    goods,
        'stats': {
            'friends':   friends,
            'followers': followers,
            'following': following,
            'groups':    groups,
            'photos':    photos,
            'posts':     wall_count,
            'verified':  bool(info.get('verified')),
            'is_closed': bool(info.get('is_closed')),
        }
    }

def analyze_profile(url: str, token: str) -> dict:
    import time as time_module

    screen_name = extract_screen_name(url)
    if not screen_name:
        raise ValueError("Не удалось извлечь имя пользователя из ссылки")

    info      = get_user_info(screen_name, token)
    user_id   = info['id']
    full_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
    photo     = info.get('photo_max', '')
    is_closed = info.get('is_closed', False)
    verified  = info.get('verified', False)

    time_module.sleep(0.34)
    wall_count    = get_wall_count(user_id, token)
    time_module.sleep(0.34)
    friends_count = get_friends_count(user_id, token)
    time_module.sleep(0.34)
    groups_count  = get_groups_count(user_id, token)
    time_module.sleep(0.34)
    subs_count    = get_subscriptions_count(user_id, token)

    photos_profile = 0
    photos_wall    = 0
    photos_tagged  = 0

    print(f"[VK DEBUG] Начинаем считать фото для user_id={user_id}")

    for album_id in ['profile', 'wall']:
        try:
            time_module.sleep(0.34)
            resp = requests.get(VK_API_BASE + 'photos.get', params={
                'owner_id':     user_id,
                'album_id':     album_id,
                'count':        1,
                'access_token': token,
                'v':            VK_API_VERSION,
            }, timeout=10)
            data = resp.json()
            c = data.get('response', {}).get('count', 0) if 'response' in data else 0
            print(f"[VK DEBUG] album '{album_id}': {c}")
            if album_id == 'profile':
                photos_profile = c
            elif album_id == 'wall':
                photos_wall = c
        except Exception as e:
            print(f"[VK DEBUG] album '{album_id}' exception: {e}")

    try:
        time_module.sleep(0.5)
        resp = requests.get(VK_API_BASE + 'photos.get', params={
            'owner_id':     user_id,
            'album_id':     'tagged',
            'count':        1,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'response' in data:
            photos_tagged = data['response'].get('count', 0)
            print(f"[VK DEBUG] album 'tagged': {photos_tagged}")
        elif 'error' in data:
            print(f"[VK DEBUG] album 'tagged' error: {data['error']['error_msg']}")
            # Пробуем getAll как запасной вариант
            time_module.sleep(0.5)
            resp2 = requests.get(VK_API_BASE + 'photos.getAll', params={
                'owner_id':          user_id,
                'count':             1,
                'no_service_albums': 0,
                'access_token':      token,
                'v':                 VK_API_VERSION,
            }, timeout=10)
            data2 = resp2.json()
            print(f"[VK DEBUG] getAll: count={data2.get('response', {}).get('count')} err={data2.get('error', {}).get('error_msg')}")
            if 'response' in data2:
                all_count     = data2['response'].get('count', 0)
                photos_tagged = max(0, all_count - photos_profile - photos_wall)
                print(f"[VK DEBUG] tagged через getAll: {photos_tagged}")
    except Exception as e:
        print(f"[VK DEBUG] tagged exception: {e}")

    try:
        time_module.sleep(0.34)
        resp = requests.get(VK_API_BASE + 'photos.getAlbums', params={
            'owner_id':     user_id,
            'need_system':  0,
            'access_token': token,
            'v':            VK_API_VERSION,
        }, timeout=10)
        data = resp.json()
        if 'response' in data:
            for album in data['response'].get('items', []):
                size = album.get('size', 0)
                if size > 0:
                    print(f"[VK DEBUG] user album '{album.get('title')}': {size}")
                    photos_tagged += size
    except Exception as e:
        print(f"[VK DEBUG] getAlbums exception: {e}")

    photos_count = photos_profile + photos_wall + photos_tagged
    print(f"[VK DEBUG] ИТОГО: profile={photos_profile} wall={photos_wall} tagged={photos_tagged} total={photos_count}")

    result = calculate_score(
        info, wall_count, photos_count,
        friends_count, groups_count, subs_count
    )

    result['photos_detail'] = {
        'profile': photos_profile,
        'wall':    photos_wall,
        'tagged':  photos_tagged,
        'total':   photos_count,
    }

    return {
        'user_id':     user_id,
        'full_name':   full_name,
        'screen_name': info.get('screen_name', str(user_id)),
        'photo':       photo,
        'vk_url':      f"https://vk.com/{info.get('screen_name', 'id' + str(user_id))}",
        'verified':    verified,
        'is_closed':   is_closed,
        **result,
    }