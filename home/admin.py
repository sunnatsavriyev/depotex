from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    TamirTuri,
    ElektroDepo,
    EhtiyotQismlari,
    HarakatTarkibi,
    TexnikKorik,
    TexnikKorikStep,
    Nosozliklar,
    NosozlikStep,
    TexnikKorikEhtiyotQism,
    TexnikKorikEhtiyotQismStep,
)

# ---------------- Custom User ----------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password", "depo")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role", "depo"),
        }),
    )
    list_display = ("username", "role", "depo", "is_staff", "is_superuser")
    search_fields = ("username",)
    ordering = ("username",)

    def get_fieldsets(self, request, obj=None):
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


# ---------------- Inline Admin ----------------
class TexnikKorikEhtiyotQismInline(admin.TabularInline):
    model = TexnikKorikEhtiyotQism
    extra = 1


class TexnikKorikEhtiyotQismStepInline(admin.TabularInline):
    model = TexnikKorikEhtiyotQismStep
    extra = 1


# ---------------- Texnik Korik ----------------
@admin.register(TexnikKorik)
class TexnikKorikAdmin(admin.ModelAdmin):
    list_display = ("id", "tarkib", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("tarkib__tarkib_raqami", "created_by__username")
    inlines = [TexnikKorikEhtiyotQismInline]  

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == "monitoring":
            return qs
        if request.user.role == "texnik" and request.user.depo:
            return qs.filter(tarkib__depo=request.user.depo)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
 

@admin.register(TexnikKorikStep)
class TexnikKorikStepAdmin(admin.ModelAdmin):
    list_display = ("id", "korik", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("korik__tarkib__tarkib_raqami", "created_by__username")
    inlines = [TexnikKorikEhtiyotQismStepInline]  


# ---------------- Qolganlari ----------------
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
        "id", "tarkib_raqami", "turi", "guruhi", "depo",
        "ishga_tushgan_vaqti", "eksplutatsiya_vaqti", "holati",
        "created_by", "created_at",
    )
    search_fields = ("tarkib_raqami", "turi", "guruhi")
    list_filter = ("depo", "holati")
    readonly_fields = ("image",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == "monitoring":
            return qs
        if request.user.role == "texnik" and request.user.depo:
            return qs.filter(depo=request.user.depo)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.role == "texnik":
            obj.depo = request.user.depo
        obj.created_by = request.user
        super().save_model(request, obj, form, change)


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


@admin.register(NosozlikStep)
class NosozlikStepAdmin(admin.ModelAdmin):
    list_display = ("id", "nosozlik", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("nosozlik__tarkib__tarkib_raqami", "created_by__username")
    autocomplete_fields = ("created_by",)
