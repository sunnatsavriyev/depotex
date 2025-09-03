from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar
from django.contrib.auth import get_user_model

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


class HarakatTarkibiSerializer(serializers.ModelSerializer):
    depo = serializers.SlugRelatedField(read_only=True, slug_field="qisqacha_nomi")
    depo_id = serializers.PrimaryKeyRelatedField(
        queryset=ElektroDepo.objects.all(), 
        source="depo"
    )

    created_by = serializers.CharField(source="created_by.username", read_only=True)

    
    ishga_tushgan_vaqti = serializers.DateField(
        format="%d.%m.%Y",
        input_formats=["%d.%m.%Y", "%Y-%m-%d"]  
    )

    class Meta:
        model = HarakatTarkibi
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class TexnikKorikSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    # Read va Write uchun nom / kod orqali
    tamir_turi = serializers.SlugRelatedField(
        queryset=TamirTuri.objects.all(),
        slug_field="tamir_nomi"
    )
    ehtiyot_qism = serializers.SlugRelatedField(
        queryset=EhtiyotQismlari.objects.all(),
        slug_field="ehtiyotqism_nomi"
    )
    tarkib = serializers.SlugRelatedField(
        queryset=HarakatTarkibi.objects.all(),
        slug_field="tarkib_raqami"
    )

    class Meta:
        model = TexnikKorik
        fields = '__all__'

    def create(self, validated_data):
        username = validated_data.pop("username")
        password = validated_data.pop("password")
        user = authenticate(username=username, password=password)
        request_user = self.context["request"].user
        if not user or user != request_user:
            raise serializers.ValidationError("Login qilingan foydalanuvchi bilan mos emas!")
        validated_data["created_by"] = request_user
        return super().create(validated_data)


class NosozliklarSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    ehtiyot_qism = serializers.SlugRelatedField(
        queryset=EhtiyotQismlari.objects.all(),
        slug_field="ehtiyotqism_nomi"
    )
    tarkib = serializers.SlugRelatedField(
        queryset=HarakatTarkibi.objects.all(),
        slug_field="tarkib_raqami"
    )

    class Meta:
        model = Nosozliklar
        fields = '__all__'

    def create(self, validated_data):
        username = validated_data.pop("username")
        password = validated_data.pop("password")
        user = authenticate(username=username, password=password)
        request_user = self.context["request"].user
        if not user or user != request_user:
            raise serializers.ValidationError("Login qilingan foydalanuvchi bilan mos emas!")
        validated_data["created_by"] = request_user
        return super().create(validated_data)