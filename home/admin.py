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
    list_display = ("id", "depo_nomi", "qisqacha_nomi", "joylashuvi", "created_by", "created_at")
    search_fields = ("depo_nomi", "qisqacha_nomi")
    list_filter = ("joylashuvi",)


@admin.register(EhtiyotQismlari)
class EhtiyotQismlariAdmin(admin.ModelAdmin):
    list_display = ("id", "ehtiyotqism_nomi", "nomenklatura_raqami", "created_by", "created_at")
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
    list_display = ("id", "tarkib", "depo_nomi", "tamir_turi", "ehtiyot_qism", "kirgan_vaqti", "chiqqan_vaqti","created_by", "created_at")
    search_fields = ("tarkib__tarkib_raqami", "natija")
    list_filter = ("tamir_turi", "kirgan_vaqti")

    def depo_nomi(self, obj):
        return obj.tarkib.depo.depo_nomi
    depo_nomi.short_description = "Depo"


@admin.register(Nosozliklar)
class NosozliklarAdmin(admin.ModelAdmin):
    list_display = ("id", "tarkib", "ehtiyot_qism", "aniqlangan_vaqti", "bartarafqilingan_vaqti", "created_by", "created_at")
    search_fields = ("tarkib__tarkib_raqami", "nosozliklar")
    list_filter = ("aniqlangan_vaqti", "bartarafqilingan_vaqti")
