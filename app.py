from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from escpos.printer import Usb, Dummy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    organization = db.Column(db.String(120), nullable=False)
    qr_code = db.Column(db.LargeBinary, nullable=False)

# Initialize the database
with app.app_context():
    db.create_all()

# Initialize USB printer
try:
    printer = Usb(0x04b8, 0x0e03)
except Exception as e:
    printer = Dummy()
    print(f"Failed to initialize USB printer: {e}")

@app.route('/')
def index():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    organization = request.form['organization']

    # Generate QR code
    qr_data = f"Name: {name}, Email: {email}, Phone: {phone}, Organization: {organization}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    # Add the name to the QR code image
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    font_path = font_path = 'path_to_your_font_file.ttf'
    font = ImageFont.truetype(font_path, 20)
    bbox = draw.textbbox((0, 0), name, font=font)
   # Calculate the width and height of the text
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    image_width, image_height = img.size
    x = (image_width - text_width) // 2
    y = 10  # 10 pixels from the top
    draw.text((x, y), name, fill="black", font=font)

    # Save QR code to bytes
    buf = BytesIO()
    img.save(buf, format='PNG')
    qr_code_bytes = buf.getvalue()

    # Store registration data in the database
    registration = Registration(
        name=name,
        email=email,
        phone=phone,
        organization=organization,
        qr_code=qr_code_bytes
    )
    db.session.add(registration)
    db.session.commit()

    # Ensure the directory exists
    qr_code_dir = os.path.join(app.static_folder, 'qr_codes')
    if not os.path.exists(qr_code_dir):
        os.makedirs(qr_code_dir)

    # Save the QR code to a file
    qr_code_path = os.path.join(qr_code_dir, f'{registration.id}.png')
    img.save(qr_code_path)

    # Print the QR code
    buf.seek(0)
    try:
        if isinstance(printer, Usb):
            printer.image(buf)
            printer.cut()
    except Exception as e:
        return str(e), 500

    return render_template('success.html', qr_code_url=url_for('static', filename=f'qr_codes/{registration.id}.png'))

@app.route('/qr/<int:registration_id>')
def qr_code(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    buf = BytesIO(registration.qr_code)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name='qr_code.png')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
