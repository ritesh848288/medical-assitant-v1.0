"""
Admin Decorators Module
Role-based access control decorators for Flask routes
"""

from functools import wraps
from flask import flash, redirect, url_for, abort, request, jsonify, session
from flask_login import current_user
import logging

# Configure logging
logger = logging.getLogger(__name__)

def admin_required(f):
    """
    Decorator to require admin role for a route
    Use for routes that need admin privileges
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role not in ['admin', 'super_admin']:
            logger.warning(f"Unauthorized admin access attempt by user {current_user.id} to {request.endpoint}")
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """
    Decorator to require super admin role for a route
    Use for sensitive routes that only super admins can access
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role != 'super_admin':
            logger.warning(f"Unauthorized super admin access attempt by user {current_user.id} to {request.endpoint}")
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def doctor_required(f):
    """
    Decorator to require doctor role for a route
    Use for doctor-specific routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role != 'doctor':
            flash('This area is only accessible to doctors.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def patient_required(f):
    """
    Decorator to require patient role for a route
    Use for patient-specific routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role != 'patient':
            flash('This area is only accessible to patients.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """
    Decorator factory to require specific roles
    Usage: @role_required('admin', 'doctor')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in roles:
                if request.is_json:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def api_admin_required(f):
    """
    Decorator for API routes that require admin authentication
    Returns JSON responses instead of redirects
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        if current_user.role not in ['admin', 'super_admin']:
            logger.warning(f"Unauthorized API admin access by user {current_user.id}")
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    """
    Decorator for fine-grained permission control
    Checks if user has specific permission
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            # Define permission mapping based on roles
            permissions = {
                'view_users': ['admin', 'super_admin'],
                'edit_users': ['admin', 'super_admin'],
                'delete_users': ['super_admin'],
                'view_reports': ['admin', 'super_admin', 'doctor'],
                'generate_reports': ['admin', 'super_admin'],
                'manage_appointments': ['admin', 'doctor', 'patient'],
                'view_analytics': ['admin', 'super_admin', 'doctor'],
                'manage_doctors': ['admin', 'super_admin'],
                'system_settings': ['super_admin'],
                'manage_roles': ['super_admin'],
                'view_logs': ['admin', 'super_admin'],
                'export_data': ['admin', 'super_admin'],
                'manage_content': ['admin', 'super_admin'],
                'send_notifications': ['admin', 'super_admin', 'doctor'],
            }
            
            if permission in permissions:
                if current_user.role not in permissions[permission]:
                    if request.is_json:
                        return jsonify({'error': f'Permission denied: {permission}'}), 403
                    abort(403)
            else:
                # If permission not defined, default to admin only
                if current_user.role not in ['admin', 'super_admin']:
                    if request.is_json:
                        return jsonify({'error': 'Permission denied'}), 403
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def ownership_required(resource_model, user_id_field='user_id'):
    """
    Decorator to check if user owns the resource
    Usage: @ownership_required(Consultation, 'patient_id')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            # Get resource ID from kwargs (assuming it's named 'id' or 'resource_id')
            resource_id = kwargs.get('id') or kwargs.get('resource_id')
            if not resource_id:
                resource_id = request.view_args.get('id')
            
            if resource_id:
                # Query the resource
                resource = resource_model.query.get(resource_id)
                if resource:
                    # Check if current user owns the resource
                    owner_id = getattr(resource, user_id_field, None)
                    if owner_id != current_user.id and current_user.role not in ['admin', 'super_admin']:
                        logger.warning(f"Unauthorized resource access by user {current_user.id} to resource {resource_id}")
                        if request.is_json:
                            return jsonify({'error': 'You do not have permission to access this resource'}), 403
                        abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def verified_email_required(f):
    """
    Decorator to require verified email
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.email_verified:
            flash('Please verify your email address to access this feature.', 'warning')
            return redirect(url_for('auth.verify_email'))
        
        return f(*args, **kwargs)
    return decorated_function


def two_factor_required(f):
    """
    Decorator to require 2FA for sensitive operations
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        # Check if 2FA is enabled and verified in this session
        if current_user.two_factor_enabled and not session.get('2fa_verified'):
            flash('Two-factor authentication required.', 'warning')
            return redirect(url_for('auth.verify_2fa', next=request.url))
        
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests=100, window_seconds=3600):
    """
    Simple rate limiting decorator
    Usage: @rate_limit(max_requests=10, window_seconds=60)
    """
    from collections import defaultdict
    import time
    
    # Store request counts in memory (use Redis in production)
    request_counts = defaultdict(list)
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                key = request.remote_addr
            else:
                key = f"user_{current_user.id}"
            
            now = time.time()
            window_start = now - window_seconds
            
            # Clean old requests
            request_counts[key] = [t for t in request_counts[key] if t > window_start]
            
            # Check rate limit
            if len(request_counts[key]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {key}")
                if request.is_json:
                    return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
                flash('Too many requests. Please try again later.', 'warning')
                return redirect(url_for('main.index'))
            
            # Add current request
            request_counts[key].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_admin_action(f):
    """
    Decorator to automatically log admin actions
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = f(*args, **kwargs)
        
        # Log the admin action
        if current_user.is_authenticated and current_user.role in ['admin', 'super_admin']:
            from models import AdminLog
            from extensions import db
            
            log = AdminLog(
                admin_id=current_user.id,
                action=request.endpoint,
                method=request.method,
                path=request.path,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                data=str(request.get_json(silent=True) or request.form or request.args)
            )
            db.session.add(log)
            db.session.commit()
            
            logger.info(f"Admin action logged: {current_user.id} - {request.endpoint}")
        
        return result
    return decorated_function


def department_access(allowed_departments):
    """
    Decorator for department-based access control
    Usage: @department_access(['cardiology', 'neurology'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            # Check if user is admin (admins have access to all departments)
            if current_user.role in ['admin', 'super_admin']:
                return f(*args, **kwargs)
            
            # Check if user's department is allowed
            if current_user.department not in allowed_departments:
                logger.warning(f"Unauthorized department access by user {current_user.id}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def active_account_required(f):
    """
    Decorator to require active account status
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return redirect(url_for('auth.logout'))
        
        return f(*args, **kwargs)
    return decorated_function


def concurrent_session_limit(max_sessions=3):
    """
    Decorator to limit concurrent sessions
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return f(*args, **kwargs)
            
            from models import UserSession
            from extensions import db
            
            # Count active sessions
            active_sessions = UserSession.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).count()
            
            if active_sessions >= max_sessions:
                logger.warning(f"Concurrent session limit exceeded for user {current_user.id}")
                flash('Maximum concurrent sessions reached. Please log out from other devices.', 'warning')
                return redirect(url_for('auth.sessions'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def ip_whitelist(allowed_ips):
    """
    Decorator to restrict access by IP address
    Usage: @ip_whitelist(['127.0.0.1', '192.168.1.0/24'])
    """
    import ipaddress
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            
            # Check if client IP is in whitelist
            allowed = False
            for allowed_ip in allowed_ips:
                if '/' in allowed_ip:  # CIDR notation
                    if ipaddress.ip_address(client_ip) in ipaddress.ip_network(allowed_ip):
                        allowed = True
                        break
                elif client_ip == allowed_ip:
                    allowed = True
                    break
            
            if not allowed:
                logger.warning(f"Blocked access from unauthorized IP: {client_ip}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def audit_trail(action_type=None):
    """
    Decorator to create audit trail entries
    Usage: @audit_trail('user_login')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            
            # Create audit trail entry
            if current_user.is_authenticated:
                from models import AuditTrail
                from extensions import db
                
                audit = AuditTrail(
                    user_id=current_user.id,
                    action=action_type or request.endpoint,
                    resource=request.path,
                    method=request.method,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                    timestamp=datetime.utcnow()
                )
                db.session.add(audit)
                db.session.commit()
            
            return result
        return decorated_function
    return decorator


# Combined decorator for common admin routes
def admin_panel_access(f):
    """Combined decorator for admin panel access"""
    @wraps(f)
    @admin_required
    @active_account_required
    @log_admin_action
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def sensitive_operation(f):
    """Combined decorator for sensitive operations"""
    @wraps(f)
    @super_admin_required
    @two_factor_required
    @active_account_required
    @audit_trail('sensitive_operation')
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


# Utility function to check permissions in templates
def has_permission(permission):
    """Helper function for template permission checks"""
    if not current_user.is_authenticated:
        return False
    
    permissions = {
        'view_users': ['admin', 'super_admin'],
        'edit_users': ['admin', 'super_admin'],
        'delete_users': ['super_admin'],
        'view_reports': ['admin', 'super_admin', 'doctor'],
        'generate_reports': ['admin', 'super_admin'],
        'manage_appointments': ['admin', 'doctor', 'patient'],
        'view_analytics': ['admin', 'super_admin', 'doctor'],
        'manage_doctors': ['admin', 'super_admin'],
        'system_settings': ['super_admin'],
        'manage_roles': ['super_admin'],
    }
    
    if permission in permissions:
        return current_user.role in permissions[permission]
    
    return False


# Register the utility function for Jinja2 templates
def register_template_utils(app):
    """Register template utility functions"""
    app.jinja_env.globals.update(has_permission=has_permission)