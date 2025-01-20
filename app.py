from flask import Flask, request, redirect, url_for, render_template, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
app.config["MONGO_URI"] = os.getenv('MONGO_URI', "mongodb://localhost:27017/event_planner")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MongoDB connection
mongo = PyMongo(app)

# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']

# Load user from the database
@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# Route for the index page
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username:
            flash('Username is required.', 'error')
            return render_template('login.html')
        
        user = mongo.db.users.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            login_user(User(user))
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html')

# Route for user logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        existing_user = mongo.db.users.find_one({'username': request.form['username']})
        if existing_user is None:
            hashed_password = generate_password_hash(request.form['password'])
            mongo.db.users.insert_one({
                'username': request.form['username'],
                'email': request.form['email'],
                'password': hashed_password
            })
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        flash('A user already exists with that username.', 'error')
    return render_template('register.html')

# Route for the dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    events = list(mongo.db.events.find({'creator': ObjectId(current_user.id)}))  # Created events
    accepted_events = list(mongo.db.events.find({
        'attendees': current_user.username
    }))  # Accepted events
    invitations = list(mongo.db.events.find({
        'invitations': {
            '$elemMatch': {
                'username': current_user.username,
                'status': 'pending'
            }
        }
    }))
    return render_template('dashboard.html', events=events, invitations=invitations)

# Route for creating a new event
@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        event = {
            'name': request.form['name'],
            'date': request.form['date'],
            'location': request.form['location'],
            'description': request.form['description'],
            'creator': ObjectId(current_user.id),
            'attendees': [current_user.username],
            'attendee_count': 1,
            'invitations': []
        }
        event_id = mongo.db.events.insert_one(event).inserted_id
        flash('Event created successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_event.html')

# Route for event details
@app.route('/event/<event_id>')
@login_required
def event_detail(event_id):
    event = mongo.db.events.find_one({'_id': ObjectId(event_id)})
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('dashboard'))
    
    creator = mongo.db.users.find_one({'_id': event['creator']})
    attendees = event.get('attendees', [])
    return render_template('event_detail.html', event=event, creator=creator, attendees=attendees)

# Route for inviting users to an event
@app.route('/invite/<event_id>', methods=['POST'])
@login_required
def invite(event_id):
    event = mongo.db.events.find_one({'_id': ObjectId(event_id)})
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('dashboard'))
    
    if event['creator'] != ObjectId(current_user.id):
        flash('You are not authorized to invite people to this event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    invite_username = request.form.get('invite_username')
    invited_user = mongo.db.users.find_one({'username': invite_username})
    
    if invited_user:
        if invite_username in event['attendees']:
            flash(f'{invite_username} is already attending this event.', 'warning')
            return redirect(url_for('event_detail', event_id=event_id))
        
        existing_invitation = next((inv for inv in event['invitations'] if inv['username'] == invite_username), None)
        if existing_invitation:
            flash(f'{invite_username} has already been invited to this event.', 'warning')
            return redirect(url_for('event_detail', event_id=event_id))
        
        new_invitation = {
            'username': invite_username,
            'status': 'pending',
            'invited_at': datetime.utcnow()
        }
        
        mongo.db.events.update_one(
            {'_id': ObjectId(event_id)},
            {'$push': {'invitations': new_invitation}}
        )
        
        flash(f'Invitation sent to {invite_username}!', 'success')
    else:
        flash('User not found with that username.', 'error')
    
    return redirect(url_for('event_detail', event_id=event_id))

# Route for responding to invitations
@app.route('/respond_invitation', methods=['POST'])
@login_required
def respond_invitation():
    event_id = request.form.get('event_id')
    response = request.form.get('response')
    
    event = mongo.db.events.find_one({'_id': ObjectId(event_id)})
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('dashboard'))
    
    invitation = next((inv for inv in event['invitations'] if inv['username'] == current_user.username and inv['status'] == 'pending'), None)
    if not invitation:
        flash('Invitation not found or you are not authorized to respond.', 'error')
        return redirect(url_for('dashboard'))
    
    if response == 'accept':
        mongo.db.events.update_one(
            {'_id': ObjectId(event_id)},
            {
                '$set': {'invitations.$[elem].status': 'accepted'},
                '$addToSet': {'attendees': current_user.username},
                '$inc': {'attendee_count': 1}
            },
            array_filters=[{'elem.username': current_user.username}]
        )
        flash('Invitation accepted successfully! The event has been added to your events.', 'success')
    elif response == 'reject':
        mongo.db.events.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': {'invitations.$[elem].status': 'rejected'}},
            array_filters=[{'elem.username': current_user.username}]
        )
        flash('Invitation rejected successfully!', 'success')
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
