from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager

db = SQLAlchemy()
login_manager = LoginManager() # Instância necessária para o app.py

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan_type = db.Column(db.String(20), default='trial') 
    sites = db.relationship('Blog', backref='owner', lazy=True)
    credits = db.Column(db.Integer, default=5)  # <-- ESSA LINHA É A QUE FALTA

    def get_limits(self):
        # Centralizamos as regras de negócio aqui
        limites = {
            'trial': {'sites': 1, 'posts_dia': 1, 'creditos_iniciais': 1},
            'pro':   {'sites': 2, 'posts_dia': 5, 'creditos_iniciais': 30},
            'vip':   {'sites': 10, 'posts_dia': 50, 'creditos_iniciais': 500}
        }
        return limites.get(self.plan_type, limites['trial'])

    def can_add_site(self):
        site_count = len(self.sites)
        limits = {'trial': 1, 'pro': 2, 'vip': 10}
        return site_count < limits.get(self.plan_type, 1)
        
    def pode_postar_automatico(self):
        # 1. Verifica saldo de créditos total
        if self.credits <= 0:
            return False
            
        # 2. Verifica se já atingiu o limite do plano HOJE
        limite_diario = self.get_limits()['posts_dia']
        
        hoje = datetime.utcnow().date()
        # Conta quantos logs de sucesso existem hoje para este usuário
        posts_feitos_hoje = PostLog.query.join(Blog).filter(
            Blog.user_id == self.id,
            db.func.date(PostLog.posted_at) == hoje
        ).count()
    
        return posts_feitos_hoje < limite_diario

# ESSA FUNÇÃO É VITAL PARA O LOGIN FUNCIONAR
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    site_name = db.Column(db.String(100), nullable=False)
    wp_url = db.Column(db.String(200), nullable=False)
    wp_user = db.Column(db.String(100), nullable=False)
    wp_app_password = db.Column(db.String(100), nullable=False)
    master_prompt = db.Column(db.Text, nullable=True)
    macro_themes = db.Column(db.String(500), nullable=True) 
    post_status = db.Column(db.String(20), default='publish') 
    frequency_hours = db.Column(db.Integer, default=24)
    tracked_channels = db.Column(db.Text, nullable=True)
    ideas = db.relationship('ContentIdea', backref='blog', lazy=True)
    logs = db.relationship('PostLog', backref='blog', lazy=True)
    # NOVAS COLUNAS:
    posts_per_day = db.Column(db.Integer, default=1)
    schedule_time = db.Column(db.String(5), default="08:00") # Armazena como "HH:MM"
    post_status = db.Column(db.String(20), default="draft")  # 'draft' ou 'publish'
    default_category = db.Column(db.String(100))

class ContentIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_posted = db.Column(db.Boolean, default=False)

class PostLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    content = db.Column(db.Text, nullable=False)
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
    blog = db.relationship('Blog', backref=db.backref('sources', lazy=True))  

class CapturedContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Link com a fonte (Radar)
    source_id = db.Column(db.Integer, db.ForeignKey('content_source.id'))
    # Link direto com o Blog (para facilitar a consulta na geração de ideias)
    site_id = db.Column(db.Integer, db.ForeignKey('blog.id')) 
    url = db.Column(db.String(500))
    title = db.Column(db.String(500))
    summary = db.Column(db.Text)  # O "suco" para a IA
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos para facilitar buscas
    source = db.relationship('ContentSource', backref='captures')
    site = db.relationship('Blog', backref='radar_captures')
    