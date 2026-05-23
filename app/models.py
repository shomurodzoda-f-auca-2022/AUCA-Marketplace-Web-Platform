from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

favourites = db.Table('favourites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), nullable=False)
    au_ca_email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20), nullable=True)  # optional phone if you want later
    items = db.relationship('Item', backref='owner', lazy=True)
    favourites = db.relationship('Item', secondary=favourites, backref='favourited_by', lazy='dynamic')  # ← ADD THIS

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=True)
    contact_info = db.Column(db.String(100), nullable=False)
    image_filename = db.Column(db.String(256), nullable=True)