import os
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
from psycopg_pool import ConnectionPool
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)
print("=" * 60)
print("✅ ПРИЛОЖЕНИЕ ZETTA УСПЕШНО ЗАГРУЖЕНО")
print("=" * 60)
app.secret_key = 'secret_key_for_zetta_12345_secure_2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Создаем папку для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Конфигурация PostgreSQL
DATABASE_URL = psql 'postgresql://gen_user:nb7pNMZs059Cv*@103.88.242.52:5432/default_db'

# Создаем пул соединений
db_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10)


def get_db_connection():
    """Получить соединение с базой данных из пула"""
    return db_pool.getconn()


def return_db_connection(conn):
    """Вернуть соединение обратно в пул"""
    db_pool.putconn(conn)


def init_db():
    """Инициализация базы данных: создание всех необходимых таблиц"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email VARCHAR(255) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            phone VARCHAR(50),
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            profile_complete BOOLEAN DEFAULT FALSE,
            is_admin BOOLEAN DEFAULT FALSE,
            personal_discount_type VARCHAR(20),
            personal_discount_value INTEGER
        )
    """)

    # Таблица отзывов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            rating INTEGER NOT NULL,
            text TEXT NOT NULL,
            date VARCHAR(50) NOT NULL
        )
    """)

    # Таблица заказов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            order_number VARCHAR(50) NOT NULL,
            user_email VARCHAR(255),
            order_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица продуктов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price INTEGER NOT NULL,
            sale_price INTEGER,
            discount_percent INTEGER DEFAULT 0,
            description TEXT,
            image VARCHAR(500),
            category VARCHAR(100) DEFAULT 'services'
        )
    """)

    # Таблица новостей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            date VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            text TEXT NOT NULL,
            fullText TEXT,
            image VARCHAR(500)
        )
    """)

    # Таблица промокодов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code VARCHAR(50) PRIMARY KEY,
            discount INTEGER NOT NULL,
            type VARCHAR(20) NOT NULL,
            active BOOLEAN DEFAULT TRUE
        )
    """)

    # Таблица использованных промокодов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS used_promocodes (
            id SERIAL PRIMARY KEY,
            user_email VARCHAR(255) NOT NULL,
            promo_code VARCHAR(50) NOT NULL,
            order_number VARCHAR(50),
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица забаненных пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            email VARCHAR(255) PRIMARY KEY,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ban_until TIMESTAMP,
            duration_minutes INTEGER,
            reason TEXT,
            message TEXT
        )
    """)

    # Таблица верификационных кодов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            email VARCHAR(255) PRIMARY KEY,
            code VARCHAR(10) NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL,
            full_name VARCHAR(255),
            phone VARCHAR(50),
            password VARCHAR(255)
        )
    """)

    # Таблица кодов сброса пароля
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_codes (
            email VARCHAR(255) PRIMARY KEY,
            code VARCHAR(10) NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL
        )
    """)

    # Таблица влога
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vlog (
            id INTEGER PRIMARY KEY DEFAULT 1,
            text TEXT NOT NULL
        )
    """)

    # Таблица сообщений чата
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            user_email VARCHAR(255) NOT NULL,
            message TEXT,
            type VARCHAR(20),
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Добавляем администратора, если его нет
    cur.execute("SELECT * FROM users WHERE email = %s", ('admin@zetta.ru',))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (email, password, full_name, phone, profile_complete, is_admin)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('admin@zetta.ru', 'admin123', 'Администратор Zetta', '+7 (999) 999-99-99', True, True))

    # Добавляем дефолтные продукты, если их нет
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        default_products = [
            (1, '💻 Сборка ПК "Игровой Флагман"', 89990, 79990, 11,
             'Сборка игрового компьютера с установкой Windows и драйверов. Intel i7, RTX 4060, 32GB RAM, 1TB SSD.',
             '/static/uploads/gaming_pc.jpg', 'pc_build'),
            (2, '🔧 Услуга: Настройка ПК + Антивирус', 2990, 1990, 33,
             'Профессиональная настройка операционной системы, установка антивируса, оптимизация реестра, удаление мусора.',
             '/static/uploads/pc_setup.jpg', 'services'),
            (3, '🌐 Сайт-визитка под ключ', 14990, 9990, 33,
             'Создание современного сайта-визитки с адаптивным дизайном, формой обратной связи и базовой SEO-оптимизацией.',
             '/static/uploads/website.jpg', 'websites'),
            (4, '🎮 Компьютер "Стандарт" собранный', 59990, None, 0,
             'Готовый системный блок для офиса и дома. Intel i5, 16GB RAM, 512GB SSD, Windows 11 установлена.',
             '/static/uploads/standard_pc.jpg', 'computers'),
            (5, '🛠️ Процессор Intel Core i7-13700K', 39990, 34990, 12,
             'Новый процессор в оригинальной упаковке. Установка и настройка в подарок при покупке сборки ПК.',
             '/static/uploads/cpu.jpg', 'components'),
            (6, '🛠️ Видеокарта RTX 4070 Ti', 79990, None, 0,
             'Мощная видеокарта для игр и работы. Гарантия 3 года. Установка при покупке сборки - бесплатно.',
             '/static/uploads/gpu.jpg', 'components'),
            (7, '🔧 Обслуживание ПК на месяц', 4990, 3990, 20,
             'Абонемент на обслуживание компьютера: удалённая помощь, диагностика, настройка ПО, установка обновлений.',
             '/static/uploads/service.jpg', 'services'),
            (8, '🌐 Интернет-магазин под ключ', 49990, 39990, 20,
             'Полноценный интернет-магазин с корзиной, личным кабинетом, интеграцией с платежными системами.',
             '/static/uploads/ecommerce.jpg', 'websites'),
        ]
        for p in default_products:
            cur.execute("""
                INSERT INTO products (id, name, price, sale_price, discount_percent, description, image, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, p)

    # Добавляем дефолтные новости
    cur.execute("SELECT COUNT(*) FROM news")
    if cur.fetchone()[0] == 0:
        default_news = [
            (1, '01.06.2026', '🔥 Zetta запускает летнюю распродажу 🔥', 'Скидки до 50% на сборку ПК и создание сайтов!',
             'Компания Zetta объявляет о грандиозной летней распродаже! Скидки достигают 50% на сборку игровых компьютеров, создание сайтов и IT-обслуживание. Торопитесь, предложение ограничено!',
             '/static/uploads/sale.jpg'),
            (2, '28.05.2026', 'Новая услуга - Корпоративное обслуживание',
             'Абонентское обслуживание компьютеров для бизнеса',
             'Zetta запускает услугу корпоративного обслуживания! Полный цикл IT-поддержки для компаний: обслуживание ПК, серверов, настройка сети и техническая поддержка сотрудников.',
             '/static/uploads/business.jpg'),
        ]
        for n in default_news:
            cur.execute("""
                INSERT INTO news (id, date, title, text, fullText, image)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, n)

    # Добавляем дефолтные промокоды
    cur.execute("SELECT COUNT(*) FROM promocodes")
    if cur.fetchone()[0] == 0:
        default_promocodes = [
            ('ZETTA10', 10, 'percent', True),
            ('ZETTA20', 20, 'percent', True),
            ('ZETTA1000', 1000, 'fixed', True),
            ('ZETTA15', 15, 'percent', True),
        ]
        for p in default_promocodes:
            cur.execute("""
                INSERT INTO promocodes (code, discount, type, active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO NOTHING
            """, p)

    # Добавляем дефолтный влог
    cur.execute("SELECT COUNT(*) FROM vlog")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO vlog (id, text)
            VALUES (1, %s)
            ON CONFLICT (id) DO NOTHING
        """,
                    ('Добро пожаловать в блог компании Zetta! Здесь мы будем делиться новостями о нашей работе, рассказывать о сотрудниках и анонсировать новые услуги.\n\n---\n\n✨ Если у вас есть предложения по улучшению или жалобы, нажимайте на кнопку "Предложения" внизу страницы!',))

    conn.commit()
    cur.close()
    return_db_connection(conn)

    print("=" * 60)
    print("База данных успешно инициализирована!")
    print("Админ аккаунт: admin@zetta.ru / admin123")
    print("=" * 60)


# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С БД (PSYCOPG3) ====================

def load_users_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        "SELECT email, full_name, phone, registered_at, profile_complete, is_admin, personal_discount_type, personal_discount_value FROM users")
    users = cur.fetchall()
    cur.close()
    return_db_connection(conn)

    result = {}
    for u in users:
        email = u['email']
        personal_discount = None
        if u['personal_discount_type'] and u['personal_discount_value']:
            personal_discount = {
                'type': u['personal_discount_type'],
                'discount': u['personal_discount_value']
            }
        result[email] = {
            'email': email,
            'full_name': u['full_name'],
            'phone': u['phone'],
            'registered_at': u['registered_at'].strftime('%d.%m.%Y %H:%M:%S') if u['registered_at'] else None,
            'profile_complete': u['profile_complete'],
            'is_admin': u['is_admin'],
            'personal_discount': personal_discount
        }
    return result


def get_user_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM users WHERE email = %s", (email.lower(),))
    user = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return user


def save_user_to_db(email, password, full_name, phone, profile_complete=False, is_admin=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (email, password, full_name, phone, profile_complete, is_admin, registered_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (email) DO UPDATE SET
            password = EXCLUDED.password,
            full_name = EXCLUDED.full_name,
            phone = EXCLUDED.phone,
            profile_complete = EXCLUDED.profile_complete,
            is_admin = EXCLUDED.is_admin
    """, (email.lower(), password, full_name, phone, profile_complete, is_admin))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def update_user_profile_db(email, full_name, phone):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET full_name = %s, phone = %s, profile_complete = TRUE
        WHERE email = %s
    """, (full_name, phone, email.lower()))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def update_user_admin_status(email, is_admin):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = %s WHERE email = %s", (is_admin, email.lower()))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def set_personal_discount_db(email, discount_type, discount_value):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET personal_discount_type = %s, personal_discount_value = %s
        WHERE email = %s
    """, (discount_type, discount_value, email.lower()))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def remove_personal_discount_db(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET personal_discount_type = NULL, personal_discount_value = NULL
        WHERE email = %s
    """, (email.lower(),))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_reviews_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT id, name, rating, text, date FROM reviews ORDER BY id DESC")
    reviews = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return reviews


def add_review_to_db(name, rating, text, date):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reviews (name, rating, text, date)
        VALUES (%s, %s, %s, %s)
    """, (name, rating, text, date))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_review_from_db(review_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_products_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM products ORDER BY id")
    products = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return products


def add_product_to_db(name, price, sale_price, discount_percent, description, image, category):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (name, price, sale_price, discount_percent, description, image, category)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, price, sale_price, discount_percent, description, image, category))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def update_product_in_db(product_id, name, price, sale_price, discount_percent, description, category):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE products 
        SET name = %s, price = %s, sale_price = %s, discount_percent = %s, description = %s, category = %s
        WHERE id = %s
    """, (name, price, sale_price, discount_percent, description, category, product_id))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_product_from_db(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_news_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM news ORDER BY id")
    news = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return news


def add_news_to_db(date, title, text, fullText, image):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO news (date, title, text, fullText, image)
        VALUES (%s, %s, %s, %s, %s)
    """, (date, title, text, fullText, image))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def update_news_in_db(news_id, title, text, fullText):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE news 
        SET title = %s, text = %s, fullText = %s
        WHERE id = %s
    """, (title, text, fullText, news_id))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_news_from_db(news_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_promocodes_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM promocodes")
    promocodes = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    result = {}
    for p in promocodes:
        result[p['code']] = {
            'discount': p['discount'],
            'type': p['type'],
            'active': p['active']
        }
    return result


def add_promocode_to_db(code, discount, type, active=True):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO promocodes (code, discount, type, active)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            discount = EXCLUDED.discount,
            type = EXCLUDED.type,
            active = EXCLUDED.active
    """, (code, discount, type, active))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def toggle_promocode_in_db(code, active):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE promocodes SET active = %s WHERE code = %s", (active, code))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_promocode_from_db(code):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM promocodes WHERE code = %s", (code,))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def is_promocode_used_db(user_email, promo_code):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM used_promocodes WHERE user_email = %s AND promo_code = %s",
                (user_email.lower(), promo_code))
    result = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return result is not None


def mark_promocode_used_db(user_email, promo_code, order_number):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO used_promocodes (user_email, promo_code, order_number)
        VALUES (%s, %s, %s)
    """, (user_email.lower(), promo_code, order_number))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_orders_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT user_email, order_data, order_number, created_at FROM orders ORDER BY created_at DESC")
    orders = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    result = {}
    for o in orders:
        email = o['user_email']
        if email not in result:
            result[email] = []
        result[email].append(o['order_data'])
    return result


def save_order_to_db(user_email, order_data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_email, order_number, order_data)
        VALUES (%s, %s, %s)
    """, (user_email.lower(), order_data['order_number'], json.dumps(order_data)))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def get_user_orders_from_db(user_email):
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT order_data FROM orders WHERE user_email = %s ORDER BY created_at DESC", (user_email.lower(),))
    orders = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return [o['order_data'] for o in orders]


def load_banned_users_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM banned_users")
    banned = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    result = {}
    for b in banned:
        result[b['email']] = {
            'banned_at': b['banned_at'].isoformat(),
            'ban_until': b['ban_until'].isoformat(),
            'duration_minutes': b['duration_minutes'],
            'reason': b['reason'],
            'message': b['message']
        }
    return result


def add_banned_user_to_db(email, ban_until, duration_minutes, reason, message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO banned_users (email, ban_until, duration_minutes, reason, message)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            ban_until = EXCLUDED.ban_until,
            duration_minutes = EXCLUDED.duration_minutes,
            reason = EXCLUDED.reason,
            message = EXCLUDED.message
    """, (email.lower(), ban_until, duration_minutes, reason, message))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def remove_banned_user_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM banned_users WHERE email = %s", (email.lower(),))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def get_verification_code_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM verification_codes WHERE email = %s", (email.lower(),))
    result = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return result


def save_verification_code_to_db(email, code, expires_at, full_name, phone, password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO verification_codes (email, code, expires_at, full_name, phone, password)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            code = EXCLUDED.code,
            expires_at = EXCLUDED.expires_at,
            full_name = EXCLUDED.full_name,
            phone = EXCLUDED.phone,
            password = EXCLUDED.password
    """, (email.lower(), code, expires_at, full_name, phone, password))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_verification_code_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM verification_codes WHERE email = %s", (email.lower(),))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def get_password_reset_code_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM password_reset_codes WHERE email = %s", (email.lower(),))
    result = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return result


def save_password_reset_code_to_db(email, code, expires_at):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO password_reset_codes (email, code, expires_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            code = EXCLUDED.code,
            expires_at = EXCLUDED.expires_at
    """, (email.lower(), code, expires_at))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def delete_password_reset_code_from_db(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM password_reset_codes WHERE email = %s", (email.lower(),))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def load_vlog_from_db():
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT text FROM vlog WHERE id = 1")
    result = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    if result:
        return {'text': result['text']}
    return {'text': 'Добро пожаловать в блог компании Zetta!'}


def update_vlog_in_db(text):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE vlog SET text = %s WHERE id = 1", (text,))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def add_chat_message_to_db(user_email, message, msg_type):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (user_email, message, type)
        VALUES (%s, %s, %s)
    """, (user_email.lower(), message, msg_type))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def get_chat_messages_from_db(user_email):
    conn = get_db_connection()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM chat_messages WHERE user_email = %s ORDER BY created_at", (user_email.lower(),))
    messages = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return [{'type': m['type'], 'message': m['message'], 'read': m['read']} for m in messages]


def mark_chat_messages_read_db(user_email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE chat_messages SET read = TRUE WHERE user_email = %s AND type = 'admin'", (user_email.lower(),))
    conn.commit()
    cur.close()
    return_db_connection(conn)


def get_unread_count_db(user_email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chat_messages WHERE user_email = %s AND type = 'admin' AND read = FALSE",
                (user_email.lower(),))
    count = cur.fetchone()[0]
    cur.close()
    return_db_connection(conn)
    return count


EMAIL_CONFIG = {
    'smtp_server': 'smtp.mail.ru',
    'smtp_port': 587,
    'email': 'vaincode@mail.ru',
    'password': '7lvM92oEvTGdieqUCwGM'
}

OFFICE_COORDINATES = {
    'lat': 53.3543,
    'lon': 83.7493,
    'address': 'г. Барнаул, ул. Юрина, 182/7'
}


# Функции отправки email
def send_verification_email(email, code, type='registration'):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = email
        if type == 'registration':
            msg['Subject'] = 'Код подтверждения регистрации - Zetta'
        else:
            msg['Subject'] = 'Код восстановления пароля - Zetta'

        if type == 'registration':
            title = 'Подтверждение регистрации'
            message = 'Вы зарегистрировались в компании Zetta.'
            instruction = 'Для завершения регистрации введите следующий код подтверждения:'
        else:
            title = 'Восстановление пароля'
            message = 'Вы запросили восстановление пароля в компании Zetta.'
            instruction = 'Для сброса пароля введите следующий код:'

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: #1a1a1a; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; text-align: center; }}
                .code {{ font-size: 32px; font-weight: bold; color: #27ae60; letter-spacing: 5px; background: #f0f0f0; padding: 15px; border-radius: 8px; font-family: monospace; }}
                .footer {{ background: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .warning {{ color: #e74c3c; font-size: 12px; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚡ Zetta</h1>
                    <p>{title}</p>
                </div>
                <div class="content">
                    <p>Здравствуйте!</p>
                    <p>{message}</p>
                    <p>{instruction}</p>
                    <div class="code">{code}</div>
                    <p>Код действителен в течение 5 минут.</p>
                    <p class="warning">Если вы не запрашивали это действие, проигнорируйте данное письмо.</p>
                </div>
                <div class="footer">
                    <p>© 2026 Zetta. Все права защищены.</p>
                    <p>г. Барнаул, ул. Юрина, 182/7</p>
                </div>
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
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False


def send_operator_request_email(user_name, user_phone, user_email):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = EMAIL_CONFIG['email']
        msg['Subject'] = 'ЗАПРОС СВЯЗИ С ОПЕРАТОРОМ - Zetta'

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif;">
            <h1>📞 ЗАПРОС СВЯЗИ С ОПЕРАТОРОМ</h1>
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

        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False


def send_receipt_email(order_data):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = order_data['customer_email']
        msg['Cc'] = EMAIL_CONFIG['email']
        msg['Subject'] = f'Чек оплаты #{order_data["order_number"]} - Zetta'

        payment_method_text = "Банковская карта (онлайн)" if order_data['payment_method'] == 'card' else "Наличными при получении"

        items_html = ''
        for item in order_data['items']:
            discount_span = '<span style="color:#e74c3c; font-size:0.8rem;">🔥 Скидка!</span>' if item.get('price') != item.get('original_price', item['price']) else ''
            items_html += f'''
            <tr>
                <td>{item["name"]} {discount_span}</td>
                <td>{item["quantity"]}</td>
                <td>{item["price"]:,} ₽</td>
                <td>{item["total"]:,} ₽</td>
            </tr>
            '''

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .receipt {{ max-width: 600px; margin: 0 auto; background: white; border: 1px solid #ddd; }}
                .header {{ background: #1a1a1a; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .order-info {{ background: #f9f9f9; padding: 15px; margin-bottom: 20px; border-left: 3px solid #27ae60; }}
                .customer-info {{ background: #e8f5e9; padding: 15px; margin-bottom: 20px; border-left: 3px solid #2196f3; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                .items-table th {{ background: #1a1a1a; color: white; padding: 10px; text-align: left; }}
                .items-table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .total {{ text-align: right; padding: 15px; background: #f9f9f9; margin-top: 20px; }}
                .status {{ display: inline-block; padding: 5px 10px; background: #27ae60; color: white; font-size: 12px; border-radius: 3px; }}
                .footer {{ background: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .delivery-info {{ background: #fff3e0; padding: 15px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="receipt">
                <div class="header">
                    <h1>⚡ ЧЕК ОПЛАТЫ</h1>
                    <p>ZETTA - Профессиональная сборка ПК и IT-услуги</p>
                </div>
                <div class="content">
                    <div class="order-info">
                        <p><strong>Номер заказа:</strong> #{order_data["order_number"]}</p>
                        <p><strong>Дата и время:</strong> {order_data["datetime"]}</p>
                        <p><strong>Статус:</strong> <span class="status">{"Оплачен онлайн" if order_data['payment_method'] == 'card' else "Ожидает оплаты при получении"}</span></p>
                    </div>

                    <div class="customer-info">
                        <h4>Информация о клиенте:</h4>
                        <p><strong>ФИО:</strong> {order_data["customer_name"]}</p>
                        <p><strong>Email:</strong> {order_data["customer_email"]}</p>
                    </div>

                    <h3>Услуги в заказе:</h3>
                    <table class="items-table">
                        <thead>
                            <tr><th>Наименование</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>

                    <div class="total">
                        <table style="width:100%; max-width:300px; margin-left:auto;">
                            <tr><td><strong>Подытог:</strong></td><td align="right">{order_data['subtotal']:,} ₽</td></tr>
                            {f'<tr><td><strong>Скидка:</strong></td><td align="right" style="color:#27ae60;">-{order_data["discount"]:,} ₽</td></tr>' if order_data['discount'] > 0 else ''}
                            <tr style="border-top:2px solid #ddd;"><td><strong>ИТОГО:</strong></td><td align="right"><strong>{order_data['total']:,} ₽</strong></td></tr>
                        </table>
                    </div>

                    <div class="delivery-info">
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
                <div class="footer">
                    <p>Спасибо за заказ в Zetta!</p>
                    <p>© 2026 Zetta. Все права защищены.</p>
                </div>
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
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False


def send_feedback_email(user_name, user_email, user_phone, message):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = EMAIL_CONFIG['email']
        msg['Subject'] = f'ПРЕДЛОЖЕНИЕ/ЖАЛОБА от {user_name}'

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif;">
            <h1 style="color: #e74c3c;">📬 НОВОЕ СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</h1>
            <hr>
            <p><strong>👤 Отправитель:</strong> {user_name}</p>
            <p><strong>📧 Email:</strong> {user_email}</p>
            <p><strong>📱 Телефон:</strong> {user_phone}</p>
            <p><strong>⏰ Время отправки:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            <hr>
            <p><strong>💬 Сообщение:</strong></p>
            <div style="background: #f0f0f0; padding: 1rem; border-radius: 8px; margin-top: 0.5rem;">
                {message.replace(chr(10), '<br>')}
            </div>
            <hr>
            <p style="color: #888;">Сообщение отправлено через форму на сайте Zetta</p>
        </body>
        </html>
        '''

        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False


def calculate_distance(address):
    address_lower = address.lower()
    if 'барнаул' in address_lower:
        return random.randint(1, 30)
    elif 'новосибирск' in address_lower:
        return random.randint(200, 250)
    elif 'москва' in address_lower:
        return random.randint(3000, 3500)
    elif 'спб' in address_lower or 'санкт-петербург' in address_lower:
        return random.randint(3500, 4000)
    elif 'томск' in address_lower:
        return random.randint(400, 450)
    elif 'кемерово' in address_lower:
        return random.randint(250, 300)
    elif 'новокузнецк' in address_lower:
        return random.randint(350, 400)
    elif 'бийск' in address_lower:
        return random.randint(150, 180)
    elif 'рубцовск' in address_lower:
        return random.randint(250, 280)
    else:
        return random.randint(100, 2000)


def calculate_delivery_date(distance_km):
    if distance_km <= 50:
        days = 3
        period_text = "3 дня"
    elif distance_km <= 100:
        days = 7
        period_text = "7 дней"
    else:
        days = 14
        period_text = "14 дней (2 недели)"
    delivery_date = (datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')
    return delivery_date, period_text


def get_product_price(product):
    if product.get('sale_price') and product['sale_price'] > 0 and product['sale_price'] < product['price']:
        return product['sale_price']
    return product['price']


def generate_verification_code():
    return str(random.randint(100000, 999999))


def register_user(email, password, full_name, phone):
    user = get_user_from_db(email)
    if user:
        return False, "Пользователь с таким email уже существует"

    is_admin = (email.lower() == 'admin@zetta.ru')
    save_user_to_db(email, password, full_name, phone, True, is_admin)
    return True, "Регистрация успешна"


def is_profile_complete(email):
    user = get_user_from_db(email)
    if user:
        return user.get('profile_complete', False) and user.get('full_name') and user.get('phone')
    return False


def update_user_profile(email, full_name, phone):
    update_user_profile_db(email, full_name, phone)
    return True


def is_admin(email):
    user = get_user_from_db(email)
    if user:
        return user.get('is_admin', False)
    return False


def login_user(email, password):
    user = get_user_from_db(email)

    # Проверка бана
    banned = get_banned_users()
    if email in banned and datetime.now() < datetime.fromisoformat(banned[email]['ban_until']):
        return False, f"Ваш аккаунт забанен до {datetime.fromisoformat(banned[email]['ban_until']).strftime('%d.%m.%Y %H:%M:%S')}. Причина: {banned[email]['reason']}"

    if user and user['password'] == password:
        session['user_email'] = email
        session['user_name'] = user['full_name']
        session['is_admin'] = user['is_admin']
        return True, "Вход выполнен"
    return False, "Неверный email или пароль"


def get_banned_users():
    return load_banned_users_from_db()


def is_user_banned(email):
    banned = get_banned_users()
    if email in banned:
        ban_until = datetime.fromisoformat(banned[email]['ban_until'])
        if datetime.now() < ban_until:
            return True, ban_until.strftime('%d.%m.%Y %H:%M:%S'), banned[email]['reason'], banned[email]['message']
        else:
            remove_banned_user_from_db(email)
    return False, None, None, None


def ban_user(email, duration_minutes, reason, message):
    ban_until = datetime.now() + timedelta(minutes=duration_minutes)
    add_banned_user_to_db(email, ban_until, duration_minutes, reason, message)


def unban_user(email):
    remove_banned_user_from_db(email)


def get_user_unread_count(email):
    return get_unread_count_db(email)


def mark_chat_read(email):
    mark_chat_messages_read_db(email)


def get_daily_random_reviews():
    reviews = load_reviews_from_db()
    if len(reviews) == 0:
        return []
    today_seed = int(datetime.now().strftime('%Y%m%d'))
    random.seed(today_seed)
    shuffled = list(reviews)
    random.shuffle(shuffled)
    return shuffled[:3]


# Инициализация БД
init_db()


# ==================== МАРШРУТЫ ====================

@app.before_request
def check_ban():
    if request.endpoint == 'static':
        return None
    if 'user_email' in session:
        is_banned, ban_until, ban_reason, ban_message = is_user_banned(session['user_email'])
        if is_banned:
            session.clear()
            return redirect(f'/ban-page?email={session["user_email"]}')


@app.route('/ban-page')
def ban_page():
    email = request.args.get('email', '')
    banned = get_banned_users()
    if email in banned:
        ban_until = datetime.fromisoformat(banned[email]['ban_until']).strftime('%d.%m.%Y %H:%M:%S')
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Аккаунт заблокирован</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { background: linear-gradient(135deg, #0a0a0a 0%, #1a0a0a 100%); display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: 'Segoe UI', Arial, sans-serif; }
                .ban-container { background: #1a1a1a; border: 1px solid #e74c3c; border-radius: 16px; padding: 2.5rem; max-width: 500px; margin: 20px; text-align: center; animation: fadeInUp 0.6s ease-out; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
                .ban-icon { font-size: 4rem; margin-bottom: 1rem; animation: pulse 1.5s ease-in-out infinite; }
                .ban-title { font-size: 1.8rem; font-weight: bold; color: #e74c3c; margin-bottom: 1rem; }
                .ban-subtitle { color: #888; margin-bottom: 1.5rem; font-size: 0.9rem; }
                .ban-info { background: #0f0f0f; border-radius: 12px; padding: 1.5rem; text-align: left; margin-bottom: 1.5rem; border-left: 4px solid #e74c3c; }
                .ban-info p { margin: 0.5rem 0; color: #bbb; }
                .ban-info strong { color: #27ae60; }
                .ban-reason { background: #2a1a1a; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0; color: #e74c3c; font-weight: bold; }
                .ban-message { background: #1a2a1a; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0; color: #27ae60; font-style: italic; }
                .ban-date { color: #f39c12; font-weight: bold; }
                .contact-link { color: #27ae60; text-decoration: none; font-weight: bold; transition: all 0.3s ease; }
                .contact-link:hover { text-decoration: underline; color: #229954; }
                .back-btn { background: #27ae60; color: white; border: none; padding: 0.8rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-top: 1rem; transition: all 0.3s ease; }
                .back-btn:hover { background: #229954; transform: scale(1.02); }
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
        ''', ban_until=ban_until, reason=banned[email]['reason'], message=banned[email]['message'])
    return redirect('/')


# ==================== API МАРШРУТЫ ====================

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'user_email' in session:
        is_banned, ban_until, ban_reason, ban_message = is_user_banned(session['user_email'])
        if is_banned:
            session.clear()
            return jsonify({'logged_in': False, 'is_admin': False, 'banned': True})

        user = get_user_from_db(session['user_email'])
        return jsonify({
            'logged_in': True,
            'user': {
                'full_name': user.get('full_name', ''),
                'email': user.get('email', ''),
                'phone': user.get('phone', ''),
                'registered_at': user['registered_at'].strftime('%d.%m.%Y %H:%M:%S') if user['registered_at'] else '',
                'personal_discount': {
                    'type': user.get('personal_discount_type'),
                    'discount': user.get('personal_discount_value')
                } if user.get('personal_discount_type') else None
            },
            'is_admin': user.get('is_admin', False)
        })
    return jsonify({'logged_in': False, 'is_admin': False})


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    success, message = login_user(data.get('email'), data.get('password'))
    return jsonify({'success': success, 'message': message})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    return jsonify({'success': True})


@app.route('/api/check-profile-complete', methods=['GET'])
def check_profile_complete():
    if 'user_email' not in session:
        return jsonify({'complete': False})
    complete = is_profile_complete(session['user_email'])
    return jsonify({'complete': complete})


@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    data = request.json
    full_name = data.get('full_name')
    phone = data.get('phone')
    if not full_name or not phone:
        return jsonify({'success': False, 'message': 'Заполните все поля'})
    if update_user_profile(session['user_email'], full_name, phone):
        session['user_name'] = full_name
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Ошибка при обновлении профиля'})


@app.route('/api/send-reset-code', methods=['POST'])
def send_reset_code():
    data = request.json
    email = data.get('email')
    user = get_user_from_db(email)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь с таким email не найден'})

    code = generate_verification_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()
    save_password_reset_code_to_db(email, code, expires_at)

    if send_verification_email(email, code, 'reset'):
        return jsonify({'success': True, 'message': 'Код восстановления отправлен на почту'})
    else:
        delete_password_reset_code_from_db(email)
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма'})


@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')

    reset_data = get_password_reset_code_from_db(email)
    if not reset_data:
        return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'})

    if datetime.now().timestamp() > reset_data['expires_at']:
        delete_password_reset_code_from_db(email)
        return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'})

    if reset_data['code'] != code:
        return jsonify({'success': False, 'message': 'Неверный код подтверждения'})

    save_user_to_db(email, new_password, None, None, False, False)
    delete_password_reset_code_from_db(email)
    return jsonify({'success': True, 'message': 'Пароль успешно изменён'})


@app.route('/api/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email = data.get('email')
    full_name = data.get('full_name')
    phone = data.get('phone')
    password = data.get('password')

    user = get_user_from_db(email)
    if user:
        return jsonify({'success': False, 'message': 'Пользователь с таким email уже существует'})

    code = generate_verification_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()
    save_verification_code_to_db(email, code, expires_at, full_name, phone, password)

    if send_verification_email(email, code, 'registration'):
        return jsonify({'success': True, 'message': 'Код подтверждения отправлен на почту'})
    else:
        delete_verification_code_from_db(email)
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма. Попробуйте позже.'})


@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    email = data.get('email')
    code = data.get('code')

    temp_data = get_verification_code_from_db(email)
    if not temp_data:
        return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'})

    if datetime.now().timestamp() > temp_data['expires_at']:
        delete_verification_code_from_db(email)
        return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'})

    if temp_data['code'] != code:
        return jsonify({'success': False, 'message': 'Неверный код подтверждения'})

    success, message = register_user(email, temp_data['password'], temp_data['full_name'], temp_data['phone'])
    if success:
        delete_verification_code_from_db(email)
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/api/resend-verification', methods=['POST'])
def resend_verification():
    data = request.json
    email = data.get('email')

    temp_data = get_verification_code_from_db(email)
    if not temp_data:
        return jsonify({'success': False, 'message': 'Данные не найдены. Заполните форму регистрации заново.'})

    new_code = generate_verification_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()
    save_verification_code_to_db(email, new_code, expires_at, temp_data['full_name'], temp_data['phone'], temp_data['password'])

    if send_verification_email(email, new_code, 'registration'):
        return jsonify({'success': True, 'message': 'Новый код отправлен на почту'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма'})


@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    if 'user_email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    user = get_user_from_db(session['user_email'])
    return jsonify({
        'full_name': user.get('full_name', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', ''),
        'registered_at': user['registered_at'].strftime('%d.%m.%Y %H:%M:%S') if user['registered_at'] else '',
        'personal_discount': {
            'type': user.get('personal_discount_type'),
            'discount': user.get('personal_discount_value')
        } if user.get('personal_discount_type') else None
    })


@app.route('/api/user/orders', methods=['GET'])
def get_user_orders_api():
    if 'user_email' not in session:
        return jsonify([])
    orders = get_user_orders_from_db(session['user_email'])
    return jsonify(orders)


@app.route('/api/home-reviews', methods=['GET'])
def get_home_reviews():
    reviews = get_daily_random_reviews()
    return jsonify(reviews)


@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    reviews = load_reviews_from_db()
    return jsonify(reviews)


@app.route('/api/add-review', methods=['POST'])
def add_review():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    data = request.json
    name = data.get('name', 'Аноним')
    rating = data.get('rating', 5)
    text = data.get('text', '')
    date = datetime.now().strftime('%d.%m.%Y %H:%M')
    add_review_to_db(name, rating, text, date)
    return jsonify({'success': True})


@app.route('/api/products')
def get_products():
    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    products = load_products_from_db()

    filtered = products
    if search:
        filtered = [p for p in filtered if search in p['name'].lower()]
    if category and category != 'all':
        filtered = [p for p in filtered if p.get('category') == category]

    return jsonify(filtered)


@app.route('/api/product/<int:product_id>')
def get_product(product_id):
    products = load_products_from_db()
    product = next((p for p in products if p['id'] == product_id), None)
    return jsonify(product) if product else ('', 404)


@app.route('/api/calculate-delivery', methods=['POST'])
def calculate_delivery():
    data = request.json
    address = data.get('address', '')
    distance = calculate_distance(address)
    delivery_date, period_text = calculate_delivery_date(distance)
    return jsonify({
        'distance': distance,
        'delivery_period': period_text,
        'delivery_date': delivery_date
    })


@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    data = request.json
    product_id = data['product_id']
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    return jsonify({'success': True})


@app.route('/api/update-cart', methods=['POST'])
def update_cart():
    data = request.json
    product_id = str(data['product_id'])
    quantity = data['quantity']
    cart = session.get('cart', {})
    if quantity > 0:
        cart[product_id] = quantity
    else:
        cart.pop(product_id, None)
    session['cart'] = cart
    return jsonify({'success': True})


@app.route('/api/remove-from-cart', methods=['POST'])
def remove_from_cart():
    data = request.json
    cart = session.get('cart', {})
    cart.pop(str(data['product_id']), None)
    session['cart'] = cart
    return jsonify({'success': True})


@app.route('/api/apply-promo', methods=['POST'])
def apply_promo():
    data = request.json
    promo_code = data.get('promo_code', '').upper()

    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Войдите в аккаунт, чтобы использовать промокод'})

    user_email = session['user_email']
    promocodes = load_promocodes_from_db()
    user = get_user_from_db(user_email)
    personal_discount = user.get('personal_discount_type')

    if promo_code == "PERSONAL_DISCOUNT" and personal_discount:
        session['promo_code'] = promo_code
        session['personal_discount_applied'] = True
        discount_text = f"{user['personal_discount_value']}%" if user['personal_discount_type'] == 'percent' else f"{user['personal_discount_value']} ₽"
        return jsonify({'success': True, 'discount_text': f"Персональная скидка: {discount_text}"})

    if is_promocode_used_db(user_email, promo_code):
        return jsonify({'success': False, 'message': 'Вы уже использовали этот промокод'})

    if promo_code in promocodes and promocodes[promo_code]['active']:
        session['promo_code'] = promo_code
        promo_data = promocodes[promo_code]
        discount_text = f"{promo_data['discount']}%" if promo_data['type'] == 'percent' else f"{promo_data['discount']} ₽"
        return jsonify({'success': True, 'discount_text': discount_text})
    else:
        return jsonify({'success': False, 'message': 'Неверный промокод'})


@app.route('/api/cart')
def get_cart():
    cart = session.get('cart', {})
    promo_code = session.get('promo_code')
    is_personal = session.get('personal_discount_applied', False)
    products = load_products_from_db()
    promocodes = load_promocodes_from_db()
    user_email = session.get('user_email')

    items = []
    subtotal = 0
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
                'quantity': quantity,
                'total': item_total
            })

    discount = 0
    if promo_code:
        if is_personal and user_email:
            user = get_user_from_db(user_email)
            personal_discount_value = user.get('personal_discount_value')
            personal_discount_type = user.get('personal_discount_type')
            if personal_discount_value:
                if personal_discount_type == 'percent':
                    discount = subtotal * personal_discount_value / 100
                else:
                    discount = min(personal_discount_value, subtotal)
        elif promo_code in promocodes and promocodes[promo_code]['active']:
            promo = promocodes[promo_code]
            if promo['type'] == 'percent':
                discount = subtotal * promo['discount'] / 100
            else:
                discount = min(promo['discount'], subtotal)

    total = subtotal - discount

    return jsonify({
        'items': items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total
    })


@app.route('/api/checkout-card', methods=['POST'])
def checkout_card():
    data = request.json
    customer_name = data.get('full_name', '')
    customer_email = data.get('email', '')
    customer_phone = data.get('phone', '')
    delivery_address = data.get('delivery_address', '')
    card_last4 = data.get('card_number', '****')

    cart = session.get('cart', {})
    promo_code = session.get('promo_code')
    is_personal = session.get('personal_discount_applied', False)
    products = load_products_from_db()
    promocodes = load_promocodes_from_db()

    distance = calculate_distance(delivery_address)
    delivery_date, period_text = calculate_delivery_date(distance)

    items = []
    subtotal = 0
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
                'total': item_total
            })

    discount = 0
    if promo_code:
        if is_personal and session.get('user_email'):
            user = get_user_from_db(session['user_email'])
            personal_discount_value = user.get('personal_discount_value')
            personal_discount_type = user.get('personal_discount_type')
            if personal_discount_value:
                if personal_discount_type == 'percent':
                    discount = subtotal * personal_discount_value / 100
                else:
                    discount = min(personal_discount_value, subtotal)
        elif promo_code in promocodes and promocodes[promo_code]['active']:
            promo = promocodes[promo_code]
            if promo['type'] == 'percent':
                discount = subtotal * promo['discount'] / 100
            else:
                discount = min(promo['discount'], subtotal)

    total = subtotal - discount
    order_number = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

    if promo_code and 'user_email' in session and not is_personal:
        mark_promocode_used_db(session['user_email'], promo_code, order_number)

    order_data = {
        'order_number': order_number,
        'datetime': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'items': items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'delivery_address': delivery_address,
        'from_address': f"{OFFICE_COORDINATES['address']}",
        'distance': distance,
        'delivery_period': period_text,
        'delivery_date': delivery_date,
        'payment_method': 'card'
    }

    if 'user_email' in session:
        save_order_to_db(session['user_email'], order_data)

    payment_log = {
        'order_number': order_number,
        'customer': customer_name,
        'email': customer_email,
        'amount': total,
        'phone': '89520062357',
        'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'card_last4': card_last4,
        'address': delivery_address,
        'distance': distance,
        'delivery_date': delivery_date
    }

    with open('payments_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"{json.dumps(payment_log, ensure_ascii=False)}\n")

    email_sent = send_receipt_email(order_data)

    session.pop('cart', None)
    session.pop('promo_code', None)
    session.pop('personal_discount_applied', None)

    if email_sent:
        return jsonify({'message': f'✅ Заказ #{order_number} оплачен картой онлайн! Сумма {total:,} ₽ поступит на номер 89520062357. Чек отправлен на {customer_email}.'})
    else:
        return jsonify({'message': f'✅ Заказ #{order_number} оплачен картой онлайн! Сумма {total:,} ₽ поступит на номер 89520062357.'})


@app.route('/api/checkout-cash', methods=['POST'])
def checkout_cash():
    data = request.json
    customer_name = data.get('full_name', '')
    customer_email = data.get('email', '')
    customer_phone = data.get('phone', '')
    delivery_address = data.get('delivery_address', '')

    cart = session.get('cart', {})
    promo_code = session.get('promo_code')
    is_personal = session.get('personal_discount_applied', False)
    products = load_products_from_db()
    promocodes = load_promocodes_from_db()

    distance = calculate_distance(delivery_address)
    delivery_date, period_text = calculate_delivery_date(distance)

    items = []
    subtotal = 0
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
                'total': item_total
            })

    discount = 0
    if promo_code:
        if is_personal and session.get('user_email'):
            user = get_user_from_db(session['user_email'])
            personal_discount_value = user.get('personal_discount_value')
            personal_discount_type = user.get('personal_discount_type')
            if personal_discount_value:
                if personal_discount_type == 'percent':
                    discount = subtotal * personal_discount_value / 100
                else:
                    discount = min(personal_discount_value, subtotal)
        elif promo_code in promocodes and promocodes[promo_code]['active']:
            promo = promocodes[promo_code]
            if promo['type'] == 'percent':
                discount = subtotal * promo['discount'] / 100
            else:
                discount = min(promo['discount'], subtotal)

    total = subtotal - discount
    order_number = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

    if promo_code and 'user_email' in session and not is_personal:
        mark_promocode_used_db(session['user_email'], promo_code, order_number)

    order_data = {
        'order_number': order_number,
        'datetime': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'items': items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'delivery_address': delivery_address,
        'from_address': f"{OFFICE_COORDINATES['address']}",
        'distance': distance,
        'delivery_period': period_text,
        'delivery_date': delivery_date,
        'payment_method': 'cash'
    }

    if 'user_email' in session:
        save_order_to_db(session['user_email'], order_data)

    order_log = {
        'order_number': order_number,
        'customer': customer_name,
        'email': customer_email,
        'amount': total,
        'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'address': delivery_address,
        'distance': distance,
        'delivery_date': delivery_date,
        'payment_method': 'cash'
    }

    with open('orders_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"{json.dumps(order_log, ensure_ascii=False)}\n")

    email_sent = send_receipt_email(order_data)

    session.pop('cart', None)
    session.pop('promo_code', None)
    session.pop('personal_discount_applied', None)

    if email_sent:
        return jsonify({'message': f'✅ Заказ #{order_number} оформлен! Оплата {total:,} ₽ наличными при получении. Чек отправлен на {customer_email}.'})
    else:
        return jsonify({'message': f'✅ Заказ #{order_number} оформлен! Оплата {total:,} ₽ наличными при получении.'})


# ==================== API ДЛЯ АДМИН-ПАНЕЛИ ====================

@app.route('/api/admin/products', methods=['GET'])
def admin_get_products():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    products = load_products_from_db()
    return jsonify(products)


@app.route('/api/admin/add-product', methods=['POST'])
def admin_add_product():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    name = request.form.get('name')
    price = request.form.get('price')
    sale_price = request.form.get('sale_price')
    discount_percent = request.form.get('discount_percent', '0')
    description = request.form.get('description')
    category = request.form.get('category', 'services')
    image = request.files.get('image')

    products = load_products_from_db()
    new_id = max([p['id'] for p in products]) + 1 if products else 1

    image_path = '/static/uploads/default.jpg'
    if image:
        filename = secure_filename(f"product_{new_id}_{image.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)
        image_path = f'/static/uploads/{filename}'

    sale_price_val = None
    discount_percent_val = int(discount_percent) if discount_percent else 0

    if sale_price and int(sale_price) > 0:
        sale_price_val = int(sale_price)
        if discount_percent_val == 0 and int(price) > 0:
            discount_percent_val = int((1 - int(sale_price) / int(price)) * 100)
    elif discount_percent_val > 0 and int(price) > 0:
        sale_price_val = int(int(price) * (1 - discount_percent_val / 100))

    add_product_to_db(name, int(price), sale_price_val, discount_percent_val, description, image_path, category)
    return jsonify({'success': True})


@app.route('/api/admin/edit-product', methods=['POST'])
def admin_edit_product():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    product_id = data.get('id')
    name = data.get('name')
    price = data.get('price')
    sale_price = data.get('sale_price')
    discount_percent = data.get('discount_percent', 0)
    description = data.get('description')
    category = data.get('category', 'services')

    update_product_in_db(product_id, name, price, sale_price, discount_percent, description, category)
    return jsonify({'success': True})


@app.route('/api/admin/delete-product', methods=['POST'])
def admin_delete_product():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    product_id = data.get('id')
    delete_product_from_db(product_id)
    return jsonify({'success': True})


@app.route('/api/admin/news', methods=['GET'])
def admin_get_news():
    news = load_news_from_db()
    return jsonify(news)


@app.route('/api/admin/add-news', methods=['POST'])
def admin_add_news():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    title = request.form.get('title')
    text = request.form.get('text')
    fullText = request.form.get('fullText')
    image = request.files.get('image')

    date = datetime.now().strftime('%d.%m.%Y')
    image_path = '/static/uploads/default_news.jpg'
    if image:
        filename = secure_filename(f"news_{int(datetime.now().timestamp())}_{image.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)
        image_path = f'/static/uploads/{filename}'

    add_news_to_db(date, title, text, fullText, image_path)
    return jsonify({'success': True})


@app.route('/api/admin/edit-news', methods=['POST'])
def admin_edit_news():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    news_id = data.get('id')
    title = data.get('title')
    text = data.get('text')
    fullText = data.get('fullText')

    update_news_in_db(news_id, title, text, fullText)
    return jsonify({'success': True})


@app.route('/api/admin/delete-news', methods=['POST'])
def admin_delete_news():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    news_id = data.get('id')
    delete_news_from_db(news_id)
    return jsonify({'success': True})


@app.route('/api/admin/promocodes', methods=['GET'])
def admin_get_promocodes():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    promocodes = load_promocodes_from_db()
    return jsonify(promocodes)


@app.route('/api/promocodes', methods=['GET'])
def get_promocodes():
    promocodes = load_promocodes_from_db()
    return jsonify(promocodes)


@app.route('/api/admin/add-promocode', methods=['POST'])
def admin_add_promocode():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    code = data.get('code', '').upper()
    type = data.get('type')
    discount = data.get('discount')

    if not code or not discount:
        return jsonify({'success': False, 'message': 'Заполните все поля'})

    add_promocode_to_db(code, discount, type)
    return jsonify({'success': True})


@app.route('/api/admin/toggle-promocode', methods=['POST'])
def admin_toggle_promocode():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    code = data.get('code', '').upper()

    promocodes = load_promocodes_from_db()
    if code in promocodes:
        new_status = not promocodes[code]['active']
        toggle_promocode_in_db(code, new_status)
        status = 'включён' if new_status else 'отключён'
        return jsonify({'success': True, 'message': f'Промокод {code} {status}'})
    return jsonify({'success': False, 'message': 'Промокод не найден'})


@app.route('/api/admin/delete-promocode', methods=['POST'])
def admin_delete_promocode():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    code = data.get('code', '').upper()
    delete_promocode_from_db(code)
    return jsonify({'success': True})


@app.route('/api/admin/delete-review', methods=['POST'])
def admin_delete_review():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    review_id = data.get('id')
    delete_review_from_db(review_id)
    return jsonify({'success': True})


@app.route('/api/admin/orders', methods=['GET'])
def admin_get_orders():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    orders = load_orders_from_db()
    return jsonify(orders)


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    users = load_users_from_db()
    return jsonify(users)


@app.route('/api/admin/make-admin', methods=['POST'])
def admin_make_admin():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')
    update_user_admin_status(email, True)
    return jsonify({'success': True})


@app.route('/api/admin/remove-admin', methods=['POST'])
def admin_remove_admin():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')
    update_user_admin_status(email, False)
    return jsonify({'success': True})


@app.route('/api/admin/ban-user', methods=['POST'])
def ban_user_route():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')
    duration_minutes = data.get('duration_minutes')
    reason = data.get('reason', 'Нарушение правил')
    message = data.get('message', 'Обратитесь к администратору для уточнения деталей')

    if not email or not duration_minutes:
        return jsonify({'success': False, 'message': 'Не указан email или срок бана'})

    ban_user(email, duration_minutes, reason, message)

    if 'user_email' in session and session['user_email'].lower() == email.lower():
        session.clear()

    ban_until = datetime.now() + timedelta(minutes=duration_minutes)
    return jsonify({'success': True, 'message': f'Пользователь {email} забанен до {ban_until.strftime("%d.%m.%Y %H:%M:%S")}'})


@app.route('/api/admin/unban-user', methods=['POST'])
def unban_user_route():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')
    unban_user(email)
    return jsonify({'success': True, 'message': f'Бан снят с {email}'})


@app.route('/api/admin/set-personal-discount', methods=['POST'])
def set_personal_discount():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    user_email = data.get('email')
    discount_type = data.get('type')
    discount_value = data.get('discount')

    if not user_email or not discount_type or discount_value is None:
        return jsonify({'success': False, 'message': 'Заполните все поля'})

    set_personal_discount_db(user_email, discount_type, discount_value)
    return jsonify({'success': True, 'message': f'Персональная скидка установлена для {user_email}'})


@app.route('/api/admin/remove-personal-discount', methods=['POST'])
def remove_personal_discount():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    user_email = data.get('email')

    if not user_email:
        return jsonify({'success': False, 'message': 'Не указан email'})

    remove_personal_discount_db(user_email)
    return jsonify({'success': True, 'message': 'Персональная скидка удалена'})


@app.route('/api/chat/send-operator-request', methods=['POST'])
def send_operator_request():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    user = get_user_from_db(session['user_email'])
    user_name = user.get('full_name', 'Не указано')
    user_phone = user.get('phone', 'Не указан')
    user_email = session['user_email']

    email_sent = send_operator_request_email(user_name, user_phone, user_email)
    return jsonify({'success': True, 'message': '✅ Заявка отправлена! Оператор свяжется с вами в ближайшее время.',
                    'email_sent': email_sent})


@app.route('/api/chat/send-payment-question', methods=['POST'])
def send_payment_question():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401
    return jsonify({'success': True,
                    'response': 'Доброго времени суток, наш дорогой клиент! В данный момент оплата принимается только за наличный расчёт или же перевод на карту. Онлайн оплата скоро появится. ЖДИТЕ НАШИХ НОВОСТЕЙ!'})


@app.route('/api/chat/site-creation-time', methods=['POST'])
def site_creation_time():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401
    return jsonify({'success': True,
                    'response': 'В среднем создание сайта уходит 1-2 недели, но если сайт не содержит в себе сложных элементов, то создание такого проекта сокращается вдвое!'})


@app.route('/api/chat/consultation', methods=['POST'])
def consultation():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    data = request.json
    choice = data.get('choice')

    phones = {
        'system_admin': '89836074115',
        'director': '89520062357',
        'manager': '89132447707'
    }
    names = {
        'system_admin': 'Системный администратор',
        'director': 'Генеральный директор',
        'manager': 'Менеджер'
    }

    if choice in phones:
        response = f"{names[choice]}: {phones[choice]}"
    else:
        response = "Пожалуйста, выберите одного из специалистов: Системный администратор, Генеральный директор или Менеджер."

    return jsonify({'success': True, 'response': response})


@app.route('/api/chat/cooperation', methods=['POST'])
def cooperation():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401
    return jsonify({'success': True,
                    'response': 'По вопросам рекламы и сотрудничества пишите нам на почту vaincode@mail.ru или можете позвонить по номеру телефона 89520062357.'})


@app.route('/api/vlog', methods=['GET'])
def get_vlog():
    vlog = load_vlog_from_db()
    return jsonify(vlog)


@app.route('/api/admin/update-vlog', methods=['POST'])
def update_vlog():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    text = data.get('text', '')
    update_vlog_in_db(text)
    return jsonify({'success': True, 'message': 'Влог обновлён'})


@app.route('/api/send-feedback', methods=['POST'])
def send_feedback():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    data = request.json
    message = data.get('message', '')

    if not message:
        return jsonify({'success': False, 'message': 'Введите сообщение'})

    user = get_user_from_db(session['user_email'])
    user_name = user.get('full_name', 'Не указано')
    user_phone = user.get('phone', 'Не указан')
    user_email = session['user_email']

    email_sent = send_feedback_email(user_name, user_email, user_phone, message)
    if email_sent:
        return jsonify({'success': True, 'message': 'Сообщение отправлено! Спасибо за обратную связь.'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка при отправке. Попробуйте позже.'})


# HTML ТЕМПЛЕЙТ (ПОЛНЫЙ, БОЛЕЕ 5000 СТРОК HTML)
HTML_TEMPLATE = '''{% raw %}<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Zetta | Профессиональная сборка ПК и IT-услуги</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            line-height: 1.5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Анимации */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeInLeft {
            from {
                opacity: 0;
                transform: translateX(-30px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes fadeInRight {
            from {
                opacity: 0;
                transform: translateX(30px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes scaleIn {
            from {
                opacity: 0;
                transform: scale(0.9);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        @keyframes shine {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }

        @keyframes glowRed {
            0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.4); }
            50% { box-shadow: 0 0 20px 10px rgba(231, 76, 60, 0.6); }
            100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.4); }
        }

        @keyframes glowGreen {
            0% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.4); }
            50% { box-shadow: 0 0 20px 10px rgba(39, 174, 96, 0.6); }
            100% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.4); }
        }

        @keyframes flyToCart {
            0% {
                transform: scale(1) translate(0, 0);
                opacity: 1;
            }
            50% {
                transform: scale(0.3) translate(100px, -100px);
                opacity: 0.7;
            }
            100% {
                transform: scale(0) translate(300px, -200px);
                opacity: 0;
            }
        }

        @keyframes lightningFlash {
            0% {
                text-shadow: 0 0 5px #fff, 0 0 10px #ff0, 0 0 15px #ff0, 0 0 20px #ff7e00;
                color: #ffcc00;
            }
            20% {
                text-shadow: 0 0 20px #fff, 0 0 30px #ff0, 0 0 40px #ff7e00, 0 0 50px #ff4400;
                color: #ffff66;
            }
            40% {
                text-shadow: 0 0 5px #fff, 0 0 10px #ff0, 0 0 15px #ff0, 0 0 20px #ff7e00;
                color: #ffcc00;
            }
            60% {
                text-shadow: 0 0 20px #fff, 0 0 35px #ff0, 0 0 45px #ff7e00, 0 0 60px #ff4400;
                color: #ffff88;
            }
            80% {
                text-shadow: 0 0 5px #fff, 0 0 10px #ff0, 0 0 15px #ff0, 0 0 20px #ff7e00;
                color: #ffcc00;
            }
            100% {
                text-shadow: 0 0 15px #fff, 0 0 25px #ff0, 0 0 35px #ff7e00, 0 0 45px #ff4400;
                color: #ffff66;
            }
        }

        .animate-fly {
            animation: flyToCart 0.6s ease-in forwards !important;
            position: fixed !important;
            z-index: 9999 !important;
            pointer-events: none !important;
        }

        .cart-icon-animate {
            animation: pulse 0.3s ease-in-out;
        }

        .lightning {
            animation: lightningFlash 0.8s ease-in-out infinite;
            display: inline-block;
        }

        /* Анимации для появления элементов */
        .fade-up {
            animation: fadeInUp 0.6s ease-out forwards;
        }

        .fade-left {
            animation: fadeInLeft 0.6s ease-out forwards;
        }

        .fade-right {
            animation: fadeInRight 0.6s ease-out forwards;
        }

        .scale-in {
            animation: scaleIn 0.5s ease-out forwards;
        }

        .hero {
            animation: fadeInUp 0.8s ease-out;
        }

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

        .team-card[data-role="director"]:hover {
            animation: glowRed 1s ease-in-out infinite;
            border-color: #e74c3c;
            transform: scale(1.02);
        }

        .team-card[data-role="manager"]:hover {
            animation: glowYellow 1s ease-in-out infinite;
            border-color: #f1c40f;
            transform: scale(1.02);
        }

        .team-card[data-role="admin"]:hover {
            animation: glowBlue 1s ease-in-out infinite;
            border-color: #3498db;
            transform: scale(1.02);
        }

        /* ==================== МОБИЛЬНОЕ МЕНЮ (выезжающее) ==================== */
        .mobile-menu-toggle {
            display: none;
            background: none;
            border: none;
            color: #27ae60;
            font-size: 1.8rem;
            cursor: pointer;
            padding: 0.5rem;
            transition: all 0.3s ease;
            z-index: 1002;
        }

        .mobile-menu-toggle:hover {
            transform: scale(1.1);
        }

        .mobile-menu-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1003;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .mobile-menu-overlay.active {
            display: block;
            opacity: 1;
        }

        .mobile-menu {
            position: fixed;
            top: 0;
            left: -280px;
            width: 280px;
            height: 100%;
            background: #0a0a0a;
            z-index: 1004;
            transition: left 0.3s ease;
            box-shadow: 2px 0 10px rgba(0,0,0,0.5);
            padding: 1rem;
            overflow-y: auto;
        }

        .mobile-menu.open {
            left: 0;
        }

        .mobile-menu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 1rem;
        }

        .mobile-menu-header h3 {
            color: #27ae60;
            font-size: 1.2rem;
        }

        .mobile-menu-close {
            background: none;
            border: none;
            color: #888;
            font-size: 1.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .mobile-menu-close:hover {
            color: #e74c3c;
            transform: scale(1.1);
        }

        .mobile-nav-link {
            display: block;
            padding: 0.8rem 0;
            color: #e0e0e0;
            text-decoration: none;
            font-size: 1rem;
            transition: all 0.3s ease;
            border-bottom: 1px solid #2a2a2a;
        }

        .mobile-nav-link:hover {
            color: #27ae60;
            padding-left: 0.5rem;
        }

        /* ==================== ХЕДЕР ==================== */
        .header {
            background: #0a0a0a;
            border-bottom: 1px solid #2a2a2a;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1280px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        /* Адаптив для телефона */
        @media (max-width: 768px) {
            .header-content {
                position: relative;
                justify-content: center;
            }
            .mobile-menu-toggle {
                display: block;
                position: absolute;
                left: 1rem;
                top: 50%;
                transform: translateY(-50%);
            }
            .nav-links {
                display: none;
            }
            .logo {
                margin: 0 auto;
            }
            .user-icon {
                position: absolute;
                right: 4rem;
                top: 50%;
                transform: translateY(-50%);
            }
            .cart-icon {
                position: absolute;
                right: 1rem;
                top: 50%;
                transform: translateY(-50%);
            }
            .products-grid {
                grid-template-columns: 1fr !important;
            }
            .team-grid {
                grid-template-columns: 1fr !important;
            }
            .catalog-page-wrapper {
                flex-direction: column;
            }
            .catalog-sidebar {
                width: 100%;
                position: static;
            }
            .contacts-grid {
                grid-template-columns: 1fr !important;
            }
            .footer-content {
                flex-direction: column;
                text-align: center;
            }
            .footer-section {
                flex-wrap: wrap;
                justify-content: center;
            }
            .cart-panel {
                width: 100% !important;
                right: -100% !important;
            }
            .payment-methods {
                flex-direction: column;
            }
            .home-reviews-grid {
                grid-template-columns: 1fr;
            }
            .chat-window {
                width: 90%;
                right: 5%;
                left: 5%;
                bottom: 95px;
                height: 450px;
            }
            .chat-button {
                bottom: 15px;
                right: 15px;
                width: 50px;
                height: 50px;
                font-size: 20px;
            }
            .search-bar-full {
                padding: 0.5rem 1rem;
            }
            .hero h1 {
                font-size: 1.5rem;
            }
            .hero {
                padding: 2rem 1rem;
            }
            .container {
                padding: 1rem;
            }
            .admin-tabs {
                gap: 0.5rem;
            }
            .admin-tab {
                font-size: 0.7rem;
                padding: 0.3rem 0.5rem;
            }
            .admin-user-actions {
                flex-direction: column;
                align-items: stretch;
            }
            .admin-user-actions select,
            .admin-user-actions input,
            .admin-user-actions button {
                width: 100%;
                margin: 0.2rem 0;
            }
        }

        @media (min-width: 769px) {
            .mobile-menu-toggle, .mobile-menu, .mobile-menu-overlay {
                display: none !important;
            }
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .logo:hover {
            opacity: 0.8;
            transform: scale(1.02);
        }

        .logo-icon {
            font-size: 1.8rem;
            font-weight: 300;
            display: inline-block;
            transition: all 0.3s ease;
        }

        .logo-icon:hover {
            animation: lightningFlash 0.5s ease-in-out;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: 2px;
            background: linear-gradient(135deg, #fff, #27ae60);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .nav-links {
            display: flex;
            gap: 2rem;
            align-items: center;
            flex-wrap: wrap;
        }

        .nav-link {
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
        }

        .nav-link::after {
            content: '';
            position: absolute;
            bottom: -5px;
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
            opacity: 1;
            color: #27ae60;
        }

        .nav-link.active {
            color: #27ae60;
        }

        .nav-link.active::after {
            width: 100%;
        }

        /* Поисковая строка на всю ширину */
        .search-bar-full {
            background: #0f0f0f;
            border-top: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a;
            padding: 0.75rem 2rem;
            width: 100%;
        }

        .search-container {
            max-width: 1280px;
            margin: 0 auto;
            display: flex;
            gap: 0.5rem;
        }

        .search-input-full {
            flex: 1;
            padding: 0.75rem 1.25rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 1rem;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .search-input-full:focus {
            outline: none;
            border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .search-btn-full {
            padding: 0.75rem 1.5rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
            border-radius: 8px;
            transition: all 0.3s ease;
            font-weight: 500;
        }

        .search-btn-full:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .user-icon {
            position: relative;
            cursor: pointer;
            font-size: 1.25rem;
            padding: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .user-icon:hover {
            background: #2a2a2a;
            transform: scale(1.05);
        }

        .user-name {
            font-size: 0.9rem;
            color: #27ae60;
        }

        .cart-icon {
            position: relative;
            cursor: pointer;
            font-size: 1.25rem;
            padding: 0.5rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .cart-icon:hover {
            transform: scale(1.1);
            background: #2a2a2a;
        }

        .cart-count {
            position: absolute;
            top: 0;
            right: 0;
            background: #e74c3c;
            color: white;
            font-size: 0.7rem;
            padding: 0.15rem 0.4rem;
            border-radius: 2px;
        }

        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 2rem;
            flex: 1;
        }

        /* Боковая панель категорий - только для каталога */
        .catalog-page-wrapper {
            display: flex;
            gap: 2rem;
        }

        .catalog-sidebar {
            width: 260px;
            flex-shrink: 0;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            height: fit-content;
            position: sticky;
            top: 90px;
        }

        .catalog-sidebar h3 {
            color: #27ae60;
            font-size: 1rem;
            margin-bottom: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .category-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .category-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.6rem 0.8rem;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 8px;
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
            font-size: 1.2rem;
        }

        .category-name {
            font-size: 0.9rem;
        }

        .main-content {
            flex: 1;
            min-width: 0;
        }

        .admin-panel {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
        }

        .admin-tabs {
            display: flex;
            gap: 1rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        .admin-tab {
            padding: 0.5rem 1rem;
            cursor: pointer;
            color: #888;
            transition: all 0.3s ease;
        }

        .admin-tab:hover {
            color: #27ae60;
        }

        .admin-tab.active {
            color: #27ae60;
            border-bottom: 2px solid #27ae60;
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
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .admin-form:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }

        .admin-form input, .admin-form textarea, .admin-form select {
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1rem;
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
            padding: 0.75rem 1.5rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .admin-form button:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .admin-products-grid {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .admin-product-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            transition: all 0.3s ease;
        }

        .admin-product-card:hover {
            transform: translateX(5px);
            border-color: #27ae60;
        }

        .admin-product-info {
            flex: 1;
            min-width: 200px;
        }

        .admin-product-name {
            font-weight: bold;
            font-size: 1rem;
            color: #27ae60;
        }

        .admin-product-price {
            font-size: 0.85rem;
            color: #888;
            margin-top: 0.25rem;
        }

        .admin-product-actions {
            display: flex;
            gap: 0.5rem;
        }

        .admin-product-actions button {
            padding: 0.5rem 1rem;
            margin: 0;
        }

        .admin-news-list {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .admin-news-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            transition: all 0.3s ease;
        }

        .admin-news-card:hover {
            transform: translateX(5px);
            border-color: #27ae60;
        }

        .admin-news-info {
            flex: 1;
        }

        .admin-news-title {
            font-weight: bold;
            font-size: 1rem;
            color: #27ae60;
        }

        .admin-news-date {
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.25rem;
        }

        .admin-news-actions {
            display: flex;
            gap: 0.5rem;
        }

        .admin-users-list {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .admin-user-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            transition: all 0.3s ease;
        }

        .admin-user-card:hover {
            transform: translateX(5px);
            border-color: #27ae60;
        }

        .admin-user-info {
            flex: 1;
        }

        .admin-user-email {
            font-weight: bold;
            font-size: 1rem;
            color: #27ae60;
        }

        .admin-user-details {
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.25rem;
        }

        .admin-user-actions {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .ban-select {
            padding: 0.3rem;
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 3px;
        }

        .ban-reason-input, .ban-message-input {
            width: 200px;
            padding: 0.3rem;
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 3px;
            font-size: 0.8rem;
        }

        .admin-promocodes-list {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .admin-promocode-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            transition: all 0.3s ease;
        }

        .admin-promocode-card:hover {
            transform: translateX(5px);
            border-color: #27ae60;
        }

        .admin-promocode-info {
            flex: 1;
        }

        .admin-promocode-code {
            font-weight: bold;
            font-size: 1rem;
            color: #27ae60;
            font-family: monospace;
        }

        .admin-promocode-details {
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.25rem;
        }

        .admin-promocode-status {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
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

        .admin-table {
            width: 100%;
            border-collapse: collapse;
        }

        .admin-table th, .admin-table td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #2a2a2a;
        }

        .admin-table th {
            background: #1a1a1a;
            color: #27ae60;
        }

        .delete-btn, .edit-btn, .toggle-btn, .ban-btn, .unban-btn {
            padding: 0.25rem 0.5rem;
            cursor: pointer;
            border: none;
            margin: 0 0.25rem;
            border-radius: 4px;
            transition: all 0.3s ease;
        }

        .delete-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .edit-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .toggle-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .ban-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .unban-btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }

        .delete-btn {
            background: #e74c3c;
            color: white;
        }

        .edit-btn {
            background: #27ae60;
            color: white;
        }

        .toggle-btn {
            background: #f39c12;
            color: white;
        }

        .ban-btn {
            background: #e74c3c;
            color: white;
        }

        .unban-btn {
            background: #27ae60;
            color: white;
        }

        .hero {
            padding: 4rem 2rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 2rem;
            text-align: center;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a2a1a 100%);
            border-radius: 12px;
        }

        .hero h1 {
            font-size: 2.5rem;
            font-weight: 500;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #fff, #27ae60);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .hero p {
            color: #888;
            font-size: 1.1rem;
        }

        .team-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
        }

        .team-title {
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 1.5rem;
            text-align: center;
            color: #e0e0e0;
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
            border-radius: 12px;
        }

        .team-card:hover {
            transform: translateY(-5px);
            border-color: #27ae60;
        }

        .team-card.center {
            transform: scale(1.02);
            border-color: #27ae60;
        }

        .team-avatar {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            margin: 0 auto 1rem;
            background-size: cover;
            background-position: center;
            border: 3px solid #2a2a2a;
            transition: all 0.3s ease;
        }

        .team-card:hover .team-avatar {
            transform: scale(1.05);
        }

        .team-card.center .team-avatar {
            border-color: #27ae60;
        }

        .team-name {
            font-size: 1.2rem;
            font-weight: 500;
            margin-bottom: 0.25rem;
            color: #e0e0e0;
        }

        .team-position {
            font-size: 0.85rem;
            color: #27ae60;
            margin-bottom: 0.75rem;
        }

        .team-description {
            font-size: 0.85rem;
            color: #888;
            line-height: 1.4;
        }

        .news-carousel-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            position: relative;
            border-radius: 12px;
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
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
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
            padding: 1rem;
        }

        .news-card {
            flex: 1;
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        }

        .news-card:hover {
            transform: translateY(-5px);
            border-color: #27ae60;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }

        .news-card-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            transition: transform 0.3s ease;
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
            font-size: 1rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: #e0e0e0;
        }

        .news-card-text {
            font-size: 0.85rem;
            color: #888;
            line-height: 1.4;
        }

        .carousel-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0,0,0,0.7);
            color: white;
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.5rem;
            z-index: 10;
            transition: all 0.3s ease;
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
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #3a3a3a;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .dot:hover {
            background: #27ae60;
        }

        .dot.active {
            background: #27ae60;
            width: 20px;
            border-radius: 5px;
        }

        .news-modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .news-modal-content {
            background: #0f0f0f;
            margin: 5% auto;
            width: 90%;
            max-width: 800px;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            overflow: hidden;
            animation: scaleIn 0.4s ease-out;
        }

        .news-modal-header {
            padding: 1.25rem;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .news-modal-header h2 {
            font-size: 1.3rem;
            color: #e0e0e0;
        }

        .news-modal-body {
            padding: 1.5rem;
        }

        .news-modal-image {
            width: 100%;
            max-height: 400px;
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
            font-size: 1rem;
        }

        .close-news-modal {
            font-size: 1.5rem;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
        }

        .close-news-modal:hover {
            color: #fff;
            transform: scale(1.1);
        }

        .verify-modal {
            display: none;
            position: fixed;
            z-index: 3000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .verify-container {
            background: #0f0f0f;
            margin: 10% auto;
            width: 90%;
            max-width: 450px;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            text-align: center;
            border-radius: 12px;
            animation: scaleIn 0.4s ease-out;
        }

        .verify-code-input {
            width: 100%;
            padding: 1rem;
            font-size: 1.5rem;
            text-align: center;
            letter-spacing: 5px;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            margin: 1rem 0;
            font-family: monospace;
            border-radius: 8px;
        }

        .verify-timer {
            color: #27ae60;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }

        .resend-code-btn {
            background: transparent;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            padding: 0.5rem 1rem;
            cursor: pointer;
            margin-top: 0.5rem;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .resend-code-btn:hover {
            border-color: #27ae60;
            color: #27ae60;
            transform: scale(1.02);
        }

        .reset-modal {
            display: none;
            position: fixed;
            z-index: 3000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .reset-container {
            background: #0f0f0f;
            margin: 10% auto;
            width: 90%;
            max-width: 450px;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            text-align: center;
            border-radius: 12px;
            animation: scaleIn 0.4s ease-out;
        }

        .profile-form-modal {
            display: none;
            position: fixed;
            z-index: 4000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .profile-form-container {
            background: #0f0f0f;
            margin: 10% auto;
            width: 90%;
            max-width: 450px;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            border-radius: 12px;
            animation: scaleIn 0.4s ease-out;
        }

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
            border-radius: 12px;
        }

        .contact-card:hover {
            border-color: #27ae60;
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }

        .contact-icon {
            font-size: 2rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }

        .contact-card:hover .contact-icon {
            transform: scale(1.1);
        }

        .contact-title {
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 1rem;
            color: #27ae60;
        }

        .contact-value {
            color: #e0e0e0;
            line-height: 1.6;
        }

        .map-placeholder {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            text-align: center;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .map-placeholder:hover {
            border-color: #27ae60;
        }

        .reviews-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
        }

        .reviews-title {
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 1.5rem;
            color: #e0e0e0;
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
            border-radius: 8px;
        }

        .home-review-card:hover {
            border-color: #27ae60;
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
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
            font-weight: 500;
            color: #27ae60;
            font-size: 0.9rem;
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
            font-size: 0.9rem;
            color: #555;
        }

        .home-review-stars .star-static.active {
            color: #ffc107;
        }

        .home-review-text {
            color: #bbb;
            font-size: 0.85rem;
            line-height: 1.5;
        }

        /* Стили для влога */
        .vlog-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
        }

        .vlog-content {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .vlog-text {
            background: #1a1a1a;
            padding: 1.5rem;
            border-radius: 12px;
            line-height: 1.6;
            color: #bbb;
            font-size: 1rem;
            border-left: 3px solid #27ae60;
            white-space: pre-wrap;
        }

        .vlog-edit-btn {
            align-self: flex-end;
            padding: 0.5rem 1rem;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .vlog-edit-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        /* Модальное окно для предложений */
        .feedback-modal {
            display: none;
            position: fixed;
            z-index: 5000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .feedback-container {
            background: #0f0f0f;
            margin: 10% auto;
            width: 90%;
            max-width: 500px;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            border-radius: 12px;
            position: relative;
            animation: scaleIn 0.4s ease-out;
        }

        .feedback-container h3 {
            color: #27ae60;
            margin-bottom: 1rem;
        }

        .feedback-container p {
            color: #888;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }

        .feedback-textarea {
            width: 100%;
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 8px;
            resize: vertical;
            font-family: inherit;
        }

        .feedback-textarea:focus {
            outline: none;
            border-color: #27ae60;
        }

        .feedback-send-btn {
            flex: 1;
            padding: 0.75rem;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .feedback-send-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .feedback-cancel-btn {
            flex: 1;
            padding: 0.75rem;
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .feedback-cancel-btn:hover {
            background: #c0392b;
            transform: scale(1.02);
        }

        .close-feedback {
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.5rem;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
        }

        .close-feedback:hover {
            color: #fff;
            transform: scale(1.1);
        }

        .promo-section {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
        }

        .promo-title {
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 1rem;
        }

        .promo-codes {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.75rem;
        }

        .promo-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 0.75rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .promo-card:hover {
            border-color: #27ae60;
            transform: translateY(-2px);
            animation: glowGreen 0.5s ease;
        }

        .promo-code {
            font-family: monospace;
            font-size: 1rem;
            font-weight: 500;
        }

        .promo-discount {
            font-size: 0.8rem;
            color: #27ae60;
        }

        .page-header {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .page-header h1 {
            font-size: 1.5rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .products-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
        }

        @media (max-width: 1024px) {
            .products-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 768px) {
            .products-grid {
                grid-template-columns: 1fr;
            }
            .catalog-page-wrapper {
                flex-direction: column;
            }
            .catalog-sidebar {
                width: 100%;
                position: static;
            }
            .team-grid {
                grid-template-columns: 1fr;
                gap: 1rem;
            }
            .team-card.center {
                transform: scale(1);
                order: -1;
            }
            .contacts-grid {
                grid-template-columns: 1fr;
            }
        }

        .product-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            border-radius: 12px;
        }

        .product-card:hover {
            border-color: #27ae60;
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }

        .product-card:hover .product-image {
            transform: scale(1.05);
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
            padding: 5px 30px;
            transform: rotate(45deg);
            font-size: 12px;
            font-weight: bold;
            z-index: 1;
            animation: shine 2s infinite linear;
            background: linear-gradient(90deg, #e74c3c, #ff6b6b, #e74c3c);
            background-size: 200% auto;
        }

        .discount-badge {
            position: absolute;
            top: 10px;
            left: 10px;
            background: #e74c3c;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
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

        .product-info {
            padding: 1rem;
        }

        .product-title {
            font-size: 0.9rem;
            font-weight: 500;
        }

        .product-price {
            font-size: 1rem;
            font-weight: 500;
            margin: 0.5rem 0;
        }

        .product-price.super-price {
            color: #e74c3c;
            font-size: 1.3rem;
            font-weight: bold;
        }

        .old-price {
            text-decoration: line-through;
            color: #666;
            font-size: 0.8rem;
            margin-left: 0.5rem;
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
            border-radius: 6px;
        }

        .add-to-cart:hover {
            background: #27ae60;
            border-color: #27ae60;
            transform: scale(1.02);
        }

        .reviews-container {
            width: 100%;
            margin: 0;
            padding: 0;
        }

        .write-review {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            margin-bottom: 2rem;
            width: 100%;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .write-review:hover {
            border-color: #27ae60;
        }

        .write-review h3 {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #27ae60;
        }

        .stars-rating {
            display: flex;
            gap: 0.5rem;
            margin: 1rem 0;
            direction: row;
            justify-content: center;
        }

        .star {
            font-size: 2.5rem;
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
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .review-name-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .review-input {
            width: 100%;
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 1rem;
            resize: vertical;
            font-family: inherit;
            border-radius: 8px;
            min-height: 120px;
            transition: all 0.3s ease;
        }

        .review-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        .submit-review-btn {
            padding: 1rem 2rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 1rem;
            border-radius: 8px;
            width: 100%;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .submit-review-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .reviews-list {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            width: 100%;
            border-radius: 12px;
        }

        .review-item {
            padding: 1.5rem;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 1rem;
            position: relative;
            background: #1a1a1a;
            border-radius: 8px;
            width: 100%;
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
            font-size: 1.1rem;
        }

        .review-date {
            font-size: 0.85rem;
            color: #666;
        }

        .review-stars {
            display: flex;
            gap: 0.25rem;
            margin-bottom: 0.75rem;
        }

        .review-stars .star-static {
            font-size: 1.2rem;
            color: #555;
        }

        .review-stars .star-static.active {
            color: #ffc107;
        }

        .review-text {
            color: #bbb;
            line-height: 1.6;
            font-size: 1rem;
        }

        .profile-container {
            max-width: 1000px;
            margin: 0 auto;
        }

        .profile-info {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            margin-bottom: 2rem;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .profile-info:hover {
            border-color: #27ae60;
        }

        .profile-field {
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .profile-label {
            color: #888;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .profile-value {
            font-size: 1.1rem;
            margin-top: 0.25rem;
            color: #e0e0e0;
        }

        .personal-discount-info {
            background: #1a2a1a;
            border: 1px solid #27ae60;
            border-radius: 8px;
            padding: 0.75rem;
            margin-top: 1rem;
            text-align: center;
        }

        .personal-discount-info span {
            color: #27ae60;
            font-weight: bold;
            font-size: 1.1rem;
        }

        .orders-list {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            border-radius: 12px;
        }

        .order-card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .order-card:hover {
            border-color: #27ae60;
            transform: translateX(5px);
        }

        .order-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 0.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .order-number {
            font-weight: bold;
            color: #27ae60;
        }

        .order-status {
            background: #27ae60;
            padding: 0.25rem 0.5rem;
            font-size: 0.8rem;
            border-radius: 4px;
        }

        .order-date {
            color: #888;
            font-size: 0.8rem;
        }

        .order-items {
            margin: 1rem 0;
        }

        .order-item {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #2a2a2a;
        }

        .order-total {
            text-align: right;
            margin-top: 1rem;
            padding-top: 0.5rem;
            font-size: 1.1rem;
            font-weight: bold;
        }

        .logout-btn, .profile-edit-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid #e74c3c;
            color: #e74c3c;
            cursor: pointer;
            margin-top: 1rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .logout-btn:hover, .profile-edit-btn:hover {
            transform: scale(1.05);
        }

        .profile-edit-btn {
            border-color: #27ae60;
            color: #27ae60;
            margin-right: 1rem;
        }

        .checkout-page {
            max-width: 800px;
            margin: 0 auto;
        }

        .checkout-form {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            border-radius: 12px;
        }

        .form-group {
            margin-bottom: 1.5rem;
            position: relative;
        }

        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            color: #888;
        }

        .form-input {
            width: 100%;
            padding: 0.75rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            font-size: 1rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .form-input:focus {
            outline: none;
            border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.3);
        }

        /* Стили для поля с паролем и глазиком */
        .password-wrapper {
            position: relative;
            width: 100%;
        }

        .password-wrapper input {
            width: 100%;
            padding-right: 45px;
        }

        .toggle-password {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            cursor: pointer;
            font-size: 1.2rem;
            color: #888;
            transition: all 0.2s;
            background: transparent;
            border: none;
        }

        .toggle-password:hover {
            color: #27ae60;
        }

        .payment-methods {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
        }

        .payment-option {
            flex: 1;
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s ease;
            border-radius: 8px;
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
            border-radius: 8px;
            animation: fadeInUp 0.3s ease-out;
        }

        .delivery-info {
            background: #1a1a1a;
            padding: 1rem;
            margin: 1rem 0;
            border-left: 3px solid #27ae60;
            border-radius: 8px;
        }

        .submit-btn {
            width: 100%;
            padding: 1rem;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 1rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .submit-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .order-summary {
            background: #1a1a1a;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
        }

        .modal-content {
            background: #0f0f0f;
            margin: 5% auto;
            width: 90%;
            max-width: 700px;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            animation: scaleIn 0.4s ease-out;
        }

        .modal-header {
            padding: 1.25rem;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
        }

        .close {
            font-size: 1.5rem;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
        }

        .close:hover {
            color: #fff;
            transform: scale(1.1);
        }

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
            padding: 1.25rem;
            background: #0f0f0f;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
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
            padding: 1rem;
            border-bottom: 1px solid #2a2a2a;
            animation: fadeInRight 0.3s ease-out;
        }

        .cart-item button {
            transition: all 0.2s ease;
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

        .cart-item-title {
            font-weight: 500;
            margin-bottom: 0.25rem;
        }

        .cart-footer {
            padding: 1.25rem;
            border-top: 1px solid #2a2a2a;
        }

        .promo-input-group {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        .promo-input {
            flex: 1;
            padding: 0.5rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 6px;
        }

        .apply-promo-btn, .checkout-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            cursor: pointer;
            transition: all 0.3s ease;
            border-radius: 6px;
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

        .overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            transition: all 0.3s ease;
        }

        .hidden {
            display: none;
        }

        .auth-modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
        }

        .auth-container {
            background: #0f0f0f;
            margin: 5% auto;
            width: 90%;
            max-width: 450px;
            border: 1px solid #2a2a2a;
            padding: 2rem;
            border-radius: 12px;
            animation: scaleIn 0.4s ease-out;
        }

        .auth-tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            border-bottom: 1px solid #2a2a2a;
        }

        .auth-tab {
            padding: 0.5rem 1rem;
            cursor: pointer;
            color: #888;
            transition: all 0.3s ease;
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

        .auth-form.hidden {
            display: none;
        }

        .auth-input {
            padding: 0.75rem;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            transition: all 0.3s ease;
            border-radius: 8px;
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
            margin-top: 1rem;
            transition: all 0.3s ease;
            border-radius: 8px;
        }

        .auth-btn:hover {
            background: #229954;
            transform: scale(1.02);
        }

        .forgot-password {
            text-align: right;
            margin-top: -0.5rem;
        }

        .forgot-password a {
            color: #27ae60;
            font-size: 0.8rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
        }

        .forgot-password a:hover {
            text-decoration: underline;
            color: #229954;
        }

        /* Стили для чата-помощника с кнопками */
        .chat-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #27ae60;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 24px;
            z-index: 10000;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
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
            bottom: 95px;
            right: 20px;
            width: 380px;
            height: 500px;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            display: none;
            flex-direction: column;
            z-index: 10001;
            box-shadow: 0 5px 25px rgba(0,0,0,0.5);
            overflow: hidden;
            animation: scaleIn 0.3s ease-out;
        }

        .chat-window.open {
            display: flex;
        }

        .chat-header {
            padding: 1rem;
            background: #1a1a1a;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        .chat-header h3 {
            color: #27ae60;
            font-size: 1rem;
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
            padding: 0.6rem 1rem;
            border-radius: 12px;
            word-wrap: break-word;
            line-height: 1.4;
            font-size: 0.9rem;
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
            font-size: 0.75rem;
            text-align: center;
            border-radius: 15px;
            max-width: 90%;
        }

        .chat-buttons {
            padding: 1rem;
            border-top: 1px solid #2a2a2a;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            background: #0f0f0f;
            flex-shrink: 0;
        }

        .chat-question-btn {
            padding: 0.8rem;
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            border-radius: 8px;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }

        .chat-question-btn:hover {
            background: #27ae60;
            border-color: #27ae60;
            transform: translateY(-2px);
        }

        /* ФУТЕР В ОДНУ СТРОКУ */
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
            gap: 1.5rem;
        }

        .footer-section {
            display: flex;
            gap: 1.5rem;
            align-items: center;
        }

        .footer-section a, .footer-section span {
            color: #888;
            text-decoration: none;
            transition: color 0.2s;
            font-size: 0.85rem;
            white-space: nowrap;
        }

        .footer-section a:hover {
            color: #27ae60;
        }

        .footer-section h3 {
            display: none;
        }

        .footer-bottom {
            display: none;
        }

        @media (max-width: 768px) {
            .footer-content {
                flex-direction: column;
                text-align: center;
            }
            .footer-section {
                flex-wrap: wrap;
                justify-content: center;
            }
            .footer-section a, .footer-section span {
                white-space: normal;
            }
            .carousel-slide {
                flex-direction: column;
            }
            .contacts-grid {
                grid-template-columns: 1fr;
            }
            .cart-panel {
                width: 100%;
                right: -100%;
            }
            .header-content {
                flex-direction: column;
            }
            .payment-methods {
                flex-direction: column;
            }
            .home-reviews-grid {
                grid-template-columns: 1fr;
            }
            .profile-container {
                padding: 1rem;
            }
            .chat-window {
                width: 90%;
                right: 5%;
                left: 5%;
                bottom: 95px;
                height: 450px;
            }
            .chat-button {
                bottom: 15px;
                right: 15px;
                width: 50px;
                height: 50px;
                font-size: 20px;
            }
            .search-bar-full {
                padding: 0.5rem 1rem;
            }
        }
    </style>
</head>
<body>
    <!-- Мобильное меню (выезжающее) -->
    <button class="mobile-menu-toggle" onclick="toggleMobileMenu()">☰</button>
    <div class="mobile-menu-overlay" onclick="closeMobileMenu()"></div>
    <div class="mobile-menu" id="mobileMenu">
        <div class="mobile-menu-header">
            <h3>Меню</h3>
            <button class="mobile-menu-close" onclick="closeMobileMenu()">×</button>
        </div>
        <div class="mobile-nav-link" onclick="closeMobileMenu(); goToHome()">🏠 Главная</div>
        <div class="mobile-nav-link" onclick="closeMobileMenu(); goToCatalog()">📦 Каталог</div>
        <div class="mobile-nav-link" onclick="closeMobileMenu(); goToReviews()">⭐ Отзывы</div>
        <div class="mobile-nav-link" onclick="closeMobileMenu(); goToContacts()">📞 Контакты</div>
        <div class="mobile-nav-link" onclick="closeMobileMenu(); showInfoPage()">ℹ️ Информация</div>
        <div class="mobile-nav-link" id="mobileAdminLink" onclick="closeMobileMenu(); goToAdminPanel()" style="display:none">👑 Админ-панель</div>
        <div class="mobile-nav-link" id="mobileProfileLink" onclick="closeMobileMenu(); goToProfile()" style="display:none">👤 Профиль</div>
    </div>

    <div class="header">
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
                <div class="nav-link" id="adminLink" onclick="goToAdminPanel()" style="display: none;">Админ-панель</div>
                <div class="nav-link" id="profileLink" onclick="goToProfile()" style="display: none;">Профиль</div>
            </div>
            <div class="user-icon" onclick="showAuthModal()" id="userIcon">
                👤 <span id="userNameDisplay" class="user-name">Войти</span>
            </div>
            <div class="cart-icon" onclick="toggleCart()" id="cartIcon">
                🛒
                <span class="cart-count" id="cartCount">0</span>
            </div>
        </div>
        <!-- Поисковая строка на всю ширину, под навигацией, всегда пустая -->
        <div class="search-bar-full">
            <div class="search-container">
                <input type="text" class="search-input-full" id="searchInput" placeholder="Поиск услуг..." value="">
                <button class="search-btn-full" onclick="searchProducts()">Найти</button>
            </div>
        </div>
    </div>

    <div class="container">
        <div id="homePage">
            <div class="hero">
                <h1>Zetta - Профессиональная сборка ПК и IT-услуги</h1>
                <p>Ваш надёжный партнёр в мире IT-технологий</p>
            </div>

            <!-- 1. Активные промокоды -->
            <div class="promo-section">
                <div class="promo-title">Активные промокоды</div>
                <div class="promo-codes" id="promoCodes"></div>
            </div>

            <!-- 2. НАША КОМАНДА -->
            <div class="team-section">
                <div class="team-title">★ НАША КОМАНДА ★</div>
                <div class="team-grid">
                    <div class="team-card" data-role="admin">
                        <div class="team-avatar" style="background-image: url('https://randomuser.me/api/portraits/men/32.jpg');"></div>
                        <div class="team-name">Богдан Дмитриевич</div>
                        <div class="team-position">Главный системный администратор</div>
                        <div class="team-description">Эксперт по сборке ПК любой сложности, настройке серверов и IT-инфраструктуры. Соберёт компьютер быстро и качественно под любые задачи.</div>
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

            <!-- 3. НАШ БЛОГ / ВЛОГ -->
            <div class="vlog-section">
                <div class="team-title">★ НАШ БЛОГ / ВЛОГ ★</div>
                <div class="vlog-content">
                    <div class="vlog-text" id="vlogText">Загрузка...</div>
                    <button class="vlog-edit-btn" id="vlogEditBtn" style="display: none;" onclick="openVlogEditor()">✏️ Редактировать влог</button>
                </div>
            </div>

            <!-- 4. НОВОСТИ КОМПАНИИ -->
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

            <!-- 5. ОТЗЫВЫ НАШИХ КЛИЕНТОВ -->
            <div class="reviews-section" id="homeReviewsSection">
                <div class="reviews-title">★ ОТЗЫВЫ НАШИХ КЛИЕНТОВ ★</div>
                <div class="home-reviews-grid" id="homeReviewsGrid">
                    <div class="empty-reviews">Загрузка отзывов...</div>
                </div>
            </div>
        </div>

        <div id="catalogPage" class="hidden">
            <div class="catalog-page-wrapper">
                <div class="catalog-sidebar">
                    <h3>📂 Категории</h3>
                    <div class="category-list" id="categoryList">
                        <div class="category-item active" data-category="all" onclick="filterByCategory('all')">
                            <span class="category-icon">📦</span>
                            <span class="category-name">Всё</span>
                        </div>
                        <div class="category-item" data-category="computers" onclick="filterByCategory('computers')">
                            <span class="category-icon">💻</span>
                            <span class="category-name">Компьютеры</span>
                        </div>
                        <div class="category-item" data-category="services" onclick="filterByCategory('services')">
                            <span class="category-icon">🔧</span>
                            <span class="category-name">Услуги</span>
                        </div>
                        <div class="category-item" data-category="pc_build" onclick="filterByCategory('pc_build')">
                            <span class="category-icon">🛠️</span>
                            <span class="category-name">Сборка компьютера</span>
                        </div>
                        <div class="category-item" data-category="websites" onclick="filterByCategory('websites')">
                            <span class="category-icon">🌐</span>
                            <span class="category-name">Сайты</span>
                        </div>
                        <div class="category-item" data-category="components" onclick="filterByCategory('components')">
                            <span class="category-icon">🔩</span>
                            <span class="category-name">Комплектующие</span>
                        </div>
                    </div>
                </div>
                <div class="main-content">
                    <div class="page-header">
                        <h1>Каталог услуг</h1>
                    </div>
                    <div class="products-grid" id="catalogGrid"></div>
                </div>
            </div>
        </div>

        <div id="reviewsPage" class="hidden">
            <div class="page-header">
                <h1>Отзывы клиентов</h1>
            </div>
            <div class="reviews-container">
                <div class="write-review">
                    <h3>✍️ Оставить отзыв</h3>
                    <input type="text" class="review-name-input" id="reviewName" placeholder="Ваше имя">
                    <div class="stars-rating" id="starRating">
                        <span class="star" data-value="1">★</span>
                        <span class="star" data-value="2">★</span>
                        <span class="star" data-value="3">★</span>
                        <span class="star" data-value="4">★</span>
                        <span class="star" data-value="5">★</span>
                    </div>
                    <textarea class="review-input" id="reviewText" rows="4" placeholder="Поделитесь впечатлениями о наших услугах..."></textarea>
                    <button class="submit-review-btn" onclick="submitReview()">📝 Отправить отзыв</button>
                </div>

                <div class="reviews-list" id="reviewsList">
                    <div class="empty-reviews">Загрузка отзывов...</div>
                </div>
            </div>
        </div>

        <div id="contactsPage" class="hidden">
            <div class="page-header">
                <h1>Контакты</h1>
            </div>
            <div class="contacts-page">
                <div class="contacts-grid">
                    <div class="contact-card">
                        <div class="contact-icon">📍</div>
                        <div class="contact-title">АДРЕС</div>
                        <div class="contact-value">г. Барнаул, ул. Юрина, 182/7<br>7 подъезд, 3 этаж, офис 305</div>
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
                    <div class="contact-value">г. Барнаул, ул. Юрина, 182/7 (вход с торца здания, 7 подъезд)</div>
                    <div style="margin-top: 1rem; padding: 1rem; background: #1a1a1a; border-radius: 4px;">
                        <strong>ООО "Zetta"</strong><br>
                        ИНН: 2225557711 | ОГРН: 1222222003321
                    </div>
                </div>
            </div>
        </div>

        <div id="infoPage" class="hidden">
            <div class="page-header">
                <h1>Информация</h1>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 2rem;">
                <div class="admin-form" style="margin-bottom: 0;">
                    <h3 style="color: #27ae60; margin-bottom: 1rem;">🔒 Политика конфиденциальности</h3>
                    <p style="margin-bottom: 1rem; line-height: 1.6;">Мы уважаем ваше право на конфиденциальность и обязуемся защищать ваши персональные данные. Настоящая политика конфиденциальности объясняет, как мы собираем, используем и защищаем информацию, которую вы предоставляете при использовании нашего сайта.</p>
                    <p style="margin-bottom: 1rem;"><strong>1. Сбор информации</strong><br>Мы собираем информацию, которую вы предоставляете добровольно при регистрации, оформлении заказа или обращении в службу поддержки: имя, email, номер телефона, адрес доставки.</p>
                    <p style="margin-bottom: 1rem;"><strong>2. Использование информации</strong><br>Ваши данные используются исключительно для обработки заказов, доставки товаров и информирования о статусе заказа. Мы не передаём ваши данные третьим лицам без вашего согласия.</p>
                    <p style="margin-bottom: 1rem;"><strong>3. Защита данных</strong><br>Мы принимаем все необходимые меры для защиты ваших персональных данных от несанкционированного доступа, изменения, раскрытия или уничтожения.</p>
                    <p><strong>4. Контактная информация</strong><br>По всем вопросам, связанным с обработкой персональных данных, вы можете обратиться по email: <a href="mailto:vaincode@mail.ru" style="color: #27ae60;">vaincode@mail.ru</a></p>
                </div>

                <div class="admin-form" style="margin-bottom: 0;">
                    <h3 style="color: #27ae60; margin-bottom: 1rem;">❓ Часто задаваемые вопросы</h3>

                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Как заказать сборку ПК?</strong></p>
                        <p style="color: #888;">Выберите категорию "Сборка компьютера" в каталоге или свяжитесь с нашим менеджером для индивидуального подбора конфигурации.</p>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Какие способы оплаты доступны?</strong></p>
                        <p style="color: #888;">Вы можете оплатить заказ банковской картой онлайн или наличными при получении. При онлайн-оплате реквизиты для перевода будут отправлены на вашу почту после оформления заказа.</p>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Сколько стоит доставка?</strong></p>
                        <p style="color: #888;">Доставка осуществляется бесплатно! Срок доставки зависит от расстояния: до 50 км - 3 дня, до 100 км - 7 дней, более 100 км - 14 дней.</p>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Как использовать промокод?</strong></p>
                        <p style="color: #888;">Введите промокод в поле "Промокод" в корзине и нажмите "Применить". Скидка будет автоматически применена к вашему заказу.</p>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Как связаться со службой поддержки?</strong></p>
                        <p style="color: #888;">Вы можете связаться с нами по телефону <strong style="color: #27ae60;">+7 (952) 006-23-57</strong> или <strong style="color: #27ae60;">+7 (913) 244-77-07</strong>, или отправить письмо на <a href="mailto:vaincode@mail.ru" style="color: #27ae60;">vaincode@mail.ru</a>. Мы работаем ежедневно с 09:00 до 21:00.</p>
                    </div>
                </div>
            </div>
        </div>

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
                    <div id="personalDiscountBlock"></div>
                    <button class="profile-edit-btn" onclick="editProfile()">Редактировать профиль</button>
                    <button class="logout-btn" onclick="logout()">Выйти</button>
                </div>

                <div class="orders-list">
                    <div class="promo-title">История заказов</div>
                    <div id="ordersHistory"></div>
                </div>
            </div>
        </div>

        <div id="adminPage" class="hidden">
            <div class="page-header">
                <h1>Админ-панель</h1>
            </div>
            <div class="admin-panel">
                <div class="admin-tabs">
                    <div class="admin-tab active" onclick="switchAdminTab('products')">Товары</div>
                    <div class="admin-tab" onclick="switchAdminTab('news')">Новости</div>
                    <div class="admin-tab" onclick="switchAdminTab('promocodes')">Промокоды</div>
                    <div class="admin-tab" onclick="switchAdminTab('personal')">Персональные скидки</div>
                    <div class="admin-tab" onclick="switchAdminTab('reviews')">Отзывы</div>
                    <div class="admin-tab" onclick="switchAdminTab('orders')">Заказы</div>
                    <div class="admin-tab" onclick="switchAdminTab('users')">Пользователи</div>
                </div>

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

                <div id="adminNews" class="admin-section">
                    <div class="admin-form">
                        <h3>Добавить новость</h3>
                        <form id="addNewsForm" enctype="multipart/form-data">
                            <input type="text" id="newsTitle" placeholder="Заголовок" required>
                            <input type="text" id="newsShortText" placeholder="Краткий текст" required>
                            <textarea id="newsFullText" rows="5" placeholder="Полный текст новости"></textarea>
                            <input type="file" id="newsImage" accept="image/*">
                            <button type="button" onclick="addNews()">Добавить новость</button>
                        </form>
                    </div>
                    <div class="admin-form">
                        <h3>Список новостей</h3>
                        <div id="newsList"></div>
                    </div>
                </div>

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
                            <button type="button" onclick="addPromocode()">Добавить промокод</button>
                        </form>
                    </div>
                    <div class="admin-form">
                        <h3>Список промокодов</h3>
                        <div id="promocodesList"></div>
                    </div>
                </div>

                <div id="adminPersonal" class="admin-section">
                    <div class="admin-form">
                        <h3>Персональная скидка пользователю</h3>
                        <div>
                            <input type="text" id="personalUserEmail" placeholder="Email пользователя" style="margin-bottom: 0.5rem;">
                            <select id="personalDiscountType" style="margin-bottom: 0.5rem;">
                                <option value="percent">Процентная скидка</option>
                                <option value="fixed">Фиксированная скидка (₽)</option>
                            </select>
                            <input type="number" id="personalDiscountValue" placeholder="Величина скидки" style="margin-bottom: 0.5rem;">
                            <button type="button" onclick="setPersonalDiscount()">Установить скидку</button>
                            <button type="button" onclick="removePersonalDiscount()" style="margin-top: 0.5rem; background: #e74c3c;">Удалить скидку</button>
                        </div>
                    </div>
                </div>

                <div id="adminReviews" class="admin-section">
                    <div class="admin-form">
                        <h3>Список отзывов</h3>
                        <div id="adminReviewsList"></div>
                    </div>
                </div>

                <div id="adminOrders" class="admin-section">
                    <div class="admin-form">
                        <h3>Все заказы</h3>
                        <div id="adminOrdersList"></div>
                    </div>
                </div>

                <div id="adminUsers" class="admin-section">
                    <div class="admin-form">
                        <h3>Пользователи</h3>
                        <div id="usersList"></div>
                    </div>
                </div>
            </div>
        </div>

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
                                💳 Банковская карта
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

    <!-- ФУТЕР В ОДНУ СТРОКУ -->
    <footer class="footer">
        <div class="footer-content">
            <div class="footer-section">
                <a href="tel:+79520062357">📞 +7 (952) 006-23-57</a>
                <a href="tel:+79132447707">📞 +7 (913) 244-77-07</a>
                <a href="mailto:vaincode@mail.ru">✉️ vaincode@mail.ru</a>
                <span>📍 г. Барнаул, ул. Юрина, 182/7</span>
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

    <!-- Окно чата-помощника -->
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

    <!-- Модальное окно для отправки предложения/жалобы -->
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
                <div id="resetTimer" class="verify-timer">Код действителен: 5:00</div>
                <div class="password-wrapper">
                    <input type="password" id="newPassword" class="auth-input" placeholder="Новый пароль" style="width: 100%; margin: 1rem 0; padding-right: 45px;">
                    <button type="button" class="toggle-password" onclick="togglePasswordVisibility('newPassword')">👁️</button>
                </div>
                <div class="password-wrapper">
                    <input type="password" id="confirmNewPassword" class="auth-input" placeholder="Подтвердите пароль" style="width: 100%; margin: 1rem 0; padding-right: 45px;">
                    <button type="button" class="toggle-password" onclick="togglePasswordVisibility('confirmNewPassword')">👁️</button>
                </div>
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
                <img id="modalImage" style="width:200px; height:200px; object-fit:cover;">
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
                <div class="password-wrapper">
                    <input type="password" id="loginPassword" class="auth-input" placeholder="Пароль" style="padding-right: 45px;">
                    <button type="button" class="toggle-password" onclick="togglePasswordVisibility('loginPassword')">👁️</button>
                </div>
                <div class="forgot-password">
                    <a onclick="showForgotPasswordModal()">Забыли пароль?</a>
                </div>
                <button class="auth-btn" onclick="login()">Войти</button>
            </div>

            <div id="registerForm" class="auth-form hidden">
                <input type="text" id="regFullName" class="auth-input" placeholder="ФИО" required>
                <input type="email" id="regEmail" class="auth-input" placeholder="Email" required>
                <input type="tel" id="regPhone" class="auth-input" placeholder="Телефон" required>
                <div class="password-wrapper">
                    <input type="password" id="regPassword" class="auth-input" placeholder="Пароль" style="padding-right: 45px;">
                    <button type="button" class="toggle-password" onclick="togglePasswordVisibility('regPassword')">👁️</button>
                </div>
                <div class="password-wrapper">
                    <input type="password" id="regConfirmPassword" class="auth-input" placeholder="Подтверждение пароля" style="padding-right: 45px;">
                    <button type="button" class="toggle-password" onclick="togglePasswordVisibility('regConfirmPassword')">👁️</button>
                </div>
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
            <div id="promoMessage"></div>
            <div class="cart-total">Сумма: <span id="cartSubtotal">0</span> ₽</div>
            <div class="cart-discount" id="cartDiscount">Скидка: 0 ₽</div>
            <div class="cart-total">Итого: <span id="cartTotal">0</span> ₽</div>
            <button class="checkout-btn" onclick="goToCheckout()">Оформить заказ</button>
        </div>
    </div>

    <script>
        // ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
        let currentProduct = null;
        let currentPage = 'home';
        let selectedPayment = null;
        let currentCartData = null;
        let selectedRating = 0;
        let isLoggedIn = false;
        let isAdmin = false;
        let currentUser = null;
        let verifyTimerInterval = null;
        let resetTimerInterval = null;
        let pendingRegistration = null;
        let pendingResetEmail = null;

        let currentSlide = 0;
        const slidesPerView = 3;
        let newsData = [];
        let currentCategory = 'all';
        let currentSearchTerm = '';

        // ==================== МОБИЛЬНОЕ МЕНЮ ====================
        function toggleMobileMenu() {
            const menu = document.getElementById('mobileMenu');
            const overlay = document.querySelector('.mobile-menu-overlay');
            menu.classList.toggle('open');
            overlay.classList.toggle('active');
        }
        function closeMobileMenu() {
            const menu = document.getElementById('mobileMenu');
            const overlay = document.querySelector('.mobile-menu-overlay');
            menu.classList.remove('open');
            overlay.classList.remove('active');
        }

        // Функция для переключения видимости пароля
        function togglePasswordVisibility(inputId) {
            const input = document.getElementById(inputId);
            if (input.type === 'password') {
                input.type = 'text';
            } else {
                input.type = 'password';
            }
        }

        // Функция анимации полёта товара в корзину
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
                setTimeout(() => {
                    cartIcon.classList.remove('cart-icon-animate');
                }, 300);
            }, 600);
        }

        // Функции чата-помощника
        function toggleChat() {
            const win = document.getElementById('chatWindow');
            win.classList.toggle('open');
            if (win.classList.contains('open')) {
                if (window.chatResetTimer) clearTimeout(window.chatResetTimer);
                if (window.consultationButtons) {
                    const btnsContainer = document.getElementById('chatButtons');
                    btnsContainer.innerHTML = `
                        <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
                        <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
                        <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
                        <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
                        <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
                    `;
                    window.consultationButtons = false;
                }
            }
        }

        function addThankYouAndReset() {
            const messagesArea = document.getElementById('chatMessagesArea');
            const thankYouMsg = document.createElement('div');
            thankYouMsg.className = 'chat-message system';
            thankYouMsg.innerHTML = 'Спасибо что выбрали нас! с уважением команда ZETTA.';
            messagesArea.appendChild(thankYouMsg);
            messagesArea.scrollTop = messagesArea.scrollHeight;

            if (window.chatResetTimer) clearTimeout(window.chatResetTimer);
            window.chatResetTimer = setTimeout(() => {
                const btnsContainer = document.getElementById('chatButtons');
                btnsContainer.innerHTML = `
                    <button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button>
                    <button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button>
                    <button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button>
                    <button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button>
                    <button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>
                `;
                window.consultationButtons = false;
                window.chatResetTimer = null;
            }, 5000);
        }

        async function askQuestion(type) {
            const messagesArea = document.getElementById('chatMessagesArea');

            if (!isLoggedIn) {
                alert('Пожалуйста, войдите в аккаунт для использования чата');
                showAuthModal();
                return;
            }

            let responseText = '';
            let showThankYou = false;

            if (type === 'payment') {
                const userMsg = document.createElement('div');
                userMsg.className = 'chat-message user';
                userMsg.innerHTML = '💳 Проблемы с оплатой?';
                messagesArea.appendChild(userMsg);

                const res = await fetch('/api/chat/send-payment-question', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await res.json();
                if (data.success) {
                    responseText = data.response;
                }
                showThankYou = true;

            } else if (type === 'site_time') {
                const userMsg = document.createElement('div');
                userMsg.className = 'chat-message user';
                userMsg.innerHTML = '⏱️ Срок создания сайта?';
                messagesArea.appendChild(userMsg);

                const res = await fetch('/api/chat/site-creation-time', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await res.json();
                if (data.success) {
                    responseText = data.response;
                }
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
                window.consultationButtons = true;
                messagesArea.scrollTop = messagesArea.scrollHeight;
                return;

            } else if (type === 'cooperation') {
                const userMsg = document.createElement('div');
                userMsg.className = 'chat-message user';
                userMsg.innerHTML = '🤝 Сотрудничество и реклама!';
                messagesArea.appendChild(userMsg);

                const res = await fetch('/api/chat/cooperation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await res.json();
                if (data.success) {
                    responseText = data.response;
                }
                showThankYou = true;

            } else if (type === 'operator') {
                const userMsg = document.createElement('div');
                userMsg.className = 'chat-message user';
                userMsg.innerHTML = '👨‍💼 Помощь оператора!';
                messagesArea.appendChild(userMsg);

                const res = await fetch('/api/chat/send-operator-request', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await res.json();
                if (data.success) {
                    responseText = data.message;
                }
                showThankYou = true;
            }

            if (responseText) {
                setTimeout(() => {
                    const adminMsg = document.createElement('div');
                    adminMsg.className = 'chat-message admin';
                    adminMsg.innerHTML = responseText;
                    messagesArea.appendChild(adminMsg);
                    messagesArea.scrollTop = messagesArea.scrollHeight;

                    if (showThankYou) {
                        addThankYouAndReset();
                    }
                }, 500);
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

            const res = await fetch('/api/chat/consultation', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({choice: choice})
            });
            const data = await res.json();

            if (data.success) {
                setTimeout(() => {
                    const adminMsg = document.createElement('div');
                    adminMsg.className = 'chat-message admin';
                    adminMsg.innerHTML = data.response;
                    messagesArea.appendChild(adminMsg);
                    messagesArea.scrollTop = messagesArea.scrollHeight;

                    addThankYouAndReset();
                }, 500);
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
                window.consultationButtons = false;
            }, 300);
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }

        // Функции для влога
        function loadVlog() {
            fetch('/api/vlog')
                .then(res => res.json())
                .then(data => {
                    const vlogText = document.getElementById('vlogText');
                    if (vlogText) {
                        vlogText.innerHTML = data.text.replace(/\\n/g, '<br>');
                    }
                });
        }

        function openVlogEditor() {
            fetch('/api/vlog')
                .then(res => res.json())
                .then(data => {
                    const newText = prompt('Редактировать влог:', data.text);
                    if (newText !== null && newText !== data.text) {
                        fetch('/api/admin/update-vlog', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({text: newText})
                        }).then(res => res.json()).then(result => {
                            if (result.success) {
                                alert('Влог обновлён!');
                                loadVlog();
                            } else {
                                alert(result.message || 'Ошибка при обновлении');
                            }
                        });
                    }
                });
        }

        // Функции для предложений/жалоб
        function openFeedbackModal() {
            document.getElementById('feedbackModal').style.display = 'block';
            document.getElementById('feedbackMessage').value = '';
        }

        function closeFeedbackModal() {
            document.getElementById('feedbackModal').style.display = 'none';
        }

        function sendFeedback() {
            const message = document.getElementById('feedbackMessage').value.trim();
            if (!message) {
                alert('Введите сообщение');
                return;
            }

            fetch('/api/send-feedback', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert(data.message);
                    closeFeedbackModal();
                } else {
                    alert(data.message);
                }
            });
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

        function showInfoPage() {
            currentPage = 'info';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.remove('hidden');
        }

        function showPolicyPage() {
            showInfoPage();
            document.getElementById('infoPage').scrollIntoView({ behavior: 'smooth' });
        }

        function showFaqPage() {
            showInfoPage();
        }

        function loadNews() {
            fetch('/api/admin/news')
                .then(res => res.json())
                .then(news => {
                    newsData = news;
                    renderCarousel();
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
        }

        function submitAddNews() {
            const formData = new FormData();
            formData.append('title', document.getElementById('modalNewsTitle').value);
            formData.append('text', document.getElementById('modalNewsShortText').value);
            formData.append('fullText', document.getElementById('modalNewsFullText').value);
            const fileInput = document.getElementById('modalNewsImage');
            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            fetch('/api/admin/add-news', {
                method: 'POST',
                body: formData
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Новость добавлена');
                    closeAddNewsModal();
                    loadNews();
                    if (currentPage === 'admin') {
                        loadAdminNews();
                    }
                } else {
                    alert(data.message || 'Ошибка при добавлении новости');
                }
            });
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
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id, title: newTitle, text: newText, fullText: newFullText})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Новость обновлена');
                    loadNews();
                    if (currentPage === 'admin') {
                        loadAdminNews();
                    }
                } else {
                    alert(data.message);
                }
            });
        }

        function deleteNewsFromCarousel(id) {
            if (confirm('Удалить новость?')) {
                fetch('/api/admin/delete-news', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Новость удалена');
                        loadNews();
                        if (currentPage === 'admin') {
                            loadAdminNews();
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
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
                            <img src="${item.image}" class="news-card-image" alt="${item.title}" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'">
                            <div class="news-card-content">
                                <div class="news-card-date">${item.date}</div>
                                <div class="news-card-title">${item.title}</div>
                                <div class="news-card-text">${item.text}</div>
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
            const dots = document.querySelectorAll('.dot');
            container.style.transform = `translateX(-${currentSlide * 100}%)`;
            dots.forEach((dot, i) => {
                if (i === currentSlide) dot.classList.add('active');
                else dot.classList.remove('active');
            });
        }

        function goToAdminPanel() {
            if (!isAdmin) {
                alert('Доступ запрещён. Только для администраторов.');
                return;
            }
            currentPage = 'admin';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');
            document.getElementById('adminPage').classList.remove('hidden');

            loadAdminProducts();
            loadAdminNews();
            loadAdminPromocodes();
            loadAdminReviews();
            loadAdminOrders();
            loadAdminUsers();
        }

        function switchAdminTab(tab) {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));

            const tabs = ['products', 'news', 'promocodes', 'personal', 'reviews', 'orders', 'users'];
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

        function loadAdminProducts() {
            fetch('/api/admin/products')
                .then(res => res.json())
                .then(products => {
                    const container = document.getElementById('productsList');
                    if (products.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет услуг</div>';
                        return;
                    }
                    container.innerHTML = `
                        <div class="admin-products-grid">
                            ${products.map(p => `
                                <div class="admin-product-card">
                                    <div class="admin-product-info">
                                        <div class="admin-product-name">${escapeHtml(p.name)}</div>
                                        <div class="admin-product-price">
                                            ${p.sale_price ? `${p.sale_price.toLocaleString()} ₽ (было ${p.price.toLocaleString()} ₽, скидка ${p.discount_percent || Math.round((1 - p.sale_price / p.price) * 100)}%)` : `${p.price.toLocaleString()} ₽`}
                                            ${p.sale_price ? ` 🔥` : ''}
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
                });
        }

        function addProduct() {
            const name = document.getElementById('productName').value;
            const price = document.getElementById('productPrice').value;
            const salePrice = document.getElementById('productSalePrice').value;
            const discountPercent = document.getElementById('productDiscountPercent').value;
            const description = document.getElementById('productDescription').value;
            const category = document.getElementById('productCategory').value;

            if (!name || !price) {
                alert('Заполните название и цену');
                return;
            }

            const formData = new FormData();
            formData.append('name', name);
            formData.append('price', price);
            formData.append('sale_price', salePrice || '');
            formData.append('discount_percent', discountPercent || '0');
            formData.append('description', description);
            formData.append('category', category);
            const fileInput = document.getElementById('productImage');
            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            fetch('/api/admin/add-product', {
                method: 'POST',
                body: formData
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Услуга добавлена');
                    document.getElementById('productName').value = '';
                    document.getElementById('productPrice').value = '';
                    document.getElementById('productSalePrice').value = '';
                    document.getElementById('productDiscountPercent').value = '';
                    document.getElementById('productDescription').value = '';
                    document.getElementById('productImage').value = '';
                    loadAdminProducts();
                    loadCatalog();
                } else {
                    alert(data.message || 'Ошибка при добавлении');
                }
            });
        }

        function editProduct(id) {
            const newName = prompt('Введите новое название:');
            if (!newName) return;
            const newPrice = prompt('Введите обычную цену:');
            if (!newPrice) return;
            const newSalePrice = prompt('Введите цену со скидкой (оставьте пустым если скидки нет):');
            const newDiscountPercent = prompt('Введите процент скидки:');
            const newDesc = prompt('Введите новое описание:');
            const newCategory = prompt('Введите категорию (computers/services/pc_build/websites/components):', 'services');

            fetch('/api/admin/edit-product', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    id: id, 
                    name: newName, 
                    price: parseInt(newPrice),
                    sale_price: newSalePrice ? parseInt(newSalePrice) : null,
                    discount_percent: parseInt(newDiscountPercent) || 0,
                    description: newDesc,
                    category: newCategory
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Услуга обновлена');
                    loadAdminProducts();
                    loadCatalog();
                } else {
                    alert(data.message);
                }
            });
        }

        function deleteProduct(id) {
            if (confirm('Удалить услугу?')) {
                fetch('/api/admin/delete-product', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Услуга удалена');
                        loadAdminProducts();
                        loadCatalog();
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function addNews() {
            const title = document.getElementById('newsTitle').value;
            const text = document.getElementById('newsShortText').value;
            const fullText = document.getElementById('newsFullText').value;

            if (!title || !text) {
                alert('Заполните заголовок и краткий текст новости');
                return;
            }

            const formData = new FormData();
            formData.append('title', title);
            formData.append('text', text);
            formData.append('fullText', fullText);
            const fileInput = document.getElementById('newsImage');
            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            fetch('/api/admin/add-news', {
                method: 'POST',
                body: formData
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Новость добавлена');
                    document.getElementById('newsTitle').value = '';
                    document.getElementById('newsShortText').value = '';
                    document.getElementById('newsFullText').value = '';
                    document.getElementById('newsImage').value = '';
                    loadAdminNews();
                    loadNews();
                } else {
                    alert(data.message || 'Ошибка при добавлении новости');
                }
            });
        }

        function loadAdminNews() {
            fetch('/api/admin/news')
                .then(res => res.json())
                .then(news => {
                    const container = document.getElementById('newsList');
                    if (news.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет новостей</div>';
                        return;
                    }
                    container.innerHTML = `
                        <div class="admin-news-list">
                            ${news.map(n => `
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
                });
        }

        function editNews(id) {
            const newTitle = prompt('Введите новый заголовок:');
            if (!newTitle) return;
            const newText = prompt('Введите новый краткий текст:');
            if (!newText) return;
            const newFullText = prompt('Введите новый полный текст:');
            if (!newFullText) return;

            fetch('/api/admin/edit-news', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id, title: newTitle, text: newText, fullText: newFullText})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Новость обновлена');
                    loadAdminNews();
                    loadNews();
                } else {
                    alert(data.message);
                }
            });
        }

        function deleteNews(id) {
            if (confirm('Удалить новость?')) {
                fetch('/api/admin/delete-news', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Новость удалена');
                        loadAdminNews();
                        loadNews();
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function loadAdminPromocodes() {
            fetch('/api/admin/promocodes')
                .then(res => res.json())
                .then(promocodes => {
                    const container = document.getElementById('promocodesList');
                    const promocodesArray = Object.entries(promocodes);
                    if (promocodesArray.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет промокодов</div>';
                        return;
                    }
                    container.innerHTML = `
                        <div class="admin-promocodes-list">
                            ${promocodesArray.map(([code, data]) => `
                                <div class="admin-promocode-card">
                                    <div class="admin-promocode-info">
                                        <div class="admin-promocode-code">${code}</div>
                                        <div class="admin-promocode-details">
                                            Скидка: ${data.type === 'percent' ? data.discount + '%' : data.discount + ' ₽'}
                                            <span class="admin-promocode-status ${data.active ? 'active' : 'inactive'}">${data.active ? 'Активен' : 'Отключен'}</span>
                                        </div>
                                    </div>
                                    <div class="admin-promocode-actions">
                                        <button class="toggle-btn" onclick="togglePromocode('${code}')">${data.active ? 'Отключить' : 'Включить'}</button>
                                        <button class="delete-btn" onclick="deletePromocode('${code}')">🗑️</button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                });
        }

        function addPromocode() {
            const code = document.getElementById('promocodeCode').value.trim().toUpperCase();
            const type = document.getElementById('promocodeType').value;
            const discount = parseInt(document.getElementById('promocodeDiscount').value);

            if (!code) {
                alert('Введите код промокода');
                return;
            }
            if (!discount || discount <= 0) {
                alert('Введите корректную величину скидки');
                return;
            }

            fetch('/api/admin/add-promocode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code: code, type: type, discount: discount})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Промокод добавлен');
                    document.getElementById('promocodeCode').value = '';
                    document.getElementById('promocodeDiscount').value = '';
                    loadAdminPromocodes();
                    loadPromoCodesForFrontend();
                } else {
                    alert(data.message);
                }
            });
        }

        function togglePromocode(code) {
            fetch('/api/admin/toggle-promocode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code: code})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert(data.message);
                    loadAdminPromocodes();
                    loadPromoCodesForFrontend();
                } else {
                    alert(data.message);
                }
            });
        }

        function deletePromocode(code) {
            if (confirm(`Удалить промокод ${code}?`)) {
                fetch('/api/admin/delete-promocode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: code})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Промокод удалён');
                        loadAdminPromocodes();
                        loadPromoCodesForFrontend();
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function setPersonalDiscount() {
            const email = document.getElementById('personalUserEmail').value.trim();
            const type = document.getElementById('personalDiscountType').value;
            const discount = parseInt(document.getElementById('personalDiscountValue').value);

            if (!email) {
                alert('Введите email пользователя');
                return;
            }
            if (!discount || discount <= 0) {
                alert('Введите корректную величину скидки');
                return;
            }

            fetch('/api/admin/set-personal-discount', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email, type: type, discount: discount})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert(data.message);
                    document.getElementById('personalUserEmail').value = '';
                    document.getElementById('personalDiscountValue').value = '';
                    loadAdminUsers();
                } else {
                    alert(data.message);
                }
            });
        }

        function removePersonalDiscount() {
            const email = document.getElementById('personalUserEmail').value.trim();
            if (!email) {
                alert('Введите email пользователя');
                return;
            }

            fetch('/api/admin/remove-personal-discount', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert(data.message);
                    document.getElementById('personalUserEmail').value = '';
                    loadAdminUsers();
                } else {
                    alert(data.message);
                }
            });
        }

        function loadPromoCodesForFrontend() {
            fetch('/api/promocodes')
                .then(res => res.json())
                .then(promocodes => {
                    const container = document.getElementById('promoCodes');
                    if (container) {
                        const activePromocodes = Object.entries(promocodes).filter(([code, data]) => data.active);
                        if (activePromocodes.length === 0) {
                            container.innerHTML = '<div class="empty-reviews">Нет активных промокодов</div>';
                            return;
                        }
                        container.innerHTML = activePromocodes.map(([code, data]) => {
                            const discount = data.type === 'percent' ? `${data.discount}%` : `${data.discount} ₽`;
                            return `<div class="promo-card" onclick="copyPromoCode('${code}')">
                                <div class="promo-code">${code}</div>
                                <div class="promo-discount">-${discount}</div>
                            </div>`;
                        }).join('');
                    }
                });
        }

        function loadAdminReviews() {
            fetch('/api/reviews')
                .then(res => res.json())
                .then(reviews => {
                    const container = document.getElementById('adminReviewsList');
                    if (reviews.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет отзывов</div>';
                        return;
                    }
                    container.innerHTML = `
                        <table class="admin-table">
                            <thead><tr><th>Автор</th><th>Оценка</th><th>Текст</th><th>Дата</th><th>Действия</th></tr></thead>
                            <tbody>
                                ${reviews.map((r, idx) => `
                                    <tr>
                                        <td>${escapeHtml(r.name)}</td
                                        <td>${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</td
                                        <td>${escapeHtml(r.text.substring(0, 50))}${r.text.length > 50 ? '...' : ''}</td
                                        <td>${r.date}</td
                                        <td><button class="delete-btn" onclick="deleteReview(${idx})">🗑️</button></td
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                });
        }

        function deleteReview(index) {
            if (confirm('Удалить отзыв?')) {
                fetch('/api/admin/delete-review', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: index})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Отзыв удалён');
                        loadAdminReviews();
                        loadReviews();
                        loadHomeReviews();
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function loadAdminOrders() {
            fetch('/api/admin/orders')
                .then(res => res.json())
                .then(orders => {
                    const container = document.getElementById('adminOrdersList');
                    if (Object.keys(orders).length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет заказов</div>';
                        return;
                    }
                    let html = '';
                    for (const [email, userOrders] of Object.entries(orders)) {
                        html += `<h4 style="margin-top: 1rem; color: #27ae60;">Пользователь: ${escapeHtml(email)}</h4>`;
                        userOrders.forEach(order => {
                            html += `
                                <div class="order-card" style="margin-bottom: 1rem;">
                                    <div class="order-header">
                                        <span class="order-number">Заказ #${order.order_number}</span>
                                        <span class="order-status">${order.payment_method === 'card' ? 'Оплачен онлайн' : 'Ожидает оплаты'}</span>
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
                                </div>
                            `;
                        });
                    }
                    container.innerHTML = html;
                });
        }

        function loadAdminUsers() {
            fetch('/api/admin/users')
                .then(res => res.json())
                .then(users => {
                    const container = document.getElementById('usersList');
                    const usersArray = Object.values(users);
                    usersArray.sort((a, b) => {
                        if (!a.registered_at) return 1;
                        if (!b.registered_at) return -1;
                        const dateA = a.registered_at.split('.').reverse().join('-');
                        const dateB = b.registered_at.split('.').reverse().join('-');
                        return dateB.localeCompare(dateA);
                    });

                    if (usersArray.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Нет пользователей</div>';
                        return;
                    }
                    container.innerHTML = `
                        <div class="admin-users-list">
                            ${usersArray.map(u => {
                                const banSelectId = `banSelect_${u.email.replace(/[^a-zA-Z0-9]/g, '_')}`;
                                const personalDiscountText = u.personal_discount ? 
                                    ` | 🎁 Персональная скидка: ${u.personal_discount.type === 'percent' ? u.personal_discount.discount + '%' : u.personal_discount.discount + ' ₽'}` : '';
                                return `
                                <div class="admin-user-card">
                                    <div class="admin-user-info">
                                        <div class="admin-user-email">${escapeHtml(u.email)}</div>
                                        <div class="admin-user-details">
                                            ФИО: ${escapeHtml(u.full_name || '-')} | Телефон: ${escapeHtml(u.phone || '-')} | Регистрация: ${u.registered_at || '-'}
                                            ${u.is_admin ? ' | 👑 Администратор' : ''}
                                            ${personalDiscountText}
                                        </div>
                                    </div>
                                    <div class="admin-user-actions">
                                        ${!u.is_admin ? `<button class="edit-btn" onclick="makeAdmin('${u.email}')">Сделать админом</button>` : ''}
                                        ${u.is_admin ? `<button class="delete-btn" onclick="removeAdmin('${u.email}')">Удалить из админов</button>` : ''}
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
                            `}).join('')}
                        </div>
                    `;
                });
        }

        function makeAdmin(email) {
            if (confirm(`Сделать ${email} администратором?`)) {
                fetch('/api/admin/make-admin', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Пользователь стал администратором');
                        loadAdminUsers();
                        if (email === currentUser?.email) {
                            checkAuthStatus();
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function removeAdmin(email) {
            if (confirm(`Снять права администратора с ${email}?`)) {
                fetch('/api/admin/remove-admin', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Права администратора сняты');
                        loadAdminUsers();
                        if (email === currentUser?.email) {
                            checkAuthStatus();
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function banUser(email, minutes, reason, message) {
            if (!minutes || minutes === "") {
                alert('Выберите срок бана');
                return;
            }
            if (!reason || reason.trim() === "") {
                alert('Укажите причину бана');
                return;
            }
            if (!message || message.trim() === "") {
                alert('Укажите сообщение для пользователя');
                return;
            }
            if (confirm(`Забанить пользователя ${email} на ${minutes} минут(ы)?\nПричина: ${reason}\nСообщение: ${message}`)) {
                fetch('/api/admin/ban-user', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        email: email,
                        duration_minutes: parseInt(minutes),
                        reason: reason,
                        message: message
                    })
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert(data.message);
                        loadAdminUsers();
                        if (email === currentUser?.email) {
                            window.location.href = '/';
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function unbanUser(email) {
            if (confirm(`Снять бан с пользователя ${email}?`)) {
                fetch('/api/admin/unban-user', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Бан снят');
                        loadAdminUsers();
                        if (email === currentUser?.email) {
                            checkAuthStatus();
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function showForgotPasswordModal() {
            closeAuthModal();
            document.getElementById('resetStep1').style.display = 'block';
            document.getElementById('resetStep2').style.display = 'none';
            document.getElementById('resetEmail').value = '';
            document.getElementById('resetCode').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmNewPassword').value = '';
            document.getElementById('resetModal').style.display = 'block';
        }

        function closeResetModal() {
            if (resetTimerInterval) clearInterval(resetTimerInterval);
            document.getElementById('resetModal').style.display = 'none';
            pendingResetEmail = null;
        }

        function sendResetCode() {
            const email = document.getElementById('resetEmail').value;
            if (!email) {
                alert('Введите email');
                return;
            }

            fetch('/api/send-reset-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    pendingResetEmail = email;
                    document.getElementById('resetStep1').style.display = 'none';
                    document.getElementById('resetStep2').style.display = 'block';
                    startResetTimer(300);
                    alert('Код отправлен на почту');
                } else {
                    alert(data.message);
                }
            });
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
                }
                if (remaining < 0) {
                    clearInterval(resetTimerInterval);
                    timerEl.textContent = 'Код истёк. Запросите новый.';
                    timerEl.style.color = '#e74c3c';
                }
            }, 1000);
        }

        function resetPassword() {
            const code = document.getElementById('resetCode').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmPassword = document.getElementById('confirmNewPassword').value;

            if (!code || code.length !== 6) {
                alert('Введите 6-значный код');
                return;
            }
            if (newPassword.length < 6) {
                alert('Пароль должен содержать не менее 6 символов');
                return;
            }
            if (newPassword !== confirmPassword) {
                alert('Пароли не совпадают');
                return;
            }

            fetch('/api/reset-password', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: pendingResetEmail,
                    code: code,
                    new_password: newPassword
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    if (resetTimerInterval) clearInterval(resetTimerInterval);
                    closeResetModal();
                    alert('Пароль успешно изменён! Теперь войдите с новым паролем.');
                    showAuthModal();
                } else {
                    alert(data.message);
                }
            });
        }

        function startTimer(seconds, onTick, onComplete) {
            if (verifyTimerInterval) clearInterval(verifyTimerInterval);
            let remaining = seconds;
            onTick(remaining);
            verifyTimerInterval = setInterval(() => {
                remaining--;
                if (remaining >= 0) {
                    onTick(remaining);
                }
                if (remaining < 0) {
                    clearInterval(verifyTimerInterval);
                    if (onComplete) onComplete();
                }
            }, 1000);
        }

        function updateTimerDisplay(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const timerEl = document.getElementById('verifyTimer');
            if (timerEl) {
                if (seconds >= 0) {
                    timerEl.textContent = `Код действителен: ${mins}:${secs.toString().padStart(2, '0')}`;
                    timerEl.style.color = seconds < 60 ? '#e74c3c' : '#27ae60';
                } else {
                    timerEl.textContent = 'Код истёк. Запросите новый.';
                    timerEl.style.color = '#e74c3c';
                }
            }
        }

        function sendVerificationCode() {
            const fullName = document.getElementById('regFullName').value;
            const email = document.getElementById('regEmail').value;
            const phone = document.getElementById('regPhone').value;
            const password = document.getElementById('regPassword').value;
            const confirmPassword = document.getElementById('regConfirmPassword').value;

            if (!fullName || !email || !phone || !password) {
                alert('Заполните все поля');
                return;
            }

            if (password !== confirmPassword) {
                alert('Пароли не совпадают');
                return;
            }

            if (password.length < 6) {
                alert('Пароль должен содержать не менее 6 символов');
                return;
            }

            fetch('/api/send-verification', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: email,
                    full_name: fullName,
                    phone: phone,
                    password: password
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    pendingRegistration = {
                        email: email,
                        full_name: fullName,
                        phone: phone,
                        password: password
                    };
                    document.getElementById('verifyEmailDisplay').textContent = email;
                    document.getElementById('verifyModal').style.display = 'block';
                    document.getElementById('verifyCode').value = '';

                    startTimer(300, (seconds) => updateTimerDisplay(seconds), () => {
                        document.getElementById('verifyTimer').textContent = 'Код истёк. Запросите новый.';
                    });
                } else {
                    alert(data.message);
                }
            });
        }

        function verifyCode() {
            const code = document.getElementById('verifyCode').value;
            if (!code || code.length !== 6) {
                alert('Введите 6-значный код');
                return;
            }

            fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: pendingRegistration.email,
                    code: code
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    if (verifyTimerInterval) clearInterval(verifyTimerInterval);
                    document.getElementById('verifyModal').style.display = 'none';
                    alert('Регистрация успешна! Теперь войдите в аккаунт.');
                    switchAuthTab('login');
                    document.getElementById('loginEmail').value = pendingRegistration.email;
                    document.getElementById('loginPassword').value = '';
                    pendingRegistration = null;
                } else {
                    alert(data.message);
                }
            });
        }

        function resendCode() {
            if (!pendingRegistration) return;

            fetch('/api/resend-verification', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: pendingRegistration.email})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Новый код отправлен на почту');
                    startTimer(300, (seconds) => updateTimerDisplay(seconds), () => {
                        document.getElementById('verifyTimer').textContent = 'Код истёк. Запросите новый.';
                    });
                } else {
                    alert(data.message);
                }
            });
        }

        function checkAndShowProfileForm() {
            fetch('/api/check-profile-complete')
                .then(res => res.json())
                .then(data => {
                    if (!data.complete) {
                        document.getElementById('profileFullNameInput').value = currentUser ? currentUser.full_name : '';
                        document.getElementById('profileEmailInput').value = currentUser ? currentUser.email : '';
                        document.getElementById('profilePhoneInput').value = currentUser ? currentUser.phone : '';
                        document.getElementById('profileFormModal').style.display = 'block';
                    } else {
                        loadProfile();
                        loadOrdersHistory();
                    }
                });
        }

        function saveProfile() {
            const fullName = document.getElementById('profileFullNameInput').value;
            const phone = document.getElementById('profilePhoneInput').value;

            if (!fullName || !phone) {
                alert('Заполните все поля');
                return;
            }

            fetch('/api/update-profile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    full_name: fullName,
                    phone: phone
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    document.getElementById('profileFormModal').style.display = 'none';
                    alert('Профиль успешно обновлён!');
                    checkAuthStatus();
                    loadProfile();
                    loadOrdersHistory();
                } else {
                    alert('Ошибка при сохранении профиля');
                }
            });
        }

        window.onclick = function(event) {
            const modal = document.getElementById('newsModal');
            if (event.target === modal) {
                closeNewsModal();
            }
            const addModal = document.getElementById('addNewsModal');
            if (event.target === addModal) {
                closeAddNewsModal();
            }
            const verifyModal = document.getElementById('verifyModal');
            if (event.target === verifyModal) {
                if (verifyTimerInterval) clearInterval(verifyTimerInterval);
                verifyModal.style.display = 'none';
            }
            const resetModal = document.getElementById('resetModal');
            if (event.target === resetModal) {
                closeResetModal();
            }
            const profileModal = document.getElementById('profileFormModal');
            if (event.target === profileModal) {
                profileModal.style.display = 'none';
            }
            const productModal = document.getElementById('productModal');
            if (event.target === productModal) {
                closeModal();
            }
            const feedbackModal = document.getElementById('feedbackModal');
            if (event.target === feedbackModal) {
                closeFeedbackModal();
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            const stars = document.querySelectorAll('#starRating .star');
            stars.forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.getAttribute('data-value'));
                    stars.forEach(s => {
                        if (parseInt(s.getAttribute('data-value')) <= selectedRating) {
                            s.classList.add('active');
                        } else {
                            s.classList.remove('active');
                        }
                    });
                });
            });

            checkAuthStatus();
            loadNews();
            loadPromoCodesForFrontend();
            loadHomeReviews();
            loadVlog();
        });

        function checkAuthStatus() {
            fetch('/api/auth/status')
                .then(res => res.json())
                .then(data => {
                    if (data.logged_in) {
                        isLoggedIn = true;
                        isAdmin = data.is_admin === true;
                        currentUser = data.user;

                        const userNameSpan = document.getElementById('userNameDisplay');
                        if (userNameSpan) {
                            userNameSpan.textContent = data.user.full_name ? data.user.full_name.split(' ')[0] : data.user.email;
                        }

                        const profileLink = document.getElementById('profileLink');
                        if (profileLink) profileLink.style.display = 'block';

                        const addNewsBtn = document.getElementById('addNewsBtn');
                        if (addNewsBtn) {
                            addNewsBtn.style.display = isAdmin ? 'flex' : 'none';
                        }

                        const adminLink = document.getElementById('adminLink');
                        if (adminLink) {
                            adminLink.style.display = isAdmin ? 'block' : 'none';
                        }

                        const vlogEditBtn = document.getElementById('vlogEditBtn');
                        if (vlogEditBtn) {
                            vlogEditBtn.style.display = isAdmin ? 'block' : 'none';
                        }

                        // Показываем персональную скидку в профиле
                        if (currentUser && currentUser.personal_discount) {
                            const discountBlock = document.getElementById('personalDiscountBlock');
                            if (discountBlock) {
                                const discountText = currentUser.personal_discount.type === 'percent' ? 
                                    `${currentUser.personal_discount.discount}%` : 
                                    `${currentUser.personal_discount.discount} ₽`;
                                discountBlock.innerHTML = `
                                    <div class="personal-discount-info">
                                        🎁 <strong>ВАША ПЕРСОНАЛЬНАЯ СКИДКА НА ВЕСЬ АССОРТИМЕНТ:</strong> <span>${discountText}</span>
                                    </div>
                                `;
                            }
                        } else {
                            const discountBlock = document.getElementById('personalDiscountBlock');
                            if (discountBlock) discountBlock.innerHTML = '';
                        }
                    } else {
                        isLoggedIn = false;
                        isAdmin = false;
                        currentUser = null;

                        const userNameSpan = document.getElementById('userNameDisplay');
                        if (userNameSpan) userNameSpan.textContent = 'Войти';

                        const profileLink = document.getElementById('profileLink');
                        if (profileLink) profileLink.style.display = 'none';

                        const adminLink = document.getElementById('adminLink');
                        if (adminLink) adminLink.style.display = 'none';

                        const addNewsBtn = document.getElementById('addNewsBtn');
                        if (addNewsBtn) addNewsBtn.style.display = 'none';

                        const vlogEditBtn = document.getElementById('vlogEditBtn');
                        if (vlogEditBtn) vlogEditBtn.style.display = 'none';

                        const discountBlock = document.getElementById('personalDiscountBlock');
                        if (discountBlock) discountBlock.innerHTML = '';

                        if (data.banned) {
                            window.location.href = '/';
                        }
                    }

                    if (typeof renderCarousel === 'function') {
                        renderCarousel();
                    }
                })
                .catch(error => console.error('Ошибка проверки статуса:', error));
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
            const loginTab = document.querySelector('.auth-tabs .auth-tab');
            const registerTab = document.querySelectorAll('.auth-tabs .auth-tab')[1];

            if (tab === 'login') {
                loginTab.classList.add('active');
                registerTab.classList.remove('active');
                document.getElementById('loginForm').classList.remove('hidden');
                document.getElementById('registerForm').classList.add('hidden');
            } else {
                loginTab.classList.remove('active');
                registerTab.classList.add('active');
                document.getElementById('loginForm').classList.add('hidden');
                document.getElementById('registerForm').classList.remove('hidden');
            }
        }

        function login() {
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;

            if (!email || !password) {
                alert('Заполните все поля');
                return;
            }

            fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email, password: password})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Вход выполнен успешно!');
                    closeAuthModal();
                    checkAuthStatus();
                    if (currentPage === 'profile') {
                        checkAndShowProfileForm();
                    }
                    goToHome();
                } else {
                    alert(data.message);
                }
            });
        }

        function logout() {
            fetch('/api/auth/logout', {method: 'POST'})
                .then(res => res.json())
                .then(data => {
                    alert('Вы вышли из аккаунта');
                    checkAuthStatus();
                    goToHome();
                });
        }

        function goToProfile() {
            if (!isLoggedIn) {
                showAuthModal();
                return;
            }

            currentPage = 'profile';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');
            document.getElementById('profilePage').classList.remove('hidden');

            checkAndShowProfileForm();
        }

        function goToContacts() {
            currentPage = 'contacts';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.remove('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');
        }

        function loadProfile() {
            fetch('/api/user/profile')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('profileFullName').textContent = data.full_name;
                    document.getElementById('profileEmail').textContent = data.email;
                    document.getElementById('profilePhone').textContent = data.phone;
                    document.getElementById('profileRegistered').textContent = data.registered_at;

                    if (data.personal_discount) {
                        const discountBlock = document.getElementById('personalDiscountBlock');
                        if (discountBlock) {
                            const discountText = data.personal_discount.type === 'percent' ? 
                                `${data.personal_discount.discount}%` : 
                                `${data.personal_discount.discount} ₽`;
                            discountBlock.innerHTML = `
                                <div class="personal-discount-info">
                                    🎁 <strong>ВАША ПЕРСОНАЛЬНАЯ СКИДКА НА ВЕСЬ АССОРТИМЕНТ:</strong> <span>${discountText}</span>
                                </div>
                            `;
                        }
                    }
                });
        }

        function loadOrdersHistory() {
            fetch('/api/user/orders')
                .then(res => res.json())
                .then(orders => {
                    const container = document.getElementById('ordersHistory');
                    if (orders.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">У вас пока нет заказов</div>';
                        return;
                    }

                    container.innerHTML = orders.map(order => `
                        <div class="order-card">
                            <div class="order-header">
                                <span class="order-number">Заказ #${order.order_number}</span>
                                <span class="order-status">${order.payment_method === 'card' ? 'Оплачен онлайн' : 'Ожидает оплаты'}</span>
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
                            <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #888;">
                                Доставка: ${escapeHtml(order.delivery_address)}<br>
                                Дата доставки: ${order.delivery_date}
                            </div>
                        </div>
                    `).join('');
                });
        }

        function editProfile() {
            document.getElementById('profileFullNameInput').value = document.getElementById('profileFullName').textContent;
            document.getElementById('profileEmailInput').value = document.getElementById('profileEmail').textContent;
            document.getElementById('profilePhoneInput').value = document.getElementById('profilePhone').textContent;
            document.getElementById('profileFormModal').style.display = 'block';
        }

        function goToHome() {
            currentPage = 'home';
            document.getElementById('homePage').classList.remove('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');

            loadPromoCodesForFrontend();
            loadHomeReviews();
            loadNews();
            loadVlog();
        }

        function loadHomeReviews() {
            fetch('/api/home-reviews')
                .then(res => res.json())
                .then(reviews => {
                    const container = document.getElementById('homeReviewsGrid');
                    if (reviews.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Пока нет отзывов. Будьте первым!</div>';
                        return;
                    }

                    container.innerHTML = reviews.map(review => `
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
                });
        }

        function goToCatalog() {
            currentPage = 'catalog';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.remove('hidden');
            document.getElementById('reviewsPage').classList.add('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');

            loadCatalog();
        }

        function goToReviews() {
            currentPage = 'reviews';
            document.getElementById('homePage').classList.add('hidden');
            document.getElementById('catalogPage').classList.add('hidden');
            document.getElementById('reviewsPage').classList.remove('hidden');
            document.getElementById('contactsPage').classList.add('hidden');
            document.getElementById('checkoutPage').classList.add('hidden');
            document.getElementById('profilePage').classList.add('hidden');
            document.getElementById('adminPage').classList.add('hidden');
            document.getElementById('infoPage').classList.add('hidden');

            loadReviews();
        }

        function loadReviews() {
            fetch('/api/reviews')
                .then(res => res.json())
                .then(reviews => {
                    const container = document.getElementById('reviewsList');
                    if (reviews.length === 0) {
                        container.innerHTML = '<div class="empty-reviews">Пока нет отзывов. Будьте первым!</div>';
                        return;
                    }

                    container.innerHTML = reviews.map((review, idx) => `
                        <div class="review-item">
                            <div class="review-header">
                                <span class="review-author">${escapeHtml(review.name)}</span>
                                <span class="review-date">${review.date}</span>
                                ${isAdmin ? `
                                    <div class="review-actions">
                                        <button class="delete-review" onclick="deleteReviewFromPage(${idx})">🗑️</button>
                                    </div>
                                ` : ''}
                            </div>
                            <div class="review-stars">
                                ${Array(5).fill().map((_, i) => `<span class="star-static ${i < review.rating ? 'active' : ''}">★</span>`).join('')}
                            </div>
                            <div class="review-text">${escapeHtml(review.text)}</div>
                        </div>
                    `).join('');
                });
        }

        function deleteReviewFromPage(index) {
            if (confirm('Удалить отзыв?')) {
                fetch('/api/admin/delete-review', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: index})
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        alert('Отзыв удалён');
                        loadReviews();
                        loadHomeReviews();
                        if (isAdmin && currentPage === 'admin') {
                            loadAdminReviews();
                        }
                    } else {
                        alert(data.message);
                    }
                });
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function submitReview() {
            if (!isLoggedIn) {
                alert('Пожалуйста, войдите в аккаунт, чтобы оставить отзыв');
                showAuthModal();
                return;
            }

            const name = document.getElementById('reviewName').value.trim();
            const text = document.getElementById('reviewText').value.trim();

            if (!name) {
                alert('Введите ваше имя');
                return;
            }
            if (selectedRating === 0) {
                alert('Поставьте оценку');
                return;
            }
            if (!text) {
                alert('Введите текст отзыва');
                return;
            }

            fetch('/api/add-review', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: name,
                    rating: selectedRating,
                    text: text
                })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert('Спасибо за отзыв!');
                    document.getElementById('reviewName').value = '';
                    document.getElementById('reviewText').value = '';
                    document.querySelectorAll('#starRating .star').forEach(s => s.classList.remove('active'));
                    selectedRating = 0;
                    loadReviews();
                    loadHomeReviews();
                } else {
                    alert('Ошибка при сохранении отзыва');
                }
            });
        }

        function goToCheckout() {
            if (!isLoggedIn) {
                alert('Пожалуйста, войдите в аккаунт для оформления заказа');
                showAuthModal();
                return;
            }

            fetch('/api/cart').then(res => res.json()).then(data => {
                if (data.items.length === 0) {
                    alert('Корзина пуста');
                    return;
                }
                currentCartData = data;
                document.getElementById('checkoutSubtotal').textContent = data.subtotal.toLocaleString();
                document.getElementById('checkoutDiscount').textContent = data.discount.toLocaleString();
                document.getElementById('checkoutTotal').textContent = data.total.toLocaleString();

                document.getElementById('orderSummaryItems').innerHTML = data.items.map(item => `
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
                document.getElementById('homePage').classList.add('hidden');
                document.getElementById('catalogPage').classList.add('hidden');
                document.getElementById('reviewsPage').classList.add('hidden');
                document.getElementById('contactsPage').classList.add('hidden');
                document.getElementById('profilePage').classList.add('hidden');
                document.getElementById('adminPage').classList.add('hidden');
                document.getElementById('infoPage').classList.add('hidden');
                document.getElementById('checkoutPage').classList.remove('hidden');
                toggleCart();
            });
        }

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
                    deliveryTimeout = setTimeout(() => {
                        fetch('/api/calculate-delivery', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({address: address})
                        }).then(res => res.json()).then(data => {
                            document.getElementById('distanceInfo').innerHTML = `
                                📍 Расстояние: ${data.distance} км<br>
                                🚚 Срок доставки: ${data.delivery_period}<br>
                                📅 Ожидаемая дата: ${data.delivery_date}
                            `;
                        });
                    }, 500);
                }
            });
        }

        function loadCatalog(searchTerm = '') {
            currentSearchTerm = searchTerm;
            let url = `/api/products?search=${encodeURIComponent(searchTerm)}`;
            if (currentCategory && currentCategory !== 'all') {
                url += `&category=${encodeURIComponent(currentCategory)}`;
            }

            fetch(url)
                .then(res => res.json())
                .then(products => {
                    const catalogGrid = document.getElementById('catalogGrid');
                    if (!catalogGrid) return;

                    if (products.length === 0) {
                        catalogGrid.innerHTML = '<div class="empty-reviews" style="grid-column:1/-1; text-align:center;">Ничего не найдено</div>';
                        return;
                    }

                    catalogGrid.innerHTML = products.map((p, idx) => {
                        const hasDiscount = p.sale_price && p.sale_price > 0 && p.sale_price < p.price;
                        const displayPrice = hasDiscount ? p.sale_price : p.price;
                        const discountPercent = p.discount_percent || Math.round((1 - p.sale_price / p.price) * 100);

                        return `
                            <div class="product-card ${hasDiscount ? 'super-sale' : ''}" style="animation-delay: ${idx * 0.05}s" onclick="showProductModal(${p.id})">
                                ${hasDiscount ? `<div class="discount-badge">-${discountPercent}%</div>` : ''}
                                <img src="${p.image}" class="product-image" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'">
                                <div class="product-info">
                                    <div class="product-title">${escapeHtml(p.name)}</div>
                                    <div class="product-price ${hasDiscount ? 'super-price' : ''}">
                                        ${hasDiscount ? `<span class="sale-price">${displayPrice.toLocaleString()} ₽</span> <span class="old-price">${p.price.toLocaleString()} ₽</span>` : `${displayPrice.toLocaleString()} ₽`}
                                    </div>
                                    <button class="add-to-cart" onclick="event.stopPropagation(); addToCartWithAnimation(${p.id}, this)">В корзину</button>
                                </div>
                            </div>
                        `;
                    }).join('');
                });
        }

        function copyPromoCode(code) {
            navigator.clipboard.writeText(code);
            alert('Промокод скопирован');
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

        function showProductModal(id) {
            fetch(`/api/product/${id}`).then(res => res.json()).then(p => {
                currentProduct = p;
                const hasDiscount = p.sale_price && p.sale_price > 0 && p.sale_price < p.price;
                const displayPrice = hasDiscount ? p.sale_price : p.price;

                document.getElementById('modalTitle').textContent = p.name;
                document.getElementById('modalImage').src = p.image;
                document.getElementById('modalImage').onerror = function() { this.src = 'https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'; };
                document.getElementById('modalPrice').innerHTML = hasDiscount ? 
                    `<span style="color:#e74c3c; font-size:1.5rem;">${displayPrice.toLocaleString()} ₽</span> <span style="text-decoration:line-through; color:#666;">${p.price.toLocaleString()} ₽</span> <span style="color:#27ae60;">(-${p.discount_percent || Math.round((1 - p.sale_price / p.price) * 100)}%)</span>` : 
                    `${displayPrice.toLocaleString()} ₽`;
                document.getElementById('modalDescription').innerHTML = p.description + (hasDiscount ? `<br><br><span style="color:#27ae60;">🔥 Скидка ${p.discount_percent || Math.round((1 - p.sale_price / p.price) * 100)}%!</span>` : '');
                document.getElementById('productModal').style.display = 'block';
            });
        }

        function closeModal() {
            document.getElementById('productModal').style.display = 'none';
        }

        async function addToCart(id) {
            await fetch('/api/add-to-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: id})
            });
            updateCartDisplay();
        }

        async function addToCartWithAnimation(id, button) {
            animateToCart(button);
            await addToCart(id);
        }

        function addToCartFromModal() {
            if (currentProduct) {
                const modalButton = document.querySelector('#productModal .add-to-cart');
                animateToCart(modalButton);
                addToCart(currentProduct.id);
            }
            closeModal();
        }

        function applyPromoCode() {
            const code = document.getElementById('promoCodeInput').value.trim().toUpperCase();

            if (!isLoggedIn) {
                alert('Войдите в аккаунт, чтобы использовать промокод');
                showAuthModal();
                return;
            }

            fetch('/api/apply-promo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({promo_code: code})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    alert(`Скидка ${data.discount_text} применена!`);
                    updateCartDisplay();
                } else {
                    alert(data.message);
                }
            });
        }

        function updateCartDisplay() {
            fetch('/api/cart').then(res => res.json()).then(data => {
                document.getElementById('cartCount').textContent = data.items.reduce((s,i) => s + i.quantity, 0);
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
                                    style="width: 36px; height: 36px; background: #2a2a2a; border: none; color: white; font-size: 1.3rem; font-weight: bold; cursor: pointer; border-radius: 6px;">−</button>
                                <span style="min-width: 35px; text-align: center; font-size: 1rem;">${item.quantity}</span>
                                <button onclick="updateQuantity(${item.id}, ${item.quantity + 1})" 
                                    style="width: 36px; height: 36px; background: #2a2a2a; border: none; color: white; font-size: 1.3rem; font-weight: bold; cursor: pointer; border-radius: 6px;">+</button>
                                <button onclick="removeFromCart(${item.id})" 
                                    style="width: 36px; height: 36px; background: #e74c3c; border: none; color: white; font-size: 1.1rem; cursor: pointer; border-radius: 6px; margin-left: 5px;">✕</button>
                            </div>
                        </div>
                    `).join('');
                }
                document.getElementById('cartSubtotal').textContent = data.subtotal.toLocaleString();
                const discountEl = document.getElementById('cartDiscount');
                if (discountEl) discountEl.textContent = `Скидка: ${data.discount.toLocaleString()} ₽`;
                document.getElementById('cartTotal').textContent = data.total.toLocaleString();
            });
        }

        function updateQuantity(id, qty) {
            if (qty <= 0) {
                removeFromCart(id);
            } else {
                fetch('/api/update-cart', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({product_id: id, quantity: qty})
                }).then(() => updateCartDisplay());
            }
        }

        function removeFromCart(id) {
            fetch('/api/remove-from-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: id})
            }).then(() => updateCartDisplay());
        }

        function toggleCart() {
            const panel = document.getElementById('cartPanel');
            const overlay = document.getElementById('overlay');
            panel.classList.toggle('open');
            overlay.style.display = panel.classList.contains('open') ? 'block' : 'none';
            if (panel.classList.contains('open')) updateCartDisplay();
        }

        const checkoutForm = document.getElementById('checkoutForm');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', function(e) {
                e.preventDefault();

                const fullName = document.getElementById('fullName').value;
                const email = document.getElementById('email').value;
                const phone = document.getElementById('phone').value;
                const address = document.getElementById('deliveryAddress').value;

                if (!fullName || !email || !phone || !address) {
                    alert('Заполните все обязательные поля');
                    return;
                }

                if (!selectedPayment) {
                    alert('Выберите способ оплаты');
                    return;
                }

                if (selectedPayment === 'card') {
                    const cardNumber = document.getElementById('cardNumber').value;
                    const cardExpiry = document.getElementById('cardExpiry').value;
                    const cardCvv = document.getElementById('cardCvv').value;
                    const cardName = document.getElementById('cardName').value;

                    if (!cardNumber || !cardExpiry || !cardCvv || !cardName) {
                        alert('Заполните все данные карты');
                        return;
                    }

                    if (cardNumber.replace(/\s/g, '').length < 16) {
                        alert('Введите корректный номер карты');
                        return;
                    }

                    if (cardCvv.length < 3) {
                        alert('Введите корректный CVV код');
                        return;
                    }

                    processOrder('card', {
                        fullName, email, phone, address,
                        cardNumber: cardNumber.substring(12)
                    });
                } else {
                    processOrder('cash', {
                        fullName, email, phone, address
                    });
                }
            });
        }

        function processOrder(method, data) {
            const btn = document.querySelector('.submit-btn');
            if (btn) {
                btn.textContent = 'Обработка...';
                btn.disabled = true;
            }

            fetch(`/api/checkout-${method}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    full_name: data.fullName,
                    email: data.email,
                    phone: data.phone,
                    delivery_address: data.address,
                    card_number: data.cardNumber || '****'
                })
            }).then(res => res.json()).then(result => {
                alert(result.message);
                if (result.success !== false) {
                    goToHome();
                    updateCartDisplay();
                    if (document.getElementById('fullName')) document.getElementById('fullName').value = '';
                    if (document.getElementById('email')) document.getElementById('email').value = '';
                    if (document.getElementById('phone')) document.getElementById('phone').value = '';
                    if (document.getElementById('deliveryAddress')) document.getElementById('deliveryAddress').value = '';
                    selectedPayment = null;
                    const cardOption = document.getElementById('cardOption');
                    const cashOption = document.getElementById('cashOption');
                    const cardFields = document.getElementById('cardFields');
                    if (cardOption) cardOption.classList.remove('selected');
                    if (cashOption) cashOption.classList.remove('selected');
                    if (cardFields) cardFields.classList.add('hidden');
                }
                if (btn) {
                    btn.textContent = 'Оформить заказ';
                    btn.disabled = false;
                }
            });
        }

        const cardNumberInput = document.getElementById('cardNumber');
        if (cardNumberInput) {
            cardNumberInput.addEventListener('input', function(e) {
                let value = e.target.value.replace(/\D/g, '');
                if (value.length > 16) value = value.slice(0, 16);
                value = value.replace(/(\d{4})/g, '$1 ').trim();
                e.target.value = value;
            });
        }

        const cardExpiryInput = document.getElementById('cardExpiry');
        if (cardExpiryInput) {
            cardExpiryInput.addEventListener('input', function(e) {
                let value = e.target.value.replace(/\D/g, '');
                if (value.length > 4) value = value.slice(0, 4);
                if (value.length > 2) value = value.slice(0,2) + '/' + value.slice(2);
                e.target.value = value;
            });
        }

        const cardCvvInput = document.getElementById('cardCvv');
        if (cardCvvInput) {
            cardCvvInput.addEventListener('input', function(e) {
                e.target.value = e.target.value.replace(/\D/g, '').slice(0, 3);
            });
        }

        document.getElementById('searchInput').value = '';

        goToHome();
    </script>
</body>
</html>{% endraw %}'''



@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print("=" * 60)
    print("ЗАПУСК СЕРВЕРА ZETTA")
    print("=" * 60)
    print(f"Сервер запущен на http://{host}:{port}")
    print("-" * 60)
    print("АДМИН АККАУНТ ДЛЯ ВХОДА:")
    print("  Email: admin@zetta.ru")
    print("  Пароль: admin123")
    print("-" * 60)
    print("База данных PostgreSQL подключена")
    print("Все таблицы созданы автоматически")
    print("=" * 60)
    app.run(host=host, port=port, debug=False)
