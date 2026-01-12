from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user

teste_bp = Blueprint('teste', __name__)

@teste_bp.route('/teste1')
@login_required
def teste1():
    return render_template('landing-old.html')