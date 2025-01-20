class Invitation:
    """Represents an invitation for an event."""
    def __init__(self, sender, inviter, event_id, status='pending', reason=None):
        self.sender = sender  # The user sending the invitation
        self.inviter = inviter  # The user being invited
        self.event_id = event_id  # The ID of the event
        self.status = status  # The current status of the invitation
        self.reason = reason  # Optional reason for the invitation

class InvitationStatus:
    """Contains constants for invitation statuses."""
    PENDING = 'pending'  # Invitation is pending
    ACCEPTED = 'accepted'  # Invitation has been accepted
    REJECTED = 'rejected'  # Invitation has been rejected
