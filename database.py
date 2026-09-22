from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class MetricHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cpu = db.Column(db.Float)
    ram = db.Column(db.Float)
    disk = db.Column(db.Float)

class AlertHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
