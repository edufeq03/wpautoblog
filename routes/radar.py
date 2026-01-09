from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentSource
from services import content_service
from services.scraper_service import extrair_texto_da_url

radar_bp = Blueprint('radar', __name__)

@radar_bp.route('/radar')
@login_required
def radar():
    query = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id)
    site_id = request.args.get('site_id', type=int)
    if site_id:
        query = query.filter(ContentSource.blog_id == site_id)
        
    fontes = query.order_by(ContentSource.created_at.desc()).all()
    return render_template('radar.html', fontes=fontes)

@radar_bp.route('/add-source', methods=['POST'])
@login_required
def add_source():
    if getattr(current_user, 'is_demo', False): # Ponto 4 do pente fino
        flash('Modo Demo: Adição desabilitada.', 'warning')
        return redirect(url_for('radar.radar'))

    url = request.form.get('url', '').strip()
    site_id = request.form.get('site_id')
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    nova_fonte = ContentSource(
        blog_id=site.id, 
        source_url=url, 
        source_type='youtube' if "youtu" in url else 'blog', 
        is_active=True
    )
    db.session.add(nova_fonte)
    db.session.commit()
    flash('Fonte adicionada com sucesso!', 'success')
    return redirect(url_for('radar.radar'))

@radar_bp.route('/sync-radar')
@login_required
def sync_radar():
    if getattr(current_user, 'is_demo', False):
        flash('Modo Demo: Sincronização desativada.', 'info')
        return redirect(url_for('radar.radar'))

    fontes = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id).all()
    if not fontes:
        flash("Adicione uma fonte primeiro!", "warning")
        return redirect(url_for('radar.radar'))

    # Delega a inteligência para o serviço
    novos = content_service.sync_sources_logic(fontes, extrair_texto_da_url)
    
    flash(f"Radar atualizado! {novos} novas análises geradas.", "success")
    return redirect(url_for('radar.radar'))

@radar_bp.route('/delete-source/<int:source_id>', methods=['POST'])
@login_required
def delete_source(source_id):
    # Lógica de deleção simples mantida aqui para brevidade
    fonte = ContentSource.query.join(Blog).filter(ContentSource.id == source_id, Blog.user_id == current_user.id).first_or_404()
    db.session.delete(fonte)
    db.session.commit()
    return redirect(url_for('radar.radar'))

@radar_bp.route('/approve-insight/<int:insight_id>')
@login_required
def approve_insight(insight_id):
    """Rota que transforma um insight em uma ideia de post real."""
    if content_service.convert_radar_insight_to_idea(insight_id):
        flash("Insight aprovado! Ele agora aparece na sua lista de Ideias.", "success")
    else:
        flash("Erro ao processar insight.", "danger")
    return redirect(url_for('radar.radar'))