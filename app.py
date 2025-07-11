from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Gokul",
    database="karkakasadara"
)
cursor = db.cursor()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['email'] = user[2]
            session['role'] = user[4]
            flash("Login Successful!", "success")

            if user[4] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = 'student'
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)", (name, email, password, role))
        db.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/student_dashboard')
def student_dashboard():
    if 'email' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM study_materials")
    materials = cursor.fetchall()

    cursor.execute("SELECT * FROM mock_tests ORDER BY test_date")
    mock_tests = cursor.fetchall()

    # Fetch completed test results for this student
    cursor.execute("""
        SELECT r.id, mt.title, mt.test_date, r.score 
        FROM results r
        JOIN mock_tests mt ON r.test_id = mt.id
        WHERE r.student_id = %s
        ORDER BY mt.test_date DESC
    """, (session['user_id'],))
    completed_tests = cursor.fetchall()

    return render_template(
        'student_dashboard.html', 
        materials=materials, 
        mock_tests=mock_tests,
        completed_tests=completed_tests
    )

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'email' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM study_materials")
    materials = cursor.fetchall()

    cursor.execute("SELECT * FROM mock_tests ORDER BY test_date")
    mock_tests = cursor.fetchall()

    return render_template('admin_dashboard.html', materials=materials, mock_tests=mock_tests)

@app.route('/upload_material', methods=['POST'])
def upload_material():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    title = request.form['title']
    file = request.files['pdf']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        link = f"/{filepath}"
        cursor.execute("INSERT INTO study_materials (title, link) VALUES (%s, %s)", (title, link))
        db.commit()
        flash("Study material uploaded successfully!", "success")
    else:
        flash("Only PDF files are allowed!", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_material/<int:id>')
def delete_material(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    cursor.execute("SELECT link FROM study_materials WHERE id = %s", (id,))
    result = cursor.fetchone()
    if result:
        file_path = result[0].lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)
    cursor.execute("DELETE FROM study_materials WHERE id = %s", (id,))
    db.commit()
    flash("Material deleted!", "info")
    return redirect(url_for('admin_dashboard'))

@app.route('/schedule_mock_test', methods=['POST'])
def schedule_mock_test():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    title = request.form['title']
    date = request.form['date']
    instructions = request.form['instructions']
    cursor.execute("INSERT INTO mock_tests (title, test_date, instructions) VALUES (%s, %s, %s)", (title, date, instructions))
    db.commit()
    flash("Mock test scheduled successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_mock_test/<int:id>')
def delete_mock_test(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        # First delete all questions for this test
        cursor.execute("DELETE FROM questions WHERE test_id = %s", (id,))
        # Then delete all results for this test
        cursor.execute("DELETE FROM results WHERE test_id = %s", (id,))
        # Finally delete the test itself
        cursor.execute("DELETE FROM mock_tests WHERE id = %s", (id,))
        db.commit()
        flash("Mock test and all related data deleted successfully!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error deleting mock test: {str(e)}", "danger")
    
    return redirect(url_for('admin_dashboard'))

@app.route('/add_question/<int:test_id>', methods=['GET', 'POST'])
def add_question(test_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Get test information
    cursor.execute("SELECT title, instructions FROM mock_tests WHERE id=%s", (test_id,))
    test_info = cursor.fetchone()
    
    if request.method == 'POST':
        # Get all submitted questions
        questions = request.form.getlist('question[]')
        options_a = request.form.getlist('option_a[]')
        options_b = request.form.getlist('option_b[]')
        options_c = request.form.getlist('option_c[]')
        options_d = request.form.getlist('option_d[]')
        answers = request.form.getlist('answer[]')
        
        # Insert each question into the database
        for i in range(len(questions)):
            qn = questions[i]
            a = options_a[i]
            b = options_b[i]
            c = options_c[i]
            d = options_d[i]
            ans = answers[i]
            
            if qn.strip():  # Only insert if question is not empty
                cursor.execute("""
                    INSERT INTO questions (test_id, question, option_a, option_b, option_c, option_d, answer) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (test_id, qn, a, b, c, d, ans))
        
        db.commit()
        flash("Questions added successfully!", "success")
        return redirect(url_for('admin_dashboard'))
    
    # Fetch existing questions for this test
    cursor.execute("SELECT * FROM questions WHERE test_id=%s", (test_id,))
    existing_questions = cursor.fetchall()
    
    return render_template(
        'add_question.html', 
        test_id=test_id, 
        test_info=test_info,
        existing_questions=existing_questions
    )
@app.route('/delete_question/<int:question_id>')
def delete_question(question_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    cursor.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    db.commit()
    flash("Question deleted successfully!", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/attend_test/<int:test_id>', methods=['GET', 'POST'])
def attend_test(test_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    if request.method == 'POST':
        marks = 0
        cursor.execute("SELECT id, answer FROM questions WHERE test_id=%s", (test_id,))
        qns = cursor.fetchall()
        for q in qns:
            qid = str(q[0])
            correct = q[1]
            selected = request.form.get(qid, '')
            if selected == correct:
                marks += 1
        
        # Check if the student has already taken this test
        cursor.execute("SELECT * FROM results WHERE student_id=%s AND test_id=%s", (session['user_id'], test_id))
        existing_result = cursor.fetchone()
        
        if existing_result:
            # Update existing result
            cursor.execute("UPDATE results SET score=%s WHERE id=%s", (marks, existing_result[0]))
        else:
            # Insert new result
            cursor.execute("INSERT INTO results (student_id, test_id, score) VALUES (%s, %s, %s)", 
                           (session['user_id'], test_id, marks))
        
        db.commit()
        flash(f"Test submitted! Your score is {marks}.", "success")
        return redirect(url_for('student_dashboard'))

    cursor.execute("SELECT * FROM questions WHERE test_id = %s", (test_id,))
    questions = cursor.fetchall()
    
    cursor.execute("SELECT title, instructions FROM mock_tests WHERE id = %s", (test_id,))
    test_info = cursor.fetchone()
    
    return render_template('attend_test.html', questions=questions, test_info=test_info)

if __name__ == '__main__':
    app.run(debug=True)