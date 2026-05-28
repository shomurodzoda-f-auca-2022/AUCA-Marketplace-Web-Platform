from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Item, ItemImage
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import re
from datetime import datetime, timezone

#Configurations
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auca_marketplace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload (optional)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

#Initialization
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for("login"))

@app.before_request
def create_tables():
    db.create_all()

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

#Web Page Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('items'))

    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if not re.match(r'.+@auca\.kg$', email):
            flash("Register cannot be completed. Use your AUCA email (example@auca.kg) only.", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(au_ca_email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = User(nickname=nickname, au_ca_email=email, password_hash=hashed_password, phone=phone or None)
        db.session.add(user)
        db.session.commit()
        flash("Registered successfully! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('items'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(au_ca_email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('items'))
        flash("Invalid email or password", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for('home'))

@app.route('/items')
@login_required
def items():
    search = request.args.get('search')

    if search:
        all_items = Item.query.filter(Item.title.ilike(f"%{search}%")).all()
    else:
        all_items = Item.query.order_by(Item.id.desc()).all()

    fav_ids = {item.id for item in current_user.favourites}

    return render_template('items.html', items=all_items, fav_ids=fav_ids)

@app.route('/item/<int:item_id>')
@login_required
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template('item_detail.html', item=item)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        title        = request.form.get('title', '').strip()
        description  = request.form.get('description', '').strip()
        try:
            quantity = int(request.form.get('quantity', 1))
        except ValueError:
            quantity = 1
        try:
            price = float(request.form.get('price', 0))
        except ValueError:
            price = 0.0
        contact_info = request.form.get('contact_info', '').strip()

        new_item = Item(
            title=title,
            description=description,
            quantity=quantity,
            price=price,
            contact_info=contact_info,
            owner=current_user
        )
        db.session.add(new_item)
        db.session.flush()  # get new_item.id before commit

        images = request.files.getlist('images')
        first  = True
        for image in images:
            if image and image.filename != '' and allowed_file(image.filename):
                import uuid
                filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                db.session.add(ItemImage(item_id=new_item.id, image_filename=filename))
                if first:
                    new_item.image_filename = filename  # thumbnail for cards
                    first = False

        db.session.commit()
        flash("Item added successfully!", "success")
        return redirect(url_for('items'))

    return render_template('add_item.html')

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)

    # SECURITY: only owner can edit
    if item.owner != current_user:
        flash("You are not allowed to edit this item.", "danger")
        return redirect(url_for('items'))

    if request.method == 'POST':
        item.title = request.form.get('title')
        item.description = request.form.get('description')
        item.quantity = int(request.form.get('quantity'))
        item.price = float(request.form.get('price'))
        item.contact_info = request.form.get('contact_info')

        db.session.commit()
        flash("Item updated successfully!", "success")
        return redirect(url_for('item_detail', item_id=item.id))

    return render_template('edit_item.html', item=item)

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)

    # SECURITY: only owner can delete
    if item.owner != current_user:
        flash("You are not allowed to delete this item.", "danger")
        return redirect(url_for('items'))

    db.session.delete(item)
    db.session.commit()

    flash("Item deleted successfully!", "success")
    return redirect(url_for('items'))


# ── FAVOURITES ────────────────────────────────────────────────────────────────

@app.route('/toggle_favourite/<int:item_id>', methods=['POST'])
@login_required
def toggle_favourite(item_id):
    item = Item.query.get_or_404(item_id)
    if current_user.favourites.filter_by(id=item_id).first():
        current_user.favourites.remove(item)
        is_fav = False
    else:
        current_user.favourites.append(item)
        is_fav = True
    db.session.commit()
    # Returns JSON so the heart button can update without a page reload
    return jsonify({'is_fav': is_fav})


@app.route('/favourites')
@login_required
def favourites():
    fav_items = current_user.favourites.all()
    fav_ids = {item.id for item in fav_items}
    return render_template('favorites.html', items=fav_items, fav_ids=fav_ids)

@app.route('/my_listings')
@login_required
def my_listings():
    user_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.id.desc()).all()
    return render_template('my_listings.html', items=user_items)

@app.template_filter('timeago')
def timeago_filter(dt):
    if dt is None:
        return 'some time ago'
    now   = datetime.utcnow()
    diff  = now - dt
    secs  = int(diff.total_seconds())
    if secs < 60:
        return 'just now'
    elif secs < 3600:
        m = secs // 60
        return f'{m} minute{"s" if m != 1 else ""} ago'
    elif secs < 86400:
        h = secs // 3600
        return f'{h} hour{"s" if h != 1 else ""} ago'
    elif secs < 604800:
        d = secs // 86400
        return f'{d} day{"s" if d != 1 else ""} ago'
    elif secs < 2592000:
        w = secs // 604800
        return f'{w} week{"s" if w != 1 else ""} ago'
    elif secs < 31536000:
        mo = secs // 2592000
        return f'{mo} month{"s" if mo != 1 else ""} ago'
    else:
        y = secs // 31536000
        return f'{y} year{"s" if y != 1 else ""} ago'

# Run
if __name__ == '__main__':
    app.run(debug=True)