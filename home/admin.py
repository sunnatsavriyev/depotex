from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    TamirTuri,
    ElektroDepo,
    EhtiyotQismlari,
    HarakatTarkibi,
    TexnikKorik,
    Nosozliklar,
    TexnikKorikStep,
    NosozlikStep
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role"),
        }),
    )

    list_display = ("username", "role", "is_staff", "is_superuser")
    search_fields = ("username",)
    ordering = ("username",)

    def get_fieldsets(self, request, obj=None):
        """
        Superuser uchun role maydonini yashiramiz.
        """
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.is_superuser:
            new_fieldsets = []
            for name, data in fieldsets:
                fields = list(data.get("fields", []))
                if "role" in fields:
                    fields.remove("role")
                new_fieldsets.append((name, {"fields": fields}))
            return new_fieldsets
        return fieldsets

    def get_add_fieldsets(self, request):
        """
        Superuser qo‘shilganda role ni ko‘rsatmaymiz.
        """
        fieldsets = super().get_add_fieldsets(request)
        if request.user.is_superuser:
            new_fieldsets = []
            for name, data in fieldsets:
                fields = list(data.get("fields", []))
                if "role" in fields:
                    fields.remove("role")
                new_fieldsets.append((name, {"fields": fields}))
            return new_fieldsets
        return fieldsets


@admin.register(TamirTuri)
class TamirTuriAdmin(admin.ModelAdmin):
    list_display = ("id", "tamir_nomi", "tamirlash_davri", "tamirlanish_vaqti", "created_by", "created_at")
    search_fields = ("tamir_nomi",)
    list_filter = ("tamirlash_davri",)


@admin.register(ElektroDepo)
class ElektroDepoAdmin(admin.ModelAdmin):
    list_display = ("id", "depo_nomi", "qisqacha_nomi", "joylashuvi", "created_by", "created_at", "image")
    search_fields = ("depo_nomi", "qisqacha_nomi")
    list_filter = ("joylashuvi",)


@admin.register(EhtiyotQismlari)
class EhtiyotQismlariAdmin(admin.ModelAdmin):
    list_display = ("id", "ehtiyotqism_nomi", "nomenklatura_raqami", "created_by", "created_at", "birligi")
    search_fields = ("ehtiyotqism_nomi", "nomenklatura_raqami")


@admin.register(HarakatTarkibi)
class HarakatTarkibiAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tarkib_raqami",
        "turi",
        "guruhi",
        "depo",
        "ishga_tushgan_vaqti",
        "eksplutatsiya_vaqti",
        "holati",
        "created_by",
        "created_at",
    )
    search_fields = ("tarkib_raqami", "turi", "guruhi")
    list_filter = ("depo", "holati")
    readonly_fields = ("image",)  # rasmni ko‘rsatadi lekin tahrir qilmaydi




@admin.register(TexnikKorik)
class TexnikKorikAdmin(admin.ModelAdmin):
    list_display = ("id", "tarkib", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("tarkib__tarkib_raqami", "created_by__username")

@admin.register(TexnikKorikStep)
class TexnikKorikStepAdmin(admin.ModelAdmin):
    list_display = ("id", "korik", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("korik__tarkib__tarkib_raqami", "created_by__username")




# ---------------- Nosozliklar ----------------
@admin.register(Nosozliklar)
class NosozliklarAdmin(admin.ModelAdmin):
    list_display = (
        "id", "tarkib", "status", "created_by", "aniqlangan_vaqti", "bartarafqilingan_vaqti"
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "tarkib__turi",
        "created_by__username"
    )
    autocomplete_fields = ("tarkib", "created_by")
    exclude = ("ehtiyot_qismlar",)


# ---------------- Nosozlik step ----------------
@admin.register(NosozlikStep)
class NosozlikStepAdmin(admin.ModelAdmin):
    list_display = ("id", "nosozlik", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("nosozlik__tarkib__tarkib_raqami", "created_by__username")
    autocomplete_fields = ("created_by",)