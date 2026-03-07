from flask import Flask, render_template, request, jsonify, session
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from backend.database import db, User, Conversation, Message, SymptomCheck
from backend.auth import auth_bp
from backend.mistral_model import MistralDoctorAssistant
import logging
import os
from datetime import datetime
import uuid

# Import admin blueprint
from backend.admin import admin_bp

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///doctor_ai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
CORS(app)


# Register admin blueprint
app.register_blueprint(admin_bp)

# Create default admin user if none exists (for first run)
def create_default_admin():
    with app.app_context():
        admin_exists = User.query.filter_by(role='super_admin').first()
        if not admin_exists:
            admin = User(
                username='admin',
                email='admin@doctorai.com',
                full_name='System Administrator',
                role='super_admin',
                is_active=True,
                is_verified=True,
                email_verified=True
            )
            admin.set_password('Admin@123')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created (username: admin, password: Admin@123)")

# Call this after database initialization
# Create database tables
with app.app_context():
    db.create_all()
    create_default_admin()

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')

# Initialize Mistral model
#try:
    #doctor_assistant = MistralDoctorAssistant()
   # model_available = True
#except Exception as e:
    #logging.error(f"Failed to load Mistral model: {e}")
    #doctor_assistant = None
   # model_available = False
# Temporary AI bypass (for low-power system)
doctor_assistant = None
model_available = False
# Create database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    return render_template('index.html', model_available=model_available)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/symptoms')
@login_required
def symptoms():
    return render_template('symptoms.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's recent conversations
    conversations = Conversation.query.filter_by(user_id=current_user.id)\
                    .order_by(Conversation.updated_at.desc()).limit(5).all()
    
    # Get recent symptom checks
    symptom_checks = SymptomCheck.query.filter_by(user_id=current_user.id)\
                    .order_by(SymptomCheck.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         conversations=conversations,
                         symptom_checks=symptom_checks)

# API Routes
@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    try:
        data = request.json
        message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get or create conversation
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                return jsonify({'error': 'Conversation not found'}), 404
        else:
            conversation = Conversation(
                user_id=current_user.id,
                title=message[:50] + '...',
                created_at=datetime.utcnow()
            )
            db.session.add(conversation)
            db.session.commit()
        
        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=message
        )
        db.session.add(user_message)
        
        # Get conversation history
        history = Message.query.filter_by(conversation_id=conversation.id)\
                  .order_by(Message.timestamp).all()
        
        history_formatted = [
            {'role': msg.role, 'content': msg.content} 
            for msg in history
        ]
        
        # Generate response
        if doctor_assistant:
            response = doctor_assistant.generate_response(message, history_formatted)
        else:
            response = "AI model is currently loading. Please try again in a moment."
        
        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role='assistant',
            content=response
        )
        db.session.add(assistant_message)
        
        # Update conversation
        conversation.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'response': response,
            'conversation_id': conversation.id,
            'message_id': assistant_message.id,
            'timestamp': assistant_message.timestamp.isoformat()
        })
        
    except Exception as e:
        logging.error(f"Chat API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/symptoms/analyze', methods=['POST'])
@login_required
def analyze_symptoms():
    try:
        data = request.json
        symptoms = data.get('symptoms', [])
        
        if not symptoms:
            return jsonify({'error': 'No symptoms provided'}), 400
        
        # Get user info
        user_info = {
            'age': current_user.date_of_birth,
            'gender': 'unknown'  # You can add gender field to User model
        }
        
        # Analyze symptoms
        if doctor_assistant:
            analysis = doctor_assistant.analyze_symptoms(symptoms, user_info)
            
            # Save symptom check
            symptom_check = SymptomCheck(
                user_id=current_user.id,
                symptoms=','.join(symptoms),
                analysis=analysis,
                severity='medium',  # Parse from analysis in production
                created_at=datetime.utcnow()
            )
            db.session.add(symptom_check)
            db.session.commit()
            
            return jsonify({
                'analysis': analysis,
                'symptom_check_id': symptom_check.id
            })
        else:
            return jsonify({'error': 'AI model not available'}), 503
            
    except Exception as e:
        logging.error(f"Symptom analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    conversations = Conversation.query.filter_by(user_id=current_user.id)\
                    .order_by(Conversation.updated_at.desc()).all()
    
    return jsonify([{
        'id': c.id,
        'title': c.title,
        'created_at': c.created_at.isoformat(),
        'updated_at': c.updated_at.isoformat(),
        'message_count': len(c.messages)
    } for c in conversations])

@app.route('/api/conversations/<int:conv_id>/messages', methods=['GET'])
@login_required
def get_conversation_messages(conv_id):
    conversation = Conversation.query.get_or_404(conv_id)
    
    if conversation.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    messages = Message.query.filter_by(conversation_id=conv_id)\
              .order_by(Message.timestamp).all()
    
    return jsonify([{
        'id': m.id,
        'role': m.role,
        'content': m.content,
        'timestamp': m.timestamp.isoformat()
    } for m in messages])

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'model_available': model_available,
        'authenticated': current_user.is_authenticated if current_user else False
    })

    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)