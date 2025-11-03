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
    NosozlikEhtiyotQism,
    NosozlikEhtiyotQismStep,
    KunlikYurish,
    Vagon,
    EhtiyotQismHistory,
    NosozlikTuri,
    TexnikKorikJadval,
    Marshrut,
    YilOy,
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
    # readonly_fields = ["ehtiyot_qism", "miqdor"]

class TexnikKorikEhtiyotQismStepInline(admin.TabularInline):
    model = TexnikKorikEhtiyotQismStep
    extra = 1
    # readonly_fields = ["ehtiyot_qism", "miqdor"]

class NosozlikEhtiyotQismInline(admin.TabularInline):
    model = NosozlikEhtiyotQism
    extra = 1
    # readonly_fields = ["ehtiyot_qism", "miqdor"]

class NosozlikEhtiyotQismStepInline(admin.TabularInline):
    model = NosozlikEhtiyotQismStep
    extra = 1
    # readonly_fields = ["ehtiyot_qism", "miqdor"]

class EhtiyotQismHistoryInline(admin.TabularInline):
    model = EhtiyotQismHistory
    extra = 0
    # readonly_fields = ["miqdor", "created_by", "created_at"]




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
    list_display = ("id", "tamir_nomi","tarkib_turi","akt_check", "tamirlash_davri", "tamirlanish_vaqti", "created_by", "created_at")
    search_fields = ("tamir_nomi",)
    list_filter = ("tamirlash_davri",)


@admin.register(ElektroDepo)
class ElektroDepoAdmin(admin.ModelAdmin):
    list_display = ("id", "depo_nomi", "qisqacha_nomi","depo_rahbari", "joylashuvi", "created_by", "created_at", "image")
    search_fields = ("depo_nomi", "qisqacha_nomi")
    list_filter = ("joylashuvi",)

@admin.register(EhtiyotQismlari)
class EhtiyotQismlariAdmin(admin.ModelAdmin):
    list_display = ("id", "ehtiyotqism_nomi", "nomenklatura_raqami", "birligi", "depo", "jami_miqdor", "created_by", "created_at")
    search_fields = ("ehtiyotqism_nomi", "nomenklatura_raqami")
    inlines = [EhtiyotQismHistoryInline]  # qo'shilgan miqdorlarni tarixini ko'rsatadi
    readonly_fields = ["jami_miqdor"]


@admin.register(Marshrut)
class MarshrutAdmin(admin.ModelAdmin):
    list_display = ("id", "marshrut_raqam")
    search_fields = ("marshrut_raqam",)



@admin.register(YilOy)
class YilOyAdmin(admin.ModelAdmin):
    list_display = ("id", "yil", "oy")
    search_fields = ("yil", "oy")



class VagonInline(admin.TabularInline):
    model = Vagon
    extra = 1


@admin.register(HarakatTarkibi)
class HarakatTarkibiAdmin(admin.ModelAdmin):
    list_display = (
        "id", "tarkib_raqami", "turi", "depo",
        "ishga_tushgan_vaqti", "eksplutatsiya_vaqti", "holati",
        "is_active", "created_by", "created_at",
    )
    search_fields = ("tarkib_raqami", "turi")
    list_filter = ("depo", "holati", "is_active")
    readonly_fields = ("image", "tarkib_raqami")  # ❗ Tarkib raqami endi faqat readonly
    inlines = [VagonInline]

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.role == "texnik":
            obj.depo = request.user.depo
        obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # vagonlar saqlanganidan keyin tarkib_raqami yangilansin
        obj.update_tarkib_raqami()




@admin.register(NosozlikTuri)
class NosozlikTuriAdmin(admin.ModelAdmin):
    list_display = ("nosozlik_turi", "created_at")
    search_fields = ("nosozlik_turi",)

@admin.register(Nosozliklar)
class NosozliklarAdmin(admin.ModelAdmin):
    inlines = [NosozlikEhtiyotQismInline]
    list_display = (
        "id", "tarkib", "status", "created_by", "aniqlangan_vaqti", "bartarafqilingan_vaqti"
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "nosozliklar_haqida__nosozlik_turi",
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
    inlines = [NosozlikEhtiyotQismStepInline]



@admin.register(TexnikKorikJadval)
class TexnikKorikJadvalAdmin(admin.ModelAdmin):
    list_display = ("tarkib","marshrut", "tamir_turi", "sana", "created_by", "created_at")
    list_filter = ("tamir_turi", "tarkib__depo")
    search_fields = ("tarkib__tarkib_raqami",)
    ordering = ("-sana",)