from ohmywod.extensions import db
from ohmywod.models.feedback import Feedback


class FeedbackController:

    def create_feedback(self, username, content):
        feedback = Feedback(username=username, content=content)
        db.session.add(feedback)
        db.session.commit()
        return feedback
