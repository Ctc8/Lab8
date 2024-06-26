from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user, LoginManager, UserMixin, login_required, current_user, logout_user
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from flask_wtf import FlaskForm
from wtforms import IntegerField, SubmitField
from wtforms.validators import NumberRange

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///db.sqlite3"
app.config['SECRET_KEY'] = "secretkey"
app.config['LOGIN_VIEW'] = 'login'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

user_courses = db.Table('user_courses',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

class GradeForm(FlaskForm):
    grade = IntegerField('Grade', validators=[NumberRange(min=0, max=100)])
    submit = SubmitField('Update Grade')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    students = db.relationship('User', secondary=user_courses, backref=db.backref('courses', lazy='dynamic'))

class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(30), unique=True) 
  password = db.Column(db.String(30))  
  
  is_admin = db.Column(db.Boolean, default=False)

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    grade = db.Column(db.Integer, nullable=False)
    course = db.relationship('Course', backref=db.backref('grades', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('grades', cascade='all, delete-orphan'))

with app.app_context():
    db.create_all()

class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

admin = Admin(app, name='Admin', template_mode='bootstrap3')
admin.add_view(AdminModelView(User, db.session))
admin.add_view(AdminModelView(Course, db.session))

@app.route('/')
def home():
  return render_template('login.html', user=current_user)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin.index'))
    
    all_courses = Course.query.all()
    available_courses_info = [{
        'id': course.id,
        'name': course.name,
        'teacher': course.teacher,
        'time': course.time,
        'student_count': len(course.students),
        'capacity': course.capacity
    } for course in all_courses if course not in current_user.courses]

    enrolled_courses_info = [{
        'id': course.id,
        'name': course.name,
        'teacher': course.teacher,
        'time': course.time,
        'student_count': len(course.students),
        'capacity': course.capacity
    } for course in current_user.courses]
    
    return render_template('dashboard.html', user=current_user, 
                           available_courses=available_courses_info, 
                           courses_info=enrolled_courses_info)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user:
            error = 'Username is already taken'
            return render_template('signup.html', error=error)

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        return redirect(url_for('dashboard'))

    return render_template('signup.html')


@app.route('/teacherdashboard')
def teacherdashboard():
    if current_user.is_admin:
        return redirect(url_for('admin.index'))
    
    all_courses = Course.query.all()
    available_courses_info = [{
        'id': course.id,
        'name': course.name,
        'teacher': course.teacher,
        'time': course.time,
        'student_count': len(course.students),
        'capacity': course.capacity
    } for course in all_courses if course not in current_user.courses]

    teaching_courses_info = [{
        'id': course.id,
        'name': course.name,
        'teacher': course.teacher,
        'time': course.time,
        'student_count': len(course.students),
        'capacity': course.capacity
    } for course in all_courses if course.teacher == current_user.username]
    
    return render_template('teacherdashboard.html', user=current_user, 
                           available_courses=available_courses_info, 
                           courses_info=teaching_courses_info)


@app.route('/update_grade/<int:course_id>/<int:student_id>', methods=['POST'])
@login_required
def update_grade(course_id, student_id):
    grade_value = request.form.get('grade')
    course = Course.query.get(course_id)
    student = User.query.get(student_id)
    if course is None or student is None:
        abort(404)
    
    grade = Grade.query.filter_by(course_id=course_id, user_id=student_id).first()
    if grade:
        grade.grade = grade_value
    else:
        grade = Grade(course_id=course_id, user_id=student_id, grade=grade_value)
        db.session.add(grade)

    db.session.commit()
    flash('Grade updated successfully.')
    return redirect(url_for('course_students', course_id=course_id))

@app.route('/course_students/<int:course_id>')
@login_required
def course_students(course_id):
    course = Course.query.get(course_id)
    if course is None:
        abort(404)
    students = course.students
    grades = {student.id: Grade.query.filter_by(course_id=course_id, user_id=student.id).first() for student in students}
    return render_template('course_students.html', course=course, students=students, grades=grades, grade_form=GradeForm())

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
  error = None
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()    

    if user and user.password == password:  
      login_user(user)
      if username == 'ahepworth' or username == 'swalker' or username == 'rjenkins':
          return redirect(url_for('teacherdashboard'))
      else:
          return redirect(url_for('dashboard'))

    error = 'Invalid username or password'

  signup_url = url_for('signup')
  return render_template('login.html', error=error, signup_url=signup_url)

@app.route('/enroll_course/<int:course_id>', methods=['POST'])
@login_required
def enroll_course(course_id):
    course = Course.query.get(course_id)
    if course and not course in current_user.courses:
        if len(course.students) < course.capacity:
            current_user.courses.append(course)
            db.session.commit()
            flash('You have been enrolled in the course.', 'success')
        else:
            flash('This course is already at full capacity.', 'error')
    else:
        flash('Course not found or already enrolled.', 'error')
    return redirect(url_for('dashboard'))


@app.route('/drop_course/<int:course_id>', methods=['POST'])
@login_required
def drop_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course in current_user.courses:
        current_user.courses.remove(course)
        db.session.commit()
        flash('You have been dropped from the course successfully.', 'success')
    else:
        flash('You are not enrolled in this course.', 'error')
    return redirect(url_for('dashboard'))


if __name__ == "__main__":
  app.run(debug=True, port=5001)
  with app.app_context():
    ahepworth_user = User.query.filter_by(username='ahepworth').first()
    if ahepworth_user:
      ahepworth_user.is_admin = True
      db.session.commit()
  app.run(debug=True, port=5001)
