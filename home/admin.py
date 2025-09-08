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
    list_display = ("id", "depo_nomi", "qisqacha_nomi", "joylashuvi", "created_by", "created_at", "image")
    search_fields = ("depo_nomi", "qisqacha_nomi")
    list_filter = ("joylashuvi",)


@admin.register(EhtiyotQismlari)
class EhtiyotQismlariAdmin(admin.ModelAdmin):
    list_display = ("id", "ehtiyotqism_nomi", "nomenklatura_raqami", "created_by", "created_at", "birligi")
    search_fields = ("ehtiyotqism_nomi", "nomenklatura_raqami")


class EhtiyotQismlarInline(admin.TabularInline):
    model = TexnikKorik.ehtiyot_qismlar.through  # through model
    extra = 1

class NosozlikEhtiyotQismlarInline(admin.TabularInline):
    model = Nosozliklar.ehtiyot_qismlar.through  # faqat Nosozliklar uchun
    extra = 1

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
    list_display = ("id", "tarkib", "status", "created_by", "created_at", "approved")
    list_filter = ("status", "created_at", "approved")
    search_fields = ("tarkib__tarkib_raqami", "created_by__username", "bartaraf_etilgan_kamchiliklar")
    exclude = ("ehtiyot_qismlar",)


@admin.register(Nosozliklar)
class NosozliklarAdmin(admin.ModelAdmin):
    list_display = ("id", "tarkib", "status", "created_by", "approved", "aniqlangan_vaqti", "bartarafqilingan_vaqti")
    list_filter = ("status", "approved", "created_at")
    search_fields = ("nosozliklar", "comment", "tarkib__turi", "created_by__username")
    autocomplete_fields = ("tarkib", "ehtiyot_qismlar", "created_by")
    exclude = ("ehtiyot_qismlar",)
