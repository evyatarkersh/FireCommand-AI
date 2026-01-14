from app.extensions import db

class TestLog(db.Model):
    __tablename__ = 'test_log'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "message": self.message
        }