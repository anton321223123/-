from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import random
import os
import hashlib
import shutil
from werkzeug.utils import secure_filename
from functools import wraps
import logging

app = Flask(__name__)
app.secret_key = 'secret_key_for_zetta_12345'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание необходимых директорий
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

REVIEWS_FILE = 'reviews.json'
USERS_FILE = 'users.json'
ORDERS_FILE = 'orders.json'
VERIFICATION_CODES_FILE = 'verification_codes.json'
PASSWORD_RESET_FILE = 'password_reset.json'
USED_PROMOCODES_FILE = 'used_promocodes.json'
PRODUCTS_FILE = 'products.json'
NEWS_FILE = 'news.json'
PROMOCODES_FILE = 'promocodes_list.json'
BANNED_USERS_FILE = 'banned_users.json'
CHAT_MESSAGES_FILE = 'chat_messages.json'
VLOG_FILE = 'vlog.json'


def load_reviews():
    if os.path.exists(REVIEWS_FILE):
        with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_reviews(reviews):
    with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_orders(orders):
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def load_verification_codes():
    if os.path.exists(VERIFICATION_CODES_FILE):
        with open(VERIFICATION_CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_verification_codes(codes):
    with open(VERIFICATION_CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def load_password_reset_codes():
    if os.path.exists(PASSWORD_RESET_FILE):
        with open(PASSWORD_RESET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_password_reset_codes(codes):
    with open(PASSWORD_RESET_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def load_used_promocodes():
    if os.path.exists(USED_PROMOCODES_FILE):
        with open(USED_PROMOCODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_used_promocodes(used):
    with open(USED_PROMOCODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(used, f, ensure_ascii=False, indent=2)


def load_banned_users():
    if os.path.exists(BANNED_USERS_FILE):
        with open(BANNED_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_banned_users(banned):
    with open(BANNED_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(banned, f, ensure_ascii=False, indent=2)


def load_chat_messages():
    if os.path.exists(CHAT_MESSAGES_FILE):
        with open(CHAT_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_chat_messages(messages):
    with open(CHAT_MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def load_vlog():
    if os.path.exists(VLOG_FILE):
        with open(VLOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'text': 'Добро пожаловать в блог компании Zetta! Здесь мы будем делиться новостями о нашей работе, рассказывать о сотрудниках и анонсировать новые услуги.\n\n---\n\n✨ Если у вас есть предложения по улучшению или жалобы, нажимайте на кнопку "Предложения" внизу страницы!'}


def save_vlog(vlog):
    with open(VLOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(vlog, f, ensure_ascii=False, indent=2)


def is_user_banned(email):
    banned_users = load_banned_users()
    email_lower = email.lower()
    if email_lower in banned_users:
        ban_until = banned_users[email_lower].get('ban_until')
        reason = banned_users[email_lower].get('reason', 'Нарушение правил')
        message = banned_users[email_lower].get('message', 'Обратитесь к администратору')
        if ban_until:
            ban_until_time = datetime.fromisoformat(ban_until)
            if datetime.now() < ban_until_time:
                return True, ban_until_time.strftime('%d.%m.%Y %H:%M:%S'), reason, message
            else:
                del banned_users[email_lower]
                save_banned_users(banned_users)
    return False, None, None, None


def get_ban_info(email):
    banned_users = load_banned_users()
    email_lower = email.lower()
    if email_lower in banned_users:
        ban_until = banned_users[email_lower].get('ban_until')
        reason = banned_users[email_lower].get('reason', 'Нарушение правил')
        message = banned_users[email_lower].get('message', 'Обратитесь к администратору')
        if ban_until:
            ban_until_time = datetime.fromisoformat(ban_until)
            if datetime.now() < ban_until_time:
                return {
                    'ban_until': ban_until_time.strftime('%d.%m.%Y %H:%M:%S'),
                    'reason': reason,
                    'message': message
                }
    return None


def get_user_unread_count(email):
    chats = load_chat_messages()
    email_lower = email.lower()
    if email_lower in chats:
        unread = 0
        for msg in chats[email_lower]:
            if not msg.get('read', False) and msg.get('type') == 'admin':
                unread += 1
        return unread
    return 0


def mark_chat_read(email):
    chats = load_chat_messages()
    email_lower = email.lower()
    if email_lower in chats:
        for msg in chats[email_lower]:
            if msg.get('type') == 'admin':
                msg['read'] = True
        save_chat_messages(chats)


def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    default_products = [
        {'id': 1, 'name': '💻 Сборка ПК "Игровой Флагман"', 'price': 89990, 'sale_price': 79990, 'discount_percent': 11,
         'description': 'Сборка игрового компьютера с установкой Windows и драйверов. Intel i7, RTX 4060, 32GB RAM, 1TB SSD.',
         'image': '/static/uploads/gaming_pc.jpg', 'category': 'pc_build'},
        {'id': 2, 'name': '🔧 Услуга: Настройка ПК + Антивирус', 'price': 2990, 'sale_price': 1990,
         'discount_percent': 33,
         'description': 'Профессиональная настройка операционной системы, установка антивируса, оптимизация реестра, удаление мусора.',
         'image': '/static/uploads/pc_setup.jpg', 'category': 'services'},
        {'id': 3, 'name': '🌐 Сайт-визитка под ключ', 'price': 14990, 'sale_price': 9990, 'discount_percent': 33,
         'description': 'Создание современного сайта-визитки с адаптивным дизайном, формой обратной связи и базовой SEO-оптимизацией.',
         'image': '/static/uploads/website.jpg', 'category': 'websites'},
        {'id': 4, 'name': '🎮 Компьютер "Стандарт" собранный', 'price': 59990, 'sale_price': None, 'discount_percent': 0,
         'description': 'Готовый системный блок для офиса и дома. Intel i5, 16GB RAM, 512GB SSD, Windows 11 установлена.',
         'image': '/static/uploads/standard_pc.jpg', 'category': 'computers'},
        {'id': 5, 'name': '🛠️ Процессор Intel Core i7-13700K', 'price': 39990, 'sale_price': 34990,
         'discount_percent': 12,
         'description': 'Новый процессор в оригинальной упаковке. Установка и настройка в подарок при покупке сборки ПК.',
         'image': '/static/uploads/cpu.jpg', 'category': 'components'},
        {'id': 6, 'name': '🛠️ Видеокарта RTX 4070 Ti', 'price': 79990, 'sale_price': None, 'discount_percent': 0,
         'description': 'Мощная видеокарта для игр и работы. Гарантия 3 года. Установка при покупке сборки - бесплатно.',
         'image': '/static/uploads/gpu.jpg', 'category': 'components'},
        {'id': 7, 'name': '🔧 Обслуживание ПК на месяц', 'price': 4990, 'sale_price': 3990, 'discount_percent': 20,
         'description': 'Абонемент на обслуживание компьютера: удалённая помощь, диагностика, настройка ПО, установка обновлений.',
         'image': '/static/uploads/service.jpg', 'category': 'services'},
        {'id': 8, 'name': '🌐 Интернет-магазин под ключ', 'price': 49990, 'sale_price': 39990, 'discount_percent': 20,
         'description': 'Полноценный интернет-магазин с корзиной, личным кабинетом, интеграцией с платежными системами.',
         'image': '/static/uploads/ecommerce.jpg', 'category': 'websites'},
    ]
    save_products(default_products)
    return default_products


def save_products(products):
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def load_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    default_news = [
        {
            'id': 1,
            'date': '01.06.2026',
            'title': '🔥 Zetta запускает летнюю распродажу 🔥',
            'text': 'Скидки до 50% на сборку ПК и создание сайтов!',
            'fullText': 'Компания Zetta объявляет о грандиозной летней распродаже! Скидки достигают 50% на сборку игровых компьютеров, создание сайтов и IT-обслуживание. Торопитесь, предложение ограничено!',
            'image': '/static/uploads/sale.jpg'
        },
        {
            'id': 2,
            'date': '28.05.2026',
            'title': 'Новая услуга - Корпоративное обслуживание',
            'text': 'Абонентское обслуживание компьютеров для бизнеса',
            'fullText': 'Zetta запускает услугу корпоративного обслуживания! Полный цикл IT-поддержки для компаний: обслуживание ПК, серверов, настройка сети и техническая поддержка сотрудников.',
            'image': '/static/uploads/business.jpg'
        }
    ]
    save_news(default_news)
    return default_news


def save_news(news):
    with open(NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=2)


def load_promocodes_list():
    if os.path.exists(PROMOCODES_FILE):
        with open(PROMOCODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    default_promocodes = {
        'ZETTA10': {'discount': 10, 'type': 'percent', 'active': True},
        'ZETTA20': {'discount': 20, 'type': 'percent', 'active': True},
        'ZETTA1000': {'discount': 1000, 'type': 'fixed', 'active': True},
        'ZETTA15': {'discount': 15, 'type': 'percent', 'active': True},
    }
    save_promocodes_list(default_promocodes)
    return default_promocodes


def save_promocodes_list(promocodes):
    with open(PROMOCODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(promocodes, f, ensure_ascii=False, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_verification_code():
    return str(random.randint(100000, 999999))


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
        'used_at': datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    }
    save_used_promocodes(used)


# ==================== ФУНКЦИИ ОТПРАВКИ ПОЧТЫ ====================

EMAIL_CONFIG = {
    'smtp_server': 'smtp.mail.ru',
    'smtp_port': 465,
    'email': 'zetta_report@zetta22.ru',
    'password': 'Wertyxa120208'
}

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

        try:
            server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except:
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], 587)
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        
        logger.info(f"Письмо отправлено на {email}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
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

        try:
            server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except:
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], 587)
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки запроса оператору: {e}")
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
            items_html += f'''
            <tr>
                <td>{item["name"]}</td>
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

        try:
            server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except:
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], 587)
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()

        return True
    except Exception as e:
        logger.error(f"Ошибка отправки чека: {e}")
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

        try:
            server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
        except:
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], 587)
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()

        return True
    except Exception as e:
        logger.error(f"Ошибка отправки фидбека: {e}")
        return False


def save_temp_registration(email, data):
    temp_registrations = load_verification_codes()
    temp_registrations[email] = {
        'code': data['code'],
        'expires_at': data['expires_at'],
        'full_name': data['full_name'],
        'phone': data['phone'],
        'password': data['password']
    }
    save_verification_codes(temp_registrations)


def get_temp_registration(email):
    temp_registrations = load_verification_codes()
    return temp_registrations.get(email)


def delete_temp_registration(email):
    temp_registrations = load_verification_codes()
    if email in temp_registrations:
        del temp_registrations[email]
        save_verification_codes(temp_registrations)


def save_password_reset(email, code, expires_at):
    reset_codes = load_password_reset_codes()
    reset_codes[email] = {
        'code': code,
        'expires_at': expires_at
    }
    save_password_reset_codes(reset_codes)


def get_password_reset(email):
    reset_codes = load_password_reset_codes()
    return reset_codes.get(email)


def delete_password_reset(email):
    reset_codes = load_password_reset_codes()
    if email in reset_codes:
        del reset_codes[email]
        save_password_reset_codes(reset_codes)


def register_user(email, password, full_name, phone):
    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        return False, "Пользователь с таким email уже существует"

    users[email_lower] = {
        'email': email_lower,
        'password': hash_password(password),
        'full_name': full_name,
        'phone': phone,
        'registered_at': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'addresses': [],
        'profile_complete': True,
        'is_admin': email_lower == 'admin@zetta.ru'
    }
    save_users(users)
    return True, "Регистрация успешна"


def update_user_profile(email, full_name, phone):
    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        users[email_lower]['full_name'] = full_name
        users[email_lower]['phone'] = phone
        users[email_lower]['profile_complete'] = True
        save_users(users)
        return True
    return False


def is_profile_complete(email):
    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        user = users[email_lower]
        return user.get('profile_complete', False) and user.get('full_name') and user.get('phone')
    return False


def is_admin(email):
    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        return users[email_lower].get('is_admin', False)
    return False


def login_user(email, password):
    users = load_users()
    email_lower = email.lower()

    is_banned, ban_until, ban_reason, ban_message = is_user_banned(email_lower)
    if is_banned:
        return False, f"Ваш аккаунт забанен до {ban_until}. Причина: {ban_reason}. Сообщение от администратора: {ban_message}"

    if email_lower in users and users[email_lower]['password'] == hash_password(password):
        session['user_email'] = email_lower
        session['user_name'] = users[email_lower]['full_name']
        session['is_admin'] = users[email_lower].get('is_admin', False)
        return True, "Вход выполнен"
    return False, "Неверный email или пароль"


def save_order_to_history(user_email, order_data):
    orders = load_orders()
    email_lower = user_email.lower()
    if email_lower not in orders:
        orders[email_lower] = []
    orders[email_lower].append(order_data)
    save_orders(orders)


def get_user_orders(user_email):
    orders = load_orders()
    email_lower = user_email.lower()
    return orders.get(email_lower, [])


def calculate_distance(address):
    address_lower = address.lower()

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
    else:
        distance = random.randint(100, 2000)

    return distance


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


OFFICE_COORDINATES = {
    'lat': 53.3543,
    'lon': 83.7493,
    'address': 'г. Барнаул, ул. Юрина, 182/7'
}


# ==================== СТРАНИЦА БАНА ====================

@app.route('/ban-page')
def ban_page():
    email = request.args.get('email', '')
    ban_info = get_ban_info(email)
    if ban_info:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Аккаунт заблокирован</title>
            <style>
                *{margin:0;padding:0;box-sizing:border-box}
                body{background:linear-gradient(135deg,#0a0a0a 0%,#1a0a0a 100%);display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:'Segoe UI',Arial,sans-serif}
                .ban-container{background:#1a1a1a;border:1px solid #e74c3c;border-radius:16px;padding:2.5rem;max-width:500px;margin:20px;text-align:center;animation:fadeInUp 0.6s ease-out}
                @keyframes fadeInUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
                .ban-icon{font-size:4rem;margin-bottom:1rem}
                .ban-title{font-size:1.8rem;font-weight:bold;color:#e74c3c;margin-bottom:1rem}
                .ban-info{background:#0f0f0f;border-radius:12px;padding:1.5rem;text-align:left;margin-bottom:1.5rem;border-left:4px solid #e74c3c}
                .ban-info p{margin:0.5rem 0;color:#bbb}
                .ban-info strong{color:#27ae60}
                .ban-reason{background:#2a1a1a;padding:0.8rem;border-radius:8px;margin:0.5rem 0;color:#e74c3c}
                .ban-message{background:#1a2a1a;padding:0.8rem;border-radius:8px;margin:0.5rem 0;color:#27ae60}
                .back-btn{background:#27ae60;color:white;border:none;padding:0.8rem 1.5rem;border-radius:8px;cursor:pointer;margin-top:1rem}
                .back-btn:hover{background:#229954}
            </style>
        </head>
        <body>
            <div class="ban-container">
                <div class="ban-icon">🚫</div>
                <div class="ban-title">ДОСТУП ЗАБЛОКИРОВАН</div>
                <div class="ban-info">
                    <p><strong>📅 До:</strong> {{ ban_until }}</p>
                    <p><strong>⚠️ Причина:</strong></p>
                    <div class="ban-reason">{{ reason }}</div>
                    <p><strong>💬 Сообщение:</strong></p>
                    <div class="ban-message">{{ message }}</div>
                </div>
                <button class="back-btn" onclick="window.location.href='/'">🔙 На главную</button>
            </div>
        </body>
        </html>
        ''', ban_until=ban_info['ban_until'], reason=ban_info['reason'], message=ban_info['message'])
    return redirect('/')


@app.before_request
def check_ban():
    if request.endpoint == 'static' or request.endpoint == 'ban_page':
        return None
    if 'user_email' in session:
        is_banned, ban_until, ban_reason, ban_message = is_user_banned(session['user_email'])
        if is_banned:
            session.clear()
            return redirect(f'/ban-page?email={session["user_email"]}')


# ==================== API МАРШРУТЫ ====================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/chat/send-operator-request', methods=['POST'])
def send_operator_request():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    users = load_users()
    user = users.get(session['user_email'], {})
    user_name = user.get('full_name', 'Не указано')
    user_phone = user.get('phone', 'Не указан')
    user_email = session['user_email']

    email_sent = send_operator_request_email(user_name, user_phone, user_email)

    return jsonify({
        'success': True,
        'message': '✅ Заявка отправлена! Оператор свяжется с вами в ближайшее время.',
        'email_sent': email_sent
    })


@app.route('/api/chat/send-payment-question', methods=['POST'])
def send_payment_question():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    auto_response = "Доброго времени суток, наш дорогой клиент! В данный момент оплата принимается только за наличный расчёт или же перевод на карту. Онлайн оплата скоро появится. ЖДИТЕ НАШИХ НОВОСТЕЙ!"

    return jsonify({
        'success': True,
        'response': auto_response
    })


@app.route('/api/chat/site-creation-time', methods=['POST'])
def site_creation_time():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    response = "В среднем создание сайта уходит 1-2 недели, но если сайт не содержит в себе сложных элементов, то создание такого проекта сокращается вдвое!"

    return jsonify({
        'success': True,
        'response': response
    })


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

    return jsonify({
        'success': True,
        'response': response
    })


@app.route('/api/chat/cooperation', methods=['POST'])
def cooperation():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    response = "По вопросам рекламы и сотрудничества пишите нам на почту zetta_report@zetta22.ru или можете позвонить по номеру телефона 89520062357."

    return jsonify({
        'success': True,
        'response': response
    })


@app.route('/api/vlog', methods=['GET'])
def get_vlog():
    vlog = load_vlog()
    return jsonify(vlog)


@app.route('/api/admin/update-vlog', methods=['POST'])
def update_vlog():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    text = data.get('text', '')

    vlog = load_vlog()
    vlog['text'] = text
    save_vlog(vlog)

    return jsonify({'success': True, 'message': 'Влог обновлён'})


@app.route('/api/send-feedback', methods=['POST'])
def send_feedback():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    data = request.json
    message = data.get('message', '')

    if not message:
        return jsonify({'success': False, 'message': 'Введите сообщение'})

    users = load_users()
    user = users.get(session['user_email'], {})
    user_name = user.get('full_name', 'Не указано')
    user_phone = user.get('phone', 'Не указан')
    user_email = session['user_email']

    email_sent = send_feedback_email(user_name, user_email, user_phone, message)

    if email_sent:
        return jsonify({'success': True, 'message': 'Сообщение отправлено! Спасибо за обратную связь.'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка при отправке. Попробуйте позже.'})


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
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
                'registered_at': user.get('registered_at', '')
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

    users = load_users()
    email_lower = email.lower()
    if email_lower not in users:
        return jsonify({'success': False, 'message': 'Пользователь с таким email не найден'})

    code = generate_verification_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()

    save_password_reset(email_lower, code, expires_at)

    if send_verification_email(email_lower, code, 'reset'):
        return jsonify({'success': True, 'message': 'Код восстановления отправлен на почту'})
    else:
        delete_password_reset(email_lower)
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма'})


@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')

    email_lower = email.lower()
    reset_data = get_password_reset(email_lower)
    if not reset_data:
        return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'})

    if datetime.now().timestamp() > reset_data['expires_at']:
        delete_password_reset(email_lower)
        return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'})

    if reset_data['code'] != code:
        return jsonify({'success': False, 'message': 'Неверный код подтверждения'})

    users = load_users()
    if email_lower in users:
        users[email_lower]['password'] = hash_password(new_password)
        save_users(users)
        delete_password_reset(email_lower)
        return jsonify({'success': True, 'message': 'Пароль успешно изменён'})

    return jsonify({'success': False, 'message': 'Пользователь не найден'})


@app.route('/api/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email = data.get('email')
    full_name = data.get('full_name')
    phone = data.get('phone')
    password = data.get('password')

    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        return jsonify({'success': False, 'message': 'Пользователь с таким email уже существует'})

    code = generate_verification_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).timestamp()

    temp_data = {
        'code': code,
        'expires_at': expires_at,
        'full_name': full_name,
        'phone': phone,
        'password': password
    }
    save_temp_registration(email_lower, temp_data)

    if send_verification_email(email_lower, code, 'registration'):
        return jsonify({'success': True, 'message': 'Код подтверждения отправлен на почту'})
    else:
        delete_temp_registration(email_lower)
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма. Попробуйте позже.'})


@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    email = data.get('email')
    code = data.get('code')

    email_lower = email.lower()
    temp_data = get_temp_registration(email_lower)
    if not temp_data:
        return jsonify({'success': False, 'message': 'Код не найден. Запросите новый код.'})

    if datetime.now().timestamp() > temp_data['expires_at']:
        delete_temp_registration(email_lower)
        return jsonify({'success': False, 'message': 'Срок действия кода истёк. Запросите новый.'})

    if temp_data['code'] != code:
        return jsonify({'success': False, 'message': 'Неверный код подтверждения'})

    success, message = register_user(email_lower, temp_data['password'], temp_data['full_name'], temp_data['phone'])

    if success:
        delete_temp_registration(email_lower)
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/api/resend-verification', methods=['POST'])
def resend_verification():
    data = request.json
    email = data.get('email')

    email_lower = email.lower()
    temp_data = get_temp_registration(email_lower)
    if not temp_data:
        return jsonify({'success': False, 'message': 'Данные не найдены. Заполните форму регистрации заново.'})

    new_code = generate_verification_code()
    temp_data['code'] = new_code
    temp_data['expires_at'] = (datetime.now() + timedelta(minutes=5)).timestamp()

    temp_registrations = load_verification_codes()
    temp_registrations[email_lower] = temp_data
    save_verification_codes(temp_registrations)

    if send_verification_email(email_lower, new_code, 'registration'):
        return jsonify({'success': True, 'message': 'Новый код отправлен на почту'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка при отправке письма'})


@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    if 'user_email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    users = load_users()
    user = users.get(session['user_email'], {})
    return jsonify({
        'full_name': user.get('full_name', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', ''),
        'registered_at': user.get('registered_at', '')
    })


@app.route('/api/user/orders', methods=['GET'])
def get_user_orders_api():
    if 'user_email' not in session:
        return jsonify([])

    orders = get_user_orders(session['user_email'])
    return jsonify(orders)


@app.route('/api/home-reviews', methods=['GET'])
def get_home_reviews():
    reviews = load_reviews()
    if len(reviews) == 0:
        return jsonify([])

    today_seed = int(datetime.now().strftime('%Y%m%d'))
    random.seed(today_seed)
    shuffled = reviews.copy()
    random.shuffle(shuffled)
    return jsonify(shuffled[:3])


@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    reviews = load_reviews()
    return jsonify(reviews)


@app.route('/api/add-review', methods=['POST'])
def add_review():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})

    data = request.json
    name = data.get('name', 'Аноним')
    rating = data.get('rating', 5)
    text = data.get('text', '')

    reviews = load_reviews()
    reviews.insert(0, {
        'name': name,
        'rating': rating,
        'text': text,
        'date': datetime.now().strftime('%d.%m.%Y %H:%M')
    })
    save_reviews(reviews)

    return jsonify({'success': True})


@app.route('/api/products')
def get_products():
    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    products = load_products()

    filtered = products
    if search:
        filtered = [p for p in filtered if search in p['name'].lower()]
    if category and category != 'all':
        filtered = [p for p in filtered if p.get('category') == category]

    return jsonify(filtered)


@app.route('/api/product/<int:product_id>')
def get_product(product_id):
    products = load_products()
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
    promocodes = load_promocodes_list()

    if is_promocode_used(user_email, promo_code):
        return jsonify({'success': False, 'message': 'Вы уже использовали этот промокод'})

    if promo_code in promocodes and promocodes[promo_code].get('active', True):
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
    products = load_products()
    promocodes = load_promocodes_list()

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
    if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
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
    products = load_products()
    promocodes = load_promocodes_list()

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
    if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
        promo = promocodes[promo_code]
        if promo['type'] == 'percent':
            discount = subtotal * promo['discount'] / 100
        else:
            discount = min(promo['discount'], subtotal)

    total = subtotal - discount

    order_number = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

    if promo_code and 'user_email' in session:
        mark_promocode_used(session['user_email'], promo_code, order_number)

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
        save_order_to_history(session['user_email'], order_data)

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

    print(f"\n💰 ОПЛАТА КАРТОЙ ЗАРЕГИСТРИРОВАНА!")
    print(f"📦 Заказ #{order_number}")
    print(f"👤 Клиент: {customer_name}")
    print(f"📧 Email: {customer_email}")
    print(f"💳 Сумма: {total:,} ₽")
    print(f"📱 Счёт получателя: 89520062357 (Сбербанк)")
    print(f"📍 Адрес: {delivery_address}")
    print(f"📏 Расстояние: {distance} км")
    print(f"🚚 Доставка: {period_text} (до {delivery_date})")

    email_sent = send_receipt_email(order_data)

    session.pop('cart', None)
    session.pop('promo_code', None)

    if email_sent:
        return jsonify({
            'message': f'✅ Заказ #{order_number} оплачен картой онлайн! Сумма {total:,} ₽ поступит на номер 89520062357. Чек отправлен на {customer_email}.'})
    else:
        return jsonify({
            'message': f'✅ Заказ #{order_number} оплачен картой онлайн! Сумма {total:,} ₽ поступит на номер 89520062357.'})


@app.route('/api/checkout-cash', methods=['POST'])
def checkout_cash():
    data = request.json
    customer_name = data.get('full_name', '')
    customer_email = data.get('email', '')
    customer_phone = data.get('phone', '')
    delivery_address = data.get('delivery_address', '')

    cart = session.get('cart', {})
    promo_code = session.get('promo_code')
    products = load_products()
    promocodes = load_promocodes_list()

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
    if promo_code and promo_code in promocodes and promocodes[promo_code].get('active', True):
        promo = promocodes[promo_code]
        if promo['type'] == 'percent':
            discount = subtotal * promo['discount'] / 100
        else:
            discount = min(promo['discount'], subtotal)

    total = subtotal - discount

    order_number = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

    if promo_code and 'user_email' in session:
        mark_promocode_used(session['user_email'], promo_code, order_number)

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
        save_order_to_history(session['user_email'], order_data)

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

    print(f"\n💰 ЗАКАЗ НАЛИЧНЫМИ ОФОРМЛЕН!")
    print(f"📦 Заказ #{order_number}")
    print(f"👤 Клиент: {customer_name}")
    print(f"📧 Email: {customer_email}")
    print(f"💵 Сумма к оплате при получении: {total:,} ₽")
    print(f"📍 Адрес доставки: {delivery_address}")
    print(f"📏 Расстояние: {distance} км")
    print(f"🚚 Доставка: {period_text} (до {delivery_date})")

    email_sent = send_receipt_email(order_data)

    session.pop('cart', None)
    session.pop('promo_code', None)

    if email_sent:
        return jsonify({
            'message': f'✅ Заказ #{order_number} оформлен! Оплата {total:,} ₽ наличными при получении. Чек отправлен на {customer_email}.'})
    else:
        return jsonify({'message': f'✅ Заказ #{order_number} оформлен! Оплата {total:,} ₽ наличными при получении.'})


# ==================== API ДЛЯ АДМИН-ПАНЕЛИ ====================

@app.route('/api/admin/products', methods=['GET'])
def admin_get_products():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    products = load_products()
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

    products = load_products()
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

    products.append({
        'id': new_id,
        'name': name,
        'price': int(price),
        'sale_price': sale_price_val,
        'discount_percent': discount_percent_val,
        'description': description,
        'image': image_path,
        'category': category
    })
    save_products(products)
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

    products = load_products()
    for p in products:
        if p['id'] == product_id:
            p['name'] = name
            p['price'] = price
            p['sale_price'] = sale_price if sale_price and sale_price > 0 else None
            p['discount_percent'] = discount_percent or 0
            p['description'] = description
            p['category'] = category
            break
    save_products(products)
    return jsonify({'success': True})


@app.route('/api/admin/delete-product', methods=['POST'])
def admin_delete_product():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    product_id = data.get('id')

    products = load_products()
    products = [p for p in products if p['id'] != product_id]
    save_products(products)
    return jsonify({'success': True})


@app.route('/api/admin/news', methods=['GET'])
def admin_get_news():
    news = load_news()
    return jsonify(news)


@app.route('/api/admin/add-news', methods=['POST'])
def admin_add_news():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    title = request.form.get('title')
    text = request.form.get('text')
    fullText = request.form.get('fullText')
    image = request.files.get('image')

    news = load_news()
    new_id = max([n['id'] for n in news]) + 1 if news else 1

    image_path = '/static/uploads/default_news.jpg'
    if image:
        filename = secure_filename(f"news_{new_id}_{image.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)
        image_path = f'/static/uploads/{filename}'

    news.append({
        'id': new_id,
        'date': datetime.now().strftime('%d.%m.%Y'),
        'title': title,
        'text': text,
        'fullText': fullText,
        'image': image_path
    })
    save_news(news)
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

    news = load_news()
    for n in news:
        if n['id'] == news_id:
            n['title'] = title
            n['text'] = text
            n['fullText'] = fullText
            break
    save_news(news)
    return jsonify({'success': True})


@app.route('/api/admin/delete-news', methods=['POST'])
def admin_delete_news():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    news_id = data.get('id')

    news = load_news()
    news = [n for n in news if n['id'] != news_id]
    save_news(news)
    return jsonify({'success': True})


@app.route('/api/admin/promocodes', methods=['GET'])
def admin_get_promocodes():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    promocodes = load_promocodes_list()
    return jsonify(promocodes)


@app.route('/api/promocodes', methods=['GET'])
def get_promocodes():
    promocodes = load_promocodes_list()
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

    promocodes = load_promocodes_list()
    if code in promocodes:
        return jsonify({'success': False, 'message': 'Промокод с таким кодом уже существует'})

    promocodes[code] = {
        'discount': discount,
        'type': type,
        'active': True
    }
    save_promocodes_list(promocodes)
    return jsonify({'success': True})


@app.route('/api/admin/toggle-promocode', methods=['POST'])
def admin_toggle_promocode():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    code = data.get('code', '').upper()

    promocodes = load_promocodes_list()
    if code in promocodes:
        promocodes[code]['active'] = not promocodes[code]['active']
        save_promocodes_list(promocodes)
        status = 'включён' if promocodes[code]['active'] else 'отключён'
        return jsonify({'success': True, 'message': f'Промокод {code} {status}'})
    return jsonify({'success': False, 'message': 'Промокод не найден'})


@app.route('/api/admin/delete-promocode', methods=['POST'])
def admin_delete_promocode():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    code = data.get('code', '').upper()

    promocodes = load_promocodes_list()
    if code in promocodes:
        del promocodes[code]
        save_promocodes_list(promocodes)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Промокод не найден'})


@app.route('/api/admin/delete-review', methods=['POST'])
def admin_delete_review():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    index = data.get('index')

    reviews = load_reviews()
    if 0 <= index < len(reviews):
        reviews.pop(index)
        save_reviews(reviews)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Отзыв не найден'})


@app.route('/api/admin/orders', methods=['GET'])
def admin_get_orders():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    orders = load_orders()
    return jsonify(orders)


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403
    users = load_users()
    return jsonify(users)


@app.route('/api/admin/make-admin', methods=['POST'])
def admin_make_admin():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')

    users = load_users()
    email_lower = email.lower()
    if email_lower in users:
        users[email_lower]['is_admin'] = True
        save_users(users)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Пользователь не найден'})


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

    banned_users = load_banned_users()
    ban_until = datetime.now() + timedelta(minutes=duration_minutes)

    banned_users[email.lower()] = {
        'banned_at': datetime.now().isoformat(),
        'ban_until': ban_until.isoformat(),
        'duration_minutes': duration_minutes,
        'reason': reason,
        'message': message
    }

    save_banned_users(banned_users)

    if 'user_email' in session and session['user_email'].lower() == email.lower():
        session.clear()

    return jsonify(
        {'success': True, 'message': f'Пользователь {email} забанен до {ban_until.strftime("%d.%m.%Y %H:%M:%S")}'})


@app.route('/api/admin/unban-user', methods=['POST'])
def unban_user_route():
    if 'user_email' not in session or not is_admin(session['user_email']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Не указан email'})

    banned_users = load_banned_users()
    if email.lower() in banned_users:
        del banned_users[email.lower()]
        save_banned_users(banned_users)
        return jsonify({'success': True, 'message': f'Бан снят с {email}'})

    return jsonify({'success': False, 'message': 'Пользователь не забанен'})


# ==================== HTML ШАБЛОН (ПОЛНЫЙ) ====================

HTML_TEMPLATE = '''{% raw %}<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

        .animate-fly {
            animation: flyToCart 0.6s ease-in forwards !important;
            position: fixed !important;
            z-index: 9999 !important;
            pointer-events: none !important;
        }

        .cart-icon-animate {
            animation: pulse 0.3s ease-in-out;
        }

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
            animation: pulse 0.5s ease-in-out;
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
    <div class="header">
        <div class="header-content">
            <div class="logo" onclick="goToHome()">
                <span class="logo-icon">⚡</span>
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

            <div class="promo-section">
                <div class="promo-title">Активные промокоды</div>
                <div class="promo-codes" id="promoCodes"></div>
            </div>

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

            <div class="vlog-section">
                <div class="team-title">★ НАШ БЛОГ ★</div>
                <div class="vlog-content">
                    <div class="vlog-text" id="vlogText">Загрузка...</div>
                    <button class="vlog-edit-btn" id="vlogEditBtn" style="display: none;" onclick="openVlogEditor()">✏️ Редактировать влог</button>
                </div>
            </div>

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
                        <div class="contact-value">zetta_report@zetta22.ru</div>
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
                    <p style="margin-bottom: 1rem; line-height: 1.6;">Мы уважаем ваше право на конфиденциальность и обязуемся защищать ваши персональные данные...</p>
                    <p><strong>Контактная информация</strong><br>По всем вопросам: <a href="mailto:zetta_report@zetta22.ru" style="color: #27ae60;">zetta_report@zetta22.ru</a></p>
                </div>
                <div class="admin-form" style="margin-bottom: 0;">
                    <h3 style="color: #27ae60; margin-bottom: 1rem;">❓ Часто задаваемые вопросы</h3>
                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Как заказать сборку ПК?</strong></p>
                        <p style="color: #888;">Выберите категорию "Сборка компьютера" в каталоге или свяжитесь с нашим менеджером.</p>
                    </div>
                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #27ae60; margin-bottom: 0.5rem;"><strong>Какие способы оплаты доступны?</strong></p>
                        <p style="color: #888;">Банковская карта онлайн или наличные при получении.</p>
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
                            <input type="number" id="productSalePrice" placeholder="Цена со скидкой">
                            <input type="number" id="productDiscountPercent" placeholder="Процент скидки">
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
                            <input type="text" id="promocodeCode" placeholder="Код промокода" required>
                            <select id="promocodeType">
                                <option value="percent">Процентная скидка</option>
                                <option value="fixed">Фиксированная скидка</option>
                            </select>
                            <input type="number" id="promocodeDiscount" placeholder="Величина скидки" required>
                            <button type="button" onclick="addPromocode()">Добавить</button>
                        </form>
                    </div>
                    <div class="admin-form">
                        <h3>Список промокодов</h3>
                        <div id="promocodesList"></div>
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
                        <input type="text" class="form-input" id="fullName" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Email *</label>
                        <input type="email" class="form-input" id="email" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Телефон *</label>
                        <input type="tel" class="form-input" id="phone" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Адрес доставки *</label>
                        <input type="text" class="form-input" id="deliveryAddress" required>
                        <div class="delivery-info" id="deliveryInfo" style="margin-top: 0.5rem;">
                            <span id="distanceInfo">Введите адрес для расчёта доставки</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Способ оплаты *</label>
                        <div class="payment-methods">
                            <div class="payment-option" onclick="selectPayment('card')" id="cardOption">💳 Банковская карта</div>
                            <div class="payment-option" onclick="selectPayment('cash')" id="cashOption">💰 Наличные при получении</div>
                        </div>
                    </div>
                    <div id="cardFields" class="card-fields hidden">
                        <div class="form-group"><label>Номер карты</label><input type="text" class="form-input" id="cardNumber" placeholder="0000 0000 0000 0000"></div>
                        <div style="display: flex; gap: 1rem;">
                            <div class="form-group" style="flex:1;"><label>ММ/ГГ</label><input type="text" class="form-input" id="cardExpiry" placeholder="12/25"></div>
                            <div class="form-group" style="flex:1;"><label>CVV</label><input type="password" class="form-input" id="cardCvv" placeholder="123"></div>
                        </div>
                        <div class="form-group"><label>Имя держателя</label><input type="text" class="form-input" id="cardName" placeholder="IVAN IVANOV"></div>
                    </div>
                    <button type="submit" class="submit-btn">Оформить заказ</button>
                </form>
            </div>
        </div>
    </div>

    <footer class="footer">
        <div class="footer-content">
            <div class="footer-section">
                <a href="tel:+79520062357">📞 +7 (952) 006-23-57</a>
                <a href="tel:+79132447707">📞 +7 (913) 244-77-07</a>
                <a href="mailto:zetta_report@zetta22.ru">✉️ zetta_report@zetta22.ru</a>
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

    <button class="chat-button" id="chatButton" onclick="toggleChat()">💬</button>

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

    <div id="feedbackModal" class="feedback-modal">
        <div class="feedback-container">
            <h3>📝 Предложения и жалобы</h3>
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
            <div class="news-modal-header"><h2 id="newsModalTitle"></h2><span class="close-news-modal" onclick="closeNewsModal()">×</span></div>
            <div class="news-modal-body">
                <img id="newsModalImage" class="news-modal-image" src="" alt="">
                <div class="news-modal-date" id="newsModalDate"></div>
                <div class="news-modal-fulltext" id="newsModalFullText"></div>
            </div>
        </div>
    </div>

    <div id="addNewsModal" class="news-modal">
        <div class="news-modal-content">
            <div class="news-modal-header"><h2>Добавить новость</h2><span class="close-news-modal" onclick="closeAddNewsModal()">×</span></div>
            <div class="news-modal-body">
                <input type="text" id="modalNewsTitle" class="form-input" placeholder="Заголовок" style="margin-bottom: 1rem;">
                <input type="text" id="modalNewsShortText" class="form-input" placeholder="Краткий текст" style="margin-bottom: 1rem;">
                <textarea id="modalNewsFullText" class="form-input" rows="5" placeholder="Полный текст" style="margin-bottom: 1rem;"></textarea>
                <input type="file" id="modalNewsImage" accept="image/*" style="margin-bottom: 1rem;">
                <button type="button" class="auth-btn" onclick="submitAddNews()" style="width:100%">Добавить</button>
            </div>
        </div>
    </div>

    <div id="verifyModal" class="verify-modal">
        <div class="verify-container">
            <h3>Подтверждение регистрации</h3>
            <p>На вашу почту отправлен код подтверждения</p>
            <p id="verifyEmailDisplay" style="color:#27ae60"></p>
            <input type="text" id="verifyCode" class="verify-code-input" placeholder="000000" maxlength="6">
            <div id="verifyTimer" class="verify-timer">Код действителен: 5:00</div>
            <button class="auth-btn" onclick="verifyCode()" style="width:100%">Подтвердить</button>
            <button class="resend-code-btn" onclick="resendCode()" style="width:100%; margin-top:0.5rem">Отправить код повторно</button>
        </div>
    </div>

    <div id="resetModal" class="reset-modal">
        <div class="reset-container">
            <span class="close" onclick="closeResetModal()" style="float:right">×</span>
            <h3>Восстановление пароля</h3>
            <div id="resetStep1">
                <input type="email" id="resetEmail" class="auth-input" placeholder="Email" style="width:100%; margin:1rem 0">
                <button class="auth-btn" onclick="sendResetCode()" style="width:100%">Отправить код</button>
            </div>
            <div id="resetStep2" style="display:none">
                <input type="text" id="resetCode" class="verify-code-input" placeholder="000000" style="margin:1rem 0">
                <input type="password" id="newPassword" class="auth-input" placeholder="Новый пароль" style="width:100%; margin:1rem 0">
                <input type="password" id="confirmNewPassword" class="auth-input" placeholder="Подтвердите пароль" style="width:100%; margin:1rem 0">
                <button class="auth-btn" onclick="resetPassword()" style="width:100%">Сбросить пароль</button>
            </div>
        </div>
    </div>

    <div id="profileFormModal" class="profile-form-modal">
        <div class="profile-form-container">
            <h3>Заполните профиль</h3>
            <input type="text" id="profileFullNameInput" class="auth-input" placeholder="ФИО *" style="width:100%; margin-bottom:1rem">
            <input type="email" id="profileEmailInput" class="auth-input" placeholder="Email *" readonly style="width:100%; margin-bottom:1rem">
            <input type="tel" id="profilePhoneInput" class="auth-input" placeholder="Телефон *" style="width:100%; margin-bottom:1rem">
            <button class="auth-btn" onclick="saveProfile()" style="width:100%">Сохранить</button>
        </div>
    </div>

    <div id="productModal" class="modal">
        <div class="modal-content">
            <div class="modal-header"><h2 id="modalTitle"></h2><span class="close" onclick="closeModal()">×</span></div>
            <div class="modal-body" style="padding:1.5rem; display:flex; gap:1.5rem; flex-wrap:wrap;">
                <img id="modalImage" style="width:200px; height:200px; object-fit:cover;">
                <div style="flex:1;"><div class="product-price" id="modalPrice"></div><div id="modalDescription" style="color:#888; margin:1rem 0;"></div><button class="add-to-cart" onclick="addToCartFromModal()">В корзину</button></div>
            </div>
        </div>
    </div>

    <div id="authModal" class="auth-modal">
        <div class="auth-container">
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem"><h3>Вход / Регистрация</h3><span class="close" onclick="closeAuthModal()">×</span></div>
            <div class="auth-tabs"><div class="auth-tab active" onclick="switchAuthTab('login')">Вход</div><div class="auth-tab" onclick="switchAuthTab('register')">Регистрация</div></div>
            <div id="loginForm" class="auth-form"><input type="email" id="loginEmail" class="auth-input" placeholder="Email"><input type="password" id="loginPassword" class="auth-input" placeholder="Пароль"><div class="forgot-password"><a onclick="showForgotPasswordModal()">Забыли пароль?</a></div><button class="auth-btn" onclick="login()">Войти</button></div>
            <div id="registerForm" class="auth-form hidden"><input type="text" id="regFullName" class="auth-input" placeholder="ФИО"><input type="email" id="regEmail" class="auth-input" placeholder="Email"><input type="tel" id="regPhone" class="auth-input" placeholder="Телефон"><input type="password" id="regPassword" class="auth-input" placeholder="Пароль"><input type="password" id="regConfirmPassword" class="auth-input" placeholder="Подтверждение пароля"><button class="auth-btn" onclick="sendVerificationCode()">Зарегистрироваться</button></div>
        </div>
    </div>

    <div class="overlay" id="overlay" onclick="toggleCart()"></div>
    <div class="cart-panel" id="cartPanel">
        <div class="cart-header"><h3>Корзина</h3><span class="close" onclick="toggleCart()">×</span></div>
        <div class="cart-items" id="cartItems"></div>
        <div class="cart-footer">
            <div class="promo-input-group"><input type="text" class="promo-input" id="promoCodeInput" placeholder="Промокод"><button class="apply-promo-btn" onclick="applyPromoCode()">Применить</button></div>
            <div id="promoMessage"></div>
            <div class="cart-total">Сумма: <span id="cartSubtotal">0</span> ₽</div>
            <div class="cart-discount" id="cartDiscount">Скидка: 0 ₽</div>
            <div class="cart-total">Итого: <span id="cartTotal">0</span> ₽</div>
            <button class="checkout-btn" onclick="goToCheckout()">Оформить заказ</button>
        </div>
    </div>

    <script>
        let currentProduct = null;
        let currentPage = 'home';
        let selectedPayment = null;
        let selectedRating = 0;
        let isLoggedIn = false;
        let isAdmin = false;
        let currentUser = null;
        let verifyTimerInterval = null;
        let resetTimerInterval = null;
        let pendingRegistration = null;
        let pendingResetEmail = null;
        let currentSlide = 0;
        let slidesPerView = 3;
        let newsData = [];
        let currentCategory = 'all';
        let currentSearchTerm = '';

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

        function toggleChat() {
            document.getElementById('chatWindow').classList.toggle('open');
            if (document.getElementById('chatWindow').classList.contains('open')) {
                if (window.chatResetTimer) clearTimeout(window.chatResetTimer);
                if (window.consultationButtons) {
                    const btns = document.getElementById('chatButtons');
                    btns.innerHTML = `<button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button><button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button><button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button><button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button><button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>`;
                    window.consultationButtons = false;
                }
            }
        }

        function addThankYouAndReset() {
            const messagesArea = document.getElementById('chatMessagesArea');
            const thankYou = document.createElement('div');
            thankYou.className = 'chat-message system';
            thankYou.innerHTML = 'Спасибо что выбрали нас! с уважением команда ZETTA.';
            messagesArea.appendChild(thankYou);
            messagesArea.scrollTop = messagesArea.scrollHeight;
            if (window.chatResetTimer) clearTimeout(window.chatResetTimer);
            window.chatResetTimer = setTimeout(() => {
                const btns = document.getElementById('chatButtons');
                btns.innerHTML = `<button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button><button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button><button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button><button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button><button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>`;
                window.consultationButtons = false;
                window.chatResetTimer = null;
            }, 5000);
        }

        async function askQuestion(type) {
            const messagesArea = document.getElementById('chatMessagesArea');
            if (!isLoggedIn) { alert('Войдите в аккаунт'); showAuthModal(); return; }
            let responseText = '', showThankYou = false;
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            if (type === 'payment') {
                userMsg.innerHTML = '💳 Проблемы с оплатой?';
                messagesArea.appendChild(userMsg);
                const res = await fetch('/api/chat/send-payment-question', { method: 'POST' });
                const data = await res.json();
                if (data.success) responseText = data.response;
                showThankYou = true;
            } else if (type === 'site_time') {
                userMsg.innerHTML = '⏱️ Срок создания сайта?';
                messagesArea.appendChild(userMsg);
                const res = await fetch('/api/chat/site-creation-time', { method: 'POST' });
                const data = await res.json();
                if (data.success) responseText = data.response;
                showThankYou = true;
            } else if (type === 'consultation') {
                userMsg.innerHTML = '📞 Хочу проконсультироваться!';
                messagesArea.appendChild(userMsg);
                const btns = document.getElementById('chatButtons');
                btns.innerHTML = `<button class="chat-question-btn" onclick="selectConsultant('system_admin')">🖥️ Системный администратор</button><button class="chat-question-btn" onclick="selectConsultant('director')">👔 Генеральный директор</button><button class="chat-question-btn" onclick="selectConsultant('manager')">📋 Менеджер</button><button class="chat-question-btn" onclick="resetConsultation()">🔙 Назад</button>`;
                window.consultationButtons = true;
                messagesArea.scrollTop = messagesArea.scrollHeight;
                return;
            } else if (type === 'cooperation') {
                userMsg.innerHTML = '🤝 Сотрудничество и реклама!';
                messagesArea.appendChild(userMsg);
                const res = await fetch('/api/chat/cooperation', { method: 'POST' });
                const data = await res.json();
                if (data.success) responseText = data.response;
                showThankYou = true;
            } else if (type === 'operator') {
                userMsg.innerHTML = '👨‍💼 Помощь оператора!';
                messagesArea.appendChild(userMsg);
                const res = await fetch('/api/chat/send-operator-request', { method: 'POST' });
                const data = await res.json();
                if (data.success) responseText = data.message;
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
                }, 500);
            }
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }

        async function selectConsultant(choice) {
            const messagesArea = document.getElementById('chatMessagesArea');
            let choiceText = choice === 'system_admin' ? 'Системный администратор' : (choice === 'director' ? 'Генеральный директор' : 'Менеджер');
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-message user';
            userMsg.innerHTML = `📞 Хочу проконсультироваться с ${choiceText}`;
            messagesArea.appendChild(userMsg);
            const res = await fetch('/api/chat/consultation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ choice }) });
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
                const btns = document.getElementById('chatButtons');
                btns.innerHTML = `<button class="chat-question-btn" onclick="askQuestion('payment')">💳 Проблемы с оплатой?</button><button class="chat-question-btn" onclick="askQuestion('site_time')">⏱️ Срок создания сайта?</button><button class="chat-question-btn" onclick="askQuestion('consultation')">📞 Хочу проконсультироваться!</button><button class="chat-question-btn" onclick="askQuestion('cooperation')">🤝 Сотрудничество и реклама!</button><button class="chat-question-btn" onclick="askQuestion('operator')">👨‍💼 Помощь оператора!</button>`;
                window.consultationButtons = false;
            }, 300);
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }

        async function loadVlog() {
            const res = await fetch('/api/vlog');
            const data = await res.json();
            document.getElementById('vlogText').innerHTML = data.text.replace(/\\n/g, '<br>');
        }

        function openVlogEditor() {
            fetch('/api/vlog').then(r => r.json()).then(d => {
                const newText = prompt('Редактировать влог:', d.text);
                if (newText && newText !== d.text) {
                    fetch('/api/admin/update-vlog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: newText }) }).then(() => loadVlog());
                }
            });
        }

        function openFeedbackModal() { document.getElementById('feedbackModal').style.display = 'block'; }
        function closeFeedbackModal() { document.getElementById('feedbackModal').style.display = 'none'; }
        async function sendFeedback() {
            const msg = document.getElementById('feedbackMessage').value;
            if (!msg) { alert('Введите сообщение'); return; }
            const res = await fetch('/api/send-feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) });
            const data = await res.json();
            alert(data.message);
            if (data.success) closeFeedbackModal();
        }

        function filterByCategory(cat) {
            currentCategory = cat;
            document.querySelectorAll('.category-item').forEach(c => c.dataset.category === cat ? c.classList.add('active') : c.classList.remove('active'));
            loadCatalog(currentSearchTerm);
        }

        function showInfoPage() {
            currentPage = 'info';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('infoPage').classList.remove('hidden');
        }
        function showPolicyPage() { showInfoPage(); }
        function showFaqPage() { showInfoPage(); }

        async function loadNews() {
            const res = await fetch('/api/admin/news');
            newsData = await res.json();
            renderCarousel();
        }

        function openNewsModal(idx) {
            const item = newsData[idx];
            if (!item) return;
            document.getElementById('newsModalTitle').innerText = item.title;
            document.getElementById('newsModalImage').src = item.image;
            document.getElementById('newsModalDate').innerText = item.date;
            document.getElementById('newsModalFullText').innerHTML = `<p>${item.fullText}</p>`;
            document.getElementById('newsModal').style.display = 'block';
        }
        function closeNewsModal() { document.getElementById('newsModal').style.display = 'none'; }
        function showAddNewsModal() { document.getElementById('addNewsModal').style.display = 'block'; }
        function closeAddNewsModal() { document.getElementById('addNewsModal').style.display = 'none'; }

        async function submitAddNews() {
            const fd = new FormData();
            fd.append('title', document.getElementById('modalNewsTitle').value);
            fd.append('text', document.getElementById('modalNewsShortText').value);
            fd.append('fullText', document.getElementById('modalNewsFullText').value);
            const file = document.getElementById('modalNewsImage').files[0];
            if (file) fd.append('image', file);
            const res = await fetch('/api/admin/add-news', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) { alert('Новость добавлена'); closeAddNewsModal(); loadNews(); if (currentPage === 'admin') loadAdminNews(); }
            else alert('Ошибка');
        }

        function editNewsFromCarousel(id) {
            const news = newsData.find(n => n.id === id);
            if (!news) return;
            const newTitle = prompt('Новый заголовок:', news.title);
            if (!newTitle) return;
            const newText = prompt('Новый краткий текст:', news.text);
            if (!newText) return;
            const newFull = prompt('Новый полный текст:', news.fullText);
            if (!newFull) return;
            fetch('/api/admin/edit-news', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, title: newTitle, text: newText, fullText: newFull }) }).then(() => { loadNews(); if (currentPage === 'admin') loadAdminNews(); });
        }

        function deleteNewsFromCarousel(id) {
            if (confirm('Удалить новость?')) {
                fetch('/api/admin/delete-news', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }).then(() => { loadNews(); if (currentPage === 'admin') loadAdminNews(); });
            }
        }

        function renderCarousel() {
            const container = document.getElementById('carouselSlides');
            const dots = document.getElementById('carouselDots');
            const total = Math.ceil(newsData.length / slidesPerView);
            if (!newsData.length) { container.innerHTML = '<div class="carousel-slide"><div class="news-card">Новостей нет</div></div>'; dots.innerHTML = ''; return; }
            container.innerHTML = '';
            for (let i = 0; i < total; i++) {
                const slide = document.createElement('div');
                slide.className = 'carousel-slide';
                for (let j = i * slidesPerView; j < Math.min((i + 1) * slidesPerView, newsData.length); j++) {
                    const item = newsData[j];
                    const adminActions = isAdmin ? `<div style="position:absolute; top:0.5rem; right:0.5rem; display:flex; gap:0.3rem;"><button class="edit-btn" style="padding:0.2rem 0.4rem; font-size:0.7rem;" onclick="event.stopPropagation(); editNewsFromCarousel(${item.id})">✏️</button><button class="delete-btn" style="padding:0.2rem 0.4rem; font-size:0.7rem;" onclick="event.stopPropagation(); deleteNewsFromCarousel(${item.id})">🗑️</button></div>` : '';
                    slide.innerHTML += `<div class="news-card" onclick="openNewsModal(${j})" style="position:relative;">${adminActions}<img src="${item.image}" class="news-card-image" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'"><div class="news-card-content"><div class="news-card-date">${item.date}</div><div class="news-card-title">${escapeHtml(item.title)}</div><div class="news-card-text">${escapeHtml(item.text)}</div></div></div>`;
                }
                container.appendChild(slide);
            }
            dots.innerHTML = '';
            for (let i = 0; i < total; i++) {
                const dot = document.createElement('div');
                dot.className = 'dot' + (i === currentSlide ? ' active' : '');
                dot.onclick = () => goToSlide(i);
                dots.appendChild(dot);
            }
            container.style.transform = `translateX(-${currentSlide * 100}%)`;
        }
        function nextSlide() { const total = Math.ceil(newsData.length / slidesPerView); if (currentSlide < total - 1) { currentSlide++; updateCarousel(); } }
        function prevSlide() { if (currentSlide > 0) { currentSlide--; updateCarousel(); } }
        function goToSlide(i) { currentSlide = i; updateCarousel(); }
        function updateCarousel() { document.getElementById('carouselSlides').style.transform = `translateX(-${currentSlide * 100}%)`; document.querySelectorAll('.dot').forEach((d, i) => { if (i === currentSlide) d.classList.add('active'); else d.classList.remove('active'); }); }

        function goToAdminPanel() {
            if (!isAdmin) { alert('Доступ запрещён'); return; }
            currentPage = 'admin';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('adminPage').classList.remove('hidden');
            loadAdminProducts(); loadAdminNews(); loadAdminPromocodes(); loadAdminReviews(); loadAdminOrders(); loadAdminUsers();
        }

        function switchAdminTab(tab) {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
            const tabs = ['products', 'news', 'promocodes', 'reviews', 'orders', 'users'];
            const idx = tabs.indexOf(tab);
            if (idx !== -1) {
                document.querySelectorAll('.admin-tab')[idx].classList.add('active');
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
            const res = await fetch('/api/admin/products');
            const products = await res.json();
            const container = document.getElementById('productsList');
            if (!products.length) { container.innerHTML = '<div>Нет услуг</div>'; return; }
            container.innerHTML = `<div class="admin-products-grid">${products.map(p => `<div class="admin-product-card"><div class="admin-product-info"><div class="admin-product-name">${escapeHtml(p.name)}</div><div class="admin-product-price">${p.sale_price ? p.sale_price.toLocaleString() + ' ₽' : p.price.toLocaleString() + ' ₽'}</div></div><div class="admin-product-actions"><button class="edit-btn" onclick="editProduct(${p.id})">✏️</button><button class="delete-btn" onclick="deleteProduct(${p.id})">🗑️</button></div></div>`).join('')}</div>`;
        }

        async function addProduct() {
            const name = document.getElementById('productName').value;
            const price = document.getElementById('productPrice').value;
            if (!name || !price) { alert('Заполните название и цену'); return; }
            const fd = new FormData();
            fd.append('name', name);
            fd.append('price', price);
            fd.append('sale_price', document.getElementById('productSalePrice').value || '');
            fd.append('discount_percent', document.getElementById('productDiscountPercent').value || '0');
            fd.append('description', document.getElementById('productDescription').value);
            fd.append('category', document.getElementById('productCategory').value);
            const file = document.getElementById('productImage').files[0];
            if (file) fd.append('image', file);
            const res = await fetch('/api/admin/add-product', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) { alert('Услуга добавлена'); loadAdminProducts(); loadCatalog(); }
            else alert('Ошибка');
        }

        async function editProduct(id) {
            const newName = prompt('Новое название:'); if (!newName) return;
            const newPrice = prompt('Новая цена:'); if (!newPrice) return;
            const newSale = prompt('Цена со скидкой (пусто если нет):');
            const newDesc = prompt('Новое описание:');
            const newCat = prompt('Категория (computers/services/pc_build/websites/components):', 'services');
            const res = await fetch('/api/admin/edit-product', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, name: newName, price: parseInt(newPrice), sale_price: newSale ? parseInt(newSale) : null, discount_percent: 0, description: newDesc, category: newCat }) });
            const data = await res.json();
            if (data.success) { alert('Обновлено'); loadAdminProducts(); loadCatalog(); }
            else alert('Ошибка');
        }

        async function deleteProduct(id) {
            if (confirm('Удалить?')) {
                const res = await fetch('/api/admin/delete-product', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
                const data = await res.json();
                if (data.success) { alert('Удалено'); loadAdminProducts(); loadCatalog(); }
            }
        }

        async function addNews() {
            const title = document.getElementById('newsTitle').value;
            const text = document.getElementById('newsShortText').value;
            if (!title || !text) { alert('Заполните заголовок и краткий текст'); return; }
            const fd = new FormData();
            fd.append('title', title);
            fd.append('text', text);
            fd.append('fullText', document.getElementById('newsFullText').value);
            const file = document.getElementById('newsImage').files[0];
            if (file) fd.append('image', file);
            const res = await fetch('/api/admin/add-news', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) { alert('Новость добавлена'); loadAdminNews(); loadNews(); }
        }

        async function loadAdminNews() {
            const res = await fetch('/api/admin/news');
            const news = await res.json();
            const container = document.getElementById('newsList');
            if (!news.length) { container.innerHTML = '<div>Нет новостей</div>'; return; }
            container.innerHTML = `<div class="admin-news-list">${news.map(n => `<div class="admin-news-card"><div class="admin-news-info"><div class="admin-news-title">${escapeHtml(n.title)}</div><div class="admin-news-date">${n.date}</div></div><div class="admin-news-actions"><button class="edit-btn" onclick="editAdminNews(${n.id})">✏️</button><button class="delete-btn" onclick="deleteAdminNews(${n.id})">🗑️</button></div></div>`).join('')}</div>`;
        }

        async function editAdminNews(id) {
            const newTitle = prompt('Новый заголовок:'); if (!newTitle) return;
            const newText = prompt('Новый краткий текст:'); if (!newText) return;
            const newFull = prompt('Новый полный текст:'); if (!newFull) return;
            const res = await fetch('/api/admin/edit-news', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, title: newTitle, text: newText, fullText: newFull }) });
            const data = await res.json();
            if (data.success) { alert('Обновлено'); loadAdminNews(); loadNews(); }
        }

        async function deleteAdminNews(id) {
            if (confirm('Удалить новость?')) {
                const res = await fetch('/api/admin/delete-news', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
                const data = await res.json();
                if (data.success) { alert('Удалено'); loadAdminNews(); loadNews(); }
            }
        }

        async function loadAdminPromocodes() {
            const res = await fetch('/api/admin/promocodes');
            const promocodes = await res.json();
            const container = document.getElementById('promocodesList');
            const entries = Object.entries(promocodes);
            if (!entries.length) { container.innerHTML = '<div>Нет промокодов</div>'; return; }
            container.innerHTML = `<div class="admin-promocodes-list">${entries.map(([code, data]) => `<div class="admin-promocode-card"><div class="admin-promocode-info"><div class="admin-promocode-code">${code}</div><div class="admin-promocode-details">Скидка: ${data.type === 'percent' ? data.discount + '%' : data.discount + ' ₽'}<span class="admin-promocode-status ${data.active ? 'active' : 'inactive'}">${data.active ? 'Активен' : 'Отключен'}</span></div></div><div class="admin-promocode-actions"><button class="toggle-btn" onclick="togglePromocode('${code}')">${data.active ? 'Отключить' : 'Включить'}</button><button class="delete-btn" onclick="deletePromocode('${code}')">🗑️</button></div></div>`).join('')}</div>`;
        }

        async function addPromocode() {
            const code = document.getElementById('promocodeCode').value.trim().toUpperCase();
            const type = document.getElementById('promocodeType').value;
            const discount = parseInt(document.getElementById('promocodeDiscount').value);
            if (!code || !discount) { alert('Заполните все поля'); return; }
            const res = await fetch('/api/admin/add-promocode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code, type, discount }) });
            const data = await res.json();
            if (data.success) { alert('Промокод добавлен'); loadAdminPromocodes(); loadPromoCodes(); }
            else alert(data.message);
        }

        async function togglePromocode(code) {
            const res = await fetch('/api/admin/toggle-promocode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
            const data = await res.json();
            if (data.success) { alert(data.message); loadAdminPromocodes(); loadPromoCodes(); }
        }

        async function deletePromocode(code) {
            if (confirm(`Удалить промокод ${code}?`)) {
                const res = await fetch('/api/admin/delete-promocode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
                const data = await res.json();
                if (data.success) { alert('Удалено'); loadAdminPromocodes(); loadPromoCodes(); }
            }
        }

        async function loadAdminReviews() {
            const res = await fetch('/api/reviews');
            const reviews = await res.json();
            const container = document.getElementById('adminReviewsList');
            if (!reviews.length) { container.innerHTML = '<div>Нет отзывов</div>'; return; }
            container.innerHTML = `<table class="admin-table"><thead><tr><th>Автор</th><th>Оценка</th><th>Текст</th><th>Действия</th></tr></thead><tbody>${reviews.map((r, idx) => `<tr><td>${escapeHtml(r.name)}</td><td>${'★'.repeat(r.rating)}</td><td>${escapeHtml(r.text.substring(0, 50))}...</td><td><button class="delete-btn" onclick="deleteReview(${idx})">🗑️</button></td></tr>`).join('')}</tbody></table>`;
        }

        async function deleteReview(idx) {
            if (confirm('Удалить отзыв?')) {
                const res = await fetch('/api/admin/delete-review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ index: idx }) });
                const data = await res.json();
                if (data.success) { alert('Удалено'); loadAdminReviews(); loadReviews(); loadHomeReviews(); }
            }
        }

        async function loadAdminOrders() {
            const res = await fetch('/api/admin/orders');
            const orders = await res.json();
            const container = document.getElementById('adminOrdersList');
            if (!Object.keys(orders).length) { container.innerHTML = '<div>Нет заказов</div>'; return; }
            let html = '';
            for (const [email, userOrders] of Object.entries(orders)) {
                html += `<h4 style="margin-top:1rem; color:#27ae60;">${escapeHtml(email)}</h4>`;
                userOrders.forEach(o => {
                    html += `<div class="order-card"><div class="order-header"><span class="order-number">Заказ #${o.order_number}</span><span class="order-date">${o.datetime}</span></div><div class="order-items">${o.items.map(i => `<div class="order-item"><span>${escapeHtml(i.name)} x ${i.quantity}</span><span>${i.total.toLocaleString()} ₽</span></div>`).join('')}</div><div class="order-total">Итого: ${o.total.toLocaleString()} ₽</div><div style="font-size:0.8rem; color:#888;">Доставка: ${escapeHtml(o.delivery_address)}</div></div>`;
                });
            }
            container.innerHTML = html;
        }

        async function loadAdminUsers() {
            const res = await fetch('/api/admin/users');
            const users = await res.json();
            const container = document.getElementById('usersList');
            const usersArray = Object.values(users);
            if (!usersArray.length) { container.innerHTML = '<div>Нет пользователей</div>'; return; }
            container.innerHTML = `<div class="admin-users-list">${usersArray.map(u => `<div class="admin-user-card"><div class="admin-user-info"><div class="admin-user-email">${escapeHtml(u.email)}</div><div class="admin-user-details">ФИО: ${escapeHtml(u.full_name || '-')} | Телефон: ${escapeHtml(u.phone || '-')}${u.is_admin ? ' | 👑 Админ' : ''}</div></div><div class="admin-user-actions">${!u.is_admin ? `<button class="edit-btn" onclick="makeAdmin('${u.email}')">Сделать админом</button>` : ''}<button class="ban-btn" onclick="banUser('${u.email}')">🚫 Бан</button><button class="unban-btn" onclick="unbanUser('${u.email}')">Разбанить</button></div></div>`).join('')}</div>`;
        }

        async function makeAdmin(email) {
            if (confirm(`Сделать ${email} администратором?`)) {
                const res = await fetch('/api/admin/make-admin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
                const data = await res.json();
                if (data.success) { alert('Готово'); loadAdminUsers(); if (email === currentUser?.email) checkAuthStatus(); }
            }
        }

        async function banUser(email) {
            const mins = prompt('Срок бана в минутах:', '5');
            if (!mins) return;
            const reason = prompt('Причина бана:', 'Нарушение правил');
            if (!reason) return;
            const message = prompt('Сообщение пользователю:', 'Обратитесь к администратору');
            if (!message) return;
            const res = await fetch('/api/admin/ban-user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, duration_minutes: parseInt(mins), reason, message }) });
            const data = await res.json();
            alert(data.message);
            if (data.success) { loadAdminUsers(); if (email === currentUser?.email) window.location.href = '/'; }
        }

        async function unbanUser(email) {
            if (confirm(`Снять бан с ${email}?`)) {
                const res = await fetch('/api/admin/unban-user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
                const data = await res.json();
                alert(data.message);
                if (data.success) { loadAdminUsers(); if (email === currentUser?.email) checkAuthStatus(); }
            }
        }

        function showForgotPasswordModal() {
            closeAuthModal();
            document.getElementById('resetStep1').style.display = 'block';
            document.getElementById('resetStep2').style.display = 'none';
            document.getElementById('resetModal').style.display = 'block';
        }
        function closeResetModal() { if (resetTimerInterval) clearInterval(resetTimerInterval); document.getElementById('resetModal').style.display = 'none'; pendingResetEmail = null; }

        async function sendResetCode() {
            const email = document.getElementById('resetEmail').value;
            if (!email) { alert('Введите email'); return; }
            const res = await fetch('/api/send-reset-code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
            const data = await res.json();
            if (data.success) { pendingResetEmail = email; document.getElementById('resetStep1').style.display = 'none'; document.getElementById('resetStep2').style.display = 'block'; startResetTimer(300); alert('Код отправлен'); }
            else alert(data.message);
        }

        function startResetTimer(seconds) {
            if (resetTimerInterval) clearInterval(resetTimerInterval);
            let remaining = seconds;
            resetTimerInterval = setInterval(() => { remaining--; if (remaining < 0) clearInterval(resetTimerInterval); }, 1000);
        }

        async function resetPassword() {
            const code = document.getElementById('resetCode').value;
            const newPwd = document.getElementById('newPassword').value;
            const confirm = document.getElementById('confirmNewPassword').value;
            if (!code || code.length !== 6) { alert('Введите код'); return; }
            if (newPwd.length < 6) { alert('Пароль минимум 6 символов'); return; }
            if (newPwd !== confirm) { alert('Пароли не совпадают'); return; }
            const res = await fetch('/api/reset-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: pendingResetEmail, code, new_password: newPwd }) });
            const data = await res.json();
            if (data.success) { if (resetTimerInterval) clearInterval(resetTimerInterval); closeResetModal(); alert('Пароль изменён'); showAuthModal(); }
            else alert(data.message);
        }

        function startTimer(seconds, onTick, onComplete) {
            if (verifyTimerInterval) clearInterval(verifyTimerInterval);
            let remaining = seconds;
            onTick(remaining);
            verifyTimerInterval = setInterval(() => {
                remaining--;
                if (remaining >= 0) onTick(remaining);
                if (remaining < 0) { clearInterval(verifyTimerInterval); if (onComplete) onComplete(); }
            }, 1000);
        }
        function updateTimerDisplay(seconds) {
            const mins = Math.floor(seconds / 60), secs = seconds % 60;
            const timer = document.getElementById('verifyTimer');
            if (timer) {
                if (seconds >= 0) { timer.textContent = `Код действителен: ${mins}:${secs.toString().padStart(2, '0')}`; timer.style.color = seconds < 60 ? '#e74c3c' : '#27ae60'; }
                else timer.textContent = 'Код истёк';
            }
        }

        async function sendVerificationCode() {
            const fullName = document.getElementById('regFullName').value;
            const email = document.getElementById('regEmail').value;
            const phone = document.getElementById('regPhone').value;
            const pwd = document.getElementById('regPassword').value;
            const confirm = document.getElementById('regConfirmPassword').value;
            if (!fullName || !email || !phone || !pwd) { alert('Заполните все поля'); return; }
            if (pwd !== confirm) { alert('Пароли не совпадают'); return; }
            if (pwd.length < 6) { alert('Пароль минимум 6 символов'); return; }
            const res = await fetch('/api/send-verification', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, full_name: fullName, phone, password: pwd }) });
            const data = await res.json();
            if (data.success) {
                pendingRegistration = { email, full_name: fullName, phone, password: pwd };
                document.getElementById('verifyEmailDisplay').innerText = email;
                document.getElementById('verifyModal').style.display = 'block';
                document.getElementById('verifyCode').value = '';
                startTimer(300, (s) => updateTimerDisplay(s), () => { document.getElementById('verifyTimer').innerHTML = 'Код истёк'; });
            } else alert(data.message);
        }

        async function verifyCode() {
            const code = document.getElementById('verifyCode').value;
            if (!code || code.length !== 6) { alert('Введите 6-значный код'); return; }
            const res = await fetch('/api/verify-code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: pendingRegistration.email, code }) });
            const data = await res.json();
            if (data.success) {
                if (verifyTimerInterval) clearInterval(verifyTimerInterval);
                document.getElementById('verifyModal').style.display = 'none';
                alert('Регистрация успешна!');
                switchAuthTab('login');
                document.getElementById('loginEmail').value = pendingRegistration.email;
                pendingRegistration = null;
            } else alert(data.message);
        }

        async function resendCode() {
            if (!pendingRegistration) return;
            const res = await fetch('/api/resend-verification', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: pendingRegistration.email }) });
            const data = await res.json();
            if (data.success) { alert('Новый код отправлен'); startTimer(300, (s) => updateTimerDisplay(s), () => { document.getElementById('verifyTimer').innerHTML = 'Код истёк'; }); }
            else alert(data.message);
        }

        async function checkAndShowProfileForm() {
            const res = await fetch('/api/check-profile-complete');
            const data = await res.json();
            if (!data.complete) {
                document.getElementById('profileFullNameInput').value = currentUser ? currentUser.full_name : '';
                document.getElementById('profileEmailInput').value = currentUser ? currentUser.email : '';
                document.getElementById('profilePhoneInput').value = currentUser ? currentUser.phone : '';
                document.getElementById('profileFormModal').style.display = 'block';
            } else { loadProfile(); loadOrdersHistory(); }
        }

        async function saveProfile() {
            const fullName = document.getElementById('profileFullNameInput').value;
            const phone = document.getElementById('profilePhoneInput').value;
            if (!fullName || !phone) { alert('Заполните все поля'); return; }
            const res = await fetch('/api/update-profile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ full_name: fullName, phone }) });
            const data = await res.json();
            if (data.success) { document.getElementById('profileFormModal').style.display = 'none'; alert('Профиль обновлён'); checkAuthStatus(); loadProfile(); loadOrdersHistory(); }
            else alert('Ошибка');
        }

        window.onclick = function(e) {
            if (e.target === document.getElementById('newsModal')) closeNewsModal();
            if (e.target === document.getElementById('addNewsModal')) closeAddNewsModal();
            if (e.target === document.getElementById('verifyModal')) { if (verifyTimerInterval) clearInterval(verifyTimerInterval); document.getElementById('verifyModal').style.display = 'none'; }
            if (e.target === document.getElementById('resetModal')) closeResetModal();
            if (e.target === document.getElementById('profileFormModal')) document.getElementById('profileFormModal').style.display = 'none';
            if (e.target === document.getElementById('productModal')) closeModal();
            if (e.target === document.getElementById('feedbackModal')) closeFeedbackModal();
        };

        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('#starRating .star').forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.dataset.value);
                    document.querySelectorAll('#starRating .star').forEach(s => parseInt(s.dataset.value) <= selectedRating ? s.classList.add('active') : s.classList.remove('active'));
                });
            });
            checkAuthStatus();
            loadNews();
            loadPromoCodes();
            loadHomeReviews();
            loadVlog();
        });

        async function checkAuthStatus() {
            const res = await fetch('/api/auth/status');
            const data = await res.json();
            if (data.logged_in) {
                isLoggedIn = true;
                isAdmin = data.is_admin === true;
                currentUser = data.user;
                document.getElementById('userNameDisplay').innerText = currentUser.full_name ? currentUser.full_name.split(' ')[0] : currentUser.email;
                document.getElementById('profileLink').style.display = 'block';
                document.getElementById('adminLink').style.display = isAdmin ? 'block' : 'none';
                document.getElementById('vlogEditBtn').style.display = isAdmin ? 'block' : 'none';
                document.getElementById('addNewsBtn').style.display = isAdmin ? 'flex' : 'none';
            } else {
                isLoggedIn = false;
                isAdmin = false;
                currentUser = null;
                document.getElementById('userNameDisplay').innerText = 'Войти';
                document.getElementById('profileLink').style.display = 'none';
                document.getElementById('adminLink').style.display = 'none';
                document.getElementById('vlogEditBtn').style.display = 'none';
                document.getElementById('addNewsBtn').style.display = 'none';
            }
            if (typeof renderCarousel === 'function') renderCarousel();
        }

        function showAuthModal() { if (isLoggedIn) goToProfile(); else document.getElementById('authModal').style.display = 'block'; }
        function closeAuthModal() { document.getElementById('authModal').style.display = 'none'; switchAuthTab('login'); }

        function switchAuthTab(tab) {
            const loginTab = document.querySelectorAll('.auth-tab')[0];
            const regTab = document.querySelectorAll('.auth-tab')[1];
            if (tab === 'login') {
                loginTab.classList.add('active'); regTab.classList.remove('active');
                document.getElementById('loginForm').classList.remove('hidden');
                document.getElementById('registerForm').classList.add('hidden');
            } else {
                loginTab.classList.remove('active'); regTab.classList.add('active');
                document.getElementById('loginForm').classList.add('hidden');
                document.getElementById('registerForm').classList.remove('hidden');
            }
        }

        async function login() {
            const email = document.getElementById('loginEmail').value;
            const pwd = document.getElementById('loginPassword').value;
            if (!email || !pwd) { alert('Заполните поля'); return; }
            const res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: pwd }) });
            const data = await res.json();
            if (data.success) { alert('Вход выполнен'); closeAuthModal(); checkAuthStatus(); goToHome(); }
            else alert(data.message);
        }

        async function logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            checkAuthStatus();
            goToHome();
        }

        function goToProfile() {
            if (!isLoggedIn) { showAuthModal(); return; }
            currentPage = 'profile';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('profilePage').classList.remove('hidden');
            checkAndShowProfileForm();
        }

        function goToContacts() {
            currentPage = 'contacts';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('contactsPage').classList.remove('hidden');
        }

        async function loadProfile() {
            const res = await fetch('/api/user/profile');
            const data = await res.json();
            document.getElementById('profileFullName').innerText = data.full_name;
            document.getElementById('profileEmail').innerText = data.email;
            document.getElementById('profilePhone').innerText = data.phone;
            document.getElementById('profileRegistered').innerText = data.registered_at;
        }

        async function loadOrdersHistory() {
            const res = await fetch('/api/user/orders');
            const orders = await res.json();
            const container = document.getElementById('ordersHistory');
            if (!orders.length) { container.innerHTML = '<div>Нет заказов</div>'; return; }
            container.innerHTML = orders.map(o => `<div class="order-card"><div class="order-header"><span class="order-number">Заказ #${o.order_number}</span><span class="order-date">${o.datetime}</span></div><div class="order-items">${o.items.map(i => `<div class="order-item"><span>${escapeHtml(i.name)} x ${i.quantity}</span><span>${i.total.toLocaleString()} ₽</span></div>`).join('')}</div><div class="order-total">Итого: ${o.total.toLocaleString()} ₽</div><div style="font-size:0.8rem;">Доставка: ${escapeHtml(o.delivery_address)}<br>Дата: ${o.delivery_date}</div></div>`).join('');
        }

        function editProfile() {
            document.getElementById('profileFullNameInput').value = document.getElementById('profileFullName').innerText;
            document.getElementById('profileEmailInput').value = document.getElementById('profileEmail').innerText;
            document.getElementById('profilePhoneInput').value = document.getElementById('profilePhone').innerText;
            document.getElementById('profileFormModal').style.display = 'block';
        }

        function goToHome() {
            currentPage = 'home';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('homePage').classList.remove('hidden');
            loadPromoCodes();
            loadHomeReviews();
            loadNews();
            loadVlog();
        }

        async function loadPromoCodes() {
            const res = await fetch('/api/promocodes');
            const data = await res.json();
            const container = document.getElementById('promoCodes');
            const active = Object.entries(data).filter(([k, v]) => v.active);
            if (!active.length) { container.innerHTML = '<div>Нет активных промокодов</div>'; return; }
            container.innerHTML = active.map(([code, data]) => `<div class="promo-card" onclick="copyPromoCode('${code}')"><div class="promo-code">${code}</div><div class="promo-discount">-${data.type === 'percent' ? data.discount + '%' : data.discount + ' ₽'}</div></div>`).join('');
        }

        function copyPromoCode(code) { navigator.clipboard.writeText(code); alert('Промокод скопирован'); }

        async function loadHomeReviews() {
            const res = await fetch('/api/home-reviews');
            const reviews = await res.json();
            const container = document.getElementById('homeReviewsGrid');
            if (!reviews.length) { container.innerHTML = '<div>Нет отзывов</div>'; return; }
            container.innerHTML = reviews.map(r => `<div class="home-review-card"><div class="home-review-header"><span class="home-review-author">${escapeHtml(r.name)}</span><span class="home-review-date">${r.date}</span></div><div class="home-review-stars">${Array(5).fill().map((_, i) => `<span class="star-static ${i < r.rating ? 'active' : ''}">★</span>`).join('')}</div><div class="home-review-text">${escapeHtml(r.text)}</div></div>`).join('');
        }

        function goToCatalog() {
            currentPage = 'catalog';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('catalogPage').classList.remove('hidden');
            loadCatalog();
        }

        function goToReviews() {
            currentPage = 'reviews';
            document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
            document.getElementById('reviewsPage').classList.remove('hidden');
            loadReviews();
        }

        async function loadReviews() {
            const res = await fetch('/api/reviews');
            const reviews = await res.json();
            const container = document.getElementById('reviewsList');
            if (!reviews.length) { container.innerHTML = '<div>Нет отзывов</div>'; return; }
            container.innerHTML = reviews.map(r => `<div class="review-item"><div class="review-header"><span class="review-author">${escapeHtml(r.name)}</span><span class="review-date">${r.date}</span></div><div class="review-stars">${Array(5).fill().map((_, i) => `<span class="star-static ${i < r.rating ? 'active' : ''}">★</span>`).join('')}</div><div class="review-text">${escapeHtml(r.text)}</div></div>`).join('');
        }

        async function submitReview() {
            if (!isLoggedIn) { alert('Войдите в аккаунт'); showAuthModal(); return; }
            const name = document.getElementById('reviewName').value;
            const text = document.getElementById('reviewText').value;
            if (!name) { alert('Введите имя'); return; }
            if (!selectedRating) { alert('Поставьте оценку'); return; }
            if (!text) { alert('Введите отзыв'); return; }
            const res = await fetch('/api/add-review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, rating: selectedRating, text }) });
            const data = await res.json();
            if (data.success) { alert('Спасибо за отзыв!'); document.getElementById('reviewName').value = ''; document.getElementById('reviewText').value = ''; document.querySelectorAll('#starRating .star').forEach(s => s.classList.remove('active')); selectedRating = 0; loadReviews(); loadHomeReviews(); }
            else alert('Ошибка');
        }

        function escapeHtml(t) { if (!t) return ''; const div = document.createElement('div'); div.textContent = t; return div.innerHTML; }

        function goToCheckout() {
            if (!isLoggedIn) { alert('Войдите в аккаунт'); showAuthModal(); return; }
            fetch('/api/cart').then(r => r.json()).then(data => {
                if (!data.items.length) { alert('Корзина пуста'); return; }
                currentCartData = data;
                document.getElementById('checkoutSubtotal').innerText = data.subtotal.toLocaleString();
                document.getElementById('checkoutDiscount').innerText = data.discount.toLocaleString();
                document.getElementById('checkoutTotal').innerText = data.total.toLocaleString();
                document.getElementById('orderSummaryItems').innerHTML = data.items.map(i => `<div style="display:flex; justify-content:space-between;"><span>${escapeHtml(i.name)} x ${i.quantity}</span><span>${i.total.toLocaleString()} ₽</span></div>`).join('');
                if (currentUser) {
                    document.getElementById('fullName').value = currentUser.full_name || '';
                    document.getElementById('email').value = currentUser.email || '';
                    document.getElementById('phone').value = currentUser.phone || '';
                }
                currentPage = 'checkout';
                document.querySelectorAll('#homePage,#catalogPage,#reviewsPage,#contactsPage,#profilePage,#checkoutPage,#adminPage,#infoPage').forEach(p => p.classList.add('hidden'));
                document.getElementById('checkoutPage').classList.remove('hidden');
                toggleCart();
            });
        }

        function selectPayment(method) {
            selectedPayment = method;
            document.getElementById('cardOption').classList.toggle('selected', method === 'card');
            document.getElementById('cashOption').classList.toggle('selected', method === 'cash');
            document.getElementById('cardFields').classList.toggle('hidden', method !== 'card');
        }

        let deliveryTimeout;
        const deliveryAddress = document.getElementById('deliveryAddress');
        if (deliveryAddress) {
            deliveryAddress.addEventListener('input', function() {
                clearTimeout(deliveryTimeout);
                const address = this.value;
                if (address.length > 10) {
                    deliveryTimeout = setTimeout(() => {
                        fetch('/api/calculate-delivery', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address }) }).then(r => r.json()).then(d => {
                            document.getElementById('distanceInfo').innerHTML = `📍 Расстояние: ${d.distance} км<br>🚚 Срок доставки: ${d.delivery_period}<br>📅 Ожидаемая дата: ${d.delivery_date}`;
                        });
                    }, 500);
                }
            });
        }

        async function loadCatalog(term = '') {
            currentSearchTerm = term;
            let url = `/api/products?search=${encodeURIComponent(term)}`;
            if (currentCategory !== 'all') url += `&category=${encodeURIComponent(currentCategory)}`;
            const res = await fetch(url);
            const products = await res.json();
            const grid = document.getElementById('catalogGrid');
            if (!products.length) { grid.innerHTML = '<div style="text-align:center;">Ничего не найдено</div>'; return; }
            grid.innerHTML = products.map((p, idx) => {
                const hasDiscount = p.sale_price && p.sale_price > 0 && p.sale_price < p.price;
                const price = hasDiscount ? p.sale_price : p.price;
                const percent = p.discount_percent || Math.round((1 - p.sale_price / p.price) * 100);
                return `<div class="product-card ${hasDiscount ? 'super-sale' : ''}" onclick="showProductModal(${p.id})">${hasDiscount ? `<div class="discount-badge">-${percent}%</div>` : ''}<img src="${p.image}" class="product-image" onerror="this.src='https://via.placeholder.com/300x200/2c3e50/ffffff?text=No+Image'"><div class="product-info"><div class="product-title">${escapeHtml(p.name)}</div><div class="product-price">${hasDiscount ? `<span class="sale-price">${price.toLocaleString()} ₽</span> <span class="old-price">${p.price.toLocaleString()} ₽</span>` : `${price.toLocaleString()} ₽`}</div><button class="add-to-cart" onclick="event.stopPropagation(); addToCart(${p.id})">В корзину</button></div></div>`;
            }).join('');
        }

        function searchProducts() {
            const term = document.getElementById('searchInput').value;
            if (currentPage === 'catalog') loadCatalog(term);
            else { goToCatalog(); setTimeout(() => loadCatalog(term), 100); }
        }

        function showProductModal(id) {
            fetch(`/api/product/${id}`).then(r => r.json()).then(p => {
                currentProduct = p;
                const hasDiscount = p.sale_price && p.sale_price > 0 && p.sale_price < p.price;
                const price = hasDiscount ? p.sale_price : p.price;
                document.getElementById('modalTitle').innerText = p.name;
                document.getElementById('modalImage').src = p.image;
                document.getElementById('modalPrice').innerHTML = hasDiscount ? `<span style="color:#e74c3c; font-size:1.5rem;">${price.toLocaleString()} ₽</span> <span style="text-decoration:line-through;">${p.price.toLocaleString()} ₽</span>` : `${price.toLocaleString()} ₽`;
                document.getElementById('modalDescription').innerHTML = p.description;
                document.getElementById('productModal').style.display = 'block';
            });
        }

        function closeModal() { document.getElementById('productModal').style.display = 'none'; }

        async function addToCart(id) {
            await fetch('/api/add-to-cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: id }) });
            updateCartDisplay();
        }

        function addToCartFromModal() { if (currentProduct) addToCart(currentProduct.id); closeModal(); }

        async function applyPromoCode() {
            const code = document.getElementById('promoCodeInput').value.trim().toUpperCase();
            if (!isLoggedIn) { alert('Войдите в аккаунт'); showAuthModal(); return; }
            const res = await fetch('/api/apply-promo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ promo_code: code }) });
            const data = await res.json();
            if (data.success) { alert(`Скидка ${data.discount_text} применена`); updateCartDisplay(); }
            else alert(data.message);
        }

        async function updateCartDisplay() {
            const res = await fetch('/api/cart');
            const data = await res.json();
            document.getElementById('cartCount').innerText = data.items.reduce((s, i) => s + i.quantity, 0);
            const itemsDiv = document.getElementById('cartItems');
            if (!data.items.length) itemsDiv.innerHTML = '<div class="empty-cart">Корзина пуста</div>';
            else {
                itemsDiv.innerHTML = data.items.map(item => `<div class="cart-item"><div><div class="cart-item-title">${escapeHtml(item.name)}</div><div style="color:#888;">${item.price.toLocaleString()} ₽</div></div><div><button onclick="updateQuantity(${item.id}, ${item.quantity - 1})">−</button><span style="min-width:35px;text-align:center;">${item.quantity}</span><button onclick="updateQuantity(${item.id}, ${item.quantity + 1})">+</button><button onclick="removeFromCart(${item.id})">✕</button></div></div>`).join('');
            }
            document.getElementById('cartSubtotal').innerText = data.subtotal.toLocaleString();
            document.getElementById('cartDiscount').innerHTML = `Скидка: ${data.discount.toLocaleString()} ₽`;
            document.getElementById('cartTotal').innerText = data.total.toLocaleString();
        }

        async function updateQuantity(id, qty) {
            if (qty <= 0) removeFromCart(id);
            else await fetch('/api/update-cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: id, quantity: qty }) });
            updateCartDisplay();
        }

        async function removeFromCart(id) {
            await fetch('/api/remove-from-cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: id }) });
            updateCartDisplay();
        }

        function toggleCart() {
            document.getElementById('cartPanel').classList.toggle('open');
            document.getElementById('overlay').style.display = document.getElementById('cartPanel').classList.contains('open') ? 'block' : 'none';
            if (document.getElementById('cartPanel').classList.contains('open')) updateCartDisplay();
        }

        const checkoutForm = document.getElementById('checkoutForm');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const fullName = document.getElementById('fullName').value;
                const email = document.getElementById('email').value;
                const phone = document.getElementById('phone').value;
                const address = document.getElementById('deliveryAddress').value;
                if (!fullName || !email || !phone || !address) { alert('Заполните все поля'); return; }
                if (!selectedPayment) { alert('Выберите способ оплаты'); return; }
                const btn = document.querySelector('.submit-btn');
                btn.innerText = 'Обработка...';
                btn.disabled = true;
                if (selectedPayment === 'card') {
                    const cardNum = document.getElementById('cardNumber').value;
                    const cardExp = document.getElementById('cardExpiry').value;
                    const cardCvv = document.getElementById('cardCvv').value;
                    const cardName = document.getElementById('cardName').value;
                    if (!cardNum || !cardExp || !cardCvv || !cardName) { alert('Заполните данные карты'); btn.innerText = 'Оформить заказ'; btn.disabled = false; return; }
                    const res = await fetch('/api/checkout-card', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ full_name: fullName, email, phone, delivery_address: address, card_number: cardNum.slice(-4) }) });
                    const result = await res.json();
                    alert(result.message);
                    goToHome();
                    updateCartDisplay();
                } else {
                    const res = await fetch('/api/checkout-cash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ full_name: fullName, email, phone, delivery_address: address }) });
                    const result = await res.json();
                    alert(result.message);
                    goToHome();
                    updateCartDisplay();
                }
                btn.innerText = 'Оформить заказ';
                btn.disabled = false;
            });
        }

        document.getElementById('searchInput').value = '';
        goToHome();
    </script>
</body>
</html>{% endraw %}'''

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    users = load_users()
    admin_email = 'admin@zetta.ru'
    admin_exists = any(u.get('is_admin', False) for u in users.values())

    if not admin_exists:
        users[admin_email] = {
            'email': admin_email,
            'password': hash_password('admin123'),
            'full_name': 'Администратор Zetta',
            'phone': '+7 (999) 999-99-99',
            'registered_at': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'addresses': [],
            'profile_complete': True,
            'is_admin': True
        }
        save_users(users)
        print("=" * 50)
        print("АДМИН ZETTA СОЗДАН:")
        print(f"Email: {admin_email}")
        print(f"Пароль: admin123")
        print("=" * 50)
    
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"Запуск сервера на {host}:{port}")
    app.run(host=host, port=port, debug=False)
