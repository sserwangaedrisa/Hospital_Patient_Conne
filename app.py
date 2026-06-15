
from flask import Flask, render_template, redirect, session, request, jsonify, url_for
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'chat_secret'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), default = "None")
    message = db.Column(db.Text, nullable=True)
    time = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)


class Users(db.Model):
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(30))
    email = db.Column(db.String(40), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(100), nullable=True)
    status = db.Column(db.Integer, default = 0)
    time = db.Column(db.DateTime, default=db.func.current_timestamp())


class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, nullable=False)
    patient_name = db.Column(db.String(20), nullable=False)
    medication_name = db.Column(db.String(20), nullable=False)
    total_dosage = db.Column(db.Integer, nullable=False)
    dosage_per_take = db.Column(db.Integer, nullable=False)
    dosage_interval = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=lambda: datetime.now().replace(second=0, microsecond=0))
    next_dosage_time = db.Column(db.DateTime)
    dosage_remaining = db.Column(db.Integer, )
    dosage_status = db.Column(db.String(20), default = 'In progress')

    def set_next_dosage_time(self):
        if self.start_date and self.dosage_interval:
            self.next_dosage_time = self.start_date + timedelta(hours=int(self.dosage_interval))

    def set_next_dosage_time_after(self):
        self.next_dosage_time += timedelta(hours = self.dosage_interval)

    def set_initial_dosage_remaining(self):
        self.dosage_remaining = self.total_dosage

    def set_dosage_remaining(self):
        self.dosage_remaining = self.dosage_remaining - self.dosage_per_take

    def auto_update_next_dosage_time():
        with app.app_context():
            medications = Medication.query.all()
            for med in medications:
                med.set_next_dosage_time()


    scheduler = BackgroundScheduler()
    scheduler.add_job(func=auto_update_next_dosage_time, trigger = "interval", minutes = 1)
    scheduler.start()

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, nullable=False)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.id'), nullable=False)
    medication_taken = db.Column(db.String(30))
    health_status = db.Column(db.String(30), nullable=False)
    time = db.Column(db.DateTime, default=lambda: datetime.now().replace(second=0, microsecond=0))
    taken_on_time = db.Column(db.Boolean, default=False)
    delay_minutes = db.Column(db.Integer, default=0)

    medication = db.relationship('Medication', backref=db.backref('responses', lazy=True))

    def mark_dosage_taken(self, med: "Medication"):
        if not med:
            return

        expected_time = med.next_dosage_time
        actual_time = self.time

        # Compare actual vs expected
        if actual_time <= expected_time:
            self.taken_on_time = True
            self.delay_minutes = 0
        else:
            self.taken_on_time = False
            self.delay_minutes = int((actual_time - expected_time).total_seconds() / 60)

        # Update medication fields
        med.set_next_dosage_time_after()
        med.set_dosage_remaining()

        # Mark complete if finished
        if med.dosage_remaining <= 0:
            med.dosage_status = 'completed'
        else:
            med.dosage_status = 'in progress'

        # Save updates
        db.session.add(self)
        db.session.add(med)
        db.session.commit()

with app.app_context():
    db.create_all()

# CHATBOT INITIALIZATION

OLLAMA_URL = "http://localhost:11434/api/generate"

ALLOWED_TOPICS = [
    "diet", "exercise", "nutrition", "sleep",
    "stress", "hydration", "fitness",
    "healthy", "wellness", "hygiene"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contact', methods = ['GET'])
def contact():
    return render_template('contact.html')

@app.route('/news', methods = ["GET"])
def news():
    return render_template('news.html')

@app.route("/about",  methods = ['GET'])
def about():
    return render_template('about.html')
@app.route('/chatbot', methods = ['GET'])
def chatbot():
    return render_template('search.html')

@app.route ('/staffDashboard', methods = ['GET', 'POST'])
def staffDashboard():
    if request.method == 'GET':
        patients = Users.query.filter_by(role = 'patient').all()
        return render_template('staffDashboard.html', patients = patients)



    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        patient_name = request.form.get('patient_name')
        medname = request.form.get('medname')
        total_dosage = request.form.get("total_dosage")
        dosage_per_take = request.form.get("dosage_per_take")
        dosage_interval = request.form.get("dosage_interval")



        med = Medication(
            patient_id=1,
            patient_name=patient_name,
            medication_name=medname,
            total_dosage=total_dosage,
            dosage_per_take=dosage_per_take,
            dosage_interval=dosage_interval,
            start_date=datetime.now().replace(second=0, microsecond=0)
        )
        med.set_next_dosage_time()
        med.set_initial_dosage_remaining()
        db.session.add(med)
        db.session.commit()

        return redirect('/chatmate')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    if request.method == 'POST':
        username = request.form.get('username')
        session['username'] = username

        user = Users.query.filter_by(username=username).first()
        print('user', user.role, user.status, user.email)
        if user.role == 'patient':
            user.status = 1
            db.session.add(user)
            db.session.commit()
            return redirect('/dashboard')
        elif user.role == 'staff':

            return redirect('/staffDashboard')
        else:
            return redirect('/login')



@app.route('/response', methods=['POST'])
def response():
    medication_taken = request.form.get('medication_name')
    patient_response = request.form.get('patient_comment')

    med = Medication.query.filter_by(medication_name=medication_taken).first()

    if not med:
        return jsonify({"error": "Medication not found"}), 404

    # Create response entry
    response = Response(
        medication_id=med.id,
        patient_id=med.patient_id,
        medication_taken=medication_taken,
        health_status=patient_response,
        time=datetime.now().replace(second=0, microsecond=0)
    )

    # Update medication and log response
    response.mark_dosage_taken(med)

    # Return updated info to frontend
    return jsonify({
        "message": "Response recorded successfully",
        "medication": {
            "id": med.id,
            "name": med.medication_name,
            "next_dosage_time": med.next_dosage_time.strftime("%Y-%m-%d %H:%M"),
            "dosage_remaining": med.dosage_remaining,
            "status": med.dosage_status
        }
    }), 200





@app.route('/dashboard', methods = ['GET', 'POST'])
def dashboard():
    if request.method == 'GET':
        username = session['username']
        med = Medication.query.filter(Medication.patient_name == username).all()
        return render_template('medication.html', med = med)

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    if request.method == 'POST':

        username = request.form.get('username')
        email  = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        status = 0



        user = Users(username = username, email = email, password = password, status = status, role = role)
        db.session.add(user)
        db.session.commit()
        return redirect('/login')

@app.route('/chatmate', methods = ["POST", "GET"])
def chatmate():
    if request.method == "GET":
        return render_template("chatDashboard.html")
    if request.method == "POST":
        receiver = request.form.get('chatmate')
        return redirect(url_for("chat", receiver = receiver))


@app.route('/chat/<receiver>', methods=['GET', 'POST'])
def chat(receiver):

    if 'username' not in session:
        return redirect('/login')
    username = session['username']

    if request.method == "GET":
        sender = username
        session['receiver'] = receiver
        dbRecievers = Users.query.filter(
            Users.username == receiver
        ).first()
        if not dbRecievers:
            return redirect('/chatmate')
        chatMessages = Message.query.filter(
            or_(
                and_(Message.receiver == receiver, Message.sender == sender),
                and_(Message.receiver == sender, Message.sender == receiver)
            )
        ).order_by(Message.time).all()
    return render_template('chat.html', messages = chatMessages, username = sender, receiver = receiver )



@socketio.on("sendMessage")
def receiveMessage(message, socketio_id):
    message = message
    origin = 'server'
    sender = session['username']
    receiver = session['receiver']
    messageData = { "message": message,
                    "origin": origin,
                    "sender": sender,
                    "receiver": receiver,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                   }
    time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"time is : {time}")
    socketio.emit("serverMessage", messageData, namespace = None, skip_sid = request.sid)

    newMessage = Message(message = message, sender = sender, receiver = receiver)
    db.session.add(newMessage)
    db.session.commit()

# CHATBOT ROUTE

@app.route('/chatbot_api', methods=['POST', 'GET'])
def chatbot_api():
    user_input = request.json.get('message', '')
    # if not any(topic in user_input.lower() for topic in ALLOWED_TOPICS):
    #     return jsonify({"response": "I'm sorry, I can only assist with health-related topics"})

    prompt = f"""
        You are a health consultant AI.

        Your task:
        - Answer ONLY health-related questions.

        Rules:
        - If the user's message is NOT related to health, reply with:
        "I am a health assistant and can only help with health-related questions."
        - Do NOT answer anything apart from the question asked
        - Do NOT include "AI:" or "User:" in your response
        - Do NOT repeat the user's question
        - Answer in plain text only
        - Keep responses short and clear
        - Give general health advice only (no diagnosis)

        User message:
        {user_input}

        Answer:
        """


    response = requests.post(OLLAMA_URL, json= {
        "model": "tinyllama",
        "prompt": prompt,
        "stream": False,
    })
    print(response.json())
    ai_response = response.json()["response"]
    print(f"AI Response: {ai_response}")
    return jsonify({"response": ai_response})



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
