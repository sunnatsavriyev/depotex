from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari,Notification, HarakatTarkibi,TexnikKorikJadval, NosozlikNotification,TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism,NosozlikTuri, TexnikKorikStep, TexnikKorikEhtiyotQismStep, NosozlikEhtiyotQismStep, NosozlikStep, KunlikYurish,Vagon,EhtiyotQismHistory
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.db.models import Sum
from django.db import models
import json
from datetime import timedelta
User = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    depo_nomi = serializers.CharField(source="depo.qisqacha_nomi", read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "role", "depo", "depo_nomi"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            role=validated_data["role"],
            depo=validated_data.get("depo")
        )
        return user
    
    
class TamirTuriSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TamirTuri
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)



class ElektroDepoSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ElektroDepo
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)









class KunlikYurishSerializer(serializers.ModelSerializer):
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)  # username chiqadi

    tarkib = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.none(),  
    )
    sana = serializers.DateField(format="%d-%m-%Y")
    class Meta:
        model = KunlikYurish
        fields = ["id", "tarkib", "tarkib_nomi", "sana", "kilometr", "created_by", "created_at"]
        read_only_fields = ["created_by", "created_at"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context["request"].user  
        
        if user.is_authenticated:
                if user.is_superuser:
                    
                    self.fields['tarkib'].queryset = HarakatTarkibi.objects.filter(
                        holati="Soz_holatda"
                    )
                elif user.depo:
                    
                    self.fields['tarkib'].queryset = HarakatTarkibi.objects.filter(
                        holati="Soz_holatda",
                        depo=user.depo
                    )
                else:
                    # Depo bo'lmagan foydalanuvchilar uchun bo'sh queryset
                    self.fields['tarkib'].queryset = HarakatTarkibi.objects.none()

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class VagonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vagon
        fields = [ "vagon_raqami"]


class HarakatTarkibiSerializer(serializers.ModelSerializer):
    depo = serializers.SlugRelatedField(read_only=True, slug_field="qisqacha_nomi")
    depo_id = serializers.PrimaryKeyRelatedField(
        queryset=ElektroDepo.objects.all(), 
        source="depo"
    )
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    ishga_tushgan_vaqti = serializers.DateField(
        format="%d-%m-%Y",
        input_formats=["%d-%m-%Y", "%Y-%m-%d"]  
    )
    total_kilometr = serializers.SerializerMethodField() 
    vagonlar = serializers.SerializerMethodField()

    class Meta:
        model = HarakatTarkibi
        fields = "__all__"
        read_only_fields = [
            "created_by", "created_at", "holati",
            "is_active", "pervious_version","vagonlar" 
        ]

    def update(self, instance, validated_data):
        """ faqat tarkib_raqami o‘zgarganda yangi versiya yaratadi,
        qolgan hollarda oddiy update qiladi """
        request = self.context["request"]

        eski_tarkib_raqami = instance.tarkib_raqami
        yangi_tarkib_raqami = validated_data.get("tarkib_raqami", eski_tarkib_raqami)

        # ✅ agar tarkib_raqami o‘zgarmagan bo‘lsa → oddiy update
        if eski_tarkib_raqami == yangi_tarkib_raqami:
            return super().update(instance, validated_data)

        # ❗ tarkib_raqami o‘zgarsa → eski versiyani deactivate qilamiz
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        depo = validated_data.pop("depo", instance.depo)

        # yangi obyekt yaratamiz
        new_instance = HarakatTarkibi.objects.create(
            **validated_data,
            depo=depo,
            created_by=request.user,
            pervious_version=instance,
            is_active=True,
        )

        # tarkib_raqamini yig‘ish (agar kerak bo‘lsa)
        if hasattr(self, "_yig_vagonlar"):
            new_instance.tarkib_raqami = self._yig_vagonlar(new_instance)
            new_instance.save(update_fields=["tarkib_raqami"])

        return new_instance


    
    
    
    def get_vagonlar(self, obj):
        """tarkib_raqamidan bo‘lib vagonlar ro‘yxatini qaytaradi"""
        if not obj.tarkib_raqami:
            return []
        return [{"vagon_raqami": v} for v in obj.tarkib_raqami.split("-")]
    
    def get_total_kilometr(self, obj):
        if hasattr(obj, "total_kilometr") and obj.total_kilometr is not None:
            return obj.total_kilometr
        return obj.kunlik_yurishlar.aggregate(total=Sum("kilometr"))["total"] or 0

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user 
        return super().create(validated_data)



class HarakatTarkibiActiveSerializer(HarakatTarkibiSerializer):
    class Meta(HarakatTarkibiSerializer.Meta):
        model = HarakatTarkibi
        fields = HarakatTarkibiSerializer.Meta.fields

    
    






class EhtiyotQismlariSerializer(serializers.ModelSerializer):
    depo = serializers.PrimaryKeyRelatedField(queryset=ElektroDepo.objects.all())
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    jami_miqdor = serializers.FloatField(read_only=True)
    depo_nomi = serializers.CharField(source="depo.qisqacha_nomi", read_only=True)

    class Meta:
        model = EhtiyotQismlari
        fields = [
            "id", "created_by", "ehtiyotqism_nomi", "nomenklatura_raqami",
            "birligi", "created_at", "depo","depo_nomi", "jami_miqdor"
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        if hasattr(user, "depo") and user.depo:
            validated_data["depo"] = user.depo
        return super().create(validated_data)


class EhtiyotQismWithMiqdorSerializer(serializers.ModelSerializer):
    miqdor = serializers.SerializerMethodField()
    depo = serializers.CharField(source="depo.qisqacha_nomi", read_only=True)

    class Meta:
        model = EhtiyotQismlari
        fields = ["id", "ehtiyotqism_nomi", "birligi", "depo", "miqdor"]

    def get_miqdor(self, obj):
        total_added = obj.ehtiyotqism_hist.aggregate(
            total=models.Sum('miqdor')
        )['total'] or 0
        return total_added





class EhtiyotQismHistorySerializer(serializers.ModelSerializer):
    miqdor = serializers.FloatField(required=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = EhtiyotQismHistory
        fields = ['id', 'miqdor', 'created_by', 'created_at']
        read_only_fields = ['created_by', 'created_at']


class SlugOrPkRelatedField(serializers.SlugRelatedField):
    """
    Agar frontend raqam (id) yuborsa — pk bo'yicha qidiradi,
    aks holda slug_field bo'yicha qidiradi.
    """
    def to_internal_value(self, data):
        qs = self.get_queryset()
        if isinstance(data, int) or (isinstance(data, str) and data.isdigit()):
            try:
                return qs.get(pk=int(data))
            except Exception:
                pass
        return super().to_internal_value(data)


class TexnikKorikEhtiyotQismSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)
    ehtiyot_qism = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(),  # ID bilan ishlaydi
        required=True
    )

    class Meta:
        model = TexnikKorikEhtiyotQism
        fields = ["id", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]

    def validate(self, attrs):
        eq = attrs.get("ehtiyot_qism")
        if eq and attrs.get("miqdor", 0) > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        eq = validated_data.get("ehtiyot_qism")
        if eq:
            EhtiyotQismHistory.objects.create(
                ehtiyot_qism=eq,
                miqdor=-instance.miqdor,
                created_by=self.context["request"].user
            )
        return instance


class TexnikKorikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)
    ehtiyot_qism = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(),  # ID bilan ishlaydi
        required=True
    )

    class Meta:
        model = TexnikKorikEhtiyotQismStep
        fields = ["id","ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]
        read_only_fields = ["korik_step"]

    def validate(self, attrs):
        eq = attrs.get("ehtiyot_qism")
        if eq and attrs.get("miqdor", 0) > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        eq = validated_data.get("ehtiyot_qism")
        if eq:
            EhtiyotQismHistory.objects.create(
                ehtiyot_qism=eq,
                miqdor=-instance.miqdor,
                created_by=self.context["request"].user
            )
        return instance


class TexnikKorikDetailForStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)

    ehtiyot_qismlar_detail = serializers.SerializerMethodField() 

    class Meta:
        model = TexnikKorik
        fields = [
            "id",
            "tarkib",
            "tarkib_nomi",
            "tamir_turi",
            "tamir_turi_nomi",
            "status",
            "kamchiliklar_haqida",
            "bartaraf_etilgan_kamchiliklar",
            "kirgan_vaqti",
            "chiqqan_vaqti",
            "created_by",
            "created_at",
            "ehtiyot_qismlar_detail",
        ]
        read_only_fields = fields

    def get_ehtiyot_qismlar_detail(self, obj):
        korik_qismlar = [
            {
                "id": item.id,
                "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                "manba": "korik",
            }
            for item in obj.texnikkorikehtiyotqism_set.select_related("ehtiyot_qism").all()
        ]


        return korik_qismlar


    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
        
    #     clean_data = {
    #         k: v for k, v in data.items()
    #         if v not in [None, False, [], {}] and not (isinstance(v, str) and v.strip() == "")
    #     }
    #     return clean_data


class TexnikKorikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)
    korik_nomi = serializers.CharField(source="korik.tarkib.tarkib_raqami", read_only=True)
    
    ehtiyot_qismlar = TexnikKorikEhtiyotQismStepSerializer(
        many=True, write_only=True, required=False, allow_null=True, default=list
    )
    ehtiyot_qismlar_detail = serializers.SerializerMethodField()

    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False)
    akt_file = serializers.FileField( required=False)
    chiqqan_vaqti = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = TexnikKorikStep
        fields = [
            "id", "korik_nomi", "tamir_turi_nomi",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "chiqqan_vaqti", "akt_file",
            "yakunlash", "created_by", "created_at", "password", "status"
        ]
        read_only_fields = ["korik_nomi", "tamir_turi_nomi", "created_by", "created_at", "status", "chiqqan_vaqti"]
        
        
    def get_ehtiyot_qismlar_detail(self, obj):
        step_qismlar = [
            {
                "id": item.id,
                "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                "manba": "step",
            }
            for item in obj.texnikkorikehtiyotqismstep_set.select_related("ehtiyot_qism").all()
        ]
        return step_qismlar





    def validate(self, attrs):
        request = self.context.get("request")
        
        # Password tekshirish
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto'g'ri."})

        # Yakunlash tekshirish
        yakunlash = attrs.get("yakunlash")
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})
        
        # Ehtiyot qismlarni JSON formatda qayta ishlash
        ehtiyot_qismlar = attrs.get("ehtiyot_qismlar", None)
        if ehtiyot_qismlar is None:
            # agar DRF bu fieldni o‘qimagan bo‘lsa (masalan, FormData’da string kelsa)
            ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])

        # 🔹 String holatda kelsa — JSON qilib ochamiz
        if isinstance(ehtiyot_qismlar, str):
            try:
                ehtiyot_qismlar = json.loads(ehtiyot_qismlar)
            except Exception:
                raise serializers.ValidationError({"ehtiyot_qismlar": "Noto‘g‘ri format."})

        # 🔹 Agar hali ham list bo‘lmasa — xato
        elif ehtiyot_qismlar and not isinstance(ehtiyot_qismlar, list):
            raise serializers.ValidationError({"ehtiyot_qismlar": "List formatida bo‘lishi kerak."})

        # ✅ Yakuniy qiymatni to‘g‘rilab yozamiz
        attrs["ehtiyot_qismlar"] = ehtiyot_qismlar or []

        return attrs

    def create(self, validated_data):
        print("\n [CREATE BOSHLANDI]")
        print(" VALIDATED DATA KEYLAR:", list(validated_data.keys()))
        print(" VALIDATED EHTIYOT QISMLAR:", validated_data.get("ehtiyot_qismlar"))
        request = self.context["request"]
        korik = self.context.get("korik")

        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        if not ehtiyot_qismlar:
            raw_data = request.data.get("ehtiyot_qismlar")
            if isinstance(raw_data, str):
                try:
                    ehtiyot_qismlar = json.loads(raw_data)
                except Exception:
                    ehtiyot_qismlar = []
            elif isinstance(raw_data, list):
                ehtiyot_qismlar = raw_data
            else:
                ehtiyot_qismlar = []

        print("✅ YUBORILGAN EHTIYOT QISMLAR:", ehtiyot_qismlar) 

        if yakunlash and akt_file:
            step_status = TexnikKorikStep.Status.BARTARAF_ETILDI
        else:
            step_status = TexnikKorikStep.Status.JARAYONDA

        # Step yaratish
        step = TexnikKorikStep.objects.create(
            korik=korik,
            tamir_turi=korik.tamir_turi,
            created_by=request.user,
            # yakunlash=yakunlash,
            akt_file=akt_file,
            status=step_status,
            **validated_data
        )

        if yakunlash and akt_file:
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI
            korik.tarkib.holati = "Soz_holatda"
            korik.akt_file = akt_file
            korik.chiqqan_vaqti = timezone.now()
            korik.save()
            korik.tarkib.save()

        # Ehtiyot qismlarni stepga bog'lash
        for item in ehtiyot_qismlar:
            eq_val = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_val:
                continue

            # Ehtiyot qismini olish
            if isinstance(eq_val, EhtiyotQismlari):
                eq_obj = eq_val
            else:
                try:
                    eq_obj = EhtiyotQismlari.objects.get(id=int(eq_val))
                except (EhtiyotQismlari.DoesNotExist, ValueError, TypeError):
                    raise serializers.ValidationError({"ehtiyot_qism": f"ID {eq_val} topilmadi"})

            # Omborda yetarli miqdor borligini tekshirish
            if yakunlash and eq_obj.jami_miqdor < miqdor:
                raise serializers.ValidationError({
                    "ehtiyot_qism": f"Omborda yetarli miqdor yo‘q ({eq_obj.jami_miqdor})"
                })

            # Ehtiyot qismni yaratish
            TexnikKorikEhtiyotQismStep.objects.create(
                korik_step=step,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )

            # if yakunlash:
            #     # eq_obj.jami_miqdor -= miqdor
            #     # eq_obj.save()
            #     EhtiyotQismHistory.objects.create(
            #         ehtiyot_qism=eq_obj,
            #         miqdor=-miqdor,
            #         created_by=request.user,
            #         # izoh=f"Texnik ko'rik step yakunlandi (Step ID: {step.id}, Korik ID: {korik.id})"
            #     )

        step.refresh_from_db()
        
        # DEBUG: Ehtiyot qismlarni tekshirish
        step = TexnikKorikStep.objects.prefetch_related(
            'texnikkorikehtiyotqismstep_set__ehtiyot_qism'
        ).get(id=step.id)
        return step


    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Ehtiyot qismlar detailni qo'lda qo'shamiz
        if 'ehtiyot_qismlar_detail' not in data or not data['ehtiyot_qismlar_detail']:
            data['ehtiyot_qismlar_detail'] = self.get_ehtiyot_qismlar_detail(instance)
        
        return data
        






class TexnikKorikSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

 
    tarkib = serializers.PrimaryKeyRelatedField(queryset=HarakatTarkibi.objects.none())

    is_active = serializers.BooleanField(source="tarkib.is_active", read_only=True)
    pervious_version = serializers.SerializerMethodField()
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)

    tamir_turi = serializers.PrimaryKeyRelatedField(queryset=TamirTuri.objects.all())
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)

    # Steps
    steps = serializers.SerializerMethodField()

    # Ehtiyot qismlar
    ehtiyot_qismlar = TexnikKorikEhtiyotQismSerializer(
        many=True,required=False,write_only=True,
    )
    ehtiyot_qismlar_detail = serializers.SerializerMethodField()  
    
    
    

    akt_file = serializers.FileField( required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    chiqqan_vaqti = serializers.DateTimeField(read_only=True)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "tarkib", "tarkib_nomi", "is_active", "pervious_version",
            "tamir_turi", "tamir_turi_nomi", "status",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", 'kirgan_vaqti', "chiqqan_vaqti",
            "akt_file", "yakunlash", "created_by", "created_at", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]


    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tarkib"].queryset = HarakatTarkibi.objects.filter(
            is_active=True,
            holati="Soz_holatda"
        )
    
    
    def get_ehtiyot_qismlar_detail(self, obj):
        korik_qismlar = [
            {
                "id": item.id,
                "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                "manba": "korik",
            }
            for item in obj.texnikkorikehtiyotqism_set.select_related("ehtiyot_qism").all()
        ]

        if getattr(obj, "yakunlash", False):
            for step in obj.steps.all().prefetch_related("texnikkorikehtiyotqismstep_set__ehtiyot_qism"):
                for item in step.texnikkorikehtiyotqismstep_set.all():
                    korik_qismlar.append({
                        "id": item.id,
                        "step_id": step.id,
                        "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                        "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                        "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                        "ishlatilgan_miqdor": item.miqdor,
                        "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                        "manba": "step",
                    })

        return korik_qismlar 




        
        
    
    # --- Serializer metodlari ---
    def get_pervious_version(self, obj):
        return obj.tarkib.pervious_version.id if obj.tarkib and obj.tarkib.pervious_version else None

    def get_tarkib_detail(self, obj):
        return {
            "id": obj.tarkib.id,
            "tarkib_raqami": obj.tarkib.tarkib_raqami,
            "holati": obj.tarkib.holati,
            "is_active": obj.tarkib.is_active,
        }

    def get_steps(self, obj):
        request = self.context.get("request")
        parent_data = TexnikKorikDetailForStepSerializer(obj, context=self.context).data

        parent_data = {
        "id": obj.id,
        "tarkib": obj.tarkib.id,
        "tarkib_nomi": obj.tarkib.tarkib_raqami,
        "tamir_turi": obj.tamir_turi.id,
        "tamir_turi_nomi": obj.tamir_turi.tamir_nomi,
        "status": obj.status,
        "kamchiliklar_haqida": obj.kamchiliklar_haqida,
        "bartaraf_etilgan_kamchiliklar": obj.bartaraf_etilgan_kamchiliklar,
        "kirgan_vaqti": obj.kirgan_vaqti,
        # "chiqqan_vaqti": obj.chiqqan_vaqti,
        "created_by": obj.created_by.username if obj.created_by else None,
        "created_at": obj.created_at,
        "ehtiyot_qismlar_detail": self.get_ehtiyot_qismlar_detail(obj)  
    }

        steps_qs = obj.steps.all().order_by("created_at")
        search = request.query_params.get("search")
        if search:
            steps_qs = steps_qs.filter(
                Q(kamchiliklar_haqida__icontains=search) |
                Q(bartaraf_etilgan_kamchiliklar__icontains=search)
            )

        paginator = StepPagination()
        page = paginator.paginate_queryset(steps_qs, request)

        steps_data = TexnikKorikStepSerializer(
            page if page is not None else steps_qs, 
            many=True, context=self.context
        ).data

        # 🔹 Natija: parent korik + steps
        if page is not None:
            return {
                "count": paginator.page.paginator.count + 1,
                "num_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": [parent_data] + steps_data,
            }
        else:
            return {
                "count": steps_qs.count() + 1,
                "num_pages": 1,
                "current_page": 1,
                "next": None,
                "previous": None,
                "results": [parent_data] + steps_data,
            }


            

    def validate(self, attrs):
        request = self.context.get("request")
        
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash")
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})

        ehtiyot_qismlar = attrs.get("ehtiyot_qismlar", None)
        if ehtiyot_qismlar is None:
            ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])

        if isinstance(ehtiyot_qismlar, str):
            try:
                ehtiyot_qismlar = json.loads(ehtiyot_qismlar)
            except Exception:
                raise serializers.ValidationError({"ehtiyot_qismlar": "Noto‘g‘ri format."})

        # 🔹 Agar hali ham list bo‘lmasa — xato
        elif ehtiyot_qismlar and not isinstance(ehtiyot_qismlar, list):
            raise serializers.ValidationError({"ehtiyot_qismlar": "List formatida bo‘lishi kerak."})

        # 🔹 Yakuniy qiymatni qayta yozamiz
        attrs["ehtiyot_qismlar"] = ehtiyot_qismlar or []

        return attrs



    
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ehtiyot qismlar detailni qayta hisoblash
        if 'ehtiyot_qismlar_detail' in data:
            data['ehtiyot_qismlar_detail'] = self.get_ehtiyot_qismlar_detail(instance)
        
        # Steps ma'lumotlarini qayta hisoblash
        if 'steps' in data:
            data['steps'] = self.get_steps(instance)
        
        # Faqat None va False qiymatlarni o'chirish
        
        return data
    
    
    # --- CREATE ---
    def create(self, validated_data):
        print("\n [CREATE BOSHLANDI]")
        print(" VALIDATED DATA KEYLAR:", list(validated_data.keys()))
        print(" VALIDATED EHTIYOT QISMLAR:", validated_data.get("ehtiyot_qismlar"))
        request = self.context["request"]

        tarkib = validated_data.pop("tarkib")
        tamir_turi = validated_data.pop("tamir_turi")
        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        if not ehtiyot_qismlar:
            raw_data = request.data.get("ehtiyot_qismlar")
            if isinstance(raw_data, str):
                try:
                    ehtiyot_qismlar = json.loads(raw_data)
                except Exception:
                    ehtiyot_qismlar = []
            elif isinstance(raw_data, list):
                ehtiyot_qismlar = raw_data
            else:
                ehtiyot_qismlar = []

        print("✅ YUBORILGAN EHTIYOT QISMLAR:", ehtiyot_qismlar)


        if yakunlash and akt_file:
            status = TexnikKorik.Status.BARTARAF_ETILDI
            tarkib_holati = "Soz_holatda"
        else:
            status = TexnikKorik.Status.JARAYONDA
            tarkib_holati = "Texnik_korikda"

        # Korik yaratish
        korik = TexnikKorik.objects.create(
            tarkib=tarkib,
            tamir_turi=tamir_turi,
            created_by=request.user,
            status=status,  
            yakunlash=yakunlash,
            akt_file=akt_file if akt_file else None,
            **validated_data
        )

        # Tarkib holatini yangilash
        korik.tarkib.holati = tarkib_holati
        korik.tarkib.save()

        # Ehtiyot qismlarni yaratish
        for item in ehtiyot_qismlar:
            eq_val = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_val:
                continue

            # Ehtiyot qismini olish
            if isinstance(eq_val, EhtiyotQismlari):
                eq_obj = eq_val
            else:
                try:
                    eq_obj = EhtiyotQismlari.objects.get(id=int(eq_val))
                except (EhtiyotQismlari.DoesNotExist, ValueError, TypeError):
                    raise serializers.ValidationError({"ehtiyot_qism": f"ID {eq_val} topilmadi"})


            # Ehtiyot qismni yaratish
            TexnikKorikEhtiyotQism.objects.create(
                korik=korik,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )

            # Yakunlash bo'lsa ombordan chiqarish
            # if yakunlash:
            #     eq_obj.jami_miqdor -= miqdor
            #     eq_obj.save()
            #     EhtiyotQismHistory.objects.create(
            #         ehtiyot_qism=eq_obj,
            #         miqdor=-miqdor,
            #         created_by=request.user,
            #         # izoh=f"Texnik ko'rik yakunlandi (ID: {korik.id})"
            #     )

        # Yakunlash bo'lsa qo'shimcha yangilashlar
        if yakunlash and akt_file:
            korik.akt_file = akt_file
            korik.chiqqan_vaqti = timezone.now()
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI   
            korik.save()
        
        # DEBUG: Ehtiyot qismlarni tekshirish
        korik = TexnikKorik.objects.prefetch_related(
            'texnikkorikehtiyotqism_set__ehtiyot_qism',
            'steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism'
        ).get(id=korik.id)
        return korik







    # --- UPDATE ---
    def update(self, instance, validated_data):
        request = self.context["request"]
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        akt_file = validated_data.pop("akt_file", None)
        yakunlash = validated_data.pop("yakunlash", False)

        if akt_file:
            instance.akt_file = akt_file
            
        instance.yakunlash = yakunlash

        if yakunlash and akt_file:
            instance.status = TexnikKorik.Status.BARTARAF_ETILDI
            instance.tarkib.holati = "Soz_holatda"
            if not instance.chiqqan_vaqti:
                instance.chiqqan_vaqti = timezone.now()
        else:
            instance.tarkib.holati = "Texnik_korikda"

        instance.tarkib.save()
        instance = super().update(instance, validated_data)

        for item in ehtiyot_qismlar:
            eq_id = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_id:
                continue

            try:
                eq_obj = EhtiyotQismlari.objects.get(id=eq_id)
            except EhtiyotQismlari.DoesNotExist:
                continue

            # 🔹 oldin mavjud bo‘lsa update, bo‘lmasa create qiladi
            obj, created = TexnikKorikEhtiyotQism.objects.update_or_create(
                korik=instance,
                ehtiyot_qism=eq_obj,
                defaults={"miqdor": miqdor}
            )

            # if yakunlash:
            #     # Har doim ombordan chiqarish (miqdor farqiga qaramasdan)
            #     eq_obj.jami_miqdor -= miqdor
            #     eq_obj.save()
            #     EhtiyotQismHistory.objects.create(
            #         ehtiyot_qism=eq_obj,
            #         miqdor=-miqdor,
            #         created_by=request.user,
            #         # izoh=f"Texnik ko'rik yangilandi (ID: {instance.id})"
            #     )

        return instance





class StepPagination(PageNumberPagination):
    page_size_query_param = "limit"
    max_page_size = 500000000000

    def get_paginated_response(self, data):
        return {
            "count": self.page.paginator.count,
            "num_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        }


       


# --- Nosozlik Ehtiyot Qism (parent level) ---
class NosozlikEhtiyotQismSerializer(serializers.ModelSerializer):
    # faqat read-only maydonlar
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    # ID orqali keladi
    ehtiyot_qism = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all()
    )

    class Meta:
        model = NosozlikEhtiyotQism
        fields = ["id", "nosozlik", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]
        read_only_fields = ["id", "nosozlik", "ehtiyot_qism_nomi", "birligi"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        # nosozlik instance-ni context orqali olamiz
        nosozlik = self.context.get("nosozlik")
        if not nosozlik:
            raise serializers.ValidationError("Nosozlik konteksti yo‘q")

        instance = NosozlikEhtiyotQism.objects.create(
            nosozlik=nosozlik,
            **validated_data
        )

        # History yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance



class NosozlikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    # ID orqali keladi
    ehtiyot_qism = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all()
    )

    class Meta:
        model = NosozlikEhtiyotQismStep
        fields = ["id", "step", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]
        read_only_fields = ["step", "ehtiyot_qism_nomi", "birligi", "id"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        # Step instance-ni context orqali olamiz
        step = self.context.get("step")
        if not step:
            raise serializers.ValidationError("Step konteksti yo‘q")

        instance = NosozlikEhtiyotQismStep.objects.create(
            step=step,
            **validated_data
        )

        # History yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance




class NosozlikTuriSerializer(serializers.ModelSerializer):
    class Meta:
        model = NosozlikTuri
        fields = ["id", "nosozlik_turi", "created_at"]
        read_only_fields = ["id", "created_at"]



# --- parent detail for steps (joylashuvi: step va parent serializerlardan OLDIN yozing) ---
class NosozlikDetailForStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    is_active = serializers.BooleanField(source="tarkib.is_active", read_only=True)

    # parent-level ehtiyot qismlar
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismSerializer(
        source="nosozlikehtiyotqism_set", many=True, read_only=True
    )

    status = serializers.CharField(read_only=True)

    class Meta:
        model = Nosozliklar
        fields = [
            "id",
            "tarkib",
            "tarkib_nomi",
            "is_active",
            "nosozliklar_haqida",
            "bartaraf_etilgan_nosozliklar",
            "ehtiyot_qismlar_detail",
            "status",
            "created_by",
            "created_at"
        ]
        read_only_fields = fields

    # def to_representation(self, instance):
    #     data = super().to_representation(instance)

    #     # Parent-level ehtiyot qismlarni id bilan obyekt sifatida chiqarish
    #     if hasattr(instance, "nosozlikehtiyotqism_set"):
    #         data["ehtiyot_qismlar_detail"] = [
    #             {
    #                 "id": item.id,
    #                 "ehtiyot_qism": item.ehtiyot_qism.id,  # id bilan
    #                 "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi,
    #                 "birligi": item.ehtiyot_qism.birligi,
    #                 "miqdor": item.miqdor
    #             }
    #             for item in instance.nosozlikehtiyotqism_set.all()
    #         ]

    #     # Bo‘sh yoki None qiymatlarni olib tashlash
    #     clean_data = {
    #         k: v for k, v in data.items()
    #         if v not in [None, False, [], {}] and not (isinstance(v, str) and v.strip() == "")
    #     }
    #     return clean_data


class NosozlikNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NosozlikNotification
        fields = "__all__"


# --- Step Serializer ---
class NosozlikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    nosozlik = serializers.PrimaryKeyRelatedField(
        queryset=Nosozliklar.objects.all(), write_only=True
    )
    nosozlik_nomi = serializers.CharField(source="nosozlik.tarkib.tarkib_raqami", read_only=True)

    ehtiyot_qismlar = NosozlikEhtiyotQismStepSerializer(many=True, write_only=True, required=False, allow_null=True, default=list)
    ehtiyot_qismlar_detail = serializers.SerializerMethodField()
    nosozliklar_haqida = serializers.SlugRelatedField(
        slug_field="nosozlik_turi",
        queryset=NosozlikTuri.objects.all(),
        required=False,
        allow_null=True
    )

    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField( required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False)
    bartaraf_qilingan_vaqti = serializers.DateTimeField(required=False, read_only=True)

    class Meta:
        model = NosozlikStep
        fields = [
            "id", "nosozlik", "nosozlik_nomi",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "akt_file", "yakunlash", "bartaraf_qilingan_vaqti",
            "created_by", "created_at", "password", "status"
        ]
        read_only_fields = ["created_by", "created_at", "status"]
        
        
        
    def get_ehtiyot_qismlar_detail(self, obj):
        step_qismlar = [
            {
                "id": item.id,
                "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                "manba": "step",
            }
            for item in obj.ehtiyot_qismlar_step.select_related("ehtiyot_qism").all()
        ]
        return step_qismlar

    def validate(self, attrs):
        request = self.context.get("request")

        password = attrs.pop("password", None)
        if not request.user.is_authenticated or not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})

        vaqt = attrs.get("bartaraf_qilingan_vaqti")
        if vaqt:
            if not yakunlash:
                raise serializers.ValidationError({"yakunlash": "Vaqt belgilash uchun yakunlash majburiy."})
            if not akt_file:
                raise serializers.ValidationError({"akt_file": "Vaqt belgilash uchun akt fayl majburiy."})

        if yakunlash and akt_file and not vaqt:
            attrs["bartaraf_qilingan_vaqti"] = timezone.now()

        ehtiyot_qismlar = attrs.get("ehtiyot_qismlar", None)
        if ehtiyot_qismlar is None:
            ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])

        if isinstance(ehtiyot_qismlar, str):
            try:
                ehtiyot_qismlar = json.loads(ehtiyot_qismlar)
            except Exception:
                raise serializers.ValidationError({"ehtiyot_qismlar": "Noto‘g‘ri format."})
        elif ehtiyot_qismlar and not isinstance(ehtiyot_qismlar, list):
            raise serializers.ValidationError({"ehtiyot_qismlar": "List formatida bo‘lishi kerak."})

        attrs["ehtiyot_qismlar"] = ehtiyot_qismlar or []

        return attrs


    def create(self, validated_data):
        print("\n [CREATE BOSHLANDI - NOSOZLIK STEP]")
        print(" VALIDATED DATA KEYLAR:", list(validated_data.keys()))
        print(" VALIDATED EHTIYOT QISMLAR:", validated_data.get("ehtiyot_qismlar"))

        request = self.context["request"]

        # validated_data ichidan nosozlikni olib qo'yamiz (ikki marta kirmasin)
        nosozlik = validated_data.pop("nosozlik", None)
        if not nosozlik:
            raise serializers.ValidationError({"nosozlik": "Nosozlik tanlanmagan."})

        yakunlash = validated_data.pop("yakunlash", False)
        bartaraf_qilingan_vaqti = validated_data.pop("bartarafqilingan_vaqti", None)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
    
        nosozliklar_haqida_data = validated_data.pop("nosozliklar_haqida", None)
        
        if nosozliklar_haqida_data:
            if isinstance(nosozliklar_haqida_data, NosozlikTuri):
                nosozlik_turi = nosozliklar_haqida_data
            else:
                nosozlik_turi, _ = NosozlikTuri.objects.get_or_create(
                    nosozliklar_haqida=str(nosozliklar_haqida_data)
                )
        else:
            nosozlik_turi = None

        # FormData yoki string bo‘lsa – JSON qilib ochish
        if not ehtiyot_qismlar:
            raw_data = request.data.get("ehtiyot_qismlar")
            if isinstance(raw_data, str):
                try:
                    ehtiyot_qismlar = json.loads(raw_data)
                except Exception:
                    ehtiyot_qismlar = []
            elif isinstance(raw_data, list):
                ehtiyot_qismlar = raw_data
            else:
                ehtiyot_qismlar = []

        print("YUBORILGAN EHTIYOT QISMLAR:", ehtiyot_qismlar)

        # Step statusini aniqlash
        if yakunlash and akt_file:
            step_status = NosozlikStep.Status.BARTARAF_ETILDI
        else:
            step_status = NosozlikStep.Status.JARAYONDA

        # 🔹 Step yaratish — endi faqat 1 ta nosozlik qiymati bilan
        step = NosozlikStep.objects.create(
            nosozlik=nosozlik,
            nosozliklar_haqida=nosozlik_turi,
            created_by=request.user,
            akt_file=akt_file,
            status=step_status,
            **validated_data
        )

        # Ehtiyot qismlarni stepga bog‘lash
        for item in ehtiyot_qismlar:
            eq_val = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_val:
                continue

            # Ehtiyot qismini olish
            if isinstance(eq_val, EhtiyotQismlari):
                eq_obj = eq_val
            else:
                try:
                    eq_obj = EhtiyotQismlari.objects.get(id=int(eq_val))
                except (EhtiyotQismlari.DoesNotExist, ValueError, TypeError):
                    raise serializers.ValidationError({"ehtiyot_qism": f"ID {eq_val} topilmadi"})

            # Omborda yetarli miqdor borligini tekshirish
            if yakunlash and eq_obj.jami_miqdor < miqdor:
                raise serializers.ValidationError({
                    "ehtiyot_qism": f"Omborda yetarli miqdor yo‘q ({eq_obj.jami_miqdor})"
                })

            # Stepga ehtiyot qism yozish
            NosozlikEhtiyotQismStep.objects.create(
                step=step,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )
            
            
            # if yakunlash:  
            #     eq_obj.jami_miqdor -= miqdor
            #     if eq_obj.jami_miqdor < 0:
            #         eq_obj.jami_miqdor = 0
            #     eq_obj.save()

            #     EhtiyotQismHistory.objects.create(
            #         ehtiyot_qism=eq_obj,
            #         miqdor=miqdor,
            #         created_by=request.user
            #     )

        # Nosozlik holatini yangilash
        if yakunlash and akt_file:

            if not bartaraf_qilingan_vaqti:
                step.bartaraf_qilingan_vaqti = timezone.now()

            step.save()
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save()
            nosozlik.save()
        else:
            if nosozlik.tarkib.holati != "Nosozlikda":
                nosozlik.tarkib.holati = "Nosozlikda"
                nosozlik.tarkib.save()

        step.refresh_from_db()
        
        
        # 🔹 Nosozlik paydo bo‘lganda notification yozish (xato tashlamasdan)
        try:
            if step.nosozlik and step.nosozlik.nosozliklar_haqida:
                tarkib = step.nosozlik.tarkib
                nosozlik_turi = step.nosozlik.nosozliklar_haqida.nosozlik_turi

                notif = (
                    NosozlikNotification.objects
                    .filter(tarkib=tarkib, nosozlik_turi=nosozlik_turi)
                    .order_by("id")
                    .first()
                )

                if notif:
                    notif.count = (notif.count or 0) + 1
                    notif.last_occurrence = timezone.now()
                    notif.message = (
                        f"{tarkib} tarkibida {nosozlik_turi} nosozligi "
                        f"{notif.count} marta takrorlandi."
                    )
                    notif.save(update_fields=["count", "last_occurrence", "message"])
                else:
                    NosozlikNotification.objects.create(
                        tarkib=tarkib,
                        nosozlik_turi=nosozlik_turi,
                        count=1,
                        first_occurrence=timezone.now(),
                        last_occurrence=timezone.now(),
                        message=f"{tarkib} tarkibida {nosozlik_turi} nosozligi aniqlandi.",
                    )

        except Exception as e:
            # ⚠️ Xato bo‘lsa ham, hech narsa to‘xtamasin
            print(f"⚠️ NosozlikNotification yozishda xatolik: {e}")
            pass




        return step



    def to_representation(self, instance):
        data = super().to_representation(instance)

        if "ehtiyot_qismlar_detail" not in data or not data["ehtiyot_qismlar_detail"]:
            data["ehtiyot_qismlar_detail"] = self.get_ehtiyot_qismlar_detail(instance)

        
        return data



class NosozliklarSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.filter(is_active=True, holati="Soz_holatda")
    )
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    is_active = serializers.BooleanField(source="tarkib.is_active", read_only=True)

    ehtiyot_qismlar = NosozlikEhtiyotQismSerializer(
        many=True, write_only=True, required=False
    )
    ehtiyot_qismlar_detail = serializers.SerializerMethodField()
    nosozliklar_haqida = serializers.SlugRelatedField(
        slug_field="nosozlik_turi",
        queryset=NosozlikTuri.objects.all(),
        required=False,
        allow_null=True
    )
    pervious_version = serializers.SerializerMethodField()
    akt_file = serializers.FileField(required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    bartarafqilingan_vaqti = serializers.DateTimeField(read_only=True)

    steps = serializers.SerializerMethodField()

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "tarkib", "tarkib_nomi", "is_active","pervious_version",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "status", "aniqlangan_vaqti", "bartarafqilingan_vaqti",
            "created_by", "created_at",
            "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "akt_file", "yakunlash", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tarkib"].queryset = HarakatTarkibi.objects.filter(
            is_active=True,
            holati="Soz_holatda"
        )


    
    # --- DETAIL uchun ehtiyot qismlar ---
    def get_ehtiyot_qismlar_detail(self, obj):
        nosozlik_qismlar = [
            {
                "id": item.id,
                "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                "manba": "nosozlik",
            }
            for item in obj.ehtiyot_qism_aloqalari.select_related("ehtiyot_qism").all()
        ]

        if getattr(obj, "yakunlash", False):
            for step in obj.steps.all().prefetch_related("ehtiyot_qismlar_step__ehtiyot_qism"):
                for item in step.ehtiyot_qismlar_step.all():
                    nosozlik_qismlar.append({
                        "id": item.id,
                        "step_id": step.id,
                        "ehtiyot_qism": item.ehtiyot_qism.id if item.ehtiyot_qism else None,
                        "ehtiyot_qism_nomi": item.ehtiyot_qism.ehtiyotqism_nomi if item.ehtiyot_qism else None,
                        "birligi": item.ehtiyot_qism.birligi if item.ehtiyot_qism else None,
                        "ishlatilgan_miqdor": item.miqdor,
                        "qoldiq": item.ehtiyot_qism.jami_miqdor if item.ehtiyot_qism else None,
                        "manba": "step",
                    })
        return nosozlik_qismlar

    
    def get_pervious_version(self, obj):
        return obj.tarkib.pervious_version.id if obj.tarkib and obj.tarkib.pervious_version else None


    def get_tarkib_detail(self, obj):
        return {
            "id": obj.tarkib.id,
            "tarkib_raqami": obj.tarkib.tarkib_raqami,
            "holati": obj.tarkib.holati,
            "is_active": obj.tarkib.is_active,
        }

    
    
    # --- STEPS ---
    def get_steps(self, obj):
        request = self.context.get("request")
        parent_data = {
            "id": obj.id,
            "tarkib": obj.tarkib.id,
            "tarkib_nomi": obj.tarkib.tarkib_raqami,
            "status": obj.status,
            "nosozliklar_haqida": obj.nosozliklar_haqida.nosozlik_turi if obj.nosozliklar_haqida else None,
            "bartaraf_etilgan_nosozliklar": obj.bartaraf_etilgan_nosozliklar,
            "aniqlangan_vaqti": obj.aniqlangan_vaqti,
            "bartarafqilingan_vaqti": obj.bartarafqilingan_vaqti,
            "created_by": obj.created_by.username if obj.created_by else None,
            "created_at": obj.created_at,
            "ehtiyot_qismlar_detail": self.get_ehtiyot_qismlar_detail(obj)
        }

        steps_qs = obj.steps.all().order_by("created_at")
        search = request.query_params.get("search")
        if search:
            steps_qs = steps_qs.filter(
                Q(nosozliklar_haqida__nosozlik_turi__icontains=search) | 
                Q(bartaraf_etilgan_nosozliklar__icontains=search)
            )

        paginator = StepPagination()
        page = paginator.paginate_queryset(steps_qs, request)

        steps_data = NosozlikStepSerializer(
            page if page is not None else steps_qs,
            many=True, context=self.context
        ).data

        if page is not None:
            return {
                "count": paginator.page.paginator.count + 1,
                "num_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": [parent_data] + steps_data,
            }
        else:
            return {
                "count": steps_qs.count() + 1,
                "num_pages": 1,
                "current_page": 1,
                "next": None,
                "previous": None,
                "results": [parent_data] + steps_data,
            }

    # --- VALIDATE ---
    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash")
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})

        ehtiyot_qismlar = attrs.get("ehtiyot_qismlar", None)
        if ehtiyot_qismlar is None:
            ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])

        # 🔹 JSON string bo‘lsa, JSON.parse qilib olamiz
        if isinstance(ehtiyot_qismlar, str):
            try:
                ehtiyot_qismlar = json.loads(ehtiyot_qismlar)
            except Exception:
                raise serializers.ValidationError({"ehtiyot_qismlar": "Noto‘g‘ri format."})

        # 🔹 List bo‘lishi shart
        if ehtiyot_qismlar and not isinstance(ehtiyot_qismlar, list):
            raise serializers.ValidationError({"ehtiyot_qismlar": "List formatida bo‘lishi kerak."})

        # 🔹 Har bir elementni tozalaymiz / to‘g‘rilaymiz
        cleaned_list = []
        for item in ehtiyot_qismlar:
            if not isinstance(item, dict):
                continue
            eq_val = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)

            # ✅ Agar ehtiyot_qism obyekti bo‘lsa — id olamiz
            if isinstance(eq_val, EhtiyotQismlari):
                eq_val = eq_val.id

            # ✅ Agar ehtiyot_qism dict bo‘lsa — undan id olamiz
            elif isinstance(eq_val, dict):
                eq_val = eq_val.get("id")

            # ✅ Agar id raqamli bo‘lmasa, urinish
            try:
                eq_val = int(eq_val) if eq_val else None
            except (ValueError, TypeError):
                eq_val = None

            # ✅ Miqdorni floatga o‘giramiz
            try:
                miqdor = float(miqdor)
            except (ValueError, TypeError):
                miqdor = 1

            if eq_val:
                cleaned_list.append({"ehtiyot_qism": eq_val, "miqdor": miqdor})

        attrs["ehtiyot_qismlar"] = cleaned_list
        print("✅ TOZALANGAN EHTIYOT QISMLAR:", cleaned_list)
        return attrs


    # --- CREATE ---
    def create(self, validated_data):
        print("\n [CREATE NOSOZLIK BOSHLANDI]")
        print(" VALIDATED DATA:", list(validated_data.keys()))
        request = self.context["request"]

        tarkib = validated_data.pop("tarkib")
        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        bartarafqilingan_vaqti = validated_data.pop("bartarafqilingan_vaqti", None)
        aniqlangan_vaqti = validated_data.get("aniqlangan_vaqti", None)
        nosozliklar_haqida_data = validated_data.pop("nosozliklar_haqida", None)  

        # 🔹 Nosozlik turi yaratish / olish
        if nosozliklar_haqida_data:
            if isinstance(nosozliklar_haqida_data, NosozlikTuri):
                nosozlik_turi = nosozliklar_haqida_data
            else:
                nosozlik_turi, _ = NosozlikTuri.objects.get_or_create(
                    nosozliklar_haqida=str(nosozliklar_haqida_data)
                )
        else:
            nosozlik_turi = None

        if not ehtiyot_qismlar:
            raw_data = request.data.get("ehtiyot_qismlar")
            if isinstance(raw_data, str):
                try:
                    ehtiyot_qismlar = json.loads(raw_data)
                except Exception:
                    ehtiyot_qismlar = []
            elif isinstance(raw_data, list):
                ehtiyot_qismlar = raw_data
            else:
                ehtiyot_qismlar = []

        print(" YUBORILGAN EHTIYOT QISMLAR:", ehtiyot_qismlar)

        if yakunlash and akt_file:
            status = Nosozliklar.Status.BARTARAF_ETILDI
            tarkib_holati = "Soz_holatda"
        else:
            status = Nosozliklar.Status.JARAYONDA
            tarkib_holati = "Nosozlikda"

        nosozlik = Nosozliklar.objects.create(
            tarkib=tarkib,
            nosozliklar_haqida=nosozlik_turi,
            created_by=request.user,
            status=status,
            yakunlash=yakunlash,
            akt_file=akt_file if akt_file else None,
            **validated_data
        )

        nosozlik.tarkib.holati = tarkib_holati
        nosozlik.tarkib.save()

        for item in ehtiyot_qismlar:
            eq_val = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_val:
                continue
            try:
                eq_obj = EhtiyotQismlari.objects.get(id=int(eq_val))
            except (EhtiyotQismlari.DoesNotExist, ValueError, TypeError):
                raise serializers.ValidationError({"ehtiyot_qism": f"ID {eq_val} topilmadi"})

            NosozlikEhtiyotQism.objects.create(
                nosozlik=nosozlik,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )

        if aniqlangan_vaqti:
            nosozlik.aniqlangan_vaqti = aniqlangan_vaqti
        else:
            nosozlik.aniqlangan_vaqti = nosozlik.created_at 

        
        if yakunlash and akt_file:
            if bartarafqilingan_vaqti:
                nosozlik.bartarafqilingan_vaqti = bartarafqilingan_vaqti
            else:
                nosozlik.bartarafqilingan_vaqti = nosozlik.created_at

        nosozlik.save()
                
            
        try:
            if nosozlik.nosozliklar_haqida:
                tarkib = nosozlik.tarkib
                nosozlik_turi = nosozlik.nosozliklar_haqida.nosozlik_turi

                # Bir nechta mavjud bo‘lsa — eng birinchisini olish
                notif = (
                    NosozlikNotification.objects
                    .filter(tarkib=tarkib, nosozlik_turi=nosozlik_turi)
                    .order_by("id")
                    .first()
                )

                if notif:
                    notif.count = (notif.count or 0) + 1
                    notif.last_occurrence = timezone.now()
                    notif.message = (
                        f"{tarkib} tarkibida {nosozlik_turi} nosozligi "
                        f"{notif.count} marta takrorlandi."
                    )
                    notif.save(update_fields=["count", "last_occurrence", "message"])
                else:
                    NosozlikNotification.objects.create(
                        tarkib=tarkib,
                        nosozlik_turi=nosozlik_turi,
                        count=1,
                        first_occurrence=timezone.now(),
                        last_occurrence=timezone.now(),
                        message=f"{tarkib} tarkibida {nosozlik_turi} nosozligi aniqlandi.",
                    )

        except Exception as e:
            print(f"⚠️ NosozlikNotification yozishda xatolik: {e}")
            pass
        return nosozlik

    # --- UPDATE ---
    def update(self, instance, validated_data):
        request = self.context["request"]
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        akt_file = validated_data.pop("akt_file", None)
        yakunlash = validated_data.pop("yakunlash", False)

        if akt_file:
            instance.akt_file = akt_file
        instance.yakunlash = yakunlash

        if yakunlash and akt_file:
            instance.status = Nosozliklar.Status.BARTARAF_ETILDI
            instance.tarkib.holati = "Soz_holatda"
            if not instance.bartarafqilingan_vaqti:
                instance.bartarafqilingan_vaqti = timezone.now()
        else:
            instance.tarkib.holati = "Nosozlikda"

        instance.tarkib.save()
        instance = super().update(instance, validated_data)

        for item in ehtiyot_qismlar:
            eq_id = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if not eq_id:
                continue
            try:
                eq_obj = EhtiyotQismlari.objects.get(id=eq_id)
            except EhtiyotQismlari.DoesNotExist:
                continue

            obj, created = NosozlikEhtiyotQism.objects.update_or_create(
                nosozlik=instance,
                ehtiyot_qism=eq_obj,
                defaults={"miqdor": miqdor}
            )

        return instance

    # --- REPRESENTATION ---
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'ehtiyot_qismlar_detail' in data:
            data['ehtiyot_qismlar_detail'] = self.get_ehtiyot_qismlar_detail(instance)
        if 'steps' in data:
            data['steps'] = self.get_steps(instance)
        
        return data




    
    


    
    
class HarakatTarkibiDetailSerializer(serializers.ModelSerializer):
    vagonlar = VagonSerializer(many=True, read_only=True, source="vagonlar")  
    koriklar = TexnikKorikSerializer(many=True, read_only=True, source="texnikkorik_set")
    nosozliklar = NosozliklarSerializer(many=True, read_only=True, source="nosozliklar_set")
    versions = serializers.SerializerMethodField()

    class Meta:
        model = HarakatTarkibi
        fields = "__all__"

    def get_versions(self, obj):
        qs = HarakatTarkibi.objects.filter(tarkib_raqami=obj.tarkib_raqami).order_by("-id")
        return HarakatTarkibiSerializer(qs, many=True).data
    
    

class TarkibFullDetailSerializer(serializers.ModelSerializer):
    texnik_koriklar = serializers.SerializerMethodField()
    nosozliklar = serializers.SerializerMethodField()
    tamir_turi_soni = serializers.SerializerMethodField()
    depo_nomi = serializers.CharField(source="depo.qisqacha_nomi", read_only=True)
    tarkib_photo = serializers.ImageField(source="image", read_only=True)
    tarkib_nomi = serializers.CharField(source="tarkib_raqami", read_only=True)

    class Meta:
        model = HarakatTarkibi
        fields = [
            "id",
            "tarkib_nomi",
            "depo_nomi",
            "guruhi",
            "turi",
            "holati",
            "tarkib_photo",
            "ishga_tushgan_vaqti",
            "eksplutatsiya_vaqti",
            "created_at",
            "texnik_koriklar",
            "nosozliklar",
            "tamir_turi_soni",
            "is_active",
            "pervious_version",
            "created_by",
        ]

    def get_texnik_koriklar(self, obj):
        koriklar = TexnikKorik.objects.filter(tarkib=obj)
        return TexnikKorikDetailForStepSerializer(koriklar, many=True, context=self.context).data

    def get_nosozliklar(self, obj):
        nosozliklar = Nosozliklar.objects.filter(tarkib=obj)
        result = []
        for n in nosozliklar:
            result.append({
                "id": n.id,
                "tarkib": n.tarkib.id if n.tarkib else None,
                "tarkib_nomi": getattr(n.tarkib, "tarkib_raqami", None),
                "is_active": n.is_active,
                "nosozlik_turi_id": getattr(n.nosozliklar_haqida, "id", None),
                "nosozlik_turi": getattr(n.nosozliklar_haqida, "nosozlik_turi", None),
                "bartaraf_etilgan_nosozliklar": n.bartaraf_etilgan_nosozliklar,
                "status": n.status,
                "bartaraf_qilingan_vaqti": n.bartaraf_qilingan_vaqti,
                "created_by": getattr(n.created_by, "username", None),
                "created_at": n.created_at,
                "akt_file": n.akt_file.url if n.akt_file else None,
            })
        return result

    def get_tamir_turi_soni(self, obj):
        return TexnikKorik.objects.filter(tarkib=obj).values("tamir_turi").distinct().count()




class TexnikKorikJadvalSerializer(serializers.ModelSerializer):
    tarkib = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.filter(is_active=True)
    )
    tarkib_raqami = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    tamir_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)
    depo_nomi = serializers.CharField(source="tarkib.depo.qisqacha_nomi", read_only=True)

    class Meta:
        model = TexnikKorikJadval
        fields = [
            "id", "tarkib", "tarkib_raqami", "depo_nomi",
            "tamir_turi", "tamir_nomi",
            "sana", "created_by", "created_at"
        ]
        read_only_fields = ["created_by", "created_at"]
        
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tamir turi tanlashda TO-1 ni chiqarilmasin
        self.fields["tamir_turi"].queryset = self.fields["tamir_turi"].queryset.exclude(tamir_nomi="TO-1")
        
    def validate(self, attrs):
        tarkib = attrs.get("tarkib")
        sana = attrs.get("sana")
        tamir_turi = attrs.get("tamir_turi")

        if not tarkib or not sana or not tamir_turi:
            return attrs

        # Shu tarkib uchun oxirgi yozuvni topamiz
        last_korik = (
            TexnikKorikJadval.objects
            .filter(tarkib=tarkib)
            .order_by('-sana')
            .first()
        )

        if last_korik:
            # Oxirgi tamirning tugash muddatini aniqlaymiz
            old_tamir = last_korik.tamir_turi
            miqdor = old_tamir.tamirlanish_miqdori or 0
            birlik = old_tamir.tamirlanish_vaqti

            if birlik == "kun":
                old_end = last_korik.sana + timedelta(days=miqdor)
            elif birlik == "oy":
                old_end = last_korik.sana + timedelta(days=miqdor * 30)
            elif birlik == "soat":
                old_end = last_korik.sana + timedelta(days=1)
            else:
                old_end = last_korik.sana

            # Agar yangi sana hali eski muddat tugamasdan kiritilsa — xato
            if sana <= old_end:
                raise serializers.ValidationError({
                    "detail": (
                        f"❌ {tarkib.tarkib_raqami} uchun "
                        f"so‘nggi '{old_tamir.tamir_nomi}' ({last_korik.sana:%d-%m-%Y}) "
                        f"tamiri hali tugamagan! "
                        f"Yangi tamirni faqat {old_end:%d-%m-%Y} dan keyin kiritish mumkin."
                    )
                })

        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
    
    
    
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "is_read", "created_at"]