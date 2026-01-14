from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from flask_login import UserMixin, LoginManager
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    credits = db.Column(db.Integer, default=5)
    last_post_date = db.Column(db.Date, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_demo = db.Column(db.Boolean, default=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False, default=1)
    plan = db.relationship('Plan', back_populates='users')
    created_at = db.Column(db.DateTime, default=db.func.now())
    sites = db.relationship('Blog', backref='owner', lazy=True)

    @property
    def plan_name(self):
        return self.plan.name if self.plan else "Free"
    
    def get_plan_limits(self):
        if self.plan:
            return {
                'max_sites': self.plan.max_sites,
                'posts_por_dia': self.plan.posts_per_day,
                'nome': self.plan.name
            }
        return {'max_sites': 1, 'posts_por_dia': 1, 'nome': 'Free'}

    def has_credits(self):
        return self.credits > 0

    def consume_credit(self, amount=1):
        if self.credits >= amount:
            self.credits -= amount
            db.session.commit()
            return True
        return False
    
    def increase_credit(self, amount=1):
        try:
            # 1. Usa o operador de adição para aumentar o saldo
            self.credits += amount
            
            # 2. Salva a alteração no banco de dados
            db.session.commit()
            return True
        except Exception as e:
            # 3. Se houver erro (ex: banco fora do ar), desfaz a alteração pendente
            db.session.rollback()
            print(f"Erro ao adicionar créditos: {e}")
            return False
    
    def can_post_today(self):
        """Verifica se o usuário atingiu o limite de posts do plano hoje"""
        # Se for admin, não tem trava diária
        if self.is_admin:
            return True
            
        limites = self.get_plan_limits()
        posts_permitidos = limites.get('posts_por_dia', 1)
        
        # Conta quantos logs de sucesso existem para hoje
        hoje = date.today()
        posts_feitos_hoje = PostLog.query.join(Blog).filter(
            Blog.user_id == self.id,
            db.func.date(PostLog.posted_at) == hoje,
            PostLog.status == 'Publicado'
        ).count()
        
        return posts_feitos_hoje < posts_permitidos
    
    def can_add_site(self):
        limits = self.get_plan_limits()
        current_sites_count = len(self.sites)
        return current_sites_count < limits['max_sites']

    def get_setup_status(self):
        if not self.sites:
            return 'no_site'
        site = self.sites[0]
        if not site.master_prompt or not site.macro_themes:
            return 'no_config'
        return 'complete'

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    max_sites = db.Column(db.Integer, default=1)
    posts_per_day = db.Column(db.Integer, default=1)
    credits_monthly = db.Column(db.Integer, default=5)
    price = db.Column(db.Float, default=0.0)
    has_radar = db.Column(db.Boolean, default=False)
    has_spy = db.Column(db.Boolean, default=False)
    has_images = db.Column(db.Boolean, default=False)
    users = db.relationship('User', back_populates='plan')

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    site_name = db.Column(db.String(100), nullable=False)
    wp_url = db.Column(db.String(200), nullable=False)
    wp_user = db.Column(db.String(100), nullable=False)
    wp_app_password = db.Column(db.String(100), nullable=False)
    timezone = db.Column(db.String(50), default='America/Sao_Paulo')
    
    # Configurações de IA
    macro_themes = db.Column(db.Text, nullable=True) 
    master_prompt = db.Column(db.Text, nullable=True, default='Voce é um excelente escritor de post para Blogs.')
    
    # NOVOS CAMPOS PARA AUTOMAÇÃO E PREFERÊNCIAS
    post_status = db.Column(db.String(20), default='publish') 
    posts_per_day = db.Column(db.Integer, default=1)      # Adicionado
    schedule_time = db.Column(db.String(10), default='09:00') # Adicionado
    default_category = db.Column(db.String(100), nullable=True) # Adicionado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    logs = db.relationship('PostLog', backref='blog', lazy=True, cascade="all, delete-orphan")

class ContentIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    context_insight = db.Column(db.Text, nullable=True) 
    full_content = db.Column(db.Text, nullable=True)
    featured_image_id = db.Column(db.Integer, nullable=True)
    is_manual = db.Column(db.Boolean, default=False)
    is_posted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # RELAÇÃO CORRIGIDA:
    # Usamos backref='ideas' aqui e MAIS EM LUGAR NENHUM (remova do Blog se houver algo parecido)
    blog = db.relationship('Blog', backref=db.backref('ideas', lazy=True))

class PostLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    wp_post_id = db.Column(db.Integer)
    post_url = db.Column(db.String(500))
    status = db.Column(db.String(50)) # 'Publicado' ou 'Erro'
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContentSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    source_type = db.Column(db.String(50), nullable=False) # 'RSS' ou 'URL'
    source_name = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_scraped = db.Column(db.DateTime, nullable=True)
    blog = db.relationship('Blog', backref='sources')

class CapturedContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('content_source.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    url = db.Column(db.String(500), nullable=True)
    title = db.Column(db.String(200))
    content_summary = db.Column(db.Text)
    is_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.relationship('ContentSource', backref=db.backref('captures', lazy=True))
    
class ApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    api_name = db.Column(db.String(50), nullable=False)  # Ex: 'Groq', 'OpenAI'
    feature = db.Column(db.String(50), nullable=False)   # Ex: 'Generate Ideas', 'Post-IA'
    tokens_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento para facilitar consultas no admin
    user = db.relationship('User', backref=db.backref('api_usages', lazy=True))