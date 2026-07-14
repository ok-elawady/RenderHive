"""
Custom DRF permission classes for the jobs app.

Three permission tiers exist across the API:
1. Any authenticated user (web session or any token).
2. Farm agent (Worker daemon or DCC plugin using the shared studio token).
3. Staff / supervisor (Django ``is_staff`` flag).
"""

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsFarmAgent(BasePermission):
    """Allow access only to users belonging to the 'farm_agents' group.

    This group is assigned to the ``farm_service`` user account whose DRF token
    is distributed in the shared network config file (``renderhive.conf``).
    Both the Worker daemon and DCC plugins authenticate using this token.

    Usage::

        permission_classes = [IsFarmAgent]

    Attributes:
        message: Error message returned on permission denial.
    """

    message = "Access restricted to farm agent accounts (Worker or DCC plugin)."

    def has_permission(self, request, view) -> bool:
        """Check if the authenticated user is a member of 'farm_agents'.

        Args:
            request: The incoming HTTP request.
            view: The view being accessed.

        Returns:
            True if the user is authenticated and in the 'farm_agents' group.
        """
        return (
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name='farm_agents').exists()
        )


class IsJobOwnerOrStaff(BasePermission):
    """Allow access only to the submitter of a job or to staff users.

    Used for destructive or mutating job-level actions (PATCH, DELETE,
    pause, resume) to prevent artists from accidentally modifying each
    other's jobs.

    This is an object-level permission — it must be combined with
    ``IsAuthenticated`` and the view must call ``self.get_object()``
    before checking the permission.

    Usage::

        permission_classes = [IsAuthenticated, IsJobOwnerOrStaff]

    Attributes:
        message: Error message returned on permission denial.
    """

    message = "You do not have permission to modify this job."

    def has_object_permission(self, request, view, obj) -> bool:
        """Check if the requesting user submitted this job or is staff.

        Args:
            request: The incoming HTTP request.
            view: The view being accessed.
            obj: The :class:`apps.jobs.models.Job` instance being accessed.

        Returns:
            True if the user is the job submitter or a staff user.
        """
        if request.user.is_staff:
            return True
        return obj.submitted_by == request.user
