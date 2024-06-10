from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import datetime
from mysql.connector import Error
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateField, TimeField, SelectField
from wtforms.validators import InputRequired, Length, ValidationError
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'aa8f7ba37f44c78d74bf50f82b337452'

# MySQL configurations
mysql_config = {
    'host': 'localhost',
    'database': 'lecture_hall_booking',
    'user': 'root',
    'password': '112003'
}


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=150)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=150)])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=150)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=150)])

class BookingForm(FlaskForm):
    hall_id = SelectField('Lecture Hall', coerce=int, validators=[InputRequired()])
    date = DateField('Date', format='%Y-%m-%d', validators=[InputRequired()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[InputRequired()])
    end_time = TimeField('End Time', format='%H:%M', validators=[InputRequired()])

    def validate_end_time(form, field):
        if field.data <= form.start_time.data:
            raise ValidationError('End time must be after start time.')

class TimetableForm(FlaskForm):
    hall_id = SelectField('Lecture Hall', coerce=int, validators=[InputRequired()])
    day_of_week = SelectField('Day of Week', choices=[
        ('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday')
    ], validators=[InputRequired()])
    date = DateField('Date', format='%Y-%m-%d', validators=[InputRequired()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[InputRequired()])
    end_time = TimeField('End Time', format='%H:%M', validators=[InputRequired()])
    course_name = StringField('Course Name', validators=[InputRequired(), Length(max=100)])

    def validate_end_time(form, field):
        if field.data <= form.start_time.data:
            raise ValidationError('End time must be after start time.')
    

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        login_type = request.form['login_type']
        
        try:
            connection = mysql.connector.connect(**mysql_config)
            cursor = connection.cursor()
            if login_type == 'admin':
                cursor.execute("SELECT * FROM admin WHERE username=%s", (username,))
            elif login_type == 'teacher':
                cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            cursor.close()
            if user and user[2] == password:
                if login_type == 'admin':
                    session['admin_id'] = user[0]
                    return redirect(url_for('admin_dashboard'))
                elif login_type == 'teacher':
                    session['user_id'] = user[0]
                    return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials')
        except Error as e:
            flash('Database error: ' + str(e))
        finally:
            if connection.is_connected():
                connection.close()
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm()
    connection = None
    try:
        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data
            hashed_password = password
            connection = mysql.connector.connect(**mysql_config)
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users(username, password) VALUES(%s, %s)", (username, hashed_password))
            connection.commit()
            cursor.close()
            return redirect(url_for('login'))
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection and connection.is_connected():
            connection.close()
    return render_template('signup.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM lecture_halls")
        halls = cursor.fetchall()

        lecture_halls = []
        for hall in halls:
            cursor.execute("""
                SELECT bookings.date, bookings.start_time, bookings.end_time, users.username 
                FROM bookings 
                JOIN users ON bookings.user_id = users.id 
                WHERE bookings.hall_id=%s
            """, (hall[0],))
            bookings = cursor.fetchall()
            formatted_bookings = []
            for booking in bookings:
                start_time = datetime.strptime(str(booking[1]), '%H:%M:%S').strftime('%I:%M %p')
                end_time = datetime.strptime(str(booking[2]), '%H:%M:%S').strftime('%I:%M %p')
                formatted_bookings.append({
                    'date': booking[0],
                    'start_time': start_time,
                    'end_time': end_time,
                    'username': booking[3]
                })
            lecture_halls.append({
                'name': hall[1],
                'bookings': formatted_bookings
            })

        cursor.execute("""
            SELECT bookings.id, lecture_halls.hall_name, bookings.date, bookings.start_time, bookings.end_time 
            FROM bookings 
            INNER JOIN lecture_halls ON bookings.hall_id = lecture_halls.id 
            WHERE bookings.user_id=%s
        """, (session['user_id'],))
        user_bookings = cursor.fetchall()

        formatted_user_bookings = []
        for booking in user_bookings:
            start_time = datetime.strptime(str(booking[3]), '%H:%M:%S').strftime('%I:%M %p')
            end_time = datetime.strptime(str(booking[4]), '%H:%M:%S').strftime('%I:%M %p')
            formatted_user_bookings.append({
                'id': booking[0],
                'hall_name': booking[1],
                'date': booking[2],
                'start_time': start_time,
                'end_time': end_time
            })

        return render_template('dashboard.html', halls=lecture_halls, user_bookings=formatted_user_bookings)
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('dashboard.html', halls=[], user_bookings=[])

@app.route('/view_all_timetable_entries')
def view_all_timetable_entries():
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT id, hall_id, day_of_week, date, start_time, end_time, course_name FROM timetable")
        timetable_entries = cursor.fetchall()

        for entry in timetable_entries:
            if 'date' in entry:
                entry['date'] = entry['date'].strftime('%Y-%m-%d')

        timetable_entries.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))

        return render_template('all_timetable_entries.html', timetable_entries=timetable_entries)
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('all_timetable_entries.html', timetable_entries=[])



# admin_dashboard route
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor(dictionary=True)

        # Fetch bookings
        cursor.execute("SELECT * FROM lecture_halls")
        halls = cursor.fetchall()

        lecture_halls = []
        for hall in halls:
            cursor.execute("""
                SELECT bookings.id, bookings.date, bookings.start_time, bookings.end_time, users.username 
                FROM bookings 
                JOIN users ON bookings.user_id = users.id 
                WHERE bookings.hall_id=%s
            """, (hall['id'],))
            bookings = cursor.fetchall()
            formatted_bookings = []
            for booking in bookings:
                start_time = datetime.strptime(str(booking['start_time']), '%H:%M:%S').strftime('%I:%M %p')
                end_time = datetime.strptime(str(booking['end_time']), '%H:%M:%S').strftime('%I:%M %p')
                formatted_bookings.append({
                    'id': booking['id'],
                    'date': booking['date'],
                    'start_time': start_time,
                    'end_time': end_time,
                    'username': booking['username']
                })
            lecture_halls.append({
                'name': hall['hall_name'],
                'bookings': formatted_bookings
            })

        # Fetch timetable entries
        cursor.execute("SELECT * FROM timetable")
        timetable_entries = cursor.fetchall()

        return render_template('admin_dashboard.html', bookings=lecture_halls, timetable=timetable_entries)
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('admin_dashboard.html', bookings=[], timetable=[])

@app.route('/delete_booking/<int:booking_id>', methods=['POST', 'DELETE'])
def delete_booking(booking_id):
    if 'user_id' in session:
        try:
            connection = mysql.connector.connect(**mysql_config)
            cursor = connection.cursor()

            cursor.execute("SELECT user_id FROM bookings WHERE id=%s", (booking_id,))
            booking = cursor.fetchone()
            if not booking:
                flash('Booking not found!')
                return redirect(url_for('dashboard'))
            elif booking[0] != session['user_id']:
                flash('You are not authorized to delete this booking!')
                return redirect(url_for('dashboard'))
            
            cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
            connection.commit()
            flash('Booking deleted successfully!')
        except Error as e:
            flash('Database error: ' + str(e))
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
        
        return redirect(url_for('dashboard'))
    elif 'admin_id' in session:
        try:
            connection = mysql.connector.connect(**mysql_config)
            cursor = connection.cursor()

            cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
            connection.commit()
            flash('Booking deleted successfully!')
        except Error as e:
            flash('Database error: ' + str(e))
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
        
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('login'))

from flask import request

@app.route('/delete_timetable_entry/<int:entry_id>', methods=['POST', 'DELETE'])
def delete_timetable_entry(entry_id):
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()

        cursor.execute("DELETE FROM timetable WHERE id = %s", (entry_id,))
        connection.commit()
        flash('Timetable entry deleted successfully!')
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('view_all_timetable_entries'))
   

@app.route('/book', methods=['GET', 'POST'])
def book():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    form = BookingForm()
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        cursor.execute("SELECT id, hall_name FROM lecture_halls")
        halls = cursor.fetchall()
        form.hall_id.choices = [(h[0], h[1]) for h in halls]

        if form.validate_on_submit():
            hall_id = form.hall_id.data
            date = form.date.data
            start_time = form.start_time.data
            end_time = form.end_time.data

            if date < datetime.now().date():
                flash('Cannot book a hall for a past date!')
            else:
                day_of_week = date.strftime('%A')
                cursor.execute("""
                    SELECT * FROM timetable 
                    WHERE hall_id = %s AND day_of_week = %s 
                    AND ((start_time <= %s AND end_time >= %s) OR (start_time <= %s AND end_time >= %s))
                """, (hall_id, day_of_week, end_time, end_time, start_time, start_time))
                conflict = cursor.fetchone()
                
                while cursor.nextset():
                    pass  # Clear any remaining results

                if conflict:
                    flash('Booking conflicts with an existing timetable entry!')
                else:
                    cursor.execute("""
                        INSERT INTO bookings (user_id, hall_id, date, start_time, end_time) 
                        VALUES (%s, %s, %s, %s, %s)
                    """, (session['user_id'], hall_id, date, start_time, end_time))
                    connection.commit()
                    flash('Booking successful!')
                    return redirect(url_for('dashboard'))
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    
    return render_template('book.html', form=form)

@app.route('/timetable', methods=['GET', 'POST'])
def timetable():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    form = TimetableForm()
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        cursor.execute("SELECT id, hall_name FROM lecture_halls")
        halls = cursor.fetchall()
        form.hall_id.choices = [(h[0], h[1]) for h in halls]

        if form.validate_on_submit():
            hall_id = form.hall_id.data
            day_of_week = form.day_of_week.data
            start_time = form.start_time.data
            end_time = form.end_time.data
            course_name = form.course_name.data

            while cursor.nextset():
                pass

            cursor.execute("""
                INSERT INTO timetable (hall_id, day_of_week, date, start_time, end_time, course_name) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (hall_id, day_of_week, form.date.data, start_time, end_time, course_name))
            connection.commit()
            flash('Timetable entry added successfully!')
            return redirect(url_for('admin_dashboard'))
    except Error as e:
        flash('Database error: ' + str(e))
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('timetable.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('admin_id', None)
    return redirect(url_for('login'))

def delete_expired_bookings():
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        current_time = datetime.now()
        cursor.execute("DELETE FROM bookings WHERE date < %s OR (date = %s AND end_time < %s)",
                       (current_time.date(), current_time.date(), current_time.time()))
        connection.commit()
        cursor.close()
        connection.close()
    except Error as e:
        print(f'Error deleting expired bookings: {e}')

scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_expired_bookings, trigger="interval", minutes=1)
scheduler.start()

import atexit
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(debug=True)
