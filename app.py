from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import bcrypt
import datetime
import os
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_save2serve_123')

# MongoDB configuration
# Uses MONGO_URI environment variable if set (recommended for production)
# Falls back to Atlas URI for Render deployment
mongo_uri = os.environ.get('MONGO_URI', 'mongodb+srv://GITAM:Gitam@123@cluster0.ojbso4h.mongodb.net/Gitamw?appName=Cluster0')
client = MongoClient(mongo_uri)
db = client['Gitamw']
users_collection = db['users']
donations_collection = db['donations']
rescues_collection = db['rescues']

@app.route('/')
def index():
    # Fetch dynamic stats
    active_savers = users_collection.count_documents({})
    # Sum food_shared_kg from donations
    total_shared_agg = list(donations_collection.aggregate([{'$group': {'_id': None, 'total': {'$sum': '$quantity'}}}]))
    total_shared = total_shared_agg[0]['total'] if total_shared_agg else 0
    
    # Placeholder for project count
    projects_funded = 50 
    lives_impacted = int(total_shared * 2) # Assume 1kg feeds 2 people (dummy calc)
    
    return render_template('index.html', 
                           savers=active_savers, 
                           shared_kg=total_shared, 
                           projects=projects_funded, 
                           impacted=lives_impacted)

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    # Store message in database
    contact_data = {
        'name': name,
        'email': email,
        'message': message,
        'date': datetime.datetime.utcnow()
    }
    db['messages'].insert_one(contact_data)
    
    flash('Thank you for your message! We will get back to you soon.', 'success')
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        if users_collection.find_one({'email': email}):
            flash('Email already exists. Please login.', 'danger')
            return redirect(url_for('signup'))

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'created_at': datetime.datetime.utcnow(),
            'food_rescued_kg': 0.0,
            'food_shared_kg': 0.0
        }

        users_collection.insert_one(user_data)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users_collection.find_one({'email': email})

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    user_donations = list(donations_collection.find({'user_id': session['user_id']}).sort('date', -1))
    user_rescues = list(rescues_collection.find({'user_id': session['user_id']}).sort('date', -1))
    
    return render_template('dashboard.html', user=user, donations=user_donations, rescues=user_rescues)

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/network')
def network():
    return render_template('network.html')

@app.route('/donate', methods=['POST'])
def donate():
    if 'user_id' not in session:
        flash('Please login to make a donation.', 'warning')
        return redirect(url_for('login'))

    try:
        quantity = float(request.form['quantity'])
        food_type = request.form['food_type']
        category = request.form['category']

        if quantity <= 0:
            flash('Quantity must be greater than zero.', 'danger')
            return redirect(url_for('dashboard'))

        donation_data = {
            'user_id': session['user_id'],
            'quantity': quantity,
            'food_type': food_type,
            'category': category,
            'date': datetime.datetime.utcnow()
        }

        donations_collection.insert_one(donation_data)

        # Update user totals
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$inc': {'food_shared_kg': quantity}}
        )

        flash(f'Successfully donated {quantity}kg of {food_type}!', 'success')
    except ValueError:
        flash('Invalid quantity entered.', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/save', methods=['POST'])
def save_money():
    if 'user_id' not in session:
        flash('Please login to track food rescue.', 'warning')
        return redirect(url_for('login'))

    try:
        quantity = float(request.form['quantity'])
        if quantity <= 0:
            flash('Quantity must be greater than zero.', 'danger')
            return redirect(url_for('dashboard'))

        # Store rescue event
        rescue_data = {
            'user_id': session['user_id'],
            'quantity': quantity,
            'date': datetime.datetime.utcnow()
        }
        rescues_collection.insert_one(rescue_data)

        # Update user food_rescued_kg
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$inc': {'food_rescued_kg': quantity}}
        )

        flash(f'Successfully tracked {quantity}kg of food rescued!', 'success')
    except ValueError:
        flash('Invalid quantity entered.', 'danger')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
