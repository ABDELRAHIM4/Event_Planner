class Invitation:
    def __init__(self, sender, inviter, event_id, status='pending', reason=None):
        self.sender = sender
        self.inviter = inviter
        self.event_id = event_id
        self.status = status
        self.reason = reason

class InvitationStatus:
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
