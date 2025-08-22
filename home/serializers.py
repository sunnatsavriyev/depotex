from rest_framework import serializers
from .models import TamirTuri, ElektroDepo, EhtiyotQismlari, HarakatTarkibi, TexnikKorik, CustomUser, Nossozliklar
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
    class Meta:
        model = TamirTuri
        fields = "__all__"


class ElektroDepoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElektroDepo
        fields = "__all__"


class EhtiyotQismlariSerializer(serializers.ModelSerializer):
    class Meta:
        model = EhtiyotQismlari
        fields = "__all__"


class HarakatTarkibiSerializer(serializers.ModelSerializer):
    depo = ElektroDepoSerializer(read_only=True)
    depo_id = serializers.PrimaryKeyRelatedField(
        queryset=ElektroDepo.objects.all(), source="depo", write_only=True
    )

    class Meta:
        model = HarakatTarkibi
        fields = "__all__"

class TexnikKorikSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)  # yangi maydon

    class Meta:
        model = TexnikKorik
        fields = '__all__'
    
    def get_created_by(self, obj):
        # obj.user bo'lmaganligi uchun request.user ni olamiz
        request = self.context.get("request")
        return request.user.username if request else None

    def validate(self, data):
        username = data.pop('username')
        password = data.pop('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Username yoki parol xato.")
        return data


class NossozliklarSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Nossozliklar
        fields = '__all__'
    
    def get_created_by(self, obj):
        request = self.context.get("request")
        return request.user.username if request else None

    def validate(self, data):
        username = data.pop('username')
        password = data.pop('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Username yoki parol xato.")
        return data