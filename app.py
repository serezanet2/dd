from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_link = db.Column(db.String(120), unique=True, nullable=False)

# Модель контакта
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Модель сообщения
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

# Создаем базу данных при первом запуске
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('profile', link=session['profile_link']))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        profile_link = request.form['profile_link']
        
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято')
            return redirect(url_for('register'))
        
        if User.query.filter_by(profile_link=profile_link).first():
            flash('Эта ссылка уже занята')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password=password, profile_link=profile_link)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['profile_link'] = new_user.profile_link
        
        return redirect(url_for('profile', link=new_user.profile_link))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['profile_link'] = user.profile_link
            return redirect(url_for('profile', link=user.profile_link))
        else:
            flash('Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/<link>')
def profile(link):
    user = User.query.filter_by(profile_link=link).first()
    
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('index'))
    
    # Проверяем, является ли текущий пользователь владельцем профиля
    is_owner = 'user_id' in session and session['user_id'] == user.id
    
    return render_template('profile.html', user=user, is_owner=is_owner)

@app.route('/add_contact/<link>', methods=['POST'])
def add_contact(link):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    contact_user = User.query.filter_by(profile_link=link).first()
    
    if not contact_user:
        flash('Пользователь не найден')
        return redirect(url_for('index'))
    
    # Проверяем, нет ли уже такого контакта
    existing_contact = Contact.query.filter_by(
        user_id=session['user_id'],
        contact_id=contact_user.id
    ).first()
    
    if not existing_contact:
        new_contact = Contact(user_id=session['user_id'], contact_id=contact_user.id)
        db.session.add(new_contact)
        db.session.commit()
        flash('Контакт добавлен')
    else:
        flash('Этот пользователь уже в ваших контактах')
    
    return redirect(url_for('profile', link=link))

@app.route('/contacts')
def contacts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_contacts = Contact.query.filter_by(user_id=session['user_id']).all()
    contact_users = [User.query.get(contact.contact_id) for contact in user_contacts]
    
    return render_template('contacts.html', contacts=contact_users)

@app.route('/chat/<link>')
def chat(link):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    contact_user = User.query.filter_by(profile_link=link).first()
    
    if not contact_user:
        flash('Пользователь не найден')
        return redirect(url_for('index'))
    
    # Проверяем, есть ли контакт
    is_contact = Contact.query.filter_by(
        user_id=session['user_id'],
        contact_id=contact_user.id
    ).first()
    
    if not is_contact:
        flash('Этот пользователь не в ваших контактах')
        return redirect(url_for('profile', link=link))
    
    # Получаем историю сообщений
    messages = Message.query.filter(
        ((Message.sender_id == session['user_id']) & (Message.receiver_id == contact_user.id)) |
        ((Message.sender_id == contact_user.id) & (Message.receiver_id == session['user_id']))
    ).order_by(Message.timestamp.asc()).all()
    
    return render_template('chat.html', contact=contact_user, messages=messages)

@app.route('/send_message/<link>', methods=['POST'])
def send_message(link):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    contact_user = User.query.filter_by(profile_link=link).first()
    
    if not contact_user:
        flash('Пользователь не найден')
        return redirect(url_for('index'))
    
    content = request.form['content']
    
    if content:
        new_message = Message(
            sender_id=session['user_id'],
            receiver_id=contact_user.id,
            content=content
        )
        db.session.add(new_message)
        db.session.commit()
    
    return redirect(url_for('chat', link=link))

if __name__ == '__main__':
    app.run(debug=True)
