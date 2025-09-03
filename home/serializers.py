from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar
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
    miqdor = serializers.IntegerField()

    class Meta:
        model = EhtiyotQismlari
        fields = ["id", "ehtiyotqism_nomi", "birligi", "miqdor"]
 


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
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class TexnikKorikSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    # INPUT
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

    # OUTPUT
    tarkib = serializers.SerializerMethodField(read_only=True)
    tamir_turi = serializers.SerializerMethodField(read_only=True)
    ehtiyot_qismlar = serializers.SerializerMethodField(read_only=True)
    approved = serializers.SerializerMethodField(read_only=True)

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = TexnikKorik
        fields = [
            "id", "created_by",
            "tarkib_id", "tamir_turi_id", "ehtiyot_qismlar_id",
            "tarkib", "tamir_turi", "ehtiyot_qismlar",
            "kamchiliklar", "comment", "status",
            "kirgan_vaqti", "chiqqan_vaqti",
            "approved", "created_at",
            "password"
        ]

    # GETTERS
    def get_tarkib(self, obj):
        return obj.tarkib.turi if obj.tarkib else None

    def get_tamir_turi(self, obj):
        return obj.tamir_turi.tamir_nomi if obj.tamir_turi else None

    def get_ehtiyot_qismlar(self, obj):
        return [q.ehtiyotqism_nomi for q in obj.ehtiyot_qismlar.all()]

    def get_approved(self, obj):
        return "Tasdiqlangan" if obj.approved else "Tasdiqlanmagan"

    # VALIDATION
    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        password = attrs.pop("password", None)

        if not user or not password:
            raise serializers.ValidationError("Parol kiritilishi shart.")

        if not user.check_password(password):
            raise serializers.ValidationError("Parol noto‘g‘ri.")

        attrs["created_by"] = user
        attrs["approved"] = True
        attrs["approved_at"] = timezone.now()

        tarkib = attrs.get("tarkib")

        # Shu tarkib uchun oxirgi yozuvni topamiz
        last_record = (
            TexnikKorik.objects.filter(tarkib=tarkib)
            .order_by("-created_at")
            .first()
        )

        if last_record:
            # ❗️Agar avvalgi yozuv bo‘lsa, tamir_turi avtomatik oxirgidan olinadi
            attrs["tamir_turi"] = last_record.tamir_turi

        return attrs

    # OUTPUT’ni tozalash
    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # ❌ approved_at umuman chiqmasin
        rep.pop("approved_at", None)

        # ✅ chiqqan_vaqti faqat BARTARAF_ETILDI va comment bo‘lsa chiqsin
        if instance.status != TexnikKorik.Status.BARTARAF_ETILDI or not instance.comment:
            rep.pop("chiqqan_vaqti", None)

        # ❌ bo‘sh qiymatlarni chiqarib tashlash
        return {k: v for k, v in rep.items() if v not in [None, "", []]}




class NosozliklarSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    # --- INPUT ---
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

    # --- OUTPUT ---
    tarkib = serializers.SerializerMethodField(read_only=True)
    tamir_turi = serializers.SerializerMethodField(read_only=True)  # 👈 qo‘shildi
    ehtiyot_qismlar = serializers.SerializerMethodField(read_only=True)
    approved = serializers.SerializerMethodField(read_only=True)

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Nosozliklar
        fields = [
            "id", "created_by",
            "tarkib_id", "ehtiyot_qismlar_id",
            "tarkib", "tamir_turi", "ehtiyot_qismlar",   # 👈 tamir_turi ham chiqadi
            "nosozliklar", "comment", "status",
            "aniqlangan_vaqti", "bartarafqilingan_vaqti",
            "approved", "created_at",
            "password"
        ]

    # --- GETTERS ---
    def get_tarkib(self, obj):
        return obj.tarkib.turi if obj.tarkib else None

    def get_tamir_turi(self, obj):
        """
        Har doim shu tarkib uchun oxirgi TexnikKorik yozuvining tamir_turi ni chiqaradi.
        """
        last_korik = (
            TexnikKorik.objects.filter(tarkib=obj.tarkib)
            .order_by("-created_at")
            .first()
        )
        return last_korik.tamir_turi.tamir_nomi if last_korik and last_korik.tamir_turi else None

    def get_ehtiyot_qismlar(self, obj):
        return [q.ehtiyotqism_nomi for q in obj.ehtiyot_qismlar.all()]

    def get_approved(self, obj):
        return "Tasdiqlangan" if obj.approved else "Tasdiqlanmagan"

    # --- VALIDATION ---
    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        password = attrs.pop("password", None)

        if not user or not password:
            raise serializers.ValidationError("Parol kiritilishi shart.")

        if not user.check_password(password):
            raise serializers.ValidationError("Parol noto‘g‘ri.")

        attrs["created_by"] = user
        attrs["approved"] = True
        attrs["approved_at"] = timezone.now()

        # Bartaraf etilgan bo‘lsa, comment majburiy
        if attrs.get("status") == Nosozliklar.Status.BARTARAF_ETILDI and not attrs.get("comment"):
            raise serializers.ValidationError("Bartaraf etilgan nosozlik uchun comment majburiy.")

        return attrs

    # --- OUTPUT TOZALASH ---
    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # ❌ approved_at chiqmasin
        rep.pop("approved_at", None)

        # ✅ aniqlangan_vaqti faqat birinchi yozuvda chiqadi
        first_record = (
            Nosozliklar.objects.filter(tarkib=instance.tarkib)
            .order_by("created_at")
            .first()
        )
        if not first_record or first_record.id != instance.id:
            rep.pop("aniqlangan_vaqti", None)

        # ✅ bartarafqilingan_vaqti faqat status = BARTARAF_ETILDI bo‘lsa chiqsin
        if instance.status != Nosozliklar.Status.BARTARAF_ETILDI:
            rep.pop("bartarafqilingan_vaqti", None)

        # ❌ Bo‘sh qiymatlarni chiqarib tashlash
        return {k: v for k, v in rep.items() if v not in [None, "", []]}
