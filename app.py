from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import random
import os
import hashlib
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
import traceback
import re
import string
import time
from functools import wraps

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__)
app.secret_key = 'zetta_super_secret_key_2026_xyz_12345_abcde'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB
app.config['VIDEO_FOLDER'] = 'static/videos'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mov'}
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Создание директорий
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('backups', exist_ok=True)
os.makedirs('data', exist_ok=True)

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
file_handler = RotatingFileHandler('logs/zetta.log', maxBytes=10485760, backupCount=20)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.DEBUG)

error_handler = RotatingFileHandler('logs/zetta_error.log', maxBytes=10485760, backupCount=10)
error_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
error_handler.setLevel(logging.ERROR)

app.logger.addHandler(file_handler)
app.logger.addHandler(error_handler)
app.logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
app.logger.addHandler(console_handler)

app.logger.info('=' * 60)
app.logger.info('ZETTA ПРИЛОЖЕНИЕ ЗАПУЩЕНО')
app.logger.info(f'Время запуска: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}')
app.logger.info('=' * 60)


def log_error(error_msg, e=None, context=None):
    app.logger.error(f'ОШИБКА: {error_msg}')
    if e:
        app.logger.error(f'Исключение: {str(e)}')
        app.logger.error(traceback.format_exc())
    if context:
        app.logger.error(f'Контекст: {context}')
    # Запись в отдельный файл ошибок
    with open('logs/errors_detailed.log', 'a', encoding='utf-8') as f:
        f.write(f'[{datetime.now().isoformat()}] {error_msg}\n')
        if e:
            f.write(f'Exception: {str(e)}\n')
            f.write(f'Traceback: {traceback.format_exc()}\n')
        f.write('-' * 50 + '\n')


def log_info(message, data=None):
    app.logger.info(message)
    if data:
        app.logger.info(f'Данные: {json.dumps(data, ensure_ascii=False, default=str)[:500]}')


# ==================== КОНСТАНТЫ И НАСТРОЙКИ ====================
# Файлы данных
DATA_FILES = {
    'reviews': 'data/reviews.json',
    'users': 'data/users.json',
    'orders': 'data/orders.json',
    'verification': 'data/verification_codes.json',
    'password_reset': 'data/password_reset.json',
    'used_promocodes': 'data/used_promocodes.json',
    'products': 'data/products.json',
    'news': 'data/news.json',
    'promocodes': 'data/promocodes_list.json',
    'banned_users': 'data/banned_users.json',
    'chat_messages': 'data/chat_messages.json',
    'vlog': 'data/vlog.json',
    'faq': 'data/faq.json',
    'partners': 'data/partners.json',
    'statistics': 'data/statistics.json',
    'mailing_list': 'data/mailing_list.json',
    'support_tickets': 'data/support_tickets.json',
    'api_keys': 'data/api_keys.json',
    'analytics': 'data/analytics.json',
    'backup_log': 'data/backup_log.json'
}

# Создание всех файлов данных если не существуют
for file_path in DATA_FILES.values():
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            if 'users' in file_path:
                json.dump({}, f, ensure_ascii=False, indent=2)
            elif 'orders' in file_path:
                json.dump({}, f, ensure_ascii=False, indent=2)
            elif 'products' in file_path:
                json.dump([], f, ensure_ascii=False, indent=2)
            else:
                json.dump({}, f, ensure_ascii=False, indent=2)


# ==================== ФУНКЦИИ ЗАГРУЗКИ/СОХРАНЕНИЯ ДАННЫХ ====================
def load_data(filename, default=None):
    """Универсальная функция загрузки данных"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except json.JSONDecodeError as e:
        log_error(f"Ошибка парсинга JSON в {filename}", e)
        return default if default is not None else {}
    except Exception as e:
        log_error(f"Ошибка загрузки {filename}", e)
        return default if default is not None else {}


def save_data(filename, data):
    """Универсальная функция сохранения данных"""
    try:
        # Создание резервной копии перед сохранением
        if os.path.exists(filename):
            backup_name = f"{filename}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            import shutil
            shutil.copy(filename, os.path.join('backups', os.path.basename(backup_name)))

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        log_error(f"Ошибка сохранения {filename}", e)
        return False


# Специфичные функции для обратной совместимости
def load_reviews():
    data = load_data(DATA_FILES['reviews'], [])
    return data if isinstance(data, list) else []


def save_reviews(reviews):
    return save_data(DATA_FILES['reviews'], reviews)


def load_users():
    return load_data(DATA_FILES['users'], {})


def save_users(users):
    return save_data(DATA_FILES['users'], users)


def load_orders():
    return load_data(DATA_FILES['orders'], {})


def save_orders(orders):
    return save_data(DATA_FILES['orders'], orders)


def load_verification_codes():
    return load_data(DATA_FILES['verification'], {})


def save_verification_codes(codes):
    return save_data(DATA_FILES['verification'], codes)


def load_password_reset_codes():
    return load_data(DATA_FILES['password_reset'], {})


def save_password_reset_codes(codes):
    return save_data(DATA_FILES['password_reset'], codes)


def load_used_promocodes():
    return load_data(DATA_FILES['used_promocodes'], {})


def save_used_promocodes(used):
    return save_data(DATA_FILES['used_promocodes'], used)


def load_products():
    products = load_data(DATA_FILES['products'], [])
    if not products:
        # Создание дефолтных товаров
        products = [
            {'id': 1, 'name': '💻 Сборка ПК "Игровой Флагман"', 'price': 89990, 'sale_price': 79990,
             'discount_percent': 11,
             'description': 'Сборка игрового компьютера с установкой Windows и драйверов. Intel i7, RTX 4060, 32GB RAM, 1TB SSD.',
             'image': '/static/uploads/gaming_pc.jpg', 'category': 'pc_build', 'in_stock': True, 'rating': 4.9,
             'sales_count': 156},
            {'id': 2, 'name': '🔧 Услуга: Настройка ПК + Антивирус', 'price': 2990, 'sale_price': 1990,
             'discount_percent': 33,
             'description': 'Профессиональная настройка операционной системы, установка антивируса, оптимизация реестра, удаление мусора.',
             'image': '/static/uploads/pc_setup.jpg', 'category': 'services', 'in_stock': True, 'rating': 4.8,
             'sales_count': 342},
            {'id': 3, 'name': '🌐 Сайт-визитка под ключ', 'price': 14990, 'sale_price': 9990, 'discount_percent': 33,
             'description': 'Создание современного сайта-визитки с адаптивным дизайном, формой обратной связи и базовой SEO-оптимизацией.',
             'image': '/static/uploads/website.jpg', 'category': 'websites', 'in_stock': True, 'rating': 4.9,
             'sales_count': 89},
            {'id': 4, 'name': '🎮 Компьютер "Стандарт" собранный', 'price': 59990, 'sale_price': None,
             'discount_percent': 0,
             'description': 'Готовый системный блок для офиса и дома. Intel i5, 16GB RAM, 512GB SSD, Windows 11 установлена.',
             'image': '/static/uploads/standard_pc.jpg', 'category': 'computers', 'in_stock': True, 'rating': 4.7,
             'sales_count': 234},
            {'id': 5, 'name': '🛠️ Процессор Intel Core i7-13700K', 'price': 39990, 'sale_price': 34990,
             'discount_percent': 12,
             'description': 'Новый процессор в оригинальной упаковке. Установка и настройка в подарок при покупке сборки ПК.',
             'image': '/static/uploads/cpu.jpg', 'category': 'components', 'in_stock': True, 'rating': 4.9,
             'sales_count': 67},
            {'id': 6, 'name': '🛠️ Видеокарта RTX 4070 Ti', 'price': 79990, 'sale_price': None, 'discount_percent': 0,
             'description': 'Мощная видеокарта для игр и работы. Гарантия 3 года. Установка при покупке сборки - бесплатно.',
             'image': '/static/uploads/gpu.jpg', 'category': 'components', 'in_stock': True, 'rating': 4.9,
             'sales_count': 45},
            {'id': 7, 'name': '🔧 Обслуживание ПК на месяц', 'price': 4990, 'sale_price': 3990, 'discount_percent': 20,
             'description': 'Абонемент на обслуживание компьютера: удалённая помощь, диагностика, настройка ПО, установка обновлений.',
             'image': '/static/uploads/service.jpg', 'category': 'services', 'in_stock': True, 'rating': 4.8,
             'sales_count': 178},
            {'id': 8, 'name': '🌐 Интернет-магазин под ключ', 'price': 49990, 'sale_price': 39990,
             'discount_percent': 20,
             'description': 'Полноценный интернет-магазин с корзиной, личным кабинетом, интеграцией с платежными системами.',
             'image': '/static/uploads/ecommerce.jpg', 'category': 'websites', 'in_stock': True, 'rating': 4.9,
             'sales_count': 34},
            {'id': 9, 'name': '💻 Сборка ПК "Офисный"', 'price': 34990, 'sale_price': 29990, 'discount_percent': 14,
             'description': 'Бюджетная сборка для офисных задач. Intel i3, 8GB RAM, 256GB SSD, Windows 11.',
             'image': '/static/uploads/office_pc.jpg', 'category': 'computers', 'in_stock': True, 'rating': 4.6,
             'sales_count': 89},
            {'id': 10, 'name': '🔧 Установка ПО и драйверов', 'price': 1490, 'sale_price': 990, 'discount_percent': 34,
             'description': 'Установка Windows, драйверов, офисного пакета, антивируса. Настройка под ключ.',
             'image': '/static/uploads/software.jpg', 'category': 'services', 'in_stock': True, 'rating': 4.9,
             'sales_count': 567},
        ]
        save_products(products)
    return products


def save_products(products):
    return save_data(DATA_FILES['products'], products)


def load_news():
    news = load_data(DATA_FILES['news'], [])
    if not news:
        news = [
            {'id': 1, 'date': '01.06.2026', 'title': '🔥 Zetta запускает летнюю распродажу 🔥',
             'text': 'Скидки до 50% на сборку ПК и создание сайтов!',
             'fullText': 'Компания Zetta объявляет о грандиозной летней распродаже! Скидки достигают 50% на сборку игровых компьютеров, создание сайтов и IT-обслуживание. Торопитесь, предложение ограничено!',
             'image': '/static/uploads/sale.jpg', 'video': None, 'video_type': None, 'views': 1250},
            {'id': 2, 'date': '28.05.2026', 'title': 'Новая услуга - Корпоративное обслуживание',
             'text': 'Абонентское обслуживание компьютеров для бизнеса',
             'fullText': 'Zetta запускает услугу корпоративного обслуживания! Полный цикл IT-поддержки для компаний: обслуживание ПК, серверов, настройка сети и техническая поддержка сотрудников.',
             'image': '/static/uploads/business.jpg', 'video': None, 'video_type': None, 'views': 890},
            {'id': 3, 'date': '25.05.2026', 'title': 'Zetta открыла новый офис',
             'text': 'Теперь мы находимся по адресу: г. Барнаул, ул. Юрина, 182',
             'fullText': 'Мы рады сообщить об открытии нового современного офиса! Теперь у нас есть просторный зал для приёма клиентов, демонстрационный зал с готовыми ПК и комфортная зона ожидания.',
             'image': '/static/uploads/office.jpg', 'video': '/static/videos/office_tour.mp4', 'video_type': 'file',
             'views': 2340}
        ]
        save_news(news)
    return news


def save_news(news):
    return save_data(DATA_FILES['news'], news)


def load_promocodes_list():
    promocodes = load_data(DATA_FILES['promocodes'], {})
    if not promocodes:
        promocodes = {
            'ZETTA10': {'discount': 10, 'type': 'percent', 'active': True, 'used_count': 0, 'max_uses': 100,
                        'conditions': {'apply_to': 'all', 'categories': [], 'products': [], 'min_order': 0}},
            'ZETTA20': {'discount': 20, 'type': 'percent', 'active': True, 'used_count': 0, 'max_uses': 50,
                        'conditions': {'apply_to': 'all', 'categories': [], 'products': [], 'min_order': 5000}},
            'ZETTA1000': {'discount': 1000, 'type': 'fixed', 'active': True, 'used_count': 0, 'max_uses': 30,
                          'conditions': {'apply_to': 'all', 'categories': [], 'products': [], 'min_order': 5000}},
            'ZETTA15': {'discount': 15, 'type': 'percent', 'active': True, 'used_count': 0, 'max_uses': 100,
                        'conditions': {'apply_to': 'categories', 'categories': ['services'], 'products': [],
                                       'min_order': 0}},
            'PCBUILD25': {'discount': 25, 'type': 'percent', 'active': True, 'used_count': 0, 'max_uses': 50,
                          'conditions': {'apply_to': 'categories', 'categories': ['pc_build'], 'products': [],
                                         'min_order': 30000}},
        }
        save_promocodes_list(promocodes)
    return promocodes


def save_promocodes_list(promocodes):
    return save_data(DATA_FILES['promocodes'], promocodes)


def load_banned_users():
    return load_data(DATA_FILES['banned_users'], {})


def save_banned_users(banned):
    return save_data(DATA_FILES['banned_users'], banned)


def load_vlog():
    vlog = load_data(DATA_FILES['vlog'], {})
    if not vlog:
        vlog = {
            'text': 'Добро пожаловать в блог компании Zetta! Здесь мы будем делиться новостями о нашей работе, рассказывать о сотрудниках и анонсировать новые услуги.\n\n---\n\n✨ Если у вас есть предложения по улучшению или жалобы, нажимайте на кнопку "Предложения" внизу страницы!',
            'last_updated': datetime.now().isoformat()}
        save_vlog(vlog)
    return vlog


def save_vlog(vlog):
    return save_data(DATA_FILES['vlog'], vlog)


def load_chat_messages():
    return load_data(DATA_FILES['chat_messages'], {})


def save_chat_messages(messages):
    return save_data(DATA_FILES['chat_messages'], messages)


def load_faq():
    faq = load_data(DATA_FILES['faq'], [])
    if not faq:
        faq = [
            {'id': 1, 'question': 'Как заказать сборку ПК?',
             'answer': 'Выберите категорию "Сборка компьютера" в каталоге или свяжитесь с нашим менеджером для индивидуального подбора конфигурации.',
             'category': 'ordering'},
            {'id': 2, 'question': 'Какие способы оплаты доступны?',
             'answer': 'Вы можете оплатить заказ банковской картой онлайн или наличными при получении. При онлайн-оплате реквизиты для перевода будут отправлены на вашу почту после оформления заказа.',
             'category': 'payment'},
            {'id': 3, 'question': 'Сколько стоит доставка?',
             'answer': 'Доставка осуществляется бесплатно! Срок доставки зависит от расстояния: до 50 км - 3 дня, до 100 км - 7 дней, более 100 км - 14 дней.',
             'category': 'delivery'},
            {'id': 4, 'question': 'Как использовать промокод?',
             'answer': 'Введите промокод в поле "Промокод" в корзине и нажмите "Применить". Скидка будет автоматически применена к вашему заказу.',
             'category': 'promo'},
            {'id': 5, 'question': 'Как связаться со службой поддержки?',
             'answer': 'Вы можете связаться с нами по телефону +7 (952) 006-23-57 или +7 (913) 244-77-07, или отправить письмо на vaincode@mail.ru.',
             'category': 'support'},
            {'id': 6, 'question': 'Есть ли гарантия на сборку ПК?',
             'answer': 'Да, на все сборки ПК предоставляется гарантия 3 года. На комплектующие действует гарантия производителя.',
             'category': 'warranty'},
        ]
        save_faq(faq)
    return faq


def save_faq(faq):
    return save_data(DATA_FILES['faq'], faq)


def load_partners():
    return load_data(DATA_FILES['partners'], [])


def save_partners(partners):
    return save_data(DATA_FILES['partners'], partners)


def load_statistics():
    return load_data(DATA_FILES['statistics'],
                     {'total_orders': 0, 'total_revenue': 0, 'total_users': 0, 'daily_stats': {}})


def save_statistics(stats):
    return save_data(DATA_FILES['statistics'], stats)


def update_statistics(order_data):
    stats = load_statistics()
    stats['total_orders'] += 1
    stats['total_revenue'] += order_data['total']

    today = datetime.now().strftime('%Y-%m-%d')
    if today not in stats['daily_stats']:
        stats['daily_stats'][today] = {'orders': 0, 'revenue': 0}
    stats['daily_stats'][today]['orders'] += 1
    stats['daily_stats'][today]['revenue'] += order_data['total']

    save_statistics(stats)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def hash_password(password):
    salt = "zetta_salt_2026"
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))


def generate_order_number():
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"


def is_promocode_used(email, promo_code):
    used = load_used_promocodes()
    key = f"{email}_{promo_code}"
    return key in used


def mark_promocode_used(email, promo_code, order_number):
    used = load_used_promocodes()
    key = f"{email}_{promo_code}"
    used[key] = {
        'email': email,
        'promo_code': promo_code,
        'order_number': order_number,
        'used_at': datetime.now().isoformat()
    }
    save_used_promocodes(used)

    # Обновление счётчика использования промокода
    promocodes = load_promocodes_list()
    if promo_code in promocodes:
        promocodes[promo_code]['used_count'] = promocodes[promo_code].get('used_count', 0) + 1
        save_promocodes_list(promocodes)


def check_promo_applies(promo_code, cart_items, subtotal):
    promocodes = load_promocodes_list()
    if promo_code not in promocodes:
        return False, "Промокод не найден"

    promo = promocodes[promo_code]
    if not promo.get('active', True):
        return False, "Промокод неактивен"

    # Проверка максимального количества использований
    max_uses = promo.get('max_uses', float('inf'))
    if promo.get('used_count', 0) >= max_uses:
        return False, "Промокод достиг лимита использований"

    # Проверка минимальной суммы заказа
    min_order = promo.get('conditions', {}).get('min_order', 0)
    if subtotal < min_order:
        return False, f"Минимальная сумма заказа для этого промокода: {min_order} ₽"

    conditions = promo.get('conditions', {})
    apply_to = conditions.get('apply_to', 'all')

    if apply_to == 'all':
        return True, None

    categories_allowed = conditions.get('categories', [])
    products_allowed = conditions.get('products', [])

    for item in cart_items:
        product_id = item.get('id')
        category = item.get('category', '')

        if apply_to == 'specific_products':
            if product_id not in products_allowed:
                return False, f"Промокод не применяется к товару '{item.get('name')}'"
        elif apply_to == 'categories':
            if category not in categories_allowed:
                return False, f"Промокод не применяется к категории товара '{item.get('name')}'"

    return True, None


def calculate_promo_discount(promo_code, subtotal):
    promocodes = load_promocodes_list()
    if promo_code not in promocodes:
        return 0

    promo = promocodes[promo_code]
    if promo['type'] == 'percent':
        return subtotal * promo['discount'] / 100
    else:
        return min(promo['discount'], subtotal)


def is_user_banned(email):
    try:
        banned = load_banned_users()
        email_lower = email.lower()
        if email_lower in banned:
            ban_info = banned[email_lower]
            ban_until = ban_info.get('ban_until')
            if ban_until:
                ban_until_time = datetime.fromisoformat(ban_until)
                if datetime.now() < ban_until_time:
                    return True, ban_until_time, ban_info.get('reason', ''), ban_info.get('message', '')
                else:
                    del banned[email_lower]
                    save_banned_users(banned)
        return False, None, None, None
    except Exception as e:
        log_error("Ошибка проверки бана", e)
        return False, None, None, None


def get_ban_info(email):
    try:
        banned = load_banned_users()
        email_lower = email.lower()
        if email_lower in banned:
            ban_info = banned[email_lower]
            ban_until = ban_info.get('ban_until')
            if ban_until and datetime.now() < datetime.fromisoformat(ban_until):
                return {
                    'ban_until': datetime.fromisoformat(ban_until).strftime('%d.%m.%Y %H:%M:%S'),
                    'reason': ban_info.get('reason', 'Нарушение правил'),
                    'message': ban_info.get('message', 'Обратитесь к администратору')
                }
        return None
    except Exception as e:
        log_error("Ошибка получения инфо о бане", e)
        return None


def is_admin(email):
    user = load_users().get(email.lower(), {})
    return user.get('is_admin', False)


def is_profile_complete(email):
    user = load_users().get(email.lower(), {})
    return user.get('profile_complete', False) and user.get('full_name') and user.get('phone')


def calculate_distance(address):
    address_lower = address.lower()
    # Города Алтайского края
    if 'барнаул' in address_lower:
        distance = random.randint(1, 30)
    elif 'новосибирск' in address_lower:
        distance = random.randint(200, 250)
    elif 'москва' in address_lower:
        distance = random.randint(3000, 3500)
    elif 'спб' in address_lower or 'санкт-петербург' in address_lower:
        distance = random.randint(3500, 4000)
    elif 'томск' in address_lower:
        distance = random.randint(400, 450)
    elif 'кемерово' in address_lower:
        distance = random.randint(250, 300)
    elif 'новокузнецк' in address_lower:
        distance = random.randint(350, 400)
    elif 'бийск' in address_lower:
        distance = random.randint(150, 180)
    elif 'рубцовск' in address_lower:
        distance = random.randint(250, 280)
    elif 'белокуриха' in address_lower:
        distance = random.randint(180, 220)
    elif 'заринск' in address_lower:
        distance = random.randint(100, 130)
    else:
        distance = random.randint(50, 2000)

    return distance


def calculate_delivery_date(distance_km):
    if distance_km <= 50:
        days = 3
        period_text = "3 дня"
        delivery_price = 0
    elif distance_km <= 100:
        days = 7
        period_text = "7 дней"
        delivery_price = 0
    elif distance_km <= 300:
        days = 10
        period_text = "10 дней"
        delivery_price = 0
    else:
        days = 14
        period_text = "14 дней (2 недели)"
        delivery_price = 0

    delivery_date = (datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')
    return delivery_date, period_text, delivery_price


def get_product_price(product):
    if product.get('sale_price') and product['sale_price'] > 0 and product['sale_price'] < product['price']:
        return product['sale_price']
    return product['price']


def get_daily_random_reviews():
    reviews = load_reviews()
    if len(reviews) == 0:
        return []
    today_seed = int(datetime.now().strftime('%Y%m%d'))
    random.seed(today_seed)
    shuffled = reviews.copy()
    random.shuffle(shuffled)
    return shuffled[:3]


def allowed_file(filename, filetype='image'):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if filetype == 'image':
        return ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    elif filetype == 'video':
        return ext in {'mp4', 'webm', 'mov', 'avi', 'mkv'}
    return False


def save_uploaded_file(file, folder, prefix):
    if file and allowed_file(file.filename, 'image' if 'image' in folder else 'video'):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(
            f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.{ext}")
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return f'/{folder}/{filename}'
    return None


def backup_all_data():
    """Создание резервной копии всех данных"""
    try:
        backup_dir = f"backups/full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)

        for name, filepath in DATA_FILES.items():
            if os.path.exists(filepath):
                import shutil
                shutil.copy(filepath, os.path.join(backup_dir, os.path.basename(filepath)))

        # Логирование бекапа
        backup_log = load_data(DATA_FILES['backup_log'], [])
        backup_log.append({
            'timestamp': datetime.now().isoformat(),
            'backup_dir': backup_dir,
            'files': list(DATA_FILES.keys())
        })
        save_data(DATA_FILES['backup_log'], backup_log[-100:])  # Храним последние 100 записей

        app.logger.info(f"Создана резервная копия: {backup_dir}")
        return True
    except Exception as e:
        log_error("Ошибка создания резервной копии", e)
        return False


# ==================== EMAIL ФУНКЦИИ ====================
EMAIL_CONFIG = {
    'smtp_server': 'smtp.mail.ru',
    'smtp_port': 587,
    'email': 'vaincode@mail.ru',
    'password': '7lvM92oEvTGdieqUCwGM',
    'admin_email': 'vaincode@mail.ru'
}


def send_email(to_email, subject, html_content):
    """Универсальная функция отправки email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()

        app.logger.info(f"Email отправлен на {to_email}: {subject}")
        return True
    except Exception as e:
        log_error(f"Ошибка отправки email на {to_email}", e)
        return False


def send_verification_email(email, code, type='registration'):
    if type == 'registration':
        subject = 'Код подтверждения регистрации - Zetta'
        title = 'Подтверждение регистрации'
        message = 'Вы зарегистрировались в компании Zetta.'
        instruction = 'Для завершения регистрации введите следующий код подтверждения:'
    else:
        subject = 'Код восстановления пароля - Zetta'
        title = 'Восстановление пароля'
        message = 'Вы запросили восстановление пароля в компании Zetta.'
        instruction = 'Для сброса пароля введите следующий код:'

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <div style="background: #1a1a1a; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">⚡ Zetta</h1>
            </div>
            <div style="padding: 30px; text-align: center;">
                <h2>{title}</h2>
                <p>{message}</p>
                <p>{instruction}</p>
                <div style="font-size: 32px; font-weight: bold; color: #27ae60; letter-spacing: 5px; background: #f0f0f0; padding: 15px; border-radius: 8px; font-family: monospace;">{code}</div>
                <p style="margin-top: 20px; color: #666;">Код действителен в течение 5 минут.</p>
                <p style="color: #999; font-size: 12px;">Если вы не запрашивали это действие, проигнорируйте данное письмо.</p>
            </div>
            <div style="background: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>© 2026 Zetta. Все права защищены.</p>
                <p>г. Барнаул, ул. Юрина, 182</p>
            </div>
        </div>
    </body>
    </html>
    '''
    return send_email(email, subject, html_content)


def send_operator_request_email(user_name, user_phone, user_email):
    subject = 'ЗАПРОС СВЯЗИ С ОПЕРАТОРОМ - Zetta'
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif;">
        <h1 style="color: #e74c3c;">📞 ЗАПРОС СВЯЗИ С ОПЕРАТОРОМ</h1>
        <p><strong>Клиент запросил звонок оператора!</strong></p>
        <hr>
        <p><strong>👤 ФИО:</strong> {user_name}</p>
        <p><strong>📱 Телефон:</strong> {user_phone}</p>
        <p><strong>📧 Email:</strong> {user_email}</p>
        <p><strong>⏰ Время запроса:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        <hr>
        <p>✅ Свяжитесь с клиентом в ближайшее время!</p>
    </body>
    </html>
    '''
    return send_email(EMAIL_CONFIG['admin_email'], subject, html_content)


def send_receipt_email(order_data):
    subject = f'Чек оплаты #{order_data["order_number"]} - Zetta'
    payment_method_text = "Банковская карта (онлайн)" if order_data[
                                                             'payment_method'] == 'card' else "Наличными при получении"

    items_html = ''
    for item in order_data['items']:
        items_html += f'''
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 8px;">{item["name"]}</td>
            <td style="padding: 8px; text-align: center;">{item["quantity"]}</td>
            <td style="padding: 8px; text-align: right;">{item["price"]:,} ₽</td>
            <td style="padding: 8px; text-align: right;">{item["total"]:,} ₽</td>
        </tr>
        '''

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border: 1px solid #ddd; border-radius: 10px; overflow: hidden;">
            <div style="background: #1a1a1a; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">⚡ ЧЕК ОПЛАТЫ</h1>
                <p style="margin: 5px 0 0;">ZETTA - Профессиональная сборка ПК и IT-услуги</p>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f9f9f9; padding: 15px; margin-bottom: 20px; border-left: 3px solid #27ae60;">
                    <p><strong>Номер заказа:</strong> #{order_data["order_number"]}</p>
                    <p><strong>Дата и время:</strong> {order_data["datetime"]}</p>
                    <p><strong>Статус:</strong> <span style="display: inline-block; padding: 3px 8px; background: #27ae60; color: white; font-size: 12px; border-radius: 3px;">{"Оплачен онлайн" if order_data['payment_method'] == 'card' else "Ожидает оплаты при получении"}</span></p>
                </div>

                <div style="background: #e8f5e9; padding: 15px; margin-bottom: 20px; border-left: 3px solid #2196f3;">
                    <h4 style="margin: 0 0 10px;">Информация о клиенте:</h4>
                    <p><strong>ФИО:</strong> {order_data["customer_name"]}</p>
                    <p><strong>Email:</strong> {order_data["customer_email"]}</p>
                    <p><strong>Телефон:</strong> {order_data["customer_phone"]}</p>
                </div>

                <h3>Услуги в заказе:</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #1a1a1a; color: white;">
                            <th style="padding: 10px; text-align: left;">Наименование</th>
                            <th style="padding: 10px; text-align: center;">Кол-во</th>
                            <th style="padding: 10px; text-align: right;">Цена</th>
                            <th style="padding: 10px; text-align: right;">Сумма</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>

                <div style="text-align: right; padding: 15px; background: #f9f9f9; margin-top: 20px;">
                    <p><strong>Подытог:</strong> {order_data['subtotal']:,} ₽</p>
                    {f'<p><strong>Скидка:</strong> -{order_data["discount"]:,} ₽</p>' if order_data['discount'] > 0 else ''}
                    <p style="font-size: 1.2em; border-top: 2px solid #ddd; padding-top: 10px;"><strong>ИТОГО:</strong> {order_data['total']:,} ₽</p>
                </div>

                <div style="background: #fff3e0; padding: 15px; margin-top: 20px;">
                    <h4>Информация о доставке:</h4>
                    <p><strong>Откуда:</strong> {order_data["from_address"]}</p>
                    <p><strong>Куда:</strong> {order_data["delivery_address"]}</p>
                    <p><strong>Расстояние:</strong> {order_data["distance"]} км</p>
                    <p><strong>Срок доставки:</strong> {order_data["delivery_period"]}</p>
                    <p><strong>Ожидаемая дата доставки:</strong> {order_data["delivery_date"]}</p>
                    <p><strong>Способ оплаты:</strong> {payment_method_text}</p>
                    {f'<p><strong>Реквизиты для оплаты:</strong> Переведите {order_data["total"]:,} ₽ на номер 89520062357 (Сбербанк)</p>' if order_data['payment_method'] == 'card' else '<p><strong>Оплата при получении:</strong> Наличными курьеру</p>'}
                </div>
            </div>
            <div style="background: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>Спасибо за заказ в Zetta!</p>
                <p>© 2026 Zetta. Все права защищены.</p>
            </div>
        </div>
    </body>
    </html>
    '''

    # Отправка клиенту и копия администратору
    send_email(order_data['customer_email'], subject, html_content)
    send_email(EMAIL_CONFIG['admin_email'], subject, html_content)
    return True


def send_order_confirmation(order_data):
    subject = f'Заказ #{order_data["order_number"]} принят - Zetta'
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; padding: 20px; border-radius: 10px; color: white;">
            <h1 style="color: #27ae60;">⚡ Заказ принят!</h1>
            <p>Ваш заказ #{order_data["order_number"]} успешно создан.</p>
            <p>Сумма: <strong>{order_data["total"]:,} ₽</strong></p>
            <p>Способ оплаты: <strong>{"Онлайн картой" if order_data["payment_method"] == "card" else "Наличными при получении"}</strong></p>
            <p>Доставка по адресу: <strong>{order_data["delivery_address"]}</strong></p>
            <p>Ожидаемая дата доставки: <strong>{order_data["delivery_date"]}</strong></p>
            <hr>
            <p>Спасибо, что выбрали Zetta!</p>
        </div>
    </body>
    </html>
    '''
    return send_email(order_data['customer_email'], subject, html_content)


def send_welcome_email(email, name):
    subject = 'Добро пожаловать в Zetta!'
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; padding: 20px; border-radius: 10px; color: white;">
            <h1 style="color: #27ae60;">⚡ Добро пожаловать в Zetta!</h1>
            <p>Здравствуйте, {name}!</p>
            <p>Благодарим вас за регистрацию в нашей компании.</p>
            <p>Теперь вы можете:</p>
            <ul>
                <li>Оформлять заказы на сборку ПК</li>
                <li>Заказывать создание сайтов</li>
                <li>Получать персональные скидки</li>
                <li>Участвовать в акциях и розыгрышах</li>
            </ul>
            <p>С уважением, команда Zetta</p>
            <hr>
            <p style="font-size: 12px; color: #888;">г. Барнаул, ул. Юрина, 182</p>
        </div>
    </body>
    </html>
    '''
    return send_email(email, subject, html_content)


# ==================== ФУНКЦИИ РЕГИСТРАЦИИ И АВТОРИЗАЦИИ ====================
def register_user(email, password, full_name, phone):
    try:
        users = load_users()
        email_lower = email.lower()
        if email_lower in users:
            return False, "Пользователь с таким email уже существует"

        # Проверка форматов
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return False, "Неверный формат email"
        if len(password) < 6:
            return False, "Пароль должен быть не менее 6 символов"
        if not full_name or len(full_name) < 2:
            return False, "Введите корректное имя"
        if not re.match(r'^[\d\s\+\(\)-]+$', phone) or len(phone.replace( /\D / g, '')) < 10:
            return False, "Неверный формат телефона"

        users[email_lower] = {
            'email': email_lower,
            'password': hash_password(password),
            'full_name': full_name,
            'phone': phone,
            'registered_at': datetime.now().isoformat(),
            'addresses': [],
            'profile_complete': True,
            'is_admin': email_lower == 'admin@zetta.ru',
            'bonus_points': 0,
            'orders_count': 0,
            'total_spent': 0,
            'last_login': None
        }
        save_users(users)

        # Обновление статистики
        stats = load_statistics()
        stats['total_users'] = len(users)
        save_statistics(stats)

        # Отправка приветственного письма
        send_welcome_email(email, full_name)

        app.logger.info(f"Новый пользователь зарегистрирован: {email_lower}")
        return True, "Регистрация успешна"
    except Exception as e:
        log_error("Ошибка регистрации пользователя", e)
        return False, "Ошибка при регистрации"


def login_user(email, password):
    try:
        users = load_users()
        email_lower = email.lower()

        # Проверка бана
        is_banned, ban_until, ban_reason, ban_message = is_user_banned(email_lower)
        if is_banned:
            return False, f"Ваш аккаунт забанен до {ban_until.strftime('%d.%m.%Y %H:%M:%S')}. Причина: {ban_reason}"

        if email_lower in users and verify_password(password, users[email_lower]['password']):
            # Обновление времени последнего входа
            users[email_lower]['last_login'] = datetime.now().isoformat()
            save_users(users)

            session['user_email'] = email_lower
            session['user_name'] = users[email_lower]['full_name']
            session['is_admin'] = users[email_lower].get('is_admin', False)
            session['login_time'] = datetime.now().isoformat()

            app.logger.info(f"Пользователь вошёл: {email_lower}")
            return True, "Вход выполнен"
        return False, "Неверный email или пароль"
    except Exception as e:
        log_error("Ошибка входа", e)
        return False, "Ошибка при входе"


def logout_user():
    if 'user_email' in session:
        app.logger.info(f"Пользователь вышел: {session['user_email']}")
    session.clear()
    return True


def update_user_profile(email, full_name, phone):
    try:
        users = load_users()
        email_lower = email.lower()
        if email_lower in users:
            users[email_lower]['full_name'] = full_name
            users[email_lower]['phone'] = phone
            users[email_lower]['profile_complete'] = True
            save_users(users)
            app.logger.info(f"Профиль обновлён: {email_lower}")
            return True
        return False
    except Exception as e:
        log_error("Ошибка обновления профиля", e)
        return False


def add_user_address(email, address):
    try:
        users = load_users()
        email_lower = email.lower()
        if email_lower in users:
            if 'addresses' not in users[email_lower]:
                users[email_lower]['addresses'] = []
            users[email_lower]['addresses'].append({
                'address': address,
                'added_at': datetime.now().isoformat(),
                'is_default': len(users[email_lower]['addresses']) == 0
            })
            save_users(users)
            return True
        return False
    except Exception as e:
        log_error("Ошибка добавления адреса", e)
        return False


def save_temp_registration(email, data):
    temp = load_verification_codes()
    temp[email] = data
    save_verification_codes(temp)


def get_temp_registration(email):
    return load_verification_codes().get(email)


def delete_temp_registration(email):
    temp = load_verification_codes()
    if email in temp:
        del temp[email]
        save_verification_codes(temp)


def save_password_reset(email, code, expires_at):
    reset = load_password_reset_codes()
    reset[email] = {'code': code, 'expires_at': expires_at}
    save_password_reset_codes(reset)


def get_password_reset(email):
    return load_password_reset_codes().get(email)


def delete_password_reset(email):
    reset = load_password_reset_codes()
    if email in reset:
        del reset[email]
        save_password_reset_codes(reset)


def save_order_to_history(user_email, order_data):
    try:
        orders = load_orders()
        email_lower = user_email.lower()
        if email_lower not in orders:
            orders[email_lower] = []
        orders[email_lower].append(order_data)
        save_orders(orders)

        # Обновление статистики пользователя
        users = load_users()
        if email_lower in users:
            users[email_lower]['orders_count'] = users[email_lower].get('orders_count', 0) + 1
            users[email_lower]['total_spent'] = users[email_lower].get('total_spent', 0) + order_data['total']
            save_users(users)

        # Обновление общей статистики
        update_statistics(order_data)

        app.logger.info(f"Заказ сохранён для {email_lower}: #{order_data['order_number']}")
        return True
    except Exception as e:
        log_error("Ошибка сохранения заказа", e)
        return False


def get_user_orders(user_email):
    return load_orders().get(user_email.lower(), [])


def get_user_stats(email):
    user = load_users().get(email.lower(), {})
    return {
        'orders_count': user.get('orders_count', 0),
        'total_spent': user.get('total_spent', 0),
        'bonus_points': user.get('bonus_points', 0),
        'registered_at': user.get('registered_at', ''),
        'last_login': user.get('last_login', '')
    }


# ==================== ДЕКОРАТОРЫ ДЛЯ АДМИН-ДОСТУПА ====================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session or not is_admin(session['user_email']):
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)

    return decorated_function


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)

    return decorated_function


def check_ban(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' in session:
            is_banned, _, _, _ = is_user_banned(session['user_email'])
            if is_banned:
                session.clear()
                return jsonify({'error': 'Account banned', 'redirect': '/ban-page'}), 403
        return f(*args, **kwargs)

    return decorated_function


# ==================== СТРАНИЦА БАНА ====================
BAN_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Аккаунт заблокирован - Zetta</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0a0a 0%, #1a0a0a 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 20px;
        }
        .ban-container {
            background: #1a1a1a;
            border: 1px solid #e74c3c;
            border-radius: 16px;
            padding: 2rem;
            max-width: 500px;
            text-align: center;
            animation: fadeInUp 0.6s ease-out;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        .ban-icon { font-size: 4rem; margin-bottom: 1rem; animation: pulse 1.5s ease-in-out infinite; }
        .ban-title { font-size: 1.5rem; font-weight: bold; color: #e74c3c; margin-bottom: 1rem; }
        .ban-subtitle { color: #888; margin-bottom: 1.5rem; font-size: 0.9rem; }
        .ban-info {
            background: #0f0f0f;
            border-radius: 12px;
            padding: 1.5rem;
            text-align: left;
            margin-bottom: 1.5rem;
            border-left: 4px solid #e74c3c;
        }
        .ban-info p { margin: 0.5rem 0; color: #bbb; }
        .ban-info strong { color: #27ae60; }
        .ban-reason {
            background: #2a1a1a;
            padding: 0.8rem;
            border-radius: 8px;
            margin: 0.5rem 0;
            color: #e74c3c;
            font-weight: bold;
        }
        .ban-message {
            background: #1a2a1a;
            padding: 0.8rem;
            border-radius: 8px;
            margin: 0.5rem 0;
            color: #27ae60;
            font-style: italic;
        }
        .ban-date { color: #f39c12; font-weight: bold; }
        .contact-link {
            color: #27ae60;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .contact-link:hover { text-decoration: underline; color: #229954; }
        .back-btn {
            background: #27ae60;
            color: white;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 1rem;
            transition: all 0.3s ease;
        }
        .back-btn:hover { background: #229954; transform: scale(1.02); }
        @media (max-width: 480px) {
            .ban-container { padding: 1.5rem; margin: 20px; }
            .ban-title { font-size: 1.2rem; }
        }
    </style>
</head>
<body>
    <div class="ban-container">
        <div class="ban-icon">🚫</div>
        <div class="ban-title">ДОСТУП ЗАБЛОКИРОВАН</div>
        <div class="ban-subtitle">Ваш аккаунт был заблокирован администрацией</div>
        <div class="ban-info">
            <p><strong>📅 Дата блокировки:</strong> <span class="ban-date">До {{ ban_until }}</span></p>
            <p><strong>⚠️ Причина блокировки:</strong></p>
            <div class="ban-reason">{{ reason }}</div>
            <p><strong>💬 Сообщение от администратора:</strong></p>
            <div class="ban-message">{{ message }}</div>
        </div>
        <p style="color: #888; font-size: 0.85rem;">
            Если вы считаете, что это ошибка, свяжитесь с нами по почте 
            <a href="mailto:vaincode@mail.ru" class="contact-link">vaincode@mail.ru</a>
        </p>
        <button class="back-btn" onclick="window.location.href='/'">🔙 Вернуться на главную</button>
    </div>
</body>
</html>
'''


@app.route('/ban-page')
def ban_page():
    email = request.args.get('email', '')
    ban_info = get_ban_info(email)
    if ban_info:
        return render_template_string(BAN_PAGE_TEMPLATE, ban_until=ban_info['ban_until'], reason=ban_info['reason'],
                                      message=ban_info['message'])
    return redirect('/')


@app.before_request
def check_ban_middleware():
    if request.endpoint in ['static', 'ban_page']:
        return None
    if 'user_email' in session:
        is_banned, ban_until, ban_reason, ban_message = is_user_banned(session['user_email'])
        if is_banned:
            session.clear()
            return redirect(f'/ban-page?email={session["user_email"]}')
    return None


# ==================== API МАРШРУТЫ ====================

# ---------- ЧАТ API ----------
@app.route('/api/chat/send-operator-request', methods=['POST'])
@login_required
@check_ban
def send_operator_request_api():
    try:
        users = load_users()
        user = users.get(session['user_email'], {})
        user_name = user.get('full_name', 'Не указано')
        user_phone = user.get('phone', 'Не указан')
        user_email = session['user_email']

        # Сохраняем заявку в историю
        tickets = load_data(DATA_FILES['support_tickets'], [])
        ticket = {
            'id': len(tickets) + 1,
            'type': 'operator_request',
            'user_email': user_email,
            'user_name': user_name,
            'user_phone': user_phone,
            'status': 'new',
            'created_at': datetime.now().isoformat(),
            'resolved_at': None
        }
        tickets.append(ticket)
        save_data(DATA_FILES['support_tickets'], tickets)

        email_sent = send_operator_request_email(user_name, user_phone, user_email)

        return jsonify({
            'success': True,
            'message': '✅ Заявка отправлена! Оператор свяжется с вами в ближайшее время.',
            'email_sent': email_sent,
            'ticket_id': ticket['id']
        })
    except Exception as e:
        log_error("Ошибка отправки запроса оператору", e)
        return jsonify({'success': False, 'message': 'Ошибка при отправке заявки'}), 500


@app.route('/api/chat/send-payment-question', methods=['POST'])
@login_required
@check_ban
def send_payment_question_api():
    auto_response = """Доброго времени суток, наш дорогой клиент!

В данный момент оплата принимается следующими способами:
1. Наличный расчёт - при получении товара курьеру
2. Перевод на карту Сбербанка - номер карты: 2202 2036 1234 5678 (получатель: Zetta)
3. Безналичный расчёт для юридических лиц - по выставленному счёту

Онлайн-оплата через сайт будет доступна в ближайшее время. 
Следите за нашими новостями!

Если у вас возникли сложности с оплатой, напишите нам на почту vaincode@mail.ru, 
мы поможем решить вопрос индивидуально.

С уважением, команда Zetta ⚡"""

    return jsonify({
        'success': True,
        'response': auto_response
    })


@app.route('/api/chat/site-creation-time', methods=['POST'])
@login_required
@check_ban
def site_creation_time_api():
    response = """⏱️ Сроки создания сайта в компании Zetta:

В зависимости от сложности проекта:
- Сайт-визитка (до 5 страниц): 3-5 рабочих дней
- Лендинг (одностраничный сайт): 5-7 рабочих дней
- Корпоративный сайт (10-20 страниц): 10-14 рабочих дней
- Интернет-магазин: 14-21 рабочий день
- Индивидуальный проект: обсуждается отдельно

⚠️ Важно: Сроки могут варьироваться в зависимости от сложности дизайна, 
наличия уникальных функций и скорости предоставления контента с вашей стороны.

Все наши работы включают:
✅ Адаптивный дизайн (корректное отображение на всех устройствах)
✅ SEO-оптимизацию базовую
✅ Форму обратной связи
✅ Подключение аналитики
✅ Обучение работе с сайтом

Хотите ускорить процесс? Предоставьте все материалы заранее!"""

    return jsonify({
        'success': True,
        'response': response
    })


@app.route('/api/chat/consultation', methods=['POST'])
@login_required
@check_ban
def consultation_api():
    data = request.json
    choice = data.get('choice')

    specialists = {
        'system_admin': {
            'name': 'Богдан Дмитриевич',
            'position': 'Системный администратор',
            'phone': '8 (983) 607-41-15',
            'telegram': '@bogdan_zetta',
            'whatsapp': '89836074115',
            'work_hours': 'Пн-Пт 10:00-18:00',
            'description': 'Специалист по сборке ПК, настройке серверов и IT-инфраструктуры'
        },
        'director': {
            'name': 'Литвинов Антон Евгеньевич',
            'position': 'Генеральный директор',
            'phone': '8 (952) 006-23-57',
            'telegram': '@anton_zetta',
            'whatsapp': '89520062357',
            'work_hours': 'Пн-Пт 10:00-19:00',
            'description': 'По вопросам сотрудничества, крупных заказов и партнёрства'
        },
        'manager': {
            'name': 'Егор Олегович',
            'position': 'Менеджер по работе с клиентами',
            'phone': '8 (913) 244-77-07',
            'telegram': '@egor_zetta',
            'whatsapp': '89132447707',
            'work_hours': 'Пн-Пт 09:00-21:00, Сб-Вс 10:00-19:00',
            'description': 'Консультации по услугам, помощь с выбором, оформление заказов'
        }
    }

    if choice in specialists:
        sp = specialists[choice]
        response = f"""📞 {sp['position']}: {sp['name']}

📱 Телефон: {sp['phone']}
💬 Telegram: {sp['telegram']}
📲 WhatsApp: {sp['whatsapp']}
⏰ Часы работы: {sp['work_hours']}

📝 О специалисте: {sp['description']}

Свяжитесь удобным для вас способом! Мы всегда рады помочь. ⚡"""
    else:
        response = """Пожалуйста, выберите специалиста для консультации:

1. 👨‍💻 Системный администратор - по вопросам сборки ПК, настройки оборудования
2. 👔 Генеральный директор - по вопросам сотрудничества и крупных заказов
3. 📋 Менеджер - по всем вопросам обслуживания клиентов

Напишите номер специалиста или нажмите соответствующую кнопку."""

    return jsonify({
        'success': True,
        'response': response
    })


@app.route('/api/chat/cooperation', methods=['POST'])
@login_required
@check_ban
def cooperation_api():
    response = """🤝 Сотрудничество и реклама с компанией Zetta

Мы открыты для партнёрских отношений!

📧 По вопросам сотрудничества пишите на почту: vaincode@mail.ru
📞 Или звоните по телефону: 8 (952) 006-23-57 (Антон Евгеньевич)

Формы сотрудничества:
✅ Реклама на нашем сайте и в социальных сетях
✅ Партнёрские программы (реферальные ссылки)
✅ Совместные проекты и интеграции
✅ Поставка комплектующих и оборудования
✅ Аутсорсинг IT-услуг

При обращении указывайте:
- Название компании/проекта
- Предлагаемые условия сотрудничества
- Контактные данные для обратной связи

Рассматриваем все предложения! Ждём ваших идей! ⚡"""

    return jsonify({
        'success': True,
        'response': response
    })


# ---------- ВЛОГ API ----------
@app.route('/api/vlog', methods=['GET'])
def get_vlog_api():
    try:
        vlog = load_vlog()
        return jsonify(vlog)
    except Exception as e:
        log_error("Ошибка получения влога", e)
        return jsonify({'text': 'Ошибка загрузки блога'}), 500


@app.route('/api/admin/update-vlog', methods=['POST'])
@admin_required
def update_vlog_api():
    try:
        data = request.json
        text = data.get('text', '')

        if not text:
            return jsonify({'success': False, 'message': 'Текст не может быть пустым'}), 400

        vlog = load_vlog()
        vlog['text'] = text
        vlog['last_updated'] = datetime.now().isoformat()
        vlog['updated_by'] = session['user_email']
        save_vlog(vlog)

        app.logger.info(f"Влог обновлён админом {session['user_email']}")
        return jsonify({'success': True, 'message': 'Влог успешно обновлён'})
    except Exception as e:
        log_error("Ошибка обновления влога", e)
        return jsonify({'success': False, 'message': 'Ошибка при обновлении влога'}), 500


# ---------- ОБРАТНАЯ СВЯЗЬ ----------
@app.route('/api/send-feedback', methods=['POST'])
@login_required
@check_ban
def send_feedback_api():
    try:
        data = request.json
        message = data.get('message', '')
        feedback_type = data.get('type', 'general')  # general, complaint, suggestion

        if not message or len(message) < 10:
            return jsonify({'success': False, 'message': 'Сообщение должно содержать не менее 10 символов'}), 400

        if len(message) > 5000:
            return jsonify({'success': False, 'message': 'Сообщение не должно превышать 5000 символов'}), 400

        users = load_users()
        user = users.get(session['user_email'], {})
        user_name = user.get('full_name', 'Не указано')
        user_phone = user.get('phone', 'Не указан')
        user_email = session['user_email']

        # Сохраняем обращение
        feedbacks = load_data('data/feedbacks.json', [])
        feedback = {
            'id': len(feedbacks) + 1,
            'type': feedback_type,
            'user_email': user_email,
            'user_name': user_name,
            'user_phone': user_phone,
            'message': message,
            'status': 'new',
            'created_at': datetime.now().isoformat(),
            'resolved_at': None,
            'admin_response': None
        }
        feedbacks.append(feedback)
        save_data('data/feedbacks.json', feedbacks)

        # Отправка email администратору
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = EMAIL_CONFIG['admin_email']
            msg['Subject'] = f'ОБРАЩЕНИЕ #{feedback["id"]}: {feedback_type.upper()} от {user_name}'

            type_names = {'general': 'Общее обращение', 'complaint': 'Жалоба', 'suggestion': 'Предложение'}

            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif;">
                <h1 style="color: #e74c3c;">📬 НОВОЕ ОБРАЩЕНИЕ #{feedback["id"]}</h1>
                <hr>
                <p><strong>📋 Тип:</strong> {type_names.get(feedback_type, 'Общее')}</p>
                <p><strong>👤 Отправитель:</strong> {user_name}</p>
                <p><strong>📧 Email:</strong> {user_email}</p>
                <p><strong>📱 Телефон:</strong> {user_phone}</p>
                <p><strong>⏰ Время отправки:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
                <hr>
                <p><strong>💬 Сообщение:</strong></p>
                <div style="background: #f0f0f0; padding: 1rem; border-radius: 8px; margin-top: 0.5rem; white-space: pre-wrap;">
                    {message.replace(chr(10), '<br>')}
                </div>
                <hr>
                <p style="color: #888;">Ответьте на обращение в течение 24 часов.</p>
            </body>
            </html>
            '''

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()

            app.logger.info(f"Отправлен фидбек от {user_email}, тип: {feedback_type}")
        except Exception as e:
            log_error("Ошибка отправки email фидбека", e)

        return jsonify({
            'success': True,
            'message': 'Сообщение отправлено! Спасибо за обратную связь.',
            'feedback_id': feedback['id']
        })
    except Exception as e:
        log_error("Ошибка отправки фидбека", e)
        return jsonify({'success': False, 'message': 'Ошибка при отправке. Попробуйте позже.'}), 500


# ---------- АВТОРИЗАЦИЯ API ----------
@app.route('/api/auth/status', methods=['GET'])
def auth_status_api():
    try:
        if 'user_email' in session:
            is_banned, ban_until, ban_reason, ban_message = is_user_banned(session['user_email'])
            if is_banned:
                session.clear()
                return jsonify({'logged_in': False, 'is_admin': False, 'banned': True})

            users = load_users()
            user = users.get(session['user_email'], {})
            return jsonify({
                'logged_in': True,
                'user': {
                    'full_name': user.get('full_name', ''),
                    'email': user.get('email', ''),
                    'phone': user.get('phone', ''),
                    'registered_at': user.get('registered_at', ''),
                    'bonus_points': user.get('bonus_points', 0),
                    'orders_count': user.get('orders_count', 0)
                },
                'is_admin': user.get('is_admin', False)
            })
        return jsonify({'logged_in': False, 'is_admin': False})
    except Exception as e:
        log_error("Ошибка получения статуса авторизации", e)
        return jsonify({'logged_in': False, 'is_admin': False}), 500


@app.route('/api/auth/login', methods=['POST'])
def api_login_route():
    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        success, message = login_user(email, password)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        log_error("Ошибка входа в API", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


@app.route('/api/auth/logout', methods=['POST'])
def api_logout_route():
    try:
        logout_user()
        return jsonify({'success': True, 'message': 'Вы вышли из аккаунта'})
    except Exception as e:
        log_error("Ошибка выхода", e)
        return jsonify({'success': False, 'message': 'Ошибка при выходе'}), 500


@app.route('/api/check-profile-complete', methods=['GET'])
@login_required
@check_ban
def check_profile_complete_api():
    try:
        complete = is_profile_complete(session['user_email'])
        return jsonify({'complete': complete})
    except Exception as e:
        log_error("Ошибка проверки профиля", e)
        return jsonify({'complete': False}), 500


@app.route('/api/update-profile', methods=['POST'])
@login_required
@check_ban
def update_profile_api():
    try:
        data = request.json
        full_name = data.get('full_name', '').strip()
        phone = data.get('phone', '').strip()

        if not full_name:
            return jsonify({'success': False, 'message': 'Введите ФИО'}), 400
        if len(full_name) < 2:
            return jsonify({'success': False, 'message': 'ФИО должно содержать не менее 2 символов'}), 400
        if not phone:
            return jsonify({'success': False, 'message': 'Введите телефон'}), 400

        # Очистка телефона
        phone_clean = re.sub(r'[\s\(\)-]', '', phone)
        if len(phone_clean) < 10:
            return jsonify({'success': False, 'message': 'Неверный формат телефона'}), 400

        if update_user_profile(session['user_email'], full_name, phone):
            session['user_name'] = full_name
            return jsonify({'success': True, 'message': 'Профиль успешно обновлён'})
        return jsonify({'success': False, 'message': 'Ошибка при обновлении профиля'}), 500
    except Exception as e:
        log_error("Ошибка обновления профиля API", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


@app.route('/api/user/profile', methods=['GET'])
@login_required
@check_ban
def get_user_profile_api():
    try:
        users = load_users()
        user = users.get(session['user_email'], {})
        stats = get_user_stats(session['user_email'])

        return jsonify({
            'full_name': user.get('full_name', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'registered_at': user.get('registered_at', ''),
            'addresses': user.get('addresses', []),
            'bonus_points': stats['bonus_points'],
            'orders_count': stats['orders_count'],
            'total_spent': stats['total_spent'],
            'last_login': user.get('last_login', '')
        })
    except Exception as e:
        log_error("Ошибка получения профиля", e)
        return jsonify({'error': 'Ошибка сервера'}), 500


@app.route('/api/user/orders', methods=['GET'])
@login_required
@check_ban
def get_user_orders_api_route():
    try:
        orders = get_user_orders(session['user_email'])
        return jsonify(orders)
    except Exception as e:
        log_error("Ошибка получения заказов", e)
        return jsonify([]), 500


@app.route('/api/user/add-address', methods=['POST'])
@login_required
@check_ban
def add_user_address_api():
    try:
        data = request.json
        address = data.get('address', '').strip()

        if not address:
            return jsonify({'success': False, 'message': 'Введите адрес'}), 400
        if len(address) < 5:
            return jsonify({'success': False, 'message': 'Адрес слишком короткий'}), 400

        if add_user_address(session['user_email'], address):
            return jsonify({'success': True, 'message': 'Адрес добавлен'})
        return jsonify({'success': False, 'message': 'Ошибка при добавлении адреса'}), 500
    except Exception as e:
        log_error("Ошибка добавления адреса", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


# ---------- ВОССТАНОВЛЕНИЕ ПАРОЛЯ ----------
@app.route('/api/send-reset-code', methods=['POST'])
def send_reset_code_api():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Введите email'}), 400

        users = load_users()
        if email not in users:
            return jsonify({'success': False, 'message': 'Пользователь с таким email не найден'}), 404

        code = generate_verification_code()
        expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()

        save_password_reset(email, code, expires_at)

        if send_verification_email(email, code, 'reset'):
            return jsonify({'success': True, 'message': 'Код восстановления отправлен на почту'})
        else:
            delete_password_reset(email)
            return jsonify({'success': False, 'message': 'Ошибка при отправке письма. Попробуйте позже.'}), 500
    except Exception as e:
        log_error("Ошибка отправки кода восстановления", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


@app.route('/api/reset-password', methods=['POST'])
def reset_password_api():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        new_password = data.get('new_password', '')

        if not email or not code or not new_password:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Пароль должен содержать не менее 6 символов'}), 400

        reset_data = get_password_reset(email)
        if not reset_data:
            return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'}), 404

        if datetime.now().timestamp() > reset_data['expires_at']:
            delete_password_reset(email)
            return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'}), 400

        if reset_data['code'] != code:
            return jsonify({'success': False, 'message': 'Неверный код подтверждения'}), 400

        users = load_users()
        if email in users:
            users[email]['password'] = hash_password(new_password)
            save_users(users)
            delete_password_reset(email)

            app.logger.info(f"Пароль сброшен для {email}")
            return jsonify({'success': True, 'message': 'Пароль успешно изменён'})

        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    except Exception as e:
        log_error("Ошибка сброса пароля", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


# ---------- РЕГИСТРАЦИЯ ----------
@app.route('/api/send-verification', methods=['POST'])
def send_verification_api():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        full_name = data.get('full_name', '').strip()
        phone = data.get('phone', '').strip()
        password = data.get('password', '')

        # Валидация
        if not full_name or not email or not phone or not password:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return jsonify({'success': False, 'message': 'Неверный формат email'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Пароль должен содержать не менее 6 символов'}), 400

        phone_clean = re.sub(r'[\s\(\)-]', '', phone)
        if len(phone_clean) < 10:
            return jsonify({'success': False, 'message': 'Неверный формат телефона'}), 400

        users = load_users()
        if email in users:
            return jsonify({'success': False, 'message': 'Пользователь с таким email уже существует'}), 409

        code = generate_verification_code()
        expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()

        temp_data = {
            'code': code,
            'expires_at': expires_at,
            'full_name': full_name,
            'phone': phone,
            'password': password
        }
        save_temp_registration(email, temp_data)

        if send_verification_email(email, code, 'registration'):
            return jsonify({'success': True, 'message': 'Код подтверждения отправлен на почту'})
        else:
            delete_temp_registration(email)
            return jsonify({'success': False, 'message': 'Ошибка при отправке письма. Попробуйте позже.'}), 500
    except Exception as e:
        log_error("Ошибка отправки кода подтверждения", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


@app.route('/api/verify-code', methods=['POST'])
def verify_code_api():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()

        if not email or not code:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        temp_data = get_temp_registration(email)
        if not temp_data:
            return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'}), 404

        if datetime.now().timestamp() > temp_data['expires_at']:
            delete_temp_registration(email)
            return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'}), 400

        if temp_data['code'] != code:
            return jsonify({'success': False, 'message': 'Неверный код подтверждения'}), 400

        success, message = register_user(
            email,
            temp_data['password'],
            temp_data['full_name'],
            temp_data['phone']
        )

        if success:
            delete_temp_registration(email)
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400
    except Exception as e:
        log_error("Ошибка верификации кода", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


@app.route('/api/resend-verification', methods=['POST'])
def resend_verification_api():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Введите email'}), 400

        temp_data = get_temp_registration(email)
        if not temp_data:
            return jsonify({'success': False, 'message': 'Данные не найдены. Заполните форму регистрации заново.'}), 404

        new_code = generate_verification_code()
        temp_data['code'] = new_code
        temp_data['expires_at'] = (datetime.now() + timedelta(minutes=5)).timestamp()

        temp_registrations = load_verification_codes()
        temp_registrations[email] = temp_data
        save_verification_codes(temp_registrations)

        if send_verification_email(email, new_code, 'registration'):
            return jsonify({'success': True, 'message': 'Новый код отправлен на почту'})
        else:
            return jsonify({'success': False, 'message': 'Ошибка при отправке письма'}), 500
    except Exception as e:
        log_error("Ошибка повторной отправки кода", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500# ---------- ОТЗЫВЫ API ----------
@app.route('/api/home-reviews', methods=['GET'])
def get_home_reviews_api():
    """Получение случайных отзывов для главной страницы"""
    try:
        reviews = get_daily_random_reviews()
        return jsonify(reviews)
    except Exception as e:
        log_error("Ошибка получения отзывов для главной", e)
        return jsonify([]), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews_api():
    """Получение всех отзывов"""
    try:
        reviews = load_reviews()
        return jsonify(reviews)
    except Exception as e:
        log_error("Ошибка получения всех отзывов", e)
        return jsonify([]), 500

@app.route('/api/add-review', methods=['POST'])
@login_required
@check_ban
def add_review_api():
    """Добавление нового отзыва"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        rating = data.get('rating', 5)
        text = data.get('text', '').strip()

        if not name:
            name = session.get('user_name', 'Аноним')

        if rating < 1 or rating > 5:
            rating = 5

        if not text or len(text) < 10:
            return jsonify({'success': False, 'message': 'Отзыв должен содержать не менее 10 символов'}), 400

        if len(text) > 2000:
            return jsonify({'success': False, 'message': 'Отзыв не должен превышать 2000 символов'}), 400

        reviews = load_reviews()

        # Добавляем отзыв в начало списка
        new_review = {
            'name': name,
            'rating': rating,
            'text': text,
            'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'user_email': session['user_email'],
            'likes': 0,
            'dislikes': 0
        }
        reviews.insert(0, new_review)
        save_reviews(reviews)

        # Отправка уведомления администратору
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = EMAIL_CONFIG['admin_email']
            msg['Subject'] = f'НОВЫЙ ОТЗЫВ от {name} - Zetta'

            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif;">
                <h1 style="color: #27ae60;">⭐ НОВЫЙ ОТЗЫВ</h1>
                <p><strong>Автор:</strong> {name}</p>
                <p><strong>Оценка:</strong> {'★' * rating}{'☆' * (5 - rating)}</p>
                <p><strong>Текст:</strong></p>
                <div style="background: #f0f0f0; padding: 1rem; border-radius: 8px;">{text.replace(chr(10), '<br>')}</div>
                <p><strong>Время:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </body>
            </html>
            '''

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except Exception as e:
            log_error("Ошибка отправки уведомления о новом отзыве", e)

        app.logger.info(f"Добавлен новый отзыв от {name}, оценка: {rating}")
        return jsonify({'success': True, 'message': 'Спасибо за отзыв!'})
    except Exception as e:
        log_error("Ошибка добавления отзыва", e)
        return jsonify({'success': False, 'message': 'Ошибка при сохранении отзыва'}), 500

@app.route('/api/review/like/<int:review_id>', methods=['POST'])
@login_required
@check_ban
def like_review_api(review_id):
    """Лайк отзыва"""
    try:
        reviews = load_reviews()
        if 0 <= review_id < len(reviews):
            reviews[review_id]['likes'] = reviews[review_id].get('likes', 0) + 1
            save_reviews(reviews)
            return jsonify({'success': True, 'likes': reviews[review_id]['likes']})
        return jsonify({'success': False, 'message': 'Отзыв не найден'}), 404
    except Exception as e:
        log_error("Ошибка лайка отзыва", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

# ---------- ТОВАРЫ API ----------
@app.route('/api/products')
def get_products_api():
    """Получение списка товаров с фильтрацией и пагинацией"""
    try:
        search = request.args.get('search', '').lower()
        category = request.args.get('category', '')
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        sort_by = request.args.get('sort_by', 'name')  # name, price_asc, price_desc, rating
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)

        products = load_products()

        # Фильтрация по поиску
        if search:
            products = [p for p in products if search in p['name'].lower() or search in p.get('description', '').lower()]

        # Фильтрация по категории
        if category and category != 'all':
            products = [p for p in products if p.get('category') == category]

        # Фильтрация по цене
        if min_price is not None:
            products = [p for p in products if get_product_price(p) >= min_price]
        if max_price is not None:
            products = [p for p in products if get_product_price(p) <= max_price]

        # Сортировка
        if sort_by == 'price_asc':
            products.sort(key=lambda x: get_product_price(x))
        elif sort_by == 'price_desc':
            products.sort(key=lambda x: get_product_price(x), reverse=True)
        elif sort_by == 'rating':
            products.sort(key=lambda x: x.get('rating', 0), reverse=True)
        else:  # name
            products.sort(key=lambda x: x['name'])

        # Пагинация
        total = len(products)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_products = products[start:end]

        return jsonify({
            'products': paginated_products,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        log_error("Ошибка получения товаров", e)
        return jsonify({'products': [], 'total': 0, 'page': 1, 'per_page': 12, 'total_pages': 0}), 500

@app.route('/api/product/<int:product_id>')
def get_product_api(product_id):
    """Получение информации о конкретном товаре"""
    try:
        products = load_products()
        product = next((p for p in products if p['id'] == product_id), None)
        if product:
            # Увеличиваем счетчик просмотров
            product['views'] = product.get('views', 0) + 1
            save_products(products)
            return jsonify(product)
        return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        log_error(f"Ошибка получения товара {product_id}", e)
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/products/categories', methods=['GET'])
def get_categories_api():
    """Получение списка категорий с количеством товаров"""
    try:
        products = load_products()
        categories = {}
        for product in products:
            cat = product.get('category', 'other')
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        # Добавляем названия категорий на русском
        category_names = {
            'computers': '💻 Компьютеры',
            'services': '🔧 Услуги',
            'pc_build': '🛠️ Сборка ПК',
            'websites': '🌐 Сайты',
            'components': '🔩 Комплектующие',
            'other': '📦 Прочее'
        }

        result = []
        for cat, count in categories.items():
            result.append({
                'id': cat,
                'name': category_names.get(cat, cat),
                'count': count
            })

        return jsonify(result)
    except Exception as e:
        log_error("Ошибка получения категорий", e)
        return jsonify([]), 500

@app.route('/api/products/search-suggestions', methods=['GET'])
def search_suggestions_api():
    """Поисковые подсказки"""
    try:
        query = request.args.get('q', '').lower()
        if len(query) < 2:
            return jsonify([])

        products = load_products()
        suggestions = []

        for product in products:
            if query in product['name'].lower():
                suggestions.append({
                    'id': product['id'],
                    'name': product['name'],
                    'price': get_product_price(product),
                    'image': product['image']
                })
                if len(suggestions) >= 5:
                    break

        return jsonify(suggestions)
    except Exception as e:
        log_error("Ошибка поисковых подсказок", e)
        return jsonify([]), 500

# ---------- ДОСТАВКА API ----------
@app.route('/api/calculate-delivery', methods=['POST'])
def calculate_delivery_api():
    """Расчёт стоимости и сроков доставки"""
    try:
        data = request.json
        address = data.get('address', '').strip()

        if not address:
            return jsonify({'error': 'Адрес не указан'}), 400

        distance = calculate_distance(address)
        delivery_date, period_text, delivery_price = calculate_delivery_date(distance)

        # Определяем возможные способы доставки
        delivery_methods = []

        if distance <= 30:
            delivery_methods.append({
                'name': 'Курьерская доставка',
                'price': 0,
                'days': 1,
                'description': 'Доставка курьером по городу'
            })

        delivery_methods.append({
            'name': 'Доставка транспортной компанией',
            'price': delivery_price,
            'days': distance // 50 + 1,
            'description': 'Доставка до пункта выдачи ТК'
        })

        delivery_methods.append({
            'name': 'Самовывоз',
            'price': 0,
            'days': 0,
            'description': 'Самовывоз из офиса: г. Барнаул, ул. Юрина, 182'
        })

        return jsonify({
            'distance': distance,
            'delivery_date': delivery_date,
            'delivery_period': period_text,
            'delivery_price': delivery_price,
            'delivery_methods': delivery_methods
        })
    except Exception as e:
        log_error("Ошибка расчёта доставки", e)
        return jsonify({'error': 'Ошибка расчёта доставки'}), 500

@app.route('/api/delivery/track/<order_number>', methods=['GET'])
def track_delivery_api(order_number):
    """Отслеживание статуса доставки заказа"""
    try:
        # Поиск заказа
        orders = load_orders()
        for email, user_orders in orders.items():
            for order in user_orders:
                if order.get('order_number') == order_number:
                    # Симуляция статуса доставки
                    days_since_order = (datetime.now() - datetime.strptime(order['datetime'], '%d.%m.%Y %H:%M:%S')).days

                    if days_since_order < 1:
                        status = 'processing'
                        status_text = 'Заказ обрабатывается'
                        description = 'Ваш заказ принят в обработку. Скоро мы начнём его сборку.'
                    elif days_since_order < 3:
                        status = 'preparing'
                        status_text = 'Сборка заказа'
                        description = 'Специалисты собирают ваш заказ. Ожидайте.'
                    elif days_since_order < 5:
                        status = 'shipping'
                        status_text = 'Передано в доставку'
                        description = 'Заказ передан в службу доставки. Ожидайте звонка курьера.'
                    elif days_since_order < 7:
                        status = 'out_for_delivery'
                        status_text = 'Доставляется'
                        description = 'Ваш заказ уже в пути! Курьер скоро свяжется с вами.'
                    else:
                        status = 'delivered'
                        status_text = 'Доставлен'
                        description = f'Заказ доставлен по адресу: {order["delivery_address"]}'

                    # История статусов
                    status_history = [
                        {'status': 'processing', 'date': order['datetime'], 'text': 'Заказ создан'},
                        {'status': 'preparing', 'date': (datetime.strptime(order['datetime'], '%d.%m.%Y %H:%M:%S') + timedelta(days=1)).strftime('%d.%m.%Y %H:%M:%S'), 'text': 'Начат сборка заказа'},
                    ]

                    if days_since_order >= 3:
                        status_history.append({'status': 'shipping', 'date': (datetime.strptime(order['datetime'], '%d.%m.%Y %H:%M:%S') + timedelta(days=3)).strftime('%d.%m.%Y %H:%M:%S'), 'text': 'Передано в доставку'})
                    if days_since_order >= 5:
                        status_history.append({'status': 'out_for_delivery', 'date': (datetime.strptime(order['datetime'], '%d.%m.%Y %H:%M:%S') + timedelta(days=5)).strftime('%d.%m.%Y %H:%M:%S'), 'text': 'Курьер выехал'})
                    if days_since_order >= 7:
                        status_history.append({'status': 'delivered', 'date': (datetime.strptime(order['datetime'], '%d.%m.%Y %H:%M:%S') + timedelta(days=7)).strftime('%d.%m.%Y %H:%M:%S'), 'text': 'Заказ доставлен'})

                    return jsonify({
                        'order_number': order_number,
                        'status': status,
                        'status_text': status_text,
                        'description': description,
                        'estimated_date': order.get('delivery_date', ''),
                        'history': status_history
                    })

        return jsonify({'error': 'Заказ не найден'}), 404
    except Exception as e:
        log_error(f"Ошибка отслеживания заказа {order_number}", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

# ---------- КОРЗИНА API ----------
@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart_api():
    """Добавление товара в корзину"""
    try:
        data = request.json
        product_id = str(data.get('product_id'))

        if not product_id:
            return jsonify({'success': False, 'message': 'ID товара не указан'}), 400

        cart = session.get('cart', {})
        cart[product_id] = cart.get(product_id, 0) + 1
        session['cart'] = cart

        # Получаем общее количество товаров в корзине
        total_items = sum(cart.values())

        return jsonify({'success': True, 'cart_count': total_items})
    except Exception as e:
        log_error("Ошибка добавления в корзину", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/update-cart', methods=['POST'])
def update_cart_api():
    """Обновление количества товара в корзине"""
    try:
        data = request.json
        product_id = str(data.get('product_id'))
        quantity = data.get('quantity', 1)

        if not product_id:
            return jsonify({'success': False, 'message': 'ID товара не указан'}), 400

        if quantity < 0:
            quantity = 0

        cart = session.get('cart', {})
        if quantity > 0:
            cart[product_id] = quantity
        else:
            cart.pop(product_id, None)

        session['cart'] = cart

        total_items = sum(cart.values())

        return jsonify({'success': True, 'cart_count': total_items})
    except Exception as e:
        log_error("Ошибка обновления корзины", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/remove-from-cart', methods=['POST'])
def remove_from_cart_api():
    """Удаление товара из корзины"""
    try:
        data = request.json
        product_id = str(data.get('product_id'))

        if not product_id:
            return jsonify({'success': False, 'message': 'ID товара не указан'}), 400

        cart = session.get('cart', {})
        cart.pop(product_id, None)
        session['cart'] = cart

        total_items = sum(cart.values())

        return jsonify({'success': True, 'cart_count': total_items})
    except Exception as e:
        log_error("Ошибка удаления из корзины", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/cart')
def get_cart_api():
    """Получение содержимого корзины"""
    try:
        cart = session.get('cart', {})
        promo_code = session.get('promo_code')
        products = load_products()
        promocodes = load_promocodes_list()

        items = []
        subtotal = 0
        cart_items_for_promo = []

        for product_id, quantity in cart.items():
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if product:
                price = get_product_price(product)
                item_total = price * quantity
                subtotal += item_total
                items.append({
                    'id': product['id'],
                    'name': product['name'],
                    'price': price,
                    'original_price': product['price'],
                    'quantity': quantity,
                    'total': item_total,
                    'category': product.get('category', ''),
                    'image': product.get('image', '')
                })
                cart_items_for_promo.append({
                    'id': product['id'],
                    'name': product['name'],
                    'category': product.get('category', '')
                })

        # Расчёт скидки по промокоду
        discount = 0
        promo_applies = False
        promo_discount_text = ''

        if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
            applies, error = check_promo_applies(promo_code, cart_items_for_promo, subtotal)
            if applies:
                promo = promocodes[promo_code]
                if promo['type'] == 'percent':
                    discount = subtotal * promo['discount'] / 100
                else:
                    discount = min(promo['discount'], subtotal)
                promo_applies = True
                promo_discount_text = f"{promo['discount']}%" if promo['type'] == 'percent' else f"{promo['discount']} ₽"

        total = subtotal - discount

        # Рекомендуемые товары (на основе товаров в корзине)
        recommended = []
        if items:
            categories_in_cart = set(item['category'] for item in items if item['category'])
            for product in products:
                if product['id'] not in [int(pid) for pid in cart.keys()]:
                    if product.get('category') in categories_in_cart:
                        recommended.append({
                            'id': product['id'],
                            'name': product['name'],
                            'price': get_product_price(product),
                            'image': product.get('image', '')
                        })
                        if len(recommended) >= 4:
                            break

        return jsonify({
            'items': items,
            'subtotal': subtotal,
            'discount': discount,
            'total': total,
            'promo_code': promo_code if promo_applies else None,
            'promo_discount': promo_discount_text,
            'item_count': sum(item['quantity'] for item in items),
            'recommended': recommended
        })
    except Exception as e:
        log_error("Ошибка получения корзины", e)
        return jsonify({'items': [], 'subtotal': 0, 'discount': 0, 'total': 0, 'item_count': 0}), 500

@app.route('/api/apply-promo', methods=['POST'])
def apply_promo_api():
    """Применение промокода"""
    try:
        data = request.json
        promo_code = data.get('promo_code', '').upper().strip()

        if not promo_code:
            return jsonify({'success': False, 'message': 'Введите промокод'}), 400

        if 'user_email' not in session:
            return jsonify({'success': False, 'message': 'Войдите в аккаунт, чтобы использовать промокод'}), 401

        # Проверка на использование промокода
        if is_promocode_used(session['user_email'], promo_code):
            return jsonify({'success': False, 'message': 'Вы уже использовали этот промокод'}), 400

        # Получаем корзину для проверки условий
        cart = session.get('cart', {})
        products = load_products()
        cart_items = []
        subtotal = 0

        for product_id, quantity in cart.items():
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if product:
                price = get_product_price(product)
                subtotal += price * quantity
                cart_items.append({
                    'id': product['id'],
                    'name': product['name'],
                    'category': product.get('category', '')
                })

        # Проверка условий промокода
        applies, error = check_promo_applies(promo_code, cart_items, subtotal)
        if not applies:
            return jsonify({'success': False, 'message': error}), 400

        promocodes = load_promocodes_list()
        if promo_code in promocodes and promocodes[promo_code].get('active', True):
            session['promo_code'] = promo_code
            promo_data = promocodes[promo_code]
            discount_text = f"{promo_data['discount']}%" if promo_data['type'] == 'percent' else f"{promo_data['discount']} ₽"

            app.logger.info(f"Применён промокод {promo_code} для {session['user_email']}")
            return jsonify({'success': True, 'discount_text': discount_text})

        return jsonify({'success': False, 'message': 'Неверный промокод'}), 400
    except Exception as e:
        log_error("Ошибка применения промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/remove-promo', methods=['POST'])
def remove_promo_api():
    """Удаление промокода из корзины"""
    try:
        if 'promo_code' in session:
            del session['promo_code']
        return jsonify({'success': True, 'message': 'Промокод удалён'})
    except Exception as e:
        log_error("Ошибка удаления промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

# ---------- ОФОРМЛЕНИЕ ЗАКАЗА API ----------
@app.route('/api/checkout-card', methods=['POST'])
@login_required
@check_ban
def checkout_card_api():
    """Оформление заказа с оплатой картой онлайн"""
    try:
        data = request.json
        customer_name = data.get('full_name', '').strip()
        customer_email = data.get('email', '').strip()
        customer_phone = data.get('phone', '').strip()
        delivery_address = data.get('delivery_address', '').strip()
        card_last4 = data.get('card_number', '****')[-4:] if data.get('card_number') else '****'

        # Валидация
        if not all([customer_name, customer_email, customer_phone, delivery_address]):
            return jsonify({'message': 'Заполните все обязательные поля'}), 400

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', customer_email):
            return jsonify({'message': 'Неверный формат email'}), 400

        phone_clean = re.sub(r'[\s\(\)-]', '', customer_phone)
        if len(phone_clean) < 10:
            return jsonify({'message': 'Неверный формат телефона'}), 400

        cart = session.get('cart', {})
        if not cart:
            return jsonify({'message': 'Корзина пуста'}), 400

        promo_code = session.get('promo_code')
        products = load_products()
        promocodes = load_promocodes_list()

        # Расчёт доставки
        distance = calculate_distance(delivery_address)
        delivery_date, period_text, delivery_price = calculate_delivery_date(distance)

        # Формирование списка товаров
        items = []
        subtotal = 0
        cart_items_for_promo = []

        for product_id, quantity in cart.items():
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if product:
                price = get_product_price(product)
                item_total = price * quantity
                subtotal += item_total
                items.append({
                    'name': product['name'],
                    'quantity': quantity,
                    'price': price,
                    'total': item_total,
                    'product_id': product['id']
                })
                cart_items_for_promo.append({
                    'id': product['id'],
                    'name': product['name'],
                    'category': product.get('category', '')
                })

        # Расчёт скидки
        discount = 0
        if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
            applies, _ = check_promo_applies(promo_code, cart_items_for_promo, subtotal)
            if applies:
                promo = promocodes[promo_code]
                if promo['type'] == 'percent':
                    discount = subtotal * promo['discount'] / 100
                else:
                    discount = min(promo['discount'], subtotal)

        total = subtotal - discount + delivery_price

        # Генерация номера заказа
        order_number = generate_order_number()

        # Отметка об использовании промокода
        if promo_code and 'user_email' in session:
            mark_promocode_used(session['user_email'], promo_code, order_number)

        # Создание данных заказа
        order_data = {
            'order_number': order_number,
            'datetime': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'items': items,
            'subtotal': subtotal,
            'discount': discount,
            'delivery_price': delivery_price,
            'total': total,
            'delivery_address': delivery_address,
            'from_address': f"{OFFICE_COORDINATES['address']}",
            'distance': distance,
            'delivery_period': period_text,
            'delivery_date': delivery_date,
            'payment_method': 'card',
            'status': 'paid'
        }

        # Сохранение заказа
        save_order_to_history(session['user_email'], order_data)

        # Логирование платежа
        payment_log = {
            'order_number': order_number,
            'customer': customer_name,
            'email': customer_email,
            'amount': total,
            'timestamp': datetime.now().isoformat(),
            'card_last4': card_last4,
            'address': delivery_address,
            'distance': distance,
            'delivery_date': delivery_date
        }

        with open('payments_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"{json.dumps(payment_log, ensure_ascii=False)}\n")

        # Отправка email с чеком
        send_receipt_email(order_data)
        send_order_confirmation(order_data)

        # Очистка корзины
        session.pop('cart', None)
        session.pop('promo_code', None)

        app.logger.info(f"Оплата картой: заказ #{order_number}, сумма {total}, клиент {customer_email}")

        return jsonify({
            'message': f'✅ Заказ #{order_number} оплачен картой онлайн! Сумма {total:,.0f} ₽. Чек отправлен на {customer_email}.',
            'order_number': order_number,
            'total': total
        })
    except Exception as e:
        log_error("Ошибка оформления заказа с картой", e)
        return jsonify({'message': 'Ошибка при оформлении заказа. Попробуйте позже.'}), 500

@app.route('/api/checkout-cash', methods=['POST'])
@login_required
@check_ban
def checkout_cash_api():
    """Оформление заказа с оплатой наличными при получении"""
    try:
        data = request.json
        customer_name = data.get('full_name', '').strip()
        customer_email = data.get('email', '').strip()
        customer_phone = data.get('phone', '').strip()
        delivery_address = data.get('delivery_address', '').strip()

        # Валидация
        if not all([customer_name, customer_email, customer_phone, delivery_address]):
            return jsonify({'message': 'Заполните все обязательные поля'}), 400

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', customer_email):
            return jsonify({'message': 'Неверный формат email'}), 400

        phone_clean = re.sub(r'[\s\(\)-]', '', customer_phone)
        if len(phone_clean) < 10:
            return jsonify({'message': 'Неверный формат телефона'}), 400

        cart = session.get('cart', {})
        if not cart:
            return jsonify({'message': 'Корзина пуста'}), 400

        promo_code = session.get('promo_code')
        products = load_products()
        promocodes = load_promocodes_list()

        # Расчёт доставки
        distance = calculate_distance(delivery_address)
        delivery_date, period_text, delivery_price = calculate_delivery_date(distance)

        # Формирование списка товаров
        items = []
        subtotal = 0
        cart_items_for_promo = []

        for product_id, quantity in cart.items():
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if product:
                price = get_product_price(product)
                item_total = price * quantity
                subtotal += item_total
                items.append({
                    'name': product['name'],
                    'quantity': quantity,
                    'price': price,
                    'total': item_total,
                    'product_id': product['id']
                })
                cart_items_for_promo.append({
                    'id': product['id'],
                    'name': product['name'],
                    'category': product.get('category', '')
                })

        # Расчёт скидки
        discount = 0
        if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
            applies, _ = check_promo_applies(promo_code, cart_items_for_promo, subtotal)
            if applies:
                promo = promocodes[promo_code]
                if promo['type'] == 'percent':
                    discount = subtotal * promo['discount'] / 100
                else:
                    discount = min(promo['discount'], subtotal)

        total = subtotal - discount + delivery_price

        # Генерация номера заказа
        order_number = generate_order_number()

        # Отметка об использовании промокода
        if promo_code and 'user_email' in session:
            mark_promocode_used(session['user_email'], promo_code, order_number)

        # Создание данных заказа
        order_data = {
            'order_number': order_number,
            'datetime': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'items': items,
            'subtotal': subtotal,
            'discount': discount,
            'delivery_price': delivery_price,
            'total': total,
            'delivery_address': delivery_address,
            'from_address': f"{OFFICE_COORDINATES['address']}",
            'distance': distance,
            'delivery_period': period_text,
            'delivery_date': delivery_date,
            'payment_method': 'cash',
            'status': 'pending'
        }

        # Сохранение заказа
        save_order_to_history(session['user_email'], order_data)

        # Логирование заказа
        order_log = {
            'order_number': order_number,
            'customer': customer_name,
            'email': customer_email,
            'amount': total,
            'timestamp': datetime.now().isoformat(),
            'address': delivery_address,
            'distance': distance,
            'delivery_date': delivery_date
        }

        with open('orders_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"{json.dumps(order_log, ensure_ascii=False)}\n")

        # Отправка email подтверждения
        send_order_confirmation(order_data)

        # Очистка корзины
        session.pop('cart', None)
        session.pop('promo_code', None)

        app.logger.info(f"Заказ наличными: #{order_number}, сумма {total}, клиент {customer_email}")

        return jsonify({
            'message': f'✅ Заказ #{order_number} оформлен! Оплата {total:,.0f} ₽ наличными при получении. Подтверждение отправлено на {customer_email}.',
            'order_number': order_number,
            'total': total
        })
    except Exception as e:
        log_error("Ошибка оформления заказа с оплатой при получении", e)
        return jsonify({'message': 'Ошибка при оформлении заказа. Попробуйте позже.'}), 500

# ---------- НОВОСТИ API ----------
@app.route('/api/news', methods=['GET'])
def get_news_api():
    """Получение списка новостей с пагинацией"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 6, type=int)

        news = load_news()
        # Сортировка по дате (новые сверху)
        news.sort(key=lambda x: x.get('date', ''), reverse=True)

        total = len(news)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_news = news[start:end]

        return jsonify({
            'news': paginated_news,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        log_error("Ошибка получения новостей", e)
        return jsonify({'news': [], 'total': 0, 'page': 1, 'per_page': 6, 'total_pages': 0}), 500

@app.route('/api/news/<int:news_id>', methods=['GET'])
def get_news_detail_api(news_id):
    """Получение детальной информации о новости"""
    try:
        news = load_news()
        item = next((n for n in news if n['id'] == news_id), None)

        if item:
            # Увеличиваем счётчик просмотров
            item['views'] = item.get('views', 0) + 1
            save_news(news)
            return jsonify(item)

        return jsonify({'error': 'News not found'}), 404
    except Exception as e:
        log_error(f"Ошибка получения новости {news_id}", e)
        return jsonify({'error': 'Server error'}), 500

# ---------- СТАТИСТИКА API ----------
@app.route('/api/statistics', methods=['GET'])
def get_statistics_api():
    """Получение общей статистики для публичной части"""
    try:
        stats = load_statistics()
        products = load_products()

        # Подсчёт количества товаров со скидкой
        products_on_sale = sum(1 for p in products if p.get('sale_price') and p['sale_price'] < p['price'])

        return jsonify({
            'total_orders': stats.get('total_orders', 0),
            'total_revenue': stats.get('total_revenue', 0),
            'total_users': stats.get('total_users', 0),
            'products_on_sale': products_on_sale,
            'today_orders': stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('orders', 0)
        })
    except Exception as e:
        log_error("Ошибка получения статистики", e)
        return jsonify({'total_orders': 0, 'total_revenue': 0, 'total_users': 0, 'products_on_sale': 0, 'today_orders': 0}), 500# ==================== АДМИН-ПАНЕЛЬ API ====================

@app.route('/api/admin/products', methods=['GET'])
@admin_required
def admin_get_products_api():
    """Получение всех товаров для админ-панели"""
    try:
        products = load_products()
        return jsonify(products)
    except Exception as e:
        log_error("Ошибка получения товаров в админ-панели", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/add-product', methods=['POST'])
@admin_required
def admin_add_product_api():
    """Добавление нового товара"""
    try:
        name = request.form.get('name', '').strip()
        price = request.form.get('price', 0, type=int)
        sale_price = request.form.get('sale_price')
        discount_percent = request.form.get('discount_percent', 0, type=int)
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'services')
        in_stock = request.form.get('in_stock', 'true') == 'true'
        image = request.files.get('image')

        # Валидация
        if not name:
            return jsonify({'success': False, 'message': 'Введите название товара'}), 400
        if price <= 0:
            return jsonify({'success': False, 'message': 'Цена должна быть больше 0'}), 400

        products = load_products()
        new_id = max([p['id'] for p in products], default=0) + 1

        # Обработка изображения
        image_path = '/static/uploads/default_product.jpg'
        if image and image.filename:
            filename = secure_filename(f"product_{new_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)
            image_path = f'/static/uploads/{filename}'

        # Обработка скидки
        sale_price_val = None
        discount_percent_val = discount_percent

        if sale_price and int(sale_price) > 0:
            sale_price_val = int(sale_price)
            if discount_percent_val == 0:
                discount_percent_val = int((1 - sale_price_val / price) * 100)
        elif discount_percent_val > 0:
            sale_price_val = int(price * (1 - discount_percent_val / 100))

        new_product = {
            'id': new_id,
            'name': name,
            'price': price,
            'sale_price': sale_price_val,
            'discount_percent': discount_percent_val,
            'description': description,
            'image': image_path,
            'category': category,
            'in_stock': in_stock,
            'created_at': datetime.now().isoformat(),
            'views': 0,
            'sales_count': 0,
            'rating': 0
        }

        products.append(new_product)
        save_products(products)

        app.logger.info(f"Админ {session['user_email']} добавил товар: {name}")
        return jsonify({'success': True, 'message': 'Товар успешно добавлен', 'product_id': new_id})
    except Exception as e:
        log_error("Ошибка добавления товара", e)
        return jsonify({'success': False, 'message': 'Ошибка при добавлении товара'}), 500

@app.route('/api/admin/edit-product', methods=['POST'])
@admin_required
def admin_edit_product_api():
    """Редактирование товара"""
    try:
        data = request.json
        product_id = data.get('id')
        name = data.get('name', '').strip()
        price = data.get('price', 0)
        sale_price = data.get('sale_price')
        discount_percent = data.get('discount_percent', 0)
        description = data.get('description', '').strip()
        category = data.get('category', 'services')
        in_stock = data.get('in_stock', True)

        if not product_id:
            return jsonify({'success': False, 'message': 'ID товара не указан'}), 400
        if not name:
            return jsonify({'success': False, 'message': 'Введите название товара'}), 400
        if price <= 0:
            return jsonify({'success': False, 'message': 'Цена должна быть больше 0'}), 400

        products = load_products()
        product_found = False

        for p in products:
            if p['id'] == product_id:
                p['name'] = name
                p['price'] = price
                p['sale_price'] = sale_price if sale_price and sale_price > 0 else None
                p['discount_percent'] = discount_percent or 0
                p['description'] = description
                p['category'] = category
                p['in_stock'] = in_stock
                p['updated_at'] = datetime.now().isoformat()
                product_found = True
                break

        if not product_found:
            return jsonify({'success': False, 'message': 'Товар не найден'}), 404

        save_products(products)
        app.logger.info(f"Админ {session['user_email']} отредактировал товар ID: {product_id}")
        return jsonify({'success': True, 'message': 'Товар успешно обновлён'})
    except Exception as e:
        log_error("Ошибка редактирования товара", e)
        return jsonify({'success': False, 'message': 'Ошибка при редактировании товара'}), 500

@app.route('/api/admin/delete-product', methods=['POST'])
@admin_required
def admin_delete_product_api():
    """Удаление товара"""
    try:
        data = request.json
        product_id = data.get('id')

        if not product_id:
            return jsonify({'success': False, 'message': 'ID товара не указан'}), 400

        products = load_products()
        original_count = len(products)
        products = [p for p in products if p['id'] != product_id]

        if len(products) == original_count:
            return jsonify({'success': False, 'message': 'Товар не найден'}), 404

        save_products(products)
        app.logger.info(f"Админ {session['user_email']} удалил товар ID: {product_id}")
        return jsonify({'success': True, 'message': 'Товар успешно удалён'})
    except Exception as e:
        log_error("Ошибка удаления товара", e)
        return jsonify({'success': False, 'message': 'Ошибка при удалении товара'}), 500

@app.route('/api/admin/news', methods=['GET'])
@admin_required
def admin_get_news_api():
    """Получение всех новостей для админ-панели"""
    try:
        news = load_news()
        return jsonify(news)
    except Exception as e:
        log_error("Ошибка получения новостей в админ-панели", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/add-news', methods=['POST'])
@admin_required
def admin_add_news_api():
    """Добавление новой новости"""
    try:
        title = request.form.get('title', '').strip()
        text = request.form.get('text', '').strip()
        fullText = request.form.get('fullText', '').strip()
        image = request.files.get('image')
        video = request.files.get('video')
        video_url = request.form.get('video_url', '').strip()

        if not title:
            return jsonify({'success': False, 'message': 'Введите заголовок новости'}), 400
        if not text:
            return jsonify({'success': False, 'message': 'Введите краткий текст новости'}), 400

        news = load_news()
        new_id = max([n['id'] for n in news], default=0) + 1

        # Обработка изображения
        image_path = '/static/uploads/default_news.jpg'
        if image and image.filename:
            filename = secure_filename(f"news_{new_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)
            image_path = f'/static/uploads/{filename}'

        # Обработка видео
        video_path = None
        video_type = None
        if video and video.filename:
            filename = secure_filename(f"video_{new_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video.filename}")
            filepath = os.path.join(app.config['VIDEO_FOLDER'], filename)
            video.save(filepath)
            video_path = f'/static/videos/{filename}'
            video_type = 'file'
        elif video_url:
            # Проверка на YouTube URL
            youtube_pattern = r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)'
            match = re.search(youtube_pattern, video_url)
            if match:
                video_path = f"https://www.youtube.com/embed/{match.group(1)}"
                video_type = 'youtube'
            else:
                video_path = video_url
                video_type = 'url'

        new_news = {
            'id': new_id,
            'date': datetime.now().strftime('%d.%m.%Y'),
            'title': title,
            'text': text,
            'fullText': fullText,
            'image': image_path,
            'video': video_path,
            'video_type': video_type,
            'views': 0,
            'created_at': datetime.now().isoformat()
        }

        news.append(new_news)
        save_news(news)

        app.logger.info(f"Админ {session['user_email']} добавил новость: {title}")
        return jsonify({'success': True, 'message': 'Новость успешно добавлена', 'news_id': new_id})
    except Exception as e:
        log_error("Ошибка добавления новости", e)
        return jsonify({'success': False, 'message': 'Ошибка при добавлении новости'}), 500

@app.route('/api/admin/edit-news', methods=['POST'])
@admin_required
def admin_edit_news_api():
    """Редактирование новости"""
    try:
        data = request.json
        news_id = data.get('id')
        title = data.get('title', '').strip()
        text = data.get('text', '').strip()
        fullText = data.get('fullText', '').strip()

        if not news_id:
            return jsonify({'success': False, 'message': 'ID новости не указан'}), 400
        if not title:
            return jsonify({'success': False, 'message': 'Введите заголовок новости'}), 400

        news = load_news()
        news_found = False

        for n in news:
            if n['id'] == news_id:
                n['title'] = title
                n['text'] = text
                n['fullText'] = fullText
                n['updated_at'] = datetime.now().isoformat()
                news_found = True
                break

        if not news_found:
            return jsonify({'success': False, 'message': 'Новость не найдена'}), 404

        save_news(news)
        app.logger.info(f"Админ {session['user_email']} отредактировал новость ID: {news_id}")
        return jsonify({'success': True, 'message': 'Новость успешно обновлена'})
    except Exception as e:
        log_error("Ошибка редактирования новости", e)
        return jsonify({'success': False, 'message': 'Ошибка при редактировании новости'}), 500

@app.route('/api/admin/delete-news', methods=['POST'])
@admin_required
def admin_delete_news_api():
    """Удаление новости"""
    try:
        data = request.json
        news_id = data.get('id')

        if not news_id:
            return jsonify({'success': False, 'message': 'ID новости не указан'}), 400

        news = load_news()
        original_count = len(news)
        news = [n for n in news if n['id'] != news_id]

        if len(news) == original_count:
            return jsonify({'success': False, 'message': 'Новость не найдена'}), 404

        save_news(news)
        app.logger.info(f"Админ {session['user_email']} удалил новость ID: {news_id}")
        return jsonify({'success': True, 'message': 'Новость успешно удалена'})
    except Exception as e:
        log_error("Ошибка удаления новости", e)
        return jsonify({'success': False, 'message': 'Ошибка при удалении новости'}), 500

@app.route('/api/admin/promocodes', methods=['GET'])
@admin_required
def admin_get_promocodes_api():
    """Получение всех промокодов для админ-панели"""
    try:
        promocodes = load_promocodes_list()
        return jsonify(promocodes)
    except Exception as e:
        log_error("Ошибка получения промокодов в админ-панели", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/promocodes-all', methods=['GET'])
@admin_required
def admin_get_all_promocodes_api():
    """Получение всех промокодов с дополнительной информацией"""
    try:
        promocodes = load_promocodes_list()
        used = load_used_promocodes()

        result = {}
        for code, data in promocodes.items():
            result[code] = {
                'discount': data['discount'],
                'type': data['type'],
                'active': data.get('active', True),
                'used_count': data.get('used_count', 0),
                'max_uses': data.get('max_uses', float('inf')),
                'conditions': data.get('conditions', {}),
                'created_at': data.get('created_at', ''),
                'users_used': sum(1 for k in used.keys() if k.endswith(f"_{code}"))
            }

        return jsonify(result)
    except Exception as e:
        log_error("Ошибка получения всех промокодов", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/add-promocode', methods=['POST'])
@admin_required
def admin_add_promocode_api():
    """Добавление нового промокода"""
    try:
        data = request.json
        code = data.get('code', '').upper().strip()
        promo_type = data.get('type', 'percent')
        discount = data.get('discount', 0)
        apply_to = data.get('apply_to', 'all')
        categories = data.get('categories', [])
        products = data.get('products', [])
        min_order = data.get('min_order', 0)
        max_uses = data.get('max_uses', 0)

        if not code:
            return jsonify({'success': False, 'message': 'Введите код промокода'}), 400
        if discount <= 0:
            return jsonify({'success': False, 'message': 'Скидка должна быть больше 0'}), 400
        if promo_type == 'percent' and discount > 100:
            return jsonify({'success': False, 'message': 'Процент скидки не может превышать 100%'}), 400

        promocodes = load_promocodes_list()
        if code in promocodes:
            return jsonify({'success': False, 'message': 'Промокод с таким кодом уже существует'}), 409

        promocodes[code] = {
            'discount': discount,
            'type': promo_type,
            'active': True,
            'used_count': 0,
            'max_uses': max_uses if max_uses > 0 else float('inf'),
            'conditions': {
                'apply_to': apply_to,
                'categories': categories,
                'products': products,
                'min_order': min_order
            },
            'created_at': datetime.now().isoformat(),
            'created_by': session['user_email']
        }

        save_promocodes_list(promocodes)
        app.logger.info(f"Админ {session['user_email']} добавил промокод: {code}")
        return jsonify({'success': True, 'message': 'Промокод успешно добавлен'})
    except Exception as e:
        log_error("Ошибка добавления промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка при добавлении промокода'}), 500

@app.route('/api/admin/edit-promocode', methods=['POST'])
@admin_required
def admin_edit_promocode_api():
    """Редактирование промокода"""
    try:
        data = request.json
        code = data.get('code', '').upper().strip()
        discount = data.get('discount')
        promo_type = data.get('type')
        active = data.get('active', True)
        min_order = data.get('min_order', 0)
        max_uses = data.get('max_uses', 0)
        apply_to = data.get('apply_to', 'all')
        categories = data.get('categories', [])
        products = data.get('products', [])

        if not code:
            return jsonify({'success': False, 'message': 'Код промокода не указан'}), 400

        promocodes = load_promocodes_list()
        if code not in promocodes:
            return jsonify({'success': False, 'message': 'Промокод не найден'}), 404

        if discount is not None:
            if discount <= 0:
                return jsonify({'success': False, 'message': 'Скидка должна быть больше 0'}), 400
            if promo_type == 'percent' and discount > 100:
                return jsonify({'success': False, 'message': 'Процент скидки не может превышать 100%'}), 400
            promocodes[code]['discount'] = discount

        if promo_type:
            promocodes[code]['type'] = promo_type

        promocodes[code]['active'] = active
        promocodes[code]['max_uses'] = max_uses if max_uses > 0 else float('inf')
        promocodes[code]['conditions'] = {
            'apply_to': apply_to,
            'categories': categories,
            'products': products,
            'min_order': min_order
        }
        promocodes[code]['updated_at'] = datetime.now().isoformat()

        save_promocodes_list(promocodes)
        app.logger.info(f"Админ {session['user_email']} отредактировал промокод: {code}")
        return jsonify({'success': True, 'message': 'Промокод успешно обновлён'})
    except Exception as e:
        log_error("Ошибка редактирования промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка при редактировании промокода'}), 500

@app.route('/api/admin/toggle-promocode', methods=['POST'])
@admin_required
def admin_toggle_promocode_api():
    """Включение/отключение промокода"""
    try:
        data = request.json
        code = data.get('code', '').upper().strip()

        if not code:
            return jsonify({'success': False, 'message': 'Код промокода не указан'}), 400

        promocodes = load_promocodes_list()
        if code not in promocodes:
            return jsonify({'success': False, 'message': 'Промокод не найден'}), 404

        promocodes[code]['active'] = not promocodes[code].get('active', True)
        save_promocodes_list(promocodes)

        status = 'включён' if promocodes[code]['active'] else 'отключён'
        app.logger.info(f"Админ {session['user_email']} {status} промокод: {code}")
        return jsonify({'success': True, 'message': f'Промокод {code} {status}'})
    except Exception as e:
        log_error("Ошибка переключения промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка при переключении промокода'}), 500

@app.route('/api/admin/delete-promocode', methods=['POST'])
@admin_required
def admin_delete_promocode_api():
    """Удаление промокода"""
    try:
        data = request.json
        code = data.get('code', '').upper().strip()

        if not code:
            return jsonify({'success': False, 'message': 'Код промокода не указан'}), 400

        promocodes = load_promocodes_list()
        if code not in promocodes:
            return jsonify({'success': False, 'message': 'Промокод не найден'}), 404

        del promocodes[code]
        save_promocodes_list(promocodes)

        app.logger.info(f"Админ {session['user_email']} удалил промокод: {code}")
        return jsonify({'success': True, 'message': 'Промокод успешно удалён'})
    except Exception as e:
        log_error("Ошибка удаления промокода", e)
        return jsonify({'success': False, 'message': 'Ошибка при удалении промокода'}), 500

@app.route('/api/admin/delete-review', methods=['POST'])
@admin_required
def admin_delete_review_api():
    """Удаление отзыва"""
    try:
        data = request.json
        index = data.get('index')

        if index is None:
            return jsonify({'success': False, 'message': 'Индекс отзыва не указан'}), 400

        reviews = load_reviews()
        if 0 <= index < len(reviews):
            deleted_review = reviews.pop(index)
            save_reviews(reviews)
            app.logger.info(f"Админ {session['user_email']} удалил отзыв от {deleted_review.get('name')}")
            return jsonify({'success': True, 'message': 'Отзыв успешно удалён'})

        return jsonify({'success': False, 'message': 'Отзыв не найден'}), 404
    except Exception as e:
        log_error("Ошибка удаления отзыва", e)
        return jsonify({'success': False, 'message': 'Ошибка при удалении отзыва'}), 500

@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def admin_get_orders_api():
    """Получение всех заказов для админ-панели"""
    try:
        orders = load_orders()
        return jsonify(orders)
    except Exception as e:
        log_error("Ошибка получения заказов в админ-панели", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/orders/all', methods=['GET'])
@admin_required
def admin_get_all_orders_flat_api():
    """Получение всех заказов в виде плоского списка с фильтрацией"""
    try:
        status = request.args.get('status', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        orders = load_orders()
        flat_orders = []

        for email, user_orders in orders.items():
            for order in user_orders:
                order['user_email'] = email
                flat_orders.append(order)

        # Сортировка по дате (новые сверху)
        flat_orders.sort(key=lambda x: x.get('datetime', ''), reverse=True)

        # Фильтрация по статусу
        if status:
            flat_orders = [o for o in flat_orders if o.get('status') == status]

        # Фильтрация по дате
        if date_from:
            flat_orders = [o for o in flat_orders if o.get('datetime', '')[:10] >= date_from]
        if date_to:
            flat_orders = [o for o in flat_orders if o.get('datetime', '')[:10] <= date_to]

        return jsonify(flat_orders)
    except Exception as e:
        log_error("Ошибка получения всех заказов", e)
        return jsonify([]), 500

@app.route('/api/admin/orders/update-status', methods=['POST'])
@admin_required
def admin_update_order_status_api():
    """Обновление статуса заказа"""
    try:
        data = request.json
        order_number = data.get('order_number')
        new_status = data.get('status')

        if not order_number or not new_status:
            return jsonify({'success': False, 'message': 'Не указаны номер заказа или статус'}), 400

        valid_statuses = ['pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Неверный статус'}), 400

        orders = load_orders()
        order_found = False

        for email, user_orders in orders.items():
            for order in user_orders:
                if order.get('order_number') == order_number:
                    old_status = order.get('status', 'pending')
                    order['status'] = new_status
                    order['status_updated_at'] = datetime.now().isoformat()

                    # Добавляем в историю статусов
                    if 'status_history' not in order:
                        order['status_history'] = []
                    order['status_history'].append({
                        'status': new_status,
                        'date': datetime.now().isoformat(),
                        'changed_by': session['user_email']
                    })

                    save_orders(orders)
                    order_found = True

                    app.logger.info(f"Админ {session['user_email']} изменил статус заказа {order_number} с {old_status} на {new_status}")

                    # Отправка уведомления клиенту
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = EMAIL_CONFIG['email']
                        msg['To'] = email
                        msg['Subject'] = f'Обновление статуса заказа #{order_number} - Zetta'

                        status_names = {
                            'pending': 'Ожидает обработки',
                            'paid': 'Оплачен',
                            'processing': 'В обработке',
                            'shipped': 'Отправлен',
                            'delivered': 'Доставлен',
                            'cancelled': 'Отменён'
                        }

                        html_content = f'''
                        <!DOCTYPE html>
                        <html>
                        <head><meta charset="UTF-8"></head>
                        <body style="font-family: Arial, sans-serif;">
                            <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; padding: 20px; border-radius: 10px; color: white;">
                                <h1 style="color: #27ae60;">Статус заказа #{order_number} обновлён</h1>
                                <p>Новый статус: <strong style="color: #27ae60;">{status_names.get(new_status, new_status)}</strong></p>
                                <p>Вы можете отслеживать статус вашего заказа в личном кабинете.</p>
                                <hr>
                                <p>Спасибо, что выбрали Zetta!</p>
                            </div>
                        </body>
                        </html>
                        '''

                        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
                        server.starttls()
                        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
                        server.send_message(msg)
                        server.quit()
                    except Exception as e:
                        log_error(f"Ошибка отправки уведомления о статусе заказа {order_number}", e)

                    break
            if order_found:
                break

        if not order_found:
            return jsonify({'success': False, 'message': 'Заказ не найден'}), 404

        return jsonify({'success': True, 'message': f'Статус заказа #{order_number} обновлён на "{new_status}"'})
    except Exception as e:
        log_error("Ошибка обновления статуса заказа", e)
        return jsonify({'success': False, 'message': 'Ошибка при обновлении статуса'}), 500

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users_api():
    """Получение всех пользователей для админ-панели"""
    try:
        users = load_users()
        return jsonify(users)
    except Exception as e:
        log_error("Ошибка получения пользователей в админ-панели", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/users/all', methods=['GET'])
@admin_required
def admin_get_all_users_with_stats_api():
    """Получение всех пользователей со статистикой"""
    try:
        users = load_users()
        orders = load_orders()

        result = []
        for email, user_data in users.items():
            user_orders = orders.get(email, [])
            total_spent = sum(o.get('total', 0) for o in user_orders)

            result.append({
                'email': email,
                'full_name': user_data.get('full_name', ''),
                'phone': user_data.get('phone', ''),
                'registered_at': user_data.get('registered_at', ''),
                'last_login': user_data.get('last_login', ''),
                'is_admin': user_data.get('is_admin', False),
                'orders_count': len(user_orders),
                'total_spent': total_spent,
                'bonus_points': user_data.get('bonus_points', 0)
            })

        # Сортировка по дате регистрации
        result.sort(key=lambda x: x.get('registered_at', ''), reverse=True)

        return jsonify(result)
    except Exception as e:
        log_error("Ошибка получения пользователей со статистикой", e)
        return jsonify([]), 500

@app.route('/api/admin/make-admin', methods=['POST'])
@admin_required
def admin_make_admin_api():
    """Назначение пользователя администратором"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Email не указан'}), 400

        if email == session['user_email']:
            return jsonify({'success': False, 'message': 'Нельзя сделать администратором самого себя'}), 400

        users = load_users()
        if email not in users:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

        users[email]['is_admin'] = True
        save_users(users)

        app.logger.info(f"Админ {session['user_email']} назначил администратором {email}")
        return jsonify({'success': True, 'message': f'Пользователь {email} назначен администратором'})
    except Exception as e:
        log_error("Ошибка назначения администратором", e)
        return jsonify({'success': False, 'message': 'Ошибка при назначении администратором'}), 500

@app.route('/api/admin/remove-admin', methods=['POST'])
@admin_required
def admin_remove_admin_api():
    """Снятие прав администратора с пользователя"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Email не указан'}), 400

        if email == session['user_email']:
            return jsonify({'success': False, 'message': 'Нельзя снять права администратора с самого себя'}), 400

        users = load_users()
        if email not in users:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

        if not users[email].get('is_admin', False):
            return jsonify({'success': False, 'message': 'Пользователь не является администратором'}), 400

        users[email]['is_admin'] = False
        save_users(users)

        app.logger.info(f"Админ {session['user_email']} снял права администратора с {email}")
        return jsonify({'success': True, 'message': f'Права администратора сняты с {email}'})
    except Exception as e:
        log_error("Ошибка снятия прав администратора", e)
        return jsonify({'success': False, 'message': 'Ошибка при снятии прав администратора'}), 500

@app.route('/api/admin/ban-user', methods=['POST'])
@admin_required
def admin_ban_user_api():
    """Блокировка пользователя"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        duration_minutes = data.get('duration_minutes')
        reason = data.get('reason', 'Нарушение правил')
        message = data.get('message', 'Обратитесь к администратору для уточнения деталей')

        if not email:
            return jsonify({'success': False, 'message': 'Email не указан'}), 400
        if not duration_minutes or duration_minutes <= 0:
            return jsonify({'success': False, 'message': 'Укажите корректный срок блокировки'}), 400

        if email == session['user_email']:
            return jsonify({'success': False, 'message': 'Нельзя заблокировать самого себя'}), 400

        banned_users = load_banned_users()
        ban_until = datetime.now() + timedelta(minutes=duration_minutes)

        banned_users[email] = {
            'banned_at': datetime.now().isoformat(),
            'ban_until': ban_until.isoformat(),
            'duration_minutes': duration_minutes,
            'reason': reason,
            'message': message,
            'banned_by': session['user_email']
        }

        save_banned_users(banned_users)

        # Отправка уведомления о блокировке
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = email
            msg['Subject'] = 'Ваш аккаунт заблокирован - Zetta'

            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; padding: 20px; border-radius: 10px; color: white;">
                    <h1 style="color: #e74c3c;">Ваш аккаунт заблокирован</h1>
                    <p><strong>Причина:</strong> {reason}</p>
                    <p><strong>Сообщение от администратора:</strong></p>
                    <div style="background: #2a1a1a; padding: 10px; border-radius: 5px;">{message}</div>
                    <p><strong>Блокировка действует до:</strong> {ban_until.strftime('%d.%m.%Y %H:%M:%S')}</p>
                    <hr>
                    <p>По вопросам разблокировки обращайтесь на почту vaincode@mail.ru</p>
                </div>
            </body>
            </html>
            '''

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except Exception as e:
            log_error(f"Ошибка отправки уведомления о блокировке для {email}", e)

        # Очистка сессии если забанен текущий пользователь
        if 'user_email' in session and session['user_email'].lower() == email:
            session.clear()

        app.logger.info(f"Админ {session['user_email']} заблокировал {email} на {duration_minutes} мин. Причина: {reason}")
        return jsonify({'success': True, 'message': f'Пользователь {email} заблокирован до {ban_until.strftime("%d.%m.%Y %H:%M:%S")}'})
    except Exception as e:
        log_error("Ошибка блокировки пользователя", e)
        return jsonify({'success': False, 'message': 'Ошибка при блокировке пользователя'}), 500

@app.route('/api/admin/unban-user', methods=['POST'])
@admin_required
def admin_unban_user_api():
    """Снятие блокировки с пользователя"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Email не указан'}), 400

        banned_users = load_banned_users()
        if email not in banned_users:
            return jsonify({'success': False, 'message': 'Пользователь не заблокирован'}), 400

        del banned_users[email]
        save_banned_users(banned_users)

        # Отправка уведомления о разблокировке
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = email
            msg['Subject'] = 'Ваш аккаунт разблокирован - Zetta'

            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; padding: 20px; border-radius: 10px; color: white;">
                    <h1 style="color: #27ae60;">Ваш аккаунт разблокирован</h1>
                    <p>Вы можете снова пользоваться услугами компании Zetta.</p>
                    <p>Приносим извинения за доставленные неудобства.</p>
                    <hr>
                    <p>С уважением, команда Zetta ⚡</p>
                </div>
            </body>
            </html>
            '''

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except Exception as e:
            log_error(f"Ошибка отправки уведомления о разблокировке для {email}", e)

        app.logger.info(f"Админ {session['user_email']} разблокировал {email}")
        return jsonify({'success': True, 'message': f'Пользователь {email} разблокирован'})
    except Exception as e:
        log_error("Ошибка снятия блокировки", e)
        return jsonify({'success': False, 'message': 'Ошибка при снятии блокировки'}), 500

@app.route('/api/admin/statistics', methods=['GET'])
@admin_required
def admin_get_detailed_statistics_api():
    """Получение детальной статистики для админ-панели"""
    try:
        stats = load_statistics()
        users = load_users()
        orders = load_orders()
        products = load_products()
        reviews = load_reviews()

        # Статистика по пользователям
        total_users = len(users)
        admin_count = sum(1 for u in users.values() if u.get('is_admin', False))

        # Статистика по заказам
        total_orders = stats.get('total_orders', 0)
        total_revenue = stats.get('total_revenue', 0)

        # Статистика за последние 7 дней
        daily_stats = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            day_stats = stats.get('daily_stats', {}).get(date, {'orders': 0, 'revenue': 0})
            daily_stats.append({
                'date': date,
                'orders': day_stats.get('orders', 0),
                'revenue': day_stats.get('revenue', 0)
            })

        # Статистика по категориям товаров
        category_stats = {}
        for product in products:
            cat = product.get('category', 'other')
            if cat not in category_stats:
                category_stats[cat] = {'count': 0, 'revenue': 0}
            category_stats[cat]['count'] += 1

        # Средний рейтинг
        avg_rating = sum(r.get('rating', 0) for r in reviews) / len(reviews) if reviews else 0

        return jsonify({
            'users': {
                'total': total_users,
                'admins': admin_count,
                'new_today': sum(1 for u in users.values() if u.get('registered_at', '').startswith(datetime.now().strftime('%Y-%m-%d'))),
                'active_last_month': sum(1 for u in users.values() if u.get('last_login', '').startswith((datetime.now() - timedelta(days=30)).strftime('%Y-%m')))
            },
            'orders': {
                'total': total_orders,
                'revenue': total_revenue,
                'today': stats.get('daily_stats', {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('orders', 0),
                'pending': sum(1 for o in orders.values() for order in o if order.get('status') == 'pending'),
                'processing': sum(1 for o in orders.values() for order in o if order.get('status') == 'processing'),
                'shipped': sum(1 for o in orders.values() for order in o if order.get('status') == 'shipped'),
                'delivered': sum(1 for o in orders.values() for order in o if order.get('status') == 'delivered'),
                'cancelled': sum(1 for o in orders.values() for order in o if order.get('status') == 'cancelled')
            },
            'products': {
                'total': len(products),
                'on_sale': sum(1 for p in products if p.get('sale_price') and p['sale_price'] < p['price']),
                'out_of_stock': sum(1 for p in products if not p.get('in_stock', True)),
                'top_selling': sorted(products, key=lambda x: x.get('sales_count', 0), reverse=True)[:5]
            },
            'reviews': {
                'total': len(reviews),
                'avg_rating': round(avg_rating, 1),
                'today': sum(1 for r in reviews if r.get('date', '').startswith(datetime.now().strftime('%d.%m.%Y')))
            },
            'daily_stats': daily_stats,
            'category_stats': category_stats
        })
    except Exception as e:
        log_error("Ошибка получения детальной статистики", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/api/admin/backup', methods=['POST'])
@admin_required
def admin_create_backup_api():
    """Создание резервной копии данных"""
    try:
        success = backup_all_data()
        if success:
            return jsonify({'success': True, 'message': 'Резервная копия успешно создана'})
        return jsonify({'success': False, 'message': 'Ошибка при создании резервной копии'}), 500
    except Exception as e:
        log_error("Ошибка создания резервной копии", e)
        return jsonify({'success': False, 'message': 'Ошибка при создании резервной копии'}), 500

@app.route('/api/admin/products-all', methods=['GET'])
@admin_required
def admin_get_products_all_api():
    """Получение всех товаров (включая скрытые) для админ-панели"""
    try:
        products = load_products()
        return jsonify(products)
    except Exception as e:
        log_error("Ошибка получения всех товаров", e)
        return jsonify({'error': 'Ошибка сервера'}), 500

# ---------- ПРОЧИЕ API ----------
@app.route('/api/promocodes', methods=['GET'])
def get_promocodes_api():
    """Получение списка активных промокодов для отображения на сайте"""
    try:
        promocodes = load_promocodes_list()
        # Возвращаем только активные промокоды
        active = {k: v for k, v in promocodes.items() if v.get('active', True)}
        return jsonify(active)
    except Exception as e:
        log_error("Ошибка получения промокодов", e)
        return jsonify({}), 500

@app.route('/api/faq', methods=['GET'])
def get_faq_api():
    """Получение списка часто задаваемых вопросов"""
    try:
        category = request.args.get('category', '')
        faq = load_faq()

        if category:
            faq = [q for q in faq if q.get('category') == category]

        return jsonify(faq)
    except Exception as e:
        log_error("Ошибка получения FAQ", e)
        return jsonify([]), 500

@app.route('/api/partners', methods=['GET'])
def get_partners_api():
    """Получение списка партнёров"""
    try:
        partners = load_partners()
        return jsonify(partners)
    except Exception as e:
        log_error("Ошибка получения партнёров", e)
        return jsonify([]), 500

@app.route('/api/subscribe', methods=['POST'])
def subscribe_api():
    """Подписка на новостную рассылку"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Введите email'}), 400

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return jsonify({'success': False, 'message': 'Неверный формат email'}), 400

        mailing_list = load_data(DATA_FILES['mailing_list'], [])
        if email in mailing_list:
            return jsonify({'success': False, 'message': 'Вы уже подписаны на рассылку'}), 409

        mailing_list.append(email)
        save_data(DATA_FILES['mailing_list'], mailing_list)

        return jsonify({'success': True, 'message': 'Вы успешно подписались на рассылку!'})
    except Exception as e:
        log_error("Ошибка подписки", e)
        return jsonify({'success': False, 'message': 'Ошибка при подписке'}), 500# ==================== ГЛАВНАЯ СТРАНИЦА HTML ====================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=yes">
    <meta name="description" content="Zetta - профессиональная сборка ПК, создание сайтов и IT-услуги в Барнауле. Лучшие цены, гарантия качества, бесплатная доставка.">
    <meta name="keywords" content="сборка пк, создание сайтов, IT услуги, Барнаул, компьютерная помощь">
    <meta name="author" content="Zetta">
    <meta property="og:title" content="Zetta | Профессиональная сборка ПК и IT-услуги">
    <meta property="og:description" content="Профессиональная сборка компьютеров, создание сайтов и IT-услуги в Барнауле">
    <meta property="og:type" content="website">
    <title>Zetta | Профессиональная сборка ПК и IT-услуги</title>
    <link rel="icon" type="image/x-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.5;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* ========== АНИМАЦИИ ========== */
        @keyframes lightningFlash {
            0% { text-shadow: 0 0 0 #27ae60; transform: scale(1); }
            15% { text-shadow: 0 0 3px #27ae60, 0 0 8px #27ae60, 0 0 15px #ffd700; transform: scale(1.08); }
            30% { text-shadow: 0 0 1px #27ae60; transform: scale(1); }
            45% { text-shadow: 0 0 5px #27ae60, 0 0 12px #ffd700, 0 0 20px #ffaa00; transform: scale(1.05); }
            60% { text-shadow: 0 0 2px #27ae60; transform: scale(1); }
            75% { text-shadow: 0 0 4px #27ae60, 0 0 10px #ffd700; transform: scale(1.03); }
            100% { text-shadow: 0 0 0 #27ae60; transform: scale(1); }
        }
        
        @keyframes lightningGlow {
            0%, 100% { filter: drop-shadow(0 0 0 #27ae60); }
            50% { filter: drop-shadow(0 0 10px #ffd700) drop-shadow(0 0 20px #ffaa00); }
        }
        
        .lightning {
            display: inline-block;
            animation: lightningFlash 1.2s infinite ease-in-out;
            cursor: pointer;
        }
        
        .lightning:hover {
            animation: lightningGlow 0.5s infinite;
        }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeInLeft {
            from { opacity: 0; transform: translateX(-30px); }
            to { opacity: 1; transform: translateX(0); }
        }

        @keyframes fadeInRight {
            from { opacity: 0; transform: translateX(30px); }
            to { opacity: 1; transform: translateX(0); }
        }

        @keyframes scaleIn {
            from { opacity: 0; transform: scale(0.9); }
            to { opacity: 1; transform: scale(1); }
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        @keyframes pulseRed {
            0% { transform: scale(1); background: #e74c3c; }
            50% { transform: scale(1.1); background: #ff6b6b; }
            100% { transform: scale(1); background: #e74c3c; }
        }

        @keyframes glowGreen {
            0% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.4); }
            50% { box-shadow: 0 0 20px 10px rgba(39, 174, 96, 0.6); }
            100% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.4); }
        }

        @keyframes glowRed {
            0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.4); }
            50% { box-shadow: 0 0 20px 10px rgba(231, 76, 60, 0.6); }
            100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.4); }
        }

        @keyframes flyToCart {
            0% { transform: scale(1) translate(0, 0); opacity: 1; }
            50% { transform: scale(0.3) translate(100px, -100px); opacity: 0.7; }
            100% { transform: scale(0) translate(300px, -200px); opacity: 0; }
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-5px); }
            75% { transform: translateX(5px); }
        }

        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        @keyframes slideInFromRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Классы анимаций */
        .animate-fly { animation: flyToCart 0.6s ease-in forwards !important; position: fixed !important; z-index: 9999 !important; pointer-events: none !important; }
        .cart-icon-animate { animation: pulse 0.3s ease-in-out; }
        .shake { animation: shake 0.3s ease-in-out; }
        .fade-up { animation: fadeInUp 0.6s ease-out forwards; }
        .fade-left { animation: fadeInLeft 0.6s ease-out forwards; }
        .fade-right { animation: fadeInRight 0.6s ease-out forwards; }
        .scale-in { animation: scaleIn 0.5s ease-out forwards; }
        .spin { animation: spin 1s linear infinite; }
        .bounce { animation: bounce 1s ease-in-out infinite; }
        .slide-in { animation: slideInFromRight 0.3s ease-out; }

        /* ========== МОБИЛЬНАЯ ОПТИМИЗАЦИЯ ========== */
        @media (max-width: 768px) {
            .container { padding: 1rem !important; }
            .products-grid { grid-template-columns: 1fr !important; gap: 1rem !important; }
            .catalog-page-wrapper { flex-direction: column !important; }
            .catalog-sidebar { width: 100% !important; position: static !important; margin-bottom: 1rem; overflow-x: auto; white-space: nowrap; padding: 0.8rem !important; border-radius: 12px !important; }
            .category-list { flex-direction: row !important; gap: 0.5rem !important; display: inline-flex !important; }
            .category-item { display: inline-flex !important; white-space: nowrap; padding: 0.4rem 0.8rem !important; }
            .team-grid { grid-template-columns: 1fr !important; gap: 1rem !important; }
            .team-card.center { transform: scale(1) !important; order: -1; border-color: #27ae60; }
            .contacts-grid { grid-template-columns: 1fr !important; gap: 1rem !important; }
            .hero { padding: 2rem 1rem !important; margin-bottom: 1rem !important; }
            .hero h1 { font-size: 1.6rem !important; }
            .hero p { font-size: 0.9rem !important; }
            .header-content { flex-direction: column !important; gap: 0.5rem !important; padding: 0.8rem !important; }
            .nav-links { flex-wrap: wrap !important; justify-content: center !important; gap: 0.8rem !important; }
            .nav-link { font-size: 0.75rem !important; }
            .search-bar-full { padding: 0.5rem !important; }
            .search-container { flex-direction: column !important; gap: 0.5rem !important; }
            .search-btn-full { width: 100% !important; padding: 0.6rem !important; }
            .search-input-full { padding: 0.6rem !important; font-size: 0.9rem !important; }
            .cart-panel { width: 100% !important; right: -100% !important; }
            .chat-window { width: 92% !important; left: 4% !important; right: 4% !important; bottom: 80px !important; height: 480px !important; }
            .chat-button { width: 50px !important; height: 50px !important; font-size: 22px !important; bottom: 15px !important; right: 15px !important; }
            .home-reviews-grid { grid-template-columns: 1fr !important; }
            .reviews-container .write-review { padding: 1rem !important; }
            .reviews-list { padding: 1rem !important; }
            .footer-content { flex-direction: column !important; text-align: center !important; gap: 0.8rem !important; }
            .footer-section { flex-wrap: wrap !important; justify-content: center !important; gap: 0.8rem !important; }
            .promo-codes { grid-template-columns: repeat(2, 1fr) !important; gap: 0.5rem !important; }
            .carousel-slide { flex-direction: column !important; }
            .carousel-btn { width: 32px !important; height: 32px !important; font-size: 1rem !important; }
            .admin-tabs { flex-wrap: wrap !important; gap: 0.5rem !important; }
            .admin-product-card { flex-direction: column !important; align-items: flex-start !important; }
            .admin-user-card { flex-direction: column !important; align-items: flex-start !important; }
            .admin-user-actions { flex-wrap: wrap !important; margin-top: 0.5rem; }
            .admin-user-actions select, .admin-user-actions input { font-size: 0.8rem; padding: 0.3rem; width: auto !important; }
            .modal-content { width: 95% !important; margin: 10% auto !important; padding: 1rem !important; }
            .order-card { padding: 1rem !important; }
            .profile-container { padding: 0 !important; }
            .team-avatar { width: 100px !important; height: 100px !important; }
            .team-name { font-size: 1rem !important; }
            .contact-title { font-size: 0.85rem !important; }
            .contact-value { font-size: 0.8rem !important; }
            .news-card-title { font-size: 0.9rem !important; }
            .news-card-text { font-size: 0.8rem !important; }
            .promo-code { font-size: 0.9rem !important; }
            .vlog-text { font-size: 0.9rem !important; padding: 1rem !important; }
            .cart-item { flex-wrap: wrap !important; gap: 0.5rem !important; }
            .payment-methods { flex-direction: column !important; gap: 0.5rem !important; }
            .payment-option { padding: 0.8rem !important; }
            .card-fields input { font-size: 0.9rem !important; }
            .admin-form input, .admin-form textarea, .admin-form select { font-size: 0.9rem !important; }
            .admin-table { font-size: 0.75rem !important; }
            .admin-table th, .admin-table td { padding: 0.3rem !important; }
            .admin-products-grid .admin-product-card { padding: 0.8rem !important; }
            .order-summary { padding: 0.8rem !important; }
            .order-summary h3 { font-size: 0.9rem !important; }
            .delivery-info { font-size: 0.75rem !important; }
            .form-label { font-size: 0.75rem !important; }
            .form-input { padding: 0.5rem !important; font-size: 0.85rem !important; }
            .submit-btn { padding: 0.6rem !important; font-size: 0.85rem !important; }
            .chat-message { font-size: 0.8rem !important; padding: 0.4rem 0.8rem !important; }
            .chat-question-btn { font-size: 0.8rem !important; padding: 0.5rem !important; }
            .verify-code-input { font-size: 1.2rem !important; padding: 0.6rem !important; }
            .auth-container { padding: 1.2rem !important; }
            .auth-tab { font-size: 0.9rem !important; padding: 0.4rem 0.8rem !important; }
            .auth-input { padding: 0.6rem !important; font-size: 0.9rem !important; }
            .auth-btn { padding: 0.6rem !important; font-size: 0.9rem !important; }
            .star { font-size: 1.5rem !important; }
            .review-name-input, .review-input { font-size: 0.85rem !important; padding: 0.6rem !important; }
            .submit-review-btn { padding: 0.6rem !important; font-size: 0.85rem !important; }
            .product-title { font-size: 0.85rem !important; }
            .product-price { font-size: 0.9rem !important; }
            .add-to-cart { font-size: 0.7rem !important; padding: 0.4rem !important; }
            .discount-badge { font-size: 10px !important; padding: 3px 6px !important; }
            .admin-add-btn { width: 30px !important; height: 30px !important; font-size: 1.1rem !important; }
            .dot { width: 6px !important; height: 6px !important; }
            .dot.active { width: 16px !important; }
        }

        @media (max-width: 480px) {
            .container { padding: 0.8rem !important; }
            .hero h1 { font-size: 1.3rem !important; }
            .logo-text { font-size: 1.2rem !important; }
            .logo-icon { font-size: 1.4rem !important; }
            .nav-link { font-size: 0.7rem !important; }
            .promo-code { font-size: 0.8rem !important; }
            .promo-discount { font-size: 0.65rem !important; }
            .contact-icon { font-size: 1.5rem !important; }
            .map-placeholder { padding: 1rem !important; }
            .review-author { font-size: 0.85rem !important; }
            .review-text { font-size: 0.8rem !important; }
            .order-number { font-size: 0.8rem !important; }
            .order-total { font-size: 0.9rem !important; }
            .profile-label { font-size: 0.7rem !important; }
            .profile-value { font-size: 0.85rem !important; }
            .vlog-edit-btn { font-size: 0.7rem !important; padding: 0.3rem 0.6rem !important; }
        }

        /* ========== ОСНОВНЫЕ СТИЛИ ========== */
        .team-title, .reviews-title, .promo-title {
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 1.5rem;
            text-align: center;
            color: #e0e0e0;
            position: relative;
        }

        .team-title::after, .reviews-title::after, .promo-title::after {
            content: '';
            position: absolute;
            bottom: -8px;
            left: 50%;
            transform: translateX(-50%);
            width: 50px;
            height: 2px;
            background: #27ae60;
            border-radius: 2px;
        }

        /* ========== ШАПКА САЙТА ========== */
        .header {
            background: #0a0a0a;
            border-bottom: 1px solid #2a2a2a;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
            background: rgba(10, 10, 10, 0.95);
        }

        .header-content {
            max-width: 1280px;
            margin: 0 auto;
            padding: 0.8rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.8rem;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .logo:hover {
            opacity: 0.9;
            transform: scale(1.02);
        }

        .logo-icon {
            font-size: 1.8rem;
            font-weight: 300;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: 2px;
            background: linear-gradient(135deg, #fff, #27ae60, #fff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            background-size: 200% auto;
            animation: shimmer 3s infinite linear;
        }

        .nav-links {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            flex-wrap: wrap;
        }

        .nav-link {
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            padding: 0.3rem 0;
        }

        .nav-link::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 0;
            height: 2px;
            background: #27ae60;
            transition: width 0.3s ease;
        }

        .nav-link:hover::after {
            width: 100%;
        }

        .nav-link:hover {
            color: #27ae60;
        }

        .nav-link.active {
            color: #27ae60;
        }

        .nav-link.active::after {
            width: 100%;
        }

        .user-icon {
            position: relative;
            cursor: pointer;
            font-size: 1.1rem;
            padding: 0.4rem 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            transition: all 0.3s ease;
            border-radius: 20px;
            background: #1a1a1a;
        }

        .user-icon:hover {
            background: #27ae60;
            color: white;
            transform: translateY(-2px);
        }

        .user-name {
            font-size: 0.85rem;
        }

        .cart-icon {
            position: relative;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0.4rem 0.8rem;
            transition: all 0.3s ease;
            border-radius: 20px;
            background: #1a1a1a;
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }

        .cart-icon:hover {
            background: #27ae60;
            transform: translateY(-2px);
        }

        .cart-count {
            position: absolute;
            top: -5px;
            right: -5px;
            background: #e74c3c;
            color: white;
            font-size: 0.65rem;
            padding: 0.15rem 0.4rem;
            border-radius: 10px;
            font-weight: bold;
            min-width: 18px;
            text-align: center;
        }

        /* ========== ПОИСК ========== */
        .search-bar-full {
            background: #0f0f0f;
            border-top: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a;
            padding: 0.5rem 2rem;
        }

        .search-container {
            max-width: 1280px;
            margin: 0 auto;
            display: flex;
            gap: 0.5rem;
        }

        .search-input-full {
            flex: 1;
            padding: 0.7rem 1.2rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 0.95rem;
            border-radius: 25px;
            transition: all 0.3s ease;
        }

        .search-input-full:focus {
            outline: none;
            border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .search-input-full::placeholder {
            color: #666;
        }

        .search-btn-full {
            padding: 0.7rem 1.5rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
            border-radius: 25px;
            transition: all 0.3s ease;
            font-weight: 500;
        }

        .search-btn-full:hover {
            background: #229954;
            transform: scale(1.02);
        }

        /* ========== ОСНОВНОЙ КОНТЕЙНЕР ========== */
        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 2rem;
            flex: 1;
        }

        /* ========== КАТАЛОГ ========== */
        .catalog-page-wrapper {
            display: flex;
            gap: 2rem;
        }

        .catalog-sidebar {
            width: 260px;
            flex-shrink: 0;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 1.5rem;
            height: fit-content;
            position: sticky;
            top: 90px;
        }

        .catalog-sidebar h3 {
            color: #27ae60;
            font-size: 0.9rem;
            margin-bottom: 1.2rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .category-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .category-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.6rem 0.8rem;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 10px;
            color: #888;
        }

        .category-item:hover {
            background: #1a1a1a;
            color: #27ae60;
            transform: translateX(5px);
        }

        .category-item.active {
            background: #1a2a1a;
            color: #27ae60;
            border-left: 3px solid #27ae60;
        }

        .category-icon {
            font-size: 1.1rem;
        }

        .category-name {
            font-size: 0.85rem;
        }

        .main-content {
            flex: 1;
            min-width: 0;
        }

        .page-header {
            margin-bottom: 1.5rem;
            padding-bottom: 0.8rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .page-header h1 {
            font-size: 1.3rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* ========== ТОВАРЫ ========== */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
        }

        .product-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            border-radius: 16px;
        }

        .product-card:hover {
            border-color: #27ae60;
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }

        .product-card.super-sale {
            border: 2px solid #e74c3c;
            background: linear-gradient(135deg, #0f0f0f 0%, #1a0a0a 100%);
            position: relative;
            overflow: hidden;
        }

        .product-card.super-sale::before {
            content: "🔥 SALE 🔥";
            position: absolute;
            top: 10px;
            right: -30px;
            background: #e74c3c;
            color: white;
            padding: 4px 30px;
            transform: rotate(45deg);
            font-size: 10px;
            font-weight: bold;
            z-index: 1;
            background: linear-gradient(90deg, #e74c3c, #ff6b6b, #e74c3c);
            background-size: 200% auto;
            animation: shimmer 2s infinite linear;
        }

        .discount-badge {
            position: absolute;
            top: 10px;
            left: 10px;
            background: #e74c3c;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: bold;
            z-index: 2;
            animation: pulse 1s infinite;
        }

        .product-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            transition: transform 0.3s ease;
        }

        .product-card:hover .product-image {
            transform: scale(1.05);
        }

        .product-info {
            padding: 1rem;
        }

        .product-title {
            font-size: 0.9rem;
            font-weight: 500;
            line-height: 1.3;
            margin-bottom: 0.5rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .product-price {
            font-size: 1rem;
            font-weight: 600;
            margin: 0.5rem 0;
        }

        .product-price.super-price {
            color: #e74c3c;
            font-size: 1.2rem;
        }

        .old-price {
            text-decoration: line-through;
            color: #666;
            font-size: 0.8rem;
            margin-left: 0.5rem;
            font-weight: normal;
        }

        .sale-price {
            color: #e74c3c;
            font-weight: bold;
        }

        .add-to-cart {
            width: 100%;
            padding: 0.5rem;
            background: transparent;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
            cursor: pointer;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            border-radius: 25px;
        }

        .add-to-cart:hover {
            background: #27ae60;
            border-color: #27ae60;
            transform: scale(1.02);
        }

        /* ========== ГЕРОЙ СЕКЦИЯ ========== */
        .hero {
            padding: 3rem 2rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 2rem;
            text-align: center;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a2a1a 100%);
            border-radius: 20px;
        }

        .hero h1 {
            font-size: 2.2rem;
            font-weight: 500;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #fff, #27ae60);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .hero p {
            color: #888;
            font-size: 1rem;
        }

        /* ========== КОМАНДА ========== */
        .team-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 20px;
        }

        .team-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 2rem;
            text-align: center;
        }

        .team-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            transition: all 0.3s ease;
            border-radius: 16px;
        }

        .team-card:hover {
            transform: translateY(-5px);
            border-color: #27ae60;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        }

        .team-card.center {
            transform: scale(1.02);
            border-color: #27ae60;
            background: linear-gradient(135deg, #1a1a1a, #1a2a1a);
        }

        .team-avatar {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            margin: 0 auto 1rem;
            background-size: cover;
            background-position: center;
            border: 3px solid #2a2a2a;
            transition: all 0.3s ease;
        }

        .team-card:hover .team-avatar {
            transform: scale(1.05);
            border-color: #27ae60;
        }

        .team-name {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            color: #e0e0e0;
        }

        .team-position {
            font-size: 0.8rem;
            color: #27ae60;
            margin-bottom: 0.75rem;
        }

        .team-description {
            font-size: 0.8rem;
            color: #888;
            line-height: 1.4;
        }        /* ========== НОВОСТИ КАРУСЕЛЬ ========== */
        .news-carousel-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            position: relative;
            border-radius: 20px;
        }

        .admin-add-btn {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: #27ae60;
            color: white;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.3rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            z-index: 5;
        }

        .admin-add-btn:hover {
            transform: scale(1.1);
            background: #229954;
        }

        .carousel-container {
            position: relative;
            max-width: 100%;
            overflow: hidden;
        }

        .carousel-slides {
            display: flex;
            transition: transform 0.5s ease;
        }

        .carousel-slide {
            min-width: 100%;
            display: flex;
            gap: 1.5rem;
            padding: 0.5rem;
        }

        .news-card {
            flex: 1;
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        }

        .news-card:hover {
            transform: translateY(-5px);
            border-color: #27ae60;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }

        .news-card-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            transition: transform 0.3s ease;
        }

        .news-card-video {
            width: 100%;
            height: 200px;
            object-fit: cover;
            background: #000;
        }

        .news-card:hover .news-card-image {
            transform: scale(1.05);
        }

        .news-card-content {
            padding: 1rem;
        }

        .news-card-date {
            font-size: 0.7rem;
            color: #27ae60;
            margin-bottom: 0.5rem;
        }

        .news-card-title {
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #e0e0e0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .news-card-text {
            font-size: 0.8rem;
            color: #888;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .carousel-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2rem;
            z-index: 10;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .carousel-btn:hover {
            background: #27ae60;
            transform: translateY(-50%) scale(1.1);
        }

        .carousel-btn.prev {
            left: 10px;
        }

        .carousel-btn.next {
            right: 10px;
        }

        .carousel-dots {
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 1rem;
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #3a3a3a;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .dot:hover {
            background: #27ae60;
            transform: scale(1.2);
        }

        .dot.active {
            background: #27ae60;
            width: 20px;
            border-radius: 4px;
        }

        /* ========== ВЛОГ ========== */
        .vlog-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 20px;
        }

        .vlog-content {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .vlog-text {
            background: #1a1a1a;
            padding: 1.5rem;
            border-radius: 16px;
            line-height: 1.6;
            color: #bbb;
            font-size: 0.95rem;
            border-left: 3px solid #27ae60;
            white-space: pre-wrap;
        }

        .vlog-edit-btn {
            align-self: flex-end;
            padding: 0.5rem 1rem;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.8rem;
        }

        .vlog-edit-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        /* ========== ОТЗЫВЫ ========== */
        .reviews-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 20px;
        }

        .home-reviews-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }

        .home-review-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 1rem;
            transition: all 0.3s ease;
            border-radius: 12px;
        }

        .home-review-card:hover {
            border-color: #27ae60;
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }

        .home-review-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .home-review-author {
            font-weight: 600;
            color: #27ae60;
            font-size: 0.85rem;
        }

        .home-review-date {
            font-size: 0.7rem;
            color: #666;
        }

        .home-review-stars {
            display: flex;
            gap: 0.2rem;
            margin-bottom: 0.75rem;
        }

        .home-review-stars .star-static {
            font-size: 0.85rem;
            color: #555;
        }

        .home-review-stars .star-static.active {
            color: #ffc107;
        }

        .home-review-text {
            color: #bbb;
            font-size: 0.8rem;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        /* ========== ПРОМОКОДЫ ========== */
        .promo-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 20px;
        }

        .promo-codes {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.75rem;
        }

        .promo-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 0.75rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 12px;
        }

        .promo-card:hover {
            border-color: #27ae60;
            transform: translateY(-2px);
            animation: glowGreen 0.5s ease;
        }

        .promo-code {
            font-family: monospace;
            font-size: 0.9rem;
            font-weight: 600;
            letter-spacing: 1px;
            color: #27ae60;
        }

        .promo-discount {
            font-size: 0.75rem;
            color: #e74c3c;
            margin-top: 0.25rem;
        }

        /* ========== КОНТАКТЫ ========== */
        .contacts-page {
            max-width: 100%;
            margin: 0 auto;
        }

        .contacts-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .contact-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
            border-radius: 16px;
        }

        .contact-card:hover {
            border-color: #27ae60;
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }

        .contact-icon {
            font-size: 2rem;
            margin-bottom: 0.8rem;
            transition: all 0.3s ease;
        }

        .contact-card:hover .contact-icon {
            transform: scale(1.1);
        }

        .contact-title {
            font-size: 0.85rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.8rem;
            color: #27ae60;
        }

        .contact-value {
            color: #e0e0e0;
            line-height: 1.5;
            font-size: 0.85rem;
        }

        .map-placeholder {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            text-align: center;
            border-radius: 16px;
            transition: all 0.3s ease;
        }

        .map-placeholder:hover {
            border-color: #27ae60;
        }

        /* ========== СТРАНИЦА ОТЗЫВОВ ========== */
        .reviews-container {
            width: 100%;
            margin: 0;
            padding: 0;
        }

        .write-review {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            width: 100%;
            border-radius: 16px;
            transition: all 0.3s ease;
        }

        .write-review:hover {
            border-color: #27ae60;
        }

        .write-review h3 {
            font-size: 1.1rem;
            margin-bottom: 1rem;
            color: #27ae60;
        }

        .stars-rating {
            display: flex;
            gap: 0.5rem;
            margin: 1rem 0;
            justify-content: center;
        }

        .star {
            font-size: 2rem;
            cursor: pointer;
            color: #555;
            transition: all 0.2s;
        }

        .star.active {
            color: #ffc107;
        }

        .star:hover {
            color: #ffc107;
            transform: scale(1.1);
        }

        .review-name-input {
            width: 100%;
            padding: 0.8rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 0.9rem;
            margin-bottom: 1rem;
            border-radius: 10px;
            transition: all 0.3s ease;
        }

        .review-name-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .review-input {
            width: 100%;
            padding: 0.8rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 0.9rem;
            resize: vertical;
            font-family: inherit;
            border-radius: 10px;
            min-height: 100px;
            transition: all 0.3s ease;
        }

        .review-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .submit-review-btn {
            padding: 0.8rem 1.5rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
            margin-top: 1rem;
            border-radius: 25px;
            width: 100%;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .submit-review-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .reviews-list {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            width: 100%;
            border-radius: 16px;
        }

        .review-item {
            padding: 1rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 0.8rem;
            background: #1a1a1a;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .review-item:hover {
            transform: translateX(5px);
            border-left: 3px solid #27ae60;
        }

        .review-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }

        .review-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .review-author {
            font-weight: 600;
            color: #27ae60;
            font-size: 0.9rem;
        }

        .review-date {
            font-size: 0.7rem;
            color: #666;
        }

        .review-stars {
            display: flex;
            gap: 0.2rem;
            margin-bottom: 0.75rem;
        }

        .review-stars .star-static {
            font-size: 1rem;
            color: #555;
        }

        .review-stars .star-static.active {
            color: #ffc107;
        }

        .review-text {
            color: #bbb;
            line-height: 1.5;
            font-size: 0.85rem;
        }

        .review-actions {
            display: flex;
            gap: 0.5rem;
        }

        .delete-review {
            background: #e74c3c;
            color: white;
            border: none;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .delete-review:hover {
            background: #c0392b;
            transform: scale(1.05);
        }

        /* ========== ПРОФИЛЬ ========== */
        .profile-container {
            max-width: 1000px;
            margin: 0 auto;
        }

        .profile-info {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 16px;
            transition: all 0.3s ease;
        }

        .profile-info:hover {
            border-color: #27ae60;
        }

        .profile-field {
            margin-bottom: 0.8rem;
            padding-bottom: 0.8rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .profile-label {
            color: #888;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .profile-value {
            font-size: 1rem;
            margin-top: 0.2rem;
            color: #e0e0e0;
        }

        .profile-edit-btn, .logout-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid #27ae60;
            color: #27ae60;
            cursor: pointer;
            margin-top: 0.8rem;
            transition: all 0.3s ease;
            border-radius: 25px;
            font-size: 0.8rem;
        }

        .profile-edit-btn:hover, .logout-btn:hover {
            transform: scale(1.02);
            background: #27ae60;
            color: white;
        }

        .logout-btn {
            border-color: #e74c3c;
            color: #e74c3c;
            margin-left: 0.5rem;
        }

        .logout-btn:hover {
            background: #e74c3c;
            color: white;
        }

        .orders-list {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            border-radius: 16px;
        }

        .order-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 1rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
            border-radius: 12px;
        }

        .order-card:hover {
            border-color: #27ae60;
            transform: translateX(5px);
        }

        .order-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.8rem;
            flex-wrap: wrap;
            gap: 0.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .order-number {
            font-weight: bold;
            color: #27ae60;
            font-size: 0.9rem;
        }

        .order-status {
            background: #27ae60;
            padding: 0.2rem 0.5rem;
            font-size: 0.7rem;
            border-radius: 4px;
            color: white;
        }

        .order-status.pending { background: #f39c12; }
        .order-status.processing { background: #3498db; }
        .order-status.shipped { background: #9b59b6; }
        .order-status.delivered { background: #27ae60; }
        .order-status.cancelled { background: #e74c3c; }

        .order-date {
            color: #888;
            font-size: 0.7rem;
        }

        .order-items {
            margin: 0.8rem 0;
        }

        .order-item {
            display: flex;
            justify-content: space-between;
            padding: 0.3rem 0;
            border-bottom: 1px solid #2a2a2a;
            font-size: 0.8rem;
        }

        .order-total {
            text-align: right;
            margin-top: 0.8rem;
            padding-top: 0.5rem;
            font-size: 1rem;
            font-weight: bold;
        }

        /* ========== ОФОРМЛЕНИЕ ЗАКАЗА ========== */
        .checkout-page {
            max-width: 800px;
            margin: 0 auto;
        }

        .checkout-form {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            border-radius: 16px;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-label {
            display: block;
            margin-bottom: 0.3rem;
            font-size: 0.8rem;
            color: #888;
        }

        .form-input {
            width: 100%;
            padding: 0.7rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 0.9rem;
            transition: all 0.3s ease;
            border-radius: 10px;
        }

        .form-input:focus {
            outline: none;
            border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .payment-methods {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
        }

        .payment-option {
            flex: 1;
            padding: 0.8rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s ease;
            border-radius: 10px;
            font-size: 0.9rem;
        }

        .payment-option:hover {
            transform: scale(1.02);
            border-color: #27ae60;
        }

        .payment-option.selected {
            border-color: #27ae60;
            background: #1a2a1a;
        }

        .card-fields {
            margin-top: 1rem;
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            animation: fadeInUp 0.3s ease-out;
        }

        .delivery-info {
            background: #1a1a1a;
            padding: 0.8rem;
            margin: 0.8rem 0;
            border-left: 3px solid #27ae60;
            border-radius: 8px;
            font-size: 0.8rem;
        }

        .order-summary {
            background: #1a1a1a;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 12px;
        }

        .order-summary h3 {
            font-size: 1rem;
            margin-bottom: 0.8rem;
            color: #27ae60;
        }

        .submit-btn {
            width: 100%;
            padding: 0.8rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 1rem;
            transition: all 0.3s ease;
            border-radius: 25px;
            font-weight: 600;
        }

        .submit-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .submit-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        /* ========== ФУТЕР ========== */
        .footer {
            background: #0a0a0a;
            border-top: 1px solid #2a2a2a;
            margin-top: 3rem;
            padding: 1rem 2rem;
        }

        .footer-content {
            max-width: 1280px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .footer-section {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            flex-wrap: wrap;
        }

        .footer-section a, .footer-section span {
            color: #888;
            text-decoration: none;
            transition: color 0.2s;
            font-size: 0.8rem;
        }

        .footer-section a:hover {
            color: #27ae60;
        }

        /* ========== ЧАТ ========== */
        .chat-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 55px;
            height: 55px;
            border-radius: 50%;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 24px;
            z-index: 10000;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .chat-button:hover {
            transform: scale(1.1);
            background: #229954;
            animation: glowGreen 1s infinite;
        }

        .chat-window {
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 380px;
            height: 500px;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            display: none;
            flex-direction: column;
            z-index: 10001;
            box-shadow: 0 5px 25px rgba(0, 0, 0, 0.5);
            overflow: hidden;
            animation: scaleIn 0.3s ease-out;
        }

        .chat-window.open {
            display: flex;
        }

        .chat-header {
            padding: 0.8rem 1rem;
            background: #1a1a1a;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        .chat-header h3 {
            color: #27ae60;
            font-size: 0.9rem;
            margin: 0;
        }

        .close-chat {
            cursor: pointer;
            font-size: 1.2rem;
            color: #888;
            transition: all 0.2s;
        }

        .close-chat:hover {
            color: #e74c3c;
            transform: scale(1.1);
        }

        .chat-messages-area {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            min-height: 0;
        }

        .chat-message {
            max-width: 85%;
            padding: 0.5rem 0.8rem;
            border-radius: 12px;
            word-wrap: break-word;
            line-height: 1.4;
            font-size: 0.85rem;
            animation: fadeInUp 0.3s ease;
        }

        .chat-message.user {
            background: #27ae60;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }

        .chat-message.admin {
            background: #e74c3c;
            color: white;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }

        .chat-message.system {
            background: #c0392b;
            color: white;
            align-self: center;
            font-size: 0.7rem;
            text-align: center;
            border-radius: 15px;
            max-width: 90%;
        }

        .chat-buttons {
            padding: 0.8rem;
            border-top: 1px solid #2a2a2a;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            background: #0f0f0f;
            flex-shrink: 0;
        }

        .chat-question-btn {
            padding: 0.6rem;
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 25px;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s ease;
            font-size: 0.8rem;
        }

        .chat-question-btn:hover {
            background: #27ae60;
            border-color: #27ae60;
            transform: translateY(-2px);
        }

        /* ========== МОДАЛЬНЫЕ ОКНА ========== */
        .hidden {
            display: none;
        }

        .modal, .auth-modal, .verify-modal, .reset-modal, .profile-form-modal, .feedback-modal, .news-modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
        }

        .modal-content, .auth-container, .verify-container, .reset-container, .profile-form-container, .feedback-container, .news-modal-content {
            background: #0f0f0f;
            margin: 5% auto;
            width: 90%;
            max-width: 500px;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            animation: scaleIn 0.4s ease-out;
        }

        .news-modal-content {
            max-width: 800px;
            padding: 0;
        }

        .news-modal-header {
            padding: 1rem;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .news-modal-header h2 {
            font-size: 1.1rem;
            color: #e0e0e0;
        }

        .news-modal-body {
            padding: 1rem;
        }

        .news-modal-image {
            width: 100%;
            max-height: 300px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .news-modal-date {
            color: #27ae60;
            font-size: 0.8rem;
            margin-bottom: 1rem;
        }

        .news-modal-fulltext {
            color: #bbb;
            line-height: 1.6;
            font-size: 0.9rem;
        }

        .close-news-modal, .close {
            font-size: 1.3rem;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
        }

        .close-news-modal:hover, .close:hover {
            color: #fff;
            transform: scale(1.1);
        }

        .verify-code-input {
            width: 100%;
            padding: 0.8rem;
            font-size: 1.3rem;
            text-align: center;
            letter-spacing: 5px;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            margin: 1rem 0;
            font-family: monospace;
            border-radius: 10px;
        }

        .verify-timer {
            color: #27ae60;
            font-size: 0.8rem;
            margin-bottom: 1rem;
            text-align: center;
        }

        .resend-code-btn {
            background: transparent;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            padding: 0.5rem 1rem;
            cursor: pointer;
            margin-top: 0.5rem;
            border-radius: 25px;
            width: 100%;
            transition: all 0.3s ease;
        }

        .resend-code-btn:hover {
            border-color: #27ae60;
            color: #27ae60;
            transform: scale(1.02);
        }

        .forgot-password {
            text-align: right;
            margin-top: -0.3rem;
            margin-bottom: 0.5rem;
        }

        .forgot-password a {
            color: #27ae60;
            font-size: 0.75rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
        }

        .forgot-password a:hover {
            text-decoration: underline;
        }        /* ========== АДМИН-ПАНЕЛЬ ========== */
        .admin-panel {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 16px;
        }

        .admin-tabs {
            display: flex;
            gap: 0.8rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        .admin-tab {
            padding: 0.5rem 1rem;
            cursor: pointer;
            color: #888;
            transition: all 0.3s ease;
            border-radius: 25px;
            font-size: 0.85rem;
        }

        .admin-tab:hover {
            color: #27ae60;
            background: #1a1a1a;
        }

        .admin-tab.active {
            color: #27ae60;
            background: #1a2a1a;
        }

        .admin-section {
            display: none;
            animation: fadeInUp 0.4s ease-out;
        }

        .admin-section.active {
            display: block;
        }

        .admin-form {
            background: #1a1a1a;
            padding: 1.2rem;
            margin-bottom: 1.5rem;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .admin-form:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
        }

        .admin-form h3 {
            color: #27ae60;
            margin-bottom: 1rem;
            font-size: 1rem;
        }

        .admin-form input, .admin-form textarea, .admin-form select {
            width: 100%;
            padding: 0.6rem;
            margin-bottom: 0.8rem;
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .admin-form input:focus, .admin-form textarea:focus, .admin-form select:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .admin-form button {
            padding: 0.6rem 1.2rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 25px;
            transition: all 0.3s ease;
            font-size: 0.85rem;
        }

        .admin-form button:hover {
            background: #229954;
            transform: scale(1.02);
        }

        /* Админ таблицы и карточки */
        .admin-products-grid, .admin-news-list, .admin-promocodes-list, .admin-users-list {
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }

        .admin-product-card, .admin-news-card, .admin-user-card, .admin-promocode-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            padding: 0.8rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.8rem;
            transition: all 0.3s ease;
        }

        .admin-product-card:hover, .admin-news-card:hover, .admin-user-card:hover, .admin-promocode-card:hover {
            transform: translateX(5px);
            border-color: #27ae60;
        }

        .admin-product-name, .admin-news-title, .admin-user-email, .admin-promocode-code {
            font-weight: bold;
            font-size: 0.9rem;
            color: #27ae60;
        }

        .admin-product-price, .admin-news-date, .admin-user-details, .admin-promocode-details {
            font-size: 0.75rem;
            color: #888;
            margin-top: 0.2rem;
        }

        .admin-product-actions, .admin-news-actions, .admin-user-actions, .admin-promocode-actions {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        /* Кнопки действий */
        .delete-btn, .edit-btn, .toggle-btn, .ban-btn, .unban-btn {
            padding: 0.25rem 0.5rem;
            cursor: pointer;
            border: none;
            margin: 0 0.2rem;
            border-radius: 6px;
            transition: all 0.3s ease;
            font-size: 0.75rem;
        }

        .delete-btn:hover, .edit-btn:hover, .toggle-btn:hover, .ban-btn:hover, .unban-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .delete-btn { background: #e74c3c; color: white; }
        .edit-btn { background: #27ae60; color: white; }
        .toggle-btn { background: #f39c12; color: white; }
        .ban-btn { background: #e74c3c; color: white; }
        .unban-btn { background: #27ae60; color: white; }

        /* Админ таблица */
        .admin-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }

        .admin-table th, .admin-table td {
            padding: 0.5rem;
            text-align: left;
            border-bottom: 1px solid #2a2a2a;
        }

        .admin-table th {
            background: #1a1a1a;
            color: #27ae60;
        }

        /* Бан контролы */
        .ban-select, .ban-reason-input, .ban-message-input {
            padding: 0.3rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 6px;
            font-size: 0.75rem;
        }

        .ban-select {
            cursor: pointer;
        }

        .admin-promocode-status {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            margin-left: 0.5rem;
        }

        .admin-promocode-status.active {
            background: #27ae60;
            color: white;
        }

        .admin-promocode-status.inactive {
            background: #e74c3c;
            color: white;
        }

        /* ========== КОРЗИНА ========== */
        .cart-panel {
            position: fixed;
            right: -450px;
            top: 0;
            width: 450px;
            height: 100%;
            background: #0a0a0a;
            z-index: 1001;
            transition: right 0.3s ease;
            display: flex;
            flex-direction: column;
            border-left: 1px solid #2a2a2a;
        }

        .cart-panel.open {
            right: 0;
        }

        .cart-header {
            padding: 1rem;
            background: #0f0f0f;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .cart-header h3 {
            color: #27ae60;
            font-size: 1rem;
        }

        .cart-items {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
        }

        .cart-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.8rem;
            border-bottom: 1px solid #2a2a2a;
            animation: fadeInRight 0.3s ease-out;
        }

        .cart-item-title {
            font-weight: 500;
            margin-bottom: 0.25rem;
            font-size: 0.85rem;
        }

        .cart-item button {
            transition: all 0.2s ease;
            background: #2a2a2a;
            border: none;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
        }

        .cart-item button:hover {
            opacity: 0.8;
            transform: scale(1.05);
        }

        .cart-item button:active {
            transform: scale(0.95);
        }

        .empty-cart {
            text-align: center;
            color: #888;
            padding: 2rem;
        }

        .cart-footer {
            padding: 1rem;
            border-top: 1px solid #2a2a2a;
        }

        .promo-input-group {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 0.8rem;
        }

        .promo-input {
            flex: 1;
            padding: 0.5rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 25px;
        }

        .apply-promo-btn, .checkout-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 25px;
            font-size: 0.8rem;
        }

        .apply-promo-btn:hover, .checkout-btn:hover {
            background: #27ae60;
            border-color: #27ae60;
            transform: scale(1.02);
        }

        .checkout-btn {
            width: 100%;
            border-color: #27ae60;
            color: #27ae60;
            margin-top: 0.5rem;
        }

        .cart-total, .cart-discount {
            margin: 0.3rem 0;
            font-size: 0.9rem;
        }

        .overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
        }

        /* ========== АВТОРИЗАЦИЯ ========== */
        .auth-tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .auth-tab {
            padding: 0.5rem 1rem;
            cursor: pointer;
            color: #888;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }

        .auth-tab:hover {
            color: #27ae60;
        }

        .auth-tab.active {
            color: #27ae60;
            border-bottom: 2px solid #27ae60;
        }

        .auth-form {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .auth-input {
            padding: 0.75rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 10px;
            transition: all 0.3s ease;
        }

        .auth-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .auth-btn {
            padding: 0.75rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            margin-top: 0.5rem;
            border-radius: 25px;
            transition: all 0.3s ease;
            font-weight: 600;
        }

        .auth-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        /* ========== FEEDBACK MODAL ========== */
        .feedback-textarea {
            width: 100%;
            padding: 0.8rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 10px;
            resize: vertical;
            font-family: inherit;
        }

        .feedback-textarea:focus {
            outline: none;
            border-color: #27ae60;
        }

        .feedback-send-btn, .feedback-cancel-btn {
            flex: 1;
            padding: 0.7rem;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.85rem;
        }

        .feedback-send-btn {
            background: #27ae60;
            color: white;
        }

        .feedback-send-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .feedback-cancel-btn {
            background: #e74c3c;
            color: white;
        }

        .feedback-cancel-btn:hover {
            background: #c0392b;
            transform: scale(1.02);
        }

        .close-feedback {
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.3rem;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
        }

        .close-feedback:hover {
            color: #fff;
            transform: scale(1.1);
        }

        /* ========== АНИМАЦИИ ДЛЯ ЭЛЕМЕНТОВ ========== */
        .team-card, .contact-card, .news-card, .product-card, .home-review-card, .promo-card {
            animation: fadeInUp 0.6s ease-out backwards;
            animation-fill-mode: both;
        }

        .team-card:nth-child(1) { animation-delay: 0.1s; }
        .team-card:nth-child(2) { animation-delay: 0.3s; }
        .team-card:nth-child(3) { animation-delay: 0.5s; }

        .contact-card:nth-child(1) { animation-delay: 0.1s; }
        .contact-card:nth-child(2) { animation-delay: 0.2s; }
        .contact-card:nth-child(3) { animation-delay: 0.3s; }
        .contact-card:nth-child(4) { animation-delay: 0.4s; }

        .product-card {
            animation-delay: calc(var(--index, 0) * 0.05s);
        }

        /* Специальные эффекты при наведении */
        .team-card[data-role="director"]:hover {
            animation: glowRed 1s ease-in-out infinite;
            border-color: #e74c3c;
        }

        .team-card[data-role="manager"]:hover {
            animation: glowGreen 1s ease-in-out infinite;
            border-color: #f1c40f;
        }

        .team-card[data-role="admin"]:hover {
            animation: glowGreen 1s ease-in-out infinite;
            border-color: #3498db;
        }

        /* Информационная страница */
        .info-content {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
        }

        .info-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }

        .info-card:hover {
            border-color: #27ae60;
            transform: translateY(-3px);
        }

        .info-card h3 {
            color: #27ae60;
            margin-bottom: 1rem;
            font-size: 1rem;
        }

        .info-card p {
            color: #bbb;
            line-height: 1.6;
            font-size: 0.9rem;
        }

        .faq-item {
            margin-bottom: 1.5rem;
            border-bottom: 1px solid #2a2a2a;
            padding-bottom: 1rem;
        }

        .faq-question {
            color: #27ae60;
            font-weight: 600;
            margin-bottom: 0.5rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .faq-question:hover {
            color: #229954;
        }

        .faq-answer {
            color: #888;
            font-size: 0.85rem;
            line-height: 1.5;
            display: none;
        }

        .faq-answer.show {
            display: block;
        }

        .faq-icon {
            transition: transform 0.3s ease;
        }

        .faq-icon.rotated {
            transform: rotate(180deg);
        }

        /* Утилиты */
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .text-green { color: #27ae60; }
        .text-red { color: #e74c3c; }
        .mt-1 { margin-top: 0.5rem; }
        .mt-2 { margin-top: 1rem; }
        .mt-3 { margin-top: 1.5rem; }
        .mb-1 { margin-bottom: 0.5rem; }
        .mb-2 { margin-bottom: 1rem; }
        .mb-3 { margin-bottom: 1.5rem; }
        .p-1 { padding: 0.5rem; }
        .p-2 { padding: 1rem; }
        .p-3 { padding: 1.5rem; }

        /* Скелетон загрузки */
        .skeleton {
            background: linear-gradient(90deg, #1a1a1a 25%, #2a2a2a 50%, #1a1a1a 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
        }

        /* Скроллбар */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #1a1a1a;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb {
            background: #3a3a3a;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #27ae60;
        }

        /* Выделение текста */
        ::selection {
            background: #27ae60;
            color: white;
        }

        /* Анимация для уведомлений */
        @keyframes slideInTop {
            from {
                transform: translateY(-100%);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #27ae60;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            z-index: 10002;
            animation: slideInTop 0.3s ease-out;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }

        .notification.error {
            background: #e74c3c;
        }

        .notification.warning {
            background: #f39c12;
        }
    </style>
</head>
<body><div class="header">
    <div class="header-content">
        <div class="logo" onclick="goToHome()">
            <span class="logo-icon lightning">⚡</span>
            <span class="logo-text">ZETTA</span>
        </div>
        <div class="nav-links">
            <div class="nav-link" id="homeLink" onclick="goToHome()">Главная</div>
            <div class="nav-link" id="catalogLink" onclick="goToCatalog()">Каталог</div>
            <div class="nav-link" id="reviewsLink" onclick="goToReviews()">Отзывы</div>
            <div class="nav-link" id="contactsLink" onclick="goToContacts()">Контакты</div>
            <div class="nav-link" id="infoLink" onclick="showInfoPage()">Информация</div>
            <div class="nav-link" id="adminLink" onclick="goToAdminPanel()" style="display: none;">Админ</div>
            <div class="nav-link" id="profileLink" onclick="goToProfile()" style="display: none;">Профиль</div>
        </div>
        <div class="user-icon" onclick="showAuthModal()">
            👤 <span id="userNameDisplay" class="user-name">Войти</span>
        </div>
        <div class="cart-icon" onclick="toggleCart()">
            🛒 <span class="cart-count" id="cartCount">0</span>
        </div>
    </div>
    <div class="search-bar-full">
        <div class="search-container">
            <input type="text" class="search-input-full" id="searchInput" placeholder="Поиск услуг..." value="">
            <button class="search-btn-full" onclick="searchProducts()">Найти</button>
        </div>
    </div>
</div>

<div class="container">
    <!-- Главная страница -->
    <div id="homePage">
        <div class="hero">
            <h1>Zetta - Профессиональная сборка ПК и IT-услуги</h1>
            <p>Ваш надёжный партнёр в мире IT-технологий в Барнауле и по всей России</p>
        </div>

        <!-- Активные промокоды -->
        <div class="promo-section">
            <div class="promo-title">🎁 Активные промокоды</div>
            <div class="promo-codes" id="promoCodes"></div>
        </div>

        <!-- Наша команда -->
        <div class="team-section">
            <div class="team-title">★ НАША КОМАНДА ★</div>
            <div class="team-grid">
                <div class="team-card" data-role="admin">
                    <div class="team-avatar" style="background-image: url('https://randomuser.me/api/portraits/men/32.jpg');"></div>
                    <div class="team-name">Богдан Дмитриевич</div>
                    <div class="team-position">Главный системный администратор</div>
                    <div class="team-description">Эксперт по сборке ПК любой сложности, настройке серверов и IT-инфраструктуры. Опыт более 10 лет.</div>
                </div>
                <div class="team-card center" data-role="director">
                    <div class="team-avatar" style="background-image: url('https://randomuser.me/api/portraits/men/1.jpg');"></div>
                    <div class="team-name">Литвинов Антон Евгеньевич</div>
                    <div class="team-position">Генеральный директор</div>
                    <div class="team-description">Основатель компании Zetta. Ценит каждого сотрудника и создал дружную команду профессионалов. Лично следит за качеством каждого заказа.</div>
                </div>
                <div class="team-card" data-role="manager">
                    <div class="team-avatar" style="background-image: url('https://randomuser.me/api/portraits/men/52.jpg');"></div>
                    <div class="team-name">Егор Олегович</div>
                    <div class="team-position">Менеджер по работе с клиентами</div>
                    <div class="team-description">Поможет подобрать оптимальную конфигурацию ПК, проконсультирует по созданию сайтов и IT-услугам. Всегда на связи!</div>
                </div>
            </div>
        </div>

        <!-- Блог / Влог -->
        <div class="vlog-section">
            <div class="team-title">★ НАШ БЛОГ / ВЛОГ ★</div>
            <div class="vlog-content">
                <div class="vlog-text" id="vlogText">Загрузка...</div>
                <button class="vlog-edit-btn" id="vlogEditBtn" style="display: none;" onclick="openVlogEditor()">✏️ Редактировать влог</button>
            </div>
        </div>

        <!-- Новости компании -->
        <div class="news-carousel-section" id="newsCarouselSection">
            <div class="team-title">★ НОВОСТИ КОМПАНИИ ★</div>
            <button class="admin-add-btn" id="addNewsBtn" onclick="showAddNewsModal()" style="display: none;">+</button>
            <div class="carousel-container">
                <button class="carousel-btn prev" onclick="prevSlide()">❮</button>
                <div class="carousel-slides" id="carouselSlides"></div>
                <button class="carousel-btn next" onclick="nextSlide()">❯</button>
            </div>
            <div class="carousel-dots" id="carouselDots"></div>
        </div>

        <!-- Отзывы клиентов -->
        <div class="reviews-section" id="homeReviewsSection">
            <div class="reviews-title">★ ОТЗЫВЫ НАШИХ КЛИЕНТОВ ★</div>
            <div class="home-reviews-grid" id="homeReviewsGrid">
                <div class="skeleton" style="height: 150px;"></div>
            </div>
        </div>
    </div>

    <!-- Страница каталога -->
    <div id="catalogPage" class="hidden">
        <div class="catalog-page-wrapper">
            <div class="catalog-sidebar">
                <h3>📂 Категории</h3>
                <div class="category-list" id="categoryList"></div>
            </div>
            <div class="main-content">
                <div class="page-header">
                    <h1>Каталог услуг</h1>
                </div>
                <div class="products-grid" id="catalogGrid"></div>
            </div>
        </div>
    </div>

    <!-- Страница отзывов -->
    <div id="reviewsPage" class="hidden">
        <div class="page-header">
            <h1>Отзывы клиентов</h1>
        </div>
        <div class="reviews-container">
            <div class="write-review">
                <h3>✍️ Оставить отзыв</h3>
                <input type="text" class="review-name-input" id="reviewName" placeholder="Ваше имя">
                <div class="stars-rating" id="starRating"></div>
                <textarea class="review-input" id="reviewText" rows="4" placeholder="Поделитесь впечатлениями о наших услугах..."></textarea>
                <button class="submit-review-btn" onclick="submitReview()">📝 Отправить отзыв</button>
            </div>
            <div class="reviews-list" id="reviewsList"></div>
        </div>
    </div>

    <!-- Страница контактов -->
    <div id="contactsPage" class="hidden">
        <div class="page-header">
            <h1>Контакты</h1>
        </div>
        <div class="contacts-page">
            <div class="contacts-grid">
                <div class="contact-card">
                    <div class="contact-icon">📍</div>
                    <div class="contact-title">АДРЕС</div>
                    <div class="contact-value">г. Барнаул, ул. Юрина, 182<br>7 подъезд, 3 этаж, офис 305</div>
                </div>
                <div class="contact-card">
                    <div class="contact-icon">📞</div>
                    <div class="contact-title">ТЕЛЕФОНЫ</div>
                    <div class="contact-value">+7 (952) 006-23-57<br>+7 (913) 244-77-07</div>
                </div>
                <div class="contact-card">
                    <div class="contact-icon">✉️</div>
                    <div class="contact-title">EMAIL</div>
                    <div class="contact-value">vaincode@mail.ru</div>
                </div>
                <div class="contact-card">
                    <div class="contact-icon">🕐</div>
                    <div class="contact-title">ЧАСЫ РАБОТЫ</div>
                    <div class="contact-value">Пн-Пт: 09:00 - 21:00<br>Сб-Вс: 10:00 - 19:00</div>
                </div>
            </div>
            <div class="map-placeholder">
                <div class="contact-icon" style="font-size: 3rem;">🗺️</div>
                <div class="contact-title">НАШЕ МЕСТОПОЛОЖЕНИЕ</div>
                <div class="contact-value">г. Барнаул, ул. Юрина, 182</div>
                <div style="margin-top: 1rem; padding: 1rem; background: #1a1a1a; border-radius: 8px;">
                    <strong>ИП "Литвинов" компания ZETTA</strong><br>
                    ИНН: 2223330011 | ОГРН: 1233222344456
                </div>
            </div>
        </div>
    </div>

    <!-- Страница информации -->
    <div id="infoPage" class="hidden">
        <div class="page-header">
            <h1>Информация</h1>
        </div>
        <div class="info-content">
            <div class="info-card">
                <h3>🔒 Политика конфиденциальности</h3>
                <p>Мы уважаем ваше право на конфиденциальность и обязуемся защищать ваши персональные данные. Настоящая политика конфиденциальности объясняет, как мы собираем, используем и защищаем информацию, которую вы предоставляете при использовании нашего сайта.</p>
                <p class="mt-2"><strong>1. Сбор информации</strong><br>Мы собираем информацию, которую вы предоставляете добровольно при регистрации, оформлении заказа или обращении в службу поддержки: имя, email, номер телефона, адрес доставки.</p>
                <p class="mt-2"><strong>2. Использование информации</strong><br>Ваши данные используются исключительно для обработки заказов, доставки товаров и информирования о статусе заказа. Мы не передаём ваши данные третьим лицам без вашего согласия.</p>
                <p class="mt-2"><strong>3. Защита данных</strong><br>Мы принимаем все необходимые меры для защиты ваших персональных данных от несанкционированного доступа, изменения, раскрытия или уничтожения.</p>
                <p class="mt-2"><strong>4. Контактная информация</strong><br>По всем вопросам, связанным с обработкой персональных данных, вы можете обратиться по email: <a href="mailto:vaincode@mail.ru" style="color: #27ae60;">vaincode@mail.ru</a></p>
            </div>
            <div class="info-card">
                <h3>❓ Часто задаваемые вопросы</h3>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Как заказать сборку ПК?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Выберите категорию "Сборка компьютера" в каталоге или свяжитесь с нашим менеджером для индивидуального подбора конфигурации. Мы поможем подобрать оптимальные компоненты под ваш бюджет и задачи.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Какие способы оплаты доступны?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Вы можете оплатить заказ банковской картой онлайн или наличными при получении. При онлайн-оплате реквизиты для перевода будут отправлены на вашу почту после оформления заказа. Для юридических лиц доступен безналичный расчёт.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Сколько стоит доставка?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Доставка осуществляется бесплатно! Срок доставки зависит от расстояния: до 50 км - 3 дня, до 100 км - 7 дней, более 100 км - 14 дней. Доставка по городу Барнаулу - 1-2 дня.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Как использовать промокод?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Введите промокод в поле "Промокод" в корзине и нажмите "Применить". Скидка будет автоматически применена к вашему заказу. Один промокод можно использовать только один раз.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Как связаться со службой поддержки?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Вы можете связаться с нами по телефону <strong class="text-green">+7 (952) 006-23-57</strong> или <strong class="text-green">+7 (913) 244-77-07</strong>, или отправить письмо на <a href="mailto:vaincode@mail.ru" style="color: #27ae60;">vaincode@mail.ru</a>. Мы работаем ежедневно с 09:00 до 21:00.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFaq(this)">
                        <span>Есть ли гарантия на сборку ПК?</span>
                        <span class="faq-icon">▼</span>
                    </div>
                    <div class="faq-answer">Да, на все сборки ПК предоставляется гарантия 3 года. На комплектующие действует гарантия производителя. Также мы предоставляем бесплатную техническую поддержку в течение всего гарантийного срока.</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Личный кабинет -->
    <div id="profilePage" class="hidden">
        <div class="page-header">
            <h1>Личный кабинет</h1>
        </div>
        <div class="profile-container">
            <div class="profile-info" id="profileInfo">
                <div class="profile-field">
                    <div class="profile-label">ФИО</div>
                    <div class="profile-value" id="profileFullName"></div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">Email</div>
                    <div class="profile-value" id="profileEmail"></div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">Телефон</div>
                    <div class="profile-value" id="profilePhone"></div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">Дата регистрации</div>
                    <div class="profile-value" id="profileRegistered"></div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">Бонусные баллы</div>
                    <div class="profile-value" id="profileBonus">0</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">Всего заказов</div>
                    <div class="profile-value" id="profileOrdersCount">0</div>
                </div>
                <button class="profile-edit-btn" onclick="editProfile()">Редактировать профиль</button>
                <button class="logout-btn" onclick="logout()">Выйти</button>
            </div>
            <div class="orders-list">
                <div class="promo-title">История заказов</div>
                <div id="ordersHistory"></div>
            </div>
        </div>
    </div>

    <!-- Админ-панель -->
    <div id="adminPage" class="hidden">
        <div class="page-header">
            <h1>Админ-панель</h1>
        </div>
        <div class="admin-panel">
            <div class="admin-tabs">
                <div class="admin-tab active" onclick="switchAdminTab('products')">Товары</div>
                <div class="admin-tab" onclick="switchAdminTab('news')">Новости</div>
                <div class="admin-tab" onclick="switchAdminTab('promocodes')">Промокоды</div>
                <div class="admin-tab" onclick="switchAdminTab('reviews')">Отзывы</div>
                <div class="admin-tab" onclick="switchAdminTab('orders')">Заказы</div>
                <div class="admin-tab" onclick="switchAdminTab('users')">Пользователи</div>
            </div>

            <!-- Товары -->
            <div id="adminProducts" class="admin-section active">
                <div class="admin-form">
                    <h3>Добавить услугу/товар</h3>
                    <form id="addProductForm" enctype="multipart/form-data">
                        <input type="text" id="productName" placeholder="Название" required>
                        <input type="number" id="productPrice" placeholder="Обычная цена" required>
                        <input type="number" id="productSalePrice" placeholder="Цена со скидкой (оставьте пустым если скидки нет)">
                        <input type="number" id="productDiscountPercent" placeholder="Процент скидки (например 20)">
                        <textarea id="productDescription" rows="3" placeholder="Описание"></textarea>
                        <select id="productCategory">
                            <option value="computers">💻 Компьютеры</option>
                            <option value="services">🔧 Услуги</option>
                            <option value="pc_build">🛠️ Сборка компьютера</option>
                            <option value="websites">🌐 Сайты</option>
                            <option value="components">🔩 Комплектующие</option>
                        </select>
                        <input type="file" id="productImage" accept="image/*">
                        <button type="button" onclick="addProduct()">Добавить</button>
                    </form>
                </div>
                <div class="admin-form">
                    <h3>Список услуг</h3>
                    <div id="productsList"></div>
                </div>
            </div>

            <!-- Новости -->
            <div id="adminNews" class="admin-section">
                <div class="admin-form">
                    <h3>Добавить новость</h3>
                    <form id="addNewsForm" enctype="multipart/form-data">
                        <input type="text" id="newsTitle" placeholder="Заголовок" required>
                        <input type="text" id="newsShortText" placeholder="Краткий текст" required>
                        <textarea id="newsFullText" rows="5" placeholder="Полный текст новости"></textarea>
                        <input type="file" id="newsImage" accept="image/*">
                        <input type="file" id="newsVideo" accept="video/*">
                        <input type="text" id="newsVideoUrl" placeholder="Ссылка на видео (YouTube)">
                        <button type="button" onclick="addNews()">Добавить новость</button>
                    </form>
                </div>
                <div class="admin-form">
                    <h3>Список новостей</h3>
                    <div id="newsList"></div>
                </div>
            </div>

            <!-- Промокоды -->
            <div id="adminPromocodes" class="admin-section">
                <div class="admin-form">
                    <h3>Добавить промокод</h3>
                    <form id="addPromocodeForm">
                        <input type="text" id="promocodeCode" placeholder="Код промокода (например ZETTA10)" required>
                        <select id="promocodeType">
                            <option value="percent">Процентная скидка</option>
                            <option value="fixed">Фиксированная скидка (₽)</option>
                        </select>
                        <input type="number" id="promocodeDiscount" placeholder="Величина скидки" required>
                        <input type="number" id="promocodeMinOrder" placeholder="Минимальная сумма заказа (0 - без ограничений)">
                        <input type="number" id="promocodeMaxUses" placeholder="Максимальное количество использований (0 - без ограничений)">
                        <select id="promocodeApplyTo">
                            <option value="all">На все товары</option>
                            <option value="categories">На категории</option>
                            <option value="specific_products">На конкретные товары</option>
                        </select>
                        <div id="promocodeCategoriesDiv" style="display:none;">
                            <select id="promocodeCategories" multiple>
                                <option value="computers">💻 Компьютеры</option>
                                <option value="services">🔧 Услуги</option>
                                <option value="pc_build">🛠️ Сборка компьютера</option>
                                <option value="websites">🌐 Сайты</option>
                                <option value="components">🔩 Комплектующие</option>
                            </select>
                            <small>Ctrl+клик для выбора нескольких</small>
                        </div>
                        <div id="promocodeProductsDiv" style="display:none;">
                            <select id="promocodeProducts" multiple></select>
                            <small>Ctrl+клик для выбора нескольких</small>
                        </div>
                        <button type="button" onclick="addPromocode()">Добавить промокод</button>
                    </form>
                </div>
                <div class="admin-form">
                    <h3>Список промокодов</h3>
                    <div id="promocodesList"></div>
                </div>
            </div>

            <!-- Отзывы -->
            <div id="adminReviews" class="admin-section">
                <div class="admin-form">
                    <h3>Список отзывов</h3>
                    <div id="adminReviewsList"></div>
                </div>
            </div>

            <!-- Заказы -->
            <div id="adminOrders" class="admin-section">
                <div class="admin-form">
                    <h3>Все заказы</h3>
                    <div id="adminOrdersList"></div>
                </div>
            </div>

            <!-- Пользователи -->
            <div id="adminUsers" class="admin-section">
                <div class="admin-form">
                    <h3>Пользователи</h3>
                    <div id="usersList"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Страница оформления заказа -->
    <div id="checkoutPage" class="hidden">
        <div class="page-header">
            <h1>Оформление заказа</h1>
        </div>
        <div class="checkout-page">
            <div class="order-summary">
                <h3>Ваш заказ</h3>
                <div id="orderSummaryItems"></div>
                <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #3a3a3a;">
                    <div>Сумма: <span id="checkoutSubtotal">0</span> ₽</div>
                    <div>Скидка: <span id="checkoutDiscount">0</span> ₽</div>
                    <div>Доставка: <span id="checkoutDelivery">0</span> ₽</div>
                    <div style="font-size: 1.2rem; font-weight: bold;">Итого: <span id="checkoutTotal">0</span> ₽</div>
                </div>
            </div>

            <form class="checkout-form" id="checkoutForm">
                <div class="form-group">
                    <label class="form-label">ФИО *</label>
                    <input type="text" class="form-input" id="fullName" required placeholder="Иванов Иван Иванович">
                </div>
                <div class="form-group">
                    <label class="form-label">Email *</label>
                    <input type="email" class="form-input" id="email" required placeholder="example@mail.ru">
                </div>
                <div class="form-group">
                    <label class="form-label">Телефон *</label>
                    <input type="tel" class="form-input" id="phone" required placeholder="+7 (999) 123-45-67">
                </div>
                <div class="form-group">
                    <label class="form-label">Адрес доставки *</label>
                    <input type="text" class="form-input" id="deliveryAddress" required placeholder="г. Барнаул, ул. Примерная, д. 1">
                    <div class="delivery-info" id="deliveryInfo" style="margin-top: 0.5rem;">
                        <span id="distanceInfo">Введите адрес для расчёта доставки</span>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Способ оплаты *</label>
                    <div class="payment-methods">
                        <div class="payment-option" onclick="selectPayment('card')" id="cardOption">
                            💳 Банковская карта (онлайн)
                        </div>
                        <div class="payment-option" onclick="selectPayment('cash')" id="cashOption">
                            💰 Наличные при получении
                        </div>
                    </div>
                </div>
                <div id="cardFields" class="card-fields hidden">
                    <div class="form-group">
                        <label class="form-label">Номер карты</label>
                        <input type="text" class="form-input" id="cardNumber" placeholder="0000 0000 0000 0000" maxlength="19">
                    </div>
                    <div style="display: flex; gap: 1rem;">
                        <div class="form-group" style="flex: 1;">
                            <label class="form-label">ММ/ГГ</label>
                            <input type="text" class="form-input" id="cardExpiry" placeholder="12/25" maxlength="5">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label class="form-label">CVV</label>
                            <input type="password" class="form-input" id="cardCvv" placeholder="123" maxlength="3">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Имя держателя</label>
                        <input type="text" class="form-input" id="cardName" placeholder="IVAN IVANOV">
                    </div>
                </div>
                <button type="submit" class="submit-btn">Оформить заказ</button>
            </form>
        </div>
    </div>
</div>

<!-- Футер -->
<footer class="footer">
    <div class="footer-content">
        <div class="footer-section">
            <a href="tel:+79520062357">📞 +7 (952) 006-23-57</a>
            <a href="tel:+79132447707">📞 +7 (913) 244-77-07</a>
            <a href="mailto:vaincode@mail.ru">✉️ vaincode@mail.ru</a>
            <span>📍 г. Барнаул, ул. Юрина, 182</span>
        </div>
        <div class="footer-section">
            <a href="#" onclick="showPolicyPage(); return false;">🔒 Политика</a>
            <a href="#" onclick="showFaqPage(); return false;">❓ FAQ</a>
            <a href="#" onclick="goToReviews(); return false;">⭐ Отзывы</a>
            <a href="#" onclick="openFeedbackModal(); return false;">💡 Предложения</a>
        </div>
        <div class="footer-section">
            <span>⚡ ZETTA © 2026</span>
        </div>
    </div>
</footer>

<!-- Кнопка чата -->
<button class="chat-button" id="chatButton" onclick="toggleChat()">💬</button>

<!-- Окно чата -->
<div class="chat-window" id="chatWindow">
    <div class="chat-header">
        <h3>Чат поддержки Zetta</h3>
        <span class="close-chat" onclick="toggleChat()">×</span>
    </div>
    <div class="chat-messages-area" id="chatMessagesArea">
        <div class="chat-message admin">👋 Здравствуйте! Чем могу помочь? Выберите один из вариантов ниже:</div>
    </div>
    <div class="chat-buttons" id="chatButtons">
        <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
        <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
        <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
        <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
        <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
    </div>
</div>

<!-- Модальные окна -->
<div id="feedbackModal" class="feedback-modal">
    <div class="feedback-container">
        <h3>📝 Предложения и жалобы</h3>
        <p>Если у вас есть предложения по улучшению или жалобы, напишите нам. Мы обязательно рассмотрим ваше обращение!</p>
        <textarea id="feedbackMessage" class="feedback-textarea" rows="5" placeholder="Опишите ваше предложение или жалобу..."></textarea>
        <div style="display: flex; gap: 1rem; margin-top: 1rem;">
            <button class="feedback-send-btn" onclick="sendFeedback()">📨 Отправить</button>
            <button class="feedback-cancel-btn" onclick="closeFeedbackModal()">Отмена</button>
        </div>
        <span class="close-feedback" onclick="closeFeedbackModal()">×</span>
    </div>
</div>

<div id="newsModal" class="news-modal">
    <div class="news-modal-content">
        <div class="news-modal-header">
            <h2 id="newsModalTitle"></h2>
            <span class="close-news-modal" onclick="closeNewsModal()">×</span>
        </div>
        <div class="news-modal-body">
            <img id="newsModalImage" class="news-modal-image" src="" alt="">
            <div class="news-modal-date" id="newsModalDate"></div>
            <div class="news-modal-fulltext" id="newsModalFullText"></div>
        </div>
    </div>
</div>

<div id="addNewsModal" class="news-modal">
    <div class="news-modal-content">
        <div class="news-modal-header">
            <h2>Добавить новость</h2>
            <span class="close-news-modal" onclick="closeAddNewsModal()">×</span>
        </div>
        <div class="news-modal-body">
            <form id="addNewsFormModal" enctype="multipart/form-data">
                <input type="text" id="modalNewsTitle" class="form-input" style="margin-bottom: 1rem;" placeholder="Заголовок" required>
                <input type="text" id="modalNewsShortText" class="form-input" style="margin-bottom: 1rem;" placeholder="Краткий текст" required>
                <textarea id="modalNewsFullText" class="form-input" rows="5" placeholder="Полный текст новости" style="margin-bottom: 1rem;"></textarea>
                <input type="file" id="modalNewsImage" accept="image/*" style="margin-bottom: 1rem;">
                <input type="file" id="modalNewsVideo" accept="video/*" style="margin-bottom: 1rem;">
                <input type="text" id="modalNewsVideoUrl" class="form-input" placeholder="Ссылка на видео (YouTube)" style="margin-bottom: 1rem;">
                <button type="button" class="auth-btn" onclick="submitAddNews()" style="width: 100%;">Добавить</button>
            </form>
        </div>
    </div>
</div>

<div id="verifyModal" class="verify-modal">
    <div class="verify-container">
        <h3>Подтверждение регистрации</h3>
        <p>На вашу почту отправлен код подтверждения</p>
        <p id="verifyEmailDisplay" style="color: #27ae60; margin: 0.5rem 0;"></p>
        <input type="text" id="verifyCode" class="verify-code-input" placeholder="000000" maxlength="6">
        <div id="verifyTimer" class="verify-timer">Код действителен: 5:00</div>
        <button class="auth-btn" onclick="verifyCode()" style="width: 100%;">Подтвердить</button>
        <button class="resend-code-btn" onclick="resendCode()" style="width: 100%; margin-top: 0.5rem;">Отправить код повторно</button>
    </div>
</div>

<div id="resetModal" class="reset-modal">
    <div class="reset-container">
        <span class="close" onclick="closeResetModal()" style="float: right;">×</span>
        <h3>Восстановление пароля</h3>
        <div id="resetStep1">
            <p>Введите email, указанный при регистрации</p>
            <input type="email" id="resetEmail" class="auth-input" style="width: 100%; margin: 1rem 0;" placeholder="Email">
            <button class="auth-btn" onclick="sendResetCode()" style="width: 100%;">Отправить код</button>
        </div>
        <div id="resetStep2" style="display: none;">
            <p>Введите код из письма</p>
            <input type="text" id="resetCode" class="verify-code-input" placeholder="000000" maxlength="6" style="margin: 1rem 0;">
            <div id="resetTimer" class="verify-timer"></div>
            <input type="password" id="newPassword" class="auth-input" style="width: 100%; margin: 1rem 0;" placeholder="Новый пароль">
            <input type="password" id="confirmNewPassword" class="auth-input" style="width: 100%; margin: 1rem 0;" placeholder="Подтвердите пароль">
            <button class="auth-btn" onclick="resetPassword()" style="width: 100%;">Сбросить пароль</button>
        </div>
    </div>
</div>

<div id="profileFormModal" class="profile-form-modal">
    <div class="profile-form-container">
        <h3>Заполните профиль</h3>
        <p style="color: #888; margin-bottom: 1rem;">Пожалуйста, укажите ваши контактные данные</p>
        <input type="text" id="profileFullNameInput" class="auth-input" style="width: 100%; margin-bottom: 1rem;" placeholder="ФИО *">
        <input type="email" id="profileEmailInput" class="auth-input" style="width: 100%; margin-bottom: 1rem;" placeholder="Email *" readonly>
        <input type="tel" id="profilePhoneInput" class="auth-input" style="width: 100%; margin-bottom: 1rem;" placeholder="Телефон *">
        <button class="auth-btn" onclick="saveProfile()" style="width: 100%;">Сохранить</button>
    </div>
</div>

<div id="productModal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h2 id="modalTitle"></h2>
            <span class="close" onclick="closeModal()">×</span>
        </div>
        <div class="modal-body" style="padding:1.5rem; display:flex; gap:1.5rem; flex-wrap:wrap;">
            <img id="modalImage" style="width:200px; height:200px; object-fit:cover; border-radius:8px;">
            <div style="flex:1;">
                <div class="product-price" id="modalPrice"></div>
                <div id="modalDescription" style="color:#888; margin:1rem 0;"></div>
                <button class="add-to-cart" onclick="addToCartFromModal()">В корзину</button>
            </div>
        </div>
    </div>
</div>

<div id="authModal" class="auth-modal">
    <div class="auth-container">
        <div style="display: flex; justify-content: space-between; margin-bottom: 1rem;">
            <h3>Вход / Регистрация</h3>
            <span class="close" onclick="closeAuthModal()">×</span>
        </div>
        <div class="auth-tabs">
            <div class="auth-tab active" onclick="switchAuthTab('login')">Вход</div>
            <div class="auth-tab" onclick="switchAuthTab('register')">Регистрация</div>
        </div>
        <div id="loginForm" class="auth-form">
            <input type="email" id="loginEmail" class="auth-input" placeholder="Email" required>
            <input type="password" id="loginPassword" class="auth-input" placeholder="Пароль" required>
            <div class="forgot-password">
                <a onclick="showForgotPasswordModal()">Забыли пароль?</a>
            </div>
            <button class="auth-btn" onclick="login()">Войти</button>
        </div>
        <div id="registerForm" class="auth-form hidden">
            <input type="text" id="regFullName" class="auth-input" placeholder="ФИО" required>
            <input type="email" id="regEmail" class="auth-input" placeholder="Email" required>
            <input type="tel" id="regPhone" class="auth-input" placeholder="Телефон" required>
            <input type="password" id="regPassword" class="auth-input" placeholder="Пароль" required>
            <input type="password" id="regConfirmPassword" class="auth-input" placeholder="Подтверждение пароля" required>
            <button class="auth-btn" onclick="sendVerificationCode()">Зарегистрироваться</button>
        </div>
    </div>
</div>

<div class="overlay" id="overlay" onclick="toggleCart()"></div>
<div class="cart-panel" id="cartPanel">
    <div class="cart-header">
        <h3>Корзина</h3>
        <span class="close" onclick="toggleCart()">×</span>
    </div>
    <div class="cart-items" id="cartItems"></div>
    <div class="cart-footer">
        <div class="promo-input-group">
            <input type="text" class="promo-input" id="promoCodeInput" placeholder="Промокод">
            <button class="apply-promo-btn" onclick="applyPromoCode()">Применить</button>
        </div>
        <div id="promoMessage" class="text-center mb-1"></div>
        <div class="cart-total">Сумма: <span id="cartSubtotal">0</span> ₽</div>
        <div class="cart-discount" id="cartDiscount">Скидка: 0 ₽</div>
        <div class="cart-total">Итого: <span id="cartTotal">0</span> ₽</div>
        <button class="checkout-btn" onclick="goToCheckout()">Оформить заказ</button>
    </div>
</div><script>
    // ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
    let currentUser = null;
    let isLoggedIn = false;
    let isAdmin = false;
    let currentPage = 'home';
    let selectedRating = 0;
    let currentCategory = 'all';
    let currentSearchTerm = '';
    let currentSlide = 0;
    let slidesPerView = 3;
    let newsData = [];
    let verifyTimerInterval = null;
    let resetTimerInterval = null;
    let pendingRegistration = null;
    let pendingResetEmail = null;
    let currentProduct = null;
    let selectedPayment = null;
    let allProducts = [];
    let consultationButtons = false;
    let chatResetTimer = null;

    // ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
    async function fetchJSON(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Fetch error:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            return null;
        }
    }

    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = message;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.style.animation = 'slideOutTop 0.3s ease-out forwards';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function animateToCart(element) {
        const cartIcon = document.getElementById('cartIcon');
        const rect = element.getBoundingClientRect();
        const clone = element.cloneNode(true);
        clone.style.position = 'fixed';
        clone.style.left = rect.left + 'px';
        clone.style.top = rect.top + 'px';
        clone.style.width = rect.width + 'px';
        clone.style.height = rect.height + 'px';
        clone.style.zIndex = '9999';
        clone.style.pointerEvents = 'none';
        clone.classList.add('animate-fly');
        document.body.appendChild(clone);
        setTimeout(() => {
            clone.remove();
            cartIcon.classList.add('cart-icon-animate');
            setTimeout(() => cartIcon.classList.remove('cart-icon-animate'), 300);
        }, 600);
    }

    function toggleFaq(element) {
        const answer = element.nextElementSibling;
        const icon = element.querySelector('.faq-icon');
        answer.classList.toggle('show');
        if (icon) icon.classList.toggle('rotated');
    }

    // ========== НАВИГАЦИЯ ==========
    function goToHome() {
        currentPage = 'home';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('homePage').classList.remove('hidden');
        loadPromoCodes();
        loadHomeReviews();
        loadNews();
        loadVlog();
        updateActiveNavLink('homeLink');
    }

    function goToCatalog() {
        currentPage = 'catalog';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('catalogPage').classList.remove('hidden');
        loadCatalog();
        updateActiveNavLink('catalogLink');
    }

    function goToReviews() {
        currentPage = 'reviews';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('reviewsPage').classList.remove('hidden');
        loadReviews();
        updateActiveNavLink('reviewsLink');
    }

    function goToContacts() {
        currentPage = 'contacts';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('contactsPage').classList.remove('hidden');
        updateActiveNavLink('contactsLink');
    }

    function showInfoPage() {
        currentPage = 'info';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('infoPage').classList.remove('hidden');
        updateActiveNavLink('infoLink');
    }

    function showPolicyPage() {
        showInfoPage();
        document.getElementById('infoPage').scrollIntoView({ behavior: 'smooth' });
    }

    function showFaqPage() {
        showInfoPage();
    }

    function goToProfile() {
        if (!isLoggedIn) {
            showAuthModal();
            return;
        }
        currentPage = 'profile';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('profilePage').classList.remove('hidden');
        checkAndShowProfileForm();
        updateActiveNavLink('profileLink');
    }

    function goToAdminPanel() {
        if (!isAdmin) {
            showNotification('Доступ запрещён. Только для администраторов.', 'error');
            return;
        }
        currentPage = 'admin';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('adminPage').classList.remove('hidden');
        loadAdminProducts();
        loadAdminNews();
        loadAdminPromocodes();
        loadAdminReviews();
        loadAdminOrders();
        loadAdminUsers();
        updateActiveNavLink('adminLink');
    }

    function updateActiveNavLink(activeId) {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        if (activeId) {
            const activeLink = document.getElementById(activeId);
            if (activeLink) activeLink.classList.add('active');
        }
    }

    // ========== АВТОРИЗАЦИЯ ==========
    async function checkAuthStatus() {
        const data = await fetchJSON('/api/auth/status');
        if (data?.logged_in) {
            isLoggedIn = true;
            isAdmin = data.is_admin === true;
            currentUser = data.user;
            document.getElementById('userNameDisplay').innerText = data.user.full_name ? data.user.full_name.split(' ')[0] : data.user.email;
            document.getElementById('profileLink').style.display = 'block';
            document.getElementById('adminLink').style.display = isAdmin ? 'block' : 'none';
            document.getElementById('addNewsBtn').style.display = isAdmin ? 'flex' : 'none';
            document.getElementById('vlogEditBtn').style.display = isAdmin ? 'block' : 'none';
            
            if (data.user.bonus_points) {
                document.getElementById('profileBonus').innerText = data.user.bonus_points;
            }
            if (data.user.orders_count) {
                document.getElementById('profileOrdersCount').innerText = data.user.orders_count;
            }
        } else {
            isLoggedIn = false;
            isAdmin = false;
            currentUser = null;
            document.getElementById('userNameDisplay').innerText = 'Войти';
            document.getElementById('profileLink').style.display = 'none';
            document.getElementById('adminLink').style.display = 'none';
            document.getElementById('addNewsBtn').style.display = 'none';
            document.getElementById('vlogEditBtn').style.display = 'none';
            if (data?.banned) {
                window.location.href = '/';
            }
        }
    }

    function showAuthModal() {
        if (isLoggedIn) {
            goToProfile();
        } else {
            document.getElementById('authModal').style.display = 'block';
        }
    }

    function closeAuthModal() {
        document.getElementById('authModal').style.display = 'none';
        switchAuthTab('login');
    }

    function switchAuthTab(tab) {
        const loginTab = document.querySelectorAll('.auth-tab')[0];
        const regTab = document.querySelectorAll('.auth-tab')[1];
        if (tab === 'login') {
            loginTab.classList.add('active');
            regTab.classList.remove('active');
            document.getElementById('loginForm').classList.remove('hidden');
            document.getElementById('registerForm').classList.add('hidden');
        } else {
            loginTab.classList.remove('active');
            regTab.classList.add('active');
            document.getElementById('loginForm').classList.add('hidden');
            document.getElementById('registerForm').classList.remove('hidden');
        }
    }

    async function login() {
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        if (!email || !password) {
            showNotification('Заполните все поля', 'error');
            return;
        }
        const result = await fetchJSON('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        if (result?.success) {
            showNotification('Вход выполнен успешно!', 'success');
            closeAuthModal();
            await checkAuthStatus();
            if (currentPage === 'profile') {
                await checkAndShowProfileForm();
            }
            goToHome();
        } else {
            showNotification(result?.message || 'Ошибка входа', 'error');
        }
    }

    async function logout() {
        await fetchJSON('/api/auth/logout', { method: 'POST' });
        showNotification('Вы вышли из аккаунта', 'success');
        await checkAuthStatus();
        goToHome();
    }

    // ========== ПРОФИЛЬ ==========
    async function checkAndShowProfileForm() {
        const data = await fetchJSON('/api/check-profile-complete');
        if (!data?.complete) {
            document.getElementById('profileFullNameInput').value = currentUser?.full_name || '';
            document.getElementById('profileEmailInput').value = currentUser?.email || '';
            document.getElementById('profilePhoneInput').value = currentUser?.phone || '';
            document.getElementById('profileFormModal').style.display = 'block';
        } else {
            await loadProfile();
            await loadOrdersHistory();
        }
    }

    async function loadProfile() {
        const data = await fetchJSON('/api/user/profile');
        if (data) {
            document.getElementById('profileFullName').innerText = data.full_name;
            document.getElementById('profileEmail').innerText = data.email;
            document.getElementById('profilePhone').innerText = data.phone;
            document.getElementById('profileRegistered').innerText = data.registered_at;
        }
    }

    async function loadOrdersHistory() {
        const data = await fetchJSON('/api/user/orders');
        const container = document.getElementById('ordersHistory');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">У вас пока нет заказов</div>';
            return;
        }
        container.innerHTML = data.map(order => `
            <div class="order-card">
                <div class="order-header">
                    <span class="order-number">Заказ #${order.order_number}</span>
                    <span class="order-status ${order.status || 'pending'}">${getStatusText(order.status)}</span>
                    <span class="order-date">${order.datetime}</span>
                </div>
                <div class="order-items">
                    ${order.items.map(item => `
                        <div class="order-item">
                            <span>${escapeHtml(item.name)} x ${item.quantity}</span>
                            <span>${item.total.toLocaleString()} ₽</span>
                        </div>
                    `).join('')}
                </div>
                <div class="order-total">
                    Итого: ${order.total.toLocaleString()} ₽
                </div>
                <div class="order-delivery" style="font-size: 0.8rem; color: #888; margin-top: 0.5rem;">
                    Доставка: ${escapeHtml(order.delivery_address)}<br>
                    Ожидаемая дата: ${order.delivery_date}
                </div>
            </div>
        `).join('');
    }

    function getStatusText(status) {
        const statusMap = {
            'pending': 'Ожидает оплаты',
            'paid': 'Оплачен',
            'processing': 'В обработке',
            'shipped': 'Отправлен',
            'delivered': 'Доставлен',
            'cancelled': 'Отменён'
        };
        return statusMap[status] || 'Ожидает обработки';
    }

    function editProfile() {
        document.getElementById('profileFullNameInput').value = document.getElementById('profileFullName').innerText;
        document.getElementById('profileEmailInput').value = document.getElementById('profileEmail').innerText;
        document.getElementById('profilePhoneInput').value = document.getElementById('profilePhone').innerText;
        document.getElementById('profileFormModal').style.display = 'block';
    }

    async function saveProfile() {
        const fullName = document.getElementById('profileFullNameInput').value;
        const phone = document.getElementById('profilePhoneInput').value;
        if (!fullName || !phone) {
            showNotification('Заполните все поля', 'error');
            return;
        }
        const result = await fetchJSON('/api/update-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, phone: phone })
        });
        if (result?.success) {
            document.getElementById('profileFormModal').style.display = 'none';
            showNotification('Профиль успешно обновлён!', 'success');
            await checkAuthStatus();
            await loadProfile();
            await loadOrdersHistory();
        } else {
            showNotification('Ошибка при сохранении профиля', 'error');
        }
    }

    // ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ ==========
    function showForgotPasswordModal() {
        closeAuthModal();
        document.getElementById('resetStep1').style.display = 'block';
        document.getElementById('resetStep2').style.display = 'none';
        document.getElementById('resetModal').style.display = 'block';
    }

    function closeResetModal() {
        if (resetTimerInterval) clearInterval(resetTimerInterval);
        document.getElementById('resetModal').style.display = 'none';
        pendingResetEmail = null;
    }

    async function sendResetCode() {
        const email = document.getElementById('resetEmail').value;
        if (!email) {
            showNotification('Введите email', 'error');
            return;
        }
        const result = await fetchJSON('/api/send-reset-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        });
        if (result?.success) {
            pendingResetEmail = email;
            document.getElementById('resetStep1').style.display = 'none';
            document.getElementById('resetStep2').style.display = 'block';
            startResetTimer(300);
            showNotification('Код отправлен на почту', 'success');
        } else {
            showNotification(result?.message || 'Ошибка отправки', 'error');
        }
    }

    function startResetTimer(seconds) {
        if (resetTimerInterval) clearInterval(resetTimerInterval);
        let remaining = seconds;
        const timerEl = document.getElementById('resetTimer');
        resetTimerInterval = setInterval(() => {
            remaining--;
            if (remaining >= 0) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                timerEl.textContent = `Код действителен: ${mins}:${secs.toString().padStart(2, '0')}`;
                timerEl.style.color = remaining < 60 ? '#e74c3c' : '#27ae60';
            } else {
                clearInterval(resetTimerInterval);
                timerEl.textContent = 'Код истёк. Запросите новый.';
                timerEl.style.color = '#e74c3c';
            }
        }, 1000);
    }

    async function resetPassword() {
        const code = document.getElementById('resetCode').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmNewPassword').value;
        if (!code || code.length !== 6) {
            showNotification('Введите 6-значный код', 'error');
            return;
        }
        if (newPassword.length < 6) {
            showNotification('Пароль должен содержать не менее 6 символов', 'error');
            return;
        }
        if (newPassword !== confirmPassword) {
            showNotification('Пароли не совпадают', 'error');
            return;
        }
        const result = await fetchJSON('/api/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: pendingResetEmail,
                code: code,
                new_password: newPassword
            })
        });
        if (result?.success) {
            if (resetTimerInterval) clearInterval(resetTimerInterval);
            closeResetModal();
            showNotification('Пароль успешно изменён! Теперь войдите с новым паролем.', 'success');
            showAuthModal();
        } else {
            showNotification(result?.message || 'Ошибка сброса пароля', 'error');
        }
    }

    // ========== РЕГИСТРАЦИЯ ==========
    async function sendVerificationCode() {
        const fullName = document.getElementById('regFullName').value;
        const email = document.getElementById('regEmail').value;
        const phone = document.getElementById('regPhone').value;
        const password = document.getElementById('regPassword').value;
        const confirmPassword = document.getElementById('regConfirmPassword').value;
        if (!fullName || !email || !phone || !password) {
            showNotification('Заполните все поля', 'error');
            return;
        }
        if (password !== confirmPassword) {
            showNotification('Пароли не совпадают', 'error');
            return;
        }
        if (password.length < 6) {
            showNotification('Пароль должен содержать не менее 6 символов', 'error');
            return;
        }
        const result = await fetchJSON('/api/send-verification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                full_name: fullName,
                phone: phone,
                password: password
            })
        });
        if (result?.success) {
            pendingRegistration = { email: email, full_name: fullName, phone: phone };
            document.getElementById('verifyEmailDisplay').textContent = email;
            document.getElementById('verifyModal').style.display = 'block';
            document.getElementById('verifyCode').value = '';
            startVerifyTimer(300);
            showNotification('Код отправлен на почту', 'success');
        } else {
            showNotification(result?.message || 'Ошибка отправки', 'error');
        }
    }

    function startVerifyTimer(seconds) {
        if (verifyTimerInterval) clearInterval(verifyTimerInterval);
        let remaining = seconds;
        const timerEl = document.getElementById('verifyTimer');
        verifyTimerInterval = setInterval(() => {
            remaining--;
            if (remaining >= 0) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                timerEl.textContent = `Код действителен: ${mins}:${secs.toString().padStart(2, '0')}`;
                timerEl.style.color = remaining < 60 ? '#e74c3c' : '#27ae60';
            } else {
                clearInterval(verifyTimerInterval);
                timerEl.textContent = 'Код истёк. Запросите новый.';
                timerEl.style.color = '#e74c3c';
            }
        }, 1000);
    }

    async function verifyCode() {
        const code = document.getElementById('verifyCode').value;
        if (!code || code.length !== 6) {
            showNotification('Введите 6-значный код', 'error');
            return;
        }
        const result = await fetchJSON('/api/verify-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: pendingRegistration?.email,
                code: code
            })
        });
        if (result?.success) {
            if (verifyTimerInterval) clearInterval(verifyTimerInterval);
            document.getElementById('verifyModal').style.display = 'none';
            showNotification('Регистрация успешна! Теперь войдите в аккаунт.', 'success');
            switchAuthTab('login');
            document.getElementById('loginEmail').value = pendingRegistration.email;
            pendingRegistration = null;
        } else {
            showNotification(result?.message || 'Неверный код', 'error');
        }
    }

    async function resendCode() {
        if (!pendingRegistration) return;
        const result = await fetchJSON('/api/resend-verification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: pendingRegistration.email })
        });
        if (result?.success) {
            showNotification('Новый код отправлен на почту', 'success');
            startVerifyTimer(300);
        } else {
            showNotification(result?.message || 'Ошибка отправки', 'error');
        }
    }    // ========== НОВОСТИ ==========
    async function loadNews() {
        const data = await fetchJSON('/api/admin/news');
        newsData = data || [];
        renderCarousel();
    }

    function renderCarousel() {
        const container = document.getElementById('carouselSlides');
        const dotsContainer = document.getElementById('carouselDots');
        const totalSlides = Math.ceil(newsData.length / slidesPerView);
        
        if (newsData.length === 0) {
            container.innerHTML = '<div class="carousel-slide"><div class="news-card" style="text-align:center; padding:2rem;">Новостей пока нет</div></div>';
            dotsContainer.innerHTML = '';
            return;
        }
        
        container.innerHTML = '';
        for (let i = 0; i < totalSlides; i++) {
            const slideDiv = document.createElement('div');
            slideDiv.className = 'carousel-slide';
            const startIdx = i * slidesPerView;
            const endIdx = Math.min(startIdx + slidesPerView, newsData.length);
            for (let j = startIdx; j < endIdx; j++) {
                const item = newsData[j];
                const adminActions = isAdmin ? `
                    <div style="position:absolute; top:0.5rem; right:0.5rem; display:flex; gap:0.3rem; z-index:5;">
                        <button class="edit-btn" style="padding:0.2rem 0.4rem; font-size:0.7rem;" onclick="event.stopPropagation(); editNewsFromCarousel(${item.id})">✏️</button>
                        <button class="delete-btn" style="padding:0.2rem 0.4rem; font-size:0.7rem;" onclick="event.stopPropagation(); deleteNewsFromCarousel(${item.id})">🗑️</button>
                    </div>
                ` : '';
                slideDiv.innerHTML += `
                    <div class="news-card" onclick="openNewsModal(${j})" style="position:relative;">
                        ${adminActions}
                        ${item.video ? 
                            `<video class="news-card-video" src="${item.video}" autoplay loop muted playsinline></video>` : 
                            `<img src="${item.image}" class="news-card-image" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'">`
                        }
                        <div class="news-card-content">
                            <div class="news-card-date">${item.date}</div>
                            <div class="news-card-title">${escapeHtml(item.title)}</div>
                            <div class="news-card-text">${escapeHtml(item.text)}</div>
                        </div>
                    </div>
                `;
            }
            container.appendChild(slideDiv);
        }
        
        dotsContainer.innerHTML = '';
        for (let i = 0; i < totalSlides; i++) {
            const dot = document.createElement('div');
            dot.className = 'dot' + (i === currentSlide ? ' active' : '');
            dot.onclick = () => goToSlide(i);
            dotsContainer.appendChild(dot);
        }
        
        container.style.transform = `translateX(-${currentSlide * 100}%)`;
    }

    function nextSlide() {
        const totalSlides = Math.ceil(newsData.length / slidesPerView);
        if (currentSlide < totalSlides - 1) {
            currentSlide++;
            updateCarousel();
        }
    }

    function prevSlide() {
        if (currentSlide > 0) {
            currentSlide--;
            updateCarousel();
        }
    }

    function goToSlide(index) {
        currentSlide = index;
        updateCarousel();
    }

    function updateCarousel() {
        const container = document.getElementById('carouselSlides');
        container.style.transform = `translateX(-${currentSlide * 100}%)`;
        const dots = document.querySelectorAll('.dot');
        dots.forEach((dot, i) => {
            if (i === currentSlide) dot.classList.add('active');
            else dot.classList.remove('active');
        });
    }

    function openNewsModal(index) {
        const item = newsData[index];
        if (!item) return;
        document.getElementById('newsModalTitle').textContent = item.title;
        document.getElementById('newsModalImage').src = item.image;
        document.getElementById('newsModalDate').textContent = item.date;
        document.getElementById('newsModalFullText').innerHTML = `<p>${item.fullText}</p><p style="margin-top:1rem;">🔥 Не упустите возможность! Обращайтесь в Zetta!</p>`;
        document.getElementById('newsModal').style.display = 'block';
    }

    function closeNewsModal() {
        document.getElementById('newsModal').style.display = 'none';
    }

    function showAddNewsModal() {
        document.getElementById('addNewsModal').style.display = 'block';
    }

    function closeAddNewsModal() {
        document.getElementById('addNewsModal').style.display = 'none';
        document.getElementById('modalNewsTitle').value = '';
        document.getElementById('modalNewsShortText').value = '';
        document.getElementById('modalNewsFullText').value = '';
        document.getElementById('modalNewsImage').value = '';
        document.getElementById('modalNewsVideo').value = '';
        document.getElementById('modalNewsVideoUrl').value = '';
    }

    function editNewsFromCarousel(id) {
        const news = newsData.find(n => n.id === id);
        if (!news) return;
        const newTitle = prompt('Введите новый заголовок:', news.title);
        if (!newTitle) return;
        const newText = prompt('Введите новый краткий текст:', news.text);
        if (!newText) return;
        const newFullText = prompt('Введите новый полный текст:', news.fullText);
        if (!newFullText) return;
        fetch('/api/admin/edit-news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, title: newTitle, text: newText, fullText: newFullText })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                showNotification('Новость обновлена', 'success');
                loadNews();
                if (currentPage === 'admin') loadAdminNews();
            } else {
                showNotification(data.message || 'Ошибка', 'error');
            }
        });
    }

    function deleteNewsFromCarousel(id) {
        if (confirm('Удалить новость?')) {
            fetch('/api/admin/delete-news', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    showNotification('Новость удалена', 'success');
                    loadNews();
                    if (currentPage === 'admin') loadAdminNews();
                } else {
                    showNotification(data.message || 'Ошибка', 'error');
                }
            });
        }
    }

    function submitAddNews() {
        const formData = new FormData();
        formData.append('title', document.getElementById('modalNewsTitle').value);
        formData.append('text', document.getElementById('modalNewsShortText').value);
        formData.append('fullText', document.getElementById('modalNewsFullText').value);
        const imageFile = document.getElementById('modalNewsImage');
        if (imageFile.files[0]) formData.append('image', imageFile.files[0]);
        const videoFile = document.getElementById('modalNewsVideo');
        if (videoFile.files[0]) formData.append('video', videoFile.files[0]);
        const videoUrl = document.getElementById('modalNewsVideoUrl').value;
        if (videoUrl) formData.append('video_url', videoUrl);
        
        fetch('/api/admin/add-news', {
            method: 'POST',
            body: formData
        }).then(res => res.json()).then(data => {
            if (data.success) {
                showNotification('Новость добавлена', 'success');
                closeAddNewsModal();
                loadNews();
                if (currentPage === 'admin') loadAdminNews();
            } else {
                showNotification(data.message || 'Ошибка при добавлении новости', 'error');
            }
        });
    }

    // ========== ВЛОГ ==========
    async function loadVlog() {
        const data = await fetchJSON('/api/vlog');
        const vlogText = document.getElementById('vlogText');
        if (vlogText && data) {
            vlogText.innerHTML = data.text.replace(/\\n/g, '<br>');
        }
    }

    function openVlogEditor() {
        fetch('/api/vlog').then(res => res.json()).then(data => {
            const newText = prompt('Редактировать влог:', data.text);
            if (newText !== null && newText !== data.text) {
                fetch('/api/admin/update-vlog', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: newText })
                }).then(res => res.json()).then(result => {
                    if (result.success) {
                        showNotification('Влог обновлён!', 'success');
                        loadVlog();
                    } else {
                        showNotification(result.message || 'Ошибка при обновлении', 'error');
                    }
                });
            }
        });
    }

    // ========== ПРОМОКОДЫ ==========
    async function loadPromoCodes() {
        const data = await fetchJSON('/api/promocodes');
        const container = document.getElementById('promoCodes');
        if (container) {
            const activePromocodes = Object.entries(data || {}).filter(([code, d]) => d.active);
            if (activePromocodes.length === 0) {
                container.innerHTML = '<div class="empty-cart">Нет активных промокодов</div>';
                return;
            }
            container.innerHTML = activePromocodes.map(([code, d]) => `
                <div class="promo-card" onclick="copyPromoCode('${code}')">
                    <div class="promo-code">${code}</div>
                    <div class="promo-discount">-${d.type === 'percent' ? d.discount + '%' : d.discount + ' ₽'}</div>
                </div>
            `).join('');
        }
    }

    function copyPromoCode(code) {
        navigator.clipboard.writeText(code);
        showNotification('Промокод скопирован!', 'success');
    }

    // ========== ОТЗЫВЫ ==========
    async function loadHomeReviews() {
        const data = await fetchJSON('/api/home-reviews');
        const container = document.getElementById('homeReviewsGrid');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">Пока нет отзывов. Будьте первым!</div>';
            return;
        }
        container.innerHTML = data.map(review => `
            <div class="home-review-card">
                <div class="home-review-header">
                    <span class="home-review-author">${escapeHtml(review.name)}</span>
                    <span class="home-review-date">${review.date}</span>
                </div>
                <div class="home-review-stars">
                    ${Array(5).fill().map((_, i) => `<span class="star-static ${i < review.rating ? 'active' : ''}">★</span>`).join('')}
                </div>
                <div class="home-review-text">${escapeHtml(review.text)}</div>
            </div>
        `).join('');
    }

    async function loadReviews() {
        const data = await fetchJSON('/api/reviews');
        const container = document.getElementById('reviewsList');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">Пока нет отзывов. Будьте первым!</div>';
            return;
        }
        container.innerHTML = data.map((review, idx) => `
            <div class="review-item">
                <div class="review-header">
                    <span class="review-author">${escapeHtml(review.name)}</span>
                    <span class="review-date">${review.date}</span>
                    ${isAdmin ? `
                        <div class="review-actions">
                            <button class="delete-review" onclick="deleteReview(${idx})">🗑️</button>
                        </div>
                    ` : ''}
                </div>
                <div class="review-stars">
                    ${Array(5).fill().map((_, i) => `<span class="star-static ${i < review.rating ? 'active' : ''}">★</span>`).join('')}
                </div>
                <div class="review-text">${escapeHtml(review.text)}</div>
            </div>
        `).join('');
    }

    async function deleteReview(index) {
        if (confirm('Удалить отзыв?')) {
            const result = await fetchJSON('/api/admin/delete-review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: index })
            });
            if (result?.success) {
                showNotification('Отзыв удалён', 'success');
                await loadReviews();
                await loadHomeReviews();
                if (isAdmin && currentPage === 'admin') await loadAdminReviews();
            } else {
                showNotification(result?.message || 'Ошибка при удалении', 'error');
            }
        }
    }

    async function submitReview() {
        if (!isLoggedIn) {
            showNotification('Пожалуйста, войдите в аккаунт, чтобы оставить отзыв', 'error');
            showAuthModal();
            return;
        }
        const name = document.getElementById('reviewName').value.trim();
        const text = document.getElementById('reviewText').value.trim();
        if (!name) {
            showNotification('Введите ваше имя', 'error');
            return;
        }
        if (selectedRating === 0) {
            showNotification('Поставьте оценку', 'error');
            return;
        }
        if (!text) {
            showNotification('Введите текст отзыва', 'error');
            return;
        }
        if (text.length < 10) {
            showNotification('Отзыв должен содержать не менее 10 символов', 'error');
            return;
        }
        const result = await fetchJSON('/api/add-review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, rating: selectedRating, text: text })
        });
        if (result?.success) {
            showNotification('Спасибо за отзыв!', 'success');
            document.getElementById('reviewName').value = '';
            document.getElementById('reviewText').value = '';
            document.querySelectorAll('#starRating .star').forEach(s => s.classList.remove('active'));
            selectedRating = 0;
            await loadReviews();
            await loadHomeReviews();
        } else {
            showNotification('Ошибка при сохранении отзыва', 'error');
        }
    }

    function initStars() {
        const starsContainer = document.getElementById('starRating');
        if (!starsContainer) return;
        starsContainer.innerHTML = '';
        for (let i = 1; i <= 5; i++) {
            const star = document.createElement('span');
            star.className = 'star';
            star.setAttribute('data-value', i);
            star.innerText = '★';
            star.onclick = function() {
                selectedRating = i;
                document.querySelectorAll('#starRating .star').forEach(s => {
                    if (parseInt(s.getAttribute('data-value')) <= selectedRating) {
                        s.classList.add('active');
                    } else {
                        s.classList.remove('active');
                    }
                });
            };
            starsContainer.appendChild(star);
        }
    }

    // ========== КАТАЛОГ ==========
    function initCategories() {
        const categories = [
            { id: 'all', name: 'Всё', icon: '📦' },
            { id: 'computers', name: 'Компьютеры', icon: '💻' },
            { id: 'services', name: 'Услуги', icon: '🔧' },
            { id: 'pc_build', name: 'Сборка', icon: '🛠️' },
            { id: 'websites', name: 'Сайты', icon: '🌐' },
            { id: 'components', name: 'Комплектующие', icon: '🔩' }
        ];
        const container = document.getElementById('categoryList');
        if (container) {
            container.innerHTML = categories.map(cat => `
                <div class="category-item ${cat.id === 'all' ? 'active' : ''}" data-category="${cat.id}" onclick="filterByCategory('${cat.id}')">
                    <span class="category-icon">${cat.icon}</span>
                    <span class="category-name">${cat.name}</span>
                </div>
            `).join('');
        }
    }

    function filterByCategory(category) {
        currentCategory = category;
        document.querySelectorAll('.category-item').forEach(item => {
            if (item.dataset.category === category) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        loadCatalog(currentSearchTerm);
    }

    function searchProducts() {
        const term = document.getElementById('searchInput').value;
        if (currentPage === 'catalog') {
            loadCatalog(term);
        } else {
            goToCatalog();
            loadCatalog(term);
        }
    }

    async function loadCatalog(searchTerm = '') {
        currentSearchTerm = searchTerm;
        let url = `/api/products?search=${encodeURIComponent(searchTerm)}`;
        if (currentCategory && currentCategory !== 'all') {
            url += `&category=${encodeURIComponent(currentCategory)}`;
        }
        const data = await fetchJSON(url);
        const catalogGrid = document.getElementById('catalogGrid');
        if (!catalogGrid) return;
        
        if (!data?.products?.length) {
            catalogGrid.innerHTML = '<div class="empty-cart" style="grid-column:1/-1; text-align:center;">Ничего не найдено</div>';
            return;
        }
        
        catalogGrid.innerHTML = data.products.map((product, idx) => {
            const hasDiscount = product.sale_price && product.sale_price > 0 && product.sale_price < product.price;
            const displayPrice = hasDiscount ? product.sale_price : product.price;
            const discountPercent = product.discount_percent || Math.round((1 - product.sale_price / product.price) * 100);
            return `
                <div class="product-card ${hasDiscount ? 'super-sale' : ''}" style="animation-delay: ${idx * 0.05}s" onclick="showProductModal(${product.id})">
                    ${hasDiscount ? `<div class="discount-badge">-${discountPercent}%</div>` : ''}
                    <img src="${product.image}" class="product-image" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'">
                    <div class="product-info">
                        <div class="product-title">${escapeHtml(product.name)}</div>
                        <div class="product-price ${hasDiscount ? 'super-price' : ''}">
                            ${hasDiscount ? 
                                `<span class="sale-price">${displayPrice.toLocaleString()} ₽</span> <span class="old-price">${product.price.toLocaleString()} ₽</span>` : 
                                `${displayPrice.toLocaleString()} ₽`
                            }
                        </div>
                        <button class="add-to-cart" onclick="event.stopPropagation(); addToCartWithAnimation(${product.id}, this)">В корзину</button>
                    </div>
                </div>
            `;
        }).join('');
    }    // ========== КОРЗИНА И ТОВАРЫ ==========
    async function showProductModal(id) {
        const product = await fetchJSON(`/api/product/${id}`);
        if (!product) return;
        currentProduct = product;
        const hasDiscount = product.sale_price && product.sale_price > 0 && product.sale_price < product.price;
        const displayPrice = hasDiscount ? product.sale_price : product.price;
        const discountPercent = product.discount_percent || Math.round((1 - product.sale_price / product.price) * 100);
        
        document.getElementById('modalTitle').textContent = product.name;
        document.getElementById('modalImage').src = product.image;
        document.getElementById('modalImage').onerror = function() { 
            this.src = 'https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'; 
        };
        document.getElementById('modalPrice').innerHTML = hasDiscount ? 
            `<span style="color:#e74c3c; font-size:1.5rem;">${displayPrice.toLocaleString()} ₽</span> 
             <span style="text-decoration:line-through; color:#666;">${product.price.toLocaleString()} ₽</span> 
             <span style="color:#27ae60;">(-${discountPercent}%)</span>` : 
            `${displayPrice.toLocaleString()} ₽`;
        document.getElementById('modalDescription').innerHTML = product.description + 
            (hasDiscount ? `<br><br><span style="color:#27ae60;">🔥 Скидка ${discountPercent}%!</span>` : '');
        document.getElementById('productModal').style.display = 'block';
    }

    function closeModal() {
        document.getElementById('productModal').style.display = 'none';
        currentProduct = null;
    }

    async function addToCart(id) {
        const result = await fetchJSON('/api/add-to-cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: id })
        });
        if (result?.success) {
            await updateCartDisplay();
            showNotification('Товар добавлен в корзину', 'success');
        }
    }

    async function addToCartWithAnimation(id, button) {
        animateToCart(button);
        await addToCart(id);
    }

    function addToCartFromModal() {
        if (currentProduct) {
            addToCart(currentProduct.id);
            closeModal();
        }
    }

    async function updateCartDisplay() {
        const data = await fetchJSON('/api/cart');
        if (!data) return;
        
        const cartCount = data.items.reduce((sum, item) => sum + item.quantity, 0);
        document.getElementById('cartCount').textContent = cartCount;
        
        const cartItemsDiv = document.getElementById('cartItems');
        if (data.items.length === 0) {
            cartItemsDiv.innerHTML = '<div class="empty-cart">Корзина пуста</div>';
        } else {
            cartItemsDiv.innerHTML = data.items.map(item => `
                <div class="cart-item">
                    <div>
                        <div class="cart-item-title">${escapeHtml(item.name)}</div>
                        <div style="color:#888; font-size:0.8rem;">${item.price.toLocaleString()} ₽</div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <button onclick="updateQuantity(${item.id}, ${item.quantity - 1})" 
                            style="width: 36px; height: 36px; background: #2a2a2a; border: none; color: white; font-size: 1.3rem; cursor: pointer; border-radius: 6px;">−</button>
                        <span style="min-width: 35px; text-align: center; font-size: 1rem;">${item.quantity}</span>
                        <button onclick="updateQuantity(${item.id}, ${item.quantity + 1})" 
                            style="width: 36px; height: 36px; background: #2a2a2a; border: none; color: white; font-size: 1.3rem; cursor: pointer; border-radius: 6px;">+</button>
                        <button onclick="removeFromCart(${item.id})" 
                            style="width: 36px; height: 36px; background: #e74c3c; border: none; color: white; font-size: 1.1rem; cursor: pointer; border-radius: 6px;">✕</button>
                    </div>
                </div>
            `).join('');
        }
        
        document.getElementById('cartSubtotal').textContent = data.subtotal.toLocaleString();
        document.getElementById('cartDiscount').textContent = data.discount.toLocaleString();
        document.getElementById('cartTotal').textContent = data.total.toLocaleString();
    }

    async function updateQuantity(id, quantity) {
        if (quantity <= 0) {
            await removeFromCart(id);
        } else {
            await fetchJSON('/api/update-cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: id, quantity: quantity })
            });
            await updateCartDisplay();
        }
    }

    async function removeFromCart(id) {
        await fetchJSON('/api/remove-from-cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: id })
        });
        await updateCartDisplay();
    }

    async function applyPromoCode() {
        if (!isLoggedIn) {
            showNotification('Войдите в аккаунт, чтобы использовать промокод', 'error');
            showAuthModal();
            return;
        }
        const code = document.getElementById('promoCodeInput').value.trim().toUpperCase();
        if (!code) {
            showNotification('Введите промокод', 'error');
            return;
        }
        const result = await fetchJSON('/api/apply-promo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ promo_code: code })
        });
        if (result?.success) {
            showNotification(`Скидка ${result.discount_text} применена!`, 'success');
            await updateCartDisplay();
        } else {
            showNotification(result?.message || 'Неверный промокод', 'error');
        }
    }

    function toggleCart() {
        const panel = document.getElementById('cartPanel');
        const overlay = document.getElementById('overlay');
        panel.classList.toggle('open');
        overlay.style.display = panel.classList.contains('open') ? 'block' : 'none';
        if (panel.classList.contains('open')) {
            updateCartDisplay();
        }
    }

    // ========== ОФОРМЛЕНИЕ ЗАКАЗА ==========
    function selectPayment(method) {
        selectedPayment = method;
        document.getElementById('cardOption').classList.remove('selected');
        document.getElementById('cashOption').classList.remove('selected');
        if (method === 'card') {
            document.getElementById('cardOption').classList.add('selected');
            document.getElementById('cardFields').classList.remove('hidden');
        } else {
            document.getElementById('cashOption').classList.add('selected');
            document.getElementById('cardFields').classList.add('hidden');
        }
    }

    let deliveryTimeout;
    const deliveryAddressInput = document.getElementById('deliveryAddress');
    if (deliveryAddressInput) {
        deliveryAddressInput.addEventListener('input', function() {
            clearTimeout(deliveryTimeout);
            const address = this.value;
            if (address.length > 10) {
                deliveryTimeout = setTimeout(async () => {
                    const data = await fetchJSON('/api/calculate-delivery', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ address: address })
                    });
                    if (data) {
                        document.getElementById('distanceInfo').innerHTML = `
                            📍 Расстояние: ${data.distance} км<br>
                            🚚 Срок доставки: ${data.delivery_period}<br>
                            📅 Ожидаемая дата: ${data.delivery_date}
                        `;
                        document.getElementById('checkoutDelivery').textContent = data.delivery_price ? data.delivery_price.toLocaleString() : '0';
                    }
                }, 500);
            }
        });
    }

    async function goToCheckout() {
        if (!isLoggedIn) {
            showNotification('Войдите в аккаунт для оформления заказа', 'error');
            showAuthModal();
            return;
        }
        const cartData = await fetchJSON('/api/cart');
        if (!cartData?.items?.length) {
            showNotification('Корзина пуста', 'error');
            return;
        }
        
        document.getElementById('checkoutSubtotal').textContent = cartData.subtotal.toLocaleString();
        document.getElementById('checkoutDiscount').textContent = cartData.discount.toLocaleString();
        document.getElementById('checkoutTotal').textContent = cartData.total.toLocaleString();
        document.getElementById('orderSummaryItems').innerHTML = cartData.items.map(item => `
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                <span>${escapeHtml(item.name)} x ${item.quantity}</span>
                <span>${item.total.toLocaleString()} ₽</span>
            </div>
        `).join('');
        
        if (currentUser) {
            document.getElementById('fullName').value = currentUser.full_name || '';
            document.getElementById('email').value = currentUser.email || '';
            document.getElementById('phone').value = currentUser.phone || '';
        }
        
        currentPage = 'checkout';
        document.querySelectorAll('#homePage, #catalogPage, #reviewsPage, #contactsPage, #profilePage, #adminPage, #infoPage, #checkoutPage').forEach(el => el.classList.add('hidden'));
        document.getElementById('checkoutPage').classList.remove('hidden');
        toggleCart();
    }

    const checkoutForm = document.getElementById('checkoutForm');
    if (checkoutForm) {
        checkoutForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const fullName = document.getElementById('fullName').value;
            const email = document.getElementById('email').value;
            const phone = document.getElementById('phone').value;
            const address = document.getElementById('deliveryAddress').value;
            
            if (!fullName || !email || !phone || !address) {
                showNotification('Заполните все обязательные поля', 'error');
                return;
            }
            if (!selectedPayment) {
                showNotification('Выберите способ оплаты', 'error');
                return;
            }
            
            const btn = document.querySelector('.submit-btn');
            btn.textContent = 'Обработка...';
            btn.disabled = true;
            
            const body = {
                full_name: fullName,
                email: email,
                phone: phone,
                delivery_address: address
            };
            
            if (selectedPayment === 'card') {
                const cardNumber = document.getElementById('cardNumber').value;
                const cardExpiry = document.getElementById('cardExpiry').value;
                const cardCvv = document.getElementById('cardCvv').value;
                const cardName = document.getElementById('cardName').value;
                
                if (!cardNumber || !cardExpiry || !cardCvv || !cardName) {
                    showNotification('Заполните все данные карты', 'error');
                    btn.textContent = 'Оформить заказ';
                    btn.disabled = false;
                    return;
                }
                if (cardNumber.replace(/\s/g, '').length < 16) {
                    showNotification('Введите корректный номер карты', 'error');
                    btn.textContent = 'Оформить заказ';
                    btn.disabled = false;
                    return;
                }
                if (cardCvv.length < 3) {
                    showNotification('Введите корректный CVV код', 'error');
                    btn.textContent = 'Оформить заказ';
                    btn.disabled = false;
                    return;
                }
                body.card_number = cardNumber.substring(12);
            }
            
            const result = await fetchJSON(`/api/checkout-${selectedPayment}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            showNotification(result.message, result.success !== false ? 'success' : 'error');
            if (result.success !== false) {
                goToHome();
                await updateCartDisplay();
                selectedPayment = null;
                document.getElementById('cardOption').classList.remove('selected');
                document.getElementById('cashOption').classList.remove('selected');
                document.getElementById('cardFields').classList.add('hidden');
            }
            btn.textContent = 'Оформить заказ';
            btn.disabled = false;
        });
    }

    // ========== АДМИН-ПАНЕЛЬ ==========
    function switchAdminTab(tab) {
        document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
        
        const tabs = ['products', 'news', 'promocodes', 'reviews', 'orders', 'users'];
        const index = tabs.indexOf(tab);
        if (index !== -1) {
            document.querySelectorAll('.admin-tab')[index].classList.add('active');
            document.getElementById(`admin${tab.charAt(0).toUpperCase() + tab.slice(1)}`).classList.add('active');
            if (tab === 'products') loadAdminProducts();
            else if (tab === 'news') loadAdminNews();
            else if (tab === 'promocodes') loadAdminPromocodes();
            else if (tab === 'reviews') loadAdminReviews();
            else if (tab === 'orders') loadAdminOrders();
            else if (tab === 'users') loadAdminUsers();
        }
    }

    async function loadAdminProducts() {
        const data = await fetchJSON('/api/admin/products');
        const container = document.getElementById('productsList');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">Нет услуг</div>';
            return;
        }
        container.innerHTML = `
            <div class="admin-products-grid">
                ${data.map(p => `
                    <div class="admin-product-card">
                        <div class="admin-product-info">
                            <div class="admin-product-name">${escapeHtml(p.name)}</div>
                            <div class="admin-product-price">
                                ${p.sale_price ? 
                                    `${p.sale_price.toLocaleString()} ₽ (было ${p.price.toLocaleString()} ₽, скидка ${p.discount_percent}%)` : 
                                    `${p.price.toLocaleString()} ₽`
                                }
                                ${p.sale_price ? ' 🔥' : ''}
                            </div>
                            <div class="admin-product-price">Категория: ${p.category || 'services'}</div>
                        </div>
                        <div class="admin-product-actions">
                            <button class="edit-btn" onclick="editProduct(${p.id})">✏️</button>
                            <button class="delete-btn" onclick="deleteProduct(${p.id})">🗑️</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async function addProduct() {
        const name = document.getElementById('productName').value;
        const price = document.getElementById('productPrice').value;
        if (!name || !price) {
            showNotification('Заполните название и цену', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('name', name);
        formData.append('price', price);
        formData.append('sale_price', document.getElementById('productSalePrice').value || '');
        formData.append('discount_percent', document.getElementById('productDiscountPercent').value || '0');
        formData.append('description', document.getElementById('productDescription').value);
        formData.append('category', document.getElementById('productCategory').value);
        const imageFile = document.getElementById('productImage');
        if (imageFile.files[0]) formData.append('image', imageFile.files[0]);
        
        const result = await fetch('/api/admin/add-product', { method: 'POST', body: formData }).then(r => r.json());
        if (result.success) {
            showNotification('Услуга добавлена', 'success');
            document.getElementById('productName').value = '';
            document.getElementById('productPrice').value = '';
            document.getElementById('productSalePrice').value = '';
            document.getElementById('productDiscountPercent').value = '';
            document.getElementById('productDescription').value = '';
            document.getElementById('productImage').value = '';
            await loadAdminProducts();
            await loadCatalog();
        } else {
            showNotification(result.message || 'Ошибка при добавлении', 'error');
        }
    }

    async function editProduct(id) {
        const newName = prompt('Введите новое название:');
        if (!newName) return;
        const newPrice = prompt('Введите обычную цену:');
        if (!newPrice) return;
        const newSalePrice = prompt('Введите цену со скидкой (оставьте пустым если скидки нет):');
        const newDiscountPercent = prompt('Введите процент скидки:');
        const newDesc = prompt('Введите новое описание:');
        const newCategory = prompt('Введите категорию (computers/services/pc_build/websites/components):', 'services');
        
        const result = await fetchJSON('/api/admin/edit-product', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: id,
                name: newName,
                price: parseInt(newPrice),
                sale_price: newSalePrice ? parseInt(newSalePrice) : null,
                discount_percent: parseInt(newDiscountPercent) || 0,
                description: newDesc,
                category: newCategory
            })
        });
        if (result.success) {
            showNotification('Услуга обновлена', 'success');
            await loadAdminProducts();
            await loadCatalog();
        } else {
            showNotification(result.message || 'Ошибка', 'error');
        }
    }

    async function deleteProduct(id) {
        if (confirm('Удалить услугу?')) {
            const result = await fetchJSON('/api/admin/delete-product', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            });
            if (result.success) {
                showNotification('Услуга удалена', 'success');
                await loadAdminProducts();
                await loadCatalog();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }    async function loadAdminNews() {
        const data = await fetchJSON('/api/admin/news');
        const container = document.getElementById('newsList');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">Нет новостей</div>';
            return;
        }
        container.innerHTML = `
            <div class="admin-news-list">
                ${data.map(n => `
                    <div class="admin-news-card">
                        <div class="admin-news-info">
                            <div class="admin-news-title">${escapeHtml(n.title)}</div>
                            <div class="admin-news-date">${n.date}</div>
                        </div>
                        <div class="admin-news-actions">
                            <button class="edit-btn" onclick="editNews(${n.id})">✏️</button>
                            <button class="delete-btn" onclick="deleteNews(${n.id})">🗑️</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async function addNews() {
        const title = document.getElementById('newsTitle').value;
        const text = document.getElementById('newsShortText').value;
        if (!title || !text) {
            showNotification('Заполните заголовок и краткий текст новости', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('title', title);
        formData.append('text', text);
        formData.append('fullText', document.getElementById('newsFullText').value);
        const imageFile = document.getElementById('newsImage');
        if (imageFile.files[0]) formData.append('image', imageFile.files[0]);
        const videoFile = document.getElementById('newsVideo');
        if (videoFile.files[0]) formData.append('video', videoFile.files[0]);
        const videoUrl = document.getElementById('newsVideoUrl').value;
        if (videoUrl) formData.append('video_url', videoUrl);
        
        const result = await fetch('/api/admin/add-news', { method: 'POST', body: formData }).then(r => r.json());
        if (result.success) {
            showNotification('Новость добавлена', 'success');
            document.getElementById('newsTitle').value = '';
            document.getElementById('newsShortText').value = '';
            document.getElementById('newsFullText').value = '';
            document.getElementById('newsImage').value = '';
            document.getElementById('newsVideo').value = '';
            document.getElementById('newsVideoUrl').value = '';
            await loadAdminNews();
            await loadNews();
        } else {
            showNotification(result.message || 'Ошибка при добавлении новости', 'error');
        }
    }

    async function editNews(id) {
        const newTitle = prompt('Введите новый заголовок:');
        if (!newTitle) return;
        const newText = prompt('Введите новый краткий текст:');
        if (!newText) return;
        const newFullText = prompt('Введите новый полный текст:');
        if (!newFullText) return;
        
        const result = await fetchJSON('/api/admin/edit-news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, title: newTitle, text: newText, fullText: newFullText })
        });
        if (result.success) {
            showNotification('Новость обновлена', 'success');
            await loadAdminNews();
            await loadNews();
        } else {
            showNotification(result.message || 'Ошибка', 'error');
        }
    }

    async function deleteNews(id) {
        if (confirm('Удалить новость?')) {
            const result = await fetchJSON('/api/admin/delete-news', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            });
            if (result.success) {
                showNotification('Новость удалена', 'success');
                await loadAdminNews();
                await loadNews();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    async function loadAdminPromocodes() {
        const data = await fetchJSON('/api/admin/promocodes');
        const container = document.getElementById('promocodesList');
        const promocodesArray = Object.entries(data || {});
        if (promocodesArray.length === 0) {
            container.innerHTML = '<div class="empty-cart">Нет промокодов</div>';
            return;
        }
        container.innerHTML = `
            <div class="admin-promocodes-list">
                ${promocodesArray.map(([code, p]) => `
                    <div class="admin-promocode-card">
                        <div class="admin-promocode-info">
                            <div class="admin-promocode-code">${code}</div>
                            <div class="admin-promocode-details">
                                Скидка: ${p.type === 'percent' ? p.discount + '%' : p.discount + ' ₽'}
                                <br>Условие: ${getPromoConditionText(p.conditions)}
                                <br>Использован: ${p.used_count || 0} / ${p.max_uses === Infinity ? '∞' : p.max_uses} раз
                                <span class="admin-promocode-status ${p.active ? 'active' : 'inactive'}">${p.active ? 'Активен' : 'Отключен'}</span>
                            </div>
                        </div>
                        <div class="admin-promocode-actions">
                            <button class="toggle-btn" onclick="togglePromocode('${code}')">${p.active ? 'Отключить' : 'Включить'}</button>
                            <button class="edit-btn" onclick="editPromocode('${code}')">✏️</button>
                            <button class="delete-btn" onclick="deletePromocode('${code}')">🗑️</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function getPromoConditionText(conditions) {
        if (!conditions) return 'На все товары';
        switch (conditions.apply_to) {
            case 'all': return 'На все товары';
            case 'categories': return `На категории: ${conditions.categories?.join(', ') || 'нет'}`;
            case 'specific_products': return `На товары: ${conditions.products?.length || 0} шт`;
            default: return 'На все товары';
        }
    }

    async function loadProductsForPromo() {
        const data = await fetchJSON('/api/admin/products-all');
        allProducts = data || [];
        const select = document.getElementById('promocodeProducts');
        if (select) {
            select.innerHTML = allProducts.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
        }
    }

    document.getElementById('promocodeApplyTo')?.addEventListener('change', function() {
        const val = this.value;
        document.getElementById('promocodeCategoriesDiv').style.display = val === 'categories' ? 'block' : 'none';
        document.getElementById('promocodeProductsDiv').style.display = val === 'specific_products' ? 'block' : 'none';
        if (val === 'specific_products') loadProductsForPromo();
    });

    async function addPromocode() {
        const code = document.getElementById('promocodeCode').value.trim().toUpperCase();
        const type = document.getElementById('promocodeType').value;
        const discount = parseInt(document.getElementById('promocodeDiscount').value);
        const minOrder = parseInt(document.getElementById('promocodeMinOrder').value) || 0;
        const maxUses = parseInt(document.getElementById('promocodeMaxUses').value) || 0;
        const applyTo = document.getElementById('promocodeApplyTo').value;
        let categories = [], products = [];
        
        if (applyTo === 'categories') {
            categories = Array.from(document.getElementById('promocodeCategories').selectedOptions).map(o => o.value);
        } else if (applyTo === 'specific_products') {
            products = Array.from(document.getElementById('promocodeProducts').selectedOptions).map(o => parseInt(o.value));
        }
        
        if (!code) {
            showNotification('Введите код промокода', 'error');
            return;
        }
        if (!discount || discount <= 0) {
            showNotification('Введите корректную величину скидки', 'error');
            return;
        }
        if (type === 'percent' && discount > 100) {
            showNotification('Процент скидки не может превышать 100%', 'error');
            return;
        }
        
        const result = await fetchJSON('/api/admin/add-promocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                type: type,
                discount: discount,
                min_order: minOrder,
                max_uses: maxUses,
                apply_to: applyTo,
                categories: categories,
                products: products
            })
        });
        if (result.success) {
            showNotification('Промокод добавлен', 'success');
            document.getElementById('promocodeCode').value = '';
            document.getElementById('promocodeDiscount').value = '';
            document.getElementById('promocodeMinOrder').value = '';
            document.getElementById('promocodeMaxUses').value = '';
            await loadAdminPromocodes();
            await loadPromoCodes();
        } else {
            showNotification(result.message || 'Ошибка при добавлении', 'error');
        }
    }

    async function editPromocode(code) {
        const newDiscount = prompt('Введите новую величину скидки:');
        if (!newDiscount) return;
        const newType = prompt('Введите тип скидки (percent/fixed):', 'percent');
        if (!newType) return;
        
        const result = await fetchJSON('/api/admin/edit-promocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                discount: parseInt(newDiscount),
                type: newType,
                active: true
            })
        });
        if (result.success) {
            showNotification('Промокод обновлён', 'success');
            await loadAdminPromocodes();
            await loadPromoCodes();
        } else {
            showNotification(result.message || 'Ошибка', 'error');
        }
    }

    async function togglePromocode(code) {
        const result = await fetchJSON('/api/admin/toggle-promocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code })
        });
        if (result.success) {
            showNotification(result.message, 'success');
            await loadAdminPromocodes();
            await loadPromoCodes();
        } else {
            showNotification(result.message || 'Ошибка', 'error');
        }
    }

    async function deletePromocode(code) {
        if (confirm(`Удалить промокод ${code}?`)) {
            const result = await fetchJSON('/api/admin/delete-promocode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            });
            if (result.success) {
                showNotification('Промокод удалён', 'success');
                await loadAdminPromocodes();
                await loadPromoCodes();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    async function loadAdminReviews() {
        const data = await fetchJSON('/api/reviews');
        const container = document.getElementById('adminReviewsList');
        if (!data?.length) {
            container.innerHTML = '<div class="empty-cart">Нет отзывов</div>';
            return;
        }
        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr><th>Автор</th><th>Оценка</th><th>Текст</th><th>Дата</th><th>Действия</th></tr>
                </thead>
                <tbody>
                    ${data.map((r, idx) => `
                        <tr>
                            <td>${escapeHtml(r.name)}</td>
                            <td>${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</td>
                            <td>${escapeHtml(r.text.substring(0, 50))}${r.text.length > 50 ? '...' : ''}</td>
                            <td>${r.date}</td>
                            <td><button class="delete-btn" onclick="deleteReview(${idx})">🗑️</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    async function loadAdminOrders() {
        const data = await fetchJSON('/api/admin/orders');
        const container = document.getElementById('adminOrdersList');
        if (!data || Object.keys(data).length === 0) {
            container.innerHTML = '<div class="empty-cart">Нет заказов</div>';
            return;
        }
        let html = '';
        for (const [email, userOrders] of Object.entries(data)) {
            html += `<h4 style="margin-top: 1rem; color: #27ae60;">Пользователь: ${escapeHtml(email)}</h4>`;
            userOrders.forEach(order => {
                html += `
                    <div class="order-card" style="margin-bottom: 1rem;">
                        <div class="order-header">
                            <span class="order-number">Заказ #${order.order_number}</span>
                            <span class="order-status ${order.status || 'pending'}">${getStatusText(order.status)}</span>
                            <span class="order-date">${order.datetime}</span>
                        </div>
                        <div class="order-items">
                            ${order.items.map(item => `
                                <div class="order-item">
                                    <span>${escapeHtml(item.name)} x ${item.quantity}</span>
                                    <span>${item.total.toLocaleString()} ₽</span>
                                </div>
                            `).join('')}
                        </div>
                        <div class="order-total">Итого: ${order.total.toLocaleString()} ₽</div>
                        <div style="font-size: 0.8rem; color: #888;">Доставка: ${escapeHtml(order.delivery_address)}</div>
                        <div style="margin-top: 0.5rem;">
                            <select id="status_${order.order_number}" class="ban-select" style="width: auto;">
                                <option value="pending" ${order.status === 'pending' ? 'selected' : ''}>Ожидает</option>
                                <option value="paid" ${order.status === 'paid' ? 'selected' : ''}>Оплачен</option>
                                <option value="processing" ${order.status === 'processing' ? 'selected' : ''}>В обработке</option>
                                <option value="shipped" ${order.status === 'shipped' ? 'selected' : ''}>Отправлен</option>
                                <option value="delivered" ${order.status === 'delivered' ? 'selected' : ''}>Доставлен</option>
                                <option value="cancelled" ${order.status === 'cancelled' ? 'selected' : ''}>Отменён</option>
                            </select>
                            <button class="edit-btn" onclick="updateOrderStatus('${order.order_number}', document.getElementById('status_${order.order_number}').value)">Обновить статус</button>
                        </div>
                    </div>
                `;
            });
        }
        container.innerHTML = html;
    }

    async function updateOrderStatus(orderNumber, newStatus) {
        const result = await fetchJSON('/api/admin/orders/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_number: orderNumber, status: newStatus })
        });
        if (result.success) {
            showNotification(result.message, 'success');
            await loadAdminOrders();
        } else {
            showNotification(result.message || 'Ошибка', 'error');
        }
    }

    async function loadAdminUsers() {
        const data = await fetchJSON('/api/admin/users');
        const container = document.getElementById('usersList');
        const usersArray = Object.values(data || {});
        usersArray.sort((a, b) => (b.registered_at || '').localeCompare(a.registered_at || ''));
        
        if (usersArray.length === 0) {
            container.innerHTML = '<div class="empty-cart">Нет пользователей</div>';
            return;
        }
        
        container.innerHTML = `
            <div class="admin-users-list">
                ${usersArray.map(u => {
                    const banSelectId = `banSelect_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}`;
                    return `
                        <div class="admin-user-card">
                            <div class="admin-user-info">
                                <div class="admin-user-email">${escapeHtml(u.email)}</div>
                                <div class="admin-user-details">
                                    ФИО: ${escapeHtml(u.full_name || '-')} | 
                                    Телефон: ${escapeHtml(u.phone || '-')} | 
                                    Регистрация: ${u.registered_at || '-'}
                                    ${u.is_admin ? ' | 👑 Администратор' : ''}
                                </div>
                            </div>
                            <div class="admin-user-actions">
                                ${!u.is_admin ? 
                                    `<button class="edit-btn" onclick="makeAdmin('${u.email}')">Сделать админом</button>` : 
                                    `<button class="delete-btn" onclick="removeAdmin('${u.email}')">Снять админа</button>`
                                }
                                <select id="${banSelectId}" class="ban-select">
                                    <option value="">Забанить</option>
                                    <option value="1">На 1 минуту</option>
                                    <option value="5">На 5 минут</option>
                                    <option value="10">На 10 минут</option>
                                    <option value="30">На 30 минут</option>
                                    <option value="60">На 1 час</option>
                                    <option value="300">На 5 часов</option>
                                    <option value="1440">На 1 день</option>
                                    <option value="10080">На неделю</option>
                                    <option value="525600">На год</option>
                                </select>
                                <input type="text" id="banReason_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}" class="ban-reason-input" placeholder="Причина бана" value="Нарушение правил">
                                <input type="text" id="banMessage_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}" class="ban-message-input" placeholder="Сообщение от админа" value="Обратитесь к администратору">
                                <button class="ban-btn" onclick="banUser('${u.email}', document.getElementById('${banSelectId}').value, document.getElementById('banReason_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}').value, document.getElementById('banMessage_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}').value)">🚫 Бан</button>
                                <button class="unban-btn" onclick="unbanUser('${u.email}')">Разбанить</button>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    async function makeAdmin(email) {
        if (confirm(`Сделать ${email} администратором?`)) {
            const result = await fetchJSON('/api/admin/make-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            if (result.success) {
                showNotification('Пользователь стал администратором', 'success');
                await loadAdminUsers();
                if (email === currentUser?.email) await checkAuthStatus();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    async function removeAdmin(email) {
        if (email === currentUser?.email) {
            showNotification('Нельзя снять права администратора с самого себя', 'error');
            return;
        }
        if (confirm(`Снять права администратора с ${email}?`)) {
            const result = await fetchJSON('/api/admin/remove-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            if (result.success) {
                showNotification('Права администратора сняты', 'success');
                await loadAdminUsers();
                if (email === currentUser?.email) await checkAuthStatus();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    async function banUser(email, minutes, reason, message) {
        if (!minutes || minutes === "") {
            showNotification('Выберите срок бана', 'error');
            return;
        }
        if (!reason || reason.trim() === "") {
            showNotification('Укажите причину бана', 'error');
            return;
        }
        if (!message || message.trim() === "") {
            showNotification('Укажите сообщение для пользователя', 'error');
            return;
        }
        if (confirm(`Забанить пользователя ${email} на ${minutes} минут(ы)?\nПричина: ${reason}\nСообщение: ${message}`)) {
            const result = await fetchJSON('/api/admin/ban-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, duration_minutes: parseInt(minutes), reason: reason, message: message })
            });
            if (result.success) {
                showNotification(result.message, 'success');
                await loadAdminUsers();
                if (email === currentUser?.email) window.location.href = '/';
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    async function unbanUser(email) {
        if (confirm(`Снять бан с пользователя ${email}?`)) {
            const result = await fetchJSON('/api/admin/unban-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            if (result.success) {
                showNotification('Бан снят', 'success');
                await loadAdminUsers();
                if (email === currentUser?.email) await checkAuthStatus();
            } else {
                showNotification(result.message || 'Ошибка', 'error');
            }
        }
    }

    // ========== ЧАТ ==========
    function toggleChat() {
        const win = document.getElementById('chatWindow');
        win.classList.toggle('open');
        if (win.classList.contains('open')) {
            if (chatResetTimer) clearTimeout(chatResetTimer);
            const btnsContainer = document.getElementById('chatButtons');
            if (consultationButtons) {
                btnsContainer.innerHTML = `
                    <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
                    <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
                    <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
                    <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
                    <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
                `;
                consultationButtons = false;
            }
        }
    }

    function addThankYouAndReset() {
        const messagesArea = document.getElementById('chatMessagesArea');
        const thankYouMsg = document.createElement('div');
        thankYouMsg.className = 'chat-message system';
        thankYouMsg.innerHTML = 'Спасибо что выбрали нас! С уважением команда ZETTA.';
        messagesArea.appendChild(thankYouMsg);
        messagesArea.scrollTop = messagesArea.scrollHeight;
        
        if (chatResetTimer) clearTimeout(chatResetTimer);
        chatResetTimer = setTimeout(() => {
            const btnsContainer = document.getElementById('chatButtons');
            btnsContainer.innerHTML = `
                <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
                <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
                <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
                <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
                <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
            `;
            consultationButtons = false;
            chatResetTimer = null;
        }, 5000);
    }

    async function askQuestion(type) {
        if (!isLoggedIn) {
            showNotification('Пожалуйста, войдите в аккаунт для использования чата', 'error');
            showAuthModal();
            return;
        }
        
        const messagesArea = document.getElementById('chatMessagesArea');
        let responseText = '';
        let showThankYou = false;
        
        if (type === 'payment') {
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = '💳 Проблемы с оплатой?';
            messagesArea.appendChild(userMsg);
            
            const result = await fetchJSON('/api/chat/send-payment-question', { method: 'POST' });
            responseText = result?.response || 'Оплата принимается наличными или переводом на карту.';
            showThankYou = true;
        } else if (type === 'site_time') {
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = '⏱️ Срок создания сайта?';
            messagesArea.appendChild(userMsg);
            
            const result = await fetchJSON('/api/chat/site-creation-time', { method: 'POST' });
            responseText = result?.response || 'Обычно 1-2 недели.';
            showThankYou = true;
        } else if (type === 'consultation') {
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = '📞 Хочу проконсультироваться!';
            messagesArea.appendChild(userMsg);
            
            const btnsContainer = document.getElementById('chatButtons');
            btnsContainer.innerHTML = `
                <button class="chat-question-btn" onclick="selectConsultant('system_admin')">🖥️ Системный администратор</button>
                <button class="chat-question-btn" onclick="selectConsultant('director')">👔 Генеральный директор</button>
                <button class="chat-question-btn" onclick="selectConsultant('manager')">📋 Менеджер</button>
                <button class="chat-question-btn" onclick="resetConsultation()">🔙 Назад</button>
            `;
            consultationButtons = true;
            messagesArea.scrollTop = messagesArea.scrollHeight;
            return;
        } else if (type === 'cooperation') {
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = '🤝 Сотрудничество и реклама!';
            messagesArea.appendChild(userMsg);
            
            const result = await fetchJSON('/api/chat/cooperation', { method: 'POST' });
            responseText = result?.response || 'Пишите на почту vaincode@mail.ru';
            showThankYou = true;
        } else if (type === 'operator') {
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = '👨‍💼 Помощь оператора!';
            messagesArea.appendChild(userMsg);
            
            const result = await fetchJSON('/api/chat/send-operator-request', { method: 'POST' });
            responseText = result?.message || 'Заявка отправлена! Оператор свяжется.';
            showThankYou = true;
        }
        
        if (responseText) {
            setTimeout(() => {
                const adminMsg = document.createElement('div');
                adminMsg.className = 'chat-message admin';
                adminMsg.innerHTML = responseText;
                messagesArea.appendChild(adminMsg);
                messagesArea.scrollTop = messagesArea.scrollHeight;
                if (showThankYou) addThankYouAndReset();
            }, 300);
        }
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    async function selectConsultant(choice) {
        const messagesArea = document.getElementById('chatMessagesArea');
        let choiceText = '';
        if (choice === 'system_admin') choiceText = 'Системный администратор';
        else if (choice === 'director') choiceText = 'Генеральный директор';
        else if (choice === 'manager') choiceText = 'Менеджер';
        
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user';
        userMsg.innerHTML = `📞 Хочу проконсультироваться с ${choiceText}`;
        messagesArea.appendChild(userMsg);
        
        const result = await fetchJSON('/api/chat/consultation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ choice: choice })
        });
        
        if (result?.success) {
            setTimeout(() => {
                const adminMsg = document.createElement('div');
                adminMsg.className = 'chat-message admin';
                adminMsg.innerHTML = result.response;
                messagesArea.appendChild(adminMsg);
                messagesArea.scrollTop = messagesArea.scrollHeight;
                addThankYouAndReset();
            }, 300);
        }
    }

    function resetConsultation() {
        const messagesArea = document.getElementById('chatMessagesArea');
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user';
        userMsg.innerHTML = '🔙 Назад к вопросам';
        messagesArea.appendChild(userMsg);
        
        setTimeout(() => {
            const btnsContainer = document.getElementById('chatButtons');
            btnsContainer.innerHTML = `
                <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
                <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
                <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
                <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
                <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
            `;
            consultationButtons = false;
        }, 300);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // ========== ОБРАТНАЯ СВЯЗЬ ==========
    function openFeedbackModal() {
        document.getElementById('feedbackModal').style.display = 'block';
        document.getElementById('feedbackMessage').value = '';
    }

    function closeFeedbackModal() {
        document.getElementById('feedbackModal').style.display = 'none';
    }

    async function sendFeedback() {
        const message = document.getElementById('feedbackMessage').value.trim();
        if (!message) {
            showNotification('Введите сообщение', 'error');
            return;
        }
        if (message.length < 10) {
            showNotification('Сообщение должно содержать не менее 10 символов', 'error');
            return;
        }
        const result = await fetchJSON('/api/send-feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        if (result.success) {
            showNotification(result.message, 'success');
            closeFeedbackModal();
        } else {
            showNotification(result.message || 'Ошибка при отправке', 'error');
        }
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ==========
    document.addEventListener('DOMContentLoaded', async function() {
        initCategories();
        initStars();
        await checkAuthStatus();
        await loadNews();
        await loadPromoCodes();
        await loadHomeReviews();
        await loadVlog();
        
        // Форматирование полей карты
        const cardNumber = document.getElementById('cardNumber');
        if (cardNumber) {
            cardNumber.addEventListener('input', function(e) {
                let value = e.target.value.replace(/\D/g, '');
                if (value.length > 16) value = value.slice(0, 16);
                value = value.replace(/(\d{4})/g, '$1 ').trim();
                e.target.value = value;
            });
        }
        
        const cardExpiry = document.getElementById('cardExpiry');
        if (cardExpiry) {
            cardExpiry.addEventListener('input', function(e) {
                let value = e.target.value.replace(/\D/g, '');
                if (value.length > 4) value = value.slice(0, 4);
                if (value.length > 2) value = value.slice(0, 2) + '/' + value.slice(2);
                e.target.value = value;
            });
        }
        
        const cardCvv = document.getElementById('cardCvv');
        if (cardCvv) {
            cardCvv.addEventListener('input', function(e) {
                e.target.value = e.target.value.replace(/\D/g, '').slice(0, 3);
            });
        }
        
        // Анимация для элементов при скролле
        const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.animationPlayState = 'running';
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);
        
        document.querySelectorAll('.team-card, .product-card, .news-card, .promo-card').forEach(el => {
            el.style.animationPlayState = 'paused';
            observer.observe(el);
        });
        
        // Обработка Enter в поиске
        document.getElementById('searchInput')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') searchProducts();
        });
    });
</script>
</body>
</html>
'''@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Создание администратора по умолчанию
    users = load_users()
    admin_email = 'admin@zetta.ru'
    admin_exists = False

    for email, user_data in users.items():
        if user_data.get('is_admin', False):
            admin_exists = True
            print(f"Админ уже существует: {email}")
            break

    if not admin_exists:
        users[admin_email] = {
            'email': admin_email,
            'password': hash_password('admin123'),
            'full_name': 'Администратор Zetta',
            'phone': '+7 (999) 999-99-99',
            'registered_at': datetime.now().isoformat(),
            'addresses': [],
            'profile_complete': True,
            'is_admin': True,
            'bonus_points': 0,
            'orders_count': 0,
            'total_spent': 0
        }
        save_users(users)
        print("=" * 60)
        print("АДМИН ZETTA СОЗДАН:")
        print(f"Email: {admin_email}")
        print(f"Пароль: admin123")
        print("=" * 60)

    # Создание резервной копии при запуске
    backup_all_data()

    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"\n🚀 Запуск сервера Zetta на http://{host}:{port}")
    print(f"📱 Открыть на телефоне: http://<IP-адрес>:{port}")
    print("=" * 60)

    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"Запуск сервера на {host}:{port}")
    app.run(host=host, port=port, debug=False)
