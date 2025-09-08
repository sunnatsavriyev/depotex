from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism
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

class EhtiyotQismWithMiqdorSerializer(serializers.ModelSerializer):
    miqdor = serializers.SerializerMethodField()

    class Meta:
        model = EhtiyotQismlari
        fields = ["id", "ehtiyotqism_nomi", "birligi", "miqdor"]

    def get_miqdor(self, obj):
        # kontekstdan korik yoki nosozlik obyektini olish
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


class TexnikKorikSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    akt_file = serializers.FileField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)

    tarkib_id = serializers.PrimaryKeyRelatedField(
        queryset=HarakatTarkibi.objects.all(),
        source="tarkib",
        write_only=True
    )
    tamir_turi_id = serializers.PrimaryKeyRelatedField(
        queryset=TamirTuri.objects.all(),
        source="tamir_turi",
        write_only=True,
        required=False,
        allow_null=True
    )
    ehtiyot_qismlar_id = serializers.PrimaryKeyRelatedField(
        queryset=EhtiyotQismlari.objects.all(),
        source="ehtiyot_qismlar",
        write_only=True,
        many=True,
        required=False
    )

    tarkib = serializers.SerializerMethodField(read_only=True)
    tamir_turi = serializers.SerializerMethodField(read_only=True)
    ehtiyot_qismlar = serializers.SerializerMethodField(read_only=True)
    approved = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "created_by",
            "tarkib_id", "tamir_turi_id", "ehtiyot_qismlar_id",
            "tarkib", "tamir_turi", "ehtiyot_qismlar",
            "kamchiliklar_haqida", "bartaraf_etilgan_kamchiliklar",
            "image", "akt_file",
            "status",
            "kirgan_vaqti", "chiqqan_vaqti",
            "approved", "created_at",
            "password"
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Default bo'sh qiymatlarni olib tashlash
        rep = {k: v for k, v in rep.items() if v not in [None, "", [], {}]}

        # 🔹 Bitta tarkib bo‘yicha barcha yozuvlarni olish
        all_records = TexnikKorik.objects.filter(tarkib=instance.tarkib).order_by("id")
        first = all_records.first()
        last = all_records.last()

        rep["status"] = instance.status

        # 🔹 Agar bu birinchi yozuv bo‘lsa → kirgan_vaqti chiqsin
        if instance.id == first.id:
            rep["kirgan_vaqti"] = instance.kirgan_vaqti
        else:
            rep.pop("kirgan_vaqti", None)

        # 🔹 Agar bu oxirgi yozuv bo‘lsa → chiqqan_vaqti + akt_file bo‘lsin
        if instance.id == last.id and instance.chiqqan_vaqti:
            rep["chiqqan_vaqti"] = instance.chiqqan_vaqti
            if instance.akt_file:
                rep["akt_file"] = instance.akt_file.url
        else:
            rep.pop("chiqqan_vaqti", None)
            rep.pop("akt_file", None)

        return rep

    def get_tarkib(self, obj):
        return str(obj.tarkib) if obj.tarkib else None

    def get_tamir_turi(self, obj):
        return str(obj.tamir_turi) if obj.tamir_turi else None

    def get_ehtiyot_qismlar(self, obj):
        return [str(e) for e in obj.ehtiyot_qismlar.all()]
    
    def get_approved(self, obj):
        return "Tasdiqlangan" if obj.approved else "Tasdiqlanmagan"

    def get_ehtiyot_qismlar(self, obj):
        serializer = EhtiyotQismWithMiqdorSerializer(
            obj.ehtiyot_qismlar.all(),
            many=True,
            context={"parent_instance": obj}
        )
        return serializer.data

    def validate(self, attrs):
        # parolni tekshirish
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        # chiqish sanasi bo‘lsa, akt fayl majburiy
        if attrs.get("chiqqan_vaqti") and not attrs.get("akt_file"):
            raise serializers.ValidationError({
                "akt_file": "Chiqish sanasi kiritilganda, akt fayl majburiy."
            })
        return attrs

    def create(self, validated_data):
        tamir_turi = validated_data.get("tamir_turi", None)
        tarkib = validated_data["tarkib"]

        if tamir_turi is None:
            oxirgi = TexnikKorik.objects.filter(tarkib=tarkib).order_by("-id").first()
            if oxirgi:
                validated_data["tamir_turi"] = oxirgi.tamir_turi

        validated_data["created_by"] = self.context["request"].user
        validated_data["approved"] = True
        validated_data["approved_at"] = timezone.now()

        return super().create(validated_data)


class NosozliklarSerializer(serializers.ModelSerializer):
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
        source="ehtiyot_qismlar",
        write_only=True,
        many=True,
        required=False
    )

    tarkib = serializers.SerializerMethodField(read_only=True)
    ehtiyot_qismlar = serializers.SerializerMethodField(read_only=True)
    approved = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "created_by",
            "tarkib_id", "ehtiyot_qismlar_id",
            "tarkib", "ehtiyot_qismlar",
            "nosozliklar_haqida", "bartaraf_etilgan_nosozliklar",
            "image", "akt_file", 
            "status",
            "aniqlangan_vaqti", "bartarafqilingan_vaqti",
            "approved", "created_at",
            "password"
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep = {k: v for k, v in rep.items() if v not in [None, "", [], {}]}

        # 🔹 Shu tarkib bo‘yicha barcha yozuvlar
        all_records = Nosozliklar.objects.filter(tarkib=instance.tarkib).order_by("id")
        first = all_records.first()
        last = all_records.last()

        rep["status"] = instance.status

        # 🔹 Birinchisida aniqlangan_vaqti chiqsin
        if instance.id == first.id:
            rep["aniqlangan_vaqti"] = instance.aniqlangan_vaqti
        else:
            rep.pop("aniqlangan_vaqti", None)

        # 🔹 Oxirgida bartarafqilingan_vaqti + akt_file chiqsin
        if instance.id == last.id and instance.bartarafqilingan_vaqti:
            rep["bartarafqilingan_vaqti"] = instance.bartarafqilingan_vaqti
            if instance.akt_file:
                rep["akt_file"] = instance.akt_file.url
        else:
            rep.pop("bartarafqilingan_vaqti", None)
            rep.pop("akt_file", None)

        return rep

    def get_tarkib(self, obj):
        return str(obj.tarkib) if obj.tarkib else None

    def get_ehtiyot_qismlar(self, obj):
        serializer = EhtiyotQismWithMiqdorSerializer(
            obj.ehtiyot_qismlar.all(),
            many=True,
            context={"parent_instance": obj}
        )
        return serializer.data

    def get_approved(self, obj):
        return "Tasdiqlangan" if obj.approved else "Tasdiqlanmagan"

    def validate(self, attrs):
        request = self.context.get("request")
        password = attrs.pop("password", None)
        if not password or not request.user.check_password(password):
            raise serializers.ValidationError({"password": "Parol noto‘g‘ri."})

        if attrs.get("bartarafqilingan_vaqti") and not attrs.get("akt_file"):
            raise serializers.ValidationError({
                "akt_file": "Bartaraf qilingan vaqt kiritilganda, akt fayl majburiy."
            })
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data["approved"] = True
        validated_data["approved_at"] = timezone.now()
        return super().create(validated_data)
