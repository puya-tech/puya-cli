"""Tests de RBAC — verifica que permissions.yaml se respeta igual que en MCP.

No hace queries a Odoo. Solo testea la lógica de RBACEngine sobre el
permissions.yaml shippeado con el paquete.
"""

from __future__ import annotations

import pytest

from puya.lib.rbac import PermissionDenied, RBACEngine


@pytest.fixture
def rbac():
    return RBACEngine()


# ── vendedor ────────────────────────────────────────────────────────


def test_vendedor_puede_leer_cualquier_modelo(rbac):
    rbac.check_model_access("vendedor", "purchase.order", "search_read")
    rbac.check_model_access("vendedor", "stock.move", "search_read")
    rbac.check_model_access("vendedor", "res.partner", "search_read")


def test_vendedor_puede_escribir_via_wildcard(rbac):
    """vendedor: '*' tiene write/create — pero always_approve=true."""
    rbac.check_model_access("vendedor", "purchase.order", "write")
    rbac.check_model_access("vendedor", "purchase.order", "create")


def test_vendedor_NO_puede_unlink(rbac):
    """unlink no está en la wildcard '*' del rol vendedor."""
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("vendedor", "res.partner", "unlink")


def test_vendedor_always_approve_es_true(rbac):
    assert rbac.always_approve("vendedor") is True


# ── administrativo ──────────────────────────────────────────────────


def test_administrativo_puede_escribir_sale_order(rbac):
    rbac.check_model_access("administrativo", "sale.order", "write")
    rbac.check_model_access("administrativo", "sale.order", "create")


def test_administrativo_solo_lee_purchase_order(rbac):
    """administrativo tiene purchase.order: [search_read] explícito."""
    rbac.check_model_access("administrativo", "purchase.order", "search_read")
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("administrativo", "purchase.order", "write")


def test_administrativo_NO_unlink(rbac):
    """administrativo no puede borrar nada."""
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("administrativo", "sale.order", "unlink")


def test_administrativo_no_always_approve(rbac):
    assert rbac.always_approve("administrativo") is False


# ── developer ──────────────────────────────────────────────────────


def test_developer_puede_todo_via_wildcard(rbac):
    rbac.check_model_access("developer", "anything.model", "search_read")
    rbac.check_model_access("developer", "anything.model", "write")
    rbac.check_model_access("developer", "anything.model", "create")
    rbac.check_model_access("developer", "anything.model", "unlink")


def test_developer_no_always_approve(rbac):
    assert rbac.always_approve("developer") is False


# ── INFRA_BLOCKED_MODELS — hardcoded, ni siquiera developer si es de otro rol ──


def test_vendedor_NO_puede_tocar_ir_config_parameter(rbac):
    """ir.config_parameter contiene secrets — bloqueado para non-developer."""
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("vendedor", "ir.config_parameter", "search_read")


def test_administrativo_NO_puede_tocar_passwords(rbac):
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("administrativo", "change.password.user", "search_read")


def test_developer_SI_puede_ir_config_parameter(rbac):
    """Developer SÍ puede tocar infra-blocked (es escape hatch)."""
    rbac.check_model_access("developer", "ir.config_parameter", "search_read")


# ── Roles inexistentes ─────────────────────────────────────────────


def test_role_inexistente_falla(rbac):
    with pytest.raises(PermissionDenied):
        rbac.check_model_access("rol_inventado", "res.partner", "search_read")


# ── Methods (call/execute) ─────────────────────────────────────────


def test_administrativo_puede_action_confirm_sale_order(rbac):
    """administrativo tiene methods_allowed: ['sale.order:action_confirm', ...]."""
    assert rbac.check_method_access("administrativo", "sale.order", "action_confirm")


def test_vendedor_NO_puede_action_post_invoice(rbac):
    """vendedor no tiene action_post en methods_allowed."""
    assert rbac.check_method_access("vendedor", "account.move", "action_post") is False


def test_developer_puede_cualquier_metodo(rbac):
    """developer: methods_allowed: ['*']"""
    assert rbac.check_method_access("developer", "x.y.z", "cualquier_metodo")
