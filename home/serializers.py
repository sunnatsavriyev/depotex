from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism, TexnikKorikStep, TexnikKorikEhtiyotQismStep, NosozlikEhtiyotQismStep, NosozlikStep, KunlikYurish
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.db.models import Sum


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


class EhtiyotQismlariSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = EhtiyotQismlari
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class EhtiyotQismInputSerializer(serializers.Serializer):
    miqdor = serializers.FloatField()




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


    class Meta:
        model = HarakatTarkibi
        fields = "__all__"
        read_only_fields = ["created_by", "created_at","holati"]


    def get_total_kilometr(self, obj):
        # Annotate orqali kelgan bo‘lsa shu qiymatni qaytaradi
        if hasattr(obj, "total_kilometr") and obj.total_kilometr is not None:
            return obj.total_kilometr
        # Aks holda, DB dan hisoblaydi
        return obj.kunlik_yurishlar.aggregate(total=Sum("kilometr"))["total"] or 0

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        validated_data.pop("holati", None)
        return super().update(instance, validated_data)
    
    
    





class EhtiyotQismWithMiqdorSerializer(serializers.ModelSerializer):
    miqdor = serializers.SerializerMethodField()

    class Meta:
        model = EhtiyotQismlari
        fields = ["id", "ehtiyotqism_nomi", "birligi", "miqdor"]

    def get_miqdor(self, obj):
        parent = self.context.get("parent_instance")
        if not parent:
            return None

        if isinstance(parent, TexnikKorik):
            through_obj = TexnikKorikEhtiyotQism.objects.filter(
                korik=parent, ehtiyot_qism=obj
            ).first()
        elif isinstance(parent, Nosozliklar):
            through_obj = NosozlikEhtiyotQism.objects.filter(
                nosozlik=parent, ehtiyot_qism=obj
            ).first()
        else:
            through_obj = None

        return through_obj.miqdor if through_obj else None




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
    # inputda id sifatida nom yoki raqam yuborish mumkin
    id = SlugOrPkRelatedField(
        slug_field="ehtiyotqism_nomi",
        queryset=EhtiyotQismlari.objects.all(),
        source="ehtiyot_qism"
    )
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQism
        fields = ["id", "birligi", "miqdor"]


class TexnikKorikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    id = SlugOrPkRelatedField(
        slug_field="ehtiyotqism_nomi",
        queryset=EhtiyotQismlari.objects.all(),
        source="ehtiyot_qism"
    )
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQismStep
        fields = ["id", "birligi", "miqdor"]



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
    korik = serializers.PrimaryKeyRelatedField(
    queryset=TexnikKorik.objects.all(),
    write_only=True
    )
    korik_nomi = serializers.CharField(source="korik.tarkib.tarkib_raqami", read_only=True)

    
    ehtiyot_qismlar = TexnikKorikEhtiyotQismStepSerializer(many=True, write_only=True, required=False)
   
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismStepSerializer(
        source="texnikkorikehtiyotqismstep_set", many=True, read_only=True
    )

    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False)
    akt_file = serializers.FileField(write_only=True, required=False)
    chiqqan_vaqti = serializers.DateTimeField(required=False, read_only=True)

    class Meta:
        model = TexnikKorikStep
        fields = [
            "id", "korik", "korik_nomi", "tamir_turi_nomi",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "chiqqan_vaqti", "akt_file",
            "yakunlash", "created_by", "created_at", "password", "status"
        ]
        read_only_fields = [ "tamir_turi_nomi", "created_by", "created_at"]

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
        korik = validated_data.pop("korik", None)
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        validated_data.pop("created_by", None)

        if not korik or korik.status != TexnikKorik.Status.JARAYONDA:
            raise serializers.ValidationError({"korik": "Avval Texnik Korik boshlang yoki u tugallanmagan."})

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

        # 🔹 Stepga ehtiyot qismlarini qo‘shamiz
        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            TexnikKorikEhtiyotQismStep.objects.create(
                korik_step=step,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )

        # 🔹 Korik va tarkib holatini yangilaymiz
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

    tarkib = serializers.PrimaryKeyRelatedField(
    queryset=HarakatTarkibi.objects.filter(holati="Soz_holatda"),
    )
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)
    kirgan_vaqti = serializers.DateTimeField(read_only=True)
    tamir_turi = serializers.PrimaryKeyRelatedField(
    queryset=TamirTuri.objects.all(),
    )
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)

    steps = serializers.SerializerMethodField()

    ehtiyot_qismlar = TexnikKorikEhtiyotQismStepSerializer(
    many=True, write_only=True, required=False, allow_null=True, default=list
)
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismSerializer(
        source="texnikkorikehtiyotqism_set", many=True, read_only=True
    )
    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    chiqqan_vaqti = serializers.DateTimeField(required=False,read_only=True)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "tarkib", "tarkib_nomi", "tamir_turi", "tamir_turi_nomi", "status",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "kirgan_vaqti", "chiqqan_vaqti",
            "akt_file", "yakunlash", "created_by", "created_at", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]

    

    def get_steps(self, obj):
        request = self.context.get("request")

        # 🔹 Parent
        parent_data = TexnikKorikDetailForStepSerializer(obj, context=self.context).data

        # 🔹 Queryset
        steps_qs = obj.steps.all().order_by("created_at")

        # 🔹 Search ishlatamiz
        search = request.query_params.get("search")
        if search:
            steps_qs = steps_qs.filter(
                Q(kamchiliklar_haqida__icontains=search) |
                Q(bartaraf_etilgan_kamchiliklar__icontains=search)
            )

        # 🔹 Pagination
        paginator = StepPagination()
        page = paginator.paginate_queryset(steps_qs, request)
        steps_data = TexnikKorikStepSerializer(page, many=True, context=self.context).data

        results = [parent_data] + steps_data

        return {
            "count": paginator.page.paginator.count + 1,
            "num_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": results,
        }

    
    
    
    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file", None)

        # ❗️ Agar yakunlash bo‘lsa → akt_file majburiy
        if yakunlash and not akt_file:
            raise serializers.ValidationError({
                "akt_file": "Yakunlash uchun akt fayl majburiy."
            })

        return attrs

    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        clean_data = {
            key: value for key, value in data.items()
            if value not in [None, False, [], {}]
        }
        return clean_data


    def create(self, validated_data):
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", []) or []
        akt_file = validated_data.pop("akt_file", None)
        yakunlash = validated_data.pop("yakunlash", False)

        validated_data["created_by"] = self.context["request"].user
        if akt_file:
            validated_data["akt_file"] = akt_file

        # Avval asosiy korikni yaratamiz
        korik = TexnikKorik.objects.create(**validated_data)

        # Holatni yangilash
        if yakunlash:
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI
            korik.tarkib.holati = "Soz_holatda"
            korik.chiqqan_vaqti = korik.created_at 
        else:
            korik.tarkib.holati = "Texnik_korikda"


        korik.tarkib.save()
        korik.save()

        # Endi ehtiyot qismlarni qo‘shamiz
        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            TexnikKorikEhtiyotQism.objects.create(
                korik=korik,
                ehtiyot_qism=eq_obj,
                miqdor=miqdor
            )

        return korik




    def update(self, instance, validated_data):
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", None)
        akt_file = validated_data.pop("akt_file", None)

        if akt_file:  # faylni yangilash
            instance.akt_file = akt_file

        yakunlash = validated_data.get("yakunlash", False)

        if yakunlash:
            instance.status = TexnikKorik.Status.BARTARAF_ETILDI
            instance.tarkib.holati = "Soz_holatda"
            if not instance.chiqqan_vaqti:
                instance.chiqqan_vaqti = instance.created_at  
        else:
            instance.tarkib.holati = "Texnik_korikda"  

        instance.tarkib.save()
        instance = super().update(instance, validated_data)

        if ehtiyot_qismlar is not None:
            instance.texnikkorikehtiyotqism_set.all().delete()
            for item in ehtiyot_qismlar:
                eq_obj = item.get("ehtiyot_qism")
                miqdor = item.get("miqdor", 1)
                TexnikKorikEhtiyotQism.objects.create(
                    korik=instance,
                    ehtiyot_qism=eq_obj,
                    miqdor=miqdor
                )
        return instance







class NosozlikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = NosozlikEhtiyotQismStep
        fields = ['id', 'ehtiyot_qism', 'ehtiyot_qism_nomi', 'birligi', 'miqdor']




class NosozlikEhtiyotQismSerializer(serializers.ModelSerializer):
    ehtiyot_qism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = NosozlikEhtiyotQism
        fields = ['id', 'ehtiyot_qism', 'ehtiyot_qism_nomi', 'birligi', 'miqdor']




class NosozliklarDetailSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismSerializer(
        source="nosozlikehtiyotqism_set", many=True, read_only=True
    )
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = Nosozliklar
        fields = [
            "id",
            "nosozliklar_haqida", "ehtiyot_qismlar", "aniqlangan_vaqti","ehtiyot_qismlar_detail",
            "bartaraf_etilgan_nosozliklar", "status", "created_by", "created_at",
            "bartarafqilingan_vaqti", 
        ]



# Nosozlik Step serializer
class NosozlikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    ehtiyot_qismlar = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(), many=True, write_only=True
    )
    ehtiyot_qismlar_detail = NosozlikEhtiyotQismStepSerializer(
        source="ehtiyot_qismlar_step", many=True, read_only=True
    )
    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField(write_only=True, required=False)
    yakunlash = serializers.BooleanField(required=False, default=False)
    bartaraf_qilingan_vaqti = serializers.DateTimeField(required=False)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = NosozlikStep
        fields = [
            "id",
            "nosozliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_nosozliklar", "akt_file",
            "yakunlash", "status", "created_by", "created_at",
            "bartaraf_qilingan_vaqti", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")
        bartaraf_qilingan_vaqti = attrs.get("bartaraf_qilingan_vaqti", None)

        # ❗ Agar bartaraf qilingan vaqt berilsa → yakunlash va akt_file majburiy
        if bartaraf_qilingan_vaqti:
            if not yakunlash:
                raise serializers.ValidationError({
                    "yakunlash": "Bartaraf qilingan vaqtni belgilash uchun yakunlash tugmasini belgilang."
                })
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Bartaraf qilingan vaqtni belgilash uchun akt fayl majburiy."
                })

        # ❗ Agar yakunlash belgilangan bo‘lsa → bartaraf qilingan vaqt va akt_file majburiy
        if yakunlash:
            if not bartaraf_qilingan_vaqti:
                attrs["bartaraf_qilingan_vaqti"] = timezone.now()
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Yakunlash uchun akt fayl majburiy."
                })

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        nosozlik_id = self.context["view"].kwargs.get("nosozlik_pk")
        nosozlik = Nosozliklar.objects.filter(id=nosozlik_id).first()
        if not nosozlik:
            raise serializers.ValidationError({"nosozlik": "Nosozlik topilmadi."})

        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        yakunlash = validated_data.pop("yakunlash", False)
        bartaraf_qilingan_vaqti = validated_data.get("bartaraf_qilingan_vaqti")

        step = NosozlikStep.objects.create(
            nosozlik=nosozlik,
            created_by=request.user,
            status=NosozlikStep.Status.BARTARAF_ETILDI if yakunlash else NosozlikStep.Status.JARAYONDA,
            **validated_data
        )

        for eq in ehtiyot_qismlar:
            NosozlikEhtiyotQismStep.objects.create(
                step=step,
                ehtiyot_qism=eq,
                miqdor=1
            )

        # Yakunlash bo‘lsa, asosiy nosozlikni yangilash
        if yakunlash:
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.bartarafqilingan_vaqti = bartaraf_qilingan_vaqti or timezone.now()
            nosozlik.save()
            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save()

        return step

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {k: v for k, v in data.items() if v not in [None, False, [], {}]}


# Nosozliklar serializer
class NosozliklarSerializer(serializers.ModelSerializer):
    tarkib = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    akt_file = serializers.FileField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)

    tarkib_id = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.filter(holati="Soz_holatda"),
        source="tarkib",
        write_only=True
    )
    ehtiyot_qismlar_id = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(),
        source="ehtiyot_qism_aloqalari",
        write_only=True,
        many=True,
        required=False
    )

    ehtiyot_qismlar_detail = NosozlikEhtiyotQismSerializer(
        source="ehtiyot_qism_aloqalari", many=True, read_only=True
    )
    status = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)
    bartarafqilingan_vaqti = serializers.DateTimeField(required=False)
    steps = serializers.SerializerMethodField()

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "created_by",
            "tarkib_id", "tarkib", "ehtiyot_qismlar_id",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "image", "akt_file",
            "status", "yakunlash", "bartarafqilingan_vaqti",
            "aniqlangan_vaqti",
            "ehtiyot_qismlar_detail",
            "steps",
            "password"
        ]


    def get_steps(self, obj):
        """
        1) Boshida korikning o‘zi 
        2) Keyin barcha steplar 
        """
        parent_data = NosozliklarDetailSerializer(
            obj, context=self.context
        ).data

        steps_qs = obj.steps.all().order_by("created_at")
        steps_data = NosozlikStepSerializer(
            steps_qs, many=True, context=self.context
        ).data

        return [parent_data] + steps_data

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file", None)
        bartarafqilingan_vaqti = attrs.get("bartarafqilingan_vaqti", None)

        # ❗ Agar bartaraf etilgan vaqt belgilansa → yakunlash va akt_file majburiy
        if bartarafqilingan_vaqti:
            if not yakunlash:
                raise serializers.ValidationError({
                    "yakunlash": "Bartaraf etilgan vaqtni belgilash uchun yakunlash tugmasini belgilang."
                })
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Bartaraf etilgan vaqtni belgilash uchun akt fayl majburiy."
                })

        # ❗ Agar yakunlash belgilangan bo‘lsa → bartaraf etilgan vaqt va akt_file majburiy
        if yakunlash:
            if not bartarafqilingan_vaqti:
                attrs["bartarafqilingan_vaqti"] = timezone.now()
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Yakunlash uchun akt fayl majburiy."
                })

        return attrs

    def create(self, validated_data):
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar_id", [])
        validated_data["created_by"] = self.context["request"].user
        nosozlik = super().create(validated_data)

        for eq in ehtiyot_qismlar:
            NosozlikEhtiyotQism.objects.create(
                nosozlik=nosozlik,
                ehtiyot_qism=eq,
                miqdor=1
            )

        # Yakunlash bo‘lsa → asosiy holat avtomatik soz holat
        if validated_data.get("yakunlash", False):
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.bartarafqilingan_vaqti = validated_data.get("bartarafqilingan_vaqti", timezone.now())
            nosozlik.save()
            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save()

        return nosozlik

    def get_tarkib(self, obj):
        return str(obj.tarkib) if obj.tarkib else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {k: v for k, v in data.items() if v not in [None, False, [], {}]}
