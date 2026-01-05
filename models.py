from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from flask_login import UserMixin, LoginManager
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan_type = db.Column(db.String(20), default='trial') 
    credits = db.Column(db.Integer, default=5)
    last_post_date = db.Column(db.Date, nullable=True)

    def get_reset_token(self):
        # O Serializer recebe apenas a chave secreta aqui
        s = Serializer(current_app.config['SECRET_KEY'])
        # O token gerado já é uma string, não precisa de .decode('utf-8') nas versões novas
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            # max_age define quanto tempo o token é válido
            data = s.loads(token, max_age=expires_sec)
            user_id = data['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    # Relação com Blog
    sites = db.relationship('Blog', backref='owner', lazy=True)

    def get_plan_limits(self):
        planos = {
            'trial': {'max_sites': 1, 'posts_por_dia': 1},
            'pro':   {'max_sites': 2, 'posts_por_dia': 5},
            'vip':   {'max_sites': 999, 'posts_por_dia': 999}
        }
        return planos.get(self.plan_type, planos['trial'])

    # --- MÉTODO RESTAURADO AQUI ---
    def can_add_site(self):
        """Verifica se o utilizador pode adicionar mais um site baseado no seu plano."""
        limite = self.get_plan_limits()['max_sites']
        return len(self.sites) < limite
    
    # No seu arquivo models.py, dentro da classe User
    def is_setup_complete(self):
        """Verifica se o usuário tem pelo menos um site e se esse site tem prompt definido."""
        if not self.sites:
            return False
        # Verifica se o primeiro site já tem as configurações básicas
        primeiro_site = self.sites[0]
        return bool(primeiro_site.wp_url and primeiro_site.master_prompt)
    
    # No models.py, dentro da classe User
    def get_setup_status(self):
        """
        Retorna o status do onboarding do utilizador para controlar o acesso às ferramentas.
        """
        if not self.sites:
            return 'no_site'
        
        # Pega o primeiro site para validar as configurações básicas
        site = self.sites[0]
        if not site.master_prompt or not site.macro_themes:
            return 'no_config'
            
        return 'complete'
    
    def pode_postar_automatico(self):
        """
        Verifica se o usuário tem tudo o que precisa para o sistema rodar sozinho.
        """
        # 1. Verifica se o setup está completo (Site + IA)
        if self.get_setup_status() != 'complete':
            return False
            
        # 2. Verifica se o usuário tem créditos (se o seu sistema usa créditos)
        if self.credits is not None and self.credits <= 0:
            return False
            
        return True
    
    def pode_postar_hoje(self):
        """
        Verifica se o usuário Trial já postou hoje.
        """
        if self.plan_type == 'trial':
            hoje = date.today()
            if self.last_post_date == hoje:
                return False
        
        # Para planos VIP, a trava pode ser apenas o saldo de créditos
        return self.credits > 0

    def deduct_credit(self, amount=1):
        """
        Dedução segura de créditos.
        Retorna True se a dedução for bem-sucedida, False caso contrário.
        A função chamadora é responsável pelo db.session.commit().
        """
        if self.credits < amount:
            return False
        self.credits -= amount
        return True

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    site_name = db.Column(db.String(100), nullable=False)
    wp_url = db.Column(db.String(200), nullable=False)
    wp_user = db.Column(db.String(100), nullable=False)
    wp_app_password = db.Column(db.String(100), nullable=False)
    
    master_prompt = db.Column(db.Text)
    macro_themes = db.Column(db.Text)
    post_status = db.Column(db.String(20), default='publish')
    frequency_hours = db.Column(db.Integer, default=24)
    posts_per_day = db.Column(db.Integer, default=1)
    schedule_time = db.Column(db.String(5), default="08:00")
    default_category = db.Column(db.Integer)
    
    # Cascade para deleção segura
    ideas = db.relationship('ContentIdea', backref='blog', lazy=True, cascade="all, delete-orphan")
    logs = db.relationship('PostLog', backref='blog', lazy=True, cascade="all, delete-orphan")
    sources = db.relationship('ContentSource', backref='blog', lazy=True, cascade="all, delete-orphan")

class ContentIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_posted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PostLog(db.Model):
    __tablename__ = 'post_log'
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    wp_post_id = db.Column(db.Integer)
    post_url = db.Column(db.String(500))
    status = db.Column(db.String(20))
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContentSource(db.Model):
    __tablename__ = 'content_source'
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)
    source_name = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_scraped = db.Column(db.DateTime, nullable=True)

class CapturedContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('content_source.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(200))
    content_summary = db.Column(db.Text)
    original_url = db.Column(db.String(500))
    is_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)