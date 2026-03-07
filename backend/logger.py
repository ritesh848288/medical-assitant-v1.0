import logging
import logging.handlers
import os
import json
from datetime import datetime
from flask import request
from backend.database import db, SystemLog, AdminAction, AuditTrail

# Create logs directory if not exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(level=logging.INFO)

# Security logger
security_logger = logging.getLogger('security')
security_handler = logging.handlers.RotatingFileHandler(
    'logs/security.log', maxBytes=10485760, backupCount=10
)
security_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
security_logger.addHandler(security_handler)

# Access logger
access_logger = logging.getLogger('access')
access_handler = logging.handlers.RotatingFileHandler(
    'logs/access.log', maxBytes=10485760, backupCount=10
)
access_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(message)s'
))
access_logger.addHandler(access_handler)

# Model logger
model_logger = logging.getLogger('model')
model_handler = logging.handlers.RotatingFileHandler(
    'logs/model.log', maxBytes=10485760, backupCount=10
)
model_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
model_logger.addHandler(model_handler)

# Admin actions logger
admin_logger = logging.getLogger('admin')
admin_handler = logging.handlers.RotatingFileHandler(
    'logs/admin_actions.log', maxBytes=10485760, backupCount=10
)
admin_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
admin_logger.addHandler(admin_handler)

def log_security_event(event_type, message, details=None, level='warning'):
    """Log security events"""
    security_logger.log(getattr(logging, level.upper()), 
                       f"{event_type} - {message} - {details if details else ''}")
    
    # Save to database
    try:
        system_log = SystemLog(
            level=level,
            component='security',
            message=message,
            details=json.dumps({'event_type': event_type, 'details': details}) if details else None,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(system_log)
        db.session.commit()
    except:
        db.session.rollback()

def log_access(user_id, action, details=None):
    """Log user access"""
    access_logger.info(f"User {user_id} - {action} - {details if details else ''}")
    
    # Save to database
    try:
        activity = UserActivity(
            user_id=user_id,
            action=action,
            details=json.dumps(details) if details else None,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(activity)
        db.session.commit()
    except:
        db.session.rollback()

def log_model_performance(request_type, response_time_ms, tokens_generated, 
                          memory_usage_mb, cpu_usage_percent, gpu_usage_percent=None):
    """Log model performance metrics"""
    model_logger.info(
        f"{request_type} - Time: {response_time_ms}ms, "
        f"Tokens: {tokens_generated}, Memory: {memory_usage_mb}MB, "
        f"CPU: {cpu_usage_percent}%, GPU: {gpu_usage_percent if gpu_usage_percent else 'N/A'}"
    )
    
    # Save to database
    try:
        performance = ModelPerformance(
            request_type=request_type,
            response_time_ms=response_time_ms,
            tokens_generated=tokens_generated,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            gpu_usage_percent=gpu_usage_percent
        )
        db.session.add(performance)
        db.session.commit()
    except:
        db.session.rollback()

def log_admin_action(admin_id, action, target_type, target_id=None, details=None, ip_address=None):
    """Log admin actions"""
    admin_logger.info(
        f"Admin {admin_id} - {action} - {target_type}:{target_id} - "
        f"{json.dumps(details) if details else ''}"
    )
    
    # Save to database
    try:
        admin_action = AdminAction(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address or (request.remote_addr if request else None)
        )
        db.session.add(admin_action)
        db.session.commit()
    except:
        db.session.rollback()

def log_audit_trail(user_id, action, resource_type, resource_id, old_value, new_value):
    """Log audit trail for critical changes"""
    try:
        audit = AuditTrail(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=json.dumps(old_value) if old_value else None,
            new_value=json.dumps(new_value) if new_value else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string if request else None
        )
        db.session.add(audit)
        db.session.commit()
    except:
        db.session.rollback()