# Import các thư viện cần thiết
from flask import Flask, render_template, request
import requests
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter

app = Flask(__name__)

# API key của OpenWeatherMap
API_KEY = "badfd5d2cdddb7db9218e90be8b3081c"

# Tải danh sách thành phố từ file JSON (dùng để lấy tên thành phố từ ID)
with open('static/city.list.json', encoding='utf-8') as f:
    cities_data = json.load(f)

# Tạo dict để tra cứu tên thành phố từ ID
city_dict = {str(city['id']): f"{city['name']}, {city['country']}" for city in cities_data}

# Hàm tạo cơ sở dữ liệu
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weather_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        temperature REAL,
        description TEXT,
        date TEXT,
        favorite INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

# Route xử lý khi người dùng gửi form tra cứu thời tiết
@app.route('/weather', methods=['POST'])
def weather():
    city_id = request.form['city_id']
    if not city_id:
        return "Thiếu mã thành phố", 400

    # Gửi yêu cầu API thời tiết hiện tại
    url = f"https://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={API_KEY}&units=metric&lang=vi"
    res = requests.get(url).json()

    if res.get("cod") != 200:
        return f"Lỗi: {res.get('message')}", 400

    # Trích xuất dữ liệu thời tiết hiện tại
    city = f"{res['name']}, {res['sys']['country']}"
    temp = res['main']['temp']
    desc = res['weather'][0]['description']
    icon = res['weather'][0]['icon']

    # Lưu vào cơ sở dữ liệu
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO weather_history (city, temperature, description, date) VALUES (?, ?, ?, ?)",
              (city, temp, desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    # Gửi yêu cầu API dự báo thời tiết (mỗi 3 giờ)
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?id={city_id}&appid={API_KEY}&units=metric&lang=vi"
    forecast_res = requests.get(forecast_url).json()

    hourly = []
    for item in forecast_res['list'][:8]:
        dt = datetime.strptime(item['dt_txt'], "%Y-%m-%d %H:%M:%S")
        time_label = dt.strftime("%H:%M")
        temp_3h = round(item['main']['temp'], 1)
        hourly.append({'time': time_label, 'temp': temp_3h})

    # Gom dữ liệu theo ngày để tính dự báo ngày
    daily_forecast = {}
    for item in forecast_res['list']:
        date = item['dt_txt'].split(' ')[0]
        temp_f = item['main']['temp']
        desc_f = item['weather'][0]['description']
        icon_f = item['weather'][0]['icon']
        if date not in daily_forecast:
            daily_forecast[date] = {
                'temps': [temp_f],
                'descs': [desc_f],
                'icons': [icon_f]
            }
        else:
            daily_forecast[date]['temps'].append(temp_f)
            daily_forecast[date]['descs'].append(desc_f)
            daily_forecast[date]['icons'].append(icon_f)

    # Dự báo cho 3 ngày tới
    forecast_3_days = []
    today = datetime.now().date()
    for i in range(1, 4):  # Ngày mai đến 2 ngày sau
        day = today + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        if day_str in daily_forecast:
            temps = daily_forecast[day_str]['temps']
            descs = daily_forecast[day_str]['descs']
            icons = daily_forecast[day_str]['icons']
            avg_temp = round(sum(temps) / len(temps), 1)
            most_common_desc = Counter(descs).most_common(1)[0][0]
            icon_common = Counter(icons).most_common(1)[0][0]
            forecast_3_days.append({
                'date': day.strftime('%d/%m'),
                'temp': avg_temp,
                'desc': most_common_desc,
                'icon': icon_common
            })

    # Trả kết quả ra trang result.html
    return render_template('result.html', city=city, temp=temp, desc=desc, icon=icon, forecast=forecast_3_days, hourly=hourly)

# Route xem lịch sử tra cứu
@app.route('/history')
def history():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM weather_history ORDER BY id DESC LIMIT 50")
    records = c.fetchall()
    conn.close()
    return render_template('history.html', history=records)

# Route xem danh sách yêu thích
@app.route('/favorites')
def favorites():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM weather_history WHERE favorite = 1 ORDER BY id DESC")
    records = c.fetchall()
    conn.close()
    return render_template('history.html', history=records)

# Route đánh dấu một bản ghi là yêu thích
@app.route('/favorite/<int:id>', methods=['POST'])
def favorite(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE weather_history SET favorite = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return ''  

if __name__ == '__main__':
    init_db()  
    app.run(debug=True)  
