"""Роль «Менеджеры магазина»: только права на модели каталога и заказов, без пользователей."""

from django.contrib.auth.models import Group, Permission

MANAGERS_GROUP = "Менеджеры магазина"

# (app_label, model, действия)
MANAGER_PERMISSIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("catalog", "category", ("view", "add", "change", "delete")),
    ("catalog", "product", ("view", "add", "change", "delete")),
    ("orders", "order", ("view", "change")),
    ("orders", "orderitem", ("view",)),
    ("orders", "paymentattempt", ("view",)),
)


def manager_permission_codenames() -> set[tuple[str, str]]:
    return {
        (app_label, f"{action}_{model}")
        for app_label, model, actions in MANAGER_PERMISSIONS
        for action in actions
    }


def ensure_managers_group() -> Group:
    """Создаёт группу и выставляет ровно нужный набор прав (идемпотентно)."""
    group, _ = Group.objects.get_or_create(name=MANAGERS_GROUP)
    wanted = manager_permission_codenames()
    perms = [
        p
        for p in Permission.objects.select_related("content_type").filter(
            content_type__app_label__in={app for app, _ in wanted}
        )
        if (p.content_type.app_label, p.codename) in wanted
    ]
    if len(perms) == len(wanted):
        group.permissions.set(perms)
    return group
