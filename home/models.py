from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum
from django.core.exceptions import ValidationError


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("monitoring", "Monitoring"),
        ("texnik", "Texnik"),
        ("skladchi", "Skladchi"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    depo = models.ForeignKey(
        "ElektroDepo",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="users"
    )

    def __str__(self):
        return f"{self.username} - {self.role} ({self.depo.qisqacha_nomi if self.depo else 'Depo yo‘q'})"



class TamirTuri(models.Model):
    tamir_nomi = models.CharField(max_length=255)

    # masofa uchun
    tamirlash_davri = models.CharField(
        max_length=50,
        help_text="Masofa bo‘yicha: 5505 ± 10 km"
    )

    # vaqt uchun
    Vaqt_Choices = [
        ("soat", "Soat"),
        ("kun", "Kun"),
        ("oy", "Oy"),
    ]
    tamirlanish_miqdori = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Vaqt soni: masalan, 4"
    )
    tamirlanish_vaqti = models.CharField(
        max_length=10,
        choices=Vaqt_Choices,
        help_text="Vaqt birligi: soat/kun/oy"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Masalan: "To-1 (5000 km, 4 soat)"
        return f"{self.tamir_nomi} ({self.tamirlash_davri}, {self.tamirlanish_miqdori} {self.tamirlanish_vaqti})"


class ElektroDepo(models.Model):
    depo_nomi = models.CharField(max_length=255)
    qisqacha_nomi = models.CharField(max_length=50)
    joylashuvi = models.CharField(max_length=255)
    image = models.ImageField(upload_to="depo/", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.depo_nomi
    



class EhtiyotQismlari(models.Model):
    ehtiyotqism_nomi = models.CharField(max_length=255, unique=True)
    nomenklatura_raqami = models.CharField(max_length=100)
    birligi = models.CharField(
        max_length=50,
        choices=[
            ("dona", "Dona"),
            ("para", "Para"),
            ("metr", "Metr"),
            ("litr", "Litr"),
        ],
        default="dona"
    )
    depo = models.ForeignKey(
        "ElektroDepo",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ehtiyotqism_nomi} ({self.birligi})"

    @property
    def jami_miqdor(self):
        """Kirim va chiqimlarni hisoblab qoldiqni chiqaradi"""
        # Omborga qo‘shilganlar
        qoshilgan = self.ehtiyotqism_hist.aggregate(
            total=Sum('miqdor')
        )['total'] or 0

        # Turli joylarda ishlatilganlar
        ishlatilgan = (
            TexnikKorikEhtiyotQism.objects.filter(ehtiyot_qism=self)
            .aggregate(total=Sum('miqdor'))['total'] or 0
        ) + (
            TexnikKorikEhtiyotQismStep.objects.filter(ehtiyot_qism=self)
            .aggregate(total=Sum('miqdor'))['total'] or 0
        ) + (
            NosozlikEhtiyotQism.objects.filter(ehtiyot_qism=self)
            .aggregate(total=Sum('miqdor'))['total'] or 0
        ) + (
            NosozlikEhtiyotQismStep.objects.filter(ehtiyot_qism=self)
            .aggregate(total=Sum('miqdor'))['total'] or 0
        )
        return qoshilgan - ishlatilgan


class EhtiyotQismHistory(models.Model):
    ehtiyot_qism = models.ForeignKey(
        EhtiyotQismlari,
        on_delete=models.CASCADE,
        related_name="ehtiyotqism_hist"
    )
    miqdor = models.FloatField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ehtiyot_qism.ehtiyotqism_nomi} +{self.miqdor} ({self.created_at:%Y-%m-%d})"


class TexnikKorikEhtiyotQism(models.Model):
    korik = models.ForeignKey("TexnikKorik", on_delete=models.CASCADE, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.FloatField(default=1)

    def save(self, *args, **kwargs):
        if self.ehtiyot_qism and self.miqdor > self.ehtiyot_qism.jami_miqdor:
            raise ValueError(f"❌ Omborda yetarli miqdor yo‘q (qoldiq: {self.ehtiyot_qism.jami_miqdor})")
        super().save(*args, **kwargs)


class TexnikKorikEhtiyotQismStep(models.Model):
    korik_step = models.ForeignKey("TexnikKorikStep", on_delete=models.CASCADE, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.FloatField(default=1)

    def save(self, *args, **kwargs):
        if self.ehtiyot_qism and self.miqdor > self.ehtiyot_qism.jami_miqdor:
            raise ValueError(f"❌ Omborda yetarli miqdor yo‘q (qoldiq: {self.ehtiyot_qism.jami_miqdor})")
        super().save(*args, **kwargs)


class NosozlikEhtiyotQism(models.Model):
    nosozlik = models.ForeignKey("Nosozliklar", on_delete=models.SET_NULL, null=True, blank=True, related_name="ehtiyot_qism_aloqalari")
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.FloatField(default=1)

    def save(self, *args, **kwargs):
        if self.ehtiyot_qism and self.miqdor > self.ehtiyot_qism.jami_miqdor:
            raise ValueError(f"❌ Omborda yetarli miqdor yo‘q (qoldiq: {self.ehtiyot_qism.jami_miqdor})")
        super().save(*args, **kwargs)


class NosozlikEhtiyotQismStep(models.Model):
    step = models.ForeignKey("NosozlikStep", on_delete=models.SET_NULL, null=True, blank=True, related_name="ehtiyot_qismlar_step")
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.FloatField(default=1)

    def save(self, *args, **kwargs):
        if self.ehtiyot_qism and self.miqdor > self.ehtiyot_qism.jami_miqdor:
            raise ValueError(f"❌ Omborda yetarli miqdor yo‘q (qoldiq: {self.ehtiyot_qism.jami_miqdor})")
        super().save(*args, **kwargs)



    
    
    
class HarakatTarkibi(models.Model):
    depo = models.ForeignKey("ElektroDepo", related_name="tarkiblar",
                             on_delete=models.SET_NULL, null=True, blank=True)
    guruhi = models.CharField(max_length=100)
    turi = models.CharField(max_length=100)
    tarkib_raqami = models.CharField(max_length=255, blank=True, null=True)  
    ishga_tushgan_vaqti = models.DateField()
    eksplutatsiya_vaqti = models.BigIntegerField(help_text="km da")
    image = models.ImageField(upload_to="tarkiblar/", blank=True, null=True)

    holati = models.CharField(
        choices=[
            ("Soz_holatda", "Soz_holatda"),
            ("Texnik_korikda", "Texnik_korikda"),
            ("Nosozlikda", "Nosozlikda"),
        ],
        max_length=100,
        default="Soz_holatda"
    )

    # 🔹 versionlash maydonlari
    is_active = models.BooleanField(default=True)  
    pervious_version = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="next_versions"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def update_tarkib_raqami(self):
        """Tarkib raqamini avtomatik yig‘ish."""
        vagonlar = self.vagonlar.order_by("id").values_list("vagon_raqami", flat=True)
        self.tarkib_raqami = "-".join(vagonlar)
        self.save(update_fields=["tarkib_raqami"])

    def __str__(self):
        return f"{self.tarkib_raqami or 'tarkib'} ({'active' if self.is_active else 'archived'})"



class Vagon(models.Model):
    tarkib = models.ForeignKey(
        "HarakatTarkibi", related_name="vagonlar",
        on_delete=models.CASCADE,
    )
    vagon_raqami = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 🔹 Har safar vagon qo‘shilganda/yangilanganda tarkib raqami yangilanadi
        if self.tarkib:
            self.tarkib.update_tarkib_raqami()

    def delete(self, *args, **kwargs):
        tarkib = self.tarkib
        super().delete(*args, **kwargs)
        # 🔹 Vagon o‘chirilib ketganda ham tarkib raqami yangilansin
        if tarkib:
            tarkib.update_tarkib_raqami()

    def __str__(self):
        return f"{self.vagon_raqami} ({self.tarkib.tarkib_raqami})"

    
    
class KunlikYurish(models.Model):
    tarkib = models.ForeignKey(
        HarakatTarkibi,
        on_delete=models.SET_NULL,
        null=True,
        related_name="kunlik_yurishlar"
    )
    sana = models.DateField(default=timezone.now)
    kilometr = models.PositiveIntegerField(help_text="Yurilgan km")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sana", "-id"]

    def __str__(self):
        return f"{self.tarkib.tarkib_raqami} - {self.sana} - {self.kilometr} km"
 


class TexnikKorik(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Texnik_korikda", "Texnik_korikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    tarkib = models.ForeignKey('HarakatTarkibi',on_delete=models.SET_NULL,limit_choices_to={"is_active": True}, null=True, blank=True,related_name="koriklar")
    tamir_turi = models.ForeignKey('TamirTuri',on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)
    ehtiyot_qismlar = models.ManyToManyField("EhtiyotQismlari", through="TexnikKorikEhtiyotQism", blank=True)
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    kirgan_vaqti = models.DateTimeField(default=timezone.now)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    akt_file = models.FileField(upload_to="texnik_korik_aktlar/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """TexnikKorik modelining saqlash mantiqi"""
        # 1️⃣ Kirgan vaqt bo‘lmasa → created_at yoki hozirgi vaqt bilan to‘ldir
        if not self.kirgan_vaqti:
            self.kirgan_vaqti = getattr(self, "created_at", timezone.now())

        # 2️⃣ Yangi yozuv bo‘lsa
        if not self.id:
            self.status = TexnikKorik.Status.JARAYONDA
            # Tarkib holatini avtomatik o‘zgartirish
            if self.tarkib and self.tarkib.holati != "Texnik_korikda":
                self.tarkib.holati = "Texnik_korikda"
                self.tarkib.save()
        else:
            # Eski yozuvda chiqqan vaqtni o‘zgartirmaymiz
            old = TexnikKorik.objects.filter(id=self.id).first()
            if old and old.chiqqan_vaqti:
                self.chiqqan_vaqti = old.chiqqan_vaqti

        # 3️⃣ Agar akt_file mavjud bo‘lsa va yakunlash True bo‘lsa
        if self.akt_file and self.yakunlash:
            self.status = TexnikKorik.Status.BARTARAF_ETILDI
            self.chiqqan_vaqti = timezone.now()
            if self.tarkib:
                self.tarkib.holati = "Soz_holatda"
                self.tarkib.save()

        super().save(*args, **kwargs)


class TexnikKorikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"
    korik = models.ForeignKey(TexnikKorik, on_delete=models.SET_NULL,null=True, blank=True, related_name="steps")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
    "EhtiyotQismlari",
    through="TexnikKorikEhtiyotQismStep",
    blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.JARAYONDA
    )
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to="akt/", null=True, blank=True)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """TexnikKorikStep modelining saqlash mantiqi"""
        #  Kirgan vaqt bo‘lmasa → created_at yoki hozirgi vaqt bilan to‘ldir

        # 2️Agar akt_file mavjud bo‘lsa → step yakunlandi
        if self.akt_file:
            self.status = self.Status.BARTARAF_ETILDI
            self.chiqqan_vaqti = timezone.now()

            if self.korik:
                self.korik.status = TexnikKorik.Status.BARTARAF_ETILDI
                self.korik.chiqqan_vaqti = timezone.now()

                if not self.korik.kirgan_vaqti:
                    self.korik.kirgan_vaqti = getattr(self.korik, "created_at", timezone.now())

                if self.korik.tarkib:
                    self.korik.tarkib.holati = "Soz_holatda"
                    self.korik.tarkib.save()

                self.korik.save()
        else:
            # 3️⃣ Aks holda jarayonda
            self.status = self.Status.JARAYONDA
            if self.korik and self.korik.tarkib.holati != "Texnik_korikda":
                self.korik.tarkib.holati = "Texnik_korikda"
                self.korik.tarkib.save()

        super().save(*args, **kwargs)





class NosozlikTuri(models.Model):
    nosozlik_turi = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nosozlik_turi




class Nosozliklar(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Nosozlikda", "Nosozlikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    ehtiyot_qismlar = models.ManyToManyField(
        "EhtiyotQismlari",
        through="NosozlikEhtiyotQism",
        related_name="nosozliklar",
        blank=True
    )
    tarkib = models.ForeignKey(
        "HarakatTarkibi",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"is_active": True},
        related_name="nosozliklar"
    )
    nosozliklar_haqida = models.ForeignKey(
        "NosozlikTuri",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nosozliklar_main"
    )
    bartaraf_etilgan_nosozliklar = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)
    aniqlangan_vaqti = models.DateTimeField(default=timezone.now)
    bartarafqilingan_vaqti = models.DateTimeField(null=True, blank=True)
    akt_file = models.FileField(upload_to="nosozlik_aktlar/", null=True, blank=True)
    image = models.ImageField(upload_to="nosozlik_images/", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """TexnikKorik save() mantiqiga moslashtirilgan (aniqlangan_vaqti/bartarafqilingan_vaqti avtomatik)"""
        is_new = not self.id  # yangi yozuv ekanligini tekshirish

        # 🔹 Yangi nosozlik bo‘lsa
        if is_new:
            self.status = Nosozliklar.Status.JARAYONDA

            # Agar aniqlangan_vaqti yuborilmagan bo‘lsa, created_at yoki hozirgi vaqtni oladi
            if not self.aniqlangan_vaqti:
                self.aniqlangan_vaqti = timezone.now()

            # Tarkib holatini "Nosozlikda" ga o‘zgartirish
            if self.tarkib and self.tarkib.holati != "Nosozlikda":
                self.tarkib.holati = "Nosozlikda"
                self.tarkib.save()
        else:
            # 🔹 Eski yozuvni olib, mavjud bartarafqilingan_vaqti ni saqlab qolamiz
            old = Nosozliklar.objects.filter(id=self.id).first()
            if old and not self.bartarafqilingan_vaqti:
                self.bartarafqilingan_vaqti = old.bartarafqilingan_vaqti

        # 🔹 Yakunlash shartlari bajarilganda
        if self.akt_file and self.yakunlash:
            self.status = Nosozliklar.Status.BARTARAF_ETILDI

            # Agar bartarafqilingan_vaqti yuborilmagan bo‘lsa — aniqlangan_vaqti yoki created_at dan olsin
            if not self.bartarafqilingan_vaqti:
                self.bartarafqilingan_vaqti = self.aniqlangan_vaqti or self.created_at or timezone.now()

            if self.tarkib:
                self.tarkib.holati = "Soz_holatda"
                self.tarkib.save()

        # 🔹 Agar hali yakunlanmagan, lekin aniqlangan_vaqti yo‘q bo‘lsa — created_at dan olsin
        if not self.aniqlangan_vaqti:
            self.aniqlangan_vaqti = self.created_at or timezone.now()

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.tarkib} - {self.status} ({self.created_by})"

    @property
    def ehtiyot_qismlar_miqdor(self):
        result = []
        for eq in self.ehtiyot_qismlar.all():
            through_obj = NosozlikEhtiyotQism.objects.get(nosozlik=self, ehtiyot_qism=eq)
            result.append(f"{eq.ehtiyotqism_nomi} - {through_obj.miqdor} {eq.birligi}")
        return result


class NosozlikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"

    nosozlik = models.ForeignKey(
        Nosozliklar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="steps"
    )
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
        'EhtiyotQismlari',
        through='NosozlikEhtiyotQismStep',
        blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.JARAYONDA)
    nosozliklar_haqida = models.ForeignKey(
        "NosozlikTuri",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nosozlikla_step"
    )
    bartaraf_etilgan_nosozliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to='nosozlik_step_aktlar/', null=True, blank=True)
    bartaraf_qilingan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """NosozlikStep  saqlash mantiqi"""

        # 2️⃣ Akt_file yuklangan bo‘lsa → stepni yakunlangan deb belgila
        if self.akt_file:
            self.status = self.Status.BARTARAF_ETILDI
            self.bartaraf_qilingan_vaqti = timezone.now()

            if self.nosozlik:
                self.nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
                # Nosozlikdagi aniqlangan_vaqti ham agar yo‘q bo‘lsa yaratilgan vaqt bilan to‘ldiriladi
                if not self.nosozlik.aniqlangan_vaqti:
                    self.nosozlik.aniqlangan_vaqti = getattr(self.nosozlik, "created_at", timezone.now())
                self.nosozlik.bartarafqilingan_vaqti = timezone.now()

                if self.nosozlik.tarkib:
                    self.nosozlik.tarkib.holati = "Soz_holatda"
                    self.nosozlik.tarkib.save()
                self.nosozlik.save()
        else:
            # Aks holda – jarayonda
            self.status = self.Status.JARAYONDA
            if self.nosozlik and self.nosozlik.tarkib.holati != "Nosozlikda":
                self.nosozlik.tarkib.holati = "Nosozlikda"
                self.nosozlik.tarkib.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nosozlik.tarkib} — Step ({self.status})"




    
class NosozlikNotification(models.Model):
    tarkib = models.ForeignKey("HarakatTarkibi", on_delete=models.CASCADE)
    nosozlik_turi = models.CharField(max_length=255)
    count = models.IntegerField(default=1)
    message = models.TextField(blank=True, null=True)
    first_occurrence = models.DateTimeField(null=True, blank=True)
    last_occurrence = models.DateTimeField(auto_now=True)
    seen = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tarkib} - {self.nosozlik_turi} ({self.count} marta)"




class TexnikKorikJadval(models.Model):
    """
    Har oylik texnik ko‘rik jadvali
    """
    tarkib = models.ForeignKey(
        "HarakatTarkibi",
        on_delete=models.CASCADE,
        related_name="korik_jadvallari"
    )
    tamir_turi = models.ForeignKey(
        "TamirTuri",
        on_delete=models.CASCADE,
        related_name="korik_jadvallari"
    )
    sana = models.DateField(help_text="Texnik ko‘rik belgilangan sana")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Texnik ko‘rik jadvali"
        verbose_name_plural = "Texnik ko‘rik jadvallari"
        unique_together = ("tarkib", "sana")  # Bitta tarkib bir kunda faqat bitta reja
        ordering = ["-sana"]

    def __str__(self):
        return f"{self.tarkib.tarkib_raqami} — {self.tamir_turi.tamir_nomi} ({self.sana})"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
        
class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.title}"