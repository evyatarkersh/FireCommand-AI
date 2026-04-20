from app.extensions import db
from datetime import datetime


class CommandLog(db.Model):
    """ טבלת יומן מבצעים: מתעדת את סיכומי האופטימיזציה המחוזית של ה-AI """
    __tablename__ = 'command_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    district_name = db.Column(db.String(100), nullable=False, index=True)

    # ה-JSON הגולמי כדי שנוכל לדבג או להציג נתונים יבשים בממשק בעתיד
    raw_json = db.Column(db.JSON, nullable=False)

    # ההודעה המילולית שה-LLM ייצר למפקד
    llm_summary_text = db.Column(db.Text, nullable=False)