from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism, TexnikKorikStep, TexnikKorikEhtiyotQismStep, NosozlikEhtiyotQismStep, NosozlikStep, KunlikYurish,Vagon,EhtiyotQismHistory
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.db.models import Sum
from django.db import models

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
            "is_active", "previous_version","vagonlar" 
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
            previous_version=instance,
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

    class Meta:
        model = EhtiyotQismlari
        fields = [
            "id", "created_by", "ehtiyotqism_nomi", "nomenklatura_raqami",
            "birligi", "created_at", "depo", "jami_miqdor"
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


class EhtiyotQismMiqdorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EhtiyotQismHistory
        fields = ['miqdor']




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


# --- Ehtiyot qismlar uchun serializerlar ---
class TexnikKorikEhtiyotQismSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQism
        fields = ["id", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        # history - minus yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance
    


class TexnikKorikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQismStep
        fields = ["id", "korik_step", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        # history - minus yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance

    


class TexnikKorikDetailForStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismSerializer(
        source="texnikkorikehtiyotqism_set", many=True, read_only=True
    )

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "tarkib", "tarkib_nomi",
            "tamir_turi", "tamir_turi_nomi",
            "status", "kamchiliklar_haqida",
            "bartaraf_etilgan_kamchiliklar",
            "kirgan_vaqti", "chiqqan_vaqti", "created_by", "created_at",
            "ehtiyot_qismlar_detail",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        clean_data = {
            k: v for k, v in data.items()
            if v not in [None, False, [], {}] and not (isinstance(v, str) and v.strip() == "")
        }
        return clean_data







class TexnikKorikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)
    korik = serializers.PrimaryKeyRelatedField(read_only=True)
    korik_nomi = serializers.CharField(source="korik.tarkib.tarkib_raqami", read_only=True)
    pervious_version = serializers.SerializerMethodField()

    ehtiyot_qismlar = TexnikKorikEhtiyotQismStepSerializer(
        many=True, write_only=True, required=False
    )
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismStepSerializer(
        source="texnikkorikehtiyotqismstep_set", many=True, read_only=True
    )

    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField(write_only=True, required=False)  # faqat bitta
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False)
    chiqqan_vaqti = serializers.DateTimeField(required=False, read_only=True)

    class Meta:
        model = TexnikKorikStep
        fields = [
            "id", "korik", "korik_nomi", "tamir_turi_nomi", "pervious_version",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "chiqqan_vaqti", "akt_file",
            "yakunlash", "created_by", "created_at", "password", "status"
        ]
        read_only_fields = ["korik", "korik_nomi", "tamir_turi_nomi", "created_by", "created_at"]

    def get_pervious_version(self, obj):
        if obj.korik and obj.korik.tarkib and obj.korik.tarkib.previous_version:
            return obj.korik.tarkib.previous_version.id
        return None

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        chiqqan_vaqti = attrs.get("chiqqan_vaqti")
        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")

        if chiqqan_vaqti:
            if not yakunlash:
                raise serializers.ValidationError({"yakunlash": "Chiqish vaqtini belgilash uchun yakunlash majburiy."})
            if not akt_file:
                raise serializers.ValidationError({"akt_file": "Chiqish vaqtini belgilash uchun akt fayl majburiy."})

        if yakunlash and akt_file and not chiqqan_vaqti:
            attrs["chiqqan_vaqti"] = timezone.now()

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        korik = self.context.get("korik")  # 👈 perform_create() dan uzatiladi
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []
        validated_data.pop("created_by", None)

        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)

        step = TexnikKorikStep.objects.create(
            korik=korik,
            tamir_turi=korik.tamir_turi,
            created_by=request.user,
            akt_file=akt_file,
            status=TexnikKorikStep.Status.BARTARAF_ETILDI if yakunlash else TexnikKorikStep.Status.JARAYONDA,
            **validated_data
        )

        # 🔧 Stepga ehtiyot qismlar ishlatish
        for item in ehtiyot_qismlar:
            eq_id = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)

            if eq_id:
                eq_obj = EhtiyotQismlari.objects.get(id=eq_id)

                # History orqali minus yozish
                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj,
                    miqdor=-miqdor,
                    created_by=request.user
                )

                TexnikKorikEhtiyotQismStep.objects.create(
                    korik_step=step,
                    ehtiyot_qism=eq_obj,
                    miqdor=miqdor
                )

        # 🔹 Step yakunlash → korik va tarkibni ham yangilash
        if yakunlash:
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI
            korik.tarkib.holati = "Soz_holatda"
            if not step.chiqqan_vaqti:
                step.chiqqan_vaqti = timezone.now()
                step.save()
        else:
            korik.tarkib.holati = "Texnik_korikda"

        korik.tarkib.save()
        korik.save()
        return step

    

class StepPagination(PageNumberPagination): 
    page_size_query_param = "limit"
    max_page_size = 50





class TexnikKorikSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    # Tarkib va tamir turi
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
        many=True, write_only=True, required=False, allow_null=True, default=list
    )
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismSerializer(
        source="texnikkorikehtiyotqism_set", many=True, read_only=True
    )

    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    chiqqan_vaqti = serializers.DateTimeField(read_only=True)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "tarkib", "tarkib_nomi", "is_active", "pervious_version",
            "tamir_turi", "tamir_turi_nomi", "status",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "kirgan_vaqti", "chiqqan_vaqti",
            "akt_file", "yakunlash", "created_by", "created_at", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]


    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Har safar serializer ochilganda dinamik querysetni DB’dan oladi
        self.fields["tarkib"].queryset = HarakatTarkibi.objects.filter(
            is_active=True,
            holati="Soz_holatda"
        )
    
    
    # --- Serializer metodlari ---
    def get_pervious_version(self, obj):
        return obj.tarkib.previous_version.id if obj.tarkib and obj.tarkib.previous_version else None

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

        ishlatilgan_qismlar = []
        for item in obj.texnikkorikehtiyotqism_set.all():
            ehtiyot_qism = item.ehtiyot_qism
            ishlatilgan_qismlar.append({
                "ehtiyot_qism": ehtiyot_qism.ehtiyotqism_nomi,
                "birligi": ehtiyot_qism.birligi,
                "ishlatilgan_miqdor": item.miqdor,
                "qoldiq": ehtiyot_qism.jami_miqdor
            })
        parent_data["ishlatilgan_qismlar"] = ishlatilgan_qismlar

        steps_qs = obj.steps.all().order_by("created_at")
        search = request.query_params.get("search")
        if search:
            steps_qs = steps_qs.filter(
                Q(kamchiliklar_haqida__icontains=search) |
                Q(bartaraf_etilgan_kamchiliklar__icontains=search)
            )

        paginator = StepPagination()
        page = paginator.paginate_queryset(steps_qs, request)

        if page is not None:
            steps_data = TexnikKorikStepSerializer(page, many=True, context=self.context).data
            return {
                "count": paginator.page.paginator.count + 1,
                "num_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": [parent_data] + steps_data,
            }
        else:
            steps_data = TexnikKorikStepSerializer(steps_qs, many=True, context=self.context).data
            return {
                "count": steps_qs.count() + 1,
                "num_pages": 1,
                "current_page": 1,
                "next": None,
                "previous": None,
                "results": [parent_data] + steps_data,
            }

    # --- Validation ---
    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})

        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {k: v for k, v in data.items() if v not in [None, False, [], {}]}

    # --- CREATE ---
    def create(self, validated_data):
        request = self.context["request"]

        tarkib = validated_data.pop("tarkib")
        tamir_turi = validated_data.pop("tamir_turi")
        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []

        # Korikni avval jarayon holatida yaratamiz
        korik = TexnikKorik.objects.create(
            tarkib=tarkib,
            tamir_turi=tamir_turi,
            created_by=request.user,
            status=TexnikKorik.Status.JARAYONDA,
            **validated_data
        )

        if yakunlash:
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI
            korik.tarkib.holati = "Soz_holatda"
            korik.tarkib.save()   # 🔴 qo‘shish kerak
            korik.save()
        else:
            # Yakunlamasa, step yaratamiz
            step = TexnikKorikStep.objects.create(
                korik=korik,
                tamir_turi=tamir_turi,
                created_by=request.user,
                akt_file=akt_file,
                status=TexnikKorikStep.Status.JARAYONDA
            )

            for item in ehtiyot_qismlar:
                eq_id = item.get("ehtiyot_qism")
                miqdor = item.get("miqdor", 1)
                if not eq_id:
                    continue
                eq_obj = EhtiyotQismlari.objects.get(id=eq_id)
                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj, miqdor=-miqdor, created_by=request.user
                )
                TexnikKorikEhtiyotQismStep.objects.create(
                    korik_step=step, ehtiyot_qism=eq_obj, miqdor=miqdor
                )

            korik.tarkib.holati = "Texnik_korikda"
            korik.tarkib.save()
            korik.save()

        return korik


    # --- UPDATE ---
    def update(self, instance, validated_data):
        request = self.context["request"]
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []
        akt_file = validated_data.pop("akt_file", None)
        yakunlash = validated_data.pop("yakunlash", False)

        if akt_file:
            instance.akt_file = akt_file

        if yakunlash:
            instance.status = TexnikKorik.Status.BARTARAF_ETILDI
            instance.tarkib.holati = "Soz_holatda"
            if not instance.chiqqan_vaqti:
                instance.chiqqan_vaqti = timezone.now()
            instance.tarkib.save()  
        else:
            instance.tarkib.holati = "Texnik_korikda"

        instance.tarkib.save()
        instance = super().update(instance, validated_data)

        for item in ehtiyot_qismlar:
            eq_id = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if eq_id:
                try:
                    eq_obj = EhtiyotQismlari.objects.get(id=eq_id)
                except EhtiyotQismlari.DoesNotExist:
                    continue

                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj,
                    miqdor=-miqdor,
                    created_by=request.user
                )

                TexnikKorikEhtiyotQism.objects.create(
                    korik=instance,
                    ehtiyot_qism=eq_obj,
                    miqdor=miqdor
                )

        return instance




class StepPagination(PageNumberPagination):
    page_size_query_param = "limit"
    max_page_size = 50

    def get_paginated_response(self, data):
        return {
            "count": self.page.paginator.count,
            "num_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        }






class NosozlikEhtiyotQismSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = NosozlikEhtiyotQism
        fields = ["id", "nosozlik", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        # history - minus yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance
    
    

class NosozlikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = NosozlikEhtiyotQismStep
        fields = ["id", "step", "ehtiyot_qism", "ehtiyot_qism_nomi", "birligi", "miqdor"]

    def validate(self, attrs):
        eq = attrs["ehtiyot_qism"]
        if attrs["miqdor"] > eq.jami_miqdor:
            raise serializers.ValidationError(f"Omborda yetarli miqdor yo‘q ({eq.jami_miqdor})")
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        # history - minus yozamiz
        EhtiyotQismHistory.objects.create(
            ehtiyot_qism=instance.ehtiyot_qism,
            miqdor=-instance.miqdor,
            created_by=self.context["request"].user
        )
        return instance






# --- parent detail for steps (joylashuvi: step va parent serializerlardan OLDIN yozing) ---
class NosozlikDetailForStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    is_active = serializers.BooleanField(source="tarkib.is_active", read_only=True)

    # agar parentda ehtiyot qismlar kerak bo'lsa (parent darajasida ko'rsatiladi)
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismSerializer(
        source="nosozlikehtiyotqism_set", many=True, read_only=True
    )

    status = serializers.CharField(read_only=True)

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "tarkib", "tarkib_nomi", "is_active",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "ehtiyot_qismlar_detail", "status", "created_by", "created_at"
        ]





# --- Step Serializer ---
class NosozlikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    nosozlik = serializers.PrimaryKeyRelatedField(
        queryset=Nosozliklar.objects.all(), write_only=True
    )
    nosozlik_nomi = serializers.CharField(source="nosozlik.tarkib.tarkib_raqami", read_only=True)

    ehtiyot_qismlar = NosozlikEhtiyotQismStepSerializer(many=True, write_only=True, required=False)
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismStepSerializer(
        source="nosozlikehtiyotqismstep_set", many=True, read_only=True
    )

    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField(write_only=True, required=False)
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

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not request.user.is_authenticated or not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")
        vaqt = attrs.get("bartaraf_qilingan_vaqti")

        if vaqt:
            if not yakunlash:
                raise serializers.ValidationError({"yakunlash": "Vaqt belgilash uchun yakunlash majburiy."})
            if not akt_file:
                raise serializers.ValidationError({"akt_file": "Vaqt belgilash uchun akt fayl majburiy."})

        if yakunlash and akt_file and not vaqt:
            attrs["bartaraf_qilingan_vaqti"] = timezone.now()

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        nosozlik = validated_data.pop("nosozlik")
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)

        step = NosozlikStep.objects.create(
            nosozlik=nosozlik,
            created_by=request.user,
            akt_file=akt_file,
            status=NosozlikStep.Status.BARTARAF_ETILDI if yakunlash else NosozlikStep.Status.JARAYONDA,
            **validated_data
        )

        # 🔹 ishlatilgan qismlarni yozamiz
        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if eq_obj:
                NosozlikEhtiyotQismStep.objects.create(step=step, ehtiyot_qism=eq_obj, miqdor=miqdor)
                EhtiyotQismHistory.objects.create(  # faqat History orqali kamayadi
                    ehtiyot_qism=eq_obj,
                    miqdor=-miqdor,
                    created_by=request.user
                )

        if yakunlash:
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.tarkib.holati = "Soz_holatda"
            if not step.bartaraf_qilingan_vaqti:
                step.bartaraf_qilingan_vaqti = timezone.now()
                step.save()

        nosozlik.tarkib.save()
        nosozlik.save()
        return step


# --- Nosozliklar Serializer (frontend mos) ---
class NosozliklarSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tarkib = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.filter(is_active=True, holati="Soz_holatda")
    )
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    is_active = serializers.BooleanField(source="tarkib.is_active", read_only=True)

    ehtiyot_qismlar = NosozlikEhtiyotQismSerializer(
        many=True, write_only=True, required=False, allow_null=True, default=list
    )
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismSerializer(
        source="nosozlikehtiyotqism_set", many=True, read_only=True
    )

    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    bartarafqilingan_vaqti = serializers.DateTimeField(read_only=True)

    steps = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "tarkib", "tarkib_nomi", "is_active",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "status", "aniqlangan_vaqti", "bartarafqilingan_vaqti",
            "created_by", "created_at",
            "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "akt_file", "yakunlash", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]

    # --- Stepsni olish ---
    def get_steps(self, obj):
        steps_qs = obj.steps.all().order_by("created_at")
        return NosozlikStepSerializer(steps_qs, many=True).data

    # --- Validatsiya ---
    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")
        if yakunlash and not akt_file:
            raise serializers.ValidationError({"akt_file": "Yakunlash uchun akt fayl majburiy."})

        return attrs

    # --- CREATE ---
    def create(self, validated_data):
        request = self.context["request"]

        # dublikat bo‘ladigan fieldlarni olib tashlaymiz
        validated_data.pop("created_by", None)
        validated_data.pop("status", None)   # <-- 🔥 shu joy muhim

        tarkib = validated_data.pop("tarkib")
        yakunlash = validated_data.pop("yakunlash", False)
        akt_file = validated_data.pop("akt_file", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []

        # asosiy nosozlik yaratamiz
        nosozlik = Nosozliklar.objects.create(
            tarkib=tarkib,
            created_by=request.user,
            status=Nosozliklar.Status.BARTARAF_ETILDI if yakunlash else Nosozliklar.Status.JARAYONDA,
            akt_file=akt_file,
            **validated_data
        )

        if yakunlash:
            nosozlik.bartarafqilingan_vaqti = timezone.now()
            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save()
            nosozlik.save()
        else:
            step = NosozlikStep.objects.create(
                nosozlik=nosozlik,
                created_by=request.user,
                akt_file=akt_file,
                status=NosozlikStep.Status.JARAYONDA
            )

            for item in ehtiyot_qismlar:
                eq_id = item.get("ehtiyot_qism")
                miqdor = item.get("miqdor", 1)
                if not eq_id:
                    continue
                eq_obj = EhtiyotQismlari.objects.get(id=eq_id)
                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj, miqdor=-miqdor, created_by=request.user
                )
                NosozlikEhtiyotQismStep.objects.create(
                    step=step, ehtiyot_qism=eq_obj, miqdor=miqdor
                )

            nosozlik.tarkib.holati = "Nosozlikda"
            nosozlik.tarkib.save()
            nosozlik.save()

        return nosozlik


    # --- UPDATE ---
    def update(self, instance, validated_data):
        request = self.context["request"]
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []
        akt_file = validated_data.pop("akt_file", None)
        yakunlash = validated_data.pop("yakunlash", False)

        if akt_file:
            instance.akt_file = akt_file

        if yakunlash:
            instance.status = Nosozliklar.Status.BARTARAF_ETILDI
            instance.bartarafqilingan_vaqti = timezone.now()
            instance.tarkib.holati = "Soz_holatda"
            instance.tarkib.save()
        else:
            instance.tarkib.holati = "Nosozlikda"

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
            EhtiyotQismHistory.objects.create(
                ehtiyot_qism=eq_obj, miqdor=-miqdor, created_by=request.user
            )
            NosozlikEhtiyotQism.objects.create(
                nosozlik=instance, ehtiyot_qism=eq_obj, miqdor=miqdor
            )

        return instance





    
    


    
    
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