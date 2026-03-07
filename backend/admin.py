from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import current_user
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import json
import csv
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from backend.database import db, User, Conversation, Message, SymptomCheck, LoginHistory
from backend.database import UserActivity, SystemLog, AdminAction, ModelPerformance
from backend.database import Report, SystemSetting, AuditTrail
from backend.admin_decorators import admin_required, super_admin_required, api_admin_required
from backend.logger import log_admin_action, log_audit_trail
from backend.mistral_model import MistralDoctorAssistant

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Dashboard
@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard"""
    # Get statistics
    total_users = User.query.count()
    active_today = User.query.filter(User.last_active >= datetime.utcnow() - timedelta(days=1)).count()
    total_conversations = Conversation.query.count()
    total_messages = Message.query.count()
    
    # New users this week
    new_users = User.query.filter(
        User.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    # System health
    model_status = 'healthy' if doctor_assistant and doctor_assistant.model else 'unhealthy'
    
    # Recent admin actions
    recent_actions = AdminAction.query.order_by(AdminAction.timestamp.desc()).limit(10).all()
    
    # System logs
    recent_logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(10).all()
    
    # Model performance
    avg_response_time = db.session.query(func.avg(ModelPerformance.response_time_ms)).scalar() or 0
    avg_tokens = db.session.query(func.avg(ModelPerformance.tokens_generated)).scalar() or 0
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_today=active_today,
                         total_conversations=total_conversations,
                         total_messages=total_messages,
                         new_users=new_users,
                         model_status=model_status,
                         recent_actions=recent_actions,
                         recent_logs=recent_logs,
                         avg_response_time=round(avg_response_time, 2),
                         avg_tokens=round(avg_tokens, 2))

# User Management
@admin_bp.route('/users')
@admin_required
def users():
    """User management page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    status = request.args.get('status', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.email.contains(search)) |
            (User.full_name.contains(search))
        )
    
    if role:
        query = query.filter_by(role=role)
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'locked':
        query = query.filter(User.account_locked_until > datetime.utcnow())
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/users.html', users=users, search=search, role=role, status=status)

@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    """User detail page"""
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    conversations = Conversation.query.filter_by(user_id=user_id).count()
    messages = Message.query.join(Conversation).filter(Conversation.user_id == user_id).count()
    symptom_checks = SymptomCheck.query.filter_by(user_id=user_id).count()
    
    # Recent activity
    recent_activity = UserActivity.query.filter_by(user_id=user_id)\
                      .order_by(UserActivity.timestamp.desc()).limit(20).all()
    
    # Login history
    login_history = LoginHistory.query.filter_by(user_id=user_id)\
                   .order_by(LoginHistory.login_time.desc()).limit(20).all()
    
    # Recent conversations
    recent_conversations = Conversation.query.filter_by(user_id=user_id)\
                          .order_by(Conversation.updated_at.desc()).limit(10).all()
    
    return render_template('admin/user_detail.html',
                         user=user,
                         conversations=conversations,
                         messages=messages,
                         symptom_checks=symptom_checks,
                         recent_activity=recent_activity,
                         login_history=login_history,
                         recent_conversations=recent_conversations)

@admin_bp.route('/api/users/<int:user_id>/toggle-status', methods=['POST'])
@api_admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    data = request.json
    
    old_status = user.is_active
    user.is_active = data.get('is_active', not user.is_active)
    
    db.session.commit()
    
    # Log action
    log_admin_action(
        admin_id=current_user.id,
        action='toggle_user_status',
        target_type='user',
        target_id=user_id,
        details={'old_status': old_status, 'new_status': user.is_active},
        ip_address=request.remote_addr
    )
    
    return jsonify({'success': True, 'is_active': user.is_active})

@admin_bp.route('/api/users/<int:user_id>/change-role', methods=['POST'])
@super_admin_required
def change_user_role(user_id):
    """Change user role"""
    user = User.query.get_or_404(user_id)
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ['user', 'admin', 'super_admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    old_role = user.role
    user.role = new_role
    
    db.session.commit()
    
    # Log action
    log_admin_action(
        admin_id=current_user.id,
        action='change_role',
        target_type='user',
        target_id=user_id,
        details={'old_role': old_role, 'new_role': new_role},
        ip_address=request.remote_addr
    )
    
    return jsonify({'success': True, 'role': user.role})

@admin_bp.route('/api/users/<int:user_id>/unlock', methods=['POST'])
@admin_required
def unlock_user(user_id):
    """Unlock locked user account"""
    user = User.query.get_or_404(user_id)
    
    user.account_locked_until = None
    user.failed_login_attempts = 0
    
    db.session.commit()
    
    log_admin_action(
        admin_id=current_user.id,
        action='unlock_account',
        target_type='user',
        target_id=user_id,
        ip_address=request.remote_addr
    )
    
    return jsonify({'success': True})

@admin_bp.route('/api/users/<int:user_id>/delete', methods=['DELETE'])
@super_admin_required
def delete_user(user_id):
    """Delete user (super admin only)"""
    user = User.query.get_or_404(user_id)
    
    if user.is_super_admin():
        return jsonify({'error': 'Cannot delete super admin'}), 400
    
    # Log before deletion
    log_admin_action(
        admin_id=current_user.id,
        action='delete_user',
        target_type='user',
        target_id=user_id,
        details={'username': user.username, 'email': user.email},
        ip_address=request.remote_addr
    )
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True})

# Conversations Management
@admin_bp.route('/conversations')
@admin_required
def conversations():
    """Conversations management page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    user_id = request.args.get('user_id', type=int)
    
    query = Conversation.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    conversations = query.order_by(Conversation.updated_at.desc())\
                    .paginate(page=page, per_page=per_page)
    
    return render_template('admin/conversations.html', conversations=conversations)

@admin_bp.route('/conversations/<int:conv_id>')
@admin_required
def view_conversation(conv_id):
    """View conversation details"""
    conversation = Conversation.query.get_or_404(conv_id)
    messages = Message.query.filter_by(conversation_id=conv_id)\
              .order_by(Message.timestamp).all()
    
    return render_template('admin/conversation_detail.html',
                         conversation=conversation,
                         messages=messages)

@admin_bp.route('/api/conversations/<int:conv_id>/delete', methods=['DELETE'])
@admin_required
def delete_conversation(conv_id):
    """Delete conversation"""
    conversation = Conversation.query.get_or_404(conv_id)
    
    log_admin_action(
        admin_id=current_user.id,
        action='delete_conversation',
        target_type='conversation',
        target_id=conv_id,
        details={'user_id': conversation.user_id, 'title': conversation.title},
        ip_address=request.remote_addr
    )
    
    db.session.delete(conversation)
    db.session.commit()
    
    return jsonify({'success': True})

# Reports and Analytics
@admin_bp.route('/reports')
@admin_required
def reports():
    """Reports page"""
    saved_reports = Report.query.order_by(Report.created_at.desc()).limit(20).all()
    
    return render_template('admin/reports.html', saved_reports=saved_reports)

@admin_bp.route('/api/reports/generate', methods=['POST'])
@admin_required
def generate_report():
    """Generate custom report"""
    data = request.json
    report_type = data.get('type')
    date_range = data.get('date_range', 'week')
    format = data.get('format', 'json')
    
    # Calculate date range
    end_date = datetime.utcnow()
    if date_range == 'day':
        start_date = end_date - timedelta(days=1)
    elif date_range == 'week':
        start_date = end_date - timedelta(days=7)
    elif date_range == 'month':
        start_date = end_date - timedelta(days=30)
    elif date_range == 'year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = datetime.min
    
    # Generate report based on type
    if report_type == 'user_activity':
        report_data = generate_user_activity_report(start_date, end_date)
    elif report_type == 'system_health':
        report_data = generate_system_health_report(start_date, end_date)
    elif report_type == 'model_performance':
        report_data = generate_model_performance_report(start_date, end_date)
    elif report_type == 'security':
        report_data = generate_security_report(start_date, end_date)
    else:
        return jsonify({'error': 'Invalid report type'}), 400
    
    # Save report
    report = Report(
        user_id=current_user.id,
        report_type=report_type,
        title=f"{report_type.replace('_', ' ').title()} Report - {end_date.strftime('%Y-%m-%d')}",
        content=json.dumps(report_data),
        format=format,
        created_by=current_user.id
    )
    db.session.add(report)
    db.session.commit()
    
    # Export in requested format
    if format == 'csv':
        return export_report_csv(report_data, report_type)
    elif format == 'pdf':
        return export_report_pdf(report_data, report_type)
    else:
        return jsonify(report_data)

def generate_user_activity_report(start_date, end_date):
    """Generate user activity report"""
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'new_users': User.query.filter(User.created_at.between(start_date, end_date)).count(),
        'active_users': User.query.filter(User.last_active.between(start_date, end_date)).count(),
        'total_conversations': Conversation.query.filter(Conversation.created_at.between(start_date, end_date)).count(),
        'total_messages': Message.query.filter(Message.timestamp.between(start_date, end_date)).count(),
        'symptom_checks': SymptomCheck.query.filter(SymptomCheck.created_at.between(start_date, end_date)).count(),
        'users_by_role': {
            role: count for role, count in 
            db.session.query(User.role, func.count(User.id))
            .filter(User.created_at.between(start_date, end_date))
            .group_by(User.role).all()
        },
        'hourly_activity': [
            {'hour': hour, 'count': count}
            for hour, count in
            db.session.query(
                func.extract('hour', Message.timestamp),
                func.count(Message.id)
            )
            .filter(Message.timestamp.between(start_date, end_date))
            .group_by(func.extract('hour', Message.timestamp))
            .order_by(func.extract('hour', Message.timestamp))
            .all()
        ]
    }

def generate_system_health_report(start_date, end_date):
    """Generate system health report"""
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'errors': SystemLog.query.filter(
            SystemLog.level.in_(['error', 'critical']),
            SystemLog.timestamp.between(start_date, end_date)
        ).count(),
        'warnings': SystemLog.query.filter_by(level='warning').filter(
            SystemLog.timestamp.between(start_date, end_date)
        ).count(),
        'avg_response_time': db.session.query(func.avg(ModelPerformance.response_time_ms))
            .filter(ModelPerformance.timestamp.between(start_date, end_date)).scalar() or 0,
        'avg_memory_usage': db.session.query(func.avg(ModelPerformance.memory_usage_mb))
            .filter(ModelPerformance.timestamp.between(start_date, end_date)).scalar() or 0,
        'peak_usage': db.session.query(
            func.max(ModelPerformance.memory_usage_mb),
            func.max(ModelPerformance.cpu_usage_percent)
        ).filter(ModelPerformance.timestamp.between(start_date, end_date)).first()
    }

def generate_model_performance_report(start_date, end_date):
    """Generate model performance report"""
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'total_requests': ModelPerformance.query.filter(
            ModelPerformance.timestamp.between(start_date, end_date)
        ).count(),
        'avg_response_time': db.session.query(func.avg(ModelPerformance.response_time_ms))
            .filter(ModelPerformance.timestamp.between(start_date, end_date)).scalar() or 0,
        'avg_tokens': db.session.query(func.avg(ModelPerformance.tokens_generated))
            .filter(ModelPerformance.timestamp.between(start_date, end_date)).scalar() or 0,
        'performance_by_type': [
            {
                'type': req_type,
                'avg_time': avg_time,
                'count': count
            }
            for req_type, avg_time, count in
            db.session.query(
                ModelPerformance.request_type,
                func.avg(ModelPerformance.response_time_ms),
                func.count(ModelPerformance.id)
            )
            .filter(ModelPerformance.timestamp.between(start_date, end_date))
            .group_by(ModelPerformance.request_type)
            .all()
        ]
    }

def generate_security_report(start_date, end_date):
    """Generate security report"""
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'failed_logins': LoginHistory.query.filter_by(success=False).filter(
            LoginHistory.login_time.between(start_date, end_date)
        ).count(),
        'locked_accounts': User.query.filter(
            User.account_locked_until > datetime.utcnow()
        ).count(),
        'admin_actions': AdminAction.query.filter(
            AdminAction.timestamp.between(start_date, end_date)
        ).count(),
        'security_events': SystemLog.query.filter_by(component='security').filter(
            SystemLog.timestamp.between(start_date, end_date)
        ).count(),
        'top_ip_addresses': [
            {'ip': ip, 'count': count}
            for ip, count in
            db.session.query(LoginHistory.ip_address, func.count(LoginHistory.id))
            .filter(LoginHistory.login_time.between(start_date, end_date))
            .group_by(LoginHistory.ip_address)
            .order_by(func.count(LoginHistory.id).desc())
            .limit(10)
            .all()
        ]
    }

def export_report_csv(report_data, report_type):
    """Export report as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Metric', 'Value'])
    
    # Flatten data and write rows
    for key, value in flatten_dict(report_data).items():
        writer.writerow([key, value])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
    )

def export_report_pdf(report_data, report_type):
    """Export report as PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(
        f"{report_type.replace('_', ' ').title()} Report",
        styles['Title']
    )
    story.append(title)
    story.append(Spacer(1, 0.25*inch))
    
    # Date
    date = Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        styles['Normal']
    )
    story.append(date)
    story.append(Spacer(1, 0.25*inch))
    
    # Create table from data
    data = [['Metric', 'Value']]
    for key, value in flatten_dict(report_data).items():
        data.append([key, str(value)])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    doc.build(story)
    
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
    )

def flatten_dict(d, parent_key='', sep='_'):
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

# Security Logs
@admin_bp.route('/security-logs')
@admin_required
def security_logs():
    """Security logs page"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    level = request.args.get('level', '')
    component = request.args.get('component', '')
    
    query = SystemLog.query
    
    if level:
        query = query.filter_by(level=level)
    
    if component:
        query = query.filter_by(component=component)
    
    logs = query.order_by(SystemLog.timestamp.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/security_logs.html', logs=logs)

# Model Monitoring
@admin_bp.route('/model-monitor')
@admin_required
def model_monitor():
    """Model monitoring page"""
    # Get recent performance
    recent_performance = ModelPerformance.query\
                        .order_by(ModelPerformance.timestamp.desc())\
                        .limit(100).all()
    
    # Calculate averages
    avg_response_time = db.session.query(func.avg(ModelPerformance.response_time_ms)).scalar() or 0
    avg_tokens = db.session.query(func.avg(ModelPerformance.tokens_generated)).scalar() or 0
    avg_memory = db.session.query(func.avg(ModelPerformance.memory_usage_mb)).scalar() or 0
    
    # Performance by hour
    hourly_performance = db.session.query(
        func.strftime('%H', ModelPerformance.timestamp),
        func.avg(ModelPerformance.response_time_ms),
        func.avg(ModelPerformance.tokens_generated),
        func.count(ModelPerformance.id)
    ).group_by(func.strftime('%H', ModelPerformance.timestamp)).all()
    
    return render_template('admin/model_monitor.html',
                         recent_performance=recent_performance,
                         avg_response_time=round(avg_response_time, 2),
                         avg_tokens=round(avg_tokens, 2),
                         avg_memory=round(avg_memory, 2),
                         hourly_performance=hourly_performance)

# System Settings
@admin_bp.route('/settings', methods=['GET', 'POST'])
@super_admin_required
def settings():
    """System settings page"""
    if request.method == 'POST':
        # Update settings
        for key, value in request.form.items():
            if key.startswith('setting_'):
                setting_key = key[8:]  # Remove 'setting_' prefix
                setting = SystemSetting.query.filter_by(key=setting_key).first()
                
                if setting:
                    old_value = setting.value
                    setting.value = value
                    setting.updated_by = current_user.id
                    
                    # Log audit trail
                    log_audit_trail(
                        user_id=current_user.id,
                        action='update_setting',
                        resource_type='system_setting',
                        resource_id=setting.id,
                        old_value={'value': old_value},
                        new_value={'value': value}
                    )
                else:
                    new_setting = SystemSetting(
                        key=setting_key,
                        value=value,
                        category=request.form.get(f'category_{setting_key}', 'general'),
                        updated_by=current_user.id
                    )
                    db.session.add(new_setting)
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get all settings
    settings = SystemSetting.query.order_by(SystemSetting.category).all()
    
    # Group by category
    settings_by_category = {}
    for setting in settings:
        if setting.category not in settings_by_category:
            settings_by_category[setting.category] = []
        settings_by_category[setting.category].append(setting)
    
    return render_template('admin/system_settings.html', settings_by_category=settings_by_category)

# Audit Trail
@admin_bp.route('/audit-trail')
@super_admin_required
def audit_trail():
    """Audit trail page"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '')
    
    query = AuditTrail.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if action:
        query = query.filter_by(action=action)
    
    audit_logs = query.order_by(AuditTrail.timestamp.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/audit_trail.html', audit_logs=audit_logs)

# API Endpoints for Admin
@admin_bp.route('/api/stats')
@api_admin_required
def get_stats():
    """Get real-time statistics"""
    return jsonify({
        'users': {
            'total': User.query.count(),
            'active_today': User.query.filter(User.last_active >= datetime.utcnow() - timedelta(days=1)).count(),
            'new_today': User.query.filter(User.created_at >= datetime.utcnow() - timedelta(days=1)).count()
        },
        'conversations': {
            'total': Conversation.query.count(),
            'today': Conversation.query.filter(Conversation.created_at >= datetime.utcnow() - timedelta(days=1)).count()
        },
        'messages': {
            'total': Message.query.count(),
            'today': Message.query.filter(Message.timestamp >= datetime.utcnow() - timedelta(days=1)).count()
        },
        'system': {
            'model_available': doctor_assistant is not None,
            'avg_response_time': db.session.query(func.avg(ModelPerformance.response_time_ms)).scalar() or 0,
            'errors_last_hour': SystemLog.query.filter(
                SystemLog.level.in_(['error', 'critical']),
                SystemLog.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).count()
        }
    })

@admin_bp.route('/api/backup-database', methods=['POST'])
@super_admin_required
def backup_database():
    """Create database backup"""
    import shutil
    from datetime import datetime
    
    # Create backups directory if not exists
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    # Create backup filename
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backups/doctorai_backup_{timestamp}.db'
    
    # Copy database file
    shutil.copy2('instance/doctor_ai.db', backup_file)
    
    # Log action
    log_admin_action(
        admin_id=current_user.id,
        action='backup_database',
        target_type='system',
        target_id=None,
        details={'backup_file': backup_file},
        ip_address=request.remote_addr
    )
    
    return jsonify({'success': True, 'backup_file': backup_file})

@admin_bp.route('/api/clear-logs/<log_type>', methods=['POST'])
@super_admin_required
def clear_logs(log_type):
    """Clear system logs"""
    if log_type == 'all':
        SystemLog.query.delete()
        AdminAction.query.delete()
        AuditTrail.query.delete()
    elif log_type == 'system':
        SystemLog.query.delete()
    elif log_type == 'admin':
        AdminAction.query.delete()
    elif log_type == 'audit':
        AuditTrail.query.delete()
    else:
        return jsonify({'error': 'Invalid log type'}), 400
    
    db.session.commit()
    
    log_admin_action(
        admin_id=current_user.id,
        action='clear_logs',
        target_type='system',
        details={'log_type': log_type},
        ip_address=request.remote_addr
    )
    
    return jsonify({'success': True})