
from flask import Flask, render_template, request, session, flash, redirect, url_for
import random
from firebase_setup import db
from firebase_admin import auth
import requests
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import json
from PyPDF2 import PdfReader
from groq import Groq
from pydantic import BaseModel, Field, ValidationError
from typing import List

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')  # Use a secret key from environment

FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY')  # Firebase Web API Ke
api_key = os.getenv("GROQ_API_KEY")

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

client = Groq(api_key=api_key)

class Question(BaseModel):
    company: str
    question_text: str
    options: List[str]
    answer: str
    explanation: str
    category: str
    topic: str
    difficulty: str
    year: str

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html')


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        college_name = request.form.get('college')
        degree = request.form.get('degree')
        branch = request.form.get('branch')
        year_of_graduation = request.form.get('grad_year')

        # Validate passwords
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')

        # Handle profile image upload
        profile_image_url = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                imgname = str(random.randint(1000, 9999))
                filename = secure_filename(imgname + "_" + file.filename)
                filepath = app.config['UPLOAD_FOLDER']+ "/"+ filename
                file.save(filepath)
                profile_image_url = filepath  # Save local path or URL if needed

        try:
            # Create Firebase Auth user
            user = auth.create_user(email=email, password=password)

            # Save user data to Firestore
            db.collection('users').document(email).set({
                'full_name': full_name,
                'email': email,
                'college_name': college_name,
                'degree': degree,
                'branch': branch,
                'year_of_graduation': int(year_of_graduation),
                'profile_image_url': profile_image_url,
                'total_attempted_quizzes': 0,
                'total_accuracy': 0.0,
                'created_at': firestore.SERVER_TIMESTAMP,
                'is_admin': False
            })

            flash('User registered successfully. Please log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            r = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}",
                json=payload
            )
            if r.status_code == 200:
                # Save user email to session
                session['user'] = email

                # Fetch user data from Firestore
                user_doc = db.collection('users').document(email).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    if user_data.get('is_admin', False):
                        session['is_admin'] = True
                        flash('Admin logged in successfully.', 'success')
                        return redirect(url_for('admin'))
                    else:
                        session['is_admin'] = False
                        flash('User logged in successfully.', 'success')
                        return redirect(url_for('index'))
                else:
                    flash('User record not found in database.', 'danger')
            else:
                flash('Login failed. Please check your credentials.', 'danger')
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']

    try:
        user_doc = db.collection('users').document(user_email).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return render_template('dashboard.html', user=user_data)
        else:
            flash("User not found.", "danger")
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Error loading dashboard: {e}", "danger")
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/pyq', methods=['GET', 'POST'])
def pyq():
    if 'user' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    # Fetch distinct values for dropdowns from Firestore
    companies = list(set([q.to_dict()['company'] for q in db.collection("questions").stream()]))
    years = list(set([q.to_dict()['year'] for q in db.collection("questions").stream()]))
    categories = list(set([q.to_dict()['category'] for q in db.collection("questions").stream()]))
    difficulties = list(set([q.to_dict()['difficulty'] for q in db.collection("questions").stream()]))

    # Initialize the questions list as empty
    question_list = []

    # Get filter parameters from the form (if any)
    company = request.form.get('company', '')
    year = request.form.get('year', '')
    category = request.form.get('category', '')
    difficulty = request.form.get('difficulty', '')

    # Check if the form was submitted with a company selection
    if company:
        # Build the Firestore query based on filters
        query = db.collection("questions")
        
        if company:
            query = query.where("company", "==", company)
        if year:
            query = query.where("year", "==", year)
        if category:
            query = query.where("category", "==", category)
        if difficulty:
            query = query.where("difficulty", "==", difficulty)

        # Execute the query and get results
        questions = query.stream()
        question_list = [q.to_dict() for q in questions]

    return render_template('pyq.html', 
                           questions=question_list,
                           companies=companies,
                           years=years,
                           categories=categories,
                           difficulties=difficulties)

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'user' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    # Fetch distinct values for company and category from Firestore
    companies = list(set([q.to_dict()['company'] for q in db.collection("questions").stream()]))
    categories = list(set([q.to_dict()['category'] for q in db.collection("questions").stream()]))

    # Get filter parameters from the form (if any)
    company = request.form.get('company', '')
    category = request.form.get('category', '')

    # Initialize the questions list as empty
    question_list = []

    # If the form is submitted, get the filtered questions
    if company or category:
        query = db.collection("questions")

        if company:
            query = query.where("company", "==", company)
        if category:
            query = query.where("category", "==", category)

        questions = query.stream()
        question_list = [q.to_dict() for q in questions]
    

    # Return the template with the filtered questions
    return render_template('quiz.html',
                           questions=question_list,
                           companies=companies,
                           categories=categories)

from flask import session
from firebase_admin import firestore
@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    # Check if the user is logged in
    if 'user' not in session:
        flash("Please log in to submit the quiz.", "warning")
        return redirect(url_for("login"))

    form = request.form
    total = int(form.get("total_questions", 0))
    correct = 0
    incorrect_questions = []

    category = form.get("category")
    company = form.get("company")

    # Iterate over all the questions to calculate results
    for i in range(1, total + 1):
        question_text = form.get(f"question{i}")
        correct_answer = form.get(f"answer{i}")
        user_answer = form.get(f"q{i}")

        # Check if the answer is correct
        is_correct = user_answer == correct_answer

        if is_correct:
            correct += 1
        else:
            incorrect_questions.append({
                "question": question_text,
                "your_answer": user_answer,
                "correct_answer": correct_answer
            })

    # Calculate accuracy
    accuracy = round((correct / total) * 100, 2)
    user_email = session['user']

    # Save quiz attempt to Firestore
    stats_ref = db.collection("user_stats").document(user_email).collection("attempts").document(f"{company}_{category}")
    stats_ref.set({
        "email": user_email,
        "company": company,
        "category": category,
        "total_questions": total,
        "correct_answers": correct,
        "accuracy": accuracy,
        "incorrect_questions": incorrect_questions,
    })

    # Update user's quiz statistics in "users" collection
    user_ref = db.collection("users").document(user_email)
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        prev_attempts = user_data.get("total_attempted_quizzes", 0)
        prev_accuracy_total = user_data.get("total_accuracy", 0.0)

        new_attempts = prev_attempts + 1
        new_avg_accuracy = round(((prev_accuracy_total * prev_attempts) + accuracy) / new_attempts, 2)

        user_ref.update({
            "total_attempted_quizzes": new_attempts,
            "total_accuracy": new_avg_accuracy
        })

    # Prepare the results to show in the template
    results = {
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "incorrect_questions": incorrect_questions,
        "category": category,
        "company": company
    }

    return render_template("quiz_result.html", **results)


@app.route("/generate_questions", methods=["GET", "POST"])
def generate_questions():
    if 'user' not in session:
        flash("Please log in to submit the quiz.", "warning")
        return redirect(url_for("login"))
    questions_output = None  # Initialize

    companies = list(set([q.to_dict().get('company', '') for q in db.collection("questions").stream()]))
    categories = list(set([q.to_dict().get('category', '') for q in db.collection("questions").stream()]))

    if request.method == "POST":
        mode = request.form.get("mode")
        user_email = session.get("user")
        prompt = ""

        if mode == "Company Wise":
            company = request.form.get("company")
            prompt = f"Generate a list of aptitude and technical questions commonly asked by {company} during their placement process. For each question, provide the correct answer immediately after it in the following format:\n\nque1 - [Question]\nans1 - [Answer]\nque2 - [Question]\nans2 - [Answer]"

        elif mode == "Category Wise":
            category = request.form.get("category")
            prompt = f"Generate placement-level questions from the '{category}' category. For each question, provide the correct answer immediately after it in the following format:\n\nque1 - [Question]\nans1 - [Answer]\nque2 - [Question]\nans2 - [Answer]"

        elif mode == "Based on Incorrect Questions":
            user_doc = db.collection("user_stats").document(user_email).collection("attempts").stream()
            past_incorrect = []
            for attempt in user_doc:
                data = attempt.to_dict()
                past_incorrect += data.get("incorrect_questions", [])
            incorrect_texts = "\n".join([q['question'] for q in past_incorrect[:5]])
            prompt = f"Based on the following incorrect questions from past attempts:\n{incorrect_texts}\n\nGenerate similar aptitude and technical questions. For each question, provide the correct answer immediately after it in the following format:\n\nque1 - [Question]\nans1 - [Answer]\nque2 - [Question]\nans2 - [Answer]"

        elif mode == "By Difficulty Level":
            difficulty = request.form.get("difficulty")
            prompt = f"Generate {difficulty.lower()} level aptitude and technical questions. For each question, provide the correct answer immediately after it in the following format:\n\nque1 - [Question]\nans1 - [Answer]\nque2 - [Question]\nans2 - [Answer]"

        elif mode == "Custom Prompt":
            prompt = request.form.get("custom_prompt")

        else:
            flash("Invalid mode selected.", "danger")
            return redirect(url_for("generate_questions"))



        # Call LLM
        from groq import Groq
        client = Groq(api_key=api_key)

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True
        )

        output = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                output += chunk.choices[0].delta.content

        questions_output = output  # Set this for rendering on the same page

    return render_template(
        "generate_form.html",
        companies=companies,
        categories=categories,
        questions_output=questions_output
    )

@app.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    suggestions = ""
    updated_resume = ""

    if request.method == "POST":
        resume_file = request.files.get("resume")
        job_description = request.form.get("job_description")

        if not resume_file or not job_description:
            flash("Please upload both a resume and job description.", "warning")
            return render_template("upload_resume.html", suggestions=suggestions, updated_resume=updated_resume)

        # Save resume temporarily
        resume_path = os.path.join("static", "uploads", resume_file.filename)
        resume_file.save(resume_path)

        # Extract text from PDF
        try:
            reader = PdfReader(resume_path)
            resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            flash(f"Error reading PDF: {e}", "danger")
            return render_template("upload_resume.html", suggestions=suggestions, updated_resume=updated_resume)

        # Prompt for LLM in plain text
        prompt = f"""
You are a professional resume assistant.

Given the resume below:

--- Resume ---
{resume_text}

And the following job description:

--- Job Description ---
{job_description}

Provide two things:
1. Suggestions to improve this resume for the job.
2. A rewritten version of the resume optimized for the job.

Format your response **clearly as plain text** without using markdown symbols like ##, **, or backticks.

Use this format exactly:

Suggestions:
- ...

Improved Resume:
...
"""



        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a resume improvement assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            content = completion.choices[0].message.content

            # Simple string split based on headings
            if "Improved Resume:" in content:
                parts = content.split("Improved Resume:")
                suggestions = parts[0].replace("Suggestions:", "").strip()
                updated_resume = parts[1].strip()
            else:
                suggestions = content.strip()

        except Exception as e:
            flash(f"LLM Error: {e}", "danger")

    return render_template("upload_resume.html", suggestions=suggestions, updated_resume=updated_resume)


# -----------------------------------------admins

@app.route("/admin/questions")


def admin_questions():
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    # Get the logged-in user's data
    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    # Fetch questions
    questions_ref = db.collection("questions")
    questions = [doc.to_dict() | {"id": doc.id} for doc in questions_ref.stream()]

    return render_template("admin_questions.html", questions=questions, user=user_data)


@app.route("/admin/edit_question/<question_id>", methods=["GET", "POST"])
def edit_question(question_id):
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    # Get the logged-in user's data
    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    question_ref = db.collection("questions").document(question_id)
    question = question_ref.get()
    if not question.exists:
        flash("Question not found.", "danger")
        return redirect(url_for("admin_questions"))

    if request.method == "POST":
        updated_data = {
            "company": request.form["company"].strip().lower(),
            "question_text": request.form["question_text"],
            "options": [
                request.form["optionA"],
                request.form["optionB"],
                request.form["optionC"],
                request.form["optionD"]
            ],
            "answer": request.form["answer"],
            "explanation": request.form["explanation"],
            "category": request.form["category"],
            "topic": request.form["topic"],
            "difficulty": request.form["difficulty"],
            "year": request.form["year"]
        }
        try:
            question_ref.update(updated_data)
            flash("Question updated successfully!", "success")
            return redirect(url_for("admin_questions"))
        except Exception as e:
            flash(f"Error updating question: {e}", "danger")

    question_data = question.to_dict()
    return render_template("admin_edit_question.html", question=question_data, question_id=question_id,user=user_data)

@app.route("/admin/delete_question/<question_id>", methods=["POST"])
def delete_question(question_id):
    try:
        db.collection("questions").document(question_id).delete()
        flash("Question deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting question: {e}", "danger")
    return redirect(url_for("admin_questions"))

@app.route("/admin/add_question", methods=["GET", "POST"])
def add_question():
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    # Get the logged-in user's data
    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    if request.method == "POST":
        try:
            question_data = {
                "company": request.form["company"].strip().lower(),
                "question_text": request.form["question_text"],
                "options": [
                    request.form["optionA"],
                    request.form["optionB"],
                    request.form["optionC"],
                    request.form["optionD"]
                ],
                "answer": request.form["answer"],
                "explanation": request.form["explanation"],
                "category": request.form["category"],
                "topic": request.form["topic"],
                "difficulty": request.form["difficulty"],
                "year": request.form["year"]
            }
            db.collection("questions").add(question_data)
            flash("Question added successfully!", "success")
            return redirect(url_for("admin_questions"))
        except Exception as e:
            flash(f"Error adding question: {e}", "danger")

    return render_template("admin_add_question.html", user=user_data)


@app.route("/admin/upload_pdf", methods=["GET", "POST"])
def upload_pdf():
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    # Get the logged-in user's data
    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    if request.method == "POST":
        pdf_file = request.files["pdf"]
        if not pdf_file:
            flash("Please upload a PDF.", "warning")
            return redirect(request.url)

        # Save PDF temporarily
        temp_path = os.path.join("static", "uploads", pdf_file.filename)
        pdf_file.save(temp_path)

        # Extract text from PDF
        reader = PdfReader(temp_path)
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        companynames = request.form.get("company", "").strip().lower()
        if not companynames:
            flash("Please provide a company name.", "warning")
            return redirect(request.url)

        # Define prompt for Groq LLM
        system_prompt = f"""
You are a question extractor and generator. For each quiz question, ensure the following:
1. Generate plausible options if missing. 
2. If fields like company, category, topic, difficulty, and year are missing, use:
   - company: "{companynames}" 
   - category: technical / aptitude or based on the question type)
   - topic: specific based on the question type
   - difficulty: "Easy" or "Medium" or "Hard" based on the question type
   - year: "2023" or current year based on the question type
3. Ensure the output is only a JSON array. No explanation or wrapping text.
4. remember you are making questions for cse students so here technial question means coding questions and aptitude means reasoning and maths questions.
Example:
[
    {{
        "company": "{companynames}",
        "question_text": "What is the time complexity of binary search?",
        "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"],
        "answer": "O(log n",
        "explanation": "Binary search divides the array in half each time.",
        "category": "Technical",
        "topic": "Algorithms",
        "difficulty": "Medium",
        "year": "2022"
    }}
]
Only return the JSON array.
"""



        try:
            # Request structured data from Groq
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_text}
                ]
            )

            content = completion.choices[0].message.content
            print("Raw Response:", content)  # Log raw JSON output
            parsed_json = json.loads(content)

            # Show parsed JSON directly in the review page
            session["parsed_questions"] = parsed_json
            return render_template("review_questions.html", questions=parsed_json,user=user_data)

        except Exception as e:
            flash(f"Error parsing LLM response: {e}", "danger")
            return redirect(url_for("upload_pdf"))

    return render_template("upload_pdf.html", user=user_data)



@app.route("/admin/save_questions", methods=["POST"])
def save_questions():
    questions = session.get("parsed_questions", [])
    if not questions:
        flash("No questions to save.", "warning")
        return redirect(url_for("upload_pdf"))

    # Save to Firebase Firestore
    for q in questions:
        db.collection("questions").add(q) 

    flash(f"{len(questions)} questions saved to Firestore.", "success")
    session.pop("parsed_questions", None) 
    return redirect(url_for("upload_pdf"))

@app.route("/admin/save_edited_questions", methods=["POST"])
def save_edited_questions():
    edited_data = request.form.to_dict(flat=False)

    # Reconstruct list of question dicts
    questions = []
    idx = 0
    while f"questions[{idx}][question_text]" in request.form:
        question = {
            "company": request.form.get(f"questions[{idx}][company]"),
            "question_text": request.form.get(f"questions[{idx}][question_text]"),
            "options": [
                request.form.get(f"questions[{idx}][options][0]"),
                request.form.get(f"questions[{idx}][options][1]"),
                request.form.get(f"questions[{idx}][options][2]"),
                request.form.get(f"questions[{idx}][options][3]"),
            ],
            "answer": request.form.get(f"questions[{idx}][answer]"),
            "explanation": request.form.get(f"questions[{idx}][explanation]"),
            "category": request.form.get(f"questions[{idx}][category]"),
            "topic": request.form.get(f"questions[{idx}][topic]"),
            "difficulty": request.form.get(f"questions[{idx}][difficulty]"),
            "year": request.form.get(f"questions[{idx}][year]"),
        }
        questions.append(question)
        idx += 1

    # Save to Firestore
    for q in questions:
        db.collection("questions").add(q)

    flash(f"{len(questions)} questions saved to Firebase.", "success")
    return redirect(url_for("upload_pdf"))

@app.route('/admin')
def admin():
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    total_users = 0
    total_quizzes_attempted = 0
    all_users = []
    try:
        users = db.collection('users').stream()
        for user in users:
            data = user.to_dict()
            total_users += 1
            total_quizzes_attempted += data.get('total_attempted_quizzes', 0)

            if data.get('total_attempted_quizzes', 0) > 0:
                all_users.append({
                    'full_name': data.get('full_name', 'N/A'),
                    'email': data.get('email', ''),
                    'accuracy': data.get('total_accuracy', 0.0),
                    'profile_image_url': data.get('profile_image_url', '')
                })

        # Sort by accuracy descending and pick top 5
        top_users = sorted(all_users, key=lambda x: x['accuracy'], reverse=True)[:5]
    except Exception as e:
        flash(f'Error fetching user stats: {str(e)}', 'warning')
        top_users = []

    total_questions = 0
    categories_set = set()
    try:
        questions = db.collection('questions').stream()
        for q in questions:
            total_questions += 1
            q_data = q.to_dict()
            category = q_data.get("category")
            if category:
                categories_set.add(category.lower())
    except Exception as e:
        flash(f'Error fetching question stats: {str(e)}', 'warning')

    return render_template(
        'admin.html',
        user=user_data,
        total_users=total_users,
        total_quizzes_attempted=total_quizzes_attempted,
        total_questions=total_questions,
        total_categories=len(categories_set),
        top_users=top_users
    )

@app.route('/admin/users')
def list_users():
    # Check if user is logged in
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']

    try:
        # Fetch the current user document
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))

        user_data = user_doc.to_dict()

        # Verify admin access
        if not user_data.get('is_admin', False):
            flash('Unauthorized access. Admins only.', 'danger')
            return redirect(url_for('login'))

        # Ensure session reflects admin status
        session['is_admin'] = True

        # Fetch all users
        users_ref = db.collection('users').stream()
        users = [{**doc.to_dict(), 'email': doc.id} for doc in users_ref]

        return render_template('list_users.html', userslist=users, user=user_data)

    except Exception as e:
        flash(f'Error verifying admin or loading users: {str(e)}', 'danger')
        return redirect(url_for('login'))


@app.route('/admin/users/edit/<email>', methods=['GET', 'POST'])
def edit_user(email):
    if not session.get('user'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if not session.get('is_admin'):
        user_email = session['user']
        try:
            user_doc = db.collection('users').document(user_email).get()
            if not user_doc.exists:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))

            user_data = user_doc.to_dict()
            if not user_data.get('is_admin', False):
                flash('Unauthorized access. Admins only.', 'danger')
                return redirect(url_for('login'))

            session['is_admin'] = True
        except Exception as e:
            flash(f'Error verifying admin status: {str(e)}', 'danger')
            return redirect(url_for('login'))

    user_email = session['user']
    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    user_ref = db.collection('users').document(email)
    if request.method == 'POST':
        updated_data = {
            'full_name': request.form['full_name'],
            'college_name': request.form['college_name'],
            'degree': request.form['degree'],
            'branch': request.form['branch'],
            'year_of_graduation': int(request.form['year_of_graduation']),
            'profile_image_url': request.form['profile_image_url'],
            'total_attempted_quizzes': int(request.form['total_attempted_quizzes']),
            'total_accuracy': float(request.form['total_accuracy']),
            'is_admin': request.form.get('is_admin') == 'on'
        }
        user_ref.update(updated_data)
        flash('User updated successfully!', 'success')
        return redirect(url_for('list_users'))

    userdata = user_ref.get().to_dict()
    return render_template('edit_user.html', userdata=userdata,user=user_data)

from firebase_admin import auth

@app.route('/admin/users/delete/<email>', methods=['POST'])
def delete_user(email):
    try:
        # 1. Delete user from 'users' collection
        db.collection('users').document(email).delete()

        # 2. Delete all attempt stats under 'user_stats/{email}/attempts/*'
        stats_attempts_ref = db.collection('user_stats').document(email).collection('attempts')
        attempts = stats_attempts_ref.stream()
        for doc in attempts:
            doc.reference.delete()

        # Optionally delete the 'user_stats/{email}' document too (if exists)
        db.collection('user_stats').document(email).delete()

        # 3. Delete from Firebase Authentication
        user_record = auth.get_user_by_email(email)
        auth.delete_user(user_record.uid)

        flash(f'User {email} and all associated data deleted.', 'success')

    except auth.UserNotFoundError:
        flash(f'User {email} not found in Authentication, but Firestore data deleted.', 'warning')
    except Exception as e:
        flash(f'Error deleting user {email}: {e}', 'error')

    return redirect(url_for('list_users'))


if __name__ == '__main__':
    app.run(debug=True)
