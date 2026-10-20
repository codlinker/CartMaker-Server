"""
Sistema de Trabajadores (Workforce): invitaciones, gestión de trabajadores por el dueño,
renuncia del trabajador y login bifurcado (espacios de trabajo personal / trabajador).

Toda la lógica de negocio vive en `api/core/workforce.py`; estas vistas solo traducen HTTP.
"""
from .base import *
from ..core.workforce import (
    WorkforceError,
    CTX_PERSONAL,
    CTX_WORKER,
    EMP_ID_CLAIM,
    COMPANY_ID_CLAIM,
    ROLE_CLAIM,
    create_invitation,
    preview_invitation,
    accept_invitation,
    decline_invitation,
    revoke_invitation,
    list_company_invitations,
    list_my_invitations,
    list_company_employees,
    get_company_employee,
    update_employee,
    leave_company,
    get_user_workspaces,
    build_worker_workspace,
    select_workspace,
)
from ..permissions import IsPersonalContext, get_request_ctx, get_token_claim


def _workforce_error_response(err: WorkforceError) -> Response:
    payload = {'error': err.message}
    if err.code:
        payload['code'] = err.code
    return Response(payload, status=err.status_code)


def _truthy(raw) -> bool:
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'si', 'sí')


####################################################
################## INVITACIONES ####################
####################################################

class WorkforceInvitationsAPI(APIView):
    """
    GET  /api/v1/workforce/invitations/?status=pending|accepted|declined|revoked|expired
    POST /api/v1/workforce/invitations/
         Body: {role: 'assistant'|'delivery', channel: 'email'|'in_app'|'qr_link',
                target_email?, target_user_id?, store_ids?: [uuid], ttl_hours?: int (1-168)}
    Solo el dueño del comercio (cuenta personal).
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def get(self, request):
        try:
            qs = list_company_invitations(request.user, status_filter=request.query_params.get('status'))
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({'data': [inv.get_json(include_company=False) for inv in qs[:200]]}, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            invitation, raw_token, link = create_invitation(request.user, request.data)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({
            'message': "Invitación creada.",
            'data': invitation.get_json(include_company=True),
            'link': link,
            'short_code': invitation.short_code,
            'qr_payload': link,
        }, status=status.HTTP_201_CREATED)


class WorkforceInvitationRevokeAPI(APIView):
    """
    POST /api/v1/workforce/invitations/<id>/revoke/
    Solo el dueño del comercio. Solo invitaciones pendientes.
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def post(self, request, invitation_id: int):
        try:
            invitation = revoke_invitation(request.user, invitation_id)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({
            'message': "Invitación revocada.",
            'data': invitation.get_json(include_company=False),
        }, status=status.HTTP_200_OK)


class WorkforceInvitationPreviewAPI(APIView):
    """
    GET /api/v1/workforce/invitations/preview/<token|short_code>/
    Público (con límite de tasa). Muestra comercio, logo, rol, vigencia y estado antes de aceptar.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'workforce_invite'

    def get(self, request, token: str):
        try:
            data = preview_invitation(token)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({'data': data, 'invitation': data, **data}, status=status.HTTP_200_OK)


class WorkforceInvitationAcceptAPI(APIView):
    """
    POST /api/v1/workforce/invitations/accept/
    Body: {token} | {short_code} | {invitation_id} (este último solo para invitaciones dirigidas al usuario).
    Usuario autenticado en su cuenta personal.
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'workforce_invite'

    def post(self, request):
        try:
            employee = accept_invitation(
                request.user,
                token=request.data.get('token'),
                short_code=request.data.get('short_code') or request.data.get('code'),
                invitation_id=request.data.get('invitation_id'),
            )
        except WorkforceError as e:
            return _workforce_error_response(e)

        employee = Employee.objects.select_related('user', 'company').get(pk=employee.pk)
        return Response({
            'message': f"¡Bienvenido al equipo de {employee.company.name}!",
            'employee': employee.get_json(include_company=True),
            'workspace': build_worker_workspace(employee),
            'workspaces': get_user_workspaces(request.user),
        }, status=status.HTTP_200_OK)


class MyInvitationsAPI(APIView):
    """
    GET /api/v1/workforce/my-invitations/
    Invitaciones pendientes y vigentes dirigidas al usuario autenticado (por cuenta o por correo).
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        qs = list_my_invitations(request.user)
        return Response({'data': [inv.get_json(include_company=True) for inv in qs[:50]]}, status=status.HTTP_200_OK)


class MyInvitationDeclineAPI(APIView):
    """
    POST /api/v1/workforce/my-invitations/<id>/decline/
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def post(self, request, invitation_id: int):
        try:
            invitation = decline_invitation(request.user, invitation_id)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({
            'message': "Invitación rechazada.",
            'data': invitation.get_json(include_company=True),
        }, status=status.HTTP_200_OK)


####################################################
############ GESTIÓN DE TRABAJADORES ###############
####################################################

class WorkforceEmployeesAPI(APIView):
    """
    GET /api/v1/workforce/employees/?include_revoked=1&role=delivery
    Lista los trabajadores del comercio del dueño autenticado.
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        try:
            qs = list_company_employees(
                request.user,
                include_revoked=_truthy(request.query_params.get('include_revoked')),
            )
        except WorkforceError as e:
            return _workforce_error_response(e)
        role_filter = (request.query_params.get('role') or '').strip().lower()
        employees = [emp for emp in qs if not role_filter or emp.role_slug == role_filter]
        return Response({'data': [emp.get_json() for emp in employees]}, status=status.HTTP_200_OK)


class WorkforceEmployeeDetailAPI(APIView):
    """
    GET   /api/v1/workforce/employees/<id>/
    PATCH /api/v1/workforce/employees/<id>/
          Body (todos opcionales): {role, vehicle_type, display_alias, store_ids: [uuid],
                                    status: 'active'|'suspended'|'revoked' | action: 'suspend'|'reactivate'|'revoke'}
    Solo el dueño del comercio.
    """
    permission_classes = [IsAuthenticated, IsPersonalContext]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def get(self, request, employee_id: int):
        try:
            employee = get_company_employee(request.user, employee_id)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({'data': employee.get_json()}, status=status.HTTP_200_OK)

    def patch(self, request, employee_id: int):
        try:
            employee = update_employee(request.user, employee_id, request.data)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({
            'message': "Trabajador actualizado.",
            'data': employee.get_json(),
        }, status=status.HTTP_200_OK)


class WorkforceLeaveAPI(APIView):
    """
    POST /api/v1/workforce/me/leave/
    Body: {employee_id}
    El trabajador renuncia al comercio (desde cualquier contexto de sesión).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def post(self, request):
        employee_id = request.data.get('employee_id')
        if employee_id in (None, ''):
            employee_id = get_token_claim(request, EMP_ID_CLAIM, None)
        try:
            employee = leave_company(request.user, employee_id)
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response({
            'message': f"Dejaste de trabajar en {employee.company.name}.",
            'employee_id': employee.id,
            'workspaces': get_user_workspaces(request.user),
        }, status=status.HTTP_200_OK)


####################################################
######### LOGIN BIFURCADO (WORKSPACES) #############
####################################################

class AuthWorkspacesAPI(APIView):
    """
    GET /api/v1/auth/workspaces/
    Espacios de trabajo disponibles y contexto de la sesión actual.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        ctx = get_request_ctx(request)
        return Response({
            'ctx': ctx,
            'current_employee_id': get_token_claim(request, EMP_ID_CLAIM, None) if ctx == CTX_WORKER else None,
            'current_company_id': get_token_claim(request, COMPANY_ID_CLAIM, None) if ctx == CTX_WORKER else None,
            'current_role': get_token_claim(request, ROLE_CLAIM, None) if ctx == CTX_WORKER else None,
            'workspaces': get_user_workspaces(request.user),
        }, status=status.HTTP_200_OK)


class AuthWorkspaceSelectAPI(APIView):
    """
    POST /api/v1/auth/workspace/select
    Body: {type: 'personal'} | {type: 'worker', employee_id}
    Emite un par de tokens nuevo con el contexto elegido.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def post(self, request):
        try:
            data = select_workspace(
                request.user,
                request.data.get('type') or CTX_PERSONAL,
                employee_id=request.data.get('employee_id'),
            )
        except WorkforceError as e:
            return _workforce_error_response(e)
        return Response(data, status=status.HTTP_200_OK)
