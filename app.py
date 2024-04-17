from flask import Flask, render_template, request,redirect,url_for



app = Flask(__name__)

@app.route('/')
def home():
    """This is the home route"""
    return render_template('login_signup.html')

@app.route('/generate_qr')
def generate_qr():
    """This is used to generate qr"""


@app.route('/validate_qr')
def validate_qr():
    """validation"""


if __name__=='__main__':
    app.run(debug=True)
