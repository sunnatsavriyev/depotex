from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism, TexnikKorikStep, TexnikKorikEhtiyotQismStep, NosozlikEhtiyotQismStep, NosozlikStep
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth import authenticate
User = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "role"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            role=validated_data["role"],
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

    class Meta:
        model = HarakatTarkibi
        fields = "__all__"
        read_only_fields = ["created_by", "created_at","holati"]

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



# class TexnikKorikSerializer(serializers.ModelSerializer):
#     created_by = serializers.CharField(source="created_by.username", read_only=True)
#     akt_file = serializers.FileField(required=False, allow_null=True)
#     image = serializers.ImageField(required=False, allow_null=True)

#     tarkib_id = serializers.PrimaryKeyRelatedField(
#         queryset=HarakatTarkibi.objects.all(),
#         source="tarkib",
#         write_only=True,
#         required=False
#     )
#     tamir_turi_id = serializers.PrimaryKeyRelatedField(
#         queryset=TamirTuri.objects.all(),
#         source="tamir_turi",
#         write_only=True,
#         required=False,
#         allow_null=True
#     )
#     ehtiyot_qismlar_id = serializers.PrimaryKeyRelatedField(
#         queryset=EhtiyotQismlari.objects.all(),
#         source="ehtiyot_qismlar",
#         write_only=True,
#         many=True,
#         required=False
#     )
#     parent_id = serializers.PrimaryKeyRelatedField(
#         queryset=TexnikKorik.objects.all(),
#         source="parent",
#         write_only=True,
#         required=False,
#         allow_null=True
#     )

#     tarkib = serializers.SerializerMethodField(read_only=True)
#     tamir_turi = serializers.SerializerMethodField(read_only=True)
#     ehtiyot_qismlar = EhtiyotQismInputSerializer(
#         many=True, write_only=True, required=False
#     )
#     ehtiyot_qismlar_detail = serializers.SerializerMethodField(read_only=True)
#     approved = serializers.SerializerMethodField(read_only=True)
#     status = serializers.CharField(read_only=True)
#     password = serializers.CharField(write_only=True, required=True)
#     yakunlash = serializers.BooleanField(required=False, default=False)

#     class Meta:
#         model = TexnikKorik
#         fields = [
#             "id", "created_by",
#             "tarkib_id", "tamir_turi_id", "ehtiyot_qismlar_id", "parent_id",
#             "tarkib", "tamir_turi", "ehtiyot_qismlar",       
#             "ehtiyot_qismlar_detail",
#             "kamchiliklar_haqida", "bartaraf_etilgan_kamchiliklar",
#             "image", "akt_file",
#             "status", "yakunlash",
#             "kirgan_vaqti", "chiqqan_vaqti",
#             "approved", "created_at",
#             "password"
#         ]

#     def get_tarkib(self, obj):
#         # Agar parent bo‘lsa, tarkibni ko‘rsatmaymiz
#         if obj.parent:
#             return None
#         return str(obj.tarkib) if obj.tarkib else None

#     def get_tamir_turi(self, obj):
#         return str(obj.tamir_turi) if obj.tamir_turi else None

#     def get_ehtiyot_qismlar(self, obj):
#         return [str(e) for e in obj.ehtiyot_qismlar.all()]
    
#     def get_approved(self, obj):
#         return "Tasdiqlangan" if obj.approved else "Tasdiqlanmagan"

#     def get_ehtiyot_qismlar_detail(self, obj):
#         return EhtiyotQismWithMiqdorSerializer(
#             obj.ehtiyot_qismlar.all(),
#             many=True,
#             context={"parent_instance": obj}
#         ).data

#     def to_representation(self, instance):
#         rep = super().to_representation(instance)
#         # Null yoki bo‘sh qiymatlarni olib tashlash
#         rep = {k: v for k, v in rep.items() if v not in [None, "", [], {}]}
#         return rep

#     # validate va create metodlarini avvalgidek saqlaymiz


#     def validate(self, attrs):
#         request = self.context.get("request")
#         password = attrs.pop("password", None)
#         if not password or not request.user.check_password(password):
#             raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

#         yakunlash = attrs.get("yakunlash", False)
#         akt_file = attrs.get("akt_file", None)
#         chiqqan_vaqti = attrs.get("chiqqan_vaqti", None)

#         if chiqqan_vaqti and (not yakunlash or not akt_file):
#             raise serializers.ValidationError({
#                 "yakunlash": "Chiqqan vaqtni belgilash uchun yakunlash belgilansin",
#                 "akt_file": "Chiqqan vaqt uchun akt fayl majburiy"
#             })

#         if yakunlash and (not chiqqan_vaqti or not akt_file):
#             raise serializers.ValidationError({
#                 "chiqqan_vaqti": "Yakunlash uchun chiqish vaqti majburiy.",
#                 "akt_file": "Yakunlash uchun akt fayl majburiy."
#             })

#         return attrs

#     def create(self, validated_data):
#         ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
#         ehtiyot_qismlar_id = validated_data.pop("ehtiyot_qismlar_id", [])
#         tarkib = validated_data["tarkib"]

#         # 🔹 Oxirgi ochilgan korikni topamiz
#         oxirgi = TexnikKorik.objects.filter(tarkib=tarkib, yakunlash=False).order_by("-id").first()

#         if oxirgi:
#             # Agar oxirgi yakunlanmagan bo‘lsa, yangi step yaratamiz
#             validated_data["parent"] = oxirgi
#         validated_data["created_by"] = self.context["request"].user
#         validated_data["approved"] = True
#         validated_data["approved_at"] = timezone.now()

#         korik = super().create(validated_data)

#         for idx, ehtiyot_id in enumerate(ehtiyot_qismlar_id):
#             miqdor = ehtiyot_qismlar[idx]["miqdor"] if idx < len(ehtiyot_qismlar) else 1
#             TexnikKorikEhtiyotQism.objects.create(
#                 korik=korik,
#                 ehtiyot_qism=ehtiyot_id,
#                 miqdor=miqdor
#             )

#         return korik



class TexnikKorikEhtiyotQismSerializer(serializers.ModelSerializer):
    ehtiyotqism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQism
        fields = ["id", "ehtiyotqism_nomi", "birligi", "miqdor"]


class TexnikKorikEhtiyotQismStepSerializer(serializers.ModelSerializer):
    ehtiyotqism_nomi = serializers.CharField(source="ehtiyot_qism.ehtiyotqism_nomi", read_only=True)
    birligi = serializers.CharField(source="ehtiyot_qism.birligi", read_only=True)

    class Meta:
        model = TexnikKorikEhtiyotQismStep
        fields = ["id", "ehtiyotqism_nomi", "birligi", "miqdor"]




class TexnikKorikStepSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)
    korik = serializers.CharField(source="korik.tarkib.tarkib_raqami", read_only=True)

    ehtiyot_qismlar = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(), many=True, write_only=True
    )
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismStepSerializer(
        source="texnikkorikehtiyotqismstep_set", many=True, read_only=True
    )
    status = serializers.CharField(read_only=True)
    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = TexnikKorikStep
        fields = [
            "id", "korik", "tamir_turi_nomi",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "chiqqan_vaqti", "akt_file",
            "yakunlash", "created_by", "created_at", "password", "status"
        ]
        read_only_fields = ["korik", "tamir_turi_nomi", "created_by", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        chiqqan_vaqti = attrs.get("chiqqan_vaqti")
        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file")

        # ❗ Agar chiqish vaqti qo‘yilgan bo‘lsa → yakunlash va akt_file majburiy
        if chiqqan_vaqti:
            if not yakunlash:
                raise serializers.ValidationError({
                    "yakunlash": "Chiqish vaqtini belgilash uchun yakunlash majburiy."
                })
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Chiqish vaqtini belgilash uchun akt fayl majburiy."
                })

        # ❗ Agar yakunlash va akt_file berilgan bo‘lsa → chiqqan_vaqti avtomatik
        if yakunlash and akt_file and not chiqqan_vaqti:
            attrs["chiqqan_vaqti"] = timezone.now()

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        korik_id = self.context["view"].kwargs.get("korik_pk")

        # faqat JARAYONDA bo'lgan korikni olish
        korik = TexnikKorik.objects.filter(
            id=korik_id,
            status=TexnikKorik.Status.JARAYONDA
        ).first()

        if not korik:
            raise serializers.ValidationError({
                "korik": "Avval Texnik Korik boshlang yoki u tugallanmagan."
            })

        # validated_data ichida mavjud bo'lishi mumkin bo'lgan kalitlarni olib tashlash
        validated_data.pop("korik", None)
        validated_data.pop("created_by", None)

        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        yakunlash = validated_data.pop("yakunlash", False)

        # Step yaratish
        step = TexnikKorikStep.objects.create(
            korik=korik,
            tamir_turi=korik.tamir_turi,
            created_by=request.user,
            # ✅ oldingi YAKUNLANDI o‘rniga BARTARAF_ETILDI ishlatish
            status=TexnikKorikStep.Status.BARTARAF_ETILDI if yakunlash else TexnikKorikStep.Status.JARAYONDA,
            **validated_data
        )

        # Ehtiyot qismlar bilan bog'lash
        for eq in ehtiyot_qismlar:
            TexnikKorikEhtiyotQismStep.objects.create(
                korik_step=step,
                ehtiyot_qism=eq,
                miqdor=1
            )

        # Yakunlash bo'lsa korik va harakat tarkibini Soz_holatda qilish
        if yakunlash:
            korik.status = TexnikKorik.Status.BARTARAF_ETILDI
            korik.save()
            korik.tarkib.holati = "Soz_holatda"
            korik.tarkib.save()

        return step





    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {k: v for k, v in data.items() if v not in [None, False, [], {}]}











class TexnikKorikSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    tarkib = serializers.PrimaryKeyRelatedField(queryset=HarakatTarkibi.objects.all())
    tarkib_nomi = serializers.CharField(source="tarkib.tarkib_raqami", read_only=True)

    tamir_turi = serializers.PrimaryKeyRelatedField(queryset=TamirTuri.objects.all())
    tamir_turi_nomi = serializers.CharField(source="tamir_turi.tamir_nomi", read_only=True)

    steps = TexnikKorikStepSerializer(many=True, read_only=True)

    ehtiyot_qismlar = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(), many=True, write_only=True
    )
    ehtiyot_qismlar_detail = TexnikKorikEhtiyotQismSerializer(
        source="texnikkorikehtiyotqism_set", many=True, read_only=True
    )
    akt_file = serializers.FileField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)
    yakunlash = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "tarkib", "tarkib_nomi", "tamir_turi", "tamir_turi_nomi", "status",
            "kamchiliklar_haqida", "ehtiyot_qismlar", "ehtiyot_qismlar_detail",
            "bartaraf_etilgan_kamchiliklar", "kirgan_vaqti", "chiqqan_vaqti",
            "akt_file", "yakunlash", "created_by", "created_at", "steps", "password"
        ]
        read_only_fields = ["status", "created_by", "created_at", "steps"]

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = attrs.get("yakunlash", False)
        akt_file = attrs.get("akt_file", None)
        chiqqan_vaqti = attrs.get("chiqqan_vaqti", None)

        # ❗️ Agar chiqish vaqti belgilansa → yakunlash va akt_file majburiy
        if chiqqan_vaqti:
            if not yakunlash:
                raise serializers.ValidationError({
                    "yakunlash": "Chiqish vaqtini belgilash uchun yakunlash tugmasini belgilang."
                })
            if not akt_file:
                raise serializers.ValidationError({
                    "akt_file": "Chiqish vaqtini belgilash uchun akt fayl majburiy."
                })

        # ❗️ Agar yakunlash belgilansa → chiqish vaqti va akt_file majburiy
        if yakunlash:
            if not chiqqan_vaqti:
                raise serializers.ValidationError({
                    "chiqqan_vaqti": "Yakunlash uchun chiqish vaqti majburiy."
                })
            if not akt_file:
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
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", [])
        validated_data["created_by"] = self.context["request"].user
        korik = TexnikKorik.objects.create(**validated_data)

        # ✅ Holatini yangilash
        korik.tarkib.holati = "Texnik_korikda"
        korik.tarkib.save()

        for eq in ehtiyot_qismlar:
            TexnikKorikEhtiyotQism.objects.create(
                korik=korik,
                ehtiyot_qism=eq,
                miqdor=1
            )
        return korik

    def update(self, instance, validated_data):
        ehtiyot_qismlar = validated_data.pop("ehtiyot_qismlar", None)

        # ✅ agar yakunlash bo‘lsa → korik va tarkib tugatilsin
        if validated_data.get("yakunlash", False):
            instance.status = TexnikKorik.Status.YAKUNLANDI
            instance.tarkib.holati = "Soz_holatda"
            instance.tarkib.save()

        instance = super().update(instance, validated_data)

        if ehtiyot_qismlar is not None:
            instance.texnikkorikehtiyotqism_set.all().delete()
            for eq in ehtiyot_qismlar:
                TexnikKorikEhtiyotQism.objects.create(
                    korik=instance,
                    ehtiyot_qism=eq,
                    miqdor=1
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





# Nosozlik Step serializer
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
        queryset=HarakatTarkibi.objects.all(),
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
    steps = NosozlikStepSerializer(many=True, read_only=True)

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
