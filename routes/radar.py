from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentSource, CapturedContent
import os
from groq import Groq
from dotenv import load_dotenv
from utils.scrapers import extrair_texto_da_url

load_dotenv()

radar_bp = Blueprint('radar', __name__)

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- CONSTANTE PARA O USUÁRIO DEMO ---
DEMO_EMAIL = 'demo@wpautoblog.com.br'

@radar_bp.route('/radar')
@login_required
def radar():
    # Busca fontes vinculadas aos sites do usuário
    query = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id)
    
    site_id = request.args.get('site_id')
    if site_id and site_id.isdigit():
        query = query.filter(ContentSource.blog_id == int(site_id))
        
    fontes = query.order_by(ContentSource.created_at.desc()).all()
    return render_template('radar.html', user=current_user, fontes=fontes)

@radar_bp.route('/add-source', methods=['POST'])
@login_required
def add_source():
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Adição de novas fontes desabilitada.', 'warning')
        return redirect(url_for('radar.radar'))

    url = request.form.get('url').strip()
    site_id = request.form.get('site_id')
    
    # Valida se o site pertence ao usuário
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    # Identificação simples de tipo
    source_type = 'youtube' if "youtube.com" in url or "youtu.be" in url else 'blog'

    nova_fonte = ContentSource(
        blog_id=site.id, 
        source_url=url, 
        source_type=source_type, 
        is_active=True
    )
    
    db.session.add(nova_fonte)
    db.session.commit()
    flash('Fonte adicionada ao Radar com sucesso!', 'success')
    return redirect(url_for('radar.radar'))

@radar_bp.route('/delete-source/<int:source_id>', methods=['POST'])
@login_required
def delete_source(source_id):
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Exclusão desabilitada.', 'warning')
        return redirect(url_for('radar.radar'))

    fonte = ContentSource.query.join(Blog).filter(
        ContentSource.id == source_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    db.session.delete(fonte)
    db.session.commit()
    flash('Fonte removida do monitoramento.', 'info')
    return redirect(url_for('radar.radar'))

@radar_bp.route('/sync-radar')
@login_required
def sync_radar():
    """Sincroniza manualmente as fontes do usuário atual."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Sincronização desativada.', 'info')
        return redirect(url_for('radar.radar'))

    fontes = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id).all()
    
    if not fontes:
        flash("Adicione uma fonte primeiro!", "warning")
        return redirect(url_for('radar.radar'))

    contador = 0
    groq_client = get_groq_client()

    for fonte in fontes:
        texto_real = extrair_texto_da_url(fonte.source_url)
        if texto_real:
            try:
                # Usa IA para resumir a oportunidade
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Extraia os 3 pontos principais deste conteúdo para um novo artigo SEO."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                
                nova_captura = CapturedContent(
                    source_id=fonte.id, 
                    site_id=fonte.blog_id, 
                    url=fonte.source_url, 
                    title="Insight Automático", 
                    summary=response.choices[0].message.content
                )
                db.session.add(nova_captura)
                contador += 1
            except Exception as e:
                print(f"Erro ao processar fonte {fonte.id}: {e}")
                continue

    db.session.commit()
    flash(f"Radar atualizado! {contador} novas análises geradas.", "success")
    return redirect(url_for('radar.radar'))