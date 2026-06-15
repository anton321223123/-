from flask import Flask

app = Flask(__name__)

print("=" * 60)
print("✅ МИНИМАЛЬНОЕ ПРИЛОЖЕНИЕ ZETTA ЗАПУЩЕНО")
print("=" * 60)

@app.route('/')
def index():
    return "Zetta работает! 🚀"

@app.route('/api/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
