# app.py
import os
import uuid
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__, 
            template_folder=os.path.abspath('templates'), 
            static_folder=os.path.abspath('static'))

app.secret_key = 'super_secret_cookie_key_reposteria' # Cambia esto si lo subes a internet
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cookies.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# ==========================================
#          MODELOS DE LA BASE DE DATOS
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=True)
    active = db.Column(db.Integer, default=1) # 1 = Activo, 0 = Eliminado/Oculto

class CookieOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Recibido') # Recibido, En horno, En camino, Entregado
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('cookie_order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

# Función auxiliar para validar extensiones de imágenes
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ==========================================
#          MÓDULO 1: FRONTEND PÚBLICO
# ==========================================

@app.route('/')
def index():
    products = Product.query.filter_by(active=1).all()
    return render_template('index.html', products=products)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    pid_str = str(product_id)
    
    # CORRECCIÓN: Captura la cantidad variable elegida por el usuario
    qty_to_add = int(request.form.get('quantity', 1))
    
    if pid_str in cart:
        cart[pid_str] += qty_to_add
    else:
        cart[pid_str] = qty_to_add
        
    session['cart'] = cart
    flash('¡Cookies añadidas al carrito correctamente!', 'success')
    return redirect(url_for('index'))

@app.route('/cart')
def cart():
    if 'cart' not in session or not session['cart']:
        return render_template('cart.html', cart_items=[], total=0)
    
    cart_items = []
    total = 0
    for pid_str, qty in session['cart'].items():
        product = Product.query.get(int(pid_str))
        if product:
            subtotal = product.price * qty
            total += subtotal
            cart_items.append({'product': product, 'quantity': qty, 'subtotal': subtotal})
            
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

@app.route('/cart/increase/<int:product_id>')
def cart_increase(product_id):
    if 'cart' in session:
        pid_str = str(product_id)
        if pid_str in session['cart']:
            session['cart'][pid_str] += 1
            session.modified = True  # Le avisa a Flask que la sesión cambió
    return redirect(url_for('cart'))

@app.route('/cart/decrease/<int:product_id>')
def cart_decrease(product_id):
    if 'cart' in session:
        pid_str = str(product_id)
        if pid_str in session['cart']:
            session['cart'][pid_str] -= 1
            # Si la cantidad baja a 0, eliminamos el producto del carrito
            if session['cart'][pid_str] <= 0:
                session['cart'].pop(pid_str)
            session.modified = True
    return redirect(url_for('cart'))

@app.route('/cart/delete/<int:product_id>')
def cart_delete_item(product_id):
    if 'cart' in session:
        pid_str = str(product_id)
        if pid_str in session['cart']:
            session['cart'].pop(pid_str)
            session.modified = True
    flash('Producto removido del carrito', 'info')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        customer_name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']
        notes = request.form['notes'] if request.form['notes'] else "Sin notas adicionales"
        
        total = 0
        items_to_save = []
        detalles_whatsapp = [] 
        
        for pid_str, qty in session['cart'].items():
            product = Product.query.get(int(pid_str))
            if product:
                subtotal = product.price * qty
                total += subtotal
                items_to_save.append((product.id, qty, product.price))
                detalles_whatsapp.append(f"- {qty}x {product.name} (${subtotal:.2f})")
        
        order_number = str(uuid.uuid4()).split('-')[0].upper()
        
        # Guardar en base de datos local para el panel ADMIN
        new_order = CookieOrder(
            order_number=order_number, customer_name=customer_name,
            address=address, phone=phone, notes=notes, total=total
        )
        db.session.add(new_order)
        db.session.commit()
        
        for p_id, qty, price in items_to_save:
            item = OrderItem(order_id=new_order.id, product_id=p_id, quantity=qty, price=price)
            db.session.add(item)
        db.session.commit()
        
        session.pop('cart', None) # Limpiar carrito de la sesión
        
        # --- CONFIGURACIÓN DE TU WHATSAPP ---
        # ⚠️ Pon tu número aquí: código de país + código de área + número (sin el signo + ni espacios)
        # Ejemplo para Argentina: "5491112345678"
        tu_telefono = "5491112345678" 
        
        productos_texto = "\n".join(detalles_whatsapp)
        mensaje_bruto = (
            f"¡Hola! Vengo de la web y quiero confirmar mi pedido:\n\n"
            f"*Pedido:* #{order_number}\n"
            f"*Cliente:* {customer_name}\n"
            f"*Dirección:* {address}\n"
            f"*Teléfono:* {phone}\n"
            f"*Notas:* {notes}\n\n"
            f"*Detalle de compra:*\n{productos_texto}\n\n"
            f"*Total a Pagar:* ${total:.2f}"
        )
        
        mensaje_encriptado = urllib.parse.quote(mensaje_bruto)
        whatsapp_url = f"https://wa.me/{tu_telefono}?text={mensaje_encriptado}"
        
        return render_template('order_success.html', order_number=order_number, whatsapp_url=whatsapp_url)
        
    return render_template('checkout.html')


# ==========================================
#       MÓDULO 2: PANEL DE ADMINISTRACIÓN
# ==========================================

def check_admin_auth():
    if 'admin_logged_in' not in session:
        return False
    return True

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['admin_logged_in'] = True
            session['admin_user'] = user.username
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_user', None)
    return redirect(url_for('index'))

@app.route('/admin')
@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not check_admin_auth():
        return redirect(url_for('admin_login'))
        
    if request.method == 'POST':
        order_id = request.form['order_id']
        new_status = request.form['status']
        order = CookieOrder.query.get(order_id)
        if order:
            order.status = new_status
            db.session.commit()
            flash(f'Pedido #{order.order_number} actualizado a: {new_status}', 'success')
            
    orders = CookieOrder.query.order_by(CookieOrder.id.desc()).all()
    return render_template('admin/dashboard.html', orders=orders)

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if not check_admin_auth():
        return redirect(url_for('admin_login'))
        
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        
        file = request.files['image']
        filename = 'default_cookie.jpg'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        new_product = Product(name=name, description=description, price=price, image_url=filename)
        db.session.add(new_product)
        db.session.commit()
        flash('¡Nueva cookie agregada al catálogo con éxito!', 'success')
        return redirect(url_for('admin_products'))
        
    products = Product.query.filter_by(active=1).all()
    return render_template('admin/products.html', products=products)

# CORRECCIÓN: Nueva ruta para guardar cambios de edición de productos
@app.route('/admin/products/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    if not check_admin_auth():
        return redirect(url_for('admin_login'))
    
    product = Product.query.get(product_id)
    if product:
        product.price = float(request.form['price'])
        product.description = request.form['description']
        db.session.commit()
        flash(f'¡{product.name} actualizada correctamente!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete/<int:product_id>')
def delete_product(product_id):
    if not check_admin_auth():
        return redirect(url_for('admin_login'))
    
    product = Product.query.get(product_id)
    if product:
        product.active = 0 # Eliminación suave (soft delete)
        db.session.commit()
        flash('Producto removido del catálogo público.', 'warning')
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)