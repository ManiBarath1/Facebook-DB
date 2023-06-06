from flask import Flask,render_template,redirect,request,url_for,session,flash,get_flashed_messages
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import LargeBinary
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from flask_login import LoginManager,login_user,logout_user,login_required,UserMixin,current_user
from flask_wtf.file import FileField, FileAllowed
from io import BytesIO
from datetime import datetime
import base64
import os
from flask_migrate import Migrate

UPLOAD_FOLDER = 'static/images' 


app=Flask(__name__, static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///facebook.db'
# app.config['SECRET_KEY']='f8abea5114b0f71693920ec2'
app.secret_key='f8abea5114b0f71693920ec2'
db=SQLAlchemy(app)
migrate=Migrate(app,db)
bcrypt=Bcrypt(app)
login_manager=LoginManager(app)
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
app.app_context().push()

class User(db.Model,UserMixin):
    id=db.Column(db.Integer(),primary_key=True)
    username=db.Column(db.String(length=30),nullable=False,unique=True)
    email=db.Column(db.String(length=50),nullable=False,unique=True)
    password_hash=db.Column(db.String(length=60),nullable=False)
    # profile_image = db.Column(LargeBinary)
    profile_image = db.Column(db.String(length=255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # uploaded_files = db.relationship('UploadedFile', backref='user', lazy=True)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.set_password(password)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, attempted_password):
        return bcrypt.check_password_hash(self.password_hash, attempted_password)


    def __repr__(self):
        return f'{self.username}'
    
class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    data = db.Column(db.LargeBinary)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('uploaded_files', lazy=True))

def get_posts():
    posts = UploadedFile.query.all()
    return posts

   
class RegisterForm(FlaskForm):
    username = StringField('Enter User Name:', validators=[DataRequired()])
    email = StringField('Enter Email:', validators=[DataRequired(), Email()])
    password = PasswordField('Enter Password:', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password:', validators=[DataRequired(), EqualTo('password')])
    profile_image = FileField('Profile Image', validators=[FileAllowed(['jpg', 'jpeg', 'png','gif'])])
    submit = SubmitField('Register')

class UploadForm(FlaskForm):
    image = FileField('Upload Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Upload')

class LoginForm(FlaskForm):
    identifier = StringField(label="Username or Email", validators=[DataRequired()])
    password = PasswordField(label="Password:", validators=[DataRequired()])
    submit = SubmitField(label="Login")
    pass

@login_manager.user_loader
def load_user(user_id):
    # return db.session.get(User, int(user_id))
    return User.query.get(int(user_id))

@app.template_filter('b64encode')
def base64_encode(value):
    encoded_bytes = base64.b64encode(value)
    return encoded_bytes.decode('utf-8')

@app.route("/", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data
        attempted_user = User.query.filter(db.or_(User.username == identifier, User.email == identifier)).first()
        if attempted_user and attempted_user.check_password(form.password.data):
            login_user(attempted_user)
            flash("Successfully logged in")
            return redirect(url_for("home"))  # Redirect to the home page

        flash("Username/Email and password are not correct")

    return render_template("index.html", form=form)


@app.route("/register", methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        confirmpassword = form.confirm_password.data
        profile_image = form.profile_image.data

        if password != confirmpassword:
            return "Passwords do not match!"

        if profile_image:
           image_bytes = profile_image.read()
        else:
           image_bytes = None


        existing_user = User.query.filter(db.or_(User.username == username, User.email == email)).first()
        if existing_user:
            return "Username or email already exists!"

        new_user = User(username=username, email=email, profile_image=image_bytes)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route('/upload', methods=["POST", "GET"])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.image.data
        description = form.description.data

        if file and description:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            with open(file_path, 'rb') as f:
                file_data = f.read()

            uploaded_file = UploadedFile(filename=filename, description=description, user=current_user, data=file_data)
            db.session.add(uploaded_file)
            db.session.commit()

            flash("File uploaded and saved to the database")
            return redirect(url_for("home"))

    return render_template("upload.html", form=form)

@app.route("/home")
@login_required
def home():
    profile_image = current_user.profile_image
    posts=get_posts()
    posts.reverse()
    return render_template("home.html", current_user=current_user, profile_image=profile_image,posts=posts)

@app.route("/profile")
@login_required
def profile():
    profile_image = current_user.profile_image
    posts = UploadedFile.query.all()
    posts=get_posts()
    if posts:
        posts.reverse()
        post = posts[0]
    else:
        post = None
    return render_template("profile.html",current_user=current_user, profile_image=profile_image,posts=posts,post=post)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Successfully logged out", "success")
    return redirect(url_for("login"))

if __name__=="__main__":
    app.run(debug=True)